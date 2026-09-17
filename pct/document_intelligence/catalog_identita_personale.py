"""Il documento d'identità del cliente: la scansione si riconosce dai suoi campi, non da un titolo.

Una carta d'identità (cartacea o elettronica), un passaporto, una patente,
un permesso di soggiorno non hanno un titolo su una riga: l'OCR di una
scansione restituisce etichette sparse — «REPUBBLICA ITALIANA», «CARTA DI
IDENTITÀ / IDENTITY CARD», «COGNOME / SURNAME», «NOME / NAME», «LUOGO E DATA
DI NASCITA», «CITTADINANZA», «SCADENZA», la riga a lettura ottica con «<<» —
spesso con l'apostrofo letto male («IDENTITA'»). Qui l'identità nasce dalla
concordanza fra il tipo di documento e almeno due campi anagrafici, e si
rafforza quando cognome e nome del cliente del fascicolo compaiono nel testo:
allora il catalogo dice «Carta d'identità di Mario Rossi».

Base normativa: art. 35 D.P.R. 445/2000 (documenti di identità e di
riconoscimento equipollenti); D.M. 23 dicembre 2015 (carta d'identità
elettronica, campi e zona a lettura ottica); art. 1 D.P.R. 445/2000 lett. c)
e d) (documento di identità e di riconoscimento).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from pct.fascicoli import TipoDocumento

CARATTERI_ESAMINATI = 4000
FONTE = "normattiva_dpr_445_2000_documentazione_amministrativa"

# (chiave, etichetta, espressione sul testo normalizzato: minuscolo, senza accenti né apostrofi)
TIPI: tuple[tuple[str, str, str], ...] = (
    ("carta_identita", "Carta d'identità", r"\bcarta\s+d\s*i?\s*identita\b|\bcarta\s+identita\b|\bidentity\s+card\b|\bcarta\s+d\s+identit\w*\b|\bc\.?i\.?e\.?\b(?=.*\b(?:cognome|surname|nome|name)\b)"),
    ("passaporto", "Passaporto", r"\bpassaporto\b|\bpassport\b"),
    ("patente", "Patente di guida", r"\bpatente\s+di\s+guida\b|\bpatente\b|\bdriving\s+licen[cs]e\b"),
    ("permesso_soggiorno", "Permesso di soggiorno", r"\bpermesso\s+di\s+soggiorno\b|\bcarta\s+di\s+soggiorno\b|\bresidence\s+permit\b"),
)
# Campi anagrafici e di rilascio che compaiono su un documento di riconoscimento.
CAMPI: tuple[tuple[str, str], ...] = (
    ("cognome", r"\bcognome\b|\bsurname\b"),
    ("nome", r"\bnome\b|\bname\b"),
    ("nascita", r"\bnat[oa]\s+(?:il|a)\b|\bnascita\b|\bbirth\b"),
    ("cittadinanza", r"\bcittadinanza\b|\bnationality\b"),
    ("residenza", r"\bresidenza\b|\bresidente\b|\baddress\b"),
    ("scadenza", r"\bscadenza\b|\bexpiry\b|\bvalid[ao]\s+fino\b|\bvalidita\b"),
    ("statura", r"\bstatura\b|\bheight\b|\bcapelli\b|\bocchi\b|\bsesso\b|\bsex\b"),
    ("emissione", r"\bcomune\s+di\b|\bsindaco\b|\bministero\s+dell\s*interno\b|\brilasciat[oa]\b|\bemissione\b|\bquestura\b|\bprefettura\b"),
    ("codice_fiscale", r"\b[a-z]{6}\d{2}[a-z]\d{2}[a-z]\d{3}[a-z]\b"),
    ("lettura_ottica", r"[a-z0-9<]{5,}<<[a-z0-9<]{5,}"),
)
_AUTORITA = re.compile(r"\brepubblica\s+italiana\b|\bministero\s+dell\s*interno\b|\bcomune\s+di\b|\bquestura\b|\bprefettura\b|\bmotorizzazione\b")
# Un atto che allega o cita il documento d'identità non è il documento d'identità.
_ATTO = re.compile(r"\bprocura\b|\bdeleg[oa]\b|\bricorso\b|\btribunale\b|\bgiudice\b|\bcitazione\b|\bcomparsa\b|\bmemoria\b|\bsi\s+allega\b|\ballego\b|\bcopia\s+(?:del|della)\b|\bdichiara\b")
_NOME_FILE = re.compile(r"^(?:copia\s+|scansione\s+|scan\s+)?(?:carta\s+d\s*i?\s*identita|documento\s+d\s*i?\s*identita|carta\s+identita|c\.?i\.?e|passaporto|patente(?:\s+di\s+guida)?|permesso\s+di\s+soggiorno|tessera\s+sanitaria)(?:\s+(?:fronte|retro|fronte\s+retro|cliente|[a-z]+(?:\s+[a-z]+)?))?(?:\s+\d{1,2})?$")


def normalizza(testo: str) -> str:
    """Minuscolo, senza accenti, apostrofi e simboli: «CARTA D'IDENTITÀ» diventa «carta d identita»."""
    piatto = unicodedata.normalize("NFD", str(testo or "").casefold())
    piatto = "".join(c for c in piatto if unicodedata.category(c) != "Mn")
    piatto = re.sub(r"[’'`´]", " ", piatto)
    piatto = re.sub(r"[^a-z0-9<]+", " ", piatto)
    return re.sub(r"\s+", " ", piatto).strip()


def _cliente_nel_testo(testo_normalizzato: str, cliente: str) -> str:
    """Il nome del cliente se cognome e nome (tutte le parole di almeno tre lettere) compaiono nel testo."""
    parole = [p for p in normalizza(cliente).split() if len(p) >= 3 and not p.isdigit()]
    if len(parole) < 2:
        return ""
    if all(re.search(rf"\b{re.escape(parola)}\b", testo_normalizzato) for parola in parole):
        return " ".join(str(cliente or "").split())
    return ""


def documento_identita_personale(testo: str, *, cliente: str = "") -> dict[str, Any] | None:
    """L'identità di una scansione di documento di riconoscimento, o None."""
    grezzo = str(testo or "")
    if not grezzo.strip():
        return None
    piatto = normalizza(grezzo[:CARATTERI_ESAMINATI])
    if _ATTO.search(piatto[:1500]):
        return None
    tipo = next(((chiave, etichetta) for chiave, etichetta, espressione in TIPI if re.search(espressione, piatto)), None)
    if tipo is None:
        return None
    campi = [chiave for chiave, espressione in CAMPI if re.search(espressione, piatto)]
    if len(campi) < 2:
        return None
    chiave, etichetta = tipo
    autorita = bool(_AUTORITA.search(piatto))
    titolare = _cliente_nel_testo(piatto, cliente)
    confidenza = 96 if len(campi) >= 3 or autorita else 90
    if titolare:
        confidenza = 99
    label = f"{etichetta} di {titolare}" if titolare else etichetta
    evidenza = f"scansione di documento di riconoscimento: tipo «{etichetta.lower()}» e campi {', '.join(campi[:5])}"
    if autorita:
        evidenza += "; autorità emittente"
    evidenza += f"; cognome e nome coincidono con il cliente del fascicolo ({titolare})" if titolare else "; titolare non riscontrato con il cliente del fascicolo"
    evidenza += " (art. 35 D.P.R. 445/2000)"
    return dict(
        label=label, role="documento_identita", section="identita", tipo_documento=TipoDocumento.ALLEGATO,
        confidence=confidenza, evidence=evidenza, deposit_role="allegato", deposit_candidate=True,
        excerpt_pattern=r"carta\s+d.{0,3}identit\w*|identity\s+card|passaporto|passport|patente|permesso\s+di\s+soggiorno|cognome|surname",
        fonte=FONTE, tipo_identita=chiave, titolare=titolare,
    )


def documento_identita_dal_nome(nome_file: str) -> str:
    """L'etichetta del documento di riconoscimento se il nome del file lo dice senza ambiguità («Carta d'identità.PDF»)."""
    base = re.sub(r"\.(?:pdf|jpe?g|png|tiff?|p7m|heic)$", "", str(nome_file or "").strip(), flags=re.IGNORECASE)
    base = re.sub(r"\.(?:pdf|jpe?g|png|tiff?)$", "", base, flags=re.IGNORECASE)
    piatto = normalizza(base)
    if not piatto or not _NOME_FILE.match(piatto):
        return ""
    for chiave, etichetta, espressione in TIPI:
        if re.search(espressione.split("(?=")[0], piatto) or (chiave == "carta_identita" and re.search(r"\b(?:documento\s+d\s*i?\s*identita|c\s?i\s?e)\b", piatto)):
            return etichetta
    if "tessera sanitaria" in piatto:
        return "Tessera sanitaria / codice fiscale"
    return "Documento d'identità"


__all__ = ["CAMPI", "FONTE", "TIPI", "documento_identita_dal_nome", "documento_identita_personale", "normalizza"]
