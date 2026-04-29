import datetime
from collections.abc import Iterable

import structlog
from pybit.unified_trading import HTTP

from project.api.base import CoinMarketAPI
from project.currencies.structures import CandleData, Coin, HistoryData
from project.utils import request_counter, retry

logger = structlog.get_logger(__name__)


class BybitMarketAPI(CoinMarketAPI):
    def __init__(self, api_key: str, api_secret: str):
        self._client = HTTP(
            testnet=False,
            api_key=api_key,
            api_secret=api_secret
        )

    @request_counter
    @retry(exception_to_check=Exception, exception_matches=['10006', '10018', '10004'], delay=30)
    def get_currency_prices(self, currency_codes: Iterable[str]) -> list[Coin]:
        result = self._client.get_tickers(category="spot")
        logger.info('got bybit tickers', data=result)
        tickers = result.get('result', {}).get('list', [])
        code_set = {c.lower() for c in currency_codes}
        coins = []
        for ticker in tickers:
            symbol = ticker.get('symbol', '').lower()
            if symbol.endswith('usdt'):
                base = symbol.replace('usdt', '')
                if base in code_set:
                    coins.append(Coin(currency_code=base, price=float(ticker['lastPrice'])))
        return coins

    @request_counter
    @retry(exception_to_check=Exception, exception_matches=['10006', '10018', '10004'], delay=30)
    def get_history_price(self, currency_code: str) -> list[HistoryData]:
        candles = self.get_ohlc(currency_code=currency_code)
        logger.info('got bybit history price', data=candles)
        return [
            HistoryData(
                unix_timestamp=int(item.datetime.timestamp()),
                value=float(item.close)
            )
            for item in candles
        ]

    @request_counter
    @retry(exception_to_check=Exception, exception_matches=['10006', '10018', '10004'], delay=30)
    def get_ohlc(self, currency_code: str) -> list[CandleData]:
        now = datetime.datetime.now(datetime.timezone.utc)
        now_seconds = int(now.timestamp())
        prev_seconds = int((now - datetime.timedelta(hours=3)).timestamp())
        symbol = f"{currency_code.upper()}USDT"
        result = self._client.get_kline(
            category="spot",
            symbol=symbol,
            interval="5",
            start=prev_seconds * 1000,
            end=now_seconds * 1000
        )
        logger.info('got bybit ohlc data', data=result)
        kline_data = result.get('result', {}).get('list', [])
        return [
            CandleData(
                datetime=datetime.datetime.fromtimestamp(int(item[0]) // 1000, tz=datetime.timezone.utc),
                open=float(item[1]),
                high=float(item[2]),
                low=float(item[3]),
                close=float(item[4]),
                volume=float(item[5]),
                turnover=float(item[6]) if len(item) > 6 else 0
            )
            for item in kline_data
        ]

    @request_counter
    @retry(exception_to_check=Exception, exception_matches=['10006', '10018', '10004'], delay=30)
    def get_favorite_coins(self) -> list[str]:
        # Bybit does not have a direct 'favorites' endpoint; assuming 'watchlist' or 'positions' as proxy
        # Here, we use positions as an example (coins with a balance)
        result = self._client.get_wallet_balance(accountType="UNIFIED")
        logger.info('got bybit wallet balance', data=result)
        items = result.get('result', {}).get('list', [])
        if not items:
            return []

        # API responses vary by account type/tier. Support both:
        # - list[0]["coin"] -> list[{"coin": "...", "usdValue": "..."}]
        # - list -> list[{"coin": "...", "walletBalance": "..."}]
        first = items[0]
        balances = first.get("coin") if isinstance(first, dict) else None
        if isinstance(balances, list):
            return [
                str(item.get("coin", "")).lower()
                for item in balances
                if float(item.get("usdValue", 0) or 0) > 0.1
            ]

        return [
            str(item.get("coin", "")).lower()
            for item in items
            if float(item.get("walletBalance", 0) or 0) > 0
        ]
