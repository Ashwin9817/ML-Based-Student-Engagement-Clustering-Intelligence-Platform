import mysql.connector
import pandas as pd
import joblib
import numpy as np

# ---------------- LOAD MODEL ---------------- #
model = joblib.load("ml/domain_likelihood_model.pkl")
label_encoder = joblib.load("ml/domain_label_encoder.pkl")

# ---------------- DB CONNECTION ---------------- #
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="##IstHISSqL321",
    database="student_engagement_ai"
)

cursor = db.cursor()

# ---------------- LOAD FEATURES ---------------- #
query = """
SELECT
    ef.student_id,
    ef.domain,
    ef.avg_score,
    ef.attempt_frequency,
    ef.recency_score,
    ef.consistency_index,
    sp.proficiency_pct,
    ec.cluster
FROM engineered_features ef
JOIN skill_profiles sp
  ON ef.student_id = sp.student_id AND ef.domain = sp.domain
JOIN engagement_clusters ec
  ON ef.student_id = ec.student_id AND ef.domain = ec.domain
"""

df = pd.read_sql(query, db)

cluster_map = {
    "CONSISTENT": 3,
    "IMPROVING": 2,
    "DROPPING": 1,
    "LOW": 0
}
df["cluster_encoded"] = df["cluster"].map(cluster_map)

X = df[[
    "avg_score",
    "attempt_frequency",
    "recency_score",
    "consistency_index",
    "proficiency_pct",
    "cluster_encoded"
]]

probs = model.predict_proba(X)
domains = label_encoder.inverse_transform(range(probs.shape[1]))

# ---------------- INSERT LIKELIHOODS ---------------- #
cursor.execute("DELETE FROM domain_likelihood")

for i, row in df.iterrows():
    student_id = int(row.student_id)
    for idx, domain in enumerate(domains):
        likelihood = float(probs[i][idx])

        cursor.execute("""
        INSERT INTO domain_likelihood (student_id, domain, likelihood_score)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
        likelihood_score = VALUES(likelihood_score);
        """, (student_id, domain, likelihood))

db.commit()

print("✅ Domain likelihood predictions inserted")
