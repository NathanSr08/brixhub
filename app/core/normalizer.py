import re
import unicodedata

DIMINUTIFS = {
    "alex": ["alexandre", "alexis"],
    "alexandre": ["alex"],
    "antoine": ["toine", "titouan"],
    "christophe": ["chris"],
    "chris": ["christophe", "christian"],
    "jean": ["jeannot"],
    "nicolas": ["nico"],
    "nico": ["nicolas"],
    "sebastien": ["seb"],
    "seb": ["sebastien"],
    "thomas": ["tom"],
    "tom": ["thomas"],
    "maxime": ["max"],
    "max": ["maxime", "maximilien"],
    "benjamin": ["ben"],
    "ben": ["benjamin"],
    "guillaume": ["guigui"],
    "edouard": ["eddy", "ed"],
    "francois": ["fanfan"],
    "stephane": ["steph"],
    "steph": ["stephane"]
}

def strip_accents(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")

def normalize_name(text: str) -> str:
    if not text:
        return ""
    text = strip_accents(text.strip().lower())
    text = re.sub(r"['\-_\.,]", " ", text)
    tokens = [t for t in text.split() if t]
    clean_tokens = [t for t in tokens if t not in ["de", "du", "des", "le", "la", "les", "van", "von", "d"]]
    return " ".join(clean_tokens) if clean_tokens else " ".join(tokens)

def normalize_phone(phone: str) -> list[str]:
    if not phone:
        return []
    digits = re.sub(r"\D", "", phone.strip())
    if not digits:
        return []
    
    variantes = {digits}
    if digits.startswith("33") and len(digits) == 11:
        national = "0" + digits[2:]
        court = digits[2:]
        variantes.update([national, digits, court])
    elif digits.startswith("0") and len(digits) == 10:
        inter = "33" + digits[1:]
        court = digits[1:]
        variantes.update([digits, inter, court])
    elif len(digits) == 9 and digits.startswith(("6", "7", "1", "2", "3", "4", "5", "9")):
        national = "0" + digits
        inter = "33" + digits
        variantes.update([national, inter, digits])
        
    return [v for v in variantes if len(v) >= 6]

def get_name_variants(name: str) -> list[str]:
    norm = normalize_name(name)
    variants = {norm}
    for t in norm.split():
        variants.add(t)
        if t in DIMINUTIFS:
            variants.update(DIMINUTIFS[t])
    return [v for v in variants if v]
