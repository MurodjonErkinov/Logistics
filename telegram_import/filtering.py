import re


FREIGHT_HINT = re.compile(
    r"\b(?:yuk\w*|юк\w*|груз\w*|погруз\w*|загруз\w*|выгруз\w*|тонн\w*|tonna\w*|"
    r"fura\w*|фур\w*|tent\w*|тент\w*|реф\w*|refr\w*|борт\w*|bort\w*|"
    r"gazel\w*|газел\w*|transport\w*|перевоз\w*|достав\w*|рейс\w*|"
    r"karzinka\w*|корзин\w*|sement\w*|цемент\w*|пустой|пустые)\b",
    re.IGNORECASE,
)
ROUTE_HINT = re.compile(r"[→➡➜➝⏩]|->|=>|[^\W\d_]{2,}\s*[-–—]\s*[^\W\d_]{2,}")
WEIGHT_HINT = re.compile(r"\d+(?:[.,]\d+)?\s*(?:т\b|t\b|kg\b|кг\b|тонн|tonn)", re.IGNORECASE)


def looks_like_load(text):
    return bool(FREIGHT_HINT.search(text) or ROUTE_HINT.search(text) or WEIGHT_HINT.search(text))
