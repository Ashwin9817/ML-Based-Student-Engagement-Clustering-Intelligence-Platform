import mysql.connector
import pandas as pd
from datetime import date

# ---------------- DB CONNECTION ---------------- #
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="##IstHISSqL321",
    database="student_engagement_ai"
)

cursor = db.cursor()

# ---------------- FETCH CURRENT CLUSTERS ---------------- #
cluster_query = """
SELECT student_id, domain, cluster
FROM engagement_clusters
"""

clusters_df = pd.read_sql(cluster_query, db)

# ---------------- FETCH ENGAGEMENT HISTORY ---------------- #
score_query = """
SELECT student_id, week, engagement_score
FROM engagement_scores
ORDER BY student_id, week
"""

scores_df = pd.read_sql(score_query, db)

today = date.today()

# ---------------- MOVEMENT LOGIC ---------------- #
for _, row in clusters_df.iterrows():
    student_id = row.student_id
    domain = row.domain
    current_cluster = row.cluster

    student_scores = scores_df[scores_df.student_id == student_id]

    if len(student_scores) < 3:
        continue  # not enough history

    last_week_score = student_scores.iloc[-1].engagement_score
    prev_avg = student_scores.iloc[-3:-1].engagement_score.mean()
    trend = last_week_score - prev_avg

    new_cluster = current_cluster

    if current_cluster == "CONSISTENT" and trend < -10:
        new_cluster = "DROPPING"

    elif current_cluster == "DROPPING":
        if trend < -5:
            new_cluster = "LOW"
        elif trend > 8:
            new_cluster = "IMPROVING"

    elif current_cluster == "IMPROVING" and trend > 10:
        new_cluster = "CONSISTENT"

    elif current_cluster == "LOW" and trend > 8:
        new_cluster = "IMPROVING"

    # ---------------- UPDATE IF CHANGED ---------------- #
    if new_cluster != current_cluster:
        cursor.execute("""
        UPDATE engagement_clusters
        SET cluster = %s, last_updated = %s
        WHERE student_id = %s AND domain = %s
        """, (
            new_cluster,
            today,
            int(student_id),
            domain
        ))

db.commit()
cursor.close()
db.close()

print("🔁 Cluster movement logic executed successfully")
