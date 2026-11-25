# PRD: Demo Monitoring Infrastructure (Linux Servers)

## 1. Overview

Local demo web app for internal L1/L2/L3 and app teams to view **real-time** Linux server metrics **without logging into each host**.

| Item | Detail |
|------|--------|
| Product | Demo Monitoring Infrastructure — Linux servers |
| Audience | Internal infra & application teams (L1–L3) |
| Deployment | Local only (machine where Cursor runs) |
| Stack | Python, Flask, browser UI |
| Collection | **Agentless** (SSH from the app host) |
| Persistence | **None** — in-memory only; lost on restart |

---

## 2. Problem

Operators must SSH into servers to check CPU, memory, network, and port usage. This demo provides a single read-mostly UI to inspect those metrics across registered Linux hosts.

---

## 3. Goals (MVP)

- Sign in as a single admin user.
- Add / remove Linux servers (admin only).
- Show live CPU, memory, network, and listening/port usage per server.
- Auto-refresh metrics every **10 seconds**.
- Attractive, simple UI; monitoring views are **read-only**.

### Non-goals (out of scope)

- Persistent database or history
- Alerts / notifications
- Multi-user or L1/L2/L3 role matrix
- Agents, SNMP, or Windows hosts
- HTTPS / production hardening
- Historical charts or long-term trends

---

## 4. Users & access

| Role | Capabilities |
|------|----------------|
| **Admin** (only user) | Sign in; add/remove servers; view all metrics |
| Unauthenticated | Sign-in page only |

- Default username: `admin`
- Password: stored as a **hash** (e.g. Werkzeug / bcrypt); configure via env or app config for the demo
- No “change password” UI required for MVP

---

## 5. Features

### 5.1 Sign-in

- Login form: username + password
- Validate against default `admin` and hashed password
- Session-based access after login
- Logout available in the UI

### 5.2 Server inventory (admin)

Admin can register Linux servers to monitor. Required fields:

| Field | Description |
|-------|-------------|
| Display name | Friendly label in the UI |
| Host | Hostname or IP |
| Port | SSH port (default `22`) |
| SSH username | Login user on the target |
| SSH password | Password for agentless SSH |

- **Add server** and **remove server** only when logged in as admin
- Optional: “Test connection” before save (nice-to-have; not required)
- No disk storage — server list lives in memory for the process lifetime

### 5.3 Live metrics (read-only)

For each reachable server, show at least:

| Metric | What to show |
|--------|----------------|
| CPU | Overall usage % |
| Memory | Used / total (and % if easy) |
| Network | RX / TX (e.g. bytes or rates) |
| Ports | Listening / in-use port details |

- Collection: **agentless** over SSH (run standard Linux commands remotely; no agent install)
- UI refresh: every **10 seconds** (auto); manual refresh optional
- Monitoring screens are **read-only** — no remote shell, no config changes on targets
- Unreachable hosts: clear error/status (e.g. “unreachable” / last error), without crashing the app

### 5.4 UI layout (minimal)

- Login page
- Dashboard: list of registered servers with high-level status / key metrics
- Server detail: full CPU, memory, network, and port info for one host
- Visual style: clean, attractive Flask-served UI (HTML/CSS; light JS for 10s refresh)

---

## 6. Technical notes (demo)

| Area | Choice |
|------|--------|
| Backend | Python + Flask |
| Frontend | Server-rendered templates + CSS (+ minimal JS for refresh) |
| Auth | Session cookie; password hash for `admin` |
| Metrics | SSH from app → target; parse command output |
| State | In-memory dict/list for servers and sessions |
| Run | Local: `python app.py` binds `0.0.0.0:57275` |

Suggested remote commands (implementation guidance, not UI):

- CPU / load: e.g. `/proc/stat`, `top -bn1`, or `mpstat`
- Memory: e.g. `/proc/meminfo` or `free -m`
- Network: e.g. `/proc/net/dev` or `ip -s link`
- Ports: e.g. `ss -tuln` or `netstat -tuln`

---

## 7. Acceptance criteria

1. User can open the app locally in a browser and sign in as `admin` with the configured password.
2. Wrong credentials are rejected.
3. Admin can add a Linux server with host, port, SSH user, and password.
4. Admin can remove a registered server.
5. Dashboard lists servers; detail view shows CPU, memory, network, and ports when SSH succeeds.
6. Metrics update automatically about every 10 seconds.
7. Metric views do not allow mutating the remote server.
8. Restarting the app clears the server list (no persisted storage).
9. Failed SSH / unreachable host shows a clear status, app remains usable.

---

## 8. Local run (minimal)

**How to run:** `python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python app.py` → open `http://<host>:57275` (binds `0.0.0.0:57275`). Demo login: `admin` / `admin`.

1. Create a Python venv and install dependencies (`flask`; later: SSH client such as `paramiko`, password hashing).
2. Set admin password hash (or demo password used to generate the hash) via env/config (Step 2+).
3. Start the Flask app (`python app.py` → `0.0.0.0:57275`).
4. Open `http://<host>:57275` in a browser; sign in as `admin` / `admin`, add a reachable Linux host, and confirm metrics refresh every 10s.

**Security (local demo):** app listens on all interfaces (`0.0.0.0:57275`) — use only on trusted networks; do not commit `.venv/`, `.env`, or real SSH passwords.

---

## 9. Assumptions

- Targets are Linux hosts reachable via SSH from the Cursor machine (host/port/user/password).
- Demo credentials and SSH passwords are for local demo use only — not production.
- “Read-only UI” means operators cannot change remote systems through the UI; admin may still manage the in-app server list.
