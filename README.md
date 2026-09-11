# PrepPilot V1

A runnable local GATE CSE adaptive-study product. It persists onboarding confidence, attempts, mistake types, mastery/trend, plan versions, and mentor messages in SQLite. Every dashboard, plan, practice selection, mentor response, and profile read uses the same learner state.

## Run

```bash
python -m app.server
# open http://127.0.0.1:8000
python -m pytest -q
```

No external service or paid API is required. The V1 mentor is a **deterministic learner-aware fallback**, not an LLM. Live research is intentionally unavailable and returns an honest official-source fallback. The knowledge foundation has structured question/source metadata in SQLite but does not yet perform embeddings or vector retrieval.

## Core loop

Signup → onboarding (goal/date/hours/confidence) → dashboard → targeted practice → evaluation (correctness, confidence, mistake type) → persistent topic-state update → updated dashboard/plan/mentor/profile.
