"""Il collaudo dei fatti: il software prova ogni dato letto prima di fidarsene.

Per una data: calendario, forma del token (quanti segni ha corretto il
formulario), ancoraggio (che cosa dice il testo), orizzonte del fascicolo
(anno di ruolo, apertura, futuro), doppia lettura (la stessa data compare in
una seconda estrazione indipendente dello stesso documento: testo nativo e
OCR, o indice documentale), concordanza (la data è già nota da agenda,
scadenziario, PEC del presidio o portale). Per un numero di ruolo: coincide
con il ruolo del fascicolo. Per una prova di notifica: quanti segnali
concordi. Il verdetto è `verificata` quando almeno una prova indipendente
riscontra il dato o quando l'origine non è ottica; `plausibile` quando il
dato è ben formato e ancorato ma nessuno lo riscontra; `respinta` quando un
controllo lo smentisce. I fatti respinti restano nell'archivio con le loro
prove ma non si propongono a nessuno.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from legal_ocr.formulario.date import trova_date
from pct.registro_letture.fatti_repository import Fatto
from pct.registro_letture.verifica_date import interpreta_data, valuta_data

ORIGINI_NON_OTTICHE = {"nativo", "pec_xml", "pec_testo", "pec_intestazioni", "metadati", "presidio_pec", "portale"}
CAMPI_FUTURI = {"udienza", "termine", "costituzione"}
CAMPI_CONSEGUENTI = {"udienza", "termine", "costituzione", "notifica", "consegna", "accettazione", "deposito"}


@dataclass(slots=True)
class Contesto:
    """Ciò che il fascicolo sa e che serve a collaudare un fatto."""

    oggi: date | None = None
    anno_riferimento: int | None = None
    data_minima: date | None = None
    numero_rg: str = ""
    anno_rg: str = ""
    # data ISO -> etichette delle fonti che la conoscono (agenda, scadenziario, PEC, portale)
    date_note: dict[str, list[str]] = field(default_factory=dict)
    # una seconda lettura indipendente dello stesso oggetto (testo nativo, OCR, indice)
    testo_secondario: str = ""
    etichetta_secondario: str = ""

    def date_del_secondario(self) -> set[str]:
        return {voce.data.isoformat() for voce in trova_date(self.testo_secondario)} if self.testo_secondario else set()


def _prova(codice: str, esito: str, dettaglio: str) -> dict[str, str]:
    return {"codice": codice, "esito": esito, "dettaglio": dettaglio}


def _collauda_data(fatto: Fatto, contesto: Contesto, secondarie: set[str]) -> Fatto:
    prove = list(fatto.prove)
    giorno = fatto.valore.split("T")[0]
    data = interpreta_data(giorno)
    if data is None:
        prove.append(_prova("calendario", "respinta", f"«{fatto.valore}» non è una data"))
        fatto.prove, fatto.verifica = prove, "respinta"
        return fatto
    smentita = False
    attenzione = False
    giudizio = valuta_data(
        data.strftime("%d/%m/%Y"), oggi=contesto.oggi, anno_riferimento=contesto.anno_riferimento,
        data_minima=contesto.data_minima if fatto.campo in CAMPI_FUTURI else None,
    )
    if giudizio.stato == "valida":
        prove.append(_prova("orizzonte", "ok", "dentro l'orizzonte del fascicolo"))
    else:
        for codice, motivo in zip(giudizio.codici, giudizio.motivi):
            if codice in {"anno_futuro", "prima_del_fascicolo", "giorno_mese_invertiti", "giorno_inesistente", "non_interpretabile"}:
                smentita = True
                prove.append(_prova("orizzonte", "respinta", motivo))
            else:
                attenzione = True
                prove.append(_prova("orizzonte", "attenzione", motivo))
    sostituzioni = 0
    for prova in fatto.prove:
        if prova.get("codice") == "forma" and prova.get("esito") == "attenzione":
            attenzione = True
            try:
                sostituzioni = int(str(prova.get("dettaglio") or "0").split(" ")[0])
            except ValueError:
                sostituzioni = 2
    riscontri: list[str] = []
    if contesto.testo_secondario:
        if giorno in secondarie:
            riscontri.append(contesto.etichetta_secondario or "seconda lettura")
            prove.append(_prova("doppia_lettura", "ok", f"la stessa data compare nella {contesto.etichetta_secondario or 'seconda lettura'}"))
        else:
            prove.append(_prova("doppia_lettura", "attenzione", f"non compare nella {contesto.etichetta_secondario or 'seconda lettura'}"))
    fonti = contesto.date_note.get(giorno) or []
    if fonti:
        riscontri.extend(fonti)
        prove.append(_prova("concordanza", "ok", "già nota da " + ", ".join(fonti[:3])))
    else:
        prove.append(_prova("concordanza", "nessuna", "nessun'altra fonte del fascicolo conosce questa data"))
    if smentita:
        verifica = "respinta"
    elif riscontri or (fatto.origine in ORIGINI_NON_OTTICHE and not attenzione):
        verifica = "verificata"
    else:
        verifica = "plausibile"
    if verifica == "verificata" and fatto.origine not in ORIGINI_NON_OTTICHE and sostituzioni > 1 and not riscontri:
        verifica = "plausibile"
    fatto.prove, fatto.verifica = prove, verifica
    return fatto


def _collauda_ruolo(fatto: Fatto, contesto: Contesto) -> Fatto:
    prove = list(fatto.prove)
    atteso = f"{int(contesto.numero_rg)}/{contesto.anno_rg}" if str(contesto.numero_rg or "").strip().isdigit() and str(contesto.anno_rg or "").strip() else ""
    if atteso and fatto.valore == atteso:
        prove.append(_prova("concordanza", "ok", f"coincide con il ruolo del fascicolo {atteso}"))
        fatto.verifica = "verificata"
    elif atteso:
        prove.append(_prova("concordanza", "attenzione", f"diverso dal ruolo del fascicolo {atteso}: altro procedimento citato o lettura errata"))
        fatto.verifica = "plausibile"
    else:
        prove.append(_prova("concordanza", "nessuna", "il fascicolo non ha un numero di ruolo registrato"))
        fatto.verifica = "verificata" if fatto.origine in ORIGINI_NON_OTTICHE and fatto.confidenza >= 0.8 else "plausibile"
    fatto.prove = prove
    return fatto


def _collauda_prova_notifica(fatto: Fatto, contesto: Contesto) -> Fatto:
    segnali_ok = any(prova.get("codice") == "segnali" and prova.get("esito") == "ok" for prova in fatto.prove)
    fatto.verifica = "verificata" if (segnali_ok or fatto.origine in ORIGINI_NON_OTTICHE) else "plausibile"
    fatto.prove = list(fatto.prove) + [_prova("origine", "ok" if fatto.origine in ORIGINI_NON_OTTICHE else "attenzione", f"letta da {fatto.origine or 'origine ignota'}")]
    return fatto


def collauda(fatto: Fatto, contesto: Contesto, *, secondarie: set[str] | None = None) -> Fatto:
    """Il fatto con le sue prove e il verdetto del software."""
    if fatto.verifica in {"corretta", "ignorata"}:
        return fatto
    if fatto.categoria == "data":
        return _collauda_data(fatto, contesto, secondarie if secondarie is not None else contesto.date_del_secondario())
    if fatto.categoria == "ruolo":
        return _collauda_ruolo(fatto, contesto)
    if fatto.categoria == "prova_notifica":
        return _collauda_prova_notifica(fatto, contesto)
    if fatto.verifica not in {"verificata", "plausibile", "respinta"}:
        fatto.verifica = "plausibile"
    return fatto


def collauda_tutti(fatti: Iterable[Fatto], contesto: Contesto) -> list[Fatto]:
    secondarie = contesto.date_del_secondario()
    return [collauda(fatto, contesto, secondarie=secondarie) for fatto in fatti]


def contesto_da_fascicolo(fascicolo: Any, *, oggi: date | None = None, date_note: dict[str, list[str]] | None = None) -> Contesto:
    """Il contesto di collaudo dal fascicolo (anno di ruolo, apertura) e dalle date note."""
    from pct.registro_letture.verifica_date import orizzonte_fascicolo

    orizzonte = orizzonte_fascicolo(fascicolo, oggi=oggi)

    def campo(nome: str) -> str:
        if isinstance(fascicolo, dict):
            return str(fascicolo.get(nome) or "")
        return str(getattr(fascicolo, nome, "") or "")

    return Contesto(
        oggi=orizzonte["oggi"], anno_riferimento=orizzonte["anno_riferimento"], data_minima=orizzonte["data_minima"],
        numero_rg=campo("numero_rg").strip(), anno_rg=campo("anno_rg").strip(), date_note=dict(date_note or {}),
    )


__all__ = ["CAMPI_CONSEGUENTI", "CAMPI_FUTURI", "ORIGINI_NON_OTTICHE", "Contesto", "collauda", "collauda_tutti", "contesto_da_fascicolo"]
