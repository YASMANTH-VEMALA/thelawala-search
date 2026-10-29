"""Unicode-safe text normalization shared by ingestion, queries, and logs."""

import re
import unicodedata
from functools import lru_cache


@lru_cache(maxsize=256)
def _phrase_pattern(keys: tuple[str, ...]):
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(k) for k in keys) + r")(?!\w)")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    # Keep combining marks: removing them destroys Telugu and Hindi words.
    value = "".join(
        ch if ch.isalnum() or unicodedata.category(ch).startswith("M")
        or (ch == "." and index > 0 and index+1 < len(value)
            and value[index-1].isdigit() and value[index+1].isdigit()) else " "
        for index, ch in enumerate(value)
    )
    value = re.sub(r"(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)", " ", value)
    return " ".join(value.split())


def replace_phrases(text: str, mapping: dict[str, str]) -> str:
    """One pass, longest phrase first; replacements never recursively expand."""
    if not mapping:
        return text
    pattern = _phrase_pattern(tuple(sorted(mapping, key=lambda k: (-len(k), k))))
    return pattern.sub(lambda match: mapping[match.group()], text)
