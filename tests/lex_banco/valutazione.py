"""Esecuzione e valutazione del banco di prova di Lex.

Ogni domanda passa dallo stesso canale del browser (`POST /api/assistente/chat`,
risposta a eventi `data: {"token": …}`) con il corpo che invia il widget di Lex.
Il modello linguistico locale è escluso (indirizzo irraggiungibile): il banco
misura il percorso deterministico, l'unico da cui devono venire date e fatti.
La data di riferimento è fissa (`IUSENTRA_LEX_REFERENCE_DATE`): ogni parte di
Lex che usa l'orologio di sistema invece di quella data è un difetto da correggere.
"""

from __future__ import annotations

import json
import os
import re
import socket
import tempfile
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .studio import DATA_RIFERIMENTO, accedi, crea_studio

CARTELLA = Path(__file__).resolve().parent
DOMANDE = CARTELLA / "domande.json"
SOGLIA = CARTELLA / "soglia.json"
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre")
_AMBIENTE_BANCO = {
    "IUSENTRA_LEX_REFERENCE_DATE": DATA_RIFERIMENTO,
    # Nessun modello locale: le risposte devono venire dai dati, in modo ripetibile.
    "OLLAMA_URL": "http://127.0.0.1:9",
    "PCT_LOCAL_AI_BASE_URL": "http://127.0.0.1:9",
}


@dataclass(slots=True)
class EsitoDomanda:
    id: str
    categoria: str
    domanda: str
    risposta: str
    superata: bool
    motivi: list[str] = field(default_factory=list)


def carica_domande() -> dict[str, Any]:
    return json.loads(DOMANDE.read_text(encoding="utf-8"))


def carica_soglia() -> dict[str, Any]:
    if not SOGLIA.exists():
        return {"superate": []}
    return json.loads(SOGLIA.read_text(encoding="utf-8"))


def _normalizza(testo: str) -> str:
    testo = unicodedata.normalize("NFKC", str(testo or "")).replace("’", "'").replace("°", "")
    return re.sub(r"\s+", " ", testo).strip().lower()


def forme_data(iso: str) -> list[str]:
    """Modi accettati di scrivere una data: in lettere italiane o gg/mm/aaaa (mai ISO)."""

    giorno = date.fromisoformat(iso)
    return [
        f"{giorno.day} {MESI[giorno.month - 1]} {giorno.year}",
        f"{giorno.day:02d} {MESI[giorno.month - 1]} {giorno.year}",
        giorno.strftime("%d/%m/%Y"),
        f"{giorno.day}/{giorno.month}/{giorno.year}",
        giorno.strftime("%d.%m.%Y"),
    ]


def contiene(risposta: str, atteso: str) -> bool:
    testo = _normalizza(risposta)
    if atteso.startswith("data:"):
        return any(_normalizza(forma) in testo for forma in forme_data(atteso[5:]))
    return _normalizza(atteso) in testo


def valuta(
    caso: dict[str, Any],
    risposta: str,
    vietate_sempre: list[str],
    date_clienti: dict[str, list[str]] | None = None,
) -> EsitoDomanda:
    motivi: list[str] = []
    if "solo" in caso:
        # Domanda su un cliente preciso: nomi e date degli altri clienti non devono comparire.
        ammesse = {data for cognome in caso["solo"] for data in (date_clienti or {}).get(cognome, [])}
        for cognome, date in (date_clienti or {}).items():
            if cognome in caso["solo"]:
                continue
            if contiene(risposta, cognome):
                motivi.append(f"parla di un altro cliente («{cognome}»)")
            estranee = [data for data in date if data not in ammesse and contiene(risposta, f"data:{data}")]
            if estranee:
                motivi.append(f"riporta date di {cognome}: {', '.join(estranee)}")
    for atteso in caso.get("deve_contenere", []):
        if not contiene(risposta, atteso):
            motivi.append(f"manca «{atteso}»")
    alternative = caso.get("almeno_uno", [])
    if alternative and not any(contiene(risposta, voce) for voce in alternative):
        motivi.append("manca una di: " + ", ".join(f"«{voce}»" for voce in alternative))
    for vietato in [*caso.get("non_deve_contenere", []), *vietate_sempre]:
        if contiene(risposta, vietato):
            motivi.append(f"contiene «{vietato}»")
    if not risposta.strip():
        motivi.append("risposta vuota")
    return EsitoDomanda(
        id=caso["id"], categoria=caso.get("categoria", ""), domanda=caso["domanda"],
        risposta=risposta, superata=not motivi, motivi=motivi,
    )


def testo_da_eventi(corpo: str) -> str:
    """Ricompone la risposta dagli eventi `data: {"token": …}` del canale di Lex."""

    parti: list[str] = []
    for riga in corpo.splitlines():
        if not riga.startswith("data:"):
            continue
        dato = riga[5:].strip()
        if not dato or dato == "[DONE]":
            continue
        try:
            evento = json.loads(dato)
        except json.JSONDecodeError:
            parti.append(dato)
            continue
        if isinstance(evento, dict):
            valore = evento.get("token") or evento.get("text") or evento.get("answer") or ""
            if valore:
                parti.append(str(valore))
    return "".join(parti)


def corpo_richiesta(domanda: str, sessione: str) -> dict[str, Any]:
    """Stesso corpo che invia il widget di Lex dal cruscotto (pct-lex-assistant.js)."""

    return {
        "session_id": sessione,
        "messages": [{"role": "user", "content": domanda}],
        "context_label": "",
        "page_context": "dashboard",
        "page_path": "/",
        "active_context": {},
        "attachments": [],
        "mode": "",
        "page_section": "dashboard",
    }


def _indirizzo_locale(indirizzo: Any) -> bool:
    if not isinstance(indirizzo, tuple) or not indirizzo:
        return True  # socket Unix e simili
    host = str(indirizzo[0])
    return host in {"localhost", "::1"} or host.startswith("127.")


@contextmanager
def _ambiente() -> Iterator[None]:
    """Data fissa, niente modello locale e niente rete esterna: il banco misura solo i dati dello studio."""

    precedenti = {chiave: os.environ.get(chiave) for chiave in _AMBIENTE_BANCO}
    connetti_originale = socket.socket.connect

    def connetti_solo_locale(sock: socket.socket, indirizzo: Any) -> Any:
        if not _indirizzo_locale(indirizzo):
            raise OSError(f"Rete esterna esclusa dal banco di prova di Lex: {indirizzo!r}")
        return connetti_originale(sock, indirizzo)

    os.environ.update(_AMBIENTE_BANCO)
    socket.socket.connect = connetti_solo_locale  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = connetti_originale  # type: ignore[method-assign]
        for chiave, valore in precedenti.items():
            if valore is None:
                os.environ.pop(chiave, None)
            else:
                os.environ[chiave] = valore


def esegui_banco(tmp_path: Path | None = None, *, solo: set[str] | None = None) -> list[EsitoDomanda]:
    dati = carica_domande()
    vietate = list(dati.get("vietate_sempre", []))
    date_clienti = dict(dati.get("date_clienti", {}))
    casi = [caso for caso in dati["domande"] if not solo or caso["id"] in solo]
    with _ambiente(), tempfile.TemporaryDirectory(prefix="banco_lex_") as cartella:
        banco = crea_studio(Path(tmp_path or cartella))
        esiti: list[EsitoDomanda] = []
        with banco.app.test_client() as client:
            accedi(client, banco)
            for caso in casi:
                # Una sessione per domanda: nessuna domanda eredita il contesto della precedente.
                risposta = client.post("/api/assistente/chat", json=corpo_richiesta(caso["domanda"], f"banco-{caso['id']}"))
                testo = testo_da_eventi(risposta.get_data(as_text=True))
                if risposta.status_code != 200:
                    testo = f"[HTTP {risposta.status_code}] {testo}"
                esiti.append(valuta(caso, testo, vietate, date_clienti))
        return esiti


def riepilogo(esiti: list[EsitoDomanda]) -> dict[str, Any]:
    categorie: dict[str, dict[str, int]] = {}
    for esito in esiti:
        voce = categorie.setdefault(esito.categoria, {"totale": 0, "superate": 0})
        voce["totale"] += 1
        voce["superate"] += int(esito.superata)
    return {
        "totale": len(esiti),
        "superate": sum(esito.superata for esito in esiti),
        "per_categoria": categorie,
        "superate_id": sorted(esito.id for esito in esiti if esito.superata),
    }
