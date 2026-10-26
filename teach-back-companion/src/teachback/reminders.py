"""Local demonstration checklist and reminders (SQLite).

Reminders can only be attached to tasks documented in the care plan. The patient
chooses the time; the software never proposes medication times or new deadlines.
Delivery is in-app only, while the page is open. Nothing typed in teach-back or
chat is stored.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import CarePlan

SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id TEXT, item_id TEXT, label TEXT, instruction TEXT,
  remind_at TEXT, repeat TEXT, created_at TEXT, acknowledged_at TEXT);
CREATE TABLE IF NOT EXISTS task_status (
  plan_id TEXT, item_id TEXT, status TEXT, updated_at TEXT, PRIMARY KEY (plan_id, item_id));
"""
STATUSES = {"not_started", "reviewed", "done"}


class ReminderError(ValueError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def create(self, plan: CarePlan, item_id: str, remind_at: datetime, repeat: str = "none",
               now: datetime | None = None, today: date | None = None) -> dict:
        now = now or datetime.now()
        try:
            item = plan.item(item_id)
        except KeyError as exc:
            raise ReminderError("That task is not in your care plan.") from exc
        if item.task is None:
            raise ReminderError("Reminders can only be set for tasks listed in your care plan.")
        if remind_at <= now:
            raise ReminderError("Please choose a time in the future.")
        if repeat not in ("none", "daily"):
            raise ReminderError("Reminders can repeat daily or not at all.")
        if repeat == "daily" and item.task.type != "daily":
            raise ReminderError("Only tasks your care plan describes as daily can repeat.")
        if item.appointment:
            due = item.appointment.when(plan.discharge_date(today or now.date()))
            limit = due if item.appointment.time else due + timedelta(days=1)
            if remind_at > limit:
                raise ReminderError(f"That time is after the planned date ({due:%B %d}). "
                                    "Choose a time before it.")
        cur = self.db.execute(
            "INSERT INTO reminders (plan_id, item_id, label, instruction, remind_at, repeat, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (plan.id, item.id, item.task.label, item.original, remind_at.isoformat(timespec="minutes"),
             repeat, now.isoformat(timespec="seconds")))
        self.db.commit()
        return self.get(cur.lastrowid)

    def get(self, rid: int) -> dict:
        row = self.db.execute("SELECT * FROM reminders WHERE id=?", (rid,)).fetchone()
        if row is None:
            raise ReminderError("Reminder not found.")
        return dict(row)

    def list(self, plan_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM reminders WHERE plan_id=? ORDER BY remind_at", (plan_id,))]

    def due(self, plan_id: str, now: datetime | None = None) -> list[dict]:
        now = (now or datetime.now()).isoformat(timespec="minutes")
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM reminders WHERE plan_id=? AND remind_at<=? AND acknowledged_at IS NULL "
            "ORDER BY remind_at", (plan_id, now))]

    def acknowledge(self, rid: int, now: datetime | None = None) -> dict:
        r = self.get(rid)
        now = now or datetime.now()
        if r["repeat"] == "daily":
            nxt = datetime.fromisoformat(r["remind_at"])
            while nxt <= now:
                nxt += timedelta(days=1)
            self.db.execute("UPDATE reminders SET remind_at=? WHERE id=?", (nxt.isoformat(timespec="minutes"), rid))
        else:
            self.db.execute("UPDATE reminders SET acknowledged_at=? WHERE id=?", (now.isoformat(timespec="seconds"), rid))
        self.db.commit()
        return self.get(rid)

    def delete(self, rid: int) -> None:
        self.db.execute("DELETE FROM reminders WHERE id=?", (rid,))
        self.db.commit()

    def set_status(self, plan: CarePlan, item_id: str, status: str) -> dict:
        if status not in STATUSES:
            raise ReminderError(f"Status must be one of {sorted(STATUSES)}.")
        plan.item(item_id)
        self.db.execute("INSERT OR REPLACE INTO task_status VALUES (?,?,?,?)",
                        (plan.id, item_id, status, datetime.now().isoformat(timespec="seconds")))
        self.db.commit()
        return {"item_id": item_id, "status": status}

    def statuses(self, plan_id: str) -> dict[str, str]:
        return {r["item_id"]: r["status"] for r in self.db.execute(
            "SELECT item_id, status FROM task_status WHERE plan_id=?", (plan_id,))}

    def clear(self) -> None:
        self.db.executescript("DELETE FROM reminders; DELETE FROM task_status;")
        self.db.commit()
