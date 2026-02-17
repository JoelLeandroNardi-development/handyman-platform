from fastapi import FastAPI
from .routes import router

app = FastAPI(title="Auth Service")

app.include_router(router)
