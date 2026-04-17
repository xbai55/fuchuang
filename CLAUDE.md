# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A fraud detection and prevention warning system (反诈预警系统) that uses multi-modal input (text/audio/image), RAG-based knowledge retrieval, and LLM-powered risk assessment to deliver real-time fraud warnings with personalized alerts.

## Development Environment

All development uses the conda environment **`fc`**. Always activate it before running any commands:
```bash
conda activate fc
```

## Commands

### Backend

```bash
cd backend
conda run -n fc pip install -r requirements.txt
python main.py                          # http://localhost:8000
uvicorn main:app --reload               # hot reload
# API docs: http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev                             # http://localhost:3000
npm run build
npm run preview
```

### Combined startup

```bash
./start.sh    # starts both backend and frontend
./stop.sh     # stops both
```

### Data ingestion (ETL)

```bash
# From local file (CSV / JSON / JSONL / HTML)
python scripts/ingest_cases.py --file data/cases.csv --source my_batch
python scripts/ingest_cases.py --file data/page.html --source web_scrape

# From live URL(s)
python scripts/ingest_cases.py --url https://example.com/case/123 --source web_live
python scripts/ingest_cases.py --url-list data/urls.txt --source bulk --delay 2.0

# Common flags
#   --no-enrich   skip LLM tagging (fast)
#   --dry-run     validate without writing to DB
```

ETL modules in `scripts/etl/`:
- `cleaner.py`     — unicode normalisation, HTML strip, PII masking, dedup hash
- `enricher.py`    — Doubao LLM tagger (scam_type, keywords, severity)
- `html_parser.py` — BeautifulSoup4 extractor; auto-detects list pages vs. detail pages
- `scraper.py`     — `requests`-based fetcher with retries, encoding detection, polite delay

### Coze workflow (AI pipeline server)

```bash
bash scripts/http_run.sh    # HTTP server for Coze platform
bash scripts/local_run.sh   # local dev run
```

## Architecture

The system has three distinct layers that work together:

### 1. Frontend (`frontend/src/`)

React 18 + TypeScript + Vite + Ant Design + Tailwind CSS. Main pages: Login/Register, ChatPage (primary interaction), ContactsPage. The `services/api.ts` module handles all HTTP calls to the backend. Vite proxies `/api` to `localhost:8000`.

### 2. Backend (`backend/`)

FastAPI application. Three route modules registered in `main.py`:

- `api/auth.py` — JWT-based registration/login
- `api/contacts.py` — guardian/contact management
- `api/fraud_detection.py` — receives user messages, calls the LangGraph workflow, persists results to SQLite via `database.py` (SQLAlchemy)

Key schemas in `schemas.py`; JWT logic in `auth.py`.

### 3. AI Workflow (`src/`)

LangGraph pipeline defined in `src/graphs/graph.py`. The workflow is also exposed as a Coze-compatible HTTP server via `src/main.py`. Global state is typed in `src/graphs/state.py`.

**Pipeline (6 nodes):**

```
multimodal_input → knowledge_search → risk_assessment → risk_decision (branch)
                                                              ↓
                                               intervention → report_generation
```

- **multimodal_input** (`nodes/multimodal_input_node.py`): text pass-through, audio via FunASR Paraformer ASR, image via OCR
- **knowledge_search** (`nodes/knowledge_search_node.py`): RAG retrieval for similar fraud cases and legal references
- **risk_assessment** (`nodes/risk_assessment_node.py`): Doubao LLM (`doubao-seed-1-8-251228`, temp=0.3) scores 0–100 and identifies fraud type; config in `config/risk_assessment_cfg.json`
- **risk_decision** (`nodes/risk_decision_node.py`): conditional branch — <40 low, 40–75 medium, >75 high
- **intervention** (`nodes/intervention_node.py`): LLM generates personalized warning based on user role (elderly/student/finance/general); config in `config/intervention_cfg.json`
- **report_generation** (`nodes/report_generation_node.py`): produces final Markdown report; config in `config/report_generation_cfg.json`

### 4. Audio Module (`audio_module/`)

Standalone FunASR Paraformer inference pipeline. `audio_inference.py` is the main entry; `VAD.py` handles voice activity detection. Model weights in `audio_module/weights/`.

## Key Technologies


| Layer       | Stack                                                                            |
| ----------- | -------------------------------------------------------------------------------- |
| Frontend    | React 18, TypeScript, Vite, Ant Design 5, Tailwind CSS, React Router 6, Axios    |
| Backend     | FastAPI, SQLAlchemy 2 (SQLite dev / PostgreSQL prod), PyJWT, BCrypt, APScheduler |
| AI/Workflow | LangGraph 1.0, LangChain 1.0, Coze SDK, Doubao LLM, FunASR Paraformer            |

## Database Models

- **User**: id, username, email, hashed_password, user_role, guardian_name
- **Contact**: id, user_id (FK), name, phone, relationship, is_guardian
- **ChatHistory**: id, user_id (FK), user_message, bot_response, risk_score, risk_level, scam_type, guardian_alert

## API Surface

```
POST /api/auth/register    POST /api/auth/login
GET  /api/auth/me          PUT  /api/auth/me

GET    /api/contacts/
POST   /api/contacts/
PUT    /api/contacts/{id}
DELETE /api/contacts/{id}

POST /api/fraud/detect     # main fraud analysis endpoint
GET  /api/fraud/history
```

## System Instructions

You are a senior engineer. Be terse. No explanations unless asked.
When fixing code: show only the changed lines + brief comment.
When answering questions: one sentence if possible.
Never repeat my question back to me. Never say "Great question!".Be maximally concise. No greetings, no apologies, no filler.
Answer directly. If explaining, use bullet points only.
Skip context I already know. Start with the answer, not the reasoning.
Max response: 100 words unless I ask for more.
