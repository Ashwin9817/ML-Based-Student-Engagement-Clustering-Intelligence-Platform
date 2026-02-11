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
    student_id,
    domain,
    cluster
FROM engagement_clusters
"""

df = pd.read_sql(query, db)

def decide_action(cluster):
    if cluster == "CONSISTENT":
        return "HARDER", "High engagement detected"
    if cluster == "IMPROVING":
        return "SAME", "Positive trend"
    if cluster == "DROPPING":
        return "SIMPLIFY", "Engagement declining"
    return "RESET", "Low engagement"

df[["content_action", "reason"]] = df["cluster"].apply(
    lambda x: pd.Series(decide_action(x))
)

cursor = db.cursor()

for _, row in df.iterrows():
    cursor.execute("""
        INSERT INTO action_outputs
        (student_id, domain, content_action, reason)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            content_action = VALUES(content_action),
            reason = VALUES(reason),
            created_at = CURRENT_TIMESTAMP
    """, (
        row.student_id,
        row.domain,
        row.content_action,
        row.reason
    ))

db.commit()
print("✅ Action decisions generated")
