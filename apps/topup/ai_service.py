import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from typing import Any

import requests
from decouple import config as env

logger = logging.getLogger(__name__)


class AiServiceError(Exception):
    pass


@dataclass
class AiContext:
    user_identifier: str
    transactions: list[dict[str, Any]]
    favorites: list[dict[str, Any]]
    reminders: list[dict[str, Any]]


class OpenAISuggestionsService:
    """Generate smart top-up cards with OpenAI Responses API."""

    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self) -> None:
        self.api_key = env("OPENAI_API_KEY", default="").strip()
        self.model = env("OPENAI_MODEL", default="gpt-4.1-mini").strip()
        self.timeout = env("OPENAI_TIMEOUT_SECONDS", default=25, cast=int)
        self.enabled = env("AI_ENABLE_REAL_SUGGESTIONS", default=True, cast=bool) and bool(self.api_key)

    def generate_cards(self, context: AiContext) -> list[dict[str, Any]]:
        if not self.enabled:
            raise AiServiceError("OpenAI suggestions are not configured.")

        payload = {
            "model": self.model,
            "instructions": self._instructions(),
            "input": json.dumps(self._input_payload(context), ensure_ascii=False),
            "temperature": 0.3,
            "max_output_tokens": 900,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ai_smart_cards",
                    "schema": self._schema(),
                    "strict": True,
                }
            },
            "safety_identifier": sha256(context.user_identifier.encode("utf-8")).hexdigest()[:32],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise AiServiceError(f"OpenAI request failed: {exc}") from exc

        raw_text = (data.get("output_text") or "").strip()
        if not raw_text:
            raise AiServiceError("OpenAI returned an empty response.")

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning("Unable to decode OpenAI AI card payload: %s", raw_text)
            raise AiServiceError("OpenAI returned invalid JSON.") from exc

        cards = parsed.get("cards") or []
        cleaned = [self._normalize_card(card) for card in cards[:4] if isinstance(card, dict)]
        if not cleaned:
            raise AiServiceError("OpenAI returned no valid smart cards.")
        return cleaned

    def _input_payload(self, context: AiContext) -> dict[str, Any]:
        return {
            "task": "Generate 2 to 4 smart cards for an Afghan mobile top-up reseller app.",
            "user_context": {
                "user_identifier": context.user_identifier,
                "transaction_count": len(context.transactions),
                "favorite_count": len(context.favorites),
                "reminder_count": len(context.reminders),
            },
            "transactions": context.transactions,
            "favorites": context.favorites,
            "reminders": context.reminders,
            "supported_routes": [
                "transactions",
                "favorites",
                "credit",
                "notifications",
                "profile",
                "services",
                "dashboard",
            ],
            "supported_card_types": [
                "repeat_topup",
                "review_pending",
                "due_reminder",
                "favorite_shortcut",
                "balance_snapshot",
                "warmup",
            ],
        }

    def _instructions(self) -> str:
        return (
            "You generate smart action cards for Afghan Top, a reseller mobile recharge app. "
            "Return only JSON that matches the schema. Create practical suggestions from transaction, favorite, and reminder history. "
            "Prefer actions the app can actually do now: open top-up with a number and amount, open transactions, open favorites, open credit, open services, or open dashboard. "
            "Do not invent unsupported features. Keep messages under 160 characters and action labels under 20 characters. "
            "confidence must be between 0.50 and 0.99. source must be 'openai'."
        )

    def _schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "cards": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"type": "string"},
                            "title": {"type": "string"},
                            "message": {"type": "string"},
                            "action_label": {"type": "string"},
                            "mobile_number": {"type": ["string", "null"]},
                            "amount": {"type": ["string", "null"]},
                            "network": {"type": ["string", "null"]},
                            "route": {"type": ["string", "null"]},
                            "confidence": {"type": "number"},
                            "source": {"type": "string"},
                        },
                        "required": [
                            "type",
                            "title",
                            "message",
                            "action_label",
                            "mobile_number",
                            "amount",
                            "network",
                            "route",
                            "confidence",
                            "source",
                        ],
                    },
                }
            },
            "required": ["cards"],
        }

    def _normalize_card(self, card: dict[str, Any]) -> dict[str, Any]:
        confidence = float(card.get("confidence") or 0.7)
        if confidence < 0.5:
            confidence = 0.5
        if confidence > 0.99:
            confidence = 0.99
        amount_value = card.get("amount")
        if amount_value is not None:
            try:
                amount_value = str(int(Decimal(str(amount_value))))
            except Exception:
                amount_value = str(amount_value)
        return {
            "type": str(card.get("type") or "warmup"),
            "title": str(card.get("title") or "Smart suggestion"),
            "message": str(card.get("message") or "Open services to continue."),
            "action_label": str(card.get("action_label") or "Open"),
            "mobile_number": self._none_or_str(card.get("mobile_number")),
            "amount": self._none_or_str(amount_value),
            "network": self._none_or_str(card.get("network")),
            "route": self._none_or_str(card.get("route")),
            "confidence": confidence,
            "source": "openai",
        }

    @staticmethod
    def _none_or_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
