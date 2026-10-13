"""Os 9 rótulos válidos do desafio (mesma ordem de evaluate.py)."""

LABELS = (
    "finance", "automotive", "health", "travel", "technology",
    "food_beverage", "fashion", "entertainment", "other",
)
_LABEL_SET = frozenset(LABELS)


def is_valid_label(value):
    return isinstance(value, str) and value in _LABEL_SET
