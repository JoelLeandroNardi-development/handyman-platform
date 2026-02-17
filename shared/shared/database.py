from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

def get_engine(database_url: str):
    return create_async_engine(database_url, echo=False, future=True)

Base = declarative_base()

def get_session(engine):
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False
    )
