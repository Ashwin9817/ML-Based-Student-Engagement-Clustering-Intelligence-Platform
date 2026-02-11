from flask import Blueprint, jsonify, request
from db import get_db

RECOMMENDATION_MIN_SCORE = 0.35
RECOMMENDATION_MIN_GAP = 0.08
NEW_STUDENT_DAYS = 7
MIN_ATTEMPTS_FOR_RECO = 3
INACTIVE_DAYS = 21
FOCUS_SKILL_MIN = 0.4

mentor_bp = Blueprint("mentor", __name__, url_prefix="/mentor")

def _normalize_score(score):
    if score is None:
        return 0.0
    return score / 100.0 if score > 1 else score

def _score_to_cluster(score):
    if score >= 0.7:
        return "CONSISTENT"
    if score >= 0.55:
        return "IMPROVING"
    if score >= 0.4:
        return "DROPPING"
    return "LOW"

def _compute_domain_scores(cursor, student_id):
    cursor.execute("""
        SELECT domain, proficiency_pct
        FROM skill_profiles
        WHERE student_id = %s
    """, (student_id,))
    skills = cursor.fetchall()
    skill_map = {s["domain"]: s["proficiency_pct"] for s in skills}

    # Fallback: derive skill proficiency from attempts if skill_profiles is empty
    if not skill_map:
        cursor.execute("""
            SELECT a.domain, AVG(aa.score) AS proficiency_pct
            FROM assessment_attempts aa
            JOIN assessments a ON a.assessment_id = aa.assessment_id
            WHERE aa.student_id = %s
            GROUP BY a.domain
        """, (student_id,))
        derived = cursor.fetchall()
        skill_map = {s["domain"]: s["proficiency_pct"] for s in derived}

    cursor.execute("""
        SELECT d.name AS domain, s.name AS skill, w.weight
        FROM domain_skill_weights w
        JOIN domains d ON d.domain_id = w.domain_id
        JOIN skills s ON s.skill_id = w.skill_id
    """)
    weight_rows = cursor.fetchall()

    domain_scores = {}
    domain_weight_sum = {}
    for row in weight_rows:
        domain = row["domain"]
        skill = row["skill"]
        weight = row["weight"]
        proficiency = skill_map.get(skill)
        if proficiency is None:
            continue
        domain_scores[domain] = domain_scores.get(domain, 0.0) + (proficiency / 100.0) * weight
        domain_weight_sum[domain] = domain_weight_sum.get(domain, 0.0) + weight

    for domain in list(domain_scores.keys()):
        total_weight = domain_weight_sum.get(domain, 0.0)
        domain_scores[domain] = (domain_scores[domain] / total_weight) if total_weight > 0 else 0.0

    cursor.execute("DELETE FROM domain_likelihood WHERE student_id=%s", (student_id,))
    for domain, score in domain_scores.items():
        cursor.execute("""
            INSERT INTO domain_likelihood (student_id, domain, likelihood_score)
            VALUES (%s, %s, %s)
        """, (student_id, domain, score))

    sorted_scores = sorted(
        [{"domain": d, "likelihood_score": s} for d, s in domain_scores.items()],
        key=lambda x: x["likelihood_score"],
        reverse=True
    )
    return sorted_scores


def _classify_recommendation(cursor, student, sorted_scores, attempt_stats):
    total_attempts = attempt_stats.get("total_attempts") or 0
    last_attempt = attempt_stats.get("last_attempt")

    cursor.execute("SELECT DATEDIFF(CURDATE(), %s) AS days_since_join", (student["join_date"],))
    days_since_join = (cursor.fetchone() or {}).get("days_since_join")

    if (
        days_since_join is not None
        and days_since_join <= NEW_STUDENT_DAYS
        and total_attempts < MIN_ATTEMPTS_FOR_RECO
    ):
        return "NEW", None
    if last_attempt is None:
        return "NOT_ENGAGED", None

    cursor.execute("SELECT DATEDIFF(CURDATE(), %s) AS days_since_attempt", (last_attempt,))
    days_since_attempt = (cursor.fetchone() or {}).get("days_since_attempt")
    if days_since_attempt is not None and days_since_attempt >= INACTIVE_DAYS:
        return "NOT_ENGAGED", None

    if len(sorted_scores) == 0:
        return "CONFUSED", None

    top = sorted_scores[0]
    second = sorted_scores[1] if len(sorted_scores) > 1 else {"likelihood_score": 0}
    gap = top["likelihood_score"] - second["likelihood_score"]
    if top["likelihood_score"] >= RECOMMENDATION_MIN_SCORE and gap >= RECOMMENDATION_MIN_GAP:
        return "RECOMMENDED", top["domain"]
    return "CONFUSED", top["domain"]

def _goal_weighted_score(cursor, student_id, goal_name):
    cursor.execute("""
        SELECT s.name AS skill, w.weight, sp.proficiency_pct
        FROM domain_skill_weights w
        JOIN domains d ON d.domain_id = w.domain_id
        JOIN skills s ON s.skill_id = w.skill_id
        LEFT JOIN skill_profiles sp
          ON sp.student_id = %s AND sp.domain = s.name
        WHERE d.name = %s
        ORDER BY w.weight DESC
    """, (student_id, goal_name))
    rows = cursor.fetchall()
    if not rows:
        return 0.0, None, []

    total_weight = 0.0
    weighted_sum = 0.0
    focus_skills = []
    for row in rows:
        proficiency = row["proficiency_pct"] or 0.0
        weight = row["weight"] or 0.0
        focus_skills.append({
            "skill": row["skill"],
            "weight": weight,
            "proficiency_pct": proficiency,
        })
        total_weight += weight
        weighted_sum += (proficiency / 100.0) * weight

    score = weighted_sum / total_weight if total_weight > 0 else 0.0
    top_skill_proficiency = (rows[0]["proficiency_pct"] or 0.0) / 100.0
    return score, top_skill_proficiency, focus_skills

def _avg_engagement_score(cursor, student_id):
    cursor.execute("""
        SELECT AVG(engagement_score) AS avg_score
        FROM engineered_features
        WHERE student_id = %s
    """, (student_id,))
    avg_score = (cursor.fetchone() or {}).get("avg_score")
    return _normalize_score(avg_score or 0.0)

@mentor_bp.route("/dashboard/<int:mentor_id>", methods=["GET"])
def mentor_dashboard(mentor_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch mentor's students
    cursor.execute("""
        SELECT s.student_id, s.name, s.goal_state, s.selected_goal, s.join_date
        FROM mentor_student_map msm
        JOIN students s ON msm.student_id = s.student_id
        WHERE msm.mentor_id = %s
    """, (mentor_id,))
    students = cursor.fetchall()

    result = {
        "goal_set": {},
        "goal_not_set": {
            "likelihood_domains": {},
            "not_decided": {
                "confused": [],
                "new": [],
                "not_engaged": []
            }
        }
    }

    for student in students:
        sid = student["student_id"]

        if student["goal_state"] == "SET":
            goal = student.get("selected_goal") or "Unknown"
            score, top_skill_proficiency, focus_skills = _goal_weighted_score(
                cursor, sid, goal
            )
            overall_cluster = _score_to_cluster(score)
            if top_skill_proficiency is not None and top_skill_proficiency < FOCUS_SKILL_MIN:
                overall_cluster = "LOW"

            if goal not in result["goal_set"]:
                result["goal_set"][goal] = []
            result["goal_set"][goal].append({
                "student_id": sid,
                "name": student["name"],
                "goal": student["selected_goal"],
                "overall_cluster": overall_cluster,
                "overall_score": score,
                "focus_skills": focus_skills
            })

        else:
            cursor.execute("""
                SELECT COUNT(*) AS total_attempts,
                       MAX(attempt_date) AS last_attempt
                FROM assessment_attempts
                WHERE student_id = %s
            """, (sid,))
            attempt_stats = cursor.fetchone() or {"total_attempts": 0, "last_attempt": None}

            likelihoods = _compute_domain_scores(cursor, sid)
            status, top_domain = _classify_recommendation(cursor, student, likelihoods, attempt_stats)
            overall_score = None
            overall_cluster = None
            if status != "NEW":
                overall_score = _avg_engagement_score(cursor, sid)
                overall_cluster = _score_to_cluster(overall_score)

            payload = {
                "student_id": sid,
                "name": student["name"],
                "predicted_domains": likelihoods[:3],
                "status": status,
                "top_domain": top_domain,
                "overall_cluster": overall_cluster,
                "overall_score": overall_score
            }

            # Likelihood domains are first-class buckets for not-set students.
            # Keep truly undecidable students in not_decided buckets.
            if status == "RECOMMENDED" and top_domain:
                bucket = result["goal_not_set"]["likelihood_domains"].setdefault(top_domain, [])
                bucket.append(payload)
            elif status == "NEW":
                result["goal_not_set"]["not_decided"]["new"].append(payload)
            elif status == "NOT_ENGAGED":
                result["goal_not_set"]["not_decided"]["not_engaged"].append(payload)
            else:
                # Confused means top domains are close; still expose top domain bucket
                # if one exists so mentor can inspect by likely pathway.
                if top_domain:
                    bucket = result["goal_not_set"]["likelihood_domains"].setdefault(top_domain, [])
                    bucket.append(payload)
                result["goal_not_set"]["not_decided"]["confused"].append(payload)

    db.commit()
    db.close()
    return jsonify(result)
