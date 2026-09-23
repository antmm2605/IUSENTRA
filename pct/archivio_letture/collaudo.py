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

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from legal_ocr.formulario.date import trova_date
from pct.registro_letture.fatti_repository import Fatto
from pct.registro_letture.verifica_date import interpreta_data, valuta_data

ORIGINI_NON_OTTICHE = {"nativo", "pec_xml", "pec_testo", "pec_intestazioni", "metadati", "presidio_pec", "portale"}
CAMPI_FUTURI = {"udienza", "termine", "costituzione"}
CAMPI_CONSEGUENTI = {"udienza", "termine", "costituzione", "notifica", "consegna", "accettazione", "deposito"}
BASE_NORMATIVA_DIGITALE = (
    "D.M. 44/2011 art. 3 e CAD art. 20: impronta, integrità e tracciabilità "
    "della fonte digitale"
)
PROCEDURA_ARCHIVIO_LETTURE = (
    "docs/REGISTRO_LETTURE.md: lettura incrementale, collaudo automatico e "
    "consegna ai presìdi dall'archivio"
)


@dataclass(slots=True)
class Contesto:
    """Ciò che il fascicolo sa e che serve a collaudare un fatto."""

    oggi: date | None = None
    anno_riferimento: int | None = None
    data_minima: date | None = None
    numero_rg: str = ""
    anno_rg: str = ""
    ufficio_giudiziario: str = ""
    # data ISO -> etichette delle fonti che la conoscono (agenda, scadenziario, PEC, portale)
    date_note: dict[str, list[str]] = field(default_factory=dict)
    # una seconda lettura indipendente dello stesso oggetto (testo nativo, OCR, indice)
    testo_secondario: str = ""
    etichetta_secondario: str = ""
    # importo (due decimali, come stringa) -> etichette delle fonti che lo conoscono
    # (pagamenti registrati nel fascicolo, parcelle, preventivi)
    importi_noti: dict[str, list[str]] = field(default_factory=dict)

    def date_del_secondario(self) -> set[str]:
        return {voce.data.isoformat() for voce in trova_date(self.testo_secondario)} if self.testo_secondario else set()


def _prova(codice: str, esito: str, dettaglio: str) -> dict[str, str]:
    return {"codice": codice, "esito": esito, "dettaglio": dettaglio}


_UFFICIO_PRIMA_DEL_RUOLO = re.compile(
    r"\b(?:tribunale(?:\s+ordinario)?|corte\s+d[’']appello|giudice\s+di\s+pace|"
    r"tribunale\s+amministrativo\s+regionale|corte\s+di\s+giustizia\s+tributaria)"
    r"\s+(?:di|del|della|per(?:\s+il|\s+la)?)\s+.+?"
    r"(?=\s+(?:r\s*\.?\s*g\s*\.?|n\s*\.?\s*r\s*\.?\s*g\s*\.?|sezione\b)|[,;:\-–—]|$)",
    re.IGNORECASE,
)
_STOP_UFFICIO = {
    "di",
    "del",
    "della",
    "dell",
    "per",
    "il",
    "la",
    "ordinario",
    "ordinaria",
}


def _chiave_ufficio(valore: str) -> str:
    testo = re.sub(r"\([^)]*\)", " ", str(valore or ""))
    testo = "".join(
        carattere
        for carattere in unicodedata.normalize("NFKD", testo)
        if not unicodedata.combining(carattere)
    ).casefold()
    token = re.findall(r"[a-z0-9]+", testo)
    if "sezione" in token:
        token = token[: token.index("sezione")]
    return " ".join(voce for voce in token if voce not in _STOP_UFFICIO)


def ufficio_esplicito_del_ruolo(fatto: Fatto) -> str:
    match = _UFFICIO_PRIMA_DEL_RUOLO.search(str(fatto.contesto or ""))
    return " ".join(match.group(0).split()) if match else ""


def ruolo_compatibile_con_ufficio(fatto: Fatto, ufficio_giudiziario: str) -> bool:
    atteso = _chiave_ufficio(ufficio_giudiziario)
    dichiarato = _chiave_ufficio(ufficio_esplicito_del_ruolo(fatto))
    if not atteso or not dichiarato:
        return True
    return (
        atteso == dichiarato
        or dichiarato.startswith(atteso + " ")
        or atteso.startswith(dichiarato + " ")
    )


def _con_prove_governance(fatto: Fatto) -> Fatto:
    """Aggiunge fonti normative e procedurali senza alterare il verdetto."""
    prove = list(fatto.prove)
    codici = {str(prova.get("codice") or "") for prova in prove}
    if "base_normativa" not in codici:
        prove.append(_prova("base_normativa", "ok", BASE_NORMATIVA_DIGITALE))
    if "procedura" not in codici:
        prove.append(_prova("procedura", "ok", PROCEDURA_ARCHIVIO_LETTURE))
    fatto.prove = prove
    return fatto


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
    ufficio_documento = ufficio_esplicito_del_ruolo(fatto)
    if not ruolo_compatibile_con_ufficio(fatto, contesto.ufficio_giudiziario):
        prove.append(
            _prova(
                "ufficio_giudiziario",
                "respinta",
                f"il documento indica {ufficio_documento}, diverso dall'ufficio "
                f"del fascicolo {contesto.ufficio_giudiziario}",
            )
        )
        fatto.prove, fatto.verifica = prove, "respinta"
        return fatto
    if ufficio_documento and contesto.ufficio_giudiziario:
        prove.append(
            _prova(
                "ufficio_giudiziario",
                "ok",
                f"ufficio coerente con il fascicolo: {contesto.ufficio_giudiziario}",
            )
        )
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


def _collauda_importo(fatto: Fatto, contesto: Contesto) -> Fatto:
    """Un importo è un fatto se è un numero sensato e la regola che l'ha letto è dichiarata.

    Le regole economiche stanno in `pct/fascicolo_sentenza_economica.py` e citano
    già la norma che governa l'importo (contributo unificato, compenso liquidato,
    spese): il collaudo qui verifica la forma del numero, l'origine della lettura
    e la concordanza con quanto il fascicolo già registra. Un importo che
    coincide con un pagamento registrato è verificato; un importo letto da un
    testo ottico senza riscontro resta da confermare.
    """
    prove = list(fatto.prove)
    try:
        numero = float(fatto.valore)
    except (TypeError, ValueError):
        numero = 0.0
    if numero <= 0:
        fatto.verifica = "respinta"
        fatto.prove = prove + [_prova("forma", "errore", "importo non leggibile come numero positivo")]
        return fatto
    prove.append(_prova("forma", "ok", f"importo {fatto.valore} ben formato"))
    fonti = contesto.importi_noti.get(fatto.valore) or []
    if fonti:
        fatto.verifica = "verificata"
        fatto.prove = prove + [_prova("concordanza", "ok", f"lo stesso importo risulta da {', '.join(fonti)}")]
        return fatto
    if fatto.origine in ORIGINI_NON_OTTICHE:
        fatto.verifica = "verificata"
        fatto.prove = prove + [_prova("origine", "ok", f"letto da {fatto.origine}, non da riconoscimento ottico")]
        return fatto
    fatto.verifica = "plausibile"
    fatto.prove = prove + [_prova("origine", "attenzione", f"letto da {fatto.origine or 'origine ignota'}: nessun riscontro nel fascicolo")]
    return fatto


def collauda(fatto: Fatto, contesto: Contesto, *, secondarie: set[str] | None = None) -> Fatto:
    """Il fatto con le sue prove e il verdetto del software."""
    if fatto.verifica in {"corretta", "ignorata"}:
        return _con_prove_governance(fatto)
    if fatto.categoria == "data":
        return _con_prove_governance(_collauda_data(fatto, contesto, secondarie if secondarie is not None else contesto.date_del_secondario()))
    if fatto.categoria == "ruolo":
        return _con_prove_governance(_collauda_ruolo(fatto, contesto))
    if fatto.categoria == "prova_notifica":
        return _con_prove_governance(_collauda_prova_notifica(fatto, contesto))
    if fatto.categoria == "importo":
        return _con_prove_governance(_collauda_importo(fatto, contesto))
    if fatto.verifica not in {"verificata", "plausibile", "respinta"}:
        fatto.verifica = "plausibile"
    return _con_prove_governance(fatto)


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
        oggi=orizzonte["oggi"],
        anno_riferimento=orizzonte["anno_riferimento"],
        data_minima=orizzonte["data_minima"],
        numero_rg=campo("numero_rg").strip(),
        anno_rg=campo("anno_rg").strip(),
        ufficio_giudiziario=(
            campo("tribunale").strip()
            or campo("ufficio_giudiziario").strip()
        ),
        date_note=dict(date_note or {}),
    )


__all__ = [
    "BASE_NORMATIVA_DIGITALE", "CAMPI_CONSEGUENTI", "CAMPI_FUTURI",
    "ORIGINI_NON_OTTICHE", "PROCEDURA_ARCHIVIO_LETTURE", "Contesto",
    "collauda", "collauda_tutti", "contesto_da_fascicolo", "ruolo_compatibile_con_ufficio", "ufficio_esplicito_del_ruolo",
]
