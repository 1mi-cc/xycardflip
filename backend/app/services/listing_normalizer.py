from __future__ import annotations

from dataclasses import dataclass
import re


NORMALIZATION_VERSION = "listing_normalizer_v1"
TRADABLE_ITEM_TYPES = frozenset({"manual_fragment", "manual_page", "manual_card"})
BLOCKED_ITEM_TYPES = frozenset({"account_service", "catalog_bundle"})

_VIRTUAL_GOODS_TOKENS = (
    "\u865a\u62df\u9053\u5177",
    "\u865a\u62df\u5546\u54c1",
    "\u865a\u62df\u7269\u54c1",
)
_VIRTUAL_GOODS_STRONG_TOKENS = (
    "\u6e38\u620f\u5185\u76f4\u63a5\u4ea4\u6613",
    "\u6e38\u620f\u5185\u4ea4\u6613",
    "\u552e\u51fa\u4e0d\u9000",
    "\u4e0d\u9000\u4e0d\u6362",
    "\u62cd\u4e0b\u53d1\u533a\u670d",
    "\u62cd\u4e0b\u7559\u533a\u53f7",
)

_ACCOUNT_SERVICE_TOKENS = (
    "\u626b\u7801",
    "\u4e0a\u53f7",
    "\u767b\u5f55",
    "\u8d26\u53f7",
    "\u4e91\u624b\u673a",
    "\u6a21\u62df\u5668",
    "\u4ee3\u7ec3",
    "\u6258\u7ba1",
)
_CATALOG_BUNDLE_TOKENS = (
    "\u56fe\u9274",
    "\u793c\u5305",
    "\u91d1\u56fe\u9274",
    "\u7ea2\u56fe\u9274",
    "\u51fa\u5168",
    "\u5168\u5957",
    "\u6574\u5957",
    "\u968f\u673a",
)
_DELIVERY_MARKETING_TOKENS = (
    "\u79d2\u53d1",
    "\u76f4\u53d1",
    "\u81ea\u52a8\u53d1\u8d27",
    "\u73b0\u8d27",
    "\u79c1\u804a",
    "\u8001\u677f",
    "\u8bda\u4fe1\u4ea4\u6613",
    "\u53ef\u5200",
)
_GAMEPLAY_NOISE_TOKENS = (
    "\u6ee1\u653b",
    "\u6ee1\u7ea2",
    "\u81f3\u5c0a",
    "\u6ee1\u7206",
    "\u5168\u5e73\u53f0",
    "\u4e92\u901a",
    "\u51b2\u5206",
    "\u4e3b\u529b\u57f9\u517b",
    "\u62cd\u5356\u4f1a",
    "\u5c5e\u6027\u62c9\u6ee1",
    "\u5e26\u8fd0\u6c14\u8bc0",
    "\u6c14\u5b9a\u795e\u95f2",
)
_REMOVE_TOKENS = (
    "\u54b8\u9c7c\u4e4b\u738b",
    "\u54c1\u9c7c\u4e4b\u738b",
    "\u5a01\u9c7c\u4e4b\u738b",
    "\u865a\u62df\u9053\u5177",
    "\u6e38\u620f\u5185\u76f4\u63a5\u4ea4\u6613",
    "\u73b0\u8d27\u79d2\u53d1",
    "\u81ea\u52a8\u53d1\u8d27",
    "\u6b22\u8fce\u6765\u95ee",
    "\u559c\u6b22\u76f4\u63a5\u62cd",
    "\u9700\u8981\u7684\u8001\u677f\u968f\u65f6\u6765\u804a",
)


@dataclass(slots=True)
class ListingNormalization:
    normalized_title: str
    normalized_key: str
    item_type: str
    noise_flags: list[str]
    normalization_confidence: float
    normalization_blocked: bool
    normalization_reason: str
    normalization_version: str = NORMALIZATION_VERSION


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _collapse_spaces(text: str) -> str:
    return " ".join(text.split()).strip()


def _strip_brackets(text: str) -> str:
    return re.sub(r"[\[\(\u3010\uff08].*?[\]\)\u3011\uff09]", " ", text)


def _strip_numeric_stats(text: str) -> str:
    text = re.sub(r"[+\-]?\d+(?:\.\d+)?\s*[\u4e07wW]?", " ", text)
    text = re.sub(
        r"(\u653b\u51fb|\u8840\u91cf|\u901f\u5ea6|\u6218\u529b|\u8bc4\u5206|\u4ef7\u683c)\s*",
        " ",
        text,
    )
    return text


def _sanitize_title(raw_title: str) -> str:
    text = str(raw_title or "").strip().lower()
    text = _strip_brackets(text)
    text = _strip_numeric_stats(text)
    for token in _REMOVE_TOKENS:
        text = text.replace(token, " ")
    text = re.sub(r"[~\u301c\uff01\uff1f\uff01\uff0c\u3002\uff1a\uff1b\\|/]+", " ", text)
    return _collapse_spaces(text)


def _item_type_from_text(text: str) -> str:
    if _contains_any(text, _ACCOUNT_SERVICE_TOKENS):
        return "account_service"
    if (
        _contains_any(text, _VIRTUAL_GOODS_TOKENS)
        and _contains_any(text, _VIRTUAL_GOODS_STRONG_TOKENS)
        and _contains_any(text, ("\u79d2\u53d1", "\u76f4\u53d1", "\u53d1id", "\u53d1\u533a\u670d"))
    ):
        return "virtual_goods"
    if _contains_any(text, _CATALOG_BUNDLE_TOKENS):
        return "catalog_bundle"
    if "\u6b8b\u5377" in text:
        return "manual_fragment"
    if "\u4e66\u9875" in text:
        return "manual_page"
    if "\u529f\u6cd5" in text:
        return "manual_card"
    return "unknown"


def _noise_flags_from_text(text: str, item_type: str) -> list[str]:
    flags: list[str] = []
    if item_type == "account_service":
        flags.append("account_service")
    if item_type == "catalog_bundle":
        flags.append("catalog_bundle")
    if _contains_any(text, _DELIVERY_MARKETING_TOKENS):
        flags.append("delivery_marketing")
    if _contains_any(text, _GAMEPLAY_NOISE_TOKENS):
        flags.append("gameplay_marketing")
    if len(text) >= 64:
        flags.append("long_marketing_title")
    return flags


def _normalized_title_from_type(item_type: str, sanitized_title: str) -> str:
    if item_type == "manual_fragment":
        return "\u529f\u6cd5\u6b8b\u5377"
    if item_type == "manual_page":
        return "\u529f\u6cd5\u4e66\u9875"
    if item_type == "manual_card":
        return "\u529f\u6cd5\u5361"
    if item_type == "virtual_goods":
        return sanitized_title[:48] or "\u865a\u62df\u5546\u54c1"
    if item_type == "catalog_bundle":
        return "\u56fe\u9274\u793c\u5305"
    if item_type == "account_service":
        return "\u8d26\u53f7\u670d\u52a1"
    return sanitized_title[:48]


def normalize_listing(*, title: str, description: str = "") -> ListingNormalization:
    combined = _collapse_spaces(f"{title} {description}".lower())
    sanitized_title = _sanitize_title(title)
    item_type = _item_type_from_text(combined or sanitized_title)
    noise_flags = _noise_flags_from_text(combined or sanitized_title, item_type)
    normalized_title = _normalized_title_from_type(item_type, sanitized_title)
    normalized_key = f"{item_type}:{normalized_title}" if normalized_title else item_type

    blocked = item_type in BLOCKED_ITEM_TYPES
    blocked_reason = ""
    if blocked:
        blocked_reason = item_type
    elif item_type == "unknown" and len(noise_flags) >= 2:
        blocked = True
        blocked_reason = "unknown_noise_listing"

    confidence = 0.25
    if item_type in {"manual_fragment", "manual_page"}:
        confidence = 0.98
    elif item_type == "manual_card":
        confidence = 0.82
    elif item_type in {"catalog_bundle", "account_service"}:
        confidence = 0.95
    elif normalized_title:
        confidence = 0.45
    confidence = max(0.0, min(1.0, confidence - (0.08 * max(0, len(noise_flags) - 1))))

    return ListingNormalization(
        normalized_title=normalized_title,
        normalized_key=normalized_key[:96],
        item_type=item_type,
        noise_flags=noise_flags,
        normalization_confidence=round(confidence, 4),
        normalization_blocked=blocked,
        normalization_reason=blocked_reason,
    )
