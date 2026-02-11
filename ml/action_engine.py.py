import mysql.connector
import pandas as pd

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="##IstHISSqL321",
    database="student_engagement_ai"
)

query = """
SELECT 
    s.student_id,
    s.name,
    s.goal_state,
    ec.domain,
    ec.cluster,
    dl.likelihood_score,
    es.engagement_score
FROM students s
JOIN engagement_clusters ec ON s.student_id = ec.student_id
LEFT JOIN domain_likelihood dl 
    ON ec.student_id = dl.student_id AND ec.domain = dl.domain
JOIN engagement_scores es ON s.student_id = es.student_id
"""

df = pd.read_sql(query, db)

def decide_actions(row):
    goal = row["goal_state"]
    cluster = row["cluster"]
    likelihood = row["likelihood_score"] or 0
    engagement = row["engagement_score"]

    if goal == "SET":
        if cluster == "CONSISTENT":
            return ("NONE", "HARDER", "NONE")
        if cluster == "IMPROVING":
            return ("MONITOR", "SAME", "MOTIVATIONAL")
        if cluster == "DROPPING":
            return ("CHECK_IN", "SIMPLIFY", "GOAL_REMINDER")
        if cluster == "LOW":
            return ("URGENT_INTERVENTION", "RESET", "ESCALATE")

    else:  # GOAL NOT SET
        if likelihood >= 0.75:
            return ("MONITOR", "SAME", "GOAL_REMINDER")
        if likelihood >= 0.5:
            return ("CHECK_IN", "SIMPLIFY", "MOTIVATIONAL")
        return ("URGENT_INTERVENTION", "RESET", "ESCALATE")

df[["mentor_action", "content_action", "nudge_action"]] = df.apply(
    decide_actions, axis=1, result_type="expand"
)

print(df[[
    "student_id",
    "name",
    "domain",
    "mentor_action",
    "content_action",
    "nudge_action"
]])
