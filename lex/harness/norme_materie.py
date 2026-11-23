"""Norme delle fattispecie per materia (cartella ``fattispecie/materia_*.py``).

Ogni voce: (chiave, estremi, citazione, rubrica, frammento URN della biblioteca, numero dell'articolo nella biblioteca).
Il testo vigente si legge dalla biblioteca di consultazione (testo Normattiva vigente alla data) con
``scripts/lex_harness_norme_materie.py`` e si conserva in ``dati/norme_vigenti_materie.json``; ``norme.py`` aggiunge
queste voci al catalogo senza sostituire quelle già presenti.
"""
from __future__ import annotations

_CC = ("r.d. 262/1942", "c.c.", "regio.decreto:1942-03-16;262")
_CPC = ("r.d. 1443/1940", "c.p.c.", "regio.decreto:1940-10-28;1443")
_CP = ("r.d. 1398/1930", "c.p.", "regio.decreto:1930-10-19;1398")
_CPP = ("d.p.r. 447/1988", "c.p.p.", "decreto.del.presidente.della.repubblica:1988-09-22;447")
_CPA = ("d.lgs. 104/2010", "c.p.a.", "decreto.legislativo:2010-07-02;104")

ATTI = {
    "cc": _CC, "cpc": _CPC, "cp": _CP, "cpp": _CPP, "cpa": _CPA,
    "dispattcc": ("r.d. 318/1942", "disp. att. c.c.", "regio.decreto:1942-03-30;318"),
    "dlgs165": ("d.lgs. 165/2001", "d.lgs. 165/2001", "decreto.legislativo:2001-03-30;165"),
    "l107": ("l. 107/2015", "l. 107/2015", "legge:2015-07-13;107"),
    "dl669": ("d.l. 669/1996", "d.l. 669/1996", "decreto.legge:1996-12-31;669"),
    "l88": ("l. 88/1989", "l. 88/1989", "legge:1989-03-09;88"),
    "l724": ("l. 724/1994", "l. 724/1994", "legge:1994-12-23;724"),
    "l412": ("l. 412/1991", "l. 412/1991", "legge:1991-12-30;412"),
    "dlgs297": ("d.lgs. 297/1994", "d.lgs. 297/1994", "decreto.legislativo:1994-04-16;297"),
    "dpr115": ("d.p.r. 115/2002", "d.P.R. 115/2002", "decreto.del.presidente.della.repubblica:2002-05-30;115"),
    "dpr639": ("d.p.r. 639/1970", "d.P.R. 639/1970", "decreto.del.presidente.della.repubblica:1970-04-30;639"),
    "dlgs81": ("d.lgs. 81/2015", "d.lgs. 81/2015", "decreto.legislativo:2015-06-15;81"),
    "l742": ("l. 742/1969", "l. 742/1969", "legge:1969-10-07;742"),
}


def _art(numero: str) -> str:
    """«473-bis.12» → «473bis.12» (numerazione della biblioteca)."""
    return numero.replace("-", "")


def _v(atto: str, numero: str, rubrica: str) -> tuple[str, str, str, str, str, str]:
    estremi_atto, sigla, urn = ATTI[atto]
    chiave = f"{atto}:{_art(numero).replace('.', '')}"
    return (chiave, f"art. {numero} {estremi_atto}", f"art. {numero} {sigla}", rubrica, urn, _art(numero))


NORME_MATERIE: tuple[tuple[str, str, str, str, str, str], ...] = (
    # ------------------------------------------------------------ pubblico impiego
    _v("dlgs165", "63", "Controversie relative ai rapporti di lavoro"),
    _v("dlgs165", "45", "Trattamento economico"),
    _v("dlgs165", "36", "Personale a tempo determinato o assunto con forme di lavoro flessibile"),
    _v("cpc", "413", "Giudice competente"),
    _v("cpc", "417-bis", "Difesa delle pubbliche amministrazioni"),
    _v("cpc", "26-bis", "Foro relativo all'espropriazione forzata di crediti"),
    _v("cpc", "410", "Tentativo di conciliazione"),
    _v("cpc", "414", "Forma della domanda"),
    _v("cc", "2948", "Prescrizione di cinque anni"),
    _v("cc", "2946", "Prescrizione ordinaria"),
    _v("l107", "1", "Carta elettronica per l'aggiornamento e la formazione del docente (comma 121)"),
    _v("dl669", "14", "Esecuzione forzata nei confronti di pubbliche amministrazioni"),
    _v("l724", "22", "Disposizioni in materia di trattamenti economici (comma 36: divieto di cumulo)"),
    _v("l412", "16", "Disposizioni varie in materia previdenziale (comma 6: interessi e rivalutazione)"),
    _v("dlgs297", "485", "Personale docente: riconoscimento del servizio non di ruolo"),
    _v("cpa", "112", "Disposizioni generali sul giudizio di ottemperanza"),
    _v("cpa", "113", "Giudice dell'ottemperanza"),
    _v("cpa", "114", "Procedimento di ottemperanza"),
    _v("cpc", "480", "Forma del precetto"),
    _v("cpc", "543", "Forma del pignoramento presso terzi"),
    _v("dpr115", "9", "Contributo unificato"),
    # ------------------------------------------------------------ lavoro e previdenza
    _v("cc", "2113", "Rinunzie e transazioni"),
    _v("cc", "2087", "Tutela delle condizioni di lavoro"),
    _v("cc", "2103", "Prestazione del lavoro"),
    _v("cpc", "411", "Processo verbale di conciliazione"),
    _v("cpc", "412-ter", "Altre modalità di conciliazione e arbitrato previste dalla contrattazione collettiva"),
    _v("cpc", "442", "Controversie in materia di previdenza e di assistenza obbligatorie"),
    _v("cpc", "443", "Rilevanza del procedimento amministrativo"),
    _v("cpc", "444", "Giudice competente"),
    _v("cpc", "445-bis", "Accertamento tecnico preventivo obbligatorio"),
    _v("dpr639", "47", "Azione giudiziaria e decadenza"),
    _v("l88", "46", "Contenzioso in materia di prestazioni"),
)
