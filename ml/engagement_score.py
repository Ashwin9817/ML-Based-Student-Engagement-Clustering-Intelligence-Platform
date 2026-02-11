import pandas as pd
import mysql.connector
from sklearn.preprocessing import MinMaxScaler

query = """
SELECT
    student_id,
    domain,
    avg_score,
    attempt_frequency,
    recency_score,
    consistency_index
FROM engineered_features
"""


db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="##IstHISSqL321",
    database="student_engagement_ai"
)

df = pd.read_sql(query, db)

# Normalize values
scaler = MinMaxScaler()
df[[
    "avg_score",
    "attempt_frequency",
    "recency_score",
    "consistency_index"
]] = scaler.fit_transform(df[[
    "avg_score",
    "attempt_frequency",
    "recency_score",
    "consistency_index"
]])

# Engagement score formula
df["engagement_score"] = (
    0.4 * df["attempt_frequency"] +
    0.3 * df["consistency_index"] +
    0.2 * df["recency_score"] +
    0.1 * df["avg_score"]
) * 100

# Update DB
cursor = db.cursor()

for _, row in df.iterrows():
    cursor.execute("""
        UPDATE engineered_features
        SET engagement_score = %s
        WHERE student_id = %s AND domain = %s
    """, (
        float(row["engagement_score"]),
        int(row["student_id"]),
        row["domain"]
    ))

db.commit()
cursor.close()
db.close()

print("✅ Engagement score computed and stored successfully")
