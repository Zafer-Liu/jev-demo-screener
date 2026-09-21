# jev-demo-screener — JD-Anchored Resume Screener

One Jev call scores a resume against the job description: JD fit, hands-on depth, keyword-puff detection, and a confidence-gated hiring recommendation — eight typed evaluations in a single pass.

> Adapted for TypeSafe Jev — the System One decision model ([docs.typesafe.ai](https://docs.typesafe.ai)) · [中文说明](README.zh-CN.md)

## What it does

Recruiters drown in resumes that mention every buzzword in the JD. This MVP takes two inputs — a job description and a resume — and asks Jev eight typed questions in one call, anchored to that specific JD: experience and depth scores, a JD-match score, probability checks for skill evidence (the keyword-puff detector), mentorship, and open source, plus career progression and a final recommendation with confidence. When signals are mixed or inflated, the verdict is `human_review`, not a guess.

Pipeline:

- Load a JD preset (JD-1 AI product engineer / JD-2 senior frontend engineer) and a resume sample (A hands-on builder / B keyword stuffer), or paste your own
- The backend assembles a single state and makes one Jev call:

  ```
  JOB DESCRIPTION:
  <jd>

  =====

  RESUME:
  <resume>
  ```

- Confidence-gated routing: the verdict is interview / reject / human_review; screening only ranks and flags — the final decision stays with a human

## Why Jev

- **Typed probabilistic decisions.** Eight answers in one call — three `Score`s, three `Noul` probabilities, two `Choice`s — each with its own scale. No JSON schema wrangling, no output repair.
- **~150 ms model latency.** ~400 ms steady-state per screening round trip after warmup (shared TLS connection).
- **Calibrated confidence as a routing gate.** The recommendation carries a confidence; mixed or inflated signals yield `human_review` (verified: a keyword-stuffed resume at 95% confidence). That keeps the tool on the ranking side and the final call with people — where hiring compliance wants it.

## Verified results

Measured 2026-09-20 with the JD-anchored web console; one call = 8 questions. "—" = not part of the recorded verification.

| Combination | jd_match (0–4) | depth (0–5) | Skill evidence | Progression | Recommendation |
|---|---|---|---|---|---|
| JD-1 AI product engineer + Resume A (hands-on builder) | — | 4.0 | 95% | steady_growth | **interview** |
| JD-1 AI product engineer + Resume B (keyword stuffer) | — | 0.2 | 44% | job_hopping | **human_review** (95% confidence) |
| JD-2 senior frontend engineer + Resume A (backend builder) | **0.03** | 3.98 | — | — | **reject** (100% confidence) |

The third row is the showcase. Against JD-2 (senior frontend), the same Resume A that earned `interview` for JD-1 collapses to jd_match 0.03/4 and a 100%-confidence reject — while its quality signals stay high: depth 3.98/5, mentorship 95%, open source 90%. "Strong candidate" and "wrong role" get cleanly separated: swap the JD and the verdict flips; the quality signals don't move.

## Quick start

Requires Python 3.10+.

```bash
pip install -r requirements.txt   # or: pip install flask typesafe-sdk requests

# Configure your API key (get one at console.typesafe.ai)
cp .env.example .env     # then edit .env
# .env needs exactly one line: TYPESAFE_API_KEY=<your key>

# Web console (JD-anchored, 8 questions per call)
python server.py
# → http://127.0.0.1:8768

# Legacy CLI — the original no-JD version (7 questions), kept for comparison
python screener.py
```

## HTTP API

**`POST /api/screen`** — body `{"jd": "<job description>", "text": "<resume>"}`. One Jev call, all eight answers, plus run metadata:

| Field | Meaning |
|---|---|
| `years`, `depth`, `jd_match` | Score answers |
| `skill_evidence`, `mentorship`, `opensource` | Noul probabilities (0–1) |
| `progression`, `progression_conf`, `recommend`, `recommend_conf` | Choice answers + confidences |
| `wall_ms` | Wall-clock time of the whole screening call |
| `input_tokens` | Input tokens reported by the API (`r.usage.input_tokens`; 0 if unreported) |
| `cost_usd` | Estimated input cost, `input_tokens / 1e6 * $0.042`, 6 decimal places |
| `gate` | `"low-confidence: human review advised"` when `recommend_conf < 0.6` (the confidence-gating rationale), else `"auto"` |

Errors come back as JSON: `400` for an empty JD/resume or a combined input over **50,000 characters** (a cap that protects the model's 64k-token context), `502` wrapped as `{"error": "jev call failed: ..."}` if the Jev call itself fails.

**`GET /api/history`** — the most recent 10 screenings, newest first, in-memory only (cleared on restart). Each entry: `ts` (local timestamp), `jd` (JD title — first line — or first 30 chars), `recommend`, `jd_match`, `wall_ms`. The web console renders this as the "最近初筛" strip under the result panel.

## The Jev questions

All eight questions go out in a single `system_one` call against the assembled JD + resume state (verbatim from `QUESTIONS` in `server.py`):

| # | Key | Type | Instructions (essence) | Scale / thresholds |
|---|---|---|---|---|
| 1 | `years` | Score | Years of professional experience as of today | 0–5, anchored: 0-1 / 2-3 / 4-5 / 6-7 / 8-9 / 10+ years |
| 2 | `depth` | Score | Hands-on engineering depth from what the candidate personally built — "ignore skills keyword lists, titles, and company names" | 0 no evidence of real building · 3 owned significant systems end to end · 5 career-defining, industry-level work |
| 3 | `jd_match` | Score | How well the candidate satisfies the explicit requirements in the JOB DESCRIPTION | 0 meets almost none · 3 meets all core requirements · 4 exceeds requirements across the board |
| 4 | `skill_evidence` | Noul | Skills this job requires are backed by concrete project evidence (built, shipped, owned), not just keyword lists | probability 0–1 — the keyword-puff detector |
| 5 | `mentorship` | Noul | Real mentoring or team leadership experience | probability 0–1 |
| 6 | `opensource` | Noul | Verifiable open-source contributions | probability 0–1 |
| 7 | `progression` | Choice | What type of career progression is shown | `steady_growth` increasing scope · `job_hopping` short stints without growth · `lateral_moves` similar roles repeated |
| 8 | `recommend` | Choice | Hiring recommendation for the role described in the JOB DESCRIPTION | `interview` strong fit, advance · `reject` clearly not a fit · `human_review` mixed or inflated signals, a human looks first |

The legacy CLI (`screener.py`) is the no-JD baseline: 7 questions that swap `jd_match` and `skill_evidence` for a generic `llm_experience` Noul ("actually developed LLM products, not just listed keywords") and a `recommend` pinned to one fixed role. Keeping both versions makes the value of JD anchoring directly measurable — same resumes, sharper verdicts.

## Configuration / customization

- **Any JD, any resume.** Paste both sides in the console, or edit the preset constants `JD1`, `JD2`, `RESUME_A`, `RESUME_B` in `web/index.html` to your own samples.
- **Your own rubric.** Edit `QUESTIONS` in `server.py`: add role-specific Noul questions (e.g. "has led design-system work"), or re-anchor the `jd_match` criteria to your leveling.
- **The experiment worth running.** Screen the same resume against JD-1 and JD-2 and watch fit flip while quality doesn't move.
- **Server**: one shared `TypeSafeClient` serialized by a lock; host/port `127.0.0.1:8768`.

## Project layout

```
jev-demo-screener/
├── screener.py       # legacy CLI: no-JD baseline, 7 questions (kept for comparison)
├── server.py         # Flask web MVP: POST /api/screen, GET /api/history, JD-anchored, 8 questions per call
├── web/
│   └── index.html    # screening console with JD/resume presets (single file, no build step)
├── requirements.txt  # flask>=3.0, typesafe-sdk, requests
├── LICENSE           # MIT
└── .env              # TYPESAFE_API_KEY=... (never commit)
```

## Notes

- The first call after startup pays a ~6 s idle TLS handshake; `server.py` warms up in a daemon thread at boot. Steady state is ~400 ms per screening.
- Each screening run costs well under $0.001 at official pricing.
- `.env` holds your API key — keep it out of version control.
- Compliance: screening ranks and flags only; the hiring decision stays with humans.
