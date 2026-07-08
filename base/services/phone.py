"""Normalisation et validation des numéros de téléphone client (E.164)."""
import phonenumbers

# Liste courte : Afrique de l'Ouest + France. Bénin par défaut (premier).
COUNTRIES = [
    {"iso2": "BJ", "dial": "+229", "label": "Bénin",          "example": "01 97 00 00 00"},
    {"iso2": "TG", "dial": "+228", "label": "Togo",           "example": "90 00 00 00"},
    {"iso2": "CI", "dial": "+225", "label": "Côte d'Ivoire",  "example": "01 23 45 67 89"},
    {"iso2": "NG", "dial": "+234", "label": "Nigéria",        "example": "0801 234 5678"},
    {"iso2": "GH", "dial": "+233", "label": "Ghana",          "example": "024 000 0000"},
    {"iso2": "SN", "dial": "+221", "label": "Sénégal",        "example": "70 000 00 00"},
    {"iso2": "BF", "dial": "+226", "label": "Burkina Faso",   "example": "70 00 00 00"},
    {"iso2": "ML", "dial": "+223", "label": "Mali",           "example": "70 00 00 00"},
    {"iso2": "NE", "dial": "+227", "label": "Niger",          "example": "90 00 00 00"},
    {"iso2": "FR", "dial": "+33",  "label": "France",         "example": "06 12 34 56 78"},
]

_VALID_ISO2 = {c["iso2"] for c in COUNTRIES}


def normalize(raw, country_iso2):
    """Retourne le numéro au format E.164, lève ValueError si invalide."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Numéro de téléphone requis")
    region = country_iso2 if country_iso2 in _VALID_ISO2 else "BJ"
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Numéro de téléphone invalide") from exc
    if not phonenumbers.is_valid_number(num):
        raise ValueError("Numéro de téléphone invalide")
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def is_valid(raw, country_iso2):
    try:
        normalize(raw, country_iso2)
        return True
    except ValueError:
        return False
