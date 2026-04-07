def normalize_afghan_mobile(value: str) -> str:
    value = (value or "").strip().replace(" ", "")
    if value.startswith("+93"):
        return value
    if value.startswith("93") and len(value) >= 11:
        return f"+{value}"
    if value.startswith("0"):
        return "+93" + value[1:]
    return value
