# QuizVoro — Live Quiz Application Backend

## Developer 1: Authentication and Quiz Management Implementation

This repository contains the backend implementation for **Developer 1 — Authentication and Quiz Management** of the QuizVoro live quiz application (a Kahoot-like multiplayer quiz platform).

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Developer 1 Responsibilities](#2-developer-1-responsibilities)
3. [Technology Stack](#3-technology-stack)
4. [Project Structure](#4-project-structure)
5. [Prerequisites](#5-prerequisites)
6. [Python Installation & Setup](#6-python-installation--setup)
7. [PostgreSQL Installation & Setup](#7-postgresql-installation--setup)
8. [Database Creation](#8-database-creation)
9. [Virtual Environment Setup](#9-virtual-environment-setup)
10. [Dependency Installation](#10-dependency-installation)
11. [Environment Variable Configuration](#11-environment-variable-configuration)
12. [Admin Account Creation](#12-admin-account-creation)
13. [Database Migrations (Alembic)](#13-database-migrations-alembic)
14. [Backend Startup Commands](#14-backend-startup-commands)
15. [Interactive Swagger Documentation](#15-interactive-swagger-documentation)
16. [API Endpoint Reference](#16-api-endpoint-reference)
17. [Authentication Instructions](#17-authentication-instructions)
18. [Example: Quiz Creation Request](#18-example-quiz-creation-request)
19. [Example: Round Creation Request](#19-example-round-creation-request)
20. [Example: Question Creation Request](#20-example-question-creation-request)
21. [Multimedia Upload Instructions](#21-multimedia-upload-instructions)
22. [Testing Commands](#22-testing-commands)
23. [Troubleshooting Guide](#23-troubleshooting-guide)
24. [Integration with Developer 2 & Developer 3](#24-integration-with-developer-2--developer-3)
25. [Developer 2: Participants and Scoring](#25-developer-2-participants-and-scoring)

---

## 1. Project Overview

The **QuizVoro Live Quiz Application** is a real-time, interactive, Kahoot-like trivia platform engineered to support hundreds of concurrent participants across multiple rounds and media-rich multiple-choice questions (MCQs).

The backend team responsibilities are partitioned as follows:
- **Developer 1 (This implementation)**: Administrator authentication, role-based authorization, quiz creation/management, round creation/management, question and option creation, multimedia attachments, and core database schema foundation.
- **Developer 2**: Participant join workflows (PIN/QR code), live answer submission, answer validation, duplicate prevention, and real-time score calculations.
- **Developer 3**: WebSocket engine, real-time event broadcasting (`QUESTION_STARTED`, `TIMER_UPDATED`, `LEADERBOARD_UPDATED`, etc.), host game orchestrator, and stage displays.

---

## 2. Developer 1 Responsibilities

1. **Admin Security**: Argon2 password hashing, JWT Bearer token generation, and secure route guard dependencies.
2. **Quiz Management**: Full lifecycle management of quizzes tied to their owning administrators.
3. **Round Management**: Round ordering, uniqueness constraint enforcement per quiz (`round_number`), and cascading relationship handling.
4. **Question & Option Management**: Atomic persistence of MCQ questions with 2–6 options, exact single-correct-answer validation, time limits (5–300s), points (0–10000), and display sequencing (`question_order`).
5. **Multimedia Storage**: File validation (MIME-type check, size restriction), UUID-based disk storage, and database URL reference association.
6. **Data Security & Cheating Prevention**: Strict schema separation between `AdminQuestionOut` (includes `is_correct`) and `ParticipantQuestionOut` (deliberately omits `is_correct`).
7. **Database & Migrations**: PostgreSQL schema definitions using SQLAlchemy 2.0 ORM and version-controlled migration scripts via Alembic.
8. **Automated Testing**: 54 comprehensive test cases covering authentication, authorization, CRUD operations, edge cases, and media handling.

---

## 3. Technology Stack

- **Language**: Python 3.11+ / 3.12
- **Web Framework**: FastAPI (v0.115.5)
- **ASGI Server**: Uvicorn (v0.32.1)
- **Database**: PostgreSQL (relational database)
- **Database Driver**: Psycopg 3 (v3.2.3 binary)
- **ORM**: SQLAlchemy (v2.0.36)
- **Migrations**: Alembic (v1.14.0)
- **Validation**: Pydantic v2 (v2.10.1) & Pydantic-Settings (v2.6.1)
- **Password Hashing**: Passlib with Argon2 (`argon2-cffi` v23.1.0)
- **JWT**: Python-Jose with Cryptography (v3.3.0)
- **File Uploads**: Python-Multipart (v0.0.12)
- **Testing**: Pytest (v8.3.3), Pytest-Asyncio (v0.24.0), HTTPX (v0.27.2)

---

## 4. Project Structure

```
quiz-backend/
├── .env                     # Local environment configuration (git-ignored)
├── .env.example             # Configuration template with placeholder values
├── .gitignore               # Ignored files (venv, .env, __pycache__, test artifacts)
├── alembic.ini              # Alembic migration configuration
├── create_admin.py          # Interactive CLI script for creating admins safely
├── pytest.ini               # Pytest configuration
├── requirements.txt         # Pinned production and development dependencies
├── alembic/                 # Database migration scripts
│   ├── env.py               # Alembic runner configured to load app.models & Settings
│   ├── script.py.mako       # Migration template
│   └── versions/            # Version-controlled migration history
│       └── 35a0f2fc1941_initial_schema_all_tables.py
├── app/                     # Main application package
│   ├── __init__.py
│   ├── config.py            # Pydantic Settings with validation
│   ├── database.py          # SQLAlchemy engine, session maker, get_db dependency
│   ├── dependencies.py      # Auth guards (get_current_admin, require_admin)
│   ├── main.py              # FastAPI app instance, CORS middleware, router registration
│   ├── models.py            # SQLAlchemy ORM models (Dev 1 models + shared stubs)
│   ├── schemas.py           # Pydantic request/response models (Admin vs Participant)
│   ├── security.py          # Argon2 hashing and JWT token encode/decode
│   ├── routers/             # Route controllers
│   │   ├── __init__.py
│   │   ├── auth.py          # /api/v1/admin/login and /api/v1/admin/me
│   │   ├── quizzes.py       # /api/v1/quizzes
│   │   ├── rounds.py        # /api/v1/quizzes/{quizId}/rounds and /api/v1/rounds/{roundId}
│   │   └── questions.py     # /api/v1/rounds/{roundId}/questions and media endpoints
│   └── services/            # Business logic and database operations
│       ├── __init__.py
│       ├── auth_service.py
│       ├── quiz_service.py
│       ├── round_service.py
│       └── question_service.py
├── media/                   # Local media storage directory for uploaded files
└── tests/                   # Comprehensive automated test suite
    ├── __init__.py
    ├── conftest.py          # Fixtures, test database override, mock auth tokens
    ├── test_auth.py         # Login, invalid credentials, token verification
    ├── test_quizzes.py      # Quiz CRUD, ownership verification, validation
    ├── test_rounds.py       # Round CRUD, duplicate number enforcement
    ├── test_questions.py    # MCQ validation, points, time limit, answer secrecy
    └── test_media.py        # File validation, mime-type verification, size limits
```

---

## 5. Prerequisites

Before installing the project, verify you have the following installed on Windows:
1. **Python 3.11 or 3.12**: Verify via `python --version`
2. **PostgreSQL 14, 15, or 16**: Ensure PostgreSQL service is running
3. **PowerShell**: Built-in to Windows

---

## 6. Python Installation & Setup

If Python is not installed:
1. Download Python 3.11 or 3.12 from [python.org](https://www.python.org/downloads/).
2. **Crucial**: During installation, check the box that says **"Add Python to PATH"**.
3. Verify the installation in Windows PowerShell:
   ```powershell
   python --version
   pip --version
   ```

---

## 7. PostgreSQL Installation & Setup

If PostgreSQL is not yet installed:
1. Download the installer from [EnterpriseDB PostgreSQL](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads).
2. Install with default settings (port `5432`). Note the `postgres` superuser password chosen during installation.
3. Verify the PostgreSQL service is running in PowerShell:
   ```powershell
   Get-Service -Name postgresql*
   ```

---

## 8. Database Creation

Open PowerShell and connect to PostgreSQL using `psql` to create the application user and database:

```powershell
# Open psql as the postgres user (you will be prompted for your postgres password)
psql -U postgres
```

Inside the `psql` prompt, execute:

```sql
-- 1. Create dedicated application user
CREATE USER quiz_user WITH PASSWORD 'your_secure_password';

-- 2. Create the application database
CREATE DATABASE quiz_app OWNER quiz_user;

-- 3. Grant privileges
GRANT ALL PRIVILEGES ON DATABASE quiz_app TO quiz_user;

-- 4. Exit psql
\q
```

---

## 9. Virtual Environment Setup

Navigate to the `quiz-backend` directory and create an isolated virtual environment:

```powershell
# Navigate into the backend directory
cd c:\Users\cvpra\OneDrive\Desktop\QuizVoro\quiz-backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

*(Note: If PowerShell shows an Execution Policy error when running scripts, run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` and re-activate).*

---

## 10. Dependency Installation

Install all required dependencies using `pip`:

```powershell
pip install -r requirements.txt
```

Verify that all packages are installed correctly:
```powershell
pip list
```

---

## 11. Environment Variable Configuration

Create your `.env` configuration file from the template `.env.example`:

```powershell
Copy-Item .env.example .env
```

Open `.env` in your text editor and fill in your database credentials and a 32+ character secret key:

```ini
# PostgreSQL Connection (replace your_secure_password with your real DB password)
DATABASE_URL=postgresql+psycopg://quiz_user:your_secure_password@localhost:5432/quiz_app

# JWT Signing Secret (must be at least 32 characters long)
JWT_SECRET_KEY=replace_this_with_a_real_secret_at_least_32_chars_long
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Media Upload Directory and Maximum Size (in Megabytes)
MEDIA_DIR=media
MAX_UPLOAD_SIZE_MB=10

# Environment mode ('development' or 'production')
ENVIRONMENT=development

# Allowed Frontend Origins for CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

To generate a cryptographically secure 32+ character JWT secret, run:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 12. Admin Account Creation

Admin accounts cannot be registered via public REST endpoints. An interactive CLI tool is provided to securely create admins with Argon2 password hashing:

```powershell
python create_admin.py
```

Prompts:
```text
==================================================
  QuizVoro — Create Admin Account
==================================================

Enter admin username: admin
Enter admin email: admin@quizvoro.com
Enter password (min 8 characters): ********
Confirm password: ********

Hashing password with Argon2 (this may take a moment)...

✓ Admin created successfully! ID: 1
  Username: admin
  Email:    admin@quizvoro.com

You can now log in via: POST /api/v1/admin/login
```

---

## 13. Database Migrations (Alembic)

Apply the database schema to your PostgreSQL database:

```powershell
# Apply all pending migrations to the latest revision
alembic upgrade head
```

To view current revision:
```powershell
alembic current
```

To inspect migration history:
```powershell
alembic history --verbose
```

---

## 14. Backend Startup Commands

Run the FastAPI development server with automatic code reloading:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Console output:
```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

---

## 15. Interactive Swagger Documentation

FastAPI provides interactive API documentation out of the box:

- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI JSON specification**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

In Swagger UI, click the green **"Authorize"** button and enter `Bearer <your_jwt_token>` to authenticate requests directly from your browser.

---

## 16. API Endpoint Reference

All endpoints strictly follow the `/api/v1/` prefix requirement.

### Authentication (`/api/v1/admin`)
| Method | Endpoint | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/admin/login` | **Required**: Authenticate admin with username/password, returns JWT token | `200 OK` |
| `GET` | `/api/v1/admin/me` | *Additional*: Retrieve authenticated admin profile | `200 OK` |

### Quizzes (`/api/v1/quizzes`)
| Method | Endpoint | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/quizzes` | **Required**: Create new quiz for authenticated admin | `201 Created` |
| `GET` | `/api/v1/quizzes` | *Additional*: List all quizzes owned by authenticated admin | `200 OK` |
| `GET` | `/api/v1/quizzes/{quizId}` | *Additional*: Get quiz details with all rounds and questions | `200 OK` |
| `PATCH` | `/api/v1/quizzes/{quizId}` | *Additional*: Partially update quiz title, description, or published state | `200 OK` |
| `DELETE` | `/api/v1/quizzes/{quizId}` | *Additional*: Delete quiz and cascade delete all child rounds & questions | `204 No Content` |

### Rounds (`/api/v1/quizzes/{quizId}/rounds` & `/api/v1/rounds/{roundId}`)
| Method | Endpoint | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/quizzes/{quizId}/rounds` | **Required**: Create round within a quiz (enforces unique `round_number`) | `201 Created` |
| `GET` | `/api/v1/quizzes/{quizId}/rounds` | *Additional*: List all rounds in quiz ordered by `round_number` | `200 OK` |
| `GET` | `/api/v1/rounds/{roundId}` | *Additional*: Retrieve single round with questions | `200 OK` |
| `PATCH` | `/api/v1/rounds/{roundId}` | *Additional*: Update round title, description, or round number | `200 OK` |
| `DELETE` | `/api/v1/rounds/{roundId}` | *Additional*: Delete round and cascade delete all questions | `204 No Content` |

### Questions & Options (`/api/v1/rounds/{roundId}/questions` & `/api/v1/questions/{questionId}`)
| Method | Endpoint | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/rounds/{roundId}/questions` | **Required**: Create question with MCQ options atomically | `201 Created` |
| `GET` | `/api/v1/rounds/{roundId}/questions` | *Additional*: List all questions in round ordered by `question_order` | `200 OK` |
| `GET` | `/api/v1/questions/{questionId}` | *Additional*: Get question details (Admin only: includes `is_correct`) | `200 OK` |
| `PATCH` | `/api/v1/questions/{questionId}` | *Additional*: Update question text, time limit, points, or order | `200 OK` |
| `DELETE` | `/api/v1/questions/{questionId}` | *Additional*: Delete question and its options | `204 No Content` |

### Multimedia (`/api/v1/questions/{questionId}/media`)
| Method | Endpoint | Description | Status |
|---|---|---|---|
| `POST` | `/api/v1/questions/{questionId}/media` | *Additional*: Upload media file (image/audio/video) for question | `201 Created` |
| `GET` | `/api/v1/questions/{questionId}/media` | *Additional*: Stream/download attached media file | `200 OK` |

### Health Check
| Method | Endpoint | Description | Status |
|---|---|---|---|
| `GET` | `/health` | Application liveness probe | `200 OK` |

---

## 17. Authentication Instructions

To access protected endpoints, provide the JWT in the HTTP `Authorization` header:

```http
Authorization: Bearer <your_access_token>
```

### Step 1: Login to get token (PowerShell)
```powershell
$body = @{
    username = "admin"
    password = "your_secure_password"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/admin/login" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$token = $response.access_token
Write-Host "Obtained Token: $token"
```

---

## 18. Example: Quiz Creation Request

```powershell
$headers = @{
    Authorization = "Bearer $token"
}

$quizBody = @{
    title = "QuizVoro Annual Tech Challenge 2026"
    description = "Grand finale live quiz covering Python, Cloud, and AI"
} | ConvertTo-Json

$quiz = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/quizzes" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $quizBody

Write-Host "Created Quiz ID: $($quiz.id)"
```

---

## 19. Example: Round Creation Request

```powershell
$roundBody = @{
    title = "Round 1 — Python & Algorithms"
    description = "Rapid fire questions with 30s timers"
    round_number = 1
} | ConvertTo-Json

$round = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/quizzes/$($quiz.id)/rounds" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $roundBody

Write-Host "Created Round ID: $($round.id)"
```

---

## 20. Example: Question Creation Request

```powershell
$questionBody = @{
    question_text = "What is the time complexity of searching in a Python dictionary on average?"
    question_type = "MCQ"
    time_limit = 20
    points = 1000
    question_order = 1
    options = @(
        @{ option_text = "O(1)"; is_correct = $true },
        @{ option_text = "O(n)"; is_correct = $false },
        @{ option_text = "O(log n)"; is_correct = $false },
        @{ option_text = "O(n^2)"; is_correct = $false }
    )
} | ConvertTo-Json -Depth 5

$question = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/rounds/$($round.id)/questions" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $questionBody

Write-Host "Created Question ID: $($question.id)"
```

---

## 21. Multimedia Upload Instructions

Attach an image, audio clip, or video to any question:

- Supported image types: JPEG (`.jpg`, `.jpeg`), PNG (`.png`), GIF (`.gif`), WebP (`.webp`)
- Supported audio types: MP3 (`.mp3`), WAV (`.wav`), OGG (`.ogg`)
- Supported video types: MP4 (`.mp4`), WebM (`.webm`)
- Maximum size: Configured via `MAX_UPLOAD_SIZE_MB` in `.env` (default: 10 MB)

### Upload media with PowerShell:
```powershell
$filePath = "c:\path\to\diagram.png"
$url = "http://127.0.0.1:8000/api/v1/questions/$($question.id)/media"

# Using curl.exe (available on modern Windows)
curl.exe -X POST $url `
    -H "Authorization: Bearer $token" `
    -F "file=@$filePath;type=image/png"
```

The server returns:
```json
{
  "question_id": 1,
  "media_url": "/media/4a9f3b9281a44e4b9f3387b3e1f57e0a.png",
  "media_type": "image"
}
```

The binary file is safely stored in `quiz-backend/media/` with a UUID-generated filename to eliminate path traversal vulnerabilities and filename collisions.

---

## 22. Testing Commands

Run the full automated test suite using `pytest`:

```powershell
# Run all tests with verbose output
pytest tests/ -v
```

Expected result:
```text
======================== 54 passed, 2 warnings in ~38s ========================
```

To run a specific test file:
```powershell
pytest tests/test_auth.py -v
pytest tests/test_quizzes.py -v
pytest tests/test_rounds.py -v
pytest tests/test_questions.py -v
pytest tests/test_media.py -v
```

Tests run automatically against an isolated in-memory SQLite database, leaving your PostgreSQL development database pristine.

---

## 23. Troubleshooting Guide

| Issue | Cause | Solution |
|---|---|---|
| `psycopg.OperationalError: connection to server failed` | PostgreSQL service not running or wrong port | Run `Get-Service -Name postgresql*` in PowerShell. Ensure PostgreSQL service is Running. Check host and port 5432 in `.env`. |
| `FATAL: password authentication failed for user "quiz_user"` | Incorrect password in `DATABASE_URL` | Check password specified in `.env`. Test login using `psql -U quiz_user -d quiz_app`. |
| `JWT_SECRET_KEY must be at least 32 characters long` | Short secret in `.env` | Run `python -c "import secrets; print(secrets.token_hex(32))"` and paste the result into `.env`. |
| `ExecutionPolicy` error running `Activate.ps1` | Windows script execution disabled | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` in PowerShell. |
| `401 Unauthorized: Could not validate credentials` | Missing or invalid Bearer token | Ensure header format is `Authorization: Bearer <token>` without extra spaces. |
| `409 Conflict: Round number X already exists` | Attempting to create duplicate round number | Each round within a quiz must have a unique `round_number`. Provide the next sequence integer. |
| `409 Conflict: Question order X is already used` | Duplicate question display order | Each question within a round must have a unique `question_order`. |
| `422 Unprocessable Entity: MCQ questions must have exactly one correct option` | Zero or multiple options marked `is_correct = true` | Ensure exactly 1 option has `is_correct: true` and all others have `is_correct: false`. |

---

## 24. Integration with Developer 2 & Developer 3

### Database Compatibility
All 10 tables from the project specification are present in `app/models.py` and Alembic migrations:
- **Developer 1**: `admins`, `quizzes`, `rounds`, `questions`, `options`
- **Shared / Developer 2**: `participants`, `game_participants`, `answers`
- **Shared / Developer 3**: `games`

Foreign keys are already defined:
- `games.quiz_id` -> `quizzes.id` (RESTRICT)
- `games.current_question_id` -> `questions.id` (SET NULL)
- `answers.question_id` -> `questions.id` (CASCADE)
- `answers.chosen_option_id` -> `options.id` (SET NULL)

### Question Data Security Contract
To prevent cheating:
- Developer 1 has implemented `ParticipantQuestionOut` in `app/schemas.py`.
- `ParticipantQuestionOut` includes `id`, `question_text`, `question_type`, `time_limit`, `points`, `media_url`, and `options` (`id`, `option_text`).
- `ParticipantQuestionOut` **never includes** `is_correct`.
- **Developer 2 and 3**: When sending questions to participants or broadcasting real-time quiz updates before the answer reveal, serialize questions using `ParticipantQuestionOut`.

---

## 25. Developer 2: Participants and Scoring

Players join with the PIN and a nickname, answer the open question, and are scored once per question at the reveal.

- Routes: `app/routers/games.py`
- Services: `app/services/participant_service.py` (games, join, rejoin), `answer_service.py` (current question, answers, scoring), `leaderboard_service.py`
- Rules: `app/scoring.py` (pure functions), nickname filter in `app/nicknames.py` + `app/blocked_words.txt`
- Migration `6271d3a819b1` adds the new columns and the `scored_questions` table: run `alembic upgrade head`.

### Endpoints (`/api/v1/games`)
| Method | Endpoint | Who | Description | Status |
|---|---|---|---|---|
| `POST` | `/api/v1/games` | Admin | Create a game for your quiz; returns the 8-digit `pin`. The quiz needs at least one question (`409` otherwise), and creating the game publishes it, so Developer 1's lock refuses edits to its rounds, questions and answers while it is live | `201 Created` |
| `POST` | `/api/v1/games/join` | Player | `{pin, nickname}` → `token` (the phone keeps it in localStorage) | `201 Created` |
| `POST` | `/api/v1/games/rejoin` | Player | `{pin, token}` → the same player, score and streak | `200 OK` |
| `GET` | `/api/v1/games/{gameId}/questions/current` | Player | Open question without `is_correct` (options listed by id), plus `question_number` / `total_questions` (for "QUESTION 1/2"), `opened_at`, `deadline`, `server_time`, `already_answered` | `200 OK` |
| `GET` | `/api/v1/games/{gameId}/current-question` | Player | Same as `/questions/current` (alias used by the frontend) | `200 OK` |
| `POST` | `/api/v1/games/{gameId}/answers` | Player | `{question_id, option_id}` or `{question_id, selected_option}` (see below); replies `{success: true, message: "Answer locked in!", accepted, question_id, option_id, response_time_ms}`, never whether it is right | `201 Created` |
| `POST` | `/api/v1/games/{gameId}/questions/{questionId}/score` | Admin (quiz owner) | Score the open question. Repeat calls change nothing and return the same result with `already_scored: true` | `200 OK` |
| `GET` | `/api/v1/games/{gameId}/leaderboard` | Anyone | `?limit=10`, `?round_id=` for one round; includes `rank_delta`, `climbers`, `close_battles` | `200 OK` |
| `GET` | `/api/v1/games/{gameId}/me` | Player | Score, rank, streak and `last_result` for the latest scored question | `200 OK` |

**Choosing an option:** send exactly one of `option_id` or `selected_option`, otherwise `422`. `selected_option` is a letter `"A"`-`"D"` (any case) or an index `0`-`3`, counted over the question's options ordered by id, which is the order the current question lists them. For example, `"B"` and `1` both pick the second option. A letter past the question's last option (such as `"D"` on a three-option question) returns `422`. The reply's `option_id` says which option was recorded.

**No rate limiting on join or answers:** unlike admin login, these endpoints deliberately have no per-IP limit, because the whole venue shares one Wi-Fi or carrier IP and a per-IP limit would lock out the room. Duplicates are already blocked by the database: one answer per player per question, and one nickname per game.

Player endpoints need the header `X-Participant-Token: <token>`: missing or unknown → `401`, removed or another game's token → `403`. Rejected answers return `409` with a message to show (paused, not open, late, already answered, closed); an option from another question returns `422`.

**Scoring:** a correct answer earns `round(points × (1 − 0.5 × time / time_limit))`, timed on the server from `current_question_started_at`. Wrong or no answer earns 0. Answers up to 300 ms after the deadline score half; later ones are rejected. Ties are broken by more correct answers, then less total time on correct answers, then earlier join.

### For Developer 3
Game control sets these columns on `games`; Developer 2 code only reads them.

- **Open a question:** `status = "active"`, `current_question_id = question.id`, `current_question_started_at = datetime.now(timezone.utc)`. A time in the future gives a "get ready" countdown; answers are refused until then.
- **Pause:** `status = "paused"` and remember when (`paused_at`). Answers are refused while paused.
- **Resume:** `current_question_started_at += now - paused_at`, then `status = "active"`. Shifting the start forward means paused time never counts against anyone's time or points.
- **Reveal:** call the service directly (works from a timer, no admin needed):
  ```python
  from app.services import answer_service, leaderboard_service, participant_service

  game = participant_service.get_game_by_id(db, game_id)
  result = answer_service.score_question(db, game, question_id)  # safe to call twice
  board = leaderboard_service.get_leaderboard(db, game, limit=10)
  ```
  Broadcast `result` (correct option, answer distribution) and `board`, then open the next question. Only the open question can be scored, and answers to it are refused once it is scored, so an early reveal is fine.
- **Remove a player:** set `GameParticipant.is_active = False`. They can no longer answer or rejoin, and are left out of scoring and leaderboards.
- **WebSockets:** authenticate a player with `participant_service.get_participant_by_token(db, token)`, and send questions only as `ParticipantQuestionOut`.

### Tests
```powershell
pytest tests/test_scoring.py tests/test_games.py -v
```
The full suite (`pytest tests/ -v`) is 267 tests: Developer 1's 68, Developer 2's 180, and Developer 3's 19 real-time tests.

---

## 26. Developer 3: Real-Time WebSockets and Host Controls

Developer 3 provides live, bi-directional WebSocket communication, host game lifecycle orchestration, and stage display broadcasting.

### Architecture & Scalability
- **Connection Manager**: In-memory room manager partitioned by `game_id` and role (`hosts`, `participants`, `stages`).
- **Concurrency**: Designed for hundreds of concurrent players per quiz room on a single ASGI application worker.
- **Multi-Worker Note**: In-memory connection management requires a single application worker (`uvicorn --workers 1`). For multi-worker deployments (e.g. distributed across multiple pods or behind a load balancer), an external pub/sub layer (such as Redis Pub/Sub) must be configured to synchronize room broadcasts across worker processes.

### Endpoints

#### 1. Host Control REST API (`/api/v1/games`)
All endpoints require admin authentication (`Authorization: Bearer <token>`) and quiz ownership.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/games/{gameId}/stage-token` | Generate a cryptographically signed token for the public stage display screen. |
| `POST` | `/api/v1/games/{gameId}/start` | Transition game from `lobby` to `active` and open Question 1. |
| `POST` | `/api/v1/games/{gameId}/next-question` | Advance to the next question in round/question sequence, or finish if on the last question. |
| `POST` | `/api/v1/games/{gameId}/pause` | Pause countdown timer and refuse answers. |
| `POST` | `/api/v1/games/{gameId}/resume` | Resume timer, shifting start time forward so paused duration does not count. |
| `POST` | `/api/v1/games/{gameId}/reveal` | Close question, score answers via `answer_service`, and broadcast results. |
| `POST` | `/api/v1/games/{gameId}/end` | Manually end the game and broadcast final leaderboard. |
| `POST` | `/api/v1/games/{gameId}/kick` | Deactivate a participant (`is_active = False`) and disconnect their live session. |

#### 2. WebSocket Endpoints (`/api/v1/ws/games`)
| Endpoint | Who | Auth Query Param | Behavior |
|---|---|---|---|
| `/api/v1/ws/games/{gameId}/host` | Admin Host | `?token=<admin_jwt>` | Receives game events and can send host commands (`START`, `NEXT_QUESTION`, `PAUSE`, `RESUME`, `REVEAL`, `END`, `KICK`). |
| `/api/v1/ws/games/{gameId}/participant` | Player | `?token=<participant_token>` | Receives question starts, answer reveals with personal stats, and leaderboard updates. Can submit answers via `SUBMIT_ANSWER`. Host commands are strictly rejected. |
| `/api/v1/ws/games/{gameId}/stage` | Stage Display | `?token=<stage_token>` | Read-only screen for audience/projector display. Any command sent is rejected. |

### Cheating Prevention & Data Isolation
- `QUESTION_STARTED` broadcasts always serialize question data through `ParticipantQuestionOut` (`app/schemas.py`), which deliberately omits `is_correct`.
- Individual answers remain private. Hosts and Stage screens receive only aggregated answer counts (`ANSWER_COUNT_UPDATED`) during the active question phase.
- Personal results (`last_result`, streak, rank delta) are unicast to the specific participant via `send_to_participant`.
- Stage display screens cannot connect with a game ID or PIN alone; they require a cryptographically signed stage token issued by the quiz host.

### Testing Commands
```powershell
# Run Developer 3 real-time tests
pytest tests/test_realtime.py -v

# Run the complete test suite (267 passed)
pytest tests/ -v
```
