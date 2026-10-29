"""Unicode-safe text normalization shared by ingestion, queries, and logs."""

import re
import unicodedata


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    # Keep combining marks: removing them destroys Telugu and Hindi words.
    value = "".join(
        ch if ch.isalnum() or unicodedata.category(ch).startswith("M") else " "
        for ch in value
    )
    value = re.sub(r"(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)", " ", value)
    return " ".join(value.split())


def replace_phrases(text: str, mapping: dict[str, str]) -> str:
    """One pass, longest phrase first; replacements never recursively expand."""
    if not mapping:
        return text
    pattern = r"(?<!\w)(?:" + "|".join(
        re.escape(k) for k in sorted(mapping, key=len, reverse=True)
    ) + r")(?!\w)"
    return re.sub(pattern, lambda match: mapping[match.group()], text)
