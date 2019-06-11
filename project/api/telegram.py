import requests
import json

from ..config import API_TOKEN


class TelegramAPI:
    """"""

    request_url = 'https://api.telegram.org/bot{api_token}/{method}/'
    headers = {
        'Content-Type': 'application/json',
        'charset': 'utf-8',
    }

    def __init__(self):
        pass

    def set_webhook(self):
        method = 'setWebhook'

        return self._make_request(method, {})

    def delete_webhook(self):
        method = 'deleteWebhook'

        return self._make_request(method, {})

    def get_webhook_info(self):
        method = 'getWebhookInfo'

        return self._make_request(method, {})

    def _make_request(self, method, data):
        """Осуществляет запрос. """
        r = requests.post(
            url=self.request_url.format(
                api_token=API_TOKEN,
                method=method
            ),
            headers=self.headers,
            data=json.dumps(data)
        )
        r.raise_for_status()

        result = r.json()

        return result
