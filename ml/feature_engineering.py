import mysql.connector
import pandas as pd
import numpy as np
from datetime import datetime

# ------------------ DB CONNECTION ------------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="##IstHISSqL321",
    database="student_engagement_ai"
)

# ------------------ LOAD DATA ------------------
query = """
SELECT 
    aa.student_id,
    a.domain,
    aa.score,
    aa.attempt_date,
    aa.level_attempted,
    a.max_level
FROM assessment_attempts aa
JOIN assessments a ON aa.assessment_id = a.assessment_id
"""

df = pd.read_sql(query, db)

# ------------------ PREPROCESS ------------------
df["attempt_date"] = pd.to_datetime(df["attempt_date"])
today = pd.Timestamp(datetime.now().date())

# ------------------ FEATURE FUNCTIONS ------------------
def compute_recency(last_date):
    days_diff = (today - last_date).days
    return np.exp(-days_diff / 30)  # exponential decay

def compute_consistency(dates):
    if len(dates) < 2:
        return 0.0
    gaps = dates.sort_values().diff().dt.days.dropna()
    return 1 / (1 + np.std(gaps))

# ------------------ FEATURE ENGINEERING ------------------
features = []

grouped = df.groupby(["student_id", "domain"])

for (student_id, domain), group in grouped:
    max_level = group["max_level"].max()
    max_attempted = group["level_attempted"].max()
    if max_attempted >= max_level:
        # Completed domains should not affect engagement clustering
        continue

    avg_score = group["score"].mean()
    attempt_frequency = len(group)
    recency_score = compute_recency(group["attempt_date"].max())
    consistency_index = compute_consistency(group["attempt_date"])

    features.append([
        student_id,
        domain,
        round(avg_score, 2),
        round(attempt_frequency, 2),
        round(recency_score, 4),
        round(consistency_index, 4)
    ])

feature_df = pd.DataFrame(features, columns=[
    "student_id",
    "domain",
    "avg_score",
    "attempt_frequency",
    "recency_score",
    "consistency_index"
])

# ------------------ WRITE TO DB ------------------
cursor = db.cursor()

cursor.execute("TRUNCATE TABLE engineered_features")

insert_query = """
INSERT INTO engineered_features
(student_id, domain, avg_score, attempt_frequency, recency_score, consistency_index)
VALUES (%s, %s, %s, %s, %s, %s)
"""

cursor.executemany(insert_query, feature_df.values.tolist())
db.commit()

print("✅ Feature engineering complete. Engineered features updated.")
