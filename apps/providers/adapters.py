from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import requests

from .models import ProviderLog


@dataclass
class ProviderResult:
    status: str
    provider_reference: str
    message: str
    network: str | None = None
    raw: dict[str, Any] | None = None


class BaseProviderAdapter:
    def __init__(self, provider):
        self.provider = provider

    def topup(self, mobile_number: str, amount: Decimal, network: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def _log(self, request_payload: dict[str, Any], response_payload: dict[str, Any], is_success: bool, reference: str = ""):
        ProviderLog.objects.create(
            provider=self.provider,
            action="topup",
            request_payload=request_payload,
            response_payload=response_payload,
            is_success=is_success,
            reference=reference,
        )


class MockProviderAdapter(BaseProviderAdapter):
    def topup(self, mobile_number: str, amount: Decimal, network: str | None = None) -> dict[str, Any]:
        response = {
            "status": "success",
            "provider_reference": f"{self.provider.code}-TXN-{mobile_number[-4:]}-{int(amount)}",
            "message": "Top-up completed successfully.",
            "network": network or "auto",
        }
        self._log(
            request_payload={"mobile_number": mobile_number, "amount": str(amount), "network": network},
            response_payload=response,
            is_success=True,
            reference=response["provider_reference"],
        )
        return response


class GenericHttpProviderAdapter(BaseProviderAdapter):
    """
    Generic adapter for real provider integration.
    Configure each provider in admin with base_url, auth_token and extra_config.

    Supported extra_config fields:
      - topup_path: "/v1/topup"
      - method: "POST" or "GET"
      - timeout_seconds: 20
      - auth_header: "Authorization"
      - auth_prefix: "Bearer"
      - headers: {"X-Client": "afghan-top"}
      - payload_template: {
            "msisdn": "{{mobile_number}}",
            "amount": "{{amount}}",
            "network": "{{network}}"
        }
      - response_mapping: {
            "status_key": "status",
            "success_values": ["success", "ok", true],
            "reference_key": "transaction_id",
            "message_key": "message"
        }
    """

    def topup(self, mobile_number: str, amount: Decimal, network: str | None = None) -> dict[str, Any]:
        cfg = self.provider.extra_config or {}
        request_payload = self._render_payload(
            cfg.get("payload_template") or {
                "mobile_number": "{{mobile_number}}",
                "amount": "{{amount}}",
                "network": "{{network}}",
            },
            mobile_number=mobile_number,
            amount=amount,
            network=network,
        )
        timeout = int(cfg.get("timeout_seconds", 20))
        method = str(cfg.get("method", "POST")).upper()
        path = str(cfg.get("topup_path", "")).lstrip("/")
        url = f"{self.provider.base_url.rstrip('/')}/{path}" if path else self.provider.base_url
        headers = {"Content-Type": "application/json", **(cfg.get("headers") or {})}
        auth_header = cfg.get("auth_header")
        if auth_header and self.provider.auth_token:
            prefix = str(cfg.get("auth_prefix", "")).strip()
            token_value = f"{prefix} {self.provider.auth_token}".strip()
            headers[auth_header] = token_value
        try:
            if method == "GET":
                resp = requests.get(url, params=request_payload, headers=headers, timeout=timeout)
            else:
                resp = requests.post(url, json=request_payload, headers=headers, timeout=timeout)
            raw = self._safe_json(resp)
            normalized = self._normalize_response(raw)
            self._log(request_payload=request_payload, response_payload=raw, is_success=normalized["status"] == "success", reference=normalized.get("provider_reference", ""))
            return normalized
        except requests.RequestException as exc:
            failure = {
                "status": "failed",
                "provider_reference": "",
                "message": f"Provider request failed: {exc}",
                "network": network,
            }
            self._log(request_payload=request_payload, response_payload=failure, is_success=False)
            return failure

    def _render_payload(self, template: dict[str, Any], **context: Any) -> dict[str, Any]:
        rendered = {}
        for key, value in template.items():
            if isinstance(value, str):
                value = value.replace("{{mobile_number}}", str(context.get("mobile_number", "")))
                value = value.replace("{{amount}}", str(context.get("amount", "")))
                value = value.replace("{{network}}", str(context.get("network", "")))
            rendered[key] = value
        return rendered

    def _normalize_response(self, raw: dict[str, Any]) -> dict[str, Any]:
        cfg = self.provider.extra_config or {}
        mapping = cfg.get("response_mapping") or {}
        status_key = mapping.get("status_key", "status")
        reference_key = mapping.get("reference_key", "provider_reference")
        message_key = mapping.get("message_key", "message")
        success_values = mapping.get("success_values", ["success", "ok", True, 1, "1"])
        status_value = raw.get(status_key)
        return {
            "status": "success" if status_value in success_values else "failed",
            "provider_reference": str(raw.get(reference_key, "")),
            "message": str(raw.get(message_key, "")) or "No provider message returned.",
            "network": raw.get("network"),
            "raw": raw,
        }

    def _safe_json(self, response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"data": payload, "status": response.status_code}
        except ValueError:
            return {"status": response.status_code, "message": response.text}
