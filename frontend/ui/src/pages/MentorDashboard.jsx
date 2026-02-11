import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./MentorDashboard.css";

const LEVEL = {
  ROOT: "ROOT",
  GOAL_SET_DOMAINS: "GOAL_SET_DOMAINS",
  GOAL_NOT_SET_DOMAINS: "GOAL_NOT_SET_DOMAINS",
  NOT_DECIDED_CHILDREN: "NOT_DECIDED_CHILDREN",
  ENGAGEMENT: "ENGAGEMENT",
  STUDENTS: "STUDENTS",
};

function buildClusterMap(students, domainLabel) {
  const map = { CONSISTENT: [], IMPROVING: [], DROPPING: [], LOW: [] };
  students.forEach((student) => {
    const cluster = student.overall_cluster;
    if (cluster && map[cluster]) {
      map[cluster].push({
        student_id: student.student_id,
        name: student.name,
        domain: domainLabel || student.top_domain || student.goal || "Mixed",
        confidence: student.overall_score,
      });
    }
  });
  return map;
}

export default function MentorDashboard() {
  const query = new URLSearchParams(window.location.search);
  const queryId = query.get("user_id");
  const storedId = localStorage.getItem("user_id");
  const mentorId = queryId ? Number(queryId) : storedId ? Number(storedId) : null;
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [level, setLevel] = useState(LEVEL.ROOT);
  const [context, setContext] = useState({});

  useEffect(() => {
    if (!mentorId) {
      setError("Missing mentor id. Please log in again.");
      return;
    }

    axios
      .get(`http://localhost:5000/mentor/dashboard/${mentorId}`)
      .then((res) => setData(res.data))
      .catch((err) => {
        console.error(err);
        setError("Failed to load mentor dashboard.");
      });
  }, []);

  const goalSetEntries = useMemo(
    () => Object.entries((data && data.goal_set) || {}),
    [data]
  );
  const goalNotSet = data?.goal_not_set || {
    likelihood_domains: {},
    not_decided: {
      confused: [],
      new: [],
      not_engaged: [],
    },
  };

  const handleRootSelect = (type) => {
    if (type === "GOAL_SET") {
      setLevel(LEVEL.GOAL_SET_DOMAINS);
      setContext({});
    } else {
      setLevel(LEVEL.GOAL_NOT_SET_DOMAINS);
      setContext({});
    }
  };

  const goalSetCount = useMemo(
    () => goalSetEntries.reduce((sum, [, students]) => sum + students.length, 0),
    [goalSetEntries]
  );
  const goalNotSetCount =
    goalNotSet.not_decided.confused.length +
    goalNotSet.not_decided.new.length +
    goalNotSet.not_decided.not_engaged.length +
    Object.values(goalNotSet.likelihood_domains).reduce(
      (sum, students) => sum + students.length,
      0
    );

  const handleDomainSelect = (scope, domain, students) => {
    setLevel(LEVEL.ENGAGEMENT);
    setContext({ scope, domain, students });
  };

  const handleNotDecidedSelect = (category, students) => {
    if (category === "New") {
      setLevel(LEVEL.STUDENTS);
      setContext({
        scope: "NOT_DECIDED",
        domain: category,
        cluster: "NEW",
        clusterStudents: students,
      });
      return;
    }
    setLevel(LEVEL.ENGAGEMENT);
    setContext({ scope: "NOT_DECIDED", domain: category, students });
  };

  const handleNotDecidedParent = () => {
    setLevel(LEVEL.NOT_DECIDED_CHILDREN);
    setContext({});
  };

  const handleEngagementSelect = (cluster, students) => {
    setLevel(LEVEL.STUDENTS);
    setContext((prev) => ({ ...prev, cluster, clusterStudents: students }));
  };

  const goBack = () => {
    if (level === LEVEL.STUDENTS) {
      if (context.cluster === "NEW") {
        setLevel(LEVEL.NOT_DECIDED_CHILDREN);
      } else {
        setLevel(LEVEL.ENGAGEMENT);
      }
      return;
    }
    if (level === LEVEL.ENGAGEMENT) {
      if (context.scope === "GOAL_SET") setLevel(LEVEL.GOAL_SET_DOMAINS);
      else setLevel(LEVEL.GOAL_NOT_SET_DOMAINS);
      return;
    }
    if (level === LEVEL.NOT_DECIDED_CHILDREN) {
      setLevel(LEVEL.GOAL_NOT_SET_DOMAINS);
      return;
    }
    if (
      level === LEVEL.GOAL_SET_DOMAINS ||
      level === LEVEL.GOAL_NOT_SET_DOMAINS
    ) {
      setLevel(LEVEL.ROOT);
      return;
    }
  };

  if (error) return <div className="loading">{error}</div>;
  if (!data) return <div className="loading">Loading mentor insights...</div>;

  return (
    <div className="mentor-dashboard">
      <h1>Mentor Dashboard</h1>

      {level !== LEVEL.ROOT ? (
        <button className="md-back" onClick={goBack}>
          ← Back
        </button>
      ) : null}

      {level === LEVEL.ROOT ? (
        <div className="md-grid">
          <button
            className="md-tile"
            style={{ "--i": 0 }}
            onClick={() => handleRootSelect("GOAL_SET")}
          >
            <h2>Goal Set</h2>
            <p>Domains chosen by students</p>
            <span className="md-count">{goalSetCount}</span>
          </button>
          <button
            className="md-tile"
            style={{ "--i": 1 }}
            onClick={() => handleRootSelect("GOAL_NOT_SET")}
          >
            <h2>Goal Not Set</h2>
            <p>Recommendations and undecided clusters</p>
            <span className="md-count">{goalNotSetCount}</span>
          </button>
        </div>
      ) : null}

      {level === LEVEL.GOAL_SET_DOMAINS ? (
        <section>
          <h2>Goal Set Domains</h2>
          {goalSetEntries.length === 0 ? <p>No goal-set students.</p> : null}
          <div className="md-grid">
            {goalSetEntries.map(([goal, students], index) => (
              <button
                key={goal}
                className="md-tile"
                style={{ "--i": index }}
                onClick={() => handleDomainSelect("GOAL_SET", goal, students)}
              >
                <h3>{goal}</h3>
                <p>{students.length} students</p>
                <span className="md-count">{students.length}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {level === LEVEL.GOAL_NOT_SET_DOMAINS ? (
        <section>
          <h2>Goal Not Set</h2>

          <h3>Likelihood Domains</h3>
          <div className="md-grid">
            {Object.entries(goalNotSet.likelihood_domains).map(
              ([domain, students], index) => (
              <button
                key={domain}
                className="md-tile"
                style={{ "--i": index }}
                onClick={() => handleDomainSelect("GOAL_NOT_SET", domain, students)}
              >
                <h3>{domain}</h3>
                <p>{students.length} students</p>
                <span className="md-count">{students.length}</span>
              </button>
            ))}
            {Object.keys(goalNotSet.likelihood_domains).length === 0 ? (
              <p>No likelihood domains yet.</p>
            ) : null}
          </div>

          <h3>Not Decided</h3>
          <div className="md-grid">
            <button
              className="md-tile"
              style={{ "--i": 0 }}
              onClick={handleNotDecidedParent}
            >
              <h3>Not Decided</h3>
              <p>Confused, New, Not Engaged</p>
              <span className="md-count">
                {goalNotSet.not_decided.confused.length +
                  goalNotSet.not_decided.new.length +
                  goalNotSet.not_decided.not_engaged.length}
              </span>
            </button>
          </div>
        </section>
      ) : null}

      {level === LEVEL.NOT_DECIDED_CHILDREN ? (
        <section>
          <h2>Not Decided</h2>
          <div className="md-grid">
            <button
              className="md-tile"
              style={{ "--i": 0 }}
              onClick={() =>
                handleNotDecidedSelect(
                  "Confused",
                  goalNotSet.not_decided.confused
                )
              }
            >
              <h3>Confused</h3>
              <p>{goalNotSet.not_decided.confused.length} students</p>
              <span className="md-count">{goalNotSet.not_decided.confused.length}</span>
            </button>
            <button
              className="md-tile"
              style={{ "--i": 1 }}
              onClick={() => handleNotDecidedSelect("New", goalNotSet.not_decided.new)}
            >
              <h3>New</h3>
              <p>{goalNotSet.not_decided.new.length} students</p>
              <span className="md-count">{goalNotSet.not_decided.new.length}</span>
            </button>
            <button
              className="md-tile"
              style={{ "--i": 2 }}
              onClick={() =>
                handleNotDecidedSelect(
                  "Not Engaged",
                  goalNotSet.not_decided.not_engaged
                )
              }
            >
              <h3>Not Engaged</h3>
              <p>{goalNotSet.not_decided.not_engaged.length} students</p>
              <span className="md-count">{goalNotSet.not_decided.not_engaged.length}</span>
            </button>
          </div>
        </section>
      ) : null}

      {level === LEVEL.ENGAGEMENT ? (
        <section>
          <h2>{context.domain}</h2>
          <h3>Engagement Clusters</h3>
          <div className="md-grid">
            {Object.entries(
              buildClusterMap(context.students || [], context.domain)
            ).map(([cluster, students], index) => (
              <button
                key={cluster}
                className="md-tile"
                style={{ "--i": index }}
                onClick={() => handleEngagementSelect(cluster, students)}
              >
                <h3>{cluster}</h3>
                <p>{students.length} students</p>
                <span className="md-count">{students.length}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {level === LEVEL.STUDENTS ? (
        <section>
          <h2>{context.cluster}</h2>
          <div className="md-card">
            {context.clusterStudents && context.clusterStudents.length > 0 ? (
              <table className="md-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Domain</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {context.clusterStudents.map((s) => (
                    <tr key={`${s.student_id}-${s.domain}`}>
                      <td>
                        <a href={`/mentor/student/${s.student_id}`}>
                          {s.name}
                        </a>
                      </td>
                      <td>{s.domain || "—"}</td>
                      <td>
                        {typeof s.confidence === "number"
                          ? `${Math.round(s.confidence * 100)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p>No students in this cluster.</p>
            )}
          </div>
        </section>
      ) : null}
    </div>
  );
}
