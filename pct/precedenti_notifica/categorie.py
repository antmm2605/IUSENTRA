"""Categorie dei precedenti di notifica: chi era la controparte, che atto, dove è stato notificato.

Solo categorie: il nome della parte e l'indirizzo PEC non escono da qui. Il domicilio si ricava dal dominio
dell'indirizzo a cui la PEC è stata consegnata (ricevuta di avvenuta consegna, art. 6 D.P.R. 68/2005).
"""

from __future__ import annotations

import re

AVVOCATURA_STATO = "avvocatura_stato"
SEDE_ISTITUTO_SCOLASTICO = "sede_istituto_scolastico"
SEDE_MINISTERO = "sede_ministero"
SEDE_ENTE = "sede_ente"
DIFENSORE = "difensore"
PUBBLICI_ELENCHI = "pubblici_elenchi"
NON_DETERMINATO = "non_determinato"

ETICHETTE_DOMICILIO = {
    AVVOCATURA_STATO: "presso l'Avvocatura dello Stato",
    SEDE_ISTITUTO_SCOLASTICO: "presso la sede dell'istituto scolastico",
    SEDE_MINISTERO: "presso la sede del Ministero o dell'Ufficio scolastico",
    SEDE_ENTE: "presso la sede dell'ente",
    DIFENSORE: "presso il difensore",
    PUBBLICI_ELENCHI: "all'indirizzo della parte nei pubblici elenchi",
}

# Il pubblico elenco da cui prendere l'indirizzo del destinatario ATTUALE (chiavi di pct.notifiche_legali.PUBLIC_PEC_REGISTERS).
REGISTRO_PER_DOMICILIO = {
    AVVOCATURA_STATO: "registro_ppaa",
    SEDE_ISTITUTO_SCOLASTICO: "registro_ppaa",
    SEDE_MINISTERO: "registro_ppaa",
    SEDE_ENTE: "registro_ppaa",
    DIFENSORE: "reginde",
    PUBBLICI_ELENCHI: "ini_pec",
}

_SCUOLA = re.compile(
    r"\b(?:istituto\s+(?:comprensivo|d['’]istruzione|di\s+istruzione|superiore|tecnico|professionale|statale|magistrale|omnicomprensivo)"
    r"|liceo|circolo\s+didattico|scuola|convitto|educandato|direzione\s+didattica|cpia)\b",
    re.IGNORECASE,
)
_NON_STATALE = re.compile(r"paritari|privat|s\.?r\.?l|s\.?p\.?a|onlus|cooperativ", re.IGNORECASE)
_STATALE = re.compile(r"\b(?:ministero|ministro|presidenza\s+del\s+consiglio|prefettura|questura|ufficio\s+scolastico|"
                      r"agenzia\s+del\s+demanio|avvocatura)\b", re.IGNORECASE)
_PA = re.compile(r"\b(?:comune|regione|provincia|citt[aà]\s+metropolitana|inps|inail|azienda\s+sanitaria|asl|asp|universit[aà]|agenzia|istituto|autorit[aà])\b",
                 re.IGNORECASE)
_ATTI = (
    ("decreto_ingiuntivo", re.compile(r"decreto.{0,12}ingiunt|ingiunzione", re.IGNORECASE)),
    ("sentenza", re.compile(r"sentenz", re.IGNORECASE)),
    ("ordinanza", re.compile(r"ordinanz", re.IGNORECASE)),
    ("decreto", re.compile(r"decret", re.IGNORECASE)),
    ("ricorso", re.compile(r"ricors", re.IGNORECASE)),
    ("atto_di_citazione", re.compile(r"citazion", re.IGNORECASE)),
    ("precetto", re.compile(r"precett", re.IGNORECASE)),
)
_ACCESSORI = re.compile(r"relata|procura|daticert|smime|postacert|attestazion", re.IGNORECASE)


def categoria_controparte(nome: str) -> str:
    """Categoria della parte destinataria (mai il nome)."""
    testo = " ".join(str(nome or "").split())
    if not testo:
        return "non_indicata"
    if _SCUOLA.search(testo) and not _NON_STATALE.search(testo):
        return "istituto_scolastico_statale"
    if _STATALE.search(testo):
        return "amministrazione_statale"
    if _PA.search(testo):
        return "ente_pubblico_non_statale"
    return "parte_privata"


def tipo_atto(testi: list[str] | tuple[str, ...]) -> str:
    """Il tipo di atto notificato dai nomi dei file o dall'etichetta del catalogo (relata e ricevute escluse)."""
    testo = " ".join(t for t in testi if t and not _ACCESSORI.search(t))
    for etichetta, schema in _ATTI:
        if schema.search(testo):
            return etichetta
    return NON_DETERMINATO


def domicilio_da_indirizzo(indirizzo: str) -> str:
    """La categoria del domicilio dal dominio della PEC a cui la notifica è stata consegnata."""
    valore = str(indirizzo or "").strip().strip("<>").casefold()
    if "@" not in valore:
        return NON_DETERMINATO
    dominio = valore.rsplit("@", 1)[-1]
    if dominio.endswith("avvocaturastato.it"):
        return AVVOCATURA_STATO
    if dominio.endswith("pec.istruzione.it"):
        return SEDE_ISTITUTO_SCOLASTICO
    if dominio.endswith("istruzione.it"):
        return SEDE_MINISTERO
    if "avvocat" in dominio or "ordineavv" in dominio:
        return DIFENSORE
    if dominio.endswith("gov.it") or re.search(r"comune|regione|provincia|inps|inail|asl|asp", dominio):
        return SEDE_ENTE
    return NON_DETERMINATO


def domicilio_normativo(presso: str) -> str:
    """La categoria del domicilio indicato dalla regola del codice (testo «presso» di pct.obblighi_notifica)."""
    testo = str(presso or "").casefold()
    if "avvocatura" in testo and "difensore letto" not in testo:
        return AVVOCATURA_STATO
    if "presso la sede" in testo:
        return SEDE_ENTE
    if "difensore costituito" in testo:
        return DIFENSORE
    if "pubblici elenchi" in testo:
        return PUBBLICI_ELENCHI
    return NON_DETERMINATO


def compatibili(normativo: str, precedente: str) -> bool:
    """La sede dell'istituto o del Ministero è una «sede dell'ente» ai fini del confronto con la regola."""
    if normativo == SEDE_ENTE:
        return precedente in {SEDE_ENTE, SEDE_ISTITUTO_SCOLASTICO, SEDE_MINISTERO}
    return normativo == precedente
