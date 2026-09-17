"""L'ancoraggio: una data è un fatto solo se il testo dice che cosa è.

«All'udienza del 10/03/2026», «entro il 31/12/2025», «notificato il 15/08/2025»,
«ricevuta di avvenuta consegna … 12/03/2026 ore 10:15»: la parola che precede
la data (o la segue da vicino) le dà il campo. Una data senza ancora — un
numero in una tabella, una data qualunque in mezzo al testo — non è un fatto e
non si propone a nessuno. Le date di nascita, dei documenti d'identità, dei
protocolli, delle fatture e delle versioni sono ancore negative: la data resta
dov'è.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FINESTRA_PRIMA = 110
FINESTRA_DOPO = 45
FINESTRA_NEGATIVA = 30

# (campo, espressione sul testo che precede la data). L'ordine conta solo a parità di distanza.
ANCORE: tuple[tuple[str, str], ...] = (
    ("udienza", r"udienz[ae]|comparizion[ei]|camera di consiglio|discussion[ei]|rinvi[ao]t?[ao]?|trattazion[ei]|fissa(?:ta|to|re)?"),
    ("termine", r"termin[ei]|entro (?:il|e non oltre|la data)|non oltre|scad(?:e|enza|ono)|perentori[oa]|decorren[zt][ae]|a decorrere"),
    ("costituzione", r"costituzion[ei]|costituirsi"),
    ("deposito", r"deposit(?:o|ato|ata|ata il|are)|data (?:di )?deposito|depositat[oa]"),
    ("notifica", r"notificat[oa]|notifica(?:zione)?|data (?:di )?notifica|notificare"),
    ("accettazione", r"accettazione|accettat[oa]"),
    ("consegna", r"avvenuta consegna|consegna|consegnat[oa]"),
    ("comunicazione", r"comunicazion[ei]|comunicat[oa]|biglietto di cancelleria"),
    ("provvedimento", r"sentenza|ordinanza|decreto|provvedimento|emess[oa]|pubblicat[oa]|pronunciat[oa]|depositata in cancelleria"),
    ("data_atto", r"(?:l[iì]'?|addì|add[iì]'?)\s*,?\s*$"),
)
_ANCORE_RE = tuple((campo, re.compile(rf"(?:{espressione})", re.IGNORECASE)) for campo, espressione in ANCORE)
_NEGATIVE = re.compile(
    r"nat[oa]\s+(?:a|il|in)|nascita|rilasciat[oa]|scadenz[ae]\s+(?:del documento|carta|passaporto|patente)|valid[oa]\s+fino|"
    r"documento\s+d'identit|carta\s+d'identit|passaporto|patente|codice\s+fiscale|prot(?:\.|ocollo)|fattura\s+n|parcella\s+n|"
    r"vers(?:\.|ione)|iban|c\.?c\.?\s*n|dal\s+\d{1,2}[./]\d{1,2}[./]\d{2,4}\s+al\s*$|"
    # la data di una legge o di un decreto normativo non è una data del fascicolo
    r"(?:legge|l\.|d\.?\s?lgs\.?|d\.?\s?p\.?\s?r\.?|d\.?\s?m\.?|d\.?\s?l\.|d\.?\s?p\.?\s?c\.?\s?m\.?|decreto\s+(?:legislativo|ministeriale|legge))\s*(?:n\.?\s*\d+(?:/\d+)?\s*(?:del)?\s*)?$",
    re.IGNORECASE,
)
_ORA = re.compile(r"(?:ore|alle ore|alle|h\.?)\s*(?P<ora>[01]?\d|2[0-3])\s*[:.,]\s*(?P<minuti>[0-5]\d)", re.IGNORECASE)
# Fine di una frase: punto seguito da spazio e da una maiuscola. Le abbreviazioni
# («art. 3-bis», «Prot. n.», «L. 53/1994») non chiudono la frase: dopo il loro
# punto non c'è una maiuscola d'inizio frase o prima c'è una sola lettera.
_FINE_FRASE = re.compile(r"(?<![A-Za-z])(?<!\bart)(?<!\bn)[^\s.][.!?]\s+(?=[A-ZÀ-Ý])")


def inizio_frase(testo: str, inizio: int, limite: int = 0) -> int:
    """L'inizio della frase in cui sta il token: un'ancora non attraversa il punto fermo."""
    finestra = testo[max(0, limite):inizio]
    ultimo = 0
    for match in _FINE_FRASE.finditer(finestra):
        ultimo = match.end()
    return max(0, limite) + ultimo


@dataclass(frozen=True, slots=True)
class Ancora:
    campo: str
    testo: str
    distanza: int


def _spazi(testo: str) -> str:
    return " ".join(str(testo or "").split())


def ancora_per(testo: str, inizio: int, fine: int, *, limite: int = 0, limite_dopo: int | None = None) -> Ancora | None:
    """L'ancora più vicina alla data che sta in testo[inizio:fine]; None se la data non ha campo.

    `limite` è la fine della data precedente e `limite_dopo` l'inizio della
    successiva: un'ancora vale per la prima data che la segue, non per una
    sfilza di date in tabella; l'ancora che segue la data vale solo sulla
    stessa riga e prima del punto.
    """
    prima = testo[max(0, inizio - FINESTRA_PRIMA, limite, inizio_frase(testo, inizio, limite)):inizio]
    if _NEGATIVE.search(prima[-FINESTRA_NEGATIVA:]):
        return None
    if re.search(r"(?:contratto|rapporto|servizio|assunzione).{0,100}decorrenza\s+(?:dal|da|del)\s*$", prima, re.IGNORECASE | re.DOTALL):
        return None
    if motivo_non_processuale(testo, inizio, fine):
        return None
    migliore: Ancora | None = None
    for campo, espressione in _ANCORE_RE:
        for match in espressione.finditer(prima):
            distanza = len(prima) - match.end()
            if migliore is None or distanza < migliore.distanza:
                migliore = Ancora(campo=campo, testo=_spazi(match.group(0)), distanza=distanza)
    if migliore is not None:
        return migliore
    dopo = testo[fine:min(fine + FINESTRA_DOPO, limite_dopo if limite_dopo is not None else len(testo))]
    dopo = re.split(r"[\n.;]", dopo, maxsplit=1)[0]
    for campo, espressione in _ANCORE_RE:
        if campo == "data_atto":
            continue
        match = espressione.search(dopo)
        if match and not _NEGATIVE.search(dopo[:match.start()]):
            distanza = match.start()
            if migliore is None or distanza < migliore.distanza:
                migliore = Ancora(campo=campo, testo=_spazi(match.group(0)), distanza=distanza)
    return migliore


def ora_vicina(testo: str, fine: int) -> str:
    """L'orario scritto subito dopo la data («ore 9.30», «alle 10:15»), in forma HH:MM."""
    match = _ORA.search(testo[fine:fine + FINESTRA_DOPO])
    if not match:
        return ""
    return f"{int(match.group('ora')):02d}:{match.group('minuti')}"


def brano(testo: str, inizio: int, fine: int, *, raggio: int = 90) -> str:
    return _spazi(testo[max(0, inizio - raggio):min(len(testo), fine + raggio)])


__all__ = ["ANCORE", "Ancora", "ancora_per", "brano", "inizio_frase", "ora_vicina"]


def motivo_non_processuale(testo: str, inizio: int, fine: int) -> str:
    """Esclusione esplicita, verificabile anche sul brano storico salvato."""
    prima = testo[max(0, inizio - 160):inizio]
    if re.search(r"(?:contratto|rapporto|servizio|assunzione).{0,120}decorrenza\s+(?:dal|da|del)\s*$", prima, re.I | re.S):
        return "decorrenza del rapporto di lavoro, non termine processuale"
    if re.search(r"(?:termine|fine)\s+(?:delle?\s+)?(?:attività didattiche|anno scolastico).{0,25}$", prima, re.I | re.S):
        return "periodo di servizio scolastico, non termine processuale"
    dopo = testo[fine:fine + 130]
    vicino = prima + testo[inizio:fine] + dopo
    if re.search(r"decorrenza\s+dal\s*$", prima, re.I) and re.search(r"cessazione|ore settimanali|tipologia posto|lezione presso", vicino, re.I):
        return "decorrenza del rapporto di lavoro, non termine processuale"
    if re.search(r"supplenza|anno scolastico|attivit[àa]\s+(?:di\s+)?didattiche|costituzione della Carta", vicino, re.I):
        if re.search(r"servizio|supplenza|costituzione della Carta", vicino, re.I):
            return "periodo di servizio scolastico o beneficio, non termine processuale"
    if re.search(r"cronol\.?(?:ogico)?\s*\d+/\d+\s+del\s*$", prima, re.I):
        return "data di registrazione del provvedimento, non data di udienza"
    if re.search(r"(?:Messina|Palmi|Vicenza|Roma|Milano|Napoli|Torino|Bologna|Firenze|Reggio Calabria),?\s*(?:l[iì]\s*)?$", prima, re.I) and re.match(r"\s*(?:Il|La)\s+Giudice", dopo, re.I):
        return "data di redazione del provvedimento, non termine processuale"
    if re.search(r"EMISSIONE/ISSUING|SCADENZA/EXPIRY|HOLDER.?S.?SIGNATURE", vicino, re.I):
        return "data del documento di identità, non termine processuale"
    if re.search(r"Corte di Giustizia\s*$", prima, re.I):
        return "data di un precedente giurisprudenziale citato"
    return ""


def esclusione_data_salvata(testo: str, valore: str) -> str:
    from legal_ocr.formulario.date import trova_date
    from pct.registro_letture.verifica_date import interpreta_data

    data = interpreta_data(valore.split("T")[0])
    occorrenze = [d for d in trova_date(testo) if d.data == data]
    motivi = [motivo_non_processuale(testo, d.inizio, d.fine) for d in occorrenze]
    return motivi[0] if motivi and all(motivi) else ""
