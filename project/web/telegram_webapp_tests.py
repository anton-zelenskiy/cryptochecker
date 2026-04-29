import hashlib
import hmac
import urllib.parse

from project.web.telegram_webapp import verify_telegram_init_data


def _make_init_data(*, bot_token: str, params: dict[str, str]) -> str:
    # emulate Telegram signing
    data = dict(params)
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    data["hash"] = h
    return urllib.parse.urlencode(data)


def test_verify_telegram_init_data_ok():
    token = "123:ABC"
    init_data = _make_init_data(
        bot_token=token,
        params={
            "query_id": "AAH",
            "user": '{"id":1,"first_name":"A"}',
            "auth_date": "1710000000",
        },
    )
    assert verify_telegram_init_data(init_data, token) is True


def test_verify_telegram_init_data_bad_hash():
    token = "123:ABC"
    init_data = "user=%7B%22id%22%3A1%7D&hash=deadbeef"
    assert verify_telegram_init_data(init_data, token) is False

