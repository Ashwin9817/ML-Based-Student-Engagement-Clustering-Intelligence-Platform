import { useState } from "react";
import axios from "axios";
import "./Login.css";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const res = await axios.post("http://localhost:5000/login", {
        email: email.trim(),
        password,
      });
      console.log("Login response:", res.data);

      const { user_id, role } = res.data || {};
      if (!user_id || !role) {
        throw new Error("Invalid login response");
      }

      localStorage.setItem("user_id", String(user_id));
      localStorage.setItem("role", role);

      const target =
        role === "STUDENT"
          ? `/student?user_id=${encodeURIComponent(user_id)}&role=${encodeURIComponent(role)}`
          : `/mentor?user_id=${encodeURIComponent(user_id)}&role=${encodeURIComponent(role)}`;
      window.location = target;
    } catch (err) {
      console.error("Login error:", {
        status: err?.response?.status,
        data: err?.response?.data,
        message: err?.message,
      });
      const message =
        err?.response?.data?.error ||
        err?.message ||
        "Login failed. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-shell">
        <div className="login-hero">
          <h1>Student Engagement Platform</h1>
          <p>
            Track goals, engagement, and skill growth in one unified view.
          </p>
          <div className="login-accent" />
        </div>
        <div className="login-card">
          <h2>Sign in</h2>
          <form onSubmit={handleLogin} className="login-form">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
            {error ? (
              <p className="login-error" role="alert">
                {error}
              </p>
            ) : null}
            <button type="submit" disabled={isLoading}>
              {isLoading ? "Logging in..." : "Login"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default Login;
