import { useEffect, useState } from "react";
import axios from "axios";
import "./StudentDashboard.css";

function StudentDashboard() {
  const [student, setStudent] = useState(null);
  const [skills, setSkills] = useState([]);
  const [engagement, setEngagement] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [recommendationStatus, setRecommendationStatus] = useState(null);
  const [topDomain, setTopDomain] = useState(null);
  const [domains, setDomains] = useState([]);
  const [selectedGoal, setSelectedGoal] = useState("");
  const [savingGoal, setSavingGoal] = useState(false);
  const [goalSkills, setGoalSkills] = useState([]);
  const [goalFocusScore, setGoalFocusScore] = useState(null);
  const [skillLevels, setSkillLevels] = useState([]);
  const [error, setError] = useState("");
  const [historySkill, setHistorySkill] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const query = new URLSearchParams(window.location.search);
  const queryId = query.get("user_id");
  const storedId = localStorage.getItem("user_id");
  const studentId = queryId ? Number(queryId) : storedId ? Number(storedId) : null;

  useEffect(() => {
    const fetchData = async () => {
      try {
        if (!studentId) {
          setError("Missing student id. Please log in again.");
          return;
        }
        const [dashboardRes, domainsRes] = await Promise.all([
          axios.get(`http://localhost:5000/student/dashboard/${studentId}`),
          axios.get("http://localhost:5000/student/domains"),
        ]);
        setStudent(dashboardRes.data.student);
        setSkills(dashboardRes.data.skills);
        setEngagement(dashboardRes.data.engagement);
        setSkillLevels(dashboardRes.data.skill_levels || []);
        setRecommendations(dashboardRes.data.recommendations || []);
        setRecommendationStatus(dashboardRes.data.recommendation_status || null);
        setTopDomain(dashboardRes.data.top_domain || null);
        setGoalSkills(dashboardRes.data.goal_skills || []);
        setGoalFocusScore(dashboardRes.data.goal_focus_score ?? null);
        setDomains(domainsRes.data.domains || []);
        if (dashboardRes.data.student?.selected_goal) {
          setSelectedGoal(dashboardRes.data.student.selected_goal);
        }
      } catch (err) {
        console.error(err);
        setError("Failed to load student dashboard.");
      }
    };

    fetchData();
  }, []);

  if (error) return <div className="sd-loading">{error}</div>;
  if (!student) return <div className="sd-loading">Loading...</div>;

  const handleSetGoal = async (e) => {
    e.preventDefault();
    if (!selectedGoal) return;
    try {
      setSavingGoal(true);
      await axios.post(`http://localhost:5000/student/goal/${studentId}`, {
        selected_goal: selectedGoal,
      });
      const res = await axios.get(
        `http://localhost:5000/student/dashboard/${studentId}`
      );
      setStudent(res.data.student);
      setSkills(res.data.skills);
      setEngagement(res.data.engagement);
      setSkillLevels(res.data.skill_levels || []);
      setRecommendations(res.data.recommendations || []);
      setRecommendationStatus(res.data.recommendation_status || null);
      setTopDomain(res.data.top_domain || null);
      setGoalSkills(res.data.goal_skills || []);
      setGoalFocusScore(res.data.goal_focus_score ?? null);
    } catch (err) {
      console.error(err);
      setError("Failed to set goal.");
    } finally {
      setSavingGoal(false);
    }
  };

  const openHistory = async (domain) => {
    if (!studentId) return;
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
    <div className="sd-page">
      <header className="sd-header">
        <div>
          <h2>Welcome, {student.name}</h2>
          <p className="sd-subtitle">
            Goal: <strong>{student.selected_goal || "Not Set"}</strong>
          </p>
        </div>
        {student.goal_state === "SET" && goalFocusScore !== null ? (
          <div className="sd-score">
            <span>Goal Focus</span>
            <strong>{Math.round(goalFocusScore * 100)}%</strong>
          </div>
        ) : null}
      </header>

      {student.goal_state !== "SET" ? (
        <section className="sd-card">
          <h3>Set Your Goal</h3>
          {recommendationStatus === "NEW" ? (
            <p>You&apos;re new here. Complete a few assessments to get a goal recommendation.</p>
          ) : recommendationStatus === "NOT_ENGAGED" ? (
            <p>You haven&apos;t been active recently. Try a few assessments to get a goal recommendation.</p>
          ) : recommendationStatus === "CONFUSED" ? (
            <p>Your skills are spread across multiple domains. Keep learning and we&apos;ll recommend a goal.</p>
          ) : recommendationStatus === "RECOMMENDED" && topDomain ? (
            <div className="sd-highlight">
              You seem strong in <strong>{topDomain}</strong>. Want to set it as your goal?
            </div>
          ) : null}

          {recommendations.length > 0 ? (
            <div className="sd-tags">
              {recommendations.map((r) => (
                <span key={r.domain}>
                  {r.domain} ({Math.round(r.likelihood_score * 100)}%)
                </span>
              ))}
            </div>
          ) : null}

          <form onSubmit={handleSetGoal} className="sd-form">
            <select
              value={selectedGoal}
              onChange={(e) => setSelectedGoal(e.target.value)}
            >
              <option value="">Select a goal</option>
              {domains.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <button type="submit" disabled={!selectedGoal || savingGoal}>
              {savingGoal ? "Saving..." : "Set Goal"}
            </button>
          </form>
        </section>
      ) : null}

      {student.goal_state === "SET" && goalSkills.length > 0 ? (
        <section className="sd-card">
          <h3>Priority Skills for {student.selected_goal}</h3>
          <div className="sd-grid">
            {goalSkills.map((s) => (
              <div key={s.skill} className="sd-skill">
                <strong>{s.skill}</strong>
                <p>Weight: {s.weight}</p>
                <div className="sd-bar">
                  <span style={{ width: `${s.proficiency_pct || 0}%` }} />
                </div>
                <small>{s.proficiency_pct?.toFixed(1) || 0}% proficiency</small>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="sd-card">
        <h3>Skill Progress</h3>
        <div className="sd-grid">
          {skillLevels.map((s) => {
            const max = Number(s.max_level || 0);
            const current = Math.min(Number(s.current_level || 0), max);
            const pct = max > 0 ? Math.round((current / max) * 100) : 0;
            return (
            <div key={s.domain} className="sd-skill">
              <div className="sd-skill-header">
                <strong>{s.domain}</strong>
                <span className="sd-pill">{pct}%</span>
              </div>
              <div className="sd-levels">
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
        <section className="sd-card">
          <h3>Engagement by Skill</h3>
          <div className="sd-grid">
            {skillLevels.map((s) => {
              const max = Number(s.max_level || 0);
              const current = Math.min(Number(s.current_level || 0), max);
              const completed = max > 0 && current >= max;
              const engagementItem = engagement.find((e) => e.domain === s.domain);
              const confidence = engagementItem?.confidence ?? 0;
              return (
                <button
                  key={`eng-${s.domain}`}
                  className="sd-skill sd-skill-button"
                  onClick={() => openHistory(s.domain)}
                >
                  <strong>{s.domain}</strong>
                  {completed ? (
                    <>
                      <p>COMPLETED</p>
                      <div className="sd-bar">
                        <span style={{ width: "100%" }} />
                      </div>
                      <small>Completed — not counted for engagement</small>
                    </>
                  ) : engagementItem ? (
                    <>
                      <p>{engagementItem.cluster}</p>
                      <div className="sd-bar">
                        <span style={{ width: `${confidence * 100}%` }} />
                      </div>
                      <small>Engagement level</small>
                    </>
                  ) : (
                    <>
                      <p>No data</p>
                      <div className="sd-bar">
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
        <div className="sd-modal">
          <div className="sd-modal-card">
            <div className="sd-modal-header">
              <h3>{historySkill} Timeline</h3>
              <button onClick={closeHistory}>Close</button>
            </div>
            {historyLoading ? (
              <p>Loading...</p>
            ) : historyData.length === 0 ? (
              <p>No attempts yet.</p>
            ) : (
              <ul className="sd-timeline">
                {historyData.map((h, idx) => (
                  <li key={`${h.attempt_date}-${idx}`}>
                    <div>
                      <strong>Level {h.level_attempted}</strong>
                      <span>
                        {h.attempt_date} • {h.difficulty || "N/A"}
                      </span>
                    </div>
                    <div className="sd-timeline-score">
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

export default StudentDashboard;
