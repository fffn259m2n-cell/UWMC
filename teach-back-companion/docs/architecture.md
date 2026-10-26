# Architecture

```
synthetic care plans (JSON, clinician-style)      education library (JSON, draft, with sources)
        │  original + plain + critical facts                │  3 reading levels, glossary
        ▼                                                    ▼
   plans.py  (schema validation, synthetic-only, injection scan)   knowledge.py
        │                                                    │
        ├── teachback.py  ← text.py (numbers, units, negation, phrases)
        ├── fidelity.py   ← text.py + readability.py   ◄── benchmark.py (seeded errors)
        ├── chat.py       ← safety.py (runs first) + knowledge.py
        ├── reminders.py  (SQLite: reminders, task status; no free text)
        └── llm.py        (optional; output must pass fidelity.py)
                 │
             app.py  FastAPI JSON API + security headers
                 │
        static/  index.html · app.js · styles.css   (no build step, no external assets)
```

**Critical fact** (per instruction): `statement`, `severity`, synonym `concepts`,
`quantities` (value + unit), optional `action` with `polarity: "dont"` and optional `objects`,
`emergency` flag, `coverage` rule, and `misconceptions` (pattern + supportive message).

**API**: `GET /api/plans`, `GET /api/plans/{id}`, `GET /api/education/{topic}`,
`POST /api/plans/{id}/chat`, `POST /api/plans/{id}/teachback`, `POST /api/plans/{id}/evaluate`,
`GET /api/benchmark`, reminders (`GET/POST /api/plans/{id}/reminders`, `GET …/due`,
`POST /api/reminders/{rid}/ack`, `DELETE /api/reminders/{rid}`), `POST /api/plans/{id}/tasks/{item}`,
`POST /api/demo/reset`.

**Adding a patient scenario**: copy a file in `src/teachback/data/plans/`, keep
`"synthetic": true`, write the original instructions, plain versions and facts, then run
`teachback check-content` and `pytest` (every plain version must pass the evaluator).
