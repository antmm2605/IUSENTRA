"""Sentenze sull'articolo aperto in «Codici e leggi», dagli archivi del software in sola lettura.

1. Prima le pronunce precalcolate per norma (``lex/harness/dati/giurisprudenza_per_norma.json``, preparato da
   ``scripts/sentenze_per_norma.py`` fuori dalle richieste): lettura istantanea, con l'indirizzo ufficiale.
2. Se la norma non è nell'indice, la ricerca dal vivo della CITAZIONE della norma come frase negli archivi
   (Corte costituzionale dell'archivio dello studio, Cassazione SentenzeWeb dal 2021), con posti contati e tempo
   massimo. Si leggono solo gli estremi, che nella tabella stanno prima del testo integrale (nessuna lettura del
   testo): per aprire la pronuncia si rimanda all'Archivio sentenze del software.
L'esito dichiara sempre da dove vengono le pronunce e cosa non ha risposto: gli estremi si leggono prima di citarli.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from typing import Any, Mapping
from urllib.parse import quote

_CODICI = {
    "urn:nir:stato:regio.decreto:1942-03-16;262": ("cc", "c.c."),
    "urn:nir:stato:regio.decreto:1940-10-28;1443": ("cpc", "c.p.c."),
    "urn:nir:stato:regio.decreto:1930-10-19;1398": ("cp", "c.p."),
    "urn:nir:presidente.repubblica:decreto:1988-09-22;447": ("cpp", "c.p.p."),
    "urn:nir:stato:decreto.del.presidente.della.repubblica:1988-09-22;447": ("cpp", "c.p.p."),
    "urn:nir:stato:costituzione:1947-12-27": ("cost", "Cost."),
}
_TIPI = (("decreto.legislativo", "dlgs", "d.lgs."), ("decreto.legge", "dl", "d.l."),
         ("presidente.della.repubblica", "dpr", "d.P.R."), ("presidente.repubblica", "dpr", "d.P.R."),
         ("regio.decreto", "rd", "r.d."), (":legge:", "l", "l."))
SECONDI = 8.0
PER_ARCHIVIO = 3


def _citazione(item: Mapping[str, Any]) -> tuple[str, str, str]:
    """(citazione leggibile, chiave delle norme, estremi «n/anno») dell'articolo."""
    numero = str(item.get("number") or "").strip().rstrip(".")
    articolo = re.sub(r"[^0-9a-z]", "", numero.lower())
    urn = str(item.get("urn") or "")
    for prefisso, (chiave, sigla) in _CODICI.items():
        if urn.startswith(prefisso):
            return f"art. {numero} {sigla}", f"{chiave}:{articolo}", ""
    anno = str(item.get("data_atto") or "")[:4]
    atto = str(item.get("numero") or "").strip()
    for marcatore, sigla_chiave, sigla in _TIPI:
        if marcatore in urn and atto and anno:
            return f"art. {numero} {sigla} {atto}/{anno}", f"{sigla_chiave}{atto}:{articolo}", f"{atto}/{anno}"
    return (f"art. {numero} {atto}/{anno}".strip(), "", "")


def _archivi() -> list[tuple[str, Any]]:
    from lex.harness.giurisprudenza import archivi

    return archivi()


def _dal_vivo(chiave: str, estremi: str) -> list[dict[str, Any]]:
    """Nel worker (tempo massimo aperto): frasi della citazione, poi solo gli estremi delle righe scelte."""
    from lex.normativa.citazioni_norma import interrogazioni

    domande = interrogazioni(chiave, f"art. x {estremi}" if estremi else "")
    uscita = []
    for nome, corpus in _archivi():
        with closing(corpus._connect()) as conn:
            ids: set[int] = set()
            for domanda in domande:
                try:
                    ids.update(r[0] for r in conn.execute(
                        "SELECT rowid FROM sentenze_fts WHERE sentenze_fts MATCH ? ORDER BY rowid DESC LIMIT 40", (domanda,)))
                except sqlite3.OperationalError as exc:
                    if "interrupt" in str(exc).lower():
                        raise
                    continue
            righe = []
            # Ogni riga letta costa un accesso al disco: solo le più recenti (identificativo più alto).
            for ident in sorted(ids, reverse=True)[:PER_ARCHIVIO + 1]:
                riga = conn.execute("SELECT organo_giudicante, sezione, numero_sentenza, anno_sentenza, data_deposito "
                                    "FROM sentenze WHERE id=?", (ident,)).fetchone()
                if riga and riga[2] and riga[3]:
                    righe.append(tuple(riga))
            righe.sort(key=lambda r: (str(r[4] or ""), str(r[3])), reverse=True)
            for organo, sezione, numero, anno, data in righe[:PER_ARCHIVIO]:
                numero = str(numero).lstrip("0") or "0"
                uscita.append({"archivio": nome, "organo": str(organo or ""), "sezione": str(sezione or ""),
                               "numero": numero, "anno": str(anno), "data": str(data or ""), "massima": "",
                               "url": f"/giurisprudenza?q={quote(f'{numero}/{anno}')}"})
    return uscita


def _estremi(p: Mapping[str, Any]) -> str:
    sezione = f", sez. {p['sezione']}" if p.get("sezione") else ""
    data = f" (dep. {p['data']})" if p.get("data") else ""
    return f"{p['organo']}{sezione}, n. {p['numero']}/{p['anno']}{data}"


def sentenze_per_articolo(item: Mapping[str, Any], *, secondi: float = SECONDI, utente: str = "") -> dict[str, Any]:
    from lex.harness.giurisprudenza import per_norme

    citazione, chiave, estremi = _citazione(item)
    esito = per_norme([chiave]) if chiave else None
    if esito is not None:
        dati = esito.to_dict()
        return {"citazione": citazione, "fonte": "pronunce che citano la norma, precalcolate negli archivi",
                "stato": dati["stato"], "archivi": dati["archivi"], "errori": dati["errori"],
                "pronunce": dati["pronunce"], "avvertenza": _AVVERTENZA}
    if not chiave:
        return {"citazione": citazione, "fonte": "", "stato": "norma non riconosciuta", "archivi": [], "pronunce": [],
                "errori": ["Per questo atto la citazione non si può cercare con certezza negli archivi."],
                "avvertenza": ""}
    from lex.tempo_ricerca import PostoNonDisponibile, RicercaTroppoLunga

    try:
        pronunce = _ESECUTORE.esegui(_dal_vivo, chiave, estremi, secondi=secondi, utente=utente)
        errori = []
    except PostoNonDisponibile:
        pronunce, errori = [], ["Gli archivi delle sentenze sono occupati da altre ricerche: riprova fra poco."]
    except RicercaTroppoLunga:
        pronunce, errori = [], [f"Gli archivi delle sentenze non hanno risposto entro {secondi:.0f} secondi."]
    return {"citazione": citazione, "fonte": "ricerca della citazione negli archivi", "stato": "consultata",
            "archivi": [n for n, _ in _archivi()], "errori": errori,
            "pronunce": [dict(p, estremi=_estremi(p)) for p in pronunce], "avvertenza": _AVVERTENZA}


_AVVERTENZA = ("Pronunce più recenti degli archivi del software che citano l'articolo: "
               "leggi la pronuncia prima di citarla.")


def _crea_esecutore():
    from lex.tempo_ricerca import EsecutoreLimitato

    return EsecutoreLimitato("sentenze-articolo", posti=2, per_utente=1)


_ESECUTORE = _crea_esecutore()
