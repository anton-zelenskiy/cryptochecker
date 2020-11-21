import requests
from urllib.parse import urlencode

from ..config import API_TOKEN


class TelegramAPI:
    """Simple tg api."""

    request_url = 'https://api.telegram.org/bot{api_token}/{method}'
    headers = {
        'Content-Type': 'application/json',
        'charset': 'utf-8',
    }

    def __init__(self):
        pass

    def get_me(self):
        method = 'getMe'

        return self._make_request(method, {})

    def get_webhook_info(self):
        method = 'getWebhookInfo'

        return self._make_request(method, {})

    def set_webhook(self, params):
        method = 'setWebhook'

        return self._make_request(method, params)

    def send_message(self, params):
        method = 'sendMessage'

        return self._make_request(method, params)

    def delete_webhook(self):
        method = 'deleteWebhook'

        return self._make_request(method, {})

    def _make_request(self, method, data):
        """Sends request."""
        r = requests.get(
            url=self.request_url.format(
                api_token=API_TOKEN,
                method=method
            ),
            headers=self.headers,
            params=urlencode(data)
        )
        r.raise_for_status()
        result = r.json()

        return result, r.url
