"""Esito di una sentenza letto dal dispositivo e ragioni della decisione lette dalla motivazione.

Il dispositivo (dopo «P.Q.M.») dice che cosa ha deciso il giudice: accoglimento, rigetto, accoglimento parziale,
inammissibilità, improcedibilità, estinzione, cessazione della materia del contendere, incompetenza o difetto di
giurisdizione; e come ha regolato le spese (condanna, compensazione, distrazione: artt. 91, 92 e 93 c.p.c.). Le
ragioni si cercano nella motivazione (art. 132, n. 4, c.p.c.) con frasi tipiche, citate con la loro posizione: sono
indizi per l'avvocato, non conclusioni.
"""

from __future__ import annotations

import re
from typing import Any

_PQM = re.compile(r"\b(?:P\.?\s?Q\.?\s?M\b\.?|PER\s+QUESTI\s+MOTIVI\b)", re.IGNORECASE)
_IMPORTO = r"(?:€|euro|eur)\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})(?!\d)(?!,\d)"
# Fine del dispositivo: la firma su una riga breve o «Città, data IL GIUDICE»; non «Il Giudice del Lavoro, definitivamente pronunciando».
_FIRMA = re.compile(r"\n\s*(?:Il\s+giudice|Il\s+presidente|Così\s+deciso)\b(?!\s+del\s+lavoro)[^\n]{0,60}(?:\n|$)"
                    r"|\b[A-Z][a-zà]+,\s*\d{1,2}[./]\d{1,2}[./]\d{4}\s+IL\s+GIUDICE", re.IGNORECASE)

# Ordine: dalle pronunce di rito a quelle di merito. La prima che compare nel dispositivo prevale.
_ESITI = (
    ("difetto_giurisdizione", r"\bdifetto\s+di\s+giurisdizione\b|\bdichiara\s+(?:la\s+)?(?:propria\s+)?carenza\s+di\s+giurisdizione"),
    ("incompetenza", r"\bdichiara\s+(?:la\s+)?(?:propria\s+)?incompetenza\b"),
    ("inammissibile", r"\bdichiara\s+(?:l['’]\s?)?inammissibil"),
    ("improcedibile", r"\bdichiara\s+(?:l['’]\s?)?improcedibil"),
    ("estinzione", r"\bdichiara\s+(?:l['’]\s?)?estint"),
    ("cessata_materia", r"\bcessata\s+(?:la\s+)?materia\s+del\s+contendere\b"),
    ("accoglimento_parziale", r"\baccoglie\s+(?:in\s+parte|parzialmente)\b|\bin\s+parziale\s+accoglimento\b"),
    ("rigetto", r"\b(?:rigetta|respinge)\b"),
    ("accoglimento", r"\baccoglie\b|\b(?:dichiara|accerta)\s+il\s+diritto\b"
                     r"|\bcondanna\s+(?:il|la|l['’])\s?(?:parte\s+)?(?:convenut|resistent|amministrazione|ministero|opposto|debitore)"),
)
_MASSIMO_DISPOSITIVO = 6000
# Le frasi del dispositivo finiscono con «;» o con un punto seguito da spazio (non i punti delle cifre, «1.234,00»).
_FINE_FRASE = re.compile(r";|\.(?=\s|$)")

_ETICHETTE = {
    "difetto_giurisdizione": "Difetto di giurisdizione", "incompetenza": "Incompetenza", "inammissibile": "Domanda o impugnazione inammissibile",
    "improcedibile": "Improcedibile", "estinzione": "Processo estinto", "cessata_materia": "Cessata materia del contendere",
    "accoglimento_parziale": "Accoglimento parziale", "rigetto": "Rigetto", "accoglimento": "Accoglimento",
}
# Ragioni ricorrenti di una decisione sfavorevole: chiave, frase cercata, che cosa significa per l'avvocato.
_RAGIONI = (
    ("prescrizione", r"\bprescri(?:tt|zion)", "Il diritto è stato ritenuto prescritto"),
    ("decadenza", r"\bdecadut|\bdecadenza\b", "È stata ritenuta maturata una decadenza"),
    ("onere_prova", r"\bnon\s+(?:è\s+stat[oa]\s+)?provat|\bonere\s+(?:della\s+)?prova\b|\bmancata\s+prova\b|\bdifetto\s+di\s+prova\b", "La domanda è stata ritenuta non provata"),
    ("legittimazione", r"\bdifetto\s+di\s+legittimazione\b|\bcarenza\s+di\s+legittimazione\b", "Difetto di legittimazione"),
    ("tardivita", r"\btardiv", "Atto o domanda ritenuti tardivi"),
    ("genericita", r"\bgeneric[ihoa]\b|\bindetermina", "Domanda o motivi ritenuti generici"),
    ("infondatezza", r"\binfondat", "Domanda ritenuta infondata nel merito"),
)


def dispositivo(testo: str) -> str:
    """Il testo dopo l'ultimo «P.Q.M.» (o «per questi motivi»), senza la firma; vuoto se non c'è."""
    trovati = list(_PQM.finditer(testo or ""))
    if not trovati:
        return ""
    # Il dispositivo è breve: se la firma non si trova, non diventa il resto del documento (allegati, note, copie).
    parte = testo[trovati[-1].end():][:_MASSIMO_DISPOSITIVO]
    fine = _FIRMA.search(parte, 40)
    return re.sub(r"\s+", " ", parte[: fine.start()] if fine else parte).strip(" .:;,")


def _importo(frase: str) -> str:
    m = re.search(_IMPORTO, frase, re.IGNORECASE)
    return m.group(1) if m else ""


def spese(dispositivo_testo: str) -> dict[str, Any]:
    testo = (dispositivo_testo or "")[:_MASSIMO_DISPOSITIVO]
    voce: dict[str, Any] = {"regolazione": "non_indicata", "importo": "", "distrazione": False, "frase": ""}
    # Frase per frase, con espressioni senza alternative sovrapposte: tempo lineare anche su testi anomali.
    frasi = [f.strip() for f in _FINE_FRASE.split(testo) if f.strip()]
    compensazione = next((f for f in frasi if re.search(r"\bcompens[ae]", f, re.IGNORECASE)), "")
    if compensazione:
        parziale = bool(re.search(r"\b(?:in\s+parte|per\s+(?:la\s+)?(?:metà|un\s+terzo|\d+/\d+))", compensazione, re.IGNORECASE))
        voce.update(regolazione="compensazione_parziale" if parziale else "compensazione", frase=compensazione)
    condanna = next((f for f in frasi if re.search(r"\bcondanna\b.*?\bspese\b", f, re.IGNORECASE | re.DOTALL)), "")
    if condanna:
        voce.update(regolazione="condanna" if voce["regolazione"] == "non_indicata" else voce["regolazione"], frase=condanna, importo=_importo(condanna))
    voce["distrazione"] = bool(re.search(r"\bdistra(?:e|zione|tt)|\bantistatari", testo, re.IGNORECASE))
    return voce


def ragioni(testo: str, esito: str) -> list[dict[str, Any]]:
    """Frasi della motivazione che spiegano un esito sfavorevole, con la loro posizione nel testo."""
    if esito not in {"rigetto", "accoglimento_parziale", "inammissibile", "improcedibile"}:
        return []
    motivazione = _PQM.split(testo or "")[0]
    trovate = []
    for chiave, schema, significato in _RAGIONI:
        m = re.search(schema, motivazione, re.IGNORECASE)
        if m:
            inizio = max(0, motivazione.rfind(".", 0, m.start()) + 1)
            fine = motivazione.find(".", m.end())
            trovate.append({"ragione": chiave, "significato": significato, "posizione": m.start(),
                            "frase": re.sub(r"\s+", " ", motivazione[inizio: fine + 1 if fine > 0 else m.end() + 200]).strip()[:400]})
    return sorted(trovate, key=lambda voce: voce["posizione"])


def esito_sentenza(testo: str, *, nostra_parte: str = "") -> dict[str, Any]:
    """Esito, spese e ragioni; ``nostra_parte`` = «attore»/«ricorrente»/«appellante» oppure «convenuto»/«resistente»/«appellato»."""
    disp = dispositivo(testo)
    codice = next((chiave for chiave, schema in _ESITI if re.search(schema, disp, re.IGNORECASE)), "non_riconosciuto")
    promotore = (nostra_parte or "").lower() in {"attore", "ricorrente", "appellante", "opponente", "reclamante"}
    difensore = (nostra_parte or "").lower() in {"convenuto", "resistente", "appellato", "opposto", "reclamato"}
    per_noi = "da_valutare"
    if codice in {"accoglimento", "rigetto", "accoglimento_parziale"} and (promotore or difensore):
        favorevole = (codice == "accoglimento") == promotore if codice != "accoglimento_parziale" else None
        per_noi = "parziale" if favorevole is None else ("favorevole" if favorevole else "sfavorevole")
    elif codice in {"inammissibile", "improcedibile", "estinzione", "incompetenza", "difetto_giurisdizione"} and promotore:
        per_noi = "sfavorevole"
    return {
        "esito": codice,
        "etichetta": _ETICHETTE.get(codice, "Esito non riconosciuto: leggere il dispositivo"),
        "per_il_cliente": per_noi,
        "dispositivo": disp[:1500],
        "spese": spese(disp),
        "ragioni": ragioni(testo, codice if per_noi != "favorevole" else ""),
        "fonti": ["art. 132 c.p.c.", "artt. 91, 92 e 93 c.p.c."],
    }
