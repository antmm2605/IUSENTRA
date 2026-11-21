"""Fase 5 — giurisprudenza: pronunce lette negli archivi di IUSENTRA, in sola lettura, con gli estremi.

Archivi consultati: il corpus nativo dello studio (Corte costituzionale e fonti pubbliche, ``GIURISPRUDENZA_DB``)
e il corpus pubblico SentenzeWeb della Cassazione (``IUSENTRA_SENTENZEWEB_DIRECTORY``). Entrambi si aprono in sola
lettura, con il ripiego sull'istantanea immutabile per gli archivi WAL non scrivibili.

Regola: l'harness non afferma il contenuto di una pronuncia. Riporta gli estremi trovati e la massima ufficiale
quando c'è, come «da leggere prima di citarla». La ricerca ha un tempo massimo: se l'archivio non risponde (disco
saturo) la fase lo dichiara e la risposta non aspetta.
"""
from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _Scaduto
from dataclasses import dataclass, field
from typing import Any, Callable

_log = logging.getLogger(__name__)
_ESECUTORE = ThreadPoolExecutor(max_workers=2, thread_name_prefix="lex-giurisprudenza")


@dataclass
class Pronuncia:
    archivio: str
    organo: str
    sezione: str
    numero: str
    anno: str
    data: str = ""
    url: str = ""
    massima: str = ""

    @property
    def estremi(self) -> str:
        sez = f", sez. {self.sezione}" if self.sezione else ""
        return f"{self.organo}{sez}, n. {self.numero}/{self.anno}" + (f" (dep. {self.data})" if self.data else "")


@dataclass
class EsitoGiurisprudenza:
    stato: str
    pronunce: list[Pronuncia] = field(default_factory=list)
    archivi: list[str] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"stato": self.stato, "archivi": self.archivi, "errori": self.errori,
                "pronunce": [dict(vars(p), estremi=p.estremi) for p in self.pronunce]}


def _riga(archivio: str, r: dict[str, Any]) -> Pronuncia:
    return Pronuncia(archivio, str(r.get("organo_giudicante") or ""), str(r.get("sezione") or ""),
                     str(r.get("numero_sentenza") or ""), str(r.get("anno_sentenza") or ""), str(r.get("data_deposito") or ""),
                     str(r.get("url_pagina_ufficiale") or r.get("url_pdf_ufficiale") or ""),
                     " ".join(str(r.get("massima_ufficiale") or r.get("principio_sintetico") or "").split())[:400])


def archivi() -> list[tuple[str, Any]]:
    """Gli archivi disponibili in questo processo, in sola lettura."""
    uscita: list[tuple[str, Any]] = []
    try:
        from pct.sentenzeweb_corpus import configured_corpus

        cass = configured_corpus()
        if cass is not None:
            uscita.append(("Cassazione (SentenzeWeb)", cass))
    except Exception:
        _log.exception("harness: archivio SentenzeWeb non apribile")
    try:
        from web.helpers import get_giurisprudenza_corpus_readonly

        uscita.append(("archivio dello studio (Consulta e fonti pubbliche)", get_giurisprudenza_corpus_readonly()))
    except Exception:
        _log.debug("harness: archivio nativo non disponibile fuori dall'applicazione", exc_info=True)
    return uscita


def cerca(domanda: str, *, limite: int = 3, secondi: float | None = None,
          sorgenti: Callable[[], list[tuple[str, Any]]] | None = None) -> EsitoGiurisprudenza:
    """Pronunce per la domanda (testo o estremi «9449/2016») in tutti gli archivi, entro un tempo massimo."""
    secondi = float(os.environ.get("LEX_HARNESS_GIURISPRUDENZA_SECONDI", "6")) if secondi is None else secondi
    elenco = (sorgenti or archivi)()
    if not elenco:
        return EsitoGiurisprudenza("nessun archivio della giurisprudenza disponibile")
    esito = EsitoGiurisprudenza("consultata", archivi=[n for n, _ in elenco])
    # Una citazione («Cass. S.U. n. 5425/2021») si cerca per soli estremi: niente scansione del testo integrale,
    # che sugli 8,6 GB di SentenzeWeb e con il disco saturo richiede minuti.
    from pct.giurisprudenza_corpus import estremi_dalla_domanda

    coppie = estremi_dalla_domanda(domanda)["coppie"]
    domanda = f"{coppie[0][0]}/{coppie[0][1]}" if len(coppie) == 1 else domanda
    futuri = {nome: _ESECUTORE.submit(corpus.cerca_sentenze, q=domanda, limit=limite, semantica=False)
              for nome, corpus in elenco}
    for nome, futuro in futuri.items():
        try:
            esito.pronunce += [_riga(nome, r) for r in futuro.result(timeout=secondi)]
        except _Scaduto:
            esito.errori.append(f"{nome}: nessuna risposta entro {secondi:.0f} s (archivio lento o disco saturo)")
        except Exception as exc:
            _log.exception("harness: ricerca nella giurisprudenza non riuscita (%s)", nome)
            esito.errori.append(f"{nome}: errore {type(exc).__name__}")
    if esito.errori and not esito.pronunce:
        esito.stato = "archivio non disponibile"
    return esito


_ESTREMI = re.compile(r"\b(\d{1,6})/(\d{4})\b")


def per_estremi(numero: str, anno: str, **kw) -> EsitoGiurisprudenza:
    """La pronuncia con quegli estremi, se l'archivio la contiene (nessun risultato di altri anni)."""
    esito = cerca(f"{numero}/{anno}", **kw)
    esito.pronunce = [p for p in esito.pronunce if p.numero.lstrip("0") == str(numero).lstrip("0") and p.anno == str(anno)]
    return esito


def sezione(esito: EsitoGiurisprudenza) -> str:
    if not esito.pronunce:
        return ""
    righe = ["**Giurisprudenza negli archivi di IUSENTRA** (estremi trovati; leggere la pronuncia prima di citarla)"]
    for p in esito.pronunce:
        # La massima resta nel registro: nel testo solo gli estremi, perché il controllo delle citazioni non può
        # verificare le norme richiamate dentro una massima.
        righe.append(f"- {p.estremi}" + (f" — {p.url}" if p.url else ""))
    return "\n".join(righe)


_PRECALCOLATE = __import__("pathlib").Path(__file__).with_name("dati") / "giurisprudenza_per_norma.json"


def _indice() -> dict[str, Any]:
    import json

    try:
        return json.loads(_PRECALCOLATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def per_norme(chiavi: list[str]) -> EsitoGiurisprudenza | None:
    """Pronunce precalcolate per norma (``scripts/lex_harness_giurisprudenza.py``): lettura istantanea, senza archivio.
    None se nessuna delle norme è nell'indice."""
    indice = _indice()
    voci = indice.get("norme", {})
    trovate = [Pronuncia(**p) for k in chiavi for p in voci.get(k, [])]
    if not any(k in voci for k in chiavi):
        return None
    return EsitoGiurisprudenza(f"indice precalcolato del {indice.get('generato_il', '')}", trovate[:4],
                               archivi=list(indice.get("archivi", [])))
