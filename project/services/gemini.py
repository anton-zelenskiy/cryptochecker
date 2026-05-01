from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

import structlog

from project.core.config import settings
from project.core.redis_async import get_redis
from project.screener.contracts import ScreenerLlmRecheckResult


logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SignalSummaryInput:
    symbol: str
    decision: str  # LONG/SHORT/WAIT
    confidence: float
    rsi_14: float | None = None
    notes: dict[str, str] | None = None
    screener_final_decision: str | None = None
    screener_final_confidence: float | None = None
    screener_reasons: list[str] | None = None
    llm_verdict: str | None = None
    llm_rationale: str | None = None


def screener_llm_cache_key(features: dict, deterministic: dict) -> str:
    h = hashlib.sha256(
        json.dumps({"f": features, "d": deterministic}, sort_keys=True, default=str).encode()
    ).hexdigest()[:48]
    return f"screener:llm_rec:{h}"


def _parse_llm_json(text: str) -> dict | None:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


async def recheck_screener_with_gemini(
    *,
    features_json: dict,
    deterministic: dict,
) -> ScreenerLlmRecheckResult | None:
    if not getattr(settings, "SCREENER_LLM_RECHECK_ENABLED", True):
        return None

    cache_key = screener_llm_cache_key(features_json, deterministic)
    try:
        r = await get_redis()
        cached = await r.get(cache_key)
        if cached:
            raw = json.loads(cached)
            return ScreenerLlmRecheckResult.model_validate(raw)
    except Exception as e:
        logger.warning("screener llm cache read failed", error=str(e))

    try:
        from google import genai
    except Exception as e:
        logger.warning("gemini sdk unavailable", error=str(e))
        return None

    try:
        client = genai.Client()
    except Exception as e:
        logger.warning("gemini client init failed", error=str(e))
        return None

    prompt = (
        "You validate a deterministic crypto screener output. "
        "Reply with JSON only, no markdown, keys: "
        'verdict (one of accept, downgrade_to_wait, flip), '
        "confidence_adjust (number between -0.35 and 0.35), "
        "rationale (short string in English).\n\n"
        f"FEATURES_JSON:\n{json.dumps(features_json, ensure_ascii=False)[:12000]}\n\n"
        f"DETERMINISTIC_JSON:\n{json.dumps(deterministic, ensure_ascii=False)[:4000]}\n"
    )

    try:
        resp = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )
        text = getattr(resp, "text", None)
        if not text:
            return None
        parsed = _parse_llm_json(str(text))
        if not parsed:
            return None
        v = str(parsed.get("verdict", "accept")).lower().strip()
        if v not in ("accept", "downgrade_to_wait", "flip"):
            v = "accept"
        parsed["verdict"] = v
        try:
            adj = float(parsed.get("confidence_adjust", 0.0))
        except (TypeError, ValueError):
            adj = 0.0
        adj = max(-0.35, min(0.35, adj))
        parsed["confidence_adjust"] = adj
        if "rationale" not in parsed or not parsed["rationale"]:
            parsed["rationale"] = ""
        out = ScreenerLlmRecheckResult.model_validate(parsed)
    except Exception as e:
        logger.warning("gemini recheck failed", error=str(e))
        return None

    try:
        r = await get_redis()
        await r.set(cache_key, out.model_dump_json(), ex=3600)
    except Exception as e:
        logger.warning("screener llm cache write failed", error=str(e))

    return out


async def summarize_with_gemini(data: SignalSummaryInput) -> str | None:
    """
    Best-effort Gemini summary.
    Returns None if API key is missing or call fails.
    """
    try:
        from google import genai
    except Exception as e:
        logger.warning("gemini sdk unavailable", error=str(e))
        return None

    # Client reads GEMINI_API_KEY / GOOGLE_API_KEY from env by default.
    try:
        client = genai.Client()
    except Exception as e:
        logger.warning("gemini client init failed", error=str(e))
        return None

    prompt = (
        "You are a crypto market screener assistant. "
        "Given the structured calculation output, write a short Telegram-friendly summary "
        "in Russian. Keep it concise.\n\n"
        f"INPUT_JSON:\n{json.dumps(asdict(data), ensure_ascii=False, indent=2)}\n"
    )

    try:
        resp = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )
        text = getattr(resp, "text", None)
        return str(text).strip() if text else None
    except Exception as e:
        logger.warning("gemini call failed", error=str(e))
        return None

