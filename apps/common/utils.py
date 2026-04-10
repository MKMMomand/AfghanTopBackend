def normalize_afghan_mobile(value: str) -> str:
    value = (value or "").strip().replace(" ", "")
    if value.startswith("+93"):
        return value
    if value.startswith("93") and len(value) >= 11:
        return f"+{value}"
    if value.startswith("0"):
        return "+93" + value[1:]
    return value


import re

AFGHAN_MOBILE_RE = re.compile(r"^(?:\+93|93|0)?7\d{8}$")
AFGHAN_TAZKIRA_RE = re.compile(r"^(?:\d{4,8}[-/ ]?\d{4,8}|[A-Za-z]{1,3}[-/ ]?\d{4,10})$")

def is_valid_afghan_mobile(value: str) -> bool:
    value = (value or "").strip().replace(" ", "")
    return bool(AFGHAN_MOBILE_RE.match(value))

def validate_afghan_tazkira(value: str) -> str:
    value = (value or "").strip().upper()
    if not value:
        return value
    compact = re.sub(r"\s+", "", value)
    if not AFGHAN_TAZKIRA_RE.match(compact):
        raise ValueError("Please enter a valid Afghan tazkira number.")
    return compact
