from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests

from .models import ProviderLog


class BaseProviderAdapter:
    def __init__(self, provider):
        self.provider = provider

    def topup(self, mobile_number: str, amount: Decimal, network: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def wallet_balance(self) -> dict[str, Any]:
        return {
            "status": "unsupported",
            "message": "Wallet balance lookup is not supported by this provider.",
            "raw": {},
        }

    def order_status(self, order_id: str) -> dict[str, Any]:
        return {
            "status": "unsupported",
            "provider_reference": order_id,
            "message": "Order status lookup is not supported by this provider.",
            "raw": {},
        }

    def _log(
        self,
        *,
        action: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        is_success: bool,
        reference: str = "",
    ):
        ProviderLog.objects.create(
            provider=self.provider,
            action=action,
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
            "raw": {"mock": True},
        }
        self._log(
            action="topup",
            request_payload={"mobile_number": mobile_number, "amount": str(amount), "network": network},
            response_payload=response,
            is_success=True,
            reference=response["provider_reference"],
        )
        return response


class SendAfProviderAdapter(BaseProviderAdapter):
    RESULT_MESSAGES = {
        "1": "Top-up order posted successfully and is being processed.",
        "002": "Provider rejected the request because the server IP is not whitelisted.",
        "003": "The same amount to the same number is not allowed for 5 minutes.",
        "004": "The amount must be between 50 AFN and 4000 AFN.",
        "005": "Wallet amount is invalid.",
        "006": "Provider token is invalid.",
        "007": "Provider wallet balance is not enough.",
        "008": "Mobile number is invalid.",
        "009": "Operator code is invalid.",
        "010": "Operator is under maintenance.",
        "011": "Invalid order ID.",
        "012": "Unauthorized order ID.",
    }

    def topup(self, mobile_number: str, amount: Decimal, network: str | None = None) -> dict[str, Any]:
        request_payload = {
            "phone": self._format_phone(mobile_number),
            "amount": self._format_amount(amount),
            "network": network or "",
        }
        try:
            raw = self._request("topup", request_payload)
            normalized = self._normalize_topup(raw, network=network)
            self._log(
                action="topup",
                request_payload=request_payload,
                response_payload=raw,
                is_success=normalized["status"] in {"success", "pending"},
                reference=normalized.get("provider_reference", ""),
            )
            return normalized
        except requests.RequestException as exc:
            failure = {
                "status": "failed",
                "provider_reference": "",
                "message": f"Provider request failed: {exc}",
                "network": network,
                "raw": {"exception": str(exc)},
            }
            self._log(action="topup", request_payload=request_payload, response_payload=failure, is_success=False)
            return failure

    def wallet_balance(self) -> dict[str, Any]:
        try:
            raw = self._request("wallet", {})
            data = self._extract_payload(raw)
            balance = data.get("balance") or data.get("wallet") or data.get("amount") or data.get("data")
            result = {
                "status": "success",
                "message": "Wallet balance fetched successfully.",
                "balance": balance,
                "raw": raw,
            }
            self._log(action="wallet", request_payload={}, response_payload=raw, is_success=True)
            return result
        except requests.RequestException as exc:
            failure = {
                "status": "failed",
                "message": f"Provider wallet request failed: {exc}",
                "raw": {"exception": str(exc)},
            }
            self._log(action="wallet", request_payload={}, response_payload=failure, is_success=False)
            return failure

    def order_status(self, order_id: str) -> dict[str, Any]:
        request_payload = {"order_id": order_id}
        try:
            raw = self._request("orderStatus", request_payload)
            normalized = self._normalize_order_status(raw, order_id=order_id)
            self._log(
                action="order_status",
                request_payload=request_payload,
                response_payload=raw,
                is_success=normalized["status"] in {"success", "pending"},
                reference=normalized.get("provider_reference", order_id),
            )
            return normalized
        except requests.RequestException as exc:
            failure = {
                "status": "failed",
                "provider_reference": order_id,
                "message": f"Provider order status request failed: {exc}",
                "raw": {"exception": str(exc)},
            }
            self._log(action="order_status", request_payload=request_payload, response_payload=failure, is_success=False, reference=order_id)
            return failure

    def _request(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        cfg = self.provider.extra_config or {}
        timeout = int(cfg.get("timeout_seconds", 20))
        path = cfg.get(f"{action}_path") or action
        base_url = (self.provider.base_url or "https://www.send.af/api").rstrip("/")
        url = f"{base_url}/{str(path).lstrip('/')}"
        query = {"token": self.provider.auth_token, **params}
        response = requests.get(url, params=query, timeout=timeout)
        response.raise_for_status()
        return self._safe_payload(response)

    def _safe_payload(self, response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {"data": payload, "http_status": response.status_code, "text": response.text}
        except ValueError:
            text = response.text.strip()
            return {
                "code": self._extract_code(text),
                "message": text,
                "http_status": response.status_code,
                "text": text,
                "query": response.url,
            }

    def _extract_payload(self, raw: dict[str, Any]) -> dict[str, Any]:
        data = raw.get("data")
        return data if isinstance(data, dict) else raw

    def _normalize_topup(self, raw: dict[str, Any], network: str | None = None) -> dict[str, Any]:
        data = self._extract_payload(raw)
        code = self._as_code(data.get("code") or data.get("status") or raw.get("code") or raw.get("status"))
        provider_reference = str(
            data.get("order_id")
            or data.get("orderId")
            or data.get("reference")
            or data.get("transaction_id")
            or raw.get("order_id")
            or ""
        )
        message = self._resolve_message(code, data.get("message") or raw.get("message"))
        status = "pending" if code == "1" else "failed"
        if code in {"success", "ok"}:
            status = "success"
        return {
            "status": status,
            "provider_reference": provider_reference,
            "message": message,
            "network": network,
            "raw": raw,
            "provider_code": code,
        }

    def _normalize_order_status(self, raw: dict[str, Any], order_id: str) -> dict[str, Any]:
        data = self._extract_payload(raw)
        code = self._as_code(data.get("code") or data.get("status") or raw.get("code") or raw.get("status"))
        message = self._resolve_message(code, data.get("message") or raw.get("message"))
        provider_reference = str(data.get("order_id") or raw.get("order_id") or order_id)

        text_blob = f"{message} {raw}".lower()
        if code in {"011", "012", "006", "007", "008", "009", "010"}:
            status = "failed"
        elif any(term in text_blob for term in ["success", "completed", "done"]):
            status = "success"
        elif any(term in text_blob for term in ["process", "pending", "queue"]):
            status = "pending"
        else:
            status = "pending" if code == "1" else "failed"

        return {
            "status": status,
            "provider_reference": provider_reference,
            "message": message,
            "raw": raw,
            "provider_code": code,
        }

    def _resolve_message(self, code: str, provider_message: Any) -> str:
        message = str(provider_message or "").strip()
        return message or self.RESULT_MESSAGES.get(code, "No provider message returned.")

    def _as_code(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            if int(value) == 1:
                return "1"
            return str(int(value)).zfill(3)
        return str(value).strip()

    def _extract_code(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return ""
        head = stripped.split()[0]
        digits = "".join(ch for ch in head if ch.isdigit())
        if digits == "1":
            return "1"
        if len(digits) == 3:
            return digits
        return digits or stripped

    def _format_phone(self, value: str) -> str:
        compact = str(value).replace("+93", "0").replace("93", "0")
        compact = compact.replace(" ", "")
        return compact

    def _format_amount(self, amount: Decimal) -> str:
        return str(int(amount)) if amount == int(amount) else str(amount)


class GenericHttpProviderAdapter(BaseProviderAdapter):
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
            self._log(
                action="topup",
                request_payload=request_payload,
                response_payload=raw,
                is_success=normalized["status"] == "success",
                reference=normalized.get("provider_reference", ""),
            )
            return normalized
        except requests.RequestException as exc:
            failure = {
                "status": "failed",
                "provider_reference": "",
                "message": f"Provider request failed: {exc}",
                "network": network,
            }
            self._log(action="topup", request_payload=request_payload, response_payload=failure, is_success=False)
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
            return {"status": response.status_code, "message": response.text, "text": response.text, "query": response.url}
