# GridWise LLM — Microgrid Energy Optimizer

A two-stage microgrid energy optimizer for the **BUP CSE Fest 2026 Preliminary
Challenge**. It accepts a 24-hour campus demand/solar/tariff schedule plus 1–3
natural-language operator notes, parses those notes with a Gemini language
model, and solves a deterministic linear program to produce a 24-hour
charge/discharge/grid plan that minimises total cost while honouring every
directive.

---

## 🌐 Live Deployment & Endpoints

- **Live Service Base URL:** [https://bup-gridwise-llm.vercel.app](https://bup-gridwise-llm.vercel.app)
- **Health Check (`GET /health`):** [https://bup-gridwise-llm.vercel.app/health](https://bup-gridwise-llm.vercel.app/health)
- **Interactive Swagger Docs (`GET /docs`):** [https://bup-gridwise-llm.vercel.app/docs](https://bup-gridwise-llm.vercel.app/docs)
- **Optimization Route (`POST /optimize-energy`):** `https://bup-gridwise-llm.vercel.app/optimize-energy`

---

This repository contains **two runnable pieces**:

| Folder | Purpose | Stack |
| --- | --- | --- |
| `main.py`, `schema.py`, `services/` | Original LLM-driven FastAPI app (PuLP solver) | FastAPI, PuLP, Google GenAI |
| `gridwise-api/` | Hardened production service (deterministic guardrails, SciPy/HiGHS) | FastAPI, SciPy, HTTPX |

Both Python services expose the same `POST /optimize-energy` contract; the
`gridwise-api/` service is the recommended submission target because it adds
structured-output guarantees, deterministic validation, and a public-sample
replay script.

---

## Repository layout

```
bup-gridwise-llm/
├── README.md                         ← you are here
├── main.py                           ← LLM-driven FastAPI entrypoint (PuLP)
├── schema.py                         ← Pydantic request schema
├── services/
│   ├── llm_interpreter.py            ← Gemini directive interpretation
│   └── optimizer.py                  ← PuLP linear program
├── requirement.txt                   ← Python deps for the top-level app
├── BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json
├── BUP_CSE_FEST_2026_Participant_Guide_&_Evaluation_Rubric_GridWise_LLM.pdf
├── BUP_CSE_FEST_2026_Preliminary_Problem_Statement_GridWise_LLM.pdf
└── gridwise-api/                     ← Hardened submission service
    ├── app/
    │   ├── main.py                   ← FastAPI routes + exception handlers
    │   ├── models.py                 ← Pydantic request/response models
    │   ├── services.py               ← Gemini + SciPy/HiGHS optimizer
    │   └── guardrails.py             ← Deterministic directive/plan checks
    ├── tests/                        ← Pytest suite (API, LLM, public samples)
    ├── scripts/
    │   └── validate_public_samples.py  ← End-to-end replay vs. organizer optima
    ├── Dockerfile
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── pytest.ini
    └── .env.example
```

---

## Pipeline

```text
OptimizeRequest
  └─► LLM directive interpretation (Gemini structured outputs)
        └─► Deterministic directive guardrails
              └─► Linear optimization (SciPy HiGHS or PuLP)
                    └─► Plan replay + total recalculation
                          └─► OptimizeResponse
```

- The **LLM** only classifies operator notes and extracts whole-hour windows
  and numeric values — it never touches the math.
- **Guardrails** check note ordering, adjustment shapes, applies/no-op
  semantics, sorted unique hours, and numeric ranges before any directive
  reaches the optimizer.
- The **optimizer** minimises `sum(grid_kwh × tariff)` subject to energy
  balance, effective solar, battery bounds/rates, every directive type, and
  end-of-day battery neutrality.
- A final **replay** re-derives every hour from the plan and recalculates all
  totals, so the response can never disagree with itself.

---

## Quickstart — recommended service (`gridwise-api/`)

Requires Python 3.13.

```powershell
cd gridwise-api
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env            # then paste your GEMINI_API_KEY
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

macOS / Linux:

```bash
cd gridwise-api
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then add your GEMINI_API_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env
```

Smoke-test:

```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok"}
```

Interactive docs: <http://127.0.0.1:8000/docs>

### Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GEMINI_API_KEY` | yes | — | Gemini API credential (never commit) |
| `GEMINI_MODEL` | no | `gemini-3.5-flash-lite` | Structured-output model |
| `GEMINI_BASE_URL` | no | `https://generativelanguage.googleapis.com/v1beta` | Gemini base URL |
| `GEMINI_TIMEOUT_SECONDS` | no | `8.0` | LLM request timeout (0.5–25) |

The service deliberately does not auto-load `.env` at runtime — uvicorn's
`--env-file` flag is the supported way to inject secrets. `.env` is git-ignored
and excluded from Docker builds.

### Call the optimisation endpoint

```bash
curl -X POST http://127.0.0.1:8000/optimize-energy \
  -H "Content-Type: application/json" \
  --data-binary @request.json
```

The response contains `scenario_id`, one `directive_interpretation` entry per
note, 24 `hourly_plan` entries, recalculated grid/cost/peak totals, and a
`plan_summary`.

---

## Quickstart — top-level service (PuLP)

The top-level `main.py` is the original LLM-driven entrypoint and remains
available for reference. It uses PuLP and the Google GenAI SDK.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirement.txt
$env:GEMINI_API_KEY = "your-key"
uvicorn main:app --host 0.0.0.0 --port 8000
```

Note that the two services bind the same route name (`/optimize-energy`) and
cannot run simultaneously on the same port.

---

## Tests and validation

Self-contained API tests (no external calls):

```powershell
cd gridwise-api
pip install -r requirements-dev.txt
python -m pytest -q
```

Replay all 10 organizer public optima through the deterministic optimizer
(no API call required):

```powershell
$env:PUBLIC_SAMPLE_CASES_PATH = "..\BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
python -m pytest tests\test_public_samples.py -q
```

Replay the **full LLM → optimizer pipeline** against the organizer ground
truth (start the API with a valid key first):

```powershell
python scripts\validate_public_samples.py `
  --base-url http://127.0.0.1:8000
```

`--cases` is optional — the script auto-locates
`BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json` from well-known positions
relative to the repo. Each case is checked for directive agreement with
ground truth, plan validity under replay, totals consistency, and a final-cost
match within ±0.01 BDT of the public optimum.

---

## Docker

```bash
cd gridwise-api
docker build -t gridwise-api:2026-preli .
docker run --rm -p 8000:8000 \
  -e GEMINI_API_KEY="your-key" \
  -e GEMINI_MODEL="gemini-2.5-flash" \
  gridwise-api:2026-preli
```

The container binds `0.0.0.0:8000`, exposes port 8000, includes a health check,
and does not copy secrets. Before submission, push this image to Docker Hub,
GHCR, or another public registry with an immutable tag or digest, then replace
the local build line above with the published pull/run command for graders.

---

## HTTP behaviour and safety

| Code | Meaning |
| --- | --- |
| `200` | Successful health or optimisation response |
| `400` | Malformed JSON or structurally invalid request |
| `422` | Well-formed but semantically invalid scenario |
| `500` | Controlled LLM, guardrail, infeasibility, or final-replay failure |

Error responses never contain provider payloads, credentials, raw prompts, or
stack traces. Repeated identical `(operator_notes, capacity)` combinations
are cached in memory for one hour (up to 128 entries) to reduce latency and
provider usage; no persistent user data is stored.

---

## Submission checklist

- [ ] `python -m pytest -q` is green inside `gridwise-api/`
- [ ] `python scripts\validate_public_samples.py` reports **All 10 public cases passed**
- [ ] Docker image built and pushed to a public registry; pull/run command recorded
- [ ] Public base URL reachable; `/health` returns `{"status":"ok"}`
- [ ] Three-minute demonstration video recorded and linked
- [ ] Repository remains **private** until after the official submission deadline

---

## Credits

- FastAPI / Uvicorn — HTTP service
- Pydantic — strict request/response validation
- HTTPX — bounded Gemini `generateContent` calls
- SciPy HiGHS / PuLP — continuous linear optimisation
- Google Gemini — structured-output language model
- Pytest — verification suite

Visit the [YouTube Link](https://youtu.be/kIi0-Aqsm70) to view the demo.

