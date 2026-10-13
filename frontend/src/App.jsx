import { useEffect, useState } from "react";
import "./App.css";

const DEFAULT_API = "http://127.0.0.1:47709";

export default function App() {
  const [apiUrl, setApiUrl] = useState(
    () => localStorage.getItem("agent_api_url") || DEFAULT_API
  );
  const [token, setToken] = useState(
    () => localStorage.getItem("agent_token") || ""
  );
  const [user, setUser] = useState(null);
  const [page, setPage] = useState("Overview");
  const [health, setHealth] = useState("Checking");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [loginForm, setLoginForm] = useState({
    username: "",
    password: "",
  });
  const [customerUsername, setCustomerUsername] = useState("johnmwanga");
  const [message, setMessage] = useState("");
  const [chat, setChat] = useState([
    {
      role: "assistant",
      text: "Hello! I'm your AI support assistant. Describe a customer problem to begin.",
    },
  ]);
  const [agentResult, setAgentResult] = useState(null);

  const [customerId, setCustomerId] = useState("");
  const [incidentIssue, setIncidentIssue] = useState("");
  const [incidentId, setIncidentId] = useState("");
  const [incident, setIncident] = useState(null);

  const base = apiUrl.trim().replace(/\/+$/, "");

  async function request(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...options.headers };
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch(`${base}${path}`, {
      ...options,
      headers,
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      throw new Error(
        typeof detail === "string"
          ? detail
          : detail
            ? JSON.stringify(detail)
            : `Request failed (${response.status})`
      );
    }
    return data;
  }

  async function checkHealth() {
    try {
      const data = await request("/health");
      setHealth(data.status === "healthy" ? "Online" : "Unknown");
    } catch {
      setHealth("Offline");
    }
  }

  async function loadUser() {
    if (!token) {
      setUser(null);
      return;
    }
    try {
      const data = await request("/auth/me");
      setUser(data);
    } catch {
      localStorage.removeItem("agent_token");
      setToken("");
      setUser(null);
    }
  }

  useEffect(() => {
    localStorage.setItem("agent_api_url", apiUrl);
  }, [apiUrl]);

  useEffect(() => {
    checkHealth();
    loadUser();
    // Initial connection check and session restoration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (token) loadUser();
    else setUser(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function login(event) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      const data = await request("/auth/login", {
        method: "POST",
        body: JSON.stringify(loginForm),
      });
      localStorage.setItem("agent_token", data.access_token);
      setToken(data.access_token);
      setUser({ username: data.username, role: data.role });
      setLoginForm({ username: "", password: "" });
      setNotice(`Welcome back, ${data.username}.`);
      setPage("Overview");
      await checkHealth();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    localStorage.removeItem("agent_token");
    setToken("");
    setUser(null);
    setNotice("You have signed out.");
    setPage("Overview");
  }

  async function sendMessage(event) {
    event.preventDefault();
    const text = message.trim();
    if (!text || busy) return;
    if (!customerUsername.trim()) {
      setNotice("Enter the customer username first.");
      return;
    }

    setChat((items) => [...items, { role: "user", text }]);
    setMessage("");
    setBusy(true);
    setNotice("");
    setAgentResult(null);

    try {
      const data = await request("/agent/run", {
        method: "POST",
        body: JSON.stringify({
          customer_message: text,
          username: customerUsername.trim(),
        }),
      });
      setAgentResult(data);
      const reply =
        data.reply ||
        data.response ||
        data.message ||
        data.answer ||
        "The agent returned a result. See the response details below.";
      setChat((items) => [
        ...items,
        { role: "assistant", text: String(reply) },
      ]);
    } catch (error) {
      setChat((items) => [
        ...items,
        { role: "error", text: error.message },
      ]);
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function createIncident(event) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    setIncident(null);
    try {
      const data = await request("/incidents", {
        method: "POST",
        body: JSON.stringify({
          customer_id: Number(customerId),
          issue: incidentIssue.trim(),
        }),
      });
      setIncident(data);
      setIncidentId(String(data.id));
      setNotice(`Incident #${data.id} created successfully.`);
      setIncidentIssue("");
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function findIncident(event) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    setIncident(null);
    try {
      const data = await request(
        `/incidents/${encodeURIComponent(incidentId.trim())}`
      );
      setIncident(data);
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  }

  const navItems = [
    { name: "Overview", icon: "◫" },
    { name: "AI Support", icon: "✳" },
    { name: "Incidents", icon: "▤" },
    { name: "Settings", icon: "⚙" },
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">✳</div>
          <div>
            <strong>AgentFlow</strong>
            <span>INTELLIGENT SUPPORT</span>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav>
          {navItems.map((item) => (
            <button
              key={item.name}
              className={`nav-item ${page === item.name ? "active" : ""}`}
              onClick={() => {
                setPage(item.name);
                setNotice("");
              }}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.name}
              {item.name === "AI Support" && (
                <span className="nav-dot" />
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="status-card">
            <div className="status-heading">
              <span className={`status-indicator ${health === "Online" ? "good" : ""}`} />
              <strong>Backend status</strong>
            </div>
            <div className="status-value">{health}</div>
            <button className="text-button" onClick={checkHealth}>
              Check connection ↗
            </button>
          </div>
          <div className="profile">
            <div className="avatar">
              {(user?.username || "G").slice(0, 1).toUpperCase()}
            </div>
            <div className="profile-info">
              <strong>{user?.username || "Guest session"}</strong>
              <span>{user?.role || "Sign in to get started"}</span>
            </div>
            {user && (
              <button className="logout-button" title="Sign out" onClick={logout}>
                ↗
              </button>
            )}
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{page}</strong>
          </div>
          <div className="topbar-right">
            <span className="secure-label">⌑ Secure workspace</span>
            <div className="top-avatar">
              {(user?.username || "G").slice(0, 1).toUpperCase()}
            </div>
          </div>
        </header>

        <div className="content">
          {notice && (
            <div className="notice" role="status">
              <span>{notice}</span>
              <button onClick={() => setNotice("")} aria-label="Dismiss">×</button>
            </div>
          )}

          {page === "Overview" && (
            <>
              <section className="page-heading">
                <div>
                  <div className="eyebrow">YOUR SUPPORT WORKSPACE</div>
                  <h1>Good to see you{user ? `, ${user.username}` : ""}.</h1>
                  <p>Manage customer issues and let your AI agent help resolve them.</p>
                </div>
                <button className="primary-button" onClick={() => setPage("AI Support")}>
                  <span>✳</span> Open AI support
                </button>
              </section>

              <section className="stats-grid">
                <div className="stat-card">
                  <div className="stat-top"><span>AI ASSISTANT</span><span className="stat-icon purple">✳</span></div>
                  <div className="stat-number">Ready to help</div>
                  <div className="stat-foot"><span className="tiny-dot" /> Local AI workflow</div>
                </div>
                <div className="stat-card">
                  <div className="stat-top"><span>BACKEND API</span><span className="stat-icon green">⌁</span></div>
                  <div className="stat-number">{health}</div>
                  <div className="stat-foot">FastAPI connection</div>
                </div>
                <div className="stat-card">
                  <div className="stat-top"><span>AUTHENTICATION</span><span className="stat-icon blue">♙</span></div>
                  <div className="stat-number">{user ? "Signed in" : "Guest"}</div>
                  <div className="stat-foot">{user ? `Role: ${user.role}` : "Login to access protected tools"}</div>
                </div>
              </section>

              <section className="dashboard-grid">
                <div className="panel welcome-panel">
                  <div className="panel-kicker">AI-POWERED CUSTOMER CARE</div>
                  <h2>Support that works<br />smarter.</h2>
                  <p>Use your AI agent to investigate customer problems through your backend's authorized workflow.</p>
                  <button className="primary-button" onClick={() => setPage("AI Support")}>
                    Start a conversation <span>→</span>
                  </button>
                  <div className="orb orb-one" />
                  <div className="orb orb-two" />
                  <div className="orb-center">✳</div>
                </div>
                <div className="panel quick-panel">
                  <div className="panel-title-row">
                    <h3>Quick actions</h3><span className="muted">TOOLS</span>
                  </div>
                  <button className="quick-action" onClick={() => setPage("AI Support")}>
                    <span className="quick-icon lavender">✳</span>
                    <span><strong>Ask the AI agent</strong><small>Investigate a customer issue</small></span>
                    <span className="arrow">→</span>
                  </button>
                  <button className="quick-action" onClick={() => setPage("Incidents")}>
                    <span className="quick-icon mint">▤</span>
                    <span><strong>Create an incident</strong><small>Record a customer problem</small></span>
                    <span className="arrow">→</span>
                  </button>
                  <button className="quick-action" onClick={() => setPage("Settings")}>
                    <span className="quick-icon sky">⚙</span>
                    <span><strong>Configure connection</strong><small>Set your backend API address</small></span>
                    <span className="arrow">→</span>
                  </button>
                </div>
              </section>

              <section className="panel checklist-panel">
                <div>
                  <h3>Workspace readiness</h3>
                  <p className="muted">Current connection and session status</p>
                </div>
                <div className="readiness-items">
                  <span><i className={health === "Online" ? "check ready" : "check"}>{health === "Online" ? "✓" : "·"}</i> API {health.toLowerCase()}</span>
                  <span><i className={user ? "check ready" : "check"}>{user ? "✓" : "·"}</i> {user ? "Authenticated" : "Login required"}</span>
                  <span><i className="check ready">✓</i> Dashboard loaded</span>
                </div>
              </section>
            </>
          )}

          {page === "AI Support" && (
            <>
              <section className="page-heading">
                <div>
                  <div className="eyebrow">CUSTOMER OPERATIONS</div>
                  <h1>AI Support</h1>
                  <p>Send a customer issue to your authenticated AI agent.</p>
                </div>
                <span className={`pill ${health === "Online" ? "pill-good" : "pill-warn"}`}>● API {health}</span>
              </section>
              {!user && (
                <div className="inline-warning">
                  You need to sign in with a user that has the <code>agent.run</code> permission before sending requests.
                  <button onClick={() => setPage("Settings")}>Go to sign in →</button>
                </div>
              )}
              <section className="support-layout">
                <div className="panel chat-panel">
                  <div className="chat-header">
                    <div className="ai-avatar">✳</div>
                    <div><strong>Support agent</strong><span><i /> AI workflow endpoint</span></div>
                    <span className="chat-header-tag">AGENT</span>
                  </div>
                  <div className="messages">
                    {chat.map((item, index) => (
                      <div className={`message-row ${item.role}`} key={`${index}-${item.role}`}>
                        {item.role !== "user" && <div className="message-avatar">{item.role === "error" ? "!" : "✳"}</div>}
                        <div className="message-bubble">
                          <span className="message-label">{item.role === "user" ? "YOU" : item.role === "error" ? "REQUEST ERROR" : "AI SUPPORT"}</span>
                          <p>{item.text}</p>
                        </div>
                      </div>
                    ))}
                    {busy && <div className="typing"><span /><span /><span /> Agent is processing the request…</div>}
                  </div>
                  {agentResult && (
                    <details className="response-details">
                      <summary>View raw agent response</summary>
                      <pre>{JSON.stringify(agentResult, null, 2)}</pre>
                    </details>
                  )}
                  <form className="composer" onSubmit={sendMessage}>
                    <textarea
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      placeholder="Describe the customer's problem…"
                      rows="2"
                      required
                    />
                    <div className="composer-bottom">
                      <span>↳ Sent to <code>/agent/run</code></span>
                      <button className="primary-button" disabled={busy || !user || !message.trim()}>
                        {busy ? "Working…" : "Send message ↑"}
                      </button>
                    </div>
                  </form>
                </div>
                <div className="panel customer-panel">
                  <div className="panel-title-row"><h3>Customer context</h3><span className="muted">INPUT</span></div>
                  <label>Customer username</label>
                  <input value={customerUsername} onChange={(event) => setCustomerUsername(event.target.value)} placeholder="e.g. johnmwanga" />
                  <p className="field-help">This is the customer username passed to your agent. It is not the staff login username.</p>
                  <div className="context-divider" />
                  <h4>Request details</h4>
                  <div className="detail-row"><span>Endpoint</span><code>POST /agent/run</code></div>
                  <div className="detail-row"><span>Authentication</span><strong>{user ? "Token available" : "Required"}</strong></div>
                  <div className="detail-row"><span>Permission</span><code>agent.run</code></div>
                  <div className="context-note">The agent's actual response depends on the backend workflow and permissions assigned to your account.</div>
                </div>
              </section>
            </>
          )}

          {page === "Incidents" && (
            <>
              <section className="page-heading">
                <div>
                  <div className="eyebrow">CUSTOMER OPERATIONS</div>
                  <h1>Incident management</h1>
                  <p>Create an incident or retrieve an existing one by its ID.</p>
                </div>
              </section>
              {!user && (
                <div className="inline-warning">Sign in with a user that has the required incident permissions to use these endpoints.</div>
              )}
              <section className="incident-grid">
                <form className="panel form-panel" onSubmit={createIncident}>
                  <div className="form-heading-icon mint">＋</div>
                  <h2>Create an incident</h2>
                  <p>Record a new customer issue in the incident system.</p>
                  <label>Customer ID</label>
                  <input type="number" min="1" value={customerId} onChange={(event) => setCustomerId(event.target.value)} placeholder="Enter numeric customer ID" required />
                  <label>Issue description</label>
                  <textarea rows="4" value={incidentIssue} onChange={(event) => setIncidentIssue(event.target.value)} placeholder="Describe what happened…" required />
                  <button className="primary-button full-button" disabled={busy || !user}>{busy ? "Processing…" : "Create incident →"}</button>
                  <small className="field-help">Endpoint: POST /incidents · Permission: incident.create</small>
                </form>
                <div className="panel form-panel">
                  <div className="form-heading-icon lavender">⌕</div>
                  <h2>Find an incident</h2>
                  <p>Look up an incident using its numeric ID.</p>
                  <form onSubmit={findIncident}>
                    <label>Incident ID</label>
                    <input type="number" min="1" value={incidentId} onChange={(event) => setIncidentId(event.target.value)} placeholder="e.g. 1" required />
                    <button className="secondary-button full-button" disabled={busy || !user}>{busy ? "Searching…" : "Find incident →"}</button>
                  </form>
                  <small className="field-help">Endpoint: GET /incidents/{`{incident_id}`} · Permission: incident.view</small>
                </div>
              </section>
              {incident && (
                <section className="panel incident-result">
                  <div className="panel-title-row">
                    <div><div className="eyebrow">INCIDENT RECORD</div><h2>Incident #{incident.id}</h2></div>
                    <span className="pill pill-good">{incident.status || "Recorded"}</span>
                  </div>
                  <div className="incident-fields">
                    <div><span>Customer ID</span><strong>{incident.customer_id}</strong></div>
                    <div><span>Status</span><strong>{incident.status || "—"}</strong></div>
                    <div><span>Created</span><strong>{incident.created_at ? new Date(incident.created_at).toLocaleString() : "—"}</strong></div>
                  </div>
                  <h4>Issue</h4><p>{incident.issue}</p>
                  {incident.diagnosis && <><h4>Diagnosis</h4><p>{incident.diagnosis}</p></>}
                </section>
              )}
            </>
          )}

          {page === "Settings" && (
            <>
              <section className="page-heading">
                <div>
                  <div className="eyebrow">CONFIGURATION</div>
                  <h1>Settings</h1>
                  <p>Configure the backend URL and manage your login session.</p>
                </div>
              </section>
              <section className="settings-grid">
                <div className="panel form-panel">
                  <h2>Backend connection</h2>
                  <p>Use the address where your FastAPI backend is running, not the Vite frontend address.</p>
                  <label>API base URL</label>
                  <input value={apiUrl} onChange={(event) => setApiUrl(event.target.value)} placeholder="http://127.0.0.1:8000" />
                  <button className="secondary-button full-button" onClick={async () => {
                    await checkHealth();
                    setNotice("Connection check finished. Backend status: " + health + ". If it just changed, check the status indicator again.");
                  }}>Test backend connection</button>
                  <div className="detail-row"><span>Health endpoint</span><code>/health</code></div>
                  <div className="detail-row"><span>Current status</span><strong>{health}</strong></div>
                </div>
                <div className="panel form-panel">
                  <h2>{user ? "Your session" : "Sign in"}</h2>
                  <p>{user ? "You are signed in. Protected actions use your bearer token." : "Use a backend account that has the permissions required for your intended actions."}</p>
                  {user ? (
                    <>
                      <div className="session-card">
                        <div className="avatar large">{user.username.slice(0, 1).toUpperCase()}</div>
                        <div><strong>{user.username}</strong><span>{user.role}</span></div>
                      </div>
                      <button className="secondary-button full-button" onClick={logout}>Sign out</button>
                    </>
                  ) : (
                    <form onSubmit={login} className="login-form">
                      <label>Username</label>
                      <input autoComplete="username" value={loginForm.username} onChange={(event) => setLoginForm({ ...loginForm, username: event.target.value })} required />
                      <label>Password</label>
                      <input type="password" autoComplete="current-password" value={loginForm.password} onChange={(event) => setLoginForm({ ...loginForm, password: event.target.value })} required />
                      <button className="primary-button full-button" disabled={busy}>{busy ? "Signing in…" : "Sign in →"}</button>
                    </form>
                  )}
                  <small className="field-help">Endpoint: POST /auth/login</small>
                </div>
              </section>
            </>
          )}

          <footer className="footer">
            <span>AgentFlow <span className="footer-separator">·</span> Intelligent AI Agent Platform</span>
            <span>FastAPI + React <span className="footer-separator">·</span> v0.1.0</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
