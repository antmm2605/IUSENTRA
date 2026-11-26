"""Termini sottratti per legge alla sospensione feriale, riconosciuti dalla norma del modello di termine.

Il motore dei termini (``pct/termini_processuali.py``) applica la sospensione dal 1° al 31 agosto (art. 1 L. 742/1969)
quando il modello la prevede. I modelli salvati negli archivi degli studi (compresi quelli importati dalla Guida
Pratica, con codice ``GP_…``) nascono quasi tutti con la sospensione attiva e non si aggiornano da soli: un reclamo
cautelare importato con la sospensione attiva scadeva 31 giorni dopo il dovuto. Questa regola si applica a ogni
calcolo, qualunque sia l'archivio di provenienza del modello, e toglie la sospensione quando la norma citata dal
modello appartiene a una materia che la legge esclude. Resta la forzatura esplicita ``force_ferial_suspension``.

Testo vigente letto nella biblioteca vigente del software (codici_leggi.sqlite del 21/11/2026):
- art. 3 L. 7 ottobre 1969, n. 742: «In materia civile, l'articolo 1 non si applica alle cause ed ai procedimenti
  indicati nell'articolo 92 dell'ordinamento giudiziario 30 gennaio 1941, n. 12, nonché alle controversie previste
  dagli articoli 429 e 459 del codice di procedura civile» (oggi lavoro, art. 409, e previdenza, art. 442 c.p.c.);
- art. 92 R.D. 30 gennaio 1941, n. 12: cause relative ad alimenti, procedimenti cautelari, procedimenti in materia di
  amministrazione di sostegno, interdizione e inabilitazione, ordini di protezione contro gli abusi familiari, sfratto,
  opposizione all'esecuzione, dichiarazione e revoca dei fallimenti, cause dichiarate urgenti dal giudice;
- art. 9, comma 1, d.lgs. 12 gennaio 2019, n. 14 (codice della crisi): la sospensione feriale «non si applica ai
  procedimenti disciplinati dal presente codice, salvo che esso non disponga diversamente» (la dispongono gli
  artt. 201, comma 10, e 207, comma 16: accertamento del passivo e impugnazioni dello stato passivo);
- art. 36-bis R.D. 16 marzo 1942, n. 267: i termini processuali degli artt. 26 e 36 l. fall. (reclami) non sono
  soggetti alla sospensione feriale;
- art. 35-bis, comma 14, d.lgs. 28 gennaio 2008, n. 25: la sospensione non opera nei procedimenti in materia di
  protezione internazionale;
- art. 203, comma 1, d.lgs. 30 aprile 1992, n. 285: il ricorso al prefetto è un ricorso amministrativo, non un termine
  processuale «relativo alle giurisdizioni ordinarie ed a quelle amministrative» (art. 1 L. 742/1969).

Il giudizio di merito dopo la misura cautelare (art. 669-octies c.p.c.) non è un procedimento cautelare: non si
esclude qui (il modello nativo ``CIV_MERITO_669_OCTIES`` lo segnala come dubbio). L'opposizione agli atti esecutivi
(art. 617 c.p.c.) non è nominata dall'art. 92: resta governata dal proprio modello.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_L742_OG92 = "art. 3 L. 742/1969; art. 92 R.D. 12/1941"


@dataclass(frozen=True)
class EsclusioneFeriale:
    codice: str
    motivo: str
    norma: str
    # «excluded»: termine processuale sottratto alla sospensione; «not_applicable»: termine non processuale;
    # «manual_review»: esclusione controversa, calcolata senza sospensione (data più prudente) e segnalata.
    politica: str = "excluded"

    @property
    def spiegazione(self) -> str:
        if self.politica == "manual_review":
            return f"Sospensione feriale da verificare: {self.motivo} ({self.norma})."
        return f"Sospensione feriale non applicata: {self.motivo} ({self.norma})."


# Il giudizio di merito e l'esecuzione della misura non sono il procedimento cautelare (art. 669-octies c.p.c.).
_MERITO = re.compile(r"\bmerito\b|669[- ]?octies|\b481\b|\binizio (?:della )?esecuzione\b")
_CPC = re.compile(r"c\.?\s?p\.?\s?c\.?")

_REGOLE: tuple[tuple[re.Pattern[str], EsclusioneFeriale], ...] = (
    (re.compile(r"669[- ]?(?:bis|ter|quater|quinquies|sexies|septies|decies|undecies|duodecies|terdecies)\b|"
                r"\bcautelar|\bsequestr|\bart\.?\s*700\b|\b700 c\.?p\.?c|denuncia di nuova opera|danno temuto|"
                r"istruzione preventiva"),
     EsclusioneFeriale("ferial_excluded_cautelare", "procedimento cautelare", _L742_OG92)),
    (re.compile(r"amministrazione di sostegno|\binterdizion|\binabilitazion|720[- ]?bis|\bads\b"),
     EsclusioneFeriale("ferial_excluded_ads_interdizione",
                       "amministrazione di sostegno, interdizione o inabilitazione", _L742_OG92)),
    (re.compile(r"\baliment"), EsclusioneFeriale("ferial_excluded_alimenti", "causa relativa ad alimenti", _L742_OG92)),
    (re.compile(r"ordin\w* di protezione|abusi familiari|342[- ]?(?:bis|ter)|473[- ]?bis\.?\s?(?:69|70|71)\b"),
     EsclusioneFeriale("ferial_excluded_ordini_protezione", "ordini di protezione contro gli abusi familiari", _L742_OG92)),
    (re.compile(r"\bsfratt|convalida di (?:licenza|sfratto)|\bart\w*\.?\s*6(?:5[7-9]|6[0-8])\b(?![- ]?(?:bis|ter))"),
     EsclusioneFeriale("ferial_excluded_sfratto", "procedimento di sfratto", _L742_OG92)),
    (re.compile(r"opposizione all'?\s*esecuzione|\b61[56]\b(?![- ]?(?:bis|ter))"),
     EsclusioneFeriale("ferial_excluded_opposizione_esecuzione", "opposizione all'esecuzione", _L742_OG92)),
    (re.compile(r"(?:dichiarazione|dichiarativa|revoca) (?:di |del )?fallimento|sentenza dichiarativa di fallimento"),
     EsclusioneFeriale("ferial_excluded_fallimento", "dichiarazione o revoca del fallimento", _L742_OG92)),
    (re.compile(r"\bl\.?\s?f(?:all)?\.?\b.{0,20}\b(?:26|36)\b|\b(?:26|36)\b.{0,12}\bl\.?\s?f(?:all)?\.?(?:\s|$|;|,)"),
     EsclusioneFeriale("ferial_excluded_reclamo_lf", "reclamo degli artt. 26 o 36 della legge fallimentare",
                       "art. 36-bis R.D. 267/1942")),
    (re.compile(r"protezione internazionale|35[- ]?bis.{0,20}25/2008|d\.?\s?lgs\.?\s*(?:n\.\s*)?25/2008"),
     EsclusioneFeriale("ferial_excluded_protezione_internazionale", "procedimento di protezione internazionale",
                       "art. 35-bis, comma 14, d.lgs. 25/2008")),
    (re.compile(r"rito del lavoro|controversi\w* (?:individuali )?di lavoro|previdenz|"
                r"\bart\w*\.?\s*(?:409|41\d|42\d|43\d|44[0-7])\b(?![- ]?(?:bis|ter))"),
     EsclusioneFeriale("labour_no_ferial_suspension_art_3_l742_1969", "controversia di lavoro o di previdenza",
                       "art. 3 L. 742/1969")),
    (re.compile(r"\b203\b.{0,40}(?:285/1992|c\.?\s?d\.?\s?s\b|codice della strada)|ricorso al prefetto"),
     EsclusioneFeriale("ferial_not_applicable_ricorso_amministrativo",
                       "il ricorso al prefetto è un ricorso amministrativo, non un termine processuale",
                       "art. 203 d.lgs. 285/1992; art. 1 L. 742/1969", politica="not_applicable")),
)
# Inizio del merito dopo la misura cautelare: il modello nativo CIV_MERITO_669_OCTIES (pct/termini_riti.py) lo tratta
# come dubbio e propone la data senza sospensione, la più prudente; i modelli importati seguono la stessa regola.
_OCTIES = re.compile(r"669[- ]?octies")
_DUBBIO_OCTIES = EsclusioneFeriale("ferial_doubt_669_octies",
                                   "sospensione feriale controversa per l'inizio del giudizio di merito dopo la misura "
                                   "cautelare: data proposta senza sospensione, la più prudente",
                                   "art. 669-octies c.p.c.; art. 3 L. 742/1969", politica="manual_review")
_GUIDA_CAUTELARE = re.compile(r"cautelar|\bart \d*\s*700\b|\b700 c p c\b|sequestro|denuncia di nuova opera|danno temuto")
_CCII = re.compile(r"d\.?\s?lgs\.?\s*(?:n\.\s*)?14/2019|\bccii\b|codice della crisi")
_CCII_SOSPESI = re.compile(r"\b20[1-7]\b")  # artt. 201, comma 10, e 207, comma 16: accertamento e impugnazioni del passivo
_ESCLUSIONE_CCII = EsclusioneFeriale("ferial_excluded_ccii", "procedimento del codice della crisi d'impresa",
                                     "art. 9, comma 1, d.lgs. 14/2019")
# Le regole che cercano un numero d'articolo valgono solo se il modello cita il c.p.c. (o non cita nessun codice).
_CON_ARTICOLO_CPC = {"ferial_excluded_sfratto", "ferial_excluded_opposizione_esecuzione",
                     "labour_no_ferial_suspension_art_3_l742_1969"}
_ALTRO_CODICE = re.compile(r"c\.?\s?p\.?\s?p\.?|c\.?\s?p\.?\s?a\.?|d\.?\s?lgs|d\.?\s?p\.?\s?r|\bl\.\s*\d|\blegge\b|c\.?\s?c\.(?!\s?p)")


_LOCATIZIO = re.compile(r"447[- ]?bis")


def rito_locatizio(reference_law: str) -> bool:
    """Vero se il modello è del rito delle locazioni (art. 447-bis c.p.c.), che usa le forme del rito del lavoro.

    L'art. 3 L. 742/1969 esclude solo le controversie di lavoro e di previdenza («articoli 429 e 459», oggi 409 e 442
    c.p.c.): le cause di locazione restano soggette alla sospensione feriale, salvo lo sfratto (art. 92 R.D. 12/1941).
    """
    return bool(_LOCATIZIO.search(_testo(reference_law)))


def _testo(*parti: Any) -> str:
    return " ".join(" ".join(str(parte or "").lower().replace("’", "'").split()) for parte in parti)


def esclusione_per_norma(name: str, reference_law: str, matter_type: str = "", guida: str = "") -> EsclusioneFeriale | None:
    """L'esclusione dalla sospensione feriale che la legge stabilisce per la norma del modello; None se non c'è.

    ``guida``: codice o nome della scheda della Guida Pratica da cui il modello è stato importato; serve solo per il
    «Reclamo» senza norma importato da una scheda cautelare (artt. 700, 670, 671 c.p.c.).
    """
    if str(matter_type or "").strip().lower() in {"penal", "penale"}:
        return None  # materia penale: art. 2 L. 742/1969, con le sue condizioni (calcolatore dei termini penali)
    norma = _testo(reference_law)
    testo = _testo(name, reference_law)
    if _OCTIES.search(norma):
        return _DUBBIO_OCTIES
    nome = _testo(name)
    if nome.startswith("reclamo") and not norma and _GUIDA_CAUTELARE.search(_testo(guida).replace("_", " ")):
        return _REGOLE[0][1]
    if _CCII.search(norma):
        return None if _CCII_SOSPESI.search(norma) else _ESCLUSIONE_CCII
    for espressione, esclusione in _REGOLE:
        if esclusione.codice == "ferial_excluded_cautelare" and _MERITO.search(testo):
            continue
        if esclusione.codice == "labour_no_ferial_suspension_art_3_l742_1969" and _LOCATIZIO.search(norma):
            continue
        bersaglio = testo
        if esclusione.codice in _CON_ARTICOLO_CPC:
            if norma and not _CPC.search(norma) and _ALTRO_CODICE.search(norma):
                # Il numero d'articolo appartiene a un'altra fonte: conta solo la descrizione del modello.
                bersaglio = _testo(name)
        if espressione.search(bersaglio):
            return esclusione
    return None


__all__ = ["EsclusioneFeriale", "esclusione_per_norma", "rito_locatizio"]
