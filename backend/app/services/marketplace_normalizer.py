from __future__ import annotations

import re


_BRACKET_RE = re.compile(r"[\[\(\{（【].*?[\]\)\}）】]")
_NON_WORD_RE = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff\.]+")
_SPACE_RE = re.compile(r"\s+")
_PSA_RE = re.compile(r"\bpsa\s*([0-9]{1,2})\b", re.IGNORECASE)
_BGS_RE = re.compile(r"\bbgs\s*([0-9](?:\.[0-9])?)\b", re.IGNORECASE)
_CGC_RE = re.compile(r"\bcgc\s*([0-9](?:\.[0-9])?)\b", re.IGNORECASE)

_DROP_TOKENS = (
    "官方",
    "现货",
    "秒发",
    "包邮",
    "自营",
    "旗舰店",
    "官方店",
    "官方旗舰店",
    "优惠",
    "券后",
    "补贴",
    "促销",
    "热卖",
    "全新",
    "正品",
    "保真",
    "特价",
)


def normalize_marketplace_canonical_key(raw_key: str | None = None, title: str | None = None) -> str:
    text = str(raw_key or "").strip()
    if not text:
        text = str(title or "").strip()
    if not text:
        return ""

    normalized = text.lower()
    normalized = _BRACKET_RE.sub(" ", normalized)
    normalized = normalized.replace("psa10", "psa 10")
    normalized = normalized.replace("psa9", "psa 9")
    normalized = normalized.replace("bgs95", "bgs 9.5")
    normalized = _PSA_RE.sub(lambda match: f"psa {match.group(1)}", normalized)
    normalized = _BGS_RE.sub(lambda match: f"bgs {match.group(1)}", normalized)
    normalized = _CGC_RE.sub(lambda match: f"cgc {match.group(1)}", normalized)
    normalized = _NON_WORD_RE.sub(" ", normalized)
    for token in _DROP_TOKENS:
        normalized = normalized.replace(token, " ")
    normalized = _SPACE_RE.sub(" ", normalized).strip()
    return normalized[:160]


def tokenize_marketplace_canonical_key(raw_key: str | None = None, title: str | None = None) -> list[str]:
    normalized = normalize_marketplace_canonical_key(raw_key=raw_key, title=title)
    if not normalized:
        return []
    return [token for token in normalized.split(" ") if token]


def explain_marketplace_match(
    *,
    left_title: str,
    right_title: str,
    left_key: str = "",
    right_key: str = "",
) -> dict[str, object]:
    left_canonical = normalize_marketplace_canonical_key(raw_key=left_key, title=left_title)
    right_canonical = normalize_marketplace_canonical_key(raw_key=right_key, title=right_title)
    left_tokens = tokenize_marketplace_canonical_key(raw_key=left_key, title=left_title)
    right_tokens = tokenize_marketplace_canonical_key(raw_key=right_key, title=right_title)
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    overlap = sorted(left_set & right_set)
    left_only = sorted(left_set - right_set)
    right_only = sorted(right_set - left_set)
    exact_match = bool(left_canonical and left_canonical == right_canonical)
    token_overlap_ratio = round((len(overlap) / max(1, len(left_set | right_set))), 4)
    if exact_match:
        verdict = "same_group"
        reason = "Canonical keys match exactly."
    elif overlap and token_overlap_ratio >= 0.6:
        verdict = "close_match"
        reason = "Canonical keys differ, but token overlap is high."
    else:
        verdict = "different_group"
        reason = "Canonical keys differ and token overlap is not high enough."
    return {
        "left_canonical_key": left_canonical,
        "right_canonical_key": right_canonical,
        "left_tokens": left_tokens,
        "right_tokens": right_tokens,
        "overlap_tokens": overlap,
        "left_only_tokens": left_only,
        "right_only_tokens": right_only,
        "exact_match": exact_match,
        "token_overlap_ratio": token_overlap_ratio,
        "verdict": verdict,
        "reason": reason,
    }
