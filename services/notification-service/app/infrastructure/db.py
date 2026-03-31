from __future__ import annotations

from shared.core.db.session import create_db, make_get_db

engine, SessionLocal, Base = create_db("NOTIFICATION_DB", echo=False)
get_db = make_get_db(SessionLocal)