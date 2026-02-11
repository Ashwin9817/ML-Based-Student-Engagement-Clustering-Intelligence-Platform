import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import "./MentorStudentDetail.css";

export default function MentorStudentDetail() {
  const { studentId } = useParams();
  const [student, setStudent] = useState(null);
  const [skills, setSkills] = useState([]);
  const [engagement, setEngagement] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [recommendationStatus, setRecommendationStatus] = useState(null);
  const [goalSkills, setGoalSkills] = useState([]);
  const [goalFocusScore, setGoalFocusScore] = useState(null);
  const [skillLevels, setSkillLevels] = useState([]);
  const [error, setError] = useState("");
  const [historySkill, setHistorySkill] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await axios.get(
          `http://localhost:5000/student/dashboard/${studentId}`
        );
        setStudent(res.data.student);
        setSkills(res.data.skills || []);
        setEngagement(res.data.engagement || []);
        setSkillLevels(res.data.skill_levels || []);
        setRecommendations(res.data.recommendations || []);
        setRecommendationStatus(res.data.recommendation_status || null);
        setGoalSkills(res.data.goal_skills || []);
        setGoalFocusScore(res.data.goal_focus_score ?? null);
      } catch (err) {
        console.error(err);
        setError("Failed to load student details.");
      }
    };

    if (studentId) fetchData();
  }, [studentId]);

  if (error) return <div className="msd-loading">{error}</div>;
  if (!student) return <div className="msd-loading">Loading...</div>;

  const openHistory = async (domain) => {
    setHistorySkill(domain);
    setHistoryLoading(true);
    try {
      const res = await axios.get(
        `http://localhost:5000/student/skill-history/${studentId}`,
        { params: { domain } }
      );
      setHistoryData(res.data.timeline || []);
    } catch (err) {
      console.error(err);
      setHistoryData([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const closeHistory = () => {
    setHistorySkill(null);
    setHistoryData([]);
  };

  return (
    <div className="msd-page">
      <header className="msd-header">
        <div>
          <h2>{student.name}</h2>
          <p className="msd-subtitle">
            Goal: <strong>{student.selected_goal || "Not Set"}</strong>
          </p>
        </div>
        {student.goal_state === "SET" && goalFocusScore !== null ? (
          <div className="msd-score">
            <span>Goal Focus</span>
            <strong>{Math.round(goalFocusScore * 100)}%</strong>
          </div>
        ) : null}
      </header>

      {student.goal_state !== "SET" ? (
        <section className="msd-card">
          <h3>Goal Not Set</h3>
          {recommendationStatus === "NEW" ? (
            <p>New student — not enough data to recommend a goal yet.</p>
          ) : recommendationStatus === "NOT_ENGAGED" ? (
            <p>Not engaged recently — recommendation may be unreliable.</p>
          ) : recommendationStatus === "CONFUSED" ? (
            <p>Skills are spread across domains — needs more focus.</p>
          ) : recommendationStatus === "RECOMMENDED" ? (
            <p>Recommended domains based on skill profile.</p>
          ) : null}

          {recommendations.length > 0 ? (
            <div className="msd-tags">
              {recommendations.map((r) => (
                <span key={r.domain}>
                  {r.domain} ({Math.round(r.likelihood_score * 100)}%)
                </span>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {student.goal_state === "SET" && goalSkills.length > 0 ? (
        <section className="msd-card">
          <h3>Priority Skills for {student.selected_goal}</h3>
          <div className="msd-grid">
            {goalSkills.map((s) => (
              <div key={s.skill} className="msd-skill">
                <strong>{s.skill}</strong>
                <p>Weight: {s.weight}</p>
                <div className="msd-bar">
                  <span style={{ width: `${s.proficiency_pct || 0}%` }} />
                </div>
                <small>{s.proficiency_pct?.toFixed(1) || 0}% proficiency</small>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="msd-card">
        <h3>Skill Progress</h3>
        <div className="msd-grid">
          {skillLevels.map((s) => {
            const max = Number(s.max_level || 0);
            const current = Math.min(Number(s.current_level || 0), max);
            const pct = max > 0 ? Math.round((current / max) * 100) : 0;
            return (
            <div key={s.domain} className="msd-skill">
              <div className="msd-skill-header">
                <strong>{s.domain}</strong>
                <span className="msd-pill">{pct}%</span>
              </div>
              <div className="msd-levels">
                {Array.from({ length: max }).map((_, idx) => (
                  <span
                    key={`${s.domain}-${idx}`}
                    className={idx < current ? "filled" : ""}
                  />
                ))}
              </div>
              <small>
                {current}/{max} levels completed
              </small>
            </div>
          );
        })}
        </div>
      </section>

      {recommendationStatus !== "NEW" ? (
        <section className="msd-card">
          <h3>Engagement by Skill</h3>
          <div className="msd-grid">
            {skillLevels.map((s) => {
              const max = Number(s.max_level || 0);
              const current = Math.min(Number(s.current_level || 0), max);
              const completed = max > 0 && current >= max;
              const engagementItem = engagement.find((e) => e.domain === s.domain);
              const confidence = engagementItem?.confidence ?? 0;
              return (
                <button
                  key={`eng-${s.domain}`}
                  className="msd-skill msd-skill-button"
                  onClick={() => openHistory(s.domain)}
                >
                  <strong>{s.domain}</strong>
                  {completed ? (
                    <>
                      <p>COMPLETED</p>
                      <div className="msd-bar">
                        <span style={{ width: "100%" }} />
                      </div>
                      <small>Completed — not counted for engagement</small>
                    </>
                  ) : engagementItem ? (
                    <>
                      <p>{engagementItem.cluster}</p>
                      <div className="msd-bar">
                        <span style={{ width: `${confidence * 100}%` }} />
                      </div>
                      <small>Engagement level</small>
                    </>
                  ) : (
                    <>
                      <p>No data</p>
                      <div className="msd-bar">
                        <span style={{ width: "0%" }} />
                      </div>
                      <small>Not enough activity</small>
                    </>
                  )}
                </button>
              );
            })}
          </div>
        </section>
      ) : null}

      {historySkill ? (
        <div className="msd-modal">
          <div className="msd-modal-card">
            <div className="msd-modal-header">
              <h3>{historySkill} Timeline</h3>
              <button onClick={closeHistory}>Close</button>
            </div>
            {historyLoading ? (
              <p>Loading...</p>
            ) : historyData.length === 0 ? (
              <p>No attempts yet.</p>
            ) : (
              <ul className="msd-timeline">
                {historyData.map((h, idx) => (
                  <li key={`${h.attempt_date}-${idx}`}>
                    <div>
                      <strong>Level {h.level_attempted}</strong>
                      <span>
                        {h.attempt_date} • {h.difficulty || "N/A"}
                      </span>
                    </div>
                    <div className="msd-timeline-score">
                      <span>
                        Score: {h.score} / {h.max_score ?? "?"}
                      </span>
                      <span className={h.passed ? "pass" : "fail"}>
                        {h.passed ? "PASS" : "FAIL"}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
