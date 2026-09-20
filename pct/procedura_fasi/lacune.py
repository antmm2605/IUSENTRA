"""Le lacune della conoscenza procedurale: ciò che il fascicolo cita e le schede non coprono ancora.

Un rito senza scheda, un canale sconosciuto, una norma citata da una scadenza o
da una PEC e assente dal registro delle fonti: il software non inventa, ma non
tace. Le lacune vengono dichiarate nella lettura, con la chiave esatta da
cercare, così che il presidio normativo (aggiornamenti legali, ricerca
pubblica governata di Lex) possa colmarle con fonti ufficiali.
"""

from __future__ import annotations

import re
from typing import Any

from .depositi import canale_deposito
from .fonti import FONTI
from .riti import rito_per_fascicolo

# Due accortezze contro il backtracking esponenziale (ReDoS): il testo in
# ingresso arriva da documenti e PEC, quindi non e' fidato.
# 1. `\d[\w-]*` invece di `\d+[\w-]*`: le due forme riconoscono le stesse
#    stringhe, ma la prima non lascia al motore piu' modi di dividere «00».
# 2. la congiunzione «e» vale solo se separata da spazi, e la virgola solo
#    come virgola: cosi' «artt. 1 e 2» e «artt. 1,2» restano riconosciuti
#    mentre «1e0» smette di essere un elenco — che del resto non lo e' mai
#    stato in una citazione forense.
_RIFERIMENTO_NORMATIVO = re.compile(
    r"\b(?:artt?\.?\s*\d[\w-]*(?:(?:\s*,\s*|\s+e\s+)\d[\w-]*)*\s*(?:c\.p\.c\.|c\.p\.p\.|c\.p\.a\.|c\.c\.|disp\.\s*att\.\s*c\.p\.c\.|d\.?lgs\.?\s*\d+/\d{4}|l\.\s*\d+/\d{4}|d\.?m\.?\s*\d+/\d{4}|d\.?p\.?r\.?\s*\d+/\d{4}|d\.?l\.?\s*\d+/\d{4}))",
    re.IGNORECASE,
)


def _norme_registrate() -> set[str]:
    return {_chiave(voce["norma"]) for voce in FONTI.values()}


def _chiave(testo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(testo or "").lower().replace("artt.", "art.").replace("articolo", "art."))


def riferimenti_nel_testo(testo: str) -> list[str]:
    """I riferimenti normativi scritti in un testo («art. 171-ter c.p.c.», «D.Lgs. 28/2010»)."""
    return [" ".join(m.group(0).split()) for m in _RIFERIMENTO_NORMATIVO.finditer(str(testo or ""))]


#: Un intervallo piu' lungo di cosi' non si espande articolo per articolo:
#: «artt. 1-500» e' un rinvio a un capo, non una citazione puntuale.
INTERVALLO_MASSIMO = 12

# «325-326» sono due articoli; «171-bis» e' un articolo solo. La differenza sta
# in cosa segue il trattino: una cifra o una parola.
_ELENCO_ARTICOLI = re.compile(r"\d[\w-]*(?:\s*,\s*|\s+e\s+)?")
_INTERVALLO = re.compile(r"^(\d+)-(\d+)$")


def _coda_normativa(norma: str) -> str:
    """Quello che viene dopo i numeri: «c.p.c.», «l. 742/1969»…"""
    resto = re.sub(r"^\s*artt?\.?\s*", "", str(norma or ""), flags=re.IGNORECASE)
    pezzi = re.split(r"^[\d\w\-,\s]*?(?=[a-zA-Z]\.)", resto, maxsplit=1)
    return (pezzi[-1] if pezzi else "").strip()


def articoli_citati(norma: str) -> list[str]:
    """Un riferimento composto, spezzato negli articoli che cita davvero.

    «artt. 325-326 c.p.c.» sono due articoli, e uno dei due — il 325 — sta gia'
    nel registro delle fonti verificate. Finche' la citazione veniva confrontata
    tutta intera, quell'articolo risultava mancante insieme all'altro: una
    lacuna dichiarata su una fonte che c'era.

    «art. 171-bis c.p.c.» invece e' un articolo solo: dopo il trattino c'e' una
    parola, non una cifra.
    """
    testo = str(norma or "").strip()
    coda = _coda_normativa(testo)
    if not coda:
        return [testo] if testo else []
    numeri_grezzi = re.sub(re.escape(coda) + r"$", "", testo).strip()
    numeri_grezzi = re.sub(r"^\s*artt?\.?\s*", "", numeri_grezzi, flags=re.IGNORECASE)
    pezzi = [p.strip() for p in re.split(r"\s*,\s*|\s+e\s+", numeri_grezzi) if p.strip()]
    if not pezzi:
        return [testo]
    articoli: list[str] = []
    for pezzo in pezzi:
        intervallo = _INTERVALLO.match(pezzo)
        if intervallo:
            primo, ultimo = int(intervallo.group(1)), int(intervallo.group(2))
            if primo <= ultimo and (ultimo - primo) < INTERVALLO_MASSIMO:
                articoli.extend(str(n) for n in range(primo, ultimo + 1))
                continue
            # Intervallo troppo ampio: si citano gli estremi, non il capo intero.
            articoli.extend([str(primo), str(ultimo)])
            continue
        articoli.append(pezzo)
    visti: set[str] = set()
    fuori: list[str] = []
    for articolo in articoli:
        voce = f"art. {articolo} {coda}".strip()
        if voce not in visti:
            visti.add(voce)
            fuori.append(voce)
    return fuori or [testo]


def lacune_conoscenza(
    *,
    tipo: str = "",
    tipo_procedimento: str = "",
    canale_operativo: str = "",
    riferimenti: list[str] | tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Le lacune: rito o canale senza scheda, norme citate e non registrate."""
    lacune: list[dict[str, Any]] = []
    rito = rito_per_fascicolo(tipo, tipo_procedimento)
    if not rito and (tipo or tipo_procedimento):
        chiave = " ".join(str(tipo_procedimento or tipo).split())
        lacune.append({
            "tipo": "rito",
            "chiave": chiave,
            "descrizione": f"Il rito «{chiave}» non ha ancora una scheda di fasi e termini: va predisposta dalle fonti ufficiali prima di indicare adempimenti.",
        })
    canale = " ".join(str(canale_operativo or "").split())
    if canale and not canale_deposito(canale):
        lacune.append({
            "tipo": "canale",
            "chiave": canale,
            "descrizione": f"Il canale di deposito «{canale}» non ha una scheda: fasi, ricevute e termini vanno verificati sulle specifiche del portale.",
        })
    registrate = _norme_registrate()
    viste: set[str] = set()
    for riferimento in riferimenti:
        for composta in riferimenti_nel_testo(riferimento):
            # Una citazione composta si confronta articolo per articolo:
            # altrimenti un articolo gia' verificato sparisce dentro l'elenco
            # e viene dichiarato mancante insieme agli altri.
            for norma in articoli_citati(composta):
                chiave = _chiave(norma)
                if not chiave or chiave in viste:
                    continue
                viste.add(chiave)
                if chiave in registrate:
                    continue
                lacune.append({
                    "tipo": "norma",
                    "chiave": norma,
                    "descrizione": f"La norma «{norma}» è citata nel fascicolo ma non è nel registro delle fonti verificate: il testo vigente va acquisito da Normattiva prima di fondarvi un termine.",
                })
    return lacune


__all__ = ["articoli_citati", "lacune_conoscenza", "riferimenti_nel_testo"]
