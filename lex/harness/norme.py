"""Norme dell'harness di Lex: catalogo, testo vigente dall'archivio e controllo di ciò che si afferma.

Ogni regola dell'harness cita una norma con una «ancora»: le parole letterali del testo vigente su cui si fonda
l'affermazione (es. art. 1385 c.c. → «esigere il doppio della caparra»). Il controllore accetta l'affermazione solo se
l'ancora compare nel testo dell'articolo letto dall'archivio Normattiva del software (``PCT_NORMATTIVA_DB``):
niente norme a memoria, niente articoli inventati.

Il testo si legge una volta dall'archivio con ``scripts/lex_harness_norme.py`` e si conserva in
``dati/norme_vigenti.json`` con edizione, URN e impronta; a runtime l'harness legge quell'istantanea (millisecondi) e,
se un articolo manca, prova l'archivio dal vivo. Una norma che non si riesce a leggere non entra nella risposta:
il punto va fra i dubbi con il motivo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

CARTELLA_DATI = Path(__file__).with_name("dati")
ISTANTANEA = CARTELLA_DATI / "norme_vigenti.json"


@dataclass(frozen=True)
class Norma:
    chiave: str        # «cc:1385»
    estremi: str       # come li legge web.services.ricerca_legale_norma_citata.estremi
    citazione: str     # «art. 1385 c.c.»
    rubrica: str = ""


def _n(chiave: str, estremi: str, citazione: str, rubrica: str = "") -> Norma:
    return Norma(chiave, estremi, citazione, rubrica)


_CC, _CPC, _CP, _CPP = "r.d. 262/1942", "r.d. 1443/1940", "r.d. 1398/1930", "d.p.r. 447/1988"

NORME: dict[str, Norma] = {n.chiave: n for n in (
    # Codice civile
    _n("cc:151", f"art. 151 {_CC}", "art. 151 c.c.", "Separazione giudiziale"),
    _n("cc:337ter", f"art. 337-ter {_CC}", "art. 337-ter c.c.", "Provvedimenti riguardo ai figli"),
    _n("cc:337septies", f"art. 337-septies {_CC}", "art. 337-septies c.c.", "Figli maggiorenni"),
    _n("cc:1137", f"art. 1137 {_CC}", "art. 1137 c.c.", "Impugnazione delle deliberazioni dell'assemblea"),
    _n("cc:1182", f"art. 1182 {_CC}", "art. 1182 c.c.", "Luogo dell'adempimento"),
    _n("cc:1224", f"art. 1224 {_CC}", "art. 1224 c.c.", "Danni nelle obbligazioni pecuniarie"),
    _n("cc:1351", f"art. 1351 {_CC}", "art. 1351 c.c.", "Contratto preliminare"),
    _n("cc:1385", f"art. 1385 {_CC}", "art. 1385 c.c.", "Caparra confirmatoria"),
    _n("cc:1453", f"art. 1453 {_CC}", "art. 1453 c.c.", "Risolubilità del contratto per inadempimento"),
    _n("cc:1455", f"art. 1455 {_CC}", "art. 1455 c.c.", "Importanza dell'inadempimento"),
    _n("cc:1454", f"art. 1454 {_CC}", "art. 1454 c.c.", "Diffida ad adempiere"),
    _n("cc:1587", f"art. 1587 {_CC}", "art. 1587 c.c.", "Obbligazioni principali del conduttore"),
    _n("cc:2932", f"art. 2932 {_CC}", "art. 2932 c.c.", "Esecuzione specifica dell'obbligo di concludere un contratto"),
    _n("cc:2948", f"art. 2948 {_CC}", "art. 2948 c.c.", "Prescrizione di cinque anni"),
    # Codice di procedura civile
    _n("cpc:7", f"art. 7 {_CPC}", "art. 7 c.p.c.", "Competenza del giudice di pace"),
    _n("cpc:9", f"art. 9 {_CPC}", "art. 9 c.p.c.", "Competenza del tribunale"),
    _n("cpc:10", f"art. 10 {_CPC}", "art. 10 c.p.c.", "Determinazione del valore"),
    _n("cpc:14", f"art. 14 {_CPC}", "art. 14 c.p.c.", "Cause relative a somme di danaro e a beni mobili"),
    _n("cpc:18", f"art. 18 {_CPC}", "art. 18 c.p.c.", "Foro generale delle persone fisiche"),
    _n("cpc:19", f"art. 19 {_CPC}", "art. 19 c.p.c.", "Foro generale delle persone giuridiche"),
    _n("cpc:20", f"art. 20 {_CPC}", "art. 20 c.p.c.", "Foro facoltativo per le cause relative a diritti di obbligazione"),
    _n("cpc:21", f"art. 21 {_CPC}", "art. 21 c.p.c.", "Foro per le cause relative a diritti reali e ad azioni possessorie"),
    _n("cpc:38", f"art. 38 {_CPC}", "art. 38 c.p.c.", "Incompetenza"),
    _n("cpc:86", f"art. 86 {_CPC}", "art. 86 c.p.c.", "Difesa personale della parte"),
    _n("cpc:83", f"art. 83 {_CPC}", "art. 83 c.p.c.", "Procura alle liti"),
    _n("cpc:155", f"art. 155 {_CPC}", "art. 155 c.p.c.", "Computo dei termini"),
    _n("cpc:163", f"art. 163 {_CPC}", "art. 163 c.p.c.", "Contenuto della citazione"),
    _n("cpc:163bis", f"art. 163-bis {_CPC}", "art. 163-bis c.p.c.", "Termini per comparire"),
    _n("cpc:165", f"art. 165 {_CPC}", "art. 165 c.p.c.", "Costituzione dell'attore"),
    _n("cpc:166", f"art. 166 {_CPC}", "art. 166 c.p.c.", "Costituzione del convenuto"),
    _n("cpc:167", f"art. 167 {_CPC}", "art. 167 c.p.c.", "Comparsa di risposta"),
    _n("cpc:168bis", f"art. 168-bis {_CPC}", "art. 168-bis c.p.c.", "Designazione del giudice istruttore"),
    _n("cpc:171ter", f"art. 171-ter {_CPC}", "art. 171-ter c.p.c.", "Memorie integrative"),
    _n("cpc:281decies", f"art. 281-decies {_CPC}", "art. 281-decies c.p.c.", "Procedimento semplificato di cognizione"),
    _n("cpc:281undecies", f"art. 281-undecies {_CPC}", "art. 281-undecies c.p.c.", "Forma della domanda"),
    _n("cpc:325", f"art. 325 {_CPC}", "art. 325 c.p.c.", "Termini per le impugnazioni"),
    _n("cpc:327", f"art. 327 {_CPC}", "art. 327 c.p.c.", "Decadenza dall'impugnazione"),
    _n("cpc:409", f"art. 409 {_CPC}", "art. 409 c.p.c.", "Controversie individuali di lavoro"),
    _n("cpc:410", f"art. 410 {_CPC}", "art. 410 c.p.c.", "Tentativo di conciliazione"),
    _n("cpc:413", f"art. 413 {_CPC}", "art. 413 c.p.c.", "Giudice competente"),
    _n("cpc:414", f"art. 414 {_CPC}", "art. 414 c.p.c.", "Forma della domanda"),
    _n("cpc:429", f"art. 429 {_CPC}", "art. 429 c.p.c.", "Pronuncia della sentenza"),
    _n("cpc:434", f"art. 434 {_CPC}", "art. 434 c.p.c.", "Deposito del ricorso in appello"),
    _n("cpc:447bis", f"art. 447-bis {_CPC}", "art. 447-bis c.p.c.", "Norme applicabili alle controversie in materia di locazione"),
    _n("cpc:473bis", f"art. 473-bis {_CPC}", "art. 473-bis c.p.c.", "Ambito di applicazione"),
    _n("cpc:473bis11", f"art. 473-bis.11 {_CPC}", "art. 473-bis.11 c.p.c.", "Competenza per territorio"),
    _n("cpc:473bis12", f"art. 473-bis.12 {_CPC}", "art. 473-bis.12 c.p.c.", "Forma della domanda"),
    _n("cpc:473bis49", f"art. 473-bis.49 {_CPC}", "art. 473-bis.49 c.p.c.", "Cumulo di domande di separazione e divorzio"),
    _n("cpc:479", f"art. 479 {_CPC}", "art. 479 c.p.c.", "Notificazione del titolo esecutivo e del precetto"),
    _n("cpc:480", f"art. 480 {_CPC}", "art. 480 c.p.c.", "Forma del precetto"),
    _n("cpc:481", f"art. 481 {_CPC}", "art. 481 c.p.c.", "Cessazione dell'efficacia del precetto"),
    _n("cpc:482", f"art. 482 {_CPC}", "art. 482 c.p.c.", "Termine ad adempiere"),
    _n("cpc:617", f"art. 617 {_CPC}", "art. 617 c.p.c.", "Forma dell'opposizione agli atti esecutivi"),
    _n("cpc:633", f"art. 633 {_CPC}", "art. 633 c.p.c.", "Condizioni di ammissibilità"),
    _n("cpc:634", f"art. 634 {_CPC}", "art. 634 c.p.c.", "Prova scritta"),
    _n("cpc:637", f"art. 637 {_CPC}", "art. 637 c.p.c.", "Giudice competente"),
    _n("cpc:641", f"art. 641 {_CPC}", "art. 641 c.p.c.", "Accoglimento della domanda"),
    _n("cpc:642", f"art. 642 {_CPC}", "art. 642 c.p.c.", "Esecuzione provvisoria"),
    _n("cpc:644", f"art. 644 {_CPC}", "art. 644 c.p.c.", "Mancata notificazione del decreto"),
    _n("cpc:645", f"art. 645 {_CPC}", "art. 645 c.p.c.", "Opposizione"),
    _n("cpc:657", f"art. 657 {_CPC}", "art. 657 c.p.c.", "Intimazione di licenza e di sfratto"),
    _n("cpc:658", f"art. 658 {_CPC}", "art. 658 c.p.c.", "Intimazione di sfratto per morosità"),
    _n("cpc:660", f"art. 660 {_CPC}", "art. 660 c.p.c.", "Forma dell'intimazione"),
    _n("cpc:661", f"art. 661 {_CPC}", "art. 661 c.p.c.", "Giudice competente"),
    # Codice penale e di procedura penale
    _n("cp:124", f"art. 124 {_CP}", "art. 124 c.p.", "Termine per proporre la querela"),
    _n("cpp:585", f"art. 585 {_CPP}", "art. 585 c.p.p.", "Termini per l'impugnazione"),
    # Leggi speciali
    _n("dl132:3", "art. 3 d.l. 132/2014", "art. 3 d.l. 132/2014", "Improcedibilità"),
    _n("dlgs28:5", "art. 5 d.lgs. 28/2010", "art. 5 d.lgs. 28/2010", "Condizione di procedibilità e rapporti con il processo"),
    _n("l742:1", "art. 1 l. 742/1969", "art. 1 l. 742/1969", "Sospensione dei termini nel periodo feriale"),
    _n("l742:3", "art. 3 l. 742/1969", "art. 3 l. 742/1969", "Esclusioni"),
    _n("l392:5", "art. 5 l. 392/1978", "art. 5 l. 392/1978", "Inadempimento del conduttore"),
    _n("l392:55", "art. 55 l. 392/1978", "art. 55 l. 392/1978", "Termine per il pagamento dei canoni scaduti"),
    _n("l604:6", "art. 6 l. 604/1966", "art. 6 l. 604/1966", "Impugnazione del licenziamento"),
    _n("l898:3", "art. 3 l. 898/1970", "art. 3 l. 898/1970", "Casi di scioglimento"),
    _n("dlgs206:66bis", "art. 66-bis d.lgs. 206/2005", "art. 66-bis d.lgs. 206/2005 (codice del consumo)", "Foro competente"),
    _n("cpa:29", "art. 29 d.lgs. 104/2010", "art. 29 c.p.a.", "Azione di annullamento"),
    _n("cpa:41", "art. 41 d.lgs. 104/2010", "art. 41 c.p.a.", "Notificazione del ricorso e suoi destinatari"),
    _n("dlgs546:21", "art. 21 d.lgs. 546/1992", "art. 21 d.lgs. 546/1992", "Termine per la proposizione del ricorso"),
    _n("dpr1199:9", "art. 9 d.p.r. 1199/1971", "art. 9 d.P.R. 1199/1971", "Termine del ricorso straordinario"),
    _n("dpr115:30", "art. 30 d.p.r. 115/2002", "art. 30 d.P.R. 115/2002", "Anticipazione forfettaria"),
    _n("dpr115:13", "art. 13 d.p.r. 115/2002", "art. 13 d.P.R. 115/2002", "Contributo unificato"),
)}


def normalizza(testo: str) -> str:
    """Confronto robusto: minuscole, senza accenti né apostrofi tipografici, spazi singoli."""
    base = unicodedata.normalize("NFKD", str(testo or "").replace("’", "'").replace("`", "'").lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    # Normattiva scrive gli accenti finali con l'apostrofo («e'», «puo'»): l'apostrofo non conta nel confronto.
    return " ".join(base.replace("'", "").split())


def piano(testo: str) -> str:
    """Per riconoscere domande e fatti: come ``normalizza`` ma l'apostrofo separa le parole («l'art.» → «l art.»)."""
    return normalizza(str(testo or "").replace("'", " ").replace("’", " "))


@dataclass(frozen=True)
class TestoNorma:
    chiave: str
    citazione: str
    testo: str
    url: str
    aggiornamento: str    # data dell'aggiornamento Normattiva dell'archivio (gg/mm/aaaa), se nota
    vigente: bool
    origine: str          # «istantanea dell'archivio» | «archivio dal vivo»


@lru_cache(maxsize=1)
def _istantanea() -> dict[str, dict[str, Any]]:
    try:
        return json.loads(ISTANTANEA.read_text(encoding="utf-8")).get("norme", {})
    except (OSError, ValueError):
        return {}


def _archivio_dal_vivo(norma: Norma) -> dict[str, Any] | None:
    percorso = os.environ.get("PCT_NORMATTIVA_DB", "")
    if not percorso or os.environ.get("LEX_HARNESS_ARCHIVIO_VIVO", "1") == "0":
        return None
    try:
        from web.services.ricerca_legale_norma_citata import estremi, norma_citata

        e = estremi(norma.estremi)
        scheda = norma_citata(Path(percorso), e) if e else None
    except Exception:
        return None
    if not scheda or not scheda.get("normaCitata"):
        return None
    return leggi_scheda(scheda)


def leggi_scheda(scheda: dict[str, Any]) -> dict[str, Any]:
    """Dalla scheda di ``norma_citata`` ai campi conservati nell'istantanea."""
    avvisi = " ".join(scheda.get("operationalChecks") or [])
    agg = re.search(r"aggiornamento del (\d{2}/\d{2}/\d{4})", avvisi)
    testo = str(scheda.get("officialContext") or "")
    return {"testo": testo, "url": str(scheda.get("sourceHref") or ""), "titolo": str(scheda.get("title") or ""),
            "aggiornamento": agg.group(1) if agg else "", "vigente": scheda.get("approvalTone") == "success",
            "sha256": hashlib.sha256(testo.encode()).hexdigest()}


_CACHE_VIVO: dict[str, dict[str, Any] | None] = {}


def testo_norma(chiave: str) -> TestoNorma | None:
    norma = NORME.get(chiave)
    if norma is None:
        return None
    riga = _istantanea().get(chiave)
    origine = "istantanea dell'archivio"
    if not riga or not riga.get("testo"):
        if chiave not in _CACHE_VIVO:
            _CACHE_VIVO[chiave] = _archivio_dal_vivo(norma)
        riga, origine = _CACHE_VIVO[chiave], "archivio dal vivo"
    if not riga or not riga.get("testo"):
        return None
    return TestoNorma(chiave, norma.citazione, str(riga["testo"]), str(riga.get("url") or ""),
                      str(riga.get("aggiornamento") or ""), bool(riga.get("vigente")), origine)


def contiene(chiave: str, ancora: str) -> bool:
    """L'ancora compare nel testo vigente dell'articolo? (spazi, accenti e apostrofi normalizzati)."""
    t = testo_norma(chiave)
    return bool(t and ancora and normalizza(ancora) in normalizza(t.testo))


_NUMERI = {"cinquemila": 5000, "diecimila": 10000, "quindicimila": 15000, "ventimila": 20000,
           "venticinquemila": 25000, "trentamila": 30000, "cinquantamila": 50000, "centomila": 100000}


def importo_in_lettere_dopo(chiave: str, prefisso: str) -> int | None:
    """Legge dal testo vigente un importo scritto in lettere dopo le parole indicate («non superiore a diecimila euro»)."""
    t = testo_norma(chiave)
    if t is None:
        return None
    m = re.search(re.escape(normalizza(prefisso)) + r"\s+(?:a\s+)?(?:euro\s+)?([a-z]+)\s+euro", normalizza(t.testo))
    if m and m.group(1) in _NUMERI:
        return _NUMERI[m.group(1)]
    m = re.search(re.escape(normalizza(prefisso)) + r"\s+(?:a\s+)?(?:euro\s+)?(\d{1,3}(?:\.\d{3})+|\d+)", normalizza(t.testo))
    return int(m.group(1).replace(".", "")) if m else None


def comma_con(chiave: str, ancora: str, *, massimo: int = 600) -> str:
    """Il periodo del testo vigente che contiene l'ancora, per riportarlo fra virgolette."""
    t = testo_norma(chiave)
    if t is None:
        return ""
    piano = " ".join(t.testo.split())
    pos = normalizza(piano).find(normalizza(ancora))
    if pos < 0:
        return ""
    inizio = max(piano.rfind(". ", 0, pos), piano.rfind("; ", 0, pos), piano.rfind(": ", 0, pos))
    inizio = 0 if inizio < 0 else inizio + 2
    fine = piano.find(".", pos + len(ancora))
    fine = len(piano) if fine < 0 else fine + 1
    estratto = piano[inizio:fine].strip()
    return estratto if len(estratto) <= massimo else estratto[: massimo - 1].rstrip() + "…"
