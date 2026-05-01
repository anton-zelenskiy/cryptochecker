from __future__ import annotations

import contextlib

import structlog

from fastapi import FastAPI

from project.core.config import settings
from project.models import candles as _candles  # noqa: F401
from project.models import catalog as _catalog  # noqa: F401
from project.models import coin_metadata as _coin_metadata  # noqa: F401
from project.models import indicators as _indicators  # noqa: F401
from project.models import market_trades as _market_trades  # noqa: F401
from project.models import orderbook_walls as _orderbook_walls  # noqa: F401
from project.models import paper_trading as _paper  # noqa: F401
from project.models import trade_clusters as _trade_clusters  # noqa: F401
from project.models import users as _users  # noqa: F401
from project.models import volatility_events as _vol_events  # noqa: F401
from project.models import screener as _screener  # noqa: F401
from project.models import notifications as _notifications  # noqa: F401
from project.web.bot import build_bot
from project.web.api.router import api_router


logger = structlog.get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    bot = app.state.bot

    yield

    await bot.session.close()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

bot, dp = build_bot()
app.state.bot = bot
app.state.dp = dp

app.include_router(api_router, prefix="/cryptochecker")

