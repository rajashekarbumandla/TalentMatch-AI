# TalentMatch AI

**Intelligent Resume Screening. Smarter Hiring Decisions.**

TalentMatch AI compares a batch of PDF/DOCX resumes against a Job Description and ranks
candidates with an explainable 0–100 score built from three parts: semantic similarity
(Sentence Transformers), weighted skill matching and experience matching. Results are stored
in Supabase PostgreSQL. It is decision support for recruiters; it never rejects candidates
automatically.

> **Status:** Phases 1–9 complete: the backend and the React recruiter dashboard work end to end, verified by 298 backend tests and 11 browser tests. Next: final documentation and deployment. This README is expanded phase by phase;
> the full methodology, API reference and deployment guide arrive with later phases.

## Architecture

```
┌──────────────────────┐   HTTPS / JSON (Axios)   ┌──────────────────────────────┐   SQL (psycopg)   ┌──────────────────────┐
│  React + Vite        │ ───────────────────────▶ │  FastAPI (Python)            │ ────────────────▶ │  Supabase PostgreSQL │
│  Tailwind, Recharts  │ ◀─────────────────────── │  parser → nlp → matching     │ ◀──────────────── │  jobs, candidates,   │
│  (Vercel)            │                          │  SQLAlchemy ORM  (Render)    │                   │  match_results, ...  │
└──────────────────────┘                          └──────────────────────────────┘                   └──────────────────────┘
                                                    local models: all-MiniLM-L6-v2, spaCy en_core_web_sm
```

The browser only talks to FastAPI. Database credentials live solely in `backend/.env`.

## Folder structure

```
TalentMatch-AI/
├── backend/
│   ├── app/                    # Python package (imported as "app.*")
│   │   ├── main.py             # FastAPI app, CORS, router registration
│   │   ├── config.py           # all settings from environment variables
│   │   ├── database.py         # SQLAlchemy engine, sessions, init_db, health check
│   │   ├── models.py           # ORM tables (jobs, candidates, analysis_history, match_results)
│   │   ├── create_tables.py    # python -m app.create_tables
│   │   ├── schemas.py          # Pydantic request/response models
│   │   ├── parser/             # pdf_parser, docx_parser, sections, experience, resume_parser
│   │   ├── nlp/                # semantic_matcher, jd_analyzer, skill_extractor + data/skills.json, education, spacy_model
│   │   ├── matching/           # scoring (hybrid formula), explanation, ranking (SQL)
│   │   ├── routes/             # job, resume, analysis, candidate, dashboard routers + serializers
│   │   ├── errors.py           # global exception handlers (consistent JSON errors)
│   │   ├── services/           # job, candidate, resume (upload), analysis, dashboard, export services
│   │   └── utils/              # text cleaning, file validation
│   ├── scripts/                # generate_sample_resumes.py
│   ├── tests/                  # pytest suite
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/              # Dashboard, NewAnalysis, Rankings, CandidateDetail, Jobs, JobEdit, History, Settings
│   │   ├── components/         # ui kit, charts, Score, Skills, FileDropzone, RequirementsEditor, Toast
│   │   ├── layouts/            # AppLayout (sidebar, top bar, notifications)
│   │   ├── hooks/              # useApi, useDebounce, useSettings
│   │   ├── services/api.js     # every API call (base URL from VITE_API_BASE_URL)
│   │   ├── utils/              # formatting, score bands, file checks, requirement helpers
│   │   ├── App.jsx, main.jsx, index.css (design tokens)
│   ├── package.json, vite.config.js, eslint.config.js
│   └── .env.example
├── sample_resumes/             # 12 synthetic PDF/DOCX resumes (fictional people)
├── sample_jds/                 # 7 synthetic job descriptions (TXT, plus a PDF and a DOCX)
├── .gitignore
└── README.md
```

The backend code sits in a `backend/app/` package rather than directly in `backend/`, so imports
look like `from app.parser import ...`. This keeps generic module names such as `config`,
`utils` and `parser` from clashing with installed libraries.

## Technology stack

| Layer | Technologies |
|---|---|
| Frontend | React 19, Vite 8, Tailwind CSS 4, React Router 7, Axios, Recharts, Lucide React, ESLint |
| Backend | Python 3.14, FastAPI, Uvicorn, Pydantic, SQLAlchemy 2, psycopg 3 |
| AI / NLP | sentence-transformers (all-MiniLM-L6-v2), spaCy (en_core_web_sm), scikit-learn, NumPy, regex, custom skill dictionary |
| Parsing | PyMuPDF (PDF), python-docx (DOCX), optional Tesseract OCR |
| Database | Supabase PostgreSQL |
| Testing | pytest, FastAPI TestClient |

No paid APIs are needed. Both models run locally on CPU.

## Prerequisites

- Python 3.14 (3.12+ should also work)
- Node.js 20+ and npm
- A free Supabase project (needed from Phase 2)

## Backend setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt   # includes CPU-only PyTorch and the spaCy English model
copy .env.example .env            # macOS/Linux: cp .env.example .env
python -m uvicorn app.main:app --reload --port 8000   # run from the backend/ folder
```

On Windows you can also just double-click / run `backend\start_backend.bat`.

Use `python -m uvicorn` / `python -m pytest` / `python -m pip` rather than the `.exe` launchers in
`.venv\Scripts\`. Smart App Control blocks those unsigned launchers (see Troubleshooting).

- Health check: http://localhost:8000/api/health
- Swagger UI: http://localhost:8000/docs

The first run downloads `all-MiniLM-L6-v2` (about 90 MB) into the Hugging Face cache.

## Frontend setup

```powershell
cd frontend
npm install
copy .env.example .env            # sets VITE_API_BASE_URL=http://localhost:8000
npm run dev                       # http://localhost:5173
```

Other scripts: `npm run build` (production build) and `npm run lint` (ESLint).

## Environment variables

| File | Variable | Purpose |
|---|---|---|
| `backend/.env` | `DATABASE_URL` | Supabase Session-pooler URL with the `postgresql+psycopg://` scheme |
| `backend/.env` | `CORS_ORIGINS` | Comma-separated frontend origins allowed to call the API |
| `backend/.env` | `WEIGHT_*`, `*_SKILL_WEIGHT` | Scoring weights (configurable, documented in `.env.example`) |
| `frontend/.env` | `VITE_API_BASE_URL` | Backend URL. Never put secrets here: `VITE_*` values are bundled into browser JS. |

## Supabase setup

1. Create a free project at https://supabase.com and save the database password.
2. Click **Connect** and copy the **Session pooler** connection string (port 5432). Session
   mode works over IPv4 and supports the prepared statements psycopg uses; the direct
   connection is IPv6-only on the free tier.
3. In `backend/.env`, set `DATABASE_URL` to that string with the scheme changed to
   `postgresql+psycopg://` and `[YOUR-PASSWORD]` replaced.
4. Create the tables. Either command works; both are safe to repeat and never delete data:
   ```powershell
   python -m app.create_tables          # or just start the API, which runs this on startup
   python -m app.create_tables --sql    # print the CREATE TABLE SQL without changing anything
   ```

## Database schema

```
jobs 1 ──< analysis_history 1 ──< match_results >── 1 candidates
jobs 1 ─────────────────────────< match_results
```

| Table | Key columns |
|---|---|
| `jobs` | `id` UUID PK, `job_title`, `description`, `required_skills` JSONB, `preferred_skills` JSONB, `minimum_experience` (NULL = not stated), `education_requirements`, `responsibilities` JSONB, `keywords` JSONB, `created_at`, `updated_at` |
| `candidates` | `id` UUID PK, `name`/`email`/`phone` (NULL = not found), `education`, `total_experience` (NULL = unknown), `extracted_skills` JSONB, `certifications` JSONB, `profile` JSONB, `resume_filename`, `file_hash` (SHA-256), `resume_text`, `created_at` |
| `analysis_history` | `id` UUID PK, `job_id` FK → jobs (cascade), `total_resumes`, `average_score`, `created_at` |
| `match_results` | `id` UUID PK, `analysis_id` FK, `job_id` FK, `candidate_id` FK (all cascade), `semantic_score`, `skills_score`, `experience_score`, `final_score`, `relevant_experience`, `matched_skills`, `missing_skills`, `additional_skills` (JSONB), `explanation`, `details` JSONB, `created_at` |

Design decisions:

- **UUID primary keys** are safe to put in URLs and can't be guessed.
- **NULL means unknown, never zero.** A resume that doesn't state experience is flagged
  *unknown*, not treated as a fresher.
- **`relevant_experience` is stored per match**, because how much experience is relevant
  depends on the job.
- **One row per candidate per analysis.** `UNIQUE(analysis_id, candidate_id)` blocks duplicate
  results, while re-running the same job creates a new, separately retrievable analysis.
- **CHECK constraints** reject scores outside 0–100 and negative experience at the database level.
- **Indexes** cover foreign keys, `analysis_history.created_at` (recent analyses) and
  `(analysis_id, final_score DESC)` (ranking query).
- **Row Level Security is enabled** on all tables, with no policies. Supabase's public REST
  API therefore can't read them, while the backend, connected as the table owner, keeps full
  access.

## Resume parsing methodology

```
file bytes ─▶ validate ─▶ extract text ─▶ clean ─▶ split into sections ─▶ extract fields
             (file_validator) (PyMuPDF /     (text_cleaner) (sections.py)   (resume_parser.py,
                              python-docx)                                   experience.py,
                                                                             skill_extractor.py)
```

1. **Validation** (`utils/file_validator.py`):
   - Only `.pdf`/`.docx`, at most `MAX_FILE_SIZE_MB`, and not empty.
   - The content must really be that type, so a renamed `.exe` is rejected.
   - DOCX archives that would expand beyond 50 MB (zip bombs) are rejected.
   - Folder paths are stripped from filenames.
   - Uploaded files are only ever read as data, never executed.
2. **Text extraction:**
   - PDFs are read page by page with PyMuPDF in reading order.
   - DOCX extraction reads the page header, paragraphs and tables in document order, plus text boxes. Word list items get a `- ` marker.
   - Files are parsed straight from memory, so nothing is written to disk.
   - A blank PDF is reported as **empty**. A PDF made only of images is reported as **scanned** (needs OCR). Damaged and password-protected PDFs get their own clear messages.
3. **Cleaning** (`utils/text_cleaner.py`):
   - Unicode normalisation; bullets become `- `; dashes become `-`; invisible characters are removed.
   - Text is deliberately **not** lowercased and punctuation is kept, because `C++`, `C#`, `.NET` and `Node.js` depend on it.
4. **Sections:** a line that exactly matches a known heading ("Work Experience", "TECHNICAL SKILLS", "Licenses & Certifications", …) starts a new section.
5. **Fields:**

| Field | Method |
|---|---|
| Email | Regular expression |
| Phone | Regex for 10–15 digit numbers; date ranges and years are excluded |
| Name | Top lines with 2–4 capitalised words and no digits, job-title or skill words; **spaCy NER** (PERSON) as a fallback |
| Skills | Dictionary match (`nlp/data/skills.json`, 120+ skills with synonyms); URLs and emails are removed first |
| Education | Lines in the Education section grouped by degree keyword (B.Tech, M.Sc, Bachelor, …); degree level detected |
| Certifications | Certifications section, or lines containing "Certified/Certificate" |
| Projects | Title lines plus their bullet descriptions, with the skills used in each project |
| Experience | Date ranges inside Experience/Internships sections only (see below) |

**Experience rules:**

- **Accepted date formats:** `Jan 2020`, `January, 2020`, `03/2020`, `2020-03` and `2020`. `Present`, `Current` and `Till date` mean today.
- **Overlap:** overlapping jobs are **merged**, so two parallel jobs aren't double counted.
- **Internships** are totalled separately and aren't part of total experience.
- **Fallbacks when there are no dated jobs:**
  - the resume states it ("5+ years of experience") → that statement is used;
  - otherwise, the resume describes a fresher or lists only internships → 0;
  - otherwise → **unknown** (NULL), never silently 0.
- **Education years** (for example "2016 - 2020") are never counted as work.

### Skill extraction without false matches

Each alias is matched with custom boundaries:

- **`C`** never matches inside `C++`, `C#` or `Objective-C`, or an initial in "John C. Smith".
- **`Java`** never matches inside `JavaScript`.
- **`SQL`** never matches inside `PostgreSQL`.
- **`JS`** never matches inside `Node.js`.
- **Overlaps are resolved longest first**, so "React Native" isn't also counted as React.
- **Synonyms map to one name:** `ML` → Machine Learning, `Postgres` → PostgreSQL, `RESTful API` → REST APIs.
- **Ambiguous words must match exact case** (`React`, `REST`, `Excel`, `Algorithms`), so "react quickly" or "control algorithms" don't count.

You can add skills by editing `skills.json`; no code changes are needed.

**Known limitations:**

- Multi-column PDFs can interleave lines from different columns.
- Names that don't look like 2–4 capitalised words rely on spaCy.
- Job titles and company names are best-effort guesses.
- Scanned PDFs need Tesseract OCR installed.

## Job Description analysis

`nlp/jd_analyzer.py` turns a pasted or uploaded (PDF/DOCX) JD into **suggested** requirements.
The recruiter reviews and edits them before saving.

1. **Clean and split.** The text is cleaned the same way as resumes and split into JD sections:
   Responsibilities, Requirements, Nice to have, About us/Benefits. This works with headings
   such as "What You'll Do" or "Good to Have".
2. **Units.** Each bullet, and each sentence of prose, becomes one unit. spaCy's sentence
   splitter is used for prose. Sentences are split again at `;`, so "Python required; Docker
   is a plus" gives two units with different meanings.
3. **Context of each unit:**
   - **preferred:** inside a "Nice to have" section, or containing a cue such as *preferred*,
     *is a plus*, *good to have*, *bonus* or *advantage*;
   - **company:** About us or Benefits. Skills here are only keywords, never requirements;
   - **required:** everything else.
4. **Extraction:**

| Field | Method |
|---|---|
| Skills | Dictionary match per unit. **Required wins**: a skill found in both contexts is only required, so it's never double counted. "FastAPI **or** Django" becomes one requirement that either skill satisfies; "HTML/CSS" means both |
| Job title | "Job Title:/Position:" label, then a short first line naming a role, then "looking for / hiring a … Engineer"; a title the recruiter types always wins |
| Minimum experience | Regex on sentences about experience: `3+ years`, `at least 3`, `minimum of four (4)`, `2-4 years`, `6 months`. The overall minimum is the largest required lower bound. Preferred statements don't raise it. "Freshers" means 0, and no statement means **NULL** (no requirement) |
| Education | Text from the degree keyword to the end of the sentence, plus the lowest *required* degree level (a preferred Master's doesn't raise it) |
| Responsibilities | Items in the Responsibilities section. Without one, sentences that start with a verb are used. spaCy part-of-speech tag `VB`, together with a list of common verbs, recognises sentences like "Design and build…" |
| Keywords | All skills, plus domain nouns (spaCy POS) that appear at least twice. Company names and headings are excluded |

The analysis also returns `skill_evidence`: the sentence each skill came from, so the recruiter
can see *why* it was extracted. It also returns warnings, for example when no technical skills
or no experience requirement were found.

**Editing:** the `JobCreate` and `JobUpdate` schemas clean what the recruiter submits:
- `postgres` becomes PostgreSQL and `ML` becomes Machine Learning;
- duplicates and empty entries are removed;
- a skill that's required is removed from preferred;
- experience must be between 0 and 50.

Unknown skills are kept as typed. `services/job_service.py` saves, edits (partial updates)
and deletes jobs in Supabase.

## AI matching engine

```
Final Score = 0.40 × Semantic + 0.35 × Skills + 0.25 × Experience      (weights configurable in .env)
```

Each component is between 0 and 100. The final score is rounded to 2 decimals. The raw
component scores and a full breakdown (`details`) are stored with every result.

### A. Semantic similarity (40%): `nlp/semantic_matcher.py`

- **Embeddings.** [Sentence Transformers](https://www.sbert.net/) with **all-MiniLM-L6-v2**, a
  small free model (~90 MB) that runs on a CPU. It turns a text into an *embedding*: 384 numbers
  that represent its meaning. Texts about similar things get similar vectors even when they use
  different words ("built REST services in Flask" ≈ "backend API development in Python").
- **Cosine similarity** measures the angle between two vectors:

  ```
  cosine(A, B) = (A · B) / (||A|| × ||B||)
  ```

  1 means same direction (same meaning), 0 means unrelated.
- **What is compared.** The JD side is the title, the description without About Us/Benefits,
  and the required/preferred skills. The resume side is its summary, skills, experience,
  projects and certifications. Names and contact details are **never** compared.
- **Long texts.** MiniLM reads only ~256 word-pieces, so long texts are split into 150-word
  chunks (30-word overlap) and the chunk embeddings are averaged. The whole resume counts.
- **Calibration.** On the sample data, cosines ranged from about 0.18 (unrelated) to 0.71
  (strong match), so the score is `(cosine − 0.15) / (0.75 − 0.15) × 100`, clipped to 0–100.
  Both bounds are configurable.
- **Model loading.** The model is loaded **once** at startup (~10–15 s) and reused. All
  resumes are encoded in one batch, so scoring 12 resumes took 0.3 s on a laptop CPU.

**Limitations of semantic similarity:**
- It measures *topic* similarity, not competence. A fresher whose projects mirror the JD
  wording can score high.
- It can't tell "used Docker for 5 years" from "want to learn Docker".
- It is sensitive to resume length and writing style.

That's why it is only 40% of the score, combined with explicit skill and experience checks.

### B. Skills matching (35%): `matching/scoring.py`

```
Skills Score = Σ weights of matched JD skills / Σ weights of all JD skills × 100
```

- **Weights.** Required skills weigh **2**, preferred skills **1** (configurable). A skill is
  never both required and preferred.
- **Alternatives.** "FastAPI or Django" is one requirement, satisfied by either skill.
- **Custom skills.** A skill the recruiter typed that isn't in the dictionary is searched for
  as a whole word in the resume text.
- **No guessing.** Only skills actually written in the resume count. A Django resume doesn't
  get credit for "Python" unless Python is written in it.
- **No JD skills.** If the JD has no recognised skills, the score is *not available* (see
  missing data below), not 0.

### C. Experience matching (25%)

```
Experience Score = min(Relevant Experience / Required Experience, 1) × 100
```

**Relevant experience** is the merged duration (overlaps counted once) of past jobs related to
the JD. A job is relevant when any of these is true:

- its title shares a meaningful word with the JD title ("Data Analyst" ~ "Data Scientist");
- it uses the JD's title skill, counting frameworks (a Django job is Python work, a Spring Boot
  job is Java work);
- it shares at least 2 required skills with the JD.

Internships aren't counted. Total and relevant experience are shown side by side.

| Situation | Experience score |
|---|---|
| JD states no requirement | 100 for everyone ("not required") |
| Fresher, or no relevant jobs | 0 (if the JD requires experience) |
| Only "4 years of experience" stated, no dates | the stated value counts if the resume has JD skills |
| Experience can't be determined | **not available**: flagged, never assumed to be 0 |

### Missing data and explanations

If a component isn't available (unknown experience, no JD skills, or the model failed to load),
the final score uses the remaining components. Their weights are rescaled to sum to 1, the
result is marked **incomplete**, and the explanation says so.

Explanations (`matching/explanation.py`) are assembled only from computed facts, for example:

> "The candidate shows strong alignment with the Python Developer role (overall score 82.66/100).
> 4 of 6 required skills were identified in the resume: Python, FastAPI, SQL and REST APIs.
> Required skills not identified: Machine Learning and Docker. The role requires at least
> 3 years of experience; the candidate has about 4.3 years of relevant experience, which meets
> the requirement. Overall similarity between the resume and the job description is high (86/100)."

### Example calculation

For the sample *Python Developer* JD and the sample candidate Priya Nair:

| Component | Calculation | Score |
|---|---|---|
| Semantic | cosine 0.665 → (0.665 − 0.15) / 0.60 × 100 | 85.8 |
| Skills | matched Python, FastAPI, SQL, REST APIs (4 × 2) / 6 × 2 | 66.67 |
| Experience | relevant 4.3 years / required 3 → capped at 1 | 100 |
| **Final** | 0.40 × 85.8 + 0.35 × 66.67 + 0.25 × 100 | **82.66** |

Scores are deterministic: the same inputs always give the same scores, with no randomness.

## Saving analyses and ranking candidates

**Saving** (`services/analysis_service.py`): `run_analysis(job, candidate_ids)` does the following:

1. Loads the job and all candidates, one query each.
2. Removes duplicates: the same candidate twice, or two uploads of an identical file (same SHA-256).
3. Scores everyone.
4. Stores one `analysis_history` row plus one `match_results` row per candidate in a **single
   transaction**. If anything fails, nothing is saved, so no half-finished analysis exists.

Each run is a new analysis, so earlier results for the same job stay in the history. Candidate
rows keep everything the scorer needs (experience entries with dates and skills) in the
`profile` JSONB column, so re-scoring from the database gives exactly the same result as
scoring the freshly parsed file. A test checks this.

**Ranking** (`matching/ranking.py`) happens in PostgreSQL, not in the browser:

```sql
WITH ranked AS (
  SELECT id AS match_id, RANK() OVER (ORDER BY final_score DESC) AS rank
  FROM match_results WHERE analysis_id = :analysis_id
)
SELECT match_results.*, candidates.*, ranked.rank, COUNT(*) OVER () AS filtered_count
FROM match_results
JOIN ranked     ON ranked.match_id = match_results.id
JOIN candidates ON candidates.id = match_results.candidate_id
WHERE <search / score / experience / top-N filters>
ORDER BY <chosen sort>, final_score DESC, skills_score DESC, experience_score DESC,
         semantic_score DESC, name, id
LIMIT … OFFSET …;
```

- **Equal scores share a rank** ("competition ranking"): 91.5, 84.2, 84.2, 76.8 are ranked 1, 2,
  2, 4. Within a tie, the order is always the same: skills, then experience, then semantic
  score, then name.
- **Ranks are fixed per analysis.** They're computed before filters, so the candidate ranked #7
  stays #7 when the recruiter searches or filters.
- **Top N means rank ≤ N**, so a tie at the cut-off is included, not dropped arbitrarily.
- **Options:**
  - search by name or email (case-insensitive; `%` and `_` are treated literally);
  - minimum/maximum score and relevant experience;
  - sort by score, name, total or relevant experience, or any component score;
  - pagination.
- **One round trip.** `COUNT(*) OVER ()` returns the filtered total with the rows. The full
  resume text isn't downloaded for list views.

## Frontend (recruiter dashboard)

React + Vite + Tailwind CSS, with every page connected to the real API (no dummy data).
Routes are in `src/App.jsx`. Each page is lazy-loaded, so the charts library is only
downloaded for the dashboard.

| Page | Route | What a recruiter does there |
|---|---|---|
| Dashboard | `/` | KPI tiles (resumes analysed, jobs, candidates, average score, high matches), latest shortlist chart (click a bar → candidate), score distribution, 30-day activity, recent analyses. A guided empty state on first use |
| New Analysis | `/analysis/new` | **3-step wizard**: (1) pick a saved job or paste/upload a JD → review and edit the extracted requirements → save; (2) drag-and-drop resumes with instant format/size checks; (3) real upload progress → server parsing → matching, then a summary listing any files that couldn't be read and why |
| Candidate Rankings | `/rankings` | Top-match card, rank, name/email, total and relevant experience, score bar + band, matched/missing skills. Search, score-band filter, Top 5/10, minimum experience, sortable columns and CSV export. Filters are kept in the URL, so a shortlist link can be shared |
| Candidate Details | `/candidates/:id/jobs/:jobId` | Overall score, a **points breakdown** (score × weight), skills checklist, experience comparison, the explanation, **"Points to verify in the interview"**, and the full extracted profile. Print / save as PDF |
| Job Descriptions | `/jobs`, `/jobs/:id/edit` | View, edit, delete (with confirmation), re-run an analysis |
| Analysis History | `/history` | Every past analysis, filterable by job |
| Settings | `/settings` | Live API/database/model status and how scores are calculated |

**Design:**
- **Colours:** navy, white, light blue and a subtle purple accent, defined as tokens in `src/index.css`.
- **Score colours** always come with a text label (Strong / Good / Partial / Limited), never colour alone.
- **Charts** use one hue, no animation, a hover tooltip, and a hidden data table for screen readers.
- **Feedback:** loading spinners, toast notifications, and error states with "Try again".
- **Layout:** responsive, with a collapsible sidebar on small screens and horizontally scrollable tables.
- **Accessibility:** forms and buttons have labels and keyboard focus styles.
- **Responsible hiring:** every page that shows scores reminds the user that they support, not replace, human review.

## HR accounts and login

**Who can do what:**
- Every page and API endpoint requires a login. The exceptions are `/api/health` and the login endpoints.
- **Each HR sees only their own data:** jobs, uploaded candidates, analyses, rankings, dashboard figures and CSV exports.
- **Admins manage accounts,** but still only see their own candidates.

**Getting started:**
1. **First start.** While no account exists, the login page shows **Create the admin account**.
   That first account becomes the admin, and any data created before accounts existed is
   assigned to it.
2. **Adding HRs.** There's no public sign-up. The admin adds each HR in **Settings → Team accounts**,
   with a name, work email, temporary password and role (HR recruiter or Admin).
3. **Managing accounts.** Admins can reset a password, change a role, or **disable** an account,
   which signs that person out immediately and keeps their data. Admins can't disable or demote
   themselves.
4. **Own password.** Every HR can change their own password in **Settings → My account**.

**What is stored** (table `users`):
- name, email (lower-case, unique) and role;
- an active flag and the last sign-in time;
- a `token_version`, explained below;
- a **password hash**. The password itself is never stored or logged.

**How it works:**

| Piece | Implementation |
|---|---|
| Password hashing | `hashlib.scrypt` (Python standard library) with a random 16-byte salt per user (n = 2¹⁴, r = 8). Checked with a constant-time comparison |
| Login errors | The same message, "Invalid email or password.", whether the email exists or not, with equal timing (a dummy hash check), so attackers can't discover accounts |
| Sessions | A JWT signed with HS256 using `JWT_SECRET_KEY`, valid for `ACCESS_TOKEN_EXPIRE_MINUTES` (8 hours). The browser sends `Authorization: Bearer <token>` |
| Instant logout | Every token carries the user's `token_version`. Changing or resetting a password, or disabling the account, increments it, so all older tokens stop working immediately |
| Data isolation | `owner_id` on `jobs` and `candidates`; analyses and results belong to an HR through their job. Every service query filters by the logged-in HR. Another HR's record returns **404**, so even its existence isn't revealed |
| Password rules | At least 8 characters, with at least one letter and one number |

**Recovery from the server**, e.g. if the only admin forgets their password:
```powershell
cd backend
python -m app.manage list-users
python -m app.manage reset-password --email admin@company.com --password "NewPass123"
python -m app.manage create-user --email hr@company.com --name "Asha Rao" --password "Temp1234" [--admin]
```

**Known limitations:**
- No email-based password reset; admins reset passwords.
- No login rate limiting. scrypt makes each guess slow, but rate limiting should be added before public use.
- No login history; only the last sign-in time is stored.
- The token is kept in `localStorage`. React escapes all text so scripts can't be injected, but an
  httpOnly cookie would be stronger if the frontend and API are hosted under the same domain.

## Deployment on Vercel (frontend + backend) with Supabase

Both parts run on Vercel's free Hobby plan as **two Vercel projects** created from the same
GitHub repository. The database stays on Supabase.

**What makes the backend fit a serverless function:**
- **The AI model runs on ONNX Runtime instead of PyTorch.** The embeddings are identical (a test
  compares them with sentence-transformers) and the install is about 1 GB smaller.
- **Linux uses PyMuPDF 1.28.2.** It has the same API and gives identical extracted text, without
  PyMuPDF 2.x's unused layout add-on. The Linux install is about 495 MB, within Vercel's 500 MB
  Python limit, and Vercel's Large Functions (up to 5 GB, automatic for new projects) give extra headroom.
- **Defaults switch automatically when Vercel sets `VERCEL=1`:**
  - no table creation at startup;
  - models load on first use, downloaded to `/tmp`;
  - a small database connection pool;
  - a 4 MB maximum file size.
- **Large batches are uploaded in groups of at most 3.5 MB**, because Vercel limits a request to 4.5 MB.
- **Region `syd1`**, next to the Supabase database.

**1. Backend project** (deploy this first):
1. In Vercel, choose **Add New → Project**, import the GitHub repository, and set **Root Directory** = `backend`.
2. Add these environment variables:
   - `DATABASE_URL`: the same Supabase Session-pooler URL as in your local `backend/.env`.
   - `JWT_SECRET_KEY`: a **new** random value. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
   - `CORS_ORIGINS`: the frontend URL from step 2. Use `https://example.com` for now and update it later.
3. Deploy, then open `https://<backend>.vercel.app/api/health`. It should report the database as connected.

Don't copy `LOAD_MODEL_ON_STARTUP` or `MAX_FILE_SIZE_MB` from your local `.env` into Vercel; the Vercel defaults are better.

**2. Frontend project:**
1. Import the same repository again as a new project, with **Root Directory** = `frontend` (Vercel detects Vite).
2. Set `VITE_API_BASE_URL` to `https://<backend>.vercel.app`. Optionally set `VITE_DEMO_EMAIL` and `VITE_DEMO_PASSWORD`.
3. Deploy. `frontend/vercel.json` sends every page route to `index.html`, so links such as `/rankings` work after a refresh.

**3. Connect the two:** set the backend's `CORS_ORIGINS` to the frontend URL (e.g. `https://talentmatch-ai.vercel.app`) and redeploy the backend.

**Behaviour to expect:**
- After a quiet period, the first request starts a new instance, which takes a few seconds.
- The first analysis after a cold start also downloads the model (~90 MB) into `/tmp` and loads spaCy.
- Supabase's free plan pauses a project after about a week of inactivity; resume it from the Supabase dashboard.

## API reference

Interactive documentation: **http://localhost:8000/docs** (Swagger UI). All errors return
`{"detail": "message"}`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | API, database and model status (public) |
| GET | `/api/auth/setup-status` | Whether the one-time admin setup is still needed (public) |
| POST | `/api/auth/setup` | Create the first admin account (only while no accounts exist) |
| POST | `/api/auth/login` | Email + password → access token |
| GET | `/api/auth/me` | The logged-in HR |
| POST | `/api/auth/change-password` | Change your own password (signs out your other sessions) |
| GET / POST | `/api/users/` | Admin: list / create HR accounts |
| PATCH | `/api/users/{user_id}` | Admin: rename, change role, disable / re-enable |
| POST | `/api/users/{user_id}/reset-password` | Admin: set a new password |
| POST | `/api/jobs/analyze` | Extract requirements from JD text (nothing saved) |
| POST | `/api/jobs/analyze-file` | Same, from an uploaded PDF/DOCX JD |
| POST | `/api/jobs/` | Save a (recruiter-edited) job → 201 |
| GET | `/api/jobs/` | List jobs with analysis counts |
| GET / PUT / DELETE | `/api/jobs/{job_id}` | Read / partially update / delete (analyses are deleted too) |
| POST | `/api/resumes/upload` | Upload up to `MAX_FILES_PER_BATCH` PDF/DOCX files; returns one result per file and `candidate_ids` |
| POST | `/api/analyze/{job_id}` | Body `{"candidate_ids": [...]}`: score, save and return the ranking |
| GET | `/api/results/{job_id}` | Ranked results (latest analysis, or `?analysis_id=`) |
| GET | `/api/results/{job_id}/export` | The same as a CSV download |
| GET | `/api/analyses/` | Analysis history (`?job_id=` optional) |
| GET | `/api/candidates/` | Candidates with best and latest score (`?search=`) |
| GET | `/api/candidates/{candidate_id}` | All extracted resume details and match history |
| DELETE | `/api/candidates/{candidate_id}` | Permanently delete a candidate's data, e.g. on a data-removal request; analysis totals are recalculated |
| GET | `/api/settings/` | Scoring weights and upload limits (read-only) |
| GET | `/api/candidates/{candidate_id}/analysis/{job_id}` | Score breakdown, skills, experience comparison, explanation |
| GET | `/api/dashboard/stats` | Totals, score distribution, 30-day activity, latest ranking |

Every endpoint except the public ones needs the header `Authorization: Bearer <access_token>`.
In Swagger, click **Authorize** and paste the token returned by `/api/auth/login`.

The results and export endpoints accept these filters: `search`, `min_score`, `max_score`,
`min_experience`, `max_experience` (relevant years), `top`, `sort_by` (`rank`, `final_score`,
`name`, `relevant_experience`, `total_experience`, `skills_score`, `semantic_score`,
`experience_score`), `order` (`asc`/`desc`), `limit` and `offset`.

**Typical workflow:**
1. `POST /api/jobs/analyze`
2. The recruiter edits the result.
3. `POST /api/jobs/`
4. `POST /api/resumes/upload`
5. `POST /api/analyze/{job_id}` with the returned `candidate_ids`
6. `GET /api/results/{job_id}`

**Status codes:**

| Code | Meaning |
|---|---|
| 400 | Invalid request, such as no resumes or too many files |
| 404 | Not found |
| 409 | The data conflicts with existing records or a database rule |
| 422 | Validation failed, or an unusable file or JD |
| 503 | Database unreachable |
| 500 | Unexpected error, with a generic message; details go only to the server log |

**Security:**
- **Uploads:**
  - files are validated by content, not just extension;
  - the size limit is enforced while reading;
  - original files are never stored or executed.
- **Untrusted text:** the CSV export neutralises spreadsheet formulas (`=`, `+`, `-`, `@`).
- **Privacy:** logs contain counts only, never names or emails.
- **Credentials:** database details stay in `backend/.env`.

## Testing

```powershell
cd backend
.venv\Scripts\python -m pytest -q
```

Database tests run against the real Supabase database inside a transaction that's rolled back
at the end, so they leave no rows behind. They're skipped if `DATABASE_URL` isn't set. They also
pass when the database already contains real data.

### End-to-end tests (real browser)

```powershell
cd frontend
npm run test:e2e        # starts the backend and frontend automatically if they aren't running
```

[Playwright](https://playwright.dev) drives the installed **Microsoft Edge** through the real
React app, FastAPI backend and Supabase database. No browser download is needed.
Results go to `frontend/e2e-report/` (open `index.html`).

| Test | What it proves |
|---|---|
| Complete recruiter workflow (11 steps) | 1. paste a JD → requirements extracted<br>2. correct them (`k8s` → Kubernetes) → save<br>3. upload 12 resumes plus an invalid `.txt`, which is flagged and removed<br>4. analyse<br>5. ranking: 12 rows, the right candidate at #1<br>6. Top 5 filter and search → candidate details for a resume without contact information<br>7. phone layout<br>8. CSV export (13 lines, correct header)<br>9. the dashboard and history show the analysis<br>10. edit the job<br>11. delete a candidate (totals recalculated) and delete the job |
| Backend unreachable | A clear "Cannot reach the server" message, and *Try again* recovers |
| Invalid JD file / too-short JD / unsupported file | The server's validation message is shown, and invalid input is blocked before sending |
| Unknown URL | A friendly 404 page with a link home |
| Phone screen (390 × 844), 6 pages | No horizontal scrolling, and the menu opens |

Before the tests, a temporary **E2E admin** account is created with `python -m app.manage`. Afterwards
it's deleted, together with every account the tests created and, through `ON DELETE CASCADE`, all
of their jobs, resumes and analyses. This happens even when a step fails, so existing data is
never touched. `e2e/auth.spec.js` covers:
- the redirect to sign-in and a wrong password;
- an admin creating an HR account in the UI;
- the new HR seeing an empty, isolated workspace;
- disabling that HR, which signs them out on their next action with an explanation.

**Bugs these tests found and fixed:**
- **Pages wider than a phone screen.** A hidden screen-reader label inside a table header
  (`position: absolute`) escaped the table's scroll box and widened the page to 488 px.
  Table wrappers are now positioned, and cards can shrink inside grid layouts.
- **One backend test assumed an empty database.** It now compares against the counts taken
  before the action.

## Troubleshooting: "An Application Control policy has blocked this file" (Windows 11)

Windows 11 **Smart App Control** blocks compiled Python/Node extensions whose exact file it
does not yet trust, and it is often newer releases that get blocked. During setup this
affected the newest `psycopg-binary`, `spacy` and `srsly` wheels, the `oxlint` binary, and the
`.exe` launchers pip creates in `.venv\Scripts\` (e.g. `uvicorn.exe`). Run the launchers as
`python -m <tool>` instead. On the development machine those blocked launchers were renamed to
`*.exe.blocked` and replaced by `*.cmd` shims that call `python -m <tool>`, so plain `uvicorn ...`
also works in an activated venv. Reinstalling a package recreates its `.exe` (which takes
priority over `.cmd`), so rename it again if the error comes back.
`requirements.txt` pins builds that load correctly, and the frontend uses ESLint (pure
JavaScript) instead of oxlint. If you upgrade a package and see this error, go back to the
pinned version. Turning Smart App Control off also fixes it, but Windows cannot turn it
back on without a reinstall.

## Development phases

1. ✅ Project initialization
2. ✅ Supabase integration
3. ✅ Resume parsing
4. ✅ Job description analysis
5. ✅ AI/NLP matching engine
6. ✅ Candidate ranking
7. ✅ Backend API
8. ✅ Frontend pages
9. ✅ Integration (end-to-end browser tests)
10. ⬜ Final testing, documentation and deployment
