"""Dati e misure per l'addestramento del modello di catalogazione sul PC dell'avvocato (senza GPU, senza torch).

Il pacchetto arriva dal server (`deploy/hetzner/esportazione_addestramento.py`): `dataset.jsonl.gz`,
`prefisso_domanda.txt` (istruzioni ed elenco delle voci del catalogo, identico alla seconda lettura di Lex) e
`manifesto.json`. Qui si leggono le righe, si costruiscono le conversazioni e si misurano le risposte.
"""

from __future__ import annotations

import gzip
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

FORMATO = "iusentra-catalogo-addestramento.v1"
NESSUNA_VOCE = "Nessuna voce del catalogo"  # come catalog_lex.NESSUNA_VOCE


def leggi_pacchetto(cartella: Path) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    cartella = Path(cartella)
    manifesto = json.loads((cartella / "manifesto.json").read_text(encoding="utf-8"))
    if manifesto.get("formato") != FORMATO:
        raise ValueError(f"Pacchetto di formato inatteso: {manifesto.get('formato')!r}")
    prefisso = (cartella / "prefisso_domanda.txt").read_text(encoding="utf-8")
    with gzip.open(cartella / "dataset.jsonl.gz", "rt", encoding="utf-8") as ingresso:
        righe = [json.loads(riga) for riga in ingresso if riga.strip()]
    return prefisso, righe, manifesto


def applica_decisioni(righe: list[dict[str, Any]], file: Path | None) -> list[dict[str, Any]]:
    """Le righe «da rivedere» decise (dall'avvocato o, su sua autorizzazione, da Claude) diventano verifica.

    Il file è JSONL: {"id": codice, "voce": voce del catalogo, "fonte": "avvocato" | "claude"}. La fonte resta
    nella riga, così ogni misura dice chi ha deciso.
    """
    if not file:
        return righe
    decisioni = {d["id"]: d for d in map(json.loads, Path(file).read_text(encoding="utf-8").splitlines()) if d}
    uscita = []
    for riga in righe:
        decisa = decisioni.get(riga["id"])
        if decisa and riga.get("gruppo") == "da_rivedere" and decisa.get("voce"):
            riga = {**riga, "gruppo": "verifica_decisioni", "voce": decisa["voce"],
                    "fonte": f"decisione_{decisa.get('fonte') or 'avvocato'}"}
        uscita.append(riga)
    return uscita


def gruppo(righe: Iterable[dict[str, Any]], nome: str) -> list[dict[str, Any]]:
    return [r for r in righe if r.get("gruppo") == nome]


def conversazione(prefisso: str, riga: dict[str, Any], *, con_risposta: bool = True) -> list[dict[str, str]]:
    messaggi = [{"role": "user", "content": prefisso + riga["testo"]}]
    if con_risposta:
        messaggi.append({"role": "assistant", "content": riga["risposta"]})
    return messaggi


def voci_del_prefisso(prefisso: str) -> set[str]:
    """Le etichette dell'elenco chiuso («- Etichetta [sezione]») scritto nel prefisso."""
    return {m.group(1).strip() for m in re.finditer(r"(?m)^- (.+?) \[[^\]]+\]$", prefisso)}


def leggi_risposta(testo: str, voci: set[str]) -> dict[str, str]:
    """Il JSON della risposta del modello; voce vuota se fuori dall'elenco chiuso o illeggibile."""
    corpo = re.search(r"\{.*\}", str(testo or ""), re.DOTALL)
    try:
        dati = json.loads(corpo.group(0)) if corpo else {}
    except json.JSONDecodeError:
        dati = {}
    etichetta = str(dati.get("etichetta") or "").strip()
    return {"etichetta": etichetta if etichetta in voci or etichetta == NESSUNA_VOCE else "",
            "citazione": str(dati.get("citazione") or ""), "motivo": str(dati.get("motivo") or "")}


def _normalizza(testo: str) -> str:
    grezzo = unicodedata.normalize("NFKD", str(testo or "").casefold())
    grezzo = "".join(c for c in grezzo if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", grezzo).split())


def citazione_presente(citazione: str, testo: str) -> bool:
    """Controllo semplificato sul PC; quello vincolante resta `catalog_lex.citazione_nel_testo` sul server."""
    cercata = _normalizza(citazione)
    return len(cercata.split()) >= 4 and f" {cercata} " in f" {_normalizza(testo)} "


def misura(righe: list[dict[str, Any]], risposte: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Accuratezza del modello, delle regole e di Spark sulle stesse righe con voce nota."""
    esito: Counter[str] = Counter()
    errori: Counter[str] = Counter()
    for riga in righe:
        vera = riga.get("voce") or ""
        if not vera:
            continue
        risposta = risposte.get(riga["id"], {})
        esito["documenti"] += 1
        esito["modello_giuste"] += int(risposta.get("etichetta") == vera)
        esito["modello_citazione_presente"] += int(citazione_presente(risposta.get("citazione", ""), riga["testo"]))
        esito["modello_illeggibile"] += int(not risposta.get("etichetta"))
        esito["regole_giuste"] += int(riga.get("voce_regole") == vera)
        if riga.get("voce_spark"):
            esito["spark_valutati"] += 1
            esito["spark_giuste"] += int(riga["voce_spark"] == vera)
        if risposta.get("etichetta") and risposta.get("etichetta") != vera:
            errori[f"{vera} → {risposta['etichetta']}"] += 1
    return {**dict(esito), "errori_piu_frequenti": dict(errori.most_common(25))}


def disaccordi(righe: list[dict[str, Any]], risposte: dict[str, dict[str, str]]) -> Iterator[dict[str, str]]:
    """Righe «da rivedere» dove il modello sceglie una voce diversa dalle regole: codici opachi soltanto."""
    for riga in righe:
        risposta = risposte.get(riga["id"], {})
        etichetta = risposta.get("etichetta", "")
        if etichetta and etichetta != NESSUNA_VOCE and etichetta != riga.get("voce_regole"):
            yield {"id": riga["id"], "voce_regole": riga.get("voce_regole", ""), "voce_modello": etichetta,
                   "voce_spark": riga.get("voce_spark", "")}


__all__ = ["FORMATO", "NESSUNA_VOCE", "applica_decisioni", "citazione_presente", "conversazione", "disaccordi", "gruppo",
           "leggi_pacchetto", "leggi_risposta", "misura", "voci_del_prefisso"]
