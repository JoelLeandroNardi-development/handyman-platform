from fastapi import FastAPI
from .routes import router

app = FastAPI(title="Availability Service")

app.include_router(router)
