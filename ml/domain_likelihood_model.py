import mysql.connector
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import joblib

# ---------------- DB CONNECTION ---------------- #
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="##IstHISSqL321",
    database="student_engagement_ai"
)

# ---------------- LOAD DATA ---------------- #
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

# ---------------- ENCODE CLUSTER ---------------- #
cluster_map = {
    "CONSISTENT": 3,
    "IMPROVING": 2,
    "DROPPING": 1,
    "LOW": 0
}
df["cluster_encoded"] = df["cluster"].map(cluster_map)

# ---------------- PREP DATA ---------------- #
X = df[[
    "avg_score",
    "attempt_frequency",
    "recency_score",
    "consistency_index",
    "proficiency_pct",
    "cluster_encoded"
]]

y = df["domain"]

label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)

# ---------------- TRAIN MODEL ---------------- #
X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42
)

pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("model", LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42
    ))
])

pipeline.fit(X, y)

# ---------------- SAVE MODEL ---------------- #
joblib.dump(pipeline, "ml/domain_likelihood_model.pkl")
joblib.dump(label_encoder, "ml/domain_label_encoder.pkl")

print("✅ Domain likelihood model trained & saved")
