from __future__ import annotations

from shared.shared.db import create_db, make_get_db


engine, SessionLocal, Base = create_db("NOTIFICATION_DB", echo=False)
get_db = make_get_db(SessionLocal)
