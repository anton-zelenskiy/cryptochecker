from __future__ import annotations

from fastapi import APIRouter

from project.web.api.health import router as health_router
from project.web.api.telegram import router as telegram_router
from project.web.api.webapp import router as webapp_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(telegram_router)
api_router.include_router(webapp_router)

