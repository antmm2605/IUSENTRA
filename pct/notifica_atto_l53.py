"""La notifica a mezzo PEC riferita all'atto notificato: quale atto, a chi, quando, con quali ricevute.

Una notifica in proprio dell'avvocato (art. 3-bis L. 53/1994) è un messaggio PEC con oggetto
«notificazione ai sensi della legge n. 53 del 1994» (comma 4) e con la relata nel corpo o in un file
firmato (comma 5), che elenca gli atti notificati (lett. b) e i destinatari con l'indirizzo dei
pubblici elenchi (lett. c-d). La notifica si perfeziona per il destinatario con la ricevuta di
avvenuta consegna (comma 3); le ricevute di accettazione e consegna portano lo stesso oggetto,
quindi lo stesso identificativo della spedizione (D.P.R. 68/2005, art. 6).

Regole (collaudo dei fascicoli reali del 10/11/2026, difetti G-3 e G-5):

1. **La prova è dell'atto elencato nella relata**, non di qualunque atto del fascicolo: la relata dice
   «I seguenti atti: A) - Sentenza (File: Sentenza.PDF)». Il file si collega al documento del
   fascicolo con lo stesso nome (o la sua copia «(originale notificato)»).
2. **Le ricevute si raggruppano per spedizione** (identificativo «Notifica_ID» dell'oggetto): la
   consegna della notifica X non prova la notifica Y.
3. **Una ricevuta PEC senza oggetto di notificazione non è una notifica** (una diffida, una richiesta
   di pagamento, una comunicazione): art. 3-bis, comma 4, L. 53/1994.
4. **La notifica non precede l'atto**: una spedizione datata prima della data dell'atto non può
   riguardarlo.

Modulo puro: riceve i testi già letti (indice documentale) e non scrive nulla.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import PurePath
from typing import Iterable, Mapping

NORMA = "art. 3-bis L. 53/1994"

# Oggetto della notificazione in proprio (art. 3-bis, comma 4, L. 53/1994).
NOTIFICAZIONE_L53 = re.compile(
    r"notificazion\w*\s+ai\s+sensi\s+della\s+l(?:egge|\.)\s*(?:n\.?\s*)?53|\bl(?:egge|\.)\s*(?:n\.?\s*)?53\s*(?:/|del|-|_)\s*(?:19)?94",
    re.IGNORECASE,
)
_ID_SPEDIZIONE = re.compile(r"Notifica[_ ]?ID\s*[:_]\s*([A-Za-z0-9]{4,})", re.IGNORECASE)
_OGGETTO = re.compile(r"(?im)^\s*Oggetto:\s*(.+)$")
_DATA_INTESTAZIONE = re.compile(r"(?im)^\s*Data:\s*(.+)$")
_DATA_IT = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
_DATA_RFC = re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})\b", re.IGNORECASE)
_MESI = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
_GIORNO_CONSEGNA = re.compile(r"Il\s+giorno\s+(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE)
_HO_NOTIFICATO = re.compile(r"\bHO\s+NOTIFICATO\s+A\b", re.IGNORECASE)
_SEGUENTI_ATTI = re.compile(r"\bI\s+seguenti\s+atti\s*:", re.IGNORECASE)
_FINE_ATTI = re.compile(r"\b(?:DICHIARO|ATTESTO)\b")
_VOCE_ATTO = re.compile(r"(?m)^\s*[A-Z]\)\s*-\s*(?P<titolo>.+?)\s*\(\s*File\s*:\s*(?P<file>[^)]+?)\s*\)")
_VOCE_DESTINATARIO = re.compile(r"(?m)^\s*\d+\)\s*-\s*(?P<nome>.+?)(?=\s+C\.?\s*F\.?\s*[:.]|\s+in\s+persona|\s+mediante|\s*$)")
_COPIA_NOTIFICATA = re.compile(r"\s*\((?:originale|copia)\s+notificat[ao]\)\s*", re.IGNORECASE)


def _piano(testo: str) -> str:
    testo = unicodedata.normalize("NFKD", str(testo or ""))
    return "".join(c for c in testo if not unicodedata.combining(c))


def _data_iso(testo: str) -> str:
    testo = str(testo or "")
    trovata = _DATA_IT.search(testo)
    if trovata:
        giorno, mese, anno = (int(x) for x in trovata.groups())
    else:
        trovata = _DATA_RFC.search(testo)
        if not trovata:
            return ""
        giorno, mese, anno = int(trovata.group(1)), _MESI[trovata.group(2)[:3].lower()], int(trovata.group(3))
    try:
        return date(anno, mese, giorno).isoformat()
    except ValueError:
        return ""


def chiave_nome(nome: str) -> str:
    """Il nome del file senza estensione, senza «(originale notificato)», minuscolo e senza segni."""
    stelo = PurePath(str(nome or "").strip()).name
    for _ in range(2):  # «x.pdf.p7m»
        if re.search(r"\.(pdf|p7m|doc|docx|eml|xml|tsd|odt|rtf|txt|jpe?g|png|tiff?)$", stelo, re.IGNORECASE):
            stelo = stelo.rsplit(".", 1)[0]
    stelo = _COPIA_NOTIFICATA.sub(" ", stelo)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _piano(stelo).lower()).split())


def e_notificazione_l53(testo: str) -> bool:
    """Vero se il testo (oggetto, nome o corpo del messaggio) è quello di una notificazione ex L. 53/1994."""
    return bool(NOTIFICAZIONE_L53.search(_piano(testo)))


@dataclass
class NotificaPec:
    """Una spedizione di notificazione a mezzo PEC, con le sue ricevute."""

    spedizione: str  # identificativo dell'oggetto («Notifica_ID») o, in mancanza, il documento del messaggio
    messaggio: str = ""  # documento con la relata (il messaggio inviato o la ricevuta che lo contiene)
    data: str = ""  # data della spedizione (intestazione del messaggio)
    atti: list[dict[str, str]] = field(default_factory=list)  # {"titolo", "file"} dalla relata
    destinatari: list[str] = field(default_factory=list)
    accettazioni: list[str] = field(default_factory=list)
    consegne: list[dict[str, str]] = field(default_factory=list)  # {"documento", "data"}
    documenti: list[str] = field(default_factory=list)

    @property
    def perfezionata(self) -> bool:
        """Relata con gli atti e almeno una ricevuta di avvenuta consegna (art. 3-bis, comma 3)."""
        return bool(self.atti and self.consegne)

    @property
    def data_consegna(self) -> str:
        date_consegna = sorted(c["data"] for c in self.consegne if c.get("data"))
        return date_consegna[-1] if date_consegna else ""


def leggi_relata(testo: str) -> tuple[list[dict[str, str]], list[str]]:
    """Gli atti notificati e i destinatari elencati nella relata (art. 3-bis, comma 5, lett. b-d)."""
    testo = str(testo or "")
    atti: list[dict[str, str]] = []
    destinatari: list[str] = []
    inizio = _SEGUENTI_ATTI.search(testo)
    if inizio:
        fine = _FINE_ATTI.search(testo, inizio.end())
        blocco = testo[inizio.end():fine.start() if fine else inizio.end() + 4000]
        for voce in _VOCE_ATTO.finditer(blocco):
            titolo, nome = " ".join(voce.group("titolo").split()), voce.group("file").strip()
            if "relata" in titolo.casefold():
                continue
            if not any(a["file"] == nome for a in atti):
                atti.append({"titolo": titolo, "file": nome})
    notificato = _HO_NOTIFICATO.search(testo)
    if notificato:
        fine = inizio.start() if inizio and inizio.start() > notificato.end() else notificato.end() + 4000
        for voce in _VOCE_DESTINATARIO.finditer(testo[notificato.end():fine]):
            nome = " ".join(voce.group("nome").split()).strip(" ,;")
            if nome and nome not in destinatari:
                destinatari.append(nome)
    return atti, destinatari


def _tipo_messaggio(testo: str) -> str:
    oggetto = _OGGETTO.search(str(testo or "")[:3000])
    riga = _piano(oggetto.group(1) if oggetto else str(testo or "")[:300]).upper()
    if re.search(r"\bACCETTAZIONE\b", riga):
        return "accettazione"
    if re.search(r"\b(?:CONSEGNA|AVVENUTA CONSEGNA)\b", riga):
        return "consegna"
    if re.search(r"\b(?:MANCATA CONSEGNA|ERRORE|ANOMALIA)\b", riga):
        return "anomalia"
    return "messaggio"


def notifiche_pec(testi: Mapping[str, str], nomi: Mapping[str, str] | None = None) -> list[NotificaPec]:
    """Le notificazioni L. 53/1994 del fascicolo, raggruppate per spedizione.

    ``testi``: documento → testo già letto; ``nomi``: documento → nome (l'oggetto è spesso anche il nome).
    """
    nomi = dict(nomi or {})
    spedizioni: dict[str, NotificaPec] = {}
    for documento, testo in testi.items():
        testo = str(testo or "")
        testata = f"{nomi.get(documento, '')}\n{testo[:3000]}"
        if not e_notificazione_l53(testata):
            continue
        identificativo = _ID_SPEDIZIONE.search(testata)
        chiave = identificativo.group(1) if identificativo else f"documento:{documento}"
        voce = spedizioni.setdefault(chiave, NotificaPec(spedizione=chiave))
        voce.documenti.append(documento)
        tipo = _tipo_messaggio(testata)
        if tipo == "accettazione":
            voce.accettazioni.append(documento)
        elif tipo == "consegna":
            giorno = _GIORNO_CONSEGNA.search(testo)
            voce.consegne.append({"documento": documento, "data": _data_iso(giorno.group(1)) if giorno else _data_iso(
                (_DATA_INTESTAZIONE.search(testo[:3000]) or _DATA_IT.search(testo[:3000]) or re.match("", "")).group(0))})
        oggetto = _OGGETTO.search(testo[:3000])
        proprio = tipo == "messaggio" and bool(oggetto) and e_notificazione_l53(oggetto.group(1))
        atti, destinatari = leggi_relata(testo)
        if atti and (not voce.atti or proprio):
            voce.atti, voce.destinatari = atti, destinatari or voce.destinatari
            voce.messaggio = documento
        if proprio and not voce.data:
            # Solo il messaggio la cui intestazione È la notificazione dà la data della spedizione: una PEC
            # successiva (un deposito) che la contiene come allegato ha la data propria, non quella della notifica.
            intestazione = _DATA_INTESTAZIONE.search(testo[:3000])
            voce.data = _data_iso(intestazione.group(1)) if intestazione else ""
    for voce in spedizioni.values():
        if not voce.data:
            voce.data = voce.data_consegna
    return sorted(spedizioni.values(), key=lambda v: (v.data, v.spedizione))


def documenti_dell_atto(nome_file: str, documenti: Mapping[str, str]) -> list[str]:
    """I documenti del fascicolo che sono il file elencato nella relata (stesso nome o sua copia notificata)."""
    chiave = chiave_nome(nome_file)
    if not chiave:
        return []
    return [documento for documento, nome in documenti.items() if chiave_nome(nome) == chiave]


def prove_per_atto(notifiche: Iterable[NotificaPec], documenti: Mapping[str, str],
                   date_atti: Mapping[str, str] | None = None) -> list[dict[str, object]]:
    """Una prova per ogni documento-atto elencato nella relata di una spedizione.

    ``documenti``: documento → nome dei documenti del fascicolo; ``date_atti``: documento → data dell'atto, se letta.
    La prova è «verificata» quando la relata elenca l'atto e c'è la ricevuta di avvenuta consegna della stessa
    spedizione: relata e ricevuta sono testi generati (dall'avvocato e dal gestore PEC) letti per intero.
    """
    date_atti = dict(date_atti or {})
    prove: list[dict[str, object]] = []
    for notifica in notifiche:
        for atto in notifica.atti:
            for documento in documenti_dell_atto(atto["file"], documenti):
                data_atto = str(date_atti.get(documento) or "")[:10]
                if data_atto and notifica.data and notifica.data < data_atto:
                    continue  # la notifica non può precedere l'atto (regola 4)
                prove.append({
                    "documento_id": notifica.messaggio or (notifica.documenti[0] if notifica.documenti else ""),
                    "atto_documento_id": documento,
                    "spedizione": notifica.spedizione,
                    "data": notifica.data,
                    "data_consegna": notifica.data_consegna,
                    "atto": f"{atto['titolo']} (File: {atto['file']})",
                    "relata": True,
                    "consegna": bool(notifica.consegne),
                    "verificata": notifica.perfezionata,
                    "destinatari": list(notifica.destinatari),
                    "ricevute": [c["documento"] for c in notifica.consegne] + list(notifica.accettazioni),
                    "fonte": NORMA,
                })
    return prove


__all__ = ["NORMA", "NOTIFICAZIONE_L53", "NotificaPec", "chiave_nome", "documenti_dell_atto", "e_notificazione_l53",
           "leggi_relata", "notifiche_pec", "prove_per_atto"]
