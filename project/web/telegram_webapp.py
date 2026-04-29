from __future__ import annotations

import hashlib
import hmac
import urllib.parse


def verify_telegram_init_data(init_data: str, bot_token: str) -> bool:
    """
    Verify Telegram WebApp initData signature.

    Based on Telegram docs: calculate HMAC-SHA256 over data_check_string using secret_key.
    secret_key = HMAC-SHA256("WebAppData", bot_token)
    """
    if not init_data:
        return False

    params = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    data = dict(params)
    received_hash = data.pop("hash", None)
    if not received_hash:
        return False

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated_hash, received_hash)

