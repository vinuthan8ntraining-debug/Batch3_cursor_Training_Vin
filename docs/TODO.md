# TODO — Demo Monitoring Infrastructure (Linux)

Incremental checklist derived from [`requirements.md`](requirements.md).  
Work **in order**. Each step is a small AI-assisted increment.  
Local demo only — keep steps minimal.

**Conventions for every step**

- **Security:** note risks and the minimal mitigation for a local demo.
- **Docs:** update this file (check the box) and add a short note under the step’s *Docs* line when done.

---

## Step 1 — Project initialization + basic UI

- [x] Create project layout (`app.py` or package, `templates/`, `static/`, `requirements.txt`, `.gitignore`)
- [x] Add Flask dependency; venv install works locally
- [x] Add base layout + empty dashboard shell (no auth yet)
- [x] Bind app to `0.0.0.0` on port `5777`
- [x] **Security:** do not commit `.venv/`, secrets, or real SSH passwords; document bind host/port
- [x] **Docs:** one-line “how to run” in `docs/requirements.md` §8 (or short `README` if added later)
  - *Docs:* layout in place; empty `/` dashboard; run line in PRD §8; `.gitignore` excludes `.venv/`, `.env`, `__pycache__/`. Bind documented as `0.0.0.0:5777`.

---

## Step 2 — Sign-in + unit tests

- [ ] Login page (username + password form)
- [ ] Single `admin` user; password stored as a **hash** (Werkzeug/bcrypt)
- [ ] Session cookie after successful login; logout clears session
- [ ] Protect dashboard route (redirect unauthenticated users to `/login`)
- [ ] Unit tests: valid login, invalid login, protected route without session
- [ ] **Security:** no plaintext password in repo; use env/`ADMIN_PASSWORD_HASH`; HttpOnly session cookie (Flask default)
- [ ] **Docs:** document default demo credentials only for local use; warn not for production

---

## Step 3 — CI/CD (GitHub Actions)

- [ ] Add `.github/workflows/ci.yml`
- [ ] On push/PR: install deps, run unit tests
- [ ] Pin/install from `requirements.txt` (and test extras if needed, e.g. `pytest`)
- [ ] **Security:** no secrets in workflow logs; use dummy/test hashes in CI only
- [ ] **Docs:** note in this file how CI is triggered (`push` / `pull_request`)

---

## Step 4 — In-memory server store

- [ ] In-memory add/list/get/remove for servers (no database)
- [ ] Fields: display name, host, port, SSH user, SSH password
- [ ] Confirm restart clears inventory
- [ ] Unit tests for store CRUD
- [ ] **Security:** never render SSH password in templates/logs; exclude from detail payloads
- [ ] **Docs:** state clearly “no persistence” in PRD/TODO notes

---

## Step 5 — Add / remove server UI (admin only)

- [ ] “Add server” form (name, host, port default 22, SSH user, password)
- [ ] Validate required fields + port range
- [ ] Remove server (POST); CSRF not required for local demo but use POST not GET for delete
- [ ] Unit/integration tests: add + remove while authenticated; reject when logged out
- [ ] **Security:** require login for mutate routes; POST-only delete; flash errors without echoing secrets
- [ ] **Docs:** short field list for “Add server” matching PRD §5.2

---

## Step 6 — Agentless SSH metrics collector

- [ ] Paramiko (or equivalent) SSH helper with short timeout
- [ ] Collect CPU %, memory used/total/%, network RX/TX, listening ports
- [ ] Return structured result; on failure return `ok=False` + error string (no crash)
- [ ] Unit tests with mocked SSH (no real hosts required in CI)
- [ ] **Security:** disable agent/keys lookup if using password auth; timeout connections; treat remote output as untrusted data when parsing
- [ ] **Docs:** list commands used (`/proc/*`, `ss`/`netstat`) in PRD §6 or a short comment block

---

## Step 7 — Dashboard live summaries

- [ ] Dashboard lists servers with status (up/down), CPU, memory, port count
- [ ] Show clear “unreachable” when SSH fails
- [ ] Auto-refresh every **10 seconds**
- [ ] Metrics view remains read-only (no remote shell/actions)
- [ ] Tests: dashboard renders empty list; renders row with mocked metrics
- [ ] **Security:** only authenticated users see host inventory; do not expose SSH password in HTML
- [ ] **Docs:** note refresh interval and read-only behavior

---

## Step 8 — Server detail page

- [ ] Detail route: full CPU, memory, network table, ports table
- [ ] Error panel when host unreachable
- [ ] Auto-refresh every 10 seconds
- [ ] Tests: detail 404 for unknown id; detail with mocked success/failure
- [ ] **Security:** strip secrets from template context; no write/exec actions on remote host from UI
- [ ] **Docs:** describe detail page contents (PRD §5.3 / §5.4)

---

## Step 9 — UI polish (demo)

- [ ] Attractive, simple styling (CSS); usable on desktop and narrow widths
- [ ] Consistent empty states and flash messages
- [ ] Manual refresh optional (browser refresh / meta refresh is enough)
- [ ] **Security:** keep static assets local; no third-party script CDNs required for MVP
- [ ] **Docs:** screenshot optional; otherwise describe pages: login, dashboard, add, detail

---

## Step 10 — Hardening pass + final local verify

- [ ] Confirm bind `0.0.0.0:5777`; debug only for local demo
- [ ] Confirm `.gitignore` excludes `.venv/`, `__pycache__/`, `.env`
- [ ] Run full unit test suite locally and via CI workflow
- [ ] Smoke: login → add server → dashboard/detail → remove → logout
- [ ] **Security:** checklist — hashed admin password, session auth on all app routes, secrets not in git, SSH passwords memory-only, metrics read-only
- [ ] **Docs:** finalize `docs/requirements.md` §7–§8 against actual behavior; keep this TODO checked up to date

---

## Out of scope (do not implement)

- [ ] ~~Persistent DB / history / charts~~
- [ ] ~~Alerts, RBAC (L1/L2/L3), HTTPS, multi-user~~
- [ ] ~~Agents, Windows hosts, production deploy~~

---

## Progress log

| Date | Step | Notes |
|------|------|-------|
| 2026-11-24 | 1 | Flask shell: empty dashboard, bind `0.0.0.0:5777`, how-to-run in PRD §8 |
