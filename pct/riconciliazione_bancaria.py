"""Riconciliazione bancaria della prima nota di studio.

Importa l'estratto conto in CSV (il formato esportabile da qualsiasi home
banking) e propone gli abbinamenti con i movimenti di prima nota: stesso
importo con segno coerente e data entro una tolleranza configurabile. La
conferma resta SEMPRE all'avvocato — nessun abbinamento e' automatico
(fail-closed) — e la riga bancaria senza corrispondenza diventa una proposta
di nuovo movimento, mai un movimento gia' registrato.

La riconciliazione e' un controllo di completezza del registro cronologico
(art. 19 D.P.R. 600/1973): aiuta a scoprire incassi e pagamenti dimenticati e
movimenti registrati ma mai transitati in banca. Nessun calcolo fiscale.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

TOLLERANZA_GIORNI_DEFAULT = 3

# Intestazioni riconosciute per l'auto-mappatura delle colonne (case-insensitive).
# "movimento" NON e' un candidato importo: in molti estratti e' il numero
# progressivo dell'operazione e produrrebbe importi assurdi.
_COLONNE_DATA = ("data contabile", "data operazione", "data valuta", "data", "date")
_COLONNE_IMPORTO = ("importo", "amount")
_COLONNE_DARE = ("addebiti", "addebito", "uscite", "dare", "debit")
_COLONNE_AVERE = ("accrediti", "accredito", "entrate", "avere", "credit")
_COLONNE_DESCRIZIONE = ("descrizione", "causale", "descrizione operazione", "dettagli", "description")


@dataclass
class RigaEstratto:
    """Una riga dell'estratto conto normalizzata."""

    id: str  # hash stabile: idempotenza tra import ripetuti
    data: str  # ISO
    importo: float  # >0 accredito, <0 addebito
    descrizione: str

    @property
    def verso(self) -> str:
        return "INCASSO" if self.importo > 0 else "PAGAMENTO"


@dataclass
class PropostaAbbinamento:
    """Esito del confronto riga-banca ↔ prima nota, da confermare a mano."""

    riga: RigaEstratto
    tipo: str  # "abbinamento" | "ambiguo" | "nuovo_movimento"
    movimento_id: str = ""  # valorizzato per "abbinamento"
    candidati: list[str] = field(default_factory=list)  # per "ambiguo"


def _parse_importo_it(value: Any) -> float | None:
    """Importo in formato italiano o anglosassone. None se non numerico o ambiguo.

    Regole (fail-closed sugli ambigui, mai valori 1000x sbagliati):
    - entrambi i separatori: quello più a destra è il decimale;
    - solo punto con esattamente 3 cifre finali → separatore delle migliaia
      (convenzione italiana: "1.220" = milleduecentoventi); altrimenti decimale;
    - solo virgola con esattamente 3 cifre finali e parte intera non nulla →
      AMBIGUO (potrebbe essere migliaia anglosassone): scartato con None;
      altrimenti decimale italiano;
    - segno negativo riconosciuto in testa, in coda ("234,56-") o tra parentesi.
    """

    raw = str(value or "").strip().replace("€", "").replace("\xa0", "").replace(" ", "")
    if not raw:
        return None
    negativo = raw.startswith("-") or raw.endswith("-") or (raw.startswith("(") and raw.endswith(")"))
    raw = raw.strip("()").strip("+-")
    if not raw:
        return None
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "." in raw:
        parti = raw.split(".")
        if len(parti[-1]) == 3 and all(p.isdigit() for p in parti):
            raw = raw.replace(".", "")  # migliaia all'italiana: 1.220 → 1220
        elif raw.count(".") > 1:
            return None
    elif "," in raw:
        parti = raw.split(",")
        if raw.count(",") > 1:
            return None
        if len(parti[-1]) == 3 and parti[0].isdigit() and parti[0] not in {"", "0"}:
            return None  # "1,000": ambiguo tra 1.0 e 1000 → si scarta con avviso
        raw = raw.replace(",", ".")
    try:
        numero = float(raw)
    except ValueError:
        return None
    return -numero if negativo else numero


def _parse_data_estratto(value: Any) -> str:
    raw = str(value or "").strip()[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return date.fromisoformat(raw).isoformat()
        except ValueError:
            return ""
    match = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", raw)
    if match:
        giorno, mese, anno = match.groups()
        anno_int = int(anno) + (2000 if len(anno) == 2 else 0)
        try:
            return date(anno_int, int(mese), int(giorno)).isoformat()
        except ValueError:
            return ""
    return ""


def _trova_colonna(intestazioni: list[str], candidate: tuple[str, ...]) -> int | None:
    normalizzate = [" ".join(h.casefold().split()) for h in intestazioni]
    for nome in candidate:
        for indice, header in enumerate(normalizzate):
            if header == nome or header.startswith(nome):
                return indice
    return None


def parse_estratto_csv(testo: str) -> tuple[list[RigaEstratto], list[str]]:
    """Legge un estratto conto CSV con auto-mappatura delle colonne.

    Gestisce: separatore ``;`` o ``,`` (sniffing), date italiane e ISO,
    decimali all'italiana, colonna importo unica (con segno) oppure colonne
    separate dare/avere. Ritorna (righe valide, avvisi sulle righe scartate).
    """

    avvisi: list[str] = []
    pulito = testo.lstrip("﻿").strip()
    if not pulito:
        return [], ["File vuoto."]
    try:
        dialect = csv.Sniffer().sniff(pulito[:2048], delimiters=";,")
        separatore = dialect.delimiter
    except csv.Error:
        separatore = ";" if pulito.splitlines()[0].count(";") >= pulito.splitlines()[0].count(",") else ","
    reader = csv.reader(io.StringIO(pulito), delimiter=separatore)
    righe_grezze = [riga for riga in reader if any(str(cella or "").strip() for cella in riga)]
    if len(righe_grezze) < 2:
        return [], ["Nessuna riga di movimento trovata sotto l'intestazione."]

    intestazioni = [str(cella or "").strip() for cella in righe_grezze[0]]
    col_data = _trova_colonna(intestazioni, _COLONNE_DATA)
    col_importo = _trova_colonna(intestazioni, _COLONNE_IMPORTO)
    col_dare = _trova_colonna(intestazioni, _COLONNE_DARE)
    col_avere = _trova_colonna(intestazioni, _COLONNE_AVERE)
    col_descrizione = _trova_colonna(intestazioni, _COLONNE_DESCRIZIONE)
    if col_data is None or (col_importo is None and col_dare is None and col_avere is None):
        return [], [
            "Intestazioni non riconosciute: servono una colonna data "
            "(es. 'Data contabile') e una colonna importo (es. 'Importo' oppure 'Addebiti'/'Accrediti')."
        ]

    righe: list[RigaEstratto] = []
    visti: dict[str, int] = {}
    for numero, riga in enumerate(righe_grezze[1:], start=2):
        def _cella(indice: int | None) -> str:
            return str(riga[indice]).strip() if indice is not None and indice < len(riga) else ""

        data_iso = _parse_data_estratto(_cella(col_data))
        if not data_iso:
            avvisi.append(f"Riga {numero}: data non riconosciuta, saltata.")
            continue
        importo: float | None = None
        if col_importo is not None and _cella(col_importo):
            importo = _parse_importo_it(_cella(col_importo))
            if importo is None:
                avvisi.append(f"Riga {numero}: importo non riconosciuto o ambiguo, saltata.")
                continue
        if importo is None:
            dare = _parse_importo_it(_cella(col_dare)) if _cella(col_dare) else None
            avere = _parse_importo_it(_cella(col_avere)) if _cella(col_avere) else None
            # Fail-closed: un valore negativo nelle colonne dare/avere e' una
            # rettifica/storno bancario, non un movimento ordinario: va
            # registrato a mano, non raddrizzato con abs().
            if (dare is not None and dare < 0) or (avere is not None and avere < 0):
                avvisi.append(
                    f"Riga {numero}: rettifica o storno bancario (importo negativo in "
                    "dare/avere): registrala manualmente in prima nota, saltata."
                )
                continue
            if dare or avere:
                importo = round((avere or 0.0) - (dare or 0.0), 2)
        if importo is None or importo == 0:
            avvisi.append(f"Riga {numero}: importo assente o nullo, saltata.")
            continue
        descrizione = " ".join(_cella(col_descrizione).split())[:240]
        # Due operazioni identiche nello stesso giorno (es. due marche da bollo)
        # sono legittime: l'occorrenza entra nell'hash, cosi' l'id resta stabile
        # tra import ripetuti senza scartare transazioni reali.
        chiave_base = f"{data_iso}|{importo:.2f}|{descrizione.casefold()}"
        occorrenza = visti.get(chiave_base, 0)
        visti[chiave_base] = occorrenza + 1
        digest = hashlib.sha256(f"{chiave_base}|{occorrenza}".encode()).hexdigest()[:16]
        righe.append(RigaEstratto(id=digest, data=data_iso, importo=round(importo, 2), descrizione=descrizione))
    return righe, avvisi


def proponi_abbinamenti(
    righe: list[RigaEstratto],
    movimenti: list[Any],
    *,
    tolleranza_giorni: int = TOLLERANZA_GIORNI_DEFAULT,
) -> list[PropostaAbbinamento]:
    """Confronta le righe banca con i movimenti di prima nota non riconciliati.

    Regole (informative, mai definitive):
    - stesso importo (accredito↔INCASSO, addebito↔PAGAMENTO) e data entro la
      tolleranza → un solo candidato = "abbinamento"; piu' candidati = "ambiguo";
    - nessun candidato → "nuovo_movimento" (proposta di registrazione);
    - ogni movimento di prima nota puo' essere candidato di una sola riga
      (il migliore per distanza di data), per evitare doppi abbinamenti.
    """

    # Solo movimenti non riconciliati, non storni/stornati, transitabili in
    # banca (i movimenti in cassa non compaiono sull'estratto conto).
    def _candidabile(m: Any) -> bool:
        if str(getattr(m, "riconciliato_il", "") or ""):
            return False
        if str(getattr(m, "metodo", "") or "") == "cassa":
            return False
        note = str(getattr(m, "note", "") or "").casefold()
        if str(getattr(m, "storno_di", "") or "") or note.startswith("storno di"):
            return False
        return True

    disponibili = {str(getattr(m, "id", "")): m for m in movimenti if _candidabile(m)}

    # Tutte le coppie compatibili (riga, movimento) con la loro distanza in
    # giorni: l'assegnazione e' globale per delta crescente, cosi' il match
    # esatto vince sempre sulla riga che capita prima nel file.
    coppie: list[tuple[int, str, str]] = []  # (delta, riga_id, movimento_id)
    candidati_per_riga: dict[str, list[str]] = {r.id: [] for r in righe}
    for riga in righe:
        for movimento_id, movimento in disponibili.items():
            if str(getattr(movimento, "tipo", "")) != riga.verso:
                continue
            if abs(float(getattr(movimento, "importo", 0.0)) - abs(riga.importo)) > 0.005:
                continue
            try:
                delta = abs(
                    (date.fromisoformat(str(getattr(movimento, "data", ""))[:10]) - date.fromisoformat(riga.data)).days
                )
            except ValueError:
                continue
            if delta <= tolleranza_giorni:
                coppie.append((delta, riga.id, movimento_id))
                candidati_per_riga[riga.id].append(movimento_id)

    coppie.sort(key=lambda c: (c[0], c[1], c[2]))  # delta minimo, poi ordine stabile
    assegnati_riga: dict[str, str] = {}
    movimenti_presi: set[str] = set()
    for _delta, riga_id, movimento_id in coppie:
        if riga_id in assegnati_riga or movimento_id in movimenti_presi:
            continue
        assegnati_riga[riga_id] = movimento_id
        movimenti_presi.add(movimento_id)

    proposte: list[PropostaAbbinamento] = []
    for riga in sorted(righe, key=lambda r: r.data):
        candidati = candidati_per_riga.get(riga.id, [])
        if riga.id in assegnati_riga and len(candidati) == 1:
            proposte.append(
                PropostaAbbinamento(riga=riga, tipo="abbinamento", movimento_id=assegnati_riga[riga.id])
            )
        elif len(candidati) > 1:
            proposte.append(PropostaAbbinamento(riga=riga, tipo="ambiguo", candidati=candidati))
        elif riga.id in assegnati_riga:
            proposte.append(
                PropostaAbbinamento(riga=riga, tipo="abbinamento", movimento_id=assegnati_riga[riga.id])
            )
        else:
            proposte.append(PropostaAbbinamento(riga=riga, tipo="nuovo_movimento"))
    return proposte
