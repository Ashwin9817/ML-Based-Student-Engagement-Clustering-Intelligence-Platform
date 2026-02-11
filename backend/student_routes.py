from flask import Blueprint, jsonify, request
from db import get_db

RECOMMENDATION_MIN_SCORE = 0.35
RECOMMENDATION_MIN_GAP = 0.08
NEW_STUDENT_DAYS = 7
MIN_ATTEMPTS_FOR_RECO = 3
INACTIVE_DAYS = 21

student_bp = Blueprint("student", __name__, url_prefix="/student")

@student_bp.route("/dashboard/<int:student_id>", methods=["GET"])
def student_dashboard(student_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Get student info
    cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
    student = cursor.fetchone()
    if not student:
        db.close()
        return jsonify({"error": "Student not found"}), 404

    # Attempt stats for recommendation gating
    cursor.execute("""
        SELECT COUNT(*) AS total_attempts,
               MAX(attempt_date) AS last_attempt
        FROM assessment_attempts
        WHERE student_id = %s
    """, (student_id,))
    attempt_stats = cursor.fetchone() or {"total_attempts": 0, "last_attempt": None}

    # Engagement clusters
    cursor.execute("""
        SELECT domain, cluster, confidence
        FROM engagement_clusters
        WHERE student_id = %s
    """, (student_id,))
    engagement = cursor.fetchall()

    # Skill profile
    cursor.execute("""
        SELECT domain, proficiency_pct
        FROM skill_profiles
        WHERE student_id = %s
    """, (student_id,))
    skills = cursor.fetchall()

    cursor.execute("""
        SELECT a.domain,
               MAX(a.max_level) AS max_level,
               COALESCE(MAX(aa.level_attempted), 0) AS current_level
        FROM assessments a
        LEFT JOIN assessment_attempts aa
          ON aa.assessment_id = a.assessment_id
         AND aa.student_id = %s
        GROUP BY a.domain
    """, (student_id,))
    skill_levels = cursor.fetchall()

    goal_skills = []
    goal_focus_score = None
    if student.get("goal_state") == "SET" and student.get("selected_goal"):
        cursor.execute("""
            SELECT s.name AS skill, w.weight, sp.proficiency_pct
            FROM domain_skill_weights w
            JOIN domains d ON d.domain_id = w.domain_id
            JOIN skills s ON s.skill_id = w.skill_id
            LEFT JOIN skill_profiles sp
              ON sp.student_id = %s AND sp.domain = s.name
            WHERE d.name = %s
            ORDER BY w.weight DESC
        """, (student_id, student["selected_goal"]))
        rows = cursor.fetchall()
        total_weight = 0.0
        weighted_sum = 0.0
        for row in rows:
            proficiency = row["proficiency_pct"] or 0.0
            weight = row["weight"] or 0.0
            goal_skills.append({
                "skill": row["skill"],
                "weight": weight,
                "proficiency_pct": proficiency,
            })
            total_weight += weight
            weighted_sum += (proficiency / 100.0) * weight
        if total_weight > 0:
            goal_focus_score = weighted_sum / total_weight

    recommendations = []
    recommendation_status = None
    top_domain = None

    if student.get("goal_state") != "SET":
        # Build skill -> proficiency map
        skill_map = {s["domain"]: s["proficiency_pct"] for s in skills}

        # Fetch domain-skill weights
        cursor.execute("""
            SELECT d.name AS domain, s.name AS skill, w.weight
            FROM domain_skill_weights w
            JOIN domains d ON d.domain_id = w.domain_id
            JOIN skills s ON s.skill_id = w.skill_id
        """)
        weight_rows = cursor.fetchall()

        # Compute weighted scores per domain
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
            if total_weight > 0:
                domain_scores[domain] = domain_scores[domain] / total_weight
            else:
                domain_scores[domain] = 0.0

        # Persist likelihoods for mentor views
        cursor.execute("DELETE FROM domain_likelihood WHERE student_id=%s", (student_id,))
        for domain, score in domain_scores.items():
            cursor.execute("""
                INSERT INTO domain_likelihood (student_id, domain, likelihood_score)
                VALUES (%s, %s, %s)
            """, (student_id, domain, score))
        db.commit()

        # Sort recommendations
        sorted_scores = sorted(
            [{"domain": d, "likelihood_score": s} for d, s in domain_scores.items()],
            key=lambda x: x["likelihood_score"],
            reverse=True
        )
        recommendations = sorted_scores[:3]

        # Determine recommendation status
        total_attempts = attempt_stats.get("total_attempts") or 0
        last_attempt = attempt_stats.get("last_attempt")

        cursor.execute("SELECT DATEDIFF(CURDATE(), %s) AS days_since_join", (student["join_date"],))
        days_since_join = (cursor.fetchone() or {}).get("days_since_join")

        if (
            days_since_join is not None
            and days_since_join <= NEW_STUDENT_DAYS
            and total_attempts < MIN_ATTEMPTS_FOR_RECO
        ):
            recommendation_status = "NEW"
        elif last_attempt is None:
            recommendation_status = "NOT_ENGAGED"
        else:
            cursor.execute("SELECT DATEDIFF(CURDATE(), %s) AS days_since_attempt", (last_attempt,))
            days_since_attempt = (cursor.fetchone() or {}).get("days_since_attempt")
            if days_since_attempt is not None and days_since_attempt >= INACTIVE_DAYS:
                recommendation_status = "NOT_ENGAGED"
            else:
                if len(sorted_scores) == 0:
                    recommendation_status = "CONFUSED"
                else:
                    top = sorted_scores[0]
                    second = sorted_scores[1] if len(sorted_scores) > 1 else {"likelihood_score": 0}
                    gap = top["likelihood_score"] - second["likelihood_score"]
                    if top["likelihood_score"] >= RECOMMENDATION_MIN_SCORE and gap >= RECOMMENDATION_MIN_GAP:
                        recommendation_status = "RECOMMENDED"
                        top_domain = top["domain"]
                    else:
                        recommendation_status = "CONFUSED"

    db.close()

    return jsonify({
        "student": student,
        "engagement": engagement,
        "skills": skills,
        "skill_levels": skill_levels,
        "recommendations": recommendations,
        "recommendation_status": recommendation_status,
        "top_domain": top_domain,
        "goal_skills": goal_skills,
        "goal_focus_score": goal_focus_score
    })


@student_bp.route("/domains", methods=["GET"])
def list_goal_domains():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT name FROM domains ORDER BY name")
    domains = [d["name"] for d in cursor.fetchall()]
    db.close()
    return jsonify({"domains": domains})


@student_bp.route("/goal/<int:student_id>", methods=["POST"])
def set_student_goal(student_id):
    data = request.json or {}
    selected_goal = data.get("selected_goal")
    if not selected_goal:
        return jsonify({"error": "selected_goal is required"}), 400

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT 1 FROM domains WHERE name=%s", (selected_goal,))
    if not cursor.fetchone():
        db.close()
        return jsonify({"error": "Invalid goal"}), 400

    cursor.execute("""
        UPDATE students
        SET goal_state = 'SET', selected_goal = %s
        WHERE student_id = %s
    """, (selected_goal, student_id))
    db.commit()
    db.close()

    return jsonify({"status": "ok", "selected_goal": selected_goal})


@student_bp.route("/skill-history/<int:student_id>", methods=["GET"])
def skill_history(student_id):
    domain = request.args.get("domain")
    if not domain:
        return jsonify({"error": "domain is required"}), 400

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            aa.attempt_datetime,
            aa.attempt_id,
            aa.level_attempted,
            aa.score,
            COALESCE(al.max_score, a.max_score) AS max_score,
            al.difficulty,
            aa.pass_fail
        FROM assessment_attempts aa
        JOIN assessments a ON a.assessment_id = aa.assessment_id
        LEFT JOIN assessment_levels al
          ON al.assessment_id = aa.assessment_id
         AND al.level = aa.level_attempted
        WHERE aa.student_id = %s AND a.domain = %s
        ORDER BY aa.attempt_datetime ASC, aa.attempt_id ASC
    """, (student_id, domain))
    rows = cursor.fetchall()
    db.close()

    timeline = []
    for row in rows:
        max_score = row.get("max_score") if row.get("max_score") is not None else 100
        score = row.get("score") or 0.0
        pass_flag = row.get("pass_fail")
        if pass_flag is None:
            passed = score >= (0.6 * max_score)
        else:
            passed = pass_flag == "PASS"
        pct = (score / max_score) * 100 if max_score else 0
        timeline.append({
            "attempt_date": row.get("attempt_datetime"),
            "level_attempted": row.get("level_attempted"),
            "score": score,
            "max_score": max_score,
            "difficulty": row.get("difficulty"),
            "passed": passed,
            "score_pct": round(pct, 1),
        })

    return jsonify({"domain": domain, "timeline": timeline})
