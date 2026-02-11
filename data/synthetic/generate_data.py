import random
import mysql.connector
from faker import Faker
from datetime import datetime, timedelta
import numpy as np
import hashlib

fake = Faker()

# ------------------ DB CONNECTION ------------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="##IstHISSqL321",
    database="student_engagement_ai"
)
cursor = db.cursor()

# ------------------ CONSTANTS ------------------
STUDENT_COUNT = 150
MENTOR_COUNT = 5
RESET_DB = False
RESET_ANALYTICS = True

# ------------------ HELPERS ------------------
def random_date(start_days_ago=180):
    return datetime.now().date() - timedelta(days=random.randint(1, start_days_ago))

def hash_pass():
    return hashlib.sha256("password123".encode()).hexdigest()

# ------------------ LOAD SKILLS ------------------
def load_skills():
    cursor.execute("SELECT name FROM skills ORDER BY name")
    return [row[0] for row in cursor.fetchall()]

# ------------------ RESET DB ------------------
def reset_db():
    # Order matters due to FK constraints; TRUNCATE resets auto-increment
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    cursor.execute("TRUNCATE TABLE assessment_attempts")
    cursor.execute("TRUNCATE TABLE assessment_levels")
    cursor.execute("TRUNCATE TABLE assessments")
    cursor.execute("TRUNCATE TABLE engagement_clusters")
    cursor.execute("TRUNCATE TABLE engineered_features")
    cursor.execute("TRUNCATE TABLE engagement_scores")
    cursor.execute("TRUNCATE TABLE skill_profiles")
    cursor.execute("TRUNCATE TABLE domain_likelihood")
    cursor.execute("TRUNCATE TABLE student_learning_state")
    cursor.execute("TRUNCATE TABLE action_outputs")
    cursor.execute("TRUNCATE TABLE mentor_student_map")
    cursor.execute("TRUNCATE TABLE students")
    cursor.execute("TRUNCATE TABLE mentors")
    cursor.execute("TRUNCATE TABLE users")
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    db.commit()

def reset_analytics():
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    cursor.execute("TRUNCATE TABLE assessment_attempts")
    cursor.execute("TRUNCATE TABLE assessment_levels")
    cursor.execute("TRUNCATE TABLE assessments")
    cursor.execute("TRUNCATE TABLE engagement_clusters")
    cursor.execute("TRUNCATE TABLE engineered_features")
    cursor.execute("TRUNCATE TABLE engagement_scores")
    cursor.execute("TRUNCATE TABLE skill_profiles")
    cursor.execute("TRUNCATE TABLE domain_likelihood")
    cursor.execute("TRUNCATE TABLE student_learning_state")
    cursor.execute("TRUNCATE TABLE action_outputs")
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    db.commit()

# ------------------ INSERT ASSESSMENTS ------------------
def get_or_create_assessment(domain):
    cursor.execute("SELECT assessment_id FROM assessments WHERE domain=%s", (domain,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("""
        INSERT INTO assessments (domain, max_level, weight, max_score)
        VALUES (%s, %s, %s, %s)
    """, (domain, 10, round(random.uniform(0.8, 1.2), 2), 100))
    return cursor.lastrowid

# ------------------ INSERT ASSESSMENTS ------------------
def insert_assessments(skills):
    for domain in skills:
        assessment_id = get_or_create_assessment(domain)
        for level in range(1, 11):
            difficulty = "EASY" if level <= 3 else "MEDIUM" if level <= 7 else "HARD"
            max_score = 100
            cursor.execute("""
                REPLACE INTO assessment_levels (assessment_id, level, difficulty, max_score)
                VALUES (%s, %s, %s, %s)
            """, (assessment_id, level, difficulty, max_score))
    db.commit()

# ------------------ INSERT USERS ------------------
def insert_users():
    students = []
    mentors = []

    def insert_user(role):
        while True:
            email = fake.email()
            try:
                cursor.execute("""
                    INSERT INTO users (email, password_hash, role)
                    VALUES (%s, %s, %s)
                """, (email, hash_pass(), role))
                return cursor.lastrowid, email
            except mysql.connector.errors.IntegrityError:
                # Duplicate email, retry with a new one
                continue

    # Mentors
    for _ in range(MENTOR_COUNT):
        mentor_id, _ = insert_user("MENTOR")
        cursor.execute("INSERT INTO mentors (mentor_id, name) VALUES (%s, %s)",
                       (mentor_id, fake.name()))
        mentors.append(mentor_id)

    # Students
    for _ in range(STUDENT_COUNT):
        student_id, _ = insert_user("STUDENT")

        goal_state = random.choice(["SET", "NOT_SET"])
        selected_goal = random.choice(["AI/ML", "Fullstack", "Java", "Data"]) if goal_state == "SET" else None

        cursor.execute("""
            INSERT INTO students (student_id, name, goal_state, selected_goal, join_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            student_id,
            fake.name(),
            goal_state,
            selected_goal,
            random_date()
        ))
        students.append(student_id)

    db.commit()
    return students, mentors

def create_mentors_only():
    mentors = []
    while len(mentors) < MENTOR_COUNT:
        email = fake.email()
        try:
            cursor.execute("""
                INSERT INTO users (email, password_hash, role)
                VALUES (%s, %s, %s)
            """, (email, hash_pass(), "MENTOR"))
            mentor_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO mentors (mentor_id, name) VALUES (%s, %s)",
                (mentor_id, fake.name()),
            )
            mentors.append(mentor_id)
        except mysql.connector.errors.IntegrityError:
            continue
    db.commit()
    return mentors

def get_existing_students_and_mentors():
    cursor.execute("SELECT student_id FROM students ORDER BY student_id")
    students = [row[0] for row in cursor.fetchall()]
    cursor.execute("SELECT mentor_id FROM mentors ORDER BY mentor_id")
    mentors = [row[0] for row in cursor.fetchall()]
    return students, mentors

# ------------------ MAP MENTORS TO STUDENTS ------------------
def map_mentors_students(students, mentors):
    if not mentors:
        return
    for student in students:
        mentor = random.choice(mentors)
        cursor.execute("""
            INSERT INTO mentor_student_map (mentor_id, student_id)
            VALUES (%s, %s)
        """, (mentor, student))
    db.commit()

# ------------------ GENERATE ATTEMPTS ------------------
def generate_attempts(students, behavior_map):
    skills = load_skills()
    if not skills:
        return
    cursor.execute(
        "SELECT assessment_id, domain FROM assessments WHERE domain IN (%s)" %
        ",".join(["%s"] * len(skills)),
        tuple(skills)
    )
    assessments = cursor.fetchall()

    for student_id in students:
        behavior_type = behavior_map.get(student_id, "CONFUSED")

        if behavior_type == "INACTIVE":
            continue

        level_cap = {
            "CONSISTENT": random.randint(8, 10),
            "IMPROVING": random.randint(6, 9),
            "DROPPING": random.randint(3, 6),
            "CONFUSED": random.randint(4, 8),
        }[behavior_type]

        for assessment_id, domain in assessments:
            start_date = datetime.now() - timedelta(days=random.randint(20, 140))
            cumulative_days = 0
            for level in range(1, level_cap + 1):
                # ensure strict chronological order of levels
                cumulative_days += random.randint(1, 4)
                base_dt = start_date + timedelta(days=cumulative_days)
                # Fail attempt
                fail_chance = {
                    "CONSISTENT": 0.1,
                    "IMPROVING": 0.2,
                    "DROPPING": 0.35,
                    "CONFUSED": 0.25
                }[behavior_type]
                if random.random() < fail_chance:
                    fail_score = round(random.uniform(20, 50), 2)
                    cursor.execute("""
                        INSERT INTO assessment_attempts
                        (student_id, assessment_id, level_attempted, score, time_spent_min, attempt_date, attempt_datetime, pass_fail)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        student_id,
                        assessment_id,
                        level,
                        fail_score,
                        round(random.uniform(10, 40), 2),
                        base_dt.date(),
                        base_dt,
                        "FAIL"
                    ))

                # Pass attempt
                pass_score = {
                    "CONSISTENT": round(random.uniform(80, 98), 2),
                    "IMPROVING": round(random.uniform(65, 90), 2),
                    "DROPPING": round(random.uniform(55, 80), 2),
                    "CONFUSED": round(random.uniform(50, 85), 2),
                }[behavior_type]
                cursor.execute("""
                    INSERT INTO assessment_attempts
                    (student_id, assessment_id, level_attempted, score, time_spent_min, attempt_date, attempt_datetime, pass_fail)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    student_id,
                    assessment_id,
                    level,
                    pass_score,
                    round(random.uniform(15, 60), 2),
                    base_dt.date(),
                    base_dt + timedelta(hours=2),
                    "PASS"
                ))

    db.commit()

def generate_skill_profiles(students):
    # Build proficiency from attempts: avg score per domain, scaled to 0-100
    cursor.execute("""
        SELECT a.domain, aa.student_id, AVG(aa.score) AS avg_score
        FROM assessment_attempts aa
        JOIN assessments a ON a.assessment_id = aa.assessment_id
        GROUP BY aa.student_id, a.domain
    """)
    rows = cursor.fetchall()
    cursor.execute("TRUNCATE TABLE skill_profiles")
    for domain, student_id, avg_score in rows:
        cursor.execute("""
            INSERT INTO skill_profiles (student_id, domain, proficiency_pct)
            VALUES (%s, %s, %s)
        """, (student_id, domain, round(min(avg_score, 100), 2)))
    db.commit()

# ------------------ MAIN ------------------
if __name__ == "__main__":
    print("Generating synthetic data...")
    if RESET_DB:
        reset_db()
    if RESET_ANALYTICS:
        reset_analytics()
    skills = load_skills()
    if not skills:
        raise RuntimeError("No skills found. Populate the skills table first.")
    insert_assessments(skills)
    if RESET_DB:
        students, mentors = insert_users()
        map_mentors_students(students, mentors)
    else:
        students, mentors = get_existing_students_and_mentors()
        if not students:
            students, mentors = insert_users()
            map_mentors_students(students, mentors)
        elif not mentors:
            # If mentors table is empty, create mentors and map existing students.
            mentors = create_mentors_only()
            map_mentors_students(students, mentors)

    # Balance behavior types across students for clearer clusters
    behavior_types = ["CONSISTENT", "IMPROVING", "DROPPING", "CONFUSED", "INACTIVE"]
    per_type = len(students) // len(behavior_types)
    remainder = len(students) % len(behavior_types)
    behaviors = []
    for b in behavior_types:
        behaviors.extend([b] * per_type)
    behaviors.extend(random.sample(behavior_types, remainder))
    random.shuffle(behaviors)
    behavior_map = {sid: behaviors[i] for i, sid in enumerate(students)}

    generate_attempts(students, behavior_map)
    generate_skill_profiles(students)
    print("Synthetic data generation complete.")
