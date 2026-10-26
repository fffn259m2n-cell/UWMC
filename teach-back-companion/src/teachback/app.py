"""Local web app (FastAPI). Run: teachback serve  (then open http://127.0.0.1:8000)."""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, benchmark, chat, knowledge, teachback
from .fidelity import evaluate_item
from .plans import load_plans
from .reminders import ReminderError, Store

STATIC = Path(str(resources.files("teachback").joinpath("static")))
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=chat.MAX_MESSAGE)
    level: str = "standard"
    last_topic: str | None = Field(default=None, max_length=80)


class TeachBackIn(BaseModel):
    item_id: str = Field(max_length=80)
    text: str = Field(max_length=teachback.MAX_INPUT)


class EvaluateIn(BaseModel):
    item_id: str = Field(max_length=80)
    candidate: str = Field(min_length=1, max_length=5000)
    language: str | None = Field(default=None, pattern=r"^(en|es|non-en)$")


class DraftIn(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    plan: str = Field(max_length=80)
    item: str = Field(max_length=80)
    text: str = Field(min_length=1, max_length=4000)
    language: str | None = Field(default=None, pattern=r"^(en|es|non-en)$")


class GateIn(BaseModel):
    drafts: list[DraftIn] = Field(min_length=1, max_length=200)


class ReminderIn(BaseModel):
    item_id: str = Field(max_length=80)
    remind_at: datetime
    repeat: str = Field(default="none", pattern=r"^(none|daily)$")


class StatusIn(BaseModel):
    status: str = Field(pattern=r"^(not_started|reviewed|done)$")


def create_app(db_path: Path | None = None, today: date | None = None) -> FastAPI:
    """Build the app. TEACHBACK_THEME=<name> adds static/themes/<name>.css (e.g. portal, high-contrast)."""
    app = FastAPI(title="Teach-Back Companion (synthetic demo)", version=__version__,
                  docs_url=None, redoc_url=None, openapi_url=None)
    plans = load_plans()
    store = Store(db_path or Path(os.environ.get("TEACHBACK_DB", "data/demo.sqlite")))

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"  # microphone: optional voice teach-back
        return resp

    def plan_or_404(pid: str):
        if pid not in plans:
            raise HTTPException(404, "Unknown demo patient")
        return plans[pid]

    def item_or_404(plan, item_id: str):
        try:
            return plan.item(item_id)
        except KeyError:
            raise HTTPException(404, "Unknown care-plan item") from None

    @app.exception_handler(ReminderError)
    async def reminder_error(_, exc: ReminderError):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/plans")
    def list_plans():
        return [{"id": p.id, "name": p.patient.display_name, "age": p.patient.age, "notice": p.notice,
                 "diagnoses": [d.name for d in p.diagnoses]} for p in plans.values()]

    @app.get("/api/plans/{pid}")
    def get_plan(pid: str):
        p = plan_or_404(pid)
        discharge = p.discharge_date(today)
        statuses = store.statuses(p.id)
        items = []
        for i in p.items:
            when = i.appointment.when(discharge) if i.appointment else None
            items.append({
                "id": i.id, "kind": i.kind, "title": i.title, "original": i.original, "plain": i.plain,
                "education_topic": i.education_topic, "task": i.task.model_dump() if i.task else None,
                "when": when.isoformat() if when else None,
                "has_time": bool(i.appointment and i.appointment.time),
                "status": statuses.get(i.id, "not_started"),
                "points": [{"id": f.id, "statement": f.statement, "severity": f.severity} for f in i.facts],
            })
        return {"id": p.id, "synthetic": p.synthetic, "notice": p.notice, "patient": p.patient.model_dump(),
                "discharge_date": discharge.isoformat(), "care_team": [c.model_dump() for c in p.care_team],
                "diagnoses": [d.model_dump() for d in p.diagnoses], "items": items}

    @app.get("/api/education/{topic_id}")
    def education(topic_id: str):
        t = knowledge.topic(topic_id)
        if not t:
            raise HTTPException(404, "Unknown topic")
        return t

    @app.get("/api/glossary")
    def glossary():
        return knowledge.library()["glossary"]

    @app.post("/api/plans/{pid}/chat")
    def ask(pid: str, body: ChatIn):
        return chat.answer(plan_or_404(pid), body.message, body.level, body.last_topic, today).to_dict()

    @app.post("/api/plans/{pid}/teachback")
    def teach_back(pid: str, body: TeachBackIn):
        p = plan_or_404(pid)
        item_or_404(p, body.item_id)
        from . import safety
        s = safety.screen(body.text, context="teachback")
        res = teachback.check(p, body.item_id, body.text).to_dict()
        if s.level != "none":
            res["safety"] = s.to_dict()
        return res

    @app.post("/api/plans/{pid}/evaluate")
    def evaluate(pid: str, body: EvaluateIn):
        p = plan_or_404(pid)
        return evaluate_item(p, item_or_404(p, body.item_id), body.candidate, body.language).to_dict()

    @app.post("/api/gate")
    def gate_drafts(body: GateIn):
        from . import gate
        return gate.run([d.model_dump() for d in body.drafts])

    insights_cache: dict = {}

    @app.get("/api/insights")
    def insights_demo():
        from . import insights
        if "r" not in insights_cache:   # the bundled cohort never changes while the app runs
            insights_cache["r"] = insights.run(insights.bundled_cohort())
        return insights_cache["r"]

    @app.get("/api/benchmark")
    def run_benchmark():
        return benchmark.run()

    @app.get("/api/plans/{pid}/reminders")
    def reminders(pid: str):
        return store.list(plan_or_404(pid).id)

    @app.get("/api/plans/{pid}/reminders/due")
    def due(pid: str):
        return store.due(plan_or_404(pid).id)

    @app.post("/api/plans/{pid}/reminders", status_code=201)
    def add_reminder(pid: str, body: ReminderIn):
        p = plan_or_404(pid)
        return store.create(p, body.item_id, body.remind_at.replace(tzinfo=None), body.repeat, today=today)

    @app.post("/api/reminders/{rid}/ack")
    def ack(rid: int):
        return store.acknowledge(rid)

    @app.delete("/api/reminders/{rid}", status_code=204)
    def delete(rid: int):
        store.delete(rid)

    @app.post("/api/plans/{pid}/tasks/{item_id}")
    def status(pid: str, item_id: str, body: StatusIn):
        p = plan_or_404(pid)
        item_or_404(p, item_id)
        return store.set_status(p, item_id, body.status)

    @app.post("/api/demo/reset", status_code=204)
    def reset():
        store.clear()

    theme = os.environ.get("TEACHBACK_THEME", "").strip()
    if theme and not re.fullmatch(r"[a-z0-9-]+", theme):
        raise ValueError("TEACHBACK_THEME may contain only lowercase letters, digits and hyphens")
    if theme and not (STATIC / "themes" / f"{theme}.css").exists():
        raise ValueError(f"Unknown theme '{theme}'. Available: "
                         + ", ".join(sorted(p.stem for p in (STATIC / "themes").glob("*.css"))))
    index_html = (STATIC / "index.html").read_text(encoding="utf-8")
    if theme:
        index_html = index_html.replace(
            '<link rel="stylesheet" href="/static/styles.css">',
            f'<link rel="stylesheet" href="/static/styles.css">\n<link rel="stylesheet" href="/static/themes/{theme}.css">')

    @app.get("/")
    def index():
        return HTMLResponse(index_html)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
