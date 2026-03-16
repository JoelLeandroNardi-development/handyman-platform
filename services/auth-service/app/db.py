from shared.shared.db import create_db

engine, SessionLocal, Base = create_db("AUTH_DB")
