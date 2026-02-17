from fastapi import FastAPI
from .routes import router

app = FastAPI(title="User Service")

app.include_router(router)
