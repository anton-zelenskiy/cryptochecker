import redis
from typing import Iterable
from project import settings
from project import constants
from functools import lru_cache

from project.currencies.structures import AppMode


@lru_cache()
def get_redis():
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True,
    )


class SettingStorage:
    def __init__(self, redis: redis.Redis | None = None) -> None:
        self.redis = redis or get_redis()

    def get_chat_ids(self) -> Iterable[str]:
        chat_ids = self.redis.smembers(constants.CACHE_KEY_CHATS)

        if not chat_ids:
            return []

        return chat_ids

    def get_all_user_currencies(self, chat_ids: Iterable[str]):
        result = {}
        for chat_id in chat_ids:
            result.update({chat_id: self.get_user_currencies(chat_id)})
        return result

    def get_user_currencies(self, chat_id: str | int) -> set[str]:
        currencies = self.redis.smembers(f"volatility:user:{chat_id}:currencies") or set()

        return {i.lower() for i in currencies}


    def get_volatility_threshold(self, chat_id: str | int) -> float:
        value = self.redis.get(f"volatility:user:{chat_id}:threshold") or constants.DEFAULT_VOLATILITY_THRESHOLD_PERCENT

        try:
            volatility_threshold = float(value)
        except TypeError:
            volatility_threshold = constants.DEFAULT_VOLATILITY_THRESHOLD_PERCENT

        return volatility_threshold

    def set_volatility_threshold(self, user_id: str | int, value: float) -> None:
        self.redis.set(f'volatility:user:{user_id}:threshold', value)


    def get_app_mode(self, chat_id: str | int) -> AppMode:
        value = self.redis.get(f'user:{chat_id}:app_mode') or AppMode.CHECK_SELECTED_COINS
        return AppMode(value)

    def set_app_mode(self, chat_id: str | int, value: AppMode) -> None:
        self.redis.set(f'user:{chat_id}:app_mode', value.value)

    def is_notifications_enabled(self, chat_id: str | int) -> bool:
        return self.redis.sismember(constants.CACHE_KEY_CHATS, chat_id)

    def toggle_notifications(self, chat_id: str | int) -> bool:
        is_enabled = self.is_notifications_enabled(chat_id)

        if is_enabled:
            self.redis.srem(constants.CACHE_KEY_CHATS, chat_id)
        else:
            self.redis.sadd(constants.CACHE_KEY_CHATS, chat_id)

        return not is_enabled

    def watch_coin(self, user_id: str | int, coin: str) -> None:
        self.redis.sadd(
            f'volatility:user:{user_id}:currencies',
            coin
        )

    def unwatch_coin(self, user_id: str | int, coin: str) -> None:
        self.redis.srem(
            f'volatility:user:{user_id}:currencies',
            coin
        )
