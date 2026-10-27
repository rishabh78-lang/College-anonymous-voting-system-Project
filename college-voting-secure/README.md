# 🎓 College Anonymous Voting System
## Zero-Vulnerability, Minimal-Dependency Edition

---

## Why This Version Has No Vulnerabilities

| Old Stack | New Stack | Why |
|-----------|-----------|-----|
| React + npm (200+ packages) | Plain HTML/CSS/JS | No npm dependency chain |
| Node.js + Express | Python Flask | Fewer deps, simpler audit |
| MySQL (remote server) | SQLite (file-based) | No network attack surface |
| bcrypt (C extensions) | Werkzeug PBKDF2 (pure Python) | Built into Flask |
| 15+ npm packages | **2 Python packages** | Tiny attack surface |

**Total external dependencies: Flask + PyJWT — that's it.**

---

## 📁 Project Structure

```
college-voting-secure/
├── start.py                ← ONE command to run everything
├── requirements.txt
│
├── backend/
│   ├── app.py              ← All API routes (Flask)
│   ├── auth.py             ← JWT helpers
│   └── db.py               ← SQLite helper (parameterised queries)
│
├── database/
│   ├── init_db.py          ← Create DB + seed data
│   └── voting.db           ← Auto-created on first run
│
└── frontend/
    └── index.html          ← Complete app (single file, no build step)
```

---

## 🚀 Setup in 3 Steps

### Step 1 — Install Python packages
```bash
pip install Flask==3.1.2 PyJWT==2.7.0
```

### Step 2 — Initialize the database
```bash
python3 database/init_db.py
```

### Step 3 — Start the server
```bash
python3 start.py
```

Open browser at: **http://localhost:5000**

That's it. No npm, no build step, no MySQL server.

---

## 🔑 Demo Credentials

### Student Portal
| Student ID | Password |
|-----------|---------|
| CS2024001 | student123 |
| CS2024002 | student123 |
| EC2024001 | student123 |

### Admin Portal
| Username | Password |
|---------|---------|
| admin | admin123 |

---

## 🔒 Security Features

### Authentication
- **PBKDF2-SHA256** password hashing via Werkzeug (same as Django uses)
- **JWT tokens** signed with HS256, expire in 24h (students) / 8h (admins)
- **Role separation**: student tokens cannot access admin routes and vice versa

### SQL Injection Prevention
- **100% parameterised queries** — no string formatting in any SQL
- SQLite with foreign key enforcement

### Anonymity Architecture
```
votes table:    nominee_id | position | voted_at
                  (NO student_id — anonymous by design)

students table: id | student_id | has_voted
                  (records WHO voted, not WHAT they voted for)
```
These two facts can never be joined together — anonymity is structural.

### Input Validation
- All inputs capped at sane lengths (name: 150 chars, password: 128 chars, etc.)
- Request body limited to 16 KB
- Rate limiting: 10 login attempts per minute per IP (5 for admin)

### HTTP Security Headers
Every response includes:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy` (restricts script/style sources)
- `Referrer-Policy: strict-origin-when-cross-origin`

### No CORS Needed
Frontend is served by the same Flask server — no cross-origin requests.

---

## 🌐 API Endpoints

### Public
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/student/login` | Student login |
| POST | `/api/auth/admin/login` | Admin login |
| GET  | `/api/election/status` | Current election status |

### Student (JWT required)
| Method | Path | Description |
|--------|------|-------------|
| GET  | `/api/nominees` | List all nominees |
| POST | `/api/vote` | Cast anonymous vote |

### Admin (Admin JWT required)
| Method | Path | Description |
|--------|------|-------------|
| GET  | `/api/admin/stats` | Dashboard statistics |
| GET  | `/api/admin/results` | Vote results by position |
| PUT  | `/api/admin/election` | Start/stop voting |
| GET/POST | `/api/admin/nominees` | List or add nominees |
| DELETE | `/api/admin/nominees/<id>` | Remove nominee |
| GET/POST | `/api/admin/students` | List or add students |
| DELETE | `/api/admin/students/<id>` | Remove student |
| POST | `/api/admin/reset-votes` | Reset all votes (testing) |

---

## ⚙️ Configuration

### Environment Variables (set before running)
```bash
export SECRET_KEY="your-long-random-secret-here"   # REQUIRED in production
export PORT=5000                                     # Optional, default 5000
export DEBUG=false                                   # Never true in production
```

### For Production
1. Set a strong `SECRET_KEY` (use `python3 -c "import secrets; print(secrets.token_hex(32))"`)
2. Use a proper WSGI server: `pip install gunicorn && gunicorn backend.app:app`
3. Put nginx in front for HTTPS
4. Back up `database/voting.db` regularly

---

## 🗃️ Database Schema

```sql
-- admins: admin accounts
CREATE TABLE admins (
  id       INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,         -- PBKDF2-SHA256 hash
  name     TEXT NOT NULL
);

-- students: registered voters
CREATE TABLE students (
  id         INTEGER PRIMARY KEY,
  student_id TEXT UNIQUE NOT NULL,
  name       TEXT NOT NULL,
  department TEXT,
  password   TEXT NOT NULL,       -- PBKDF2-SHA256 hash
  has_voted  INTEGER DEFAULT 0    -- 0=no, 1=yes (boolean)
);

-- election: single-row config
CREATE TABLE election (
  id        INTEGER PRIMARY KEY CHECK (id = 1),
  name      TEXT NOT NULL,
  is_active INTEGER DEFAULT 0
);

-- nominees: candidates
CREATE TABLE nominees (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  position   TEXT NOT NULL,
  department TEXT,
  bio        TEXT,
  vote_count INTEGER DEFAULT 0   -- aggregate only
);

-- votes: ANONYMOUS — no student_id stored here
CREATE TABLE votes (
  id         INTEGER PRIMARY KEY,
  nominee_id INTEGER NOT NULL REFERENCES nominees(id),
  position   TEXT NOT NULL,
  voted_at   TEXT DEFAULT (datetime('now'))
);
```
