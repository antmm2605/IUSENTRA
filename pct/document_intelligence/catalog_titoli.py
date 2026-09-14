"""Identità dell'atto dal suo titolo, prima di qualunque parola nel corpo.

Un atto giudiziario dichiara che cosa è nella prima riga: «RICORSO PER DECRETO
INGIUNTIVO», «COMPARSA DI COSTITUZIONE E RISPOSTA», «ATTO DI PRECETTO». Il corpo,
invece, cita di tutto: un ricorso dice quanto contributo unificato è dovuto, una
comparsa racconta l'atto di citazione ricevuto, un'istanza chiede un'ordinanza.
Cercare parole chiave nel corpo produce esattamente gli errori visti il
14/09/2026: un ricorso catalogato come «contributo unificato», un'istanza di
rinvio come «verbale», un'istanza ex art. 186-ter come «ordinanza».

Qui la regola è una sola: il **titolo dell'atto sulla propria riga** più **un
segnale di conferma nel corpo** che appartiene a quel tipo di atto (la formula
«INGIUNGE» per il decreto ingiuntivo, «si costituisce» per la comparsa,
«INTIMA … PRECETTO» per il precetto, «HO NOTIFICATO» per la relata). Il titolo
senza conferma non basta; la conferma senza titolo nemmeno. Ogni regola cita
la norma che definisce l'atto, così la catalogazione resta verificabile.

Le buste vengono prima degli atti che contengono: un messaggio di posta che
allega una sentenza è un messaggio, come già vale per le ricevute PEC.
"""

from __future__ import annotations

import re
from typing import Any

from pct.fascicoli import TipoDocumento

# Il titolo sta nelle prime righe: oltre questa soglia non è più un titolo.
RIGHE_TITOLO = 14
CARATTERI_TITOLO = 2400
LUNGHEZZA_MASSIMA_RIGA_TITOLO = 120
# Un titolo spezzato dall'OCR su due righe va comunque letto: le prime tre
# righe unite sono l'unico posto in cui si cerca un titolo non allineato.
RIGHE_TITOLO_UNITE = 3

_CODICE_FISCALE = r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b"
_INTESTAZIONE_MESSAGGIO = re.compile(r"(?im)^\s*(?:da|from|mittente)\s*:")
_OGGETTO_MESSAGGIO = re.compile(r"(?im)^\s*(?:oggetto|subject)\s*:\s*(.+)$")
_DESTINATARIO_MESSAGGIO = re.compile(r"(?im)^\s*(?:a|to|per|destinatari[oi])\s*:")


from .titoli import REGOLE_TITOLO, RegolaTitolo  # le regole vivono per area

# Ricevute dei depositi telematici: la specifica DGSIA descrive i messaggi che
# il PCT restituisce (esito controlli automatici, accettazione/rifiuto della
# cancelleria). Si riconoscono dall'oggetto del messaggio, non dal corpo.
_RICEVUTE_DEPOSITO: tuple[tuple[str, str, str], ...] = (
    (r"esito\s+controlli\s+automatici", "Ricevuta PCT — esito controlli automatici", "esito controlli automatici del deposito telematico"),
    (r"accettazione\s+(?:del\s+)?deposito|deposito\s+accettato|accettato\s+dalla\s+cancelleria", "Ricevuta PCT — accettazione della cancelleria", "accettazione del deposito da parte della cancelleria"),
    (r"rifiuto\s+(?:del\s+)?deposito|deposito\s+rifiutato|rifiutato\s+dalla\s+cancelleria", "Ricevuta PCT — rifiuto della cancelleria", "rifiuto del deposito da parte della cancelleria"),
    (r"ricevuta\s+di\s+deposito|deposito\s+telematico\s+-", "Ricevuta PCT — deposito telematico", "messaggio del deposito telematico"),
)
_CONFERMA_DEPOSITO = re.compile(r"\bdeposito\b|\bgiustiziacert\b|\bptel\b|\bcancelleria\b|\bbusta\b", re.IGNORECASE)


def _righe_titolo(testo: str) -> list[str]:
    righe: list[str] = []
    for grezza in str(testo or "")[:CARATTERI_TITOLO].splitlines():
        riga = re.sub(r"\s+", " ", grezza).strip(" \t-–—•·:;")
        if riga:
            righe.append(riga)
        if len(righe) >= RIGHE_TITOLO:
            break
    return righe


def _normalizza(testo: str) -> str:
    return re.sub(r"\s+", " ", str(testo or "")).casefold()


def _titolo_trovato(regola: RegolaTitolo, righe: list[str]) -> str:
    """La riga del titolo che soddisfa la regola, se esiste.

    Le comunicazioni portano il titolo nella riga «Oggetto:», come ogni lettera;
    gli atti lo portano su una riga propria. Un titolo spezzato dall'OCR su due
    o tre righe si riconosce unendo le prime righe, ma sempre per intero: un
    confronto per prefisso scambierebbe «Reclamo al Garante» per un reclamo
    cautelare.
    """
    prefisso = r"(?:(?:oggetto|subject)\s*:\s*)?" if regola.section == "comunicazioni" else ""
    modello = re.compile(rf"^{prefisso}(?:{regola.titolo})\s*$", re.IGNORECASE)
    for riga in righe:
        if len(riga) <= LUNGHEZZA_MASSIMA_RIGA_TITOLO and modello.match(riga):
            return riga
    for quante in (2, RIGHE_TITOLO_UNITE):
        unite = " ".join(righe[:quante])
        if len(unite) <= LUNGHEZZA_MASSIMA_RIGA_TITOLO * 2 and modello.match(unite):
            return unite
    return ""


def _esito(regola: RegolaTitolo, riga: str, *, label: str | None = None) -> dict[str, Any]:
    return {
        "label": label or regola.label,
        "role": regola.role,
        "section": regola.section,
        "tipo_documento": regola.tipo,
        "confidence": regola.confidence,
        "evidence": f"titolo dell'atto e conferma nel testo: {regola.evidence}",
        "deposit_role": regola.deposit_role,
        "deposit_candidate": regola.deposit_candidate,
        "excerpt_pattern": re.escape(riga) if riga else regola.titolo,
        "fonte": regola.fonte,
    }


def _etichetta_specifica(regola: RegolaTitolo, riga: str) -> str:
    """Il titolo stesso quando è più preciso dell'etichetta generica."""
    if regola.id in {"istanza", "contratto"} and riga:
        titolo = " ".join(riga.split())
        if len(titolo) <= 90:
            return titolo[:1].upper() + titolo[1:].lower() if titolo.isupper() else titolo
    if regola.id == "memoria_171ter":
        numero = re.search(r"\bn\.?\s*([123])\b", riga, re.IGNORECASE)
        if numero:
            return f"Memoria integrativa ex art. 171-ter, n. {numero.group(1)}, c.p.c."
    return regola.label


def identita_messaggio(testo: str) -> dict[str, Any] | None:
    """Ricevute di deposito PCT e messaggi di posta: la busta prima del contenuto."""
    grezzo = str(testo or "")
    testa = grezzo[:1500]
    oggetto = _OGGETTO_MESSAGGIO.search(testa)
    ha_intestazione = bool(_INTESTAZIONE_MESSAGGIO.search(testa))
    corpo = _normalizza(grezzo[:12000])

    # Le ricevute PCT si riconoscono dall'oggetto, anche quando l'estratto non
    # riporta il mittente: la formula è quella della specifica ministeriale.
    oggetto_testo = _normalizza(oggetto.group(1) if oggetto else testa[:300])
    for formula, label, evidenza in _RICEVUTE_DEPOSITO:
        if re.search(formula, oggetto_testo) and _CONFERMA_DEPOSITO.search(corpo):
            return {
                "label": label, "role": "ricevuta_deposito", "section": "comunicazioni",
                "tipo_documento": TipoDocumento.COMUNICAZIONE, "confidence": 97,
                "evidence": f"oggetto del messaggio e conferma nel testo: {evidenza} (Specifiche tecniche D.M. 44/2011)",
                "deposit_role": "fuori_busta", "deposit_candidate": False,
                "excerpt_pattern": formula, "fonte": "pst_specifiche_tecniche_pct",
            }

    if ha_intestazione and oggetto and _DESTINATARIO_MESSAGGIO.search(testa):
        certificata = bool(re.search(r"\bpec\b|posta\s+(?:elettronica\s+)?certificata|postacert", corpo))
        return {
            "label": "Messaggio PEC" if certificata else "Messaggio di posta elettronica",
            "role": "corrispondenza", "section": "comunicazioni",
            "tipo_documento": TipoDocumento.COMUNICAZIONE, "confidence": 95,
            "evidence": "intestazioni del messaggio (mittente, destinatario, oggetto)" + ("; indirizzi di posta certificata" if certificata else ""),
            "deposit_role": "fuori_busta", "deposit_candidate": False,
            "excerpt_pattern": r"(?:oggetto|subject)\s*:", "fonte": "normattiva_dpr_68_2005_pec" if certificata else "catalog_agid_metadati",
        }
    return None


def identita_dal_titolo(testo: str) -> dict[str, Any] | None:
    """Identità dell'atto dal titolo in testa e da un segnale di conferma nel corpo."""
    grezzo = str(testo or "")
    if not grezzo.strip():
        return None
    messaggio = identita_messaggio(grezzo)
    if messaggio is not None:
        return messaggio
    righe = _righe_titolo(grezzo)
    if not righe:
        return None
    corpo = _normalizza(grezzo[:12000])
    for regola in REGOLE_TITOLO:
        riga = _titolo_trovato(regola, righe)
        if not riga:
            continue
        conferma = re.compile(regola.conferma, re.IGNORECASE)
        corpo_da_verificare = grezzo[:12000] if regola.id == "tessera_sanitaria" else corpo
        if not conferma.search(corpo_da_verificare):
            continue
        return _esito(regola, riga, label=_etichetta_specifica(regola, riga))
    return None


__all__ = ["REGOLE_TITOLO", "RegolaTitolo", "identita_dal_titolo", "identita_messaggio"]
