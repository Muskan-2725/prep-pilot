# PrepPilot

A runnable, dependency-light MVP of an adaptive GATE CSE mentor. It implements the full local loop: account → onboarding → evidence-based plan → tutor → practice → evaluation → learner-state update → next recommendation.

## Run

```bash
python -m app.server
# open http://127.0.0.1:8000
```

The service uses SQLite locally (`data/preppilot.db`) and Python standard-library WSGI so it can run in a constrained environment. Set `PREPPILOT_SECRET` before any non-development use. Run tests with `python -m pytest`.

## Current limits

This is an MVP, not a production deployment. The tutor, question bank, and retrieval corpus are deterministic and deliberately small. Research is fail-closed: it returns an official-source link and warns that live retrieval is unavailable rather than inventing date-sensitive GATE policy. See `docs/IMPLEMENTATION_REPORT.md` for the acceptance status.
