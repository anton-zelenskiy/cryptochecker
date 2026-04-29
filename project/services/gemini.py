from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import structlog


logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SignalSummaryInput:
    symbol: str
    decision: str  # LONG/SHORT/WAIT
    confidence: float
    rsi_14: float | None = None
    notes: dict[str, str] | None = None


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

