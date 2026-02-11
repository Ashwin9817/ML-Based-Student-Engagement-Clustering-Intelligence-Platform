import mysql.connector
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from datetime import date

# ---------------- DB CONNECTION ---------------- #
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="##IstHISSqL321",
    database="student_engagement_ai"
)

# ---------------- FETCH DATA ---------------- #
query = """
SELECT 
    ef.student_id,
    ef.domain,
    ef.avg_score,
    ef.attempt_frequency,
    ef.recency_score,
    ef.consistency_index,
    COALESCE(es.engagement_score, 50) AS engagement_score
FROM engineered_features ef
LEFT JOIN (
    SELECT student_id, MAX(week) AS max_week
    FROM engagement_scores
    GROUP BY student_id
) latest ON ef.student_id = latest.student_id
LEFT JOIN engagement_scores es 
    ON es.student_id = latest.student_id 
    AND es.week = latest.max_week
"""

df = pd.read_sql(query, db)

# ---------------- CLUSTERING ---------------- #
cursor = db.cursor()
today = date.today()

for domain in df["domain"].unique():
    domain_df = df[df["domain"] == domain].copy()

    if len(domain_df) < 4:
        continue  # not enough data to cluster

    features = domain_df[
        ["avg_score", "attempt_frequency", "recency_score",
         "consistency_index", "engagement_score"]
    ]

    # Normalize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(features)

    # KMeans
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    domain_df["cluster_id"] = kmeans.fit_predict(X_scaled)

    # Rank clusters by engagement quality
    cluster_rank = (
        domain_df.groupby("cluster_id")["engagement_score"]
        .mean()
        .sort_values()
        .index.tolist()
    )

    cluster_map = {
        cluster_rank[3]: "CONSISTENT",
        cluster_rank[2]: "IMPROVING",
        cluster_rank[1]: "DROPPING",
        cluster_rank[0]: "LOW"
    }

    domain_df["cluster"] = domain_df["cluster_id"].map(cluster_map)

    # Confidence = distance from centroid (normalized)
    distances = kmeans.transform(X_scaled)
    domain_df["confidence"] = 1 / (1 + np.min(distances, axis=1))

    # ---------------- SAVE TO DB ---------------- #
    for _, row in domain_df.iterrows():
        cursor.execute("""
        REPLACE INTO engagement_clusters
        (student_id, domain, cluster, confidence, last_updated)
        VALUES (%s, %s, %s, %s, %s)
        """, (
            int(row.student_id),
            row.domain,
            row.cluster,
            float(row.confidence),
            today
        ))

db.commit()
cursor.close()
db.close()

print("✅ Engagement clustering completed successfully")
