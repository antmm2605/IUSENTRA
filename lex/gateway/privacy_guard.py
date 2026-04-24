import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CF_RE = re.compile(r"\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b", re.I)
PIVA_RE = re.compile(r"\b\d{11}\b")
PHONE_RE = re.compile(r"(?:(?:\+39)?\s?)?(?:3\d{2}|0\d{1,4})[\s.-]?\d{5,8}")
IBAN_RE = re.compile(r"\bIT\d{2}[A-Z]\d{10}[A-Z0-9]{12}\b", re.I)
RG_RE = re.compile(r"\b(?:R\.?G\.?|RG)\s*(?:n\.?)?\s*\d{1,8}/\d{2,4}\b", re.I)

LEGAL_SENSITIVE_TERMS = {
    "fascicolo",
    "polisweb",
    "pst",
    "pdp",
    "pat",
    "ptt",
    "cliente",
    "controparte",
    "atto",
    "ricorso",
    "comparsa",
    "querela",
    "decreto ingiuntivo",
    "pignoramento",
    "sentenza",
    "udienza",
    "codice fiscale",
    "partita iva",
    "procura alle liti",
    "documento allegato",
    "consulenza legale",
}


@dataclass
class PrivacyResult:
    sensitivity: str
    reasons: list[str]
    redacted_text: str


class PrivacyGuard:
    """
    Classifica il contenuto prima di inviarlo a un provider AI.

    Livelli:
    - public: contenuto generico
    - internal: contenuto operativo ma non personale
    - sensitive: contiene dati legali/personali
    - highly_sensitive: contiene dati identificativi o fascicoli
    """

    def classify_text(self, text: str) -> PrivacyResult:
        reasons: list[str] = []
        lowered = text.lower()

        if EMAIL_RE.search(text):
            reasons.append("email")
        if CF_RE.search(text):
            reasons.append("codice_fiscale")
        if PIVA_RE.search(text):
            reasons.append("partita_iva_o_numero_11_cifre")
        if PHONE_RE.search(text):
            reasons.append("telefono")
        if IBAN_RE.search(text):
            reasons.append("iban")
        if RG_RE.search(text):
            reasons.append("numero_rg")

        for term in LEGAL_SENSITIVE_TERMS:
            if term in lowered:
                reasons.append(f"termine_legale:{term}")

        if any(r in reasons for r in ["codice_fiscale", "iban", "numero_rg"]):
            sensitivity = "highly_sensitive"
        elif reasons:
            sensitivity = "sensitive"
        elif any(term in lowered for term in ["studio", "pratica", "deposito", "scadenza"]):
            sensitivity = "internal"
        else:
            sensitivity = "public"

        return PrivacyResult(
            sensitivity=sensitivity,
            reasons=sorted(set(reasons)),
            redacted_text=self.redact(text),
        )

    def redact(self, text: str) -> str:
        text = EMAIL_RE.sub("[EMAIL_OSCURATA]", text)
        text = CF_RE.sub("[CODICE_FISCALE_OSCURATO]", text)
        text = IBAN_RE.sub("[IBAN_OSCURATO]", text)
        text = RG_RE.sub("[RG_OSCURATO]", text)
        text = PHONE_RE.sub("[TELEFONO_OSCURATO]", text)
        return text

    def can_send_to_external(self, sensitivity: str, allow_external: bool) -> bool:
        if not allow_external:
            return False
        return sensitivity not in {"sensitive", "highly_sensitive"}
