from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .middleware import RequestLoggingMiddleware, RateLimitMiddleware
from .routes.system import router as system_router
from .routes.auth import router as auth_router
from .routes.users import router as users_router
from .routes.handymen import router as handymen_router
from .routes.availability import router as availability_router
from .routes.match import router as match_router
from .routes.bookings import router as bookings_router

origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

OPENAPI_TAGS = [
    {"name": "System"},
    {"name": "Auth"},
    {"name": "Users"},
    {"name": "Handymen"},
    {"name": "Availability"},
    {"name": "Match"},
    {"name": "Bookings"},
]

app = FastAPI(title="Smart API Gateway", openapi_tags=OPENAPI_TAGS)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_per_minute=120)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(handymen_router)
app.include_router(availability_router)
app.include_router(match_router)
app.include_router(bookings_router)
