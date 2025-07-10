import datetime
import pytest
from unittest.mock import MagicMock, patch
from project.api.bybit import BybitMarketAPI
from project.currencies.structures import Coin, HistoryData, CandleData

@pytest.fixture
def bybit_api():
    with patch('project.api.bybit.HTTP') as mock_http:
        mock_client = MagicMock()
        mock_http.return_value = mock_client
        api = BybitMarketAPI(api_key='test', api_secret='test')
        api._client = mock_client
        yield api, mock_client

def test_get_currency_prices(bybit_api):
    api, mock_client = bybit_api
    mock_client.get_tickers.return_value = {
        'result': {
            'list': [
                {'symbol': 'BTCUSDT', 'lastPrice': '50000'},
                {'symbol': 'ETHUSDT', 'lastPrice': '4000'},
            ]
        }
    }
    result = api.get_currency_prices(['btc', 'eth'])
    assert result == [
        Coin(currency_code='btc', price=50000.0),
        Coin(currency_code='eth', price=4000.0)
    ]

def test_get_ohlc(bybit_api):
    api, mock_client = bybit_api
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    mock_client.get_kline.return_value = {
        'result': {
            'list': [
                [str(now * 1000), '1', '2', '0.5', '1.5', '100', '150']
            ]
        }
    }
    result = api.get_ohlc('btc')
    assert isinstance(result[0], CandleData)
    assert result[0].open == 1.0
    assert result[0].close == 1.5
    assert result[0].volume == 100.0
    assert result[0].turnover == 150.0

def test_get_history_price(bybit_api):
    api, mock_client = bybit_api
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    mock_client.get_kline.return_value = {
        'result': {
            'list': [
                [str(now * 1000), '1', '2', '0.5', '1.5', '100', '150']
            ]
        }
    }
    result = api.get_history_price('btc')
    assert isinstance(result[0], HistoryData)
    assert result[0].value == 1.5

def test_get_favorite_coins(bybit_api):
    api, mock_client = bybit_api
    mock_client.get_wallet_balance.return_value = {
        'result': {
            'list': [
                {'coin': 'BTC', 'walletBalance': '0.1'},
                {'coin': 'ETH', 'walletBalance': '0.0'},
                {'coin': 'USDT', 'walletBalance': '5'}
            ]
        }
    }
    result = api.get_favorite_coins()
    assert set(result) == {'btc', 'usdt'}