from __future__ import annotations

from shared.core.db.session import create_db, make_get_db
from .config import NOTIFICATION_DB_ENV

engine, SessionLocal, Base = create_db(NOTIFICATION_DB_ENV, echo=False)
get_db = make_get_db(SessionLocal)