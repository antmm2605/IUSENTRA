"""Adattatore: il lavoro sul decreto di trattazione scritta (art. 127-ter c.p.c.) come passaggi spiegabili.

La logica di dominio vive in ``pct/note_127_ter/`` (riconoscimento del decreto,
udienza sostituita, proposta del termine, adempimenti, udienza cartolare);
qui si traduce il suo esito in passaggi, senza ricalcolare nulla:

- ``passaggi_da_esame`` riceve l'``EsitoDecretoNote`` che la pipeline PEC
  ottiene da ``esamina_decreto_pec`` e mostra la sequenza completa: decreto
  riconosciuto, collegamento per RG e ufficio, udienza sostituita (o la
  domanda all'avvocato se è ambigua), termine perentorio, udienza cartolare,
  adempimenti delle note, bozza delle note;
- ``passaggi_da_scadenza`` parte dalla scadenza «NOTE_127_TER» già nel
  fascicolo (proposta in bozza o confermata), che è ciò che resta del decreto
  dopo l'esame: è la via usata dalla vista del fascicolo.

Il termine perentorio è quello indicato dal giudice. La data assegnata per le note
vale come data d'udienza ai sensi dell'art. 127-ter c.p.c. Per la trasmissione
telematica si applica l'art. 196-sexies disp. att. c.p.c.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable

from pct.note_127_ter.adempimenti import Adempimento, adempimenti_note
from pct.note_127_ter.proposta import CODICE_NOTE_127_TER, FINE_GIORNO, MODALITA_NOTE_SCRITTE, TITOLO_NOTE_127_TER

from ..modello import Campo, Contesto, Dato, Passaggio, Prova

PRODUTTORE = "decreto di trattazione scritta (art. 127-ter c.p.c.)"
REGOLA_RICONOSCIMENTO = "127ter.riconoscimento_decreto"
REGOLA_COLLEGAMENTO = "127ter.collegamento_rg_ufficio"
REGOLA_UDIENZA = "127ter.udienza_sostituita"
REGOLA_TERMINE = "127ter.termine_note"
REGOLA_EQUIVALENTE = "127ter.termine_equivalente"
REGOLA_CARTOLARE = "127ter.udienza_cartolare"
REGOLA_BOZZA = "127ter.bozza_note"
PREFISSO_ADEMPIMENTO = "127ter.adempimento."
_RE_ORA = re.compile(r"entro le ore (\d{1,2}[:.]\d{2})")
_MOTIVO_DATA = "la scadenza per le note è quella assegnata dal giudice nel provvedimento"


def _it(giorno: date | None) -> str:
    return f"{giorno:%d/%m/%Y}" if giorno else ""


def _chiave(regola: str, contesto: Contesto, oggetto: str) -> str:
    return f"{regola}:{contesto.fascicolo_id or '-'}:{oggetto}"


def _termine(ordine: int, contesto: Contesto, oggetto: str, giorno: date, ora: str, stato: str, prove: tuple[Prova, ...], dati: tuple[Dato, ...]) -> Passaggio:
    return Passaggio(
        chiave=_chiave(REGOLA_TERMINE, contesto, oggetto), produttore=PRODUTTORE, ordine=ordine,
        titolo=f"Termine perentorio per le note: {_it(giorno)} ore {ora}", stato=stato,
        regola_id=REGOLA_TERMINE,
        regola_descrizione="Il giudice assegna il termine perentorio per le note. Quel giorno vale come data "
                           "d’udienza. L’orario registrato segue il provvedimento o, in assenza di un orario "
                           "indicato, la regola ordinaria della fine del giorno.",
        contesto=contesto, norme=("cpc_127ter", "dispatt_196sexies"), prove=prove, dati=dati,
        campi={
            "data": Campo("Data di scadenza", giorno.isoformat(), vincolato=True, motivo_vincolo=_MOTIVO_DATA),
            "ora": Campo("Ora limite del deposito", ora),
        },
        vincoli=("termine_perentorio",), confidenza=0.9 if stato != "da_chiedere" else None, href="#udienze",
    )


def _cartolare(ordine: int, contesto: Contesto, oggetto: str, giorno: date, confermato: bool) -> Passaggio:
    return Passaggio(
        chiave=_chiave(REGOLA_CARTOLARE, contesto, oggetto), produttore=PRODUTTORE, ordine=ordine,
        titolo=f"Il {_it(giorno)} vale come data d’udienza per la trattazione scritta",
        stato="eseguito" if confermato else "proposto", regola_id=REGOLA_CARTOLARE,
        regola_descrizione="Il deposito delle note sostituisce la comparizione. Il giorno di scadenza vale "
                           "come data d’udienza ai sensi dell’art. 127-ter c.p.c.",
        contesto=contesto, norme=("cpc_127ter",), campi={"modalita": Campo("Modalità d'udienza", MODALITA_NOTE_SCRITTE, vincolato=True,
                                                                            motivo_vincolo="la sostituisce il decreto")},
        href="#udienze",
    )


def _adempimenti(ordine: int, contesto: Contesto, oggetto: str, voci: Iterable[Adempimento]) -> list[Passaggio]:
    passaggi = []
    for numero, voce in enumerate(voci):
        passaggi.append(Passaggio(
            chiave=_chiave(PREFISSO_ADEMPIMENTO + voce.codice, contesto, oggetto), produttore=PRODUTTORE, ordine=ordine + numero,
            titolo=voce.testo[:1].upper() + voce.testo[1:], stato="proposto", regola_id=PREFISSO_ADEMPIMENTO + voce.codice,
            regola_descrizione=voce.dettaglio, contesto=contesto, norme=tuple(voce.fonti), href="#udienze",
        ))
    return passaggi


def _bozza(ordine: int, contesto: Contesto, oggetto: str, giorno: date) -> Passaggio:
    return Passaggio(
        chiave=_chiave(REGOLA_BOZZA, contesto, oggetto), produttore=PRODUTTORE, ordine=ordine,
        titolo=f"Preparare la bozza «Note per la trattazione scritta» per l'udienza del {_it(giorno)}",
        stato="proposto", regola_id=REGOLA_BOZZA,
        regola_descrizione="Il software prepara la bozza con intestazione e indicazioni del decreto; "
                           "conclusioni, firma e deposito restano dell'avvocato.",
        contesto=contesto, norme=("cpc_127ter", "dispatt_196quater"),
        campi={
            "termine_note": Campo("Termine assegnato", giorno.isoformat(), vincolato=True,
                                  motivo_vincolo="data del provvedimento"),
            "deposito": Campo("Deposito", "a cura dell'avvocato, con firma digitale"),
        },
        vincoli=("deposito_non_autonomo",), href="#documenti",
    )


def passaggi_da_esame(esito: Any, contesto: Contesto, *, pec_id: str = "", oggetto_pec: str = "", rg: str = "", estratto: str = "") -> list[Passaggio]:
    """I passaggi dall'``EsitoDecretoNote`` di ``pct.note_127_ter.esame_pec.esamina_decreto_pec``."""
    oggetto = pec_id or "decreto"
    decreto = esito.decreto
    prova_pec = Prova("pec", estratto or "decreto che sostituisce l'udienza già fissata con il deposito di note scritte", oggetto_pec, pec_id)
    passaggi = [Passaggio(
        chiave=_chiave(REGOLA_RICONOSCIMENTO, contesto, oggetto), produttore=PRODUTTORE, ordine=10,
        titolo="Riconosciuto un decreto di trattazione scritta che rinvia all'udienza già fissata", stato="eseguito",
        regola_id=REGOLA_RICONOSCIMENTO,
        regola_descrizione="Il testo dispone la sostituzione dell'udienza con note scritte e non indica una data propria.",
        contesto=contesto, norme=("cpc_127ter",), prove=(prova_pec,),
        dati=tuple(d for d in (Dato("Ora indicata dal decreto", decreto.ora_limite, "decreto"),) if d.valore),
        confidenza=1.0,
    )]
    collegato = bool(contesto.fascicolo_id)
    passaggi.append(Passaggio(
        chiave=_chiave(REGOLA_COLLEGAMENTO, contesto, oggetto), produttore=PRODUTTORE, ordine=20,
        titolo="PEC collegata al fascicolo per numero di ruolo e ufficio" if collegato else "Collegare la PEC al fascicolo giusto",
        stato="eseguito" if collegato else "da_chiedere", regola_id=REGOLA_COLLEGAMENTO,
        regola_descrizione="Il collegamento automatico richiede RG e ufficio certificati dalla comunicazione di cancelleria.",
        contesto=contesto, norme=("dm44_art16",), dati=(Dato("Numero di ruolo", rg, "comunicazione"), Dato("Ufficio", contesto.ufficio, "comunicazione")),
        vincoli=() if collegato else ("conferma_avvocato",),
    ))
    if not collegato:
        return passaggi
    udienza = esito.udienza
    if udienza is None or udienza.giorno is None:
        candidate = ", ".join(_it(g) for g in (udienza.candidate if udienza else ())) or "nessuna udienza futura"
        passaggi.append(Passaggio(
            chiave=_chiave(REGOLA_UDIENZA, contesto, oggetto), produttore=PRODUTTORE, ordine=30,
            titolo="Indicare quale udienza il decreto sostituisce", stato="da_chiedere", regola_id=REGOLA_UDIENZA,
            regola_descrizione="Si propone una data solo se nel fascicolo c'è una sola udienza futura: altrimenti decide l'avvocato.",
            contesto=contesto, norme=("cpc_127ter",), dati=(Dato("Udienze candidate", candidate, "agenda e scadenziario"),),
            prove=(Prova("fascicolo", esito.da_verificare, "esame del decreto"),), vincoli=("conferma_avvocato",),
        ))
        return passaggi
    passaggi.append(Passaggio(
        chiave=_chiave(REGOLA_UDIENZA, contesto, oggetto), produttore=PRODUTTORE, ordine=30,
        titolo=f"Udienza sostituita: {_it(udienza.giorno)}", stato="eseguito", regola_id=REGOLA_UDIENZA,
        regola_descrizione="Unica udienza futura del fascicolo (ora italiana, Europe/Rome).",
        contesto=contesto, norme=("cpc_127ter",), dati=(Dato("Prossima udienza", _it(udienza.giorno), "agenda del fascicolo"),), confidenza=0.9,
    ))
    if esito.equivalente_id:
        passaggi.append(Passaggio(
            chiave=_chiave(REGOLA_EQUIVALENTE, contesto, oggetto), produttore=PRODUTTORE, ordine=40,
            titolo="Termine per le note già nello scadenziario: nessuna nuova proposta", stato="eseguito", regola_id=REGOLA_EQUIVALENTE,
            regola_descrizione="Un termine per note dello stesso giorno presidia già il decreto: niente doppioni.",
            contesto=contesto, norme=("cpc_127ter",), dati=(Dato("Scadenza esistente", esito.equivalente_id, "scadenziario"),),
        ))
    for proposta in esito.proposte:
        giorno = date.fromisoformat(proposta.due_date)
        passaggi.append(_termine(40, contesto, oggetto, giorno, proposta.ora, "da_confermare", (prova_pec,),
                                 (Dato("Udienza sostituita", _it(giorno), "agenda del fascicolo"), Dato("Comunicazione", proposta.dies_a_quo, "PEC"))))
        passaggi.append(_cartolare(50, contesto, oggetto, giorno, confermato=False))
    passaggi.extend(_adempimenti(60, contesto, oggetto, esito.adempimenti))
    passaggi.append(_bozza(90, contesto, oggetto, udienza.giorno))
    return passaggi


def _e_note(scadenza: dict[str, Any]) -> bool:
    return (str(scadenza.get("deadline_profile_code") or "").upper() == CODICE_NOTE_127_TER
            or f":{CODICE_NOTE_127_TER}" in str(scadenza.get("note") or "")
            or str(scadenza.get("titolo") or "").startswith(TITOLO_NOTE_127_TER))


def _ora(scadenza: dict[str, Any]) -> str:
    dovuta = str(scadenza.get("operational_due_at") or "")
    if "T" in dovuta and len(dovuta) >= 16:
        return dovuta[11:16]
    trovata = _RE_ORA.search(f"{scadenza.get('note') or ''} {scadenza.get('descrizione') or ''}")
    if not trovata:
        return FINE_GIORNO
    ore, minuti = re.split(r"[:.]", trovata.group(1))
    return f"{int(ore):02d}:{minuti}"


def passaggi_da_scadenza(
    scadenze: Iterable[dict[str, Any]], contesto: Contesto, *, oggi: date, rg: str = "",
    conclusioni: Iterable[dict[str, Any]] | None = (),
) -> list[Passaggio]:
    """I passaggi delle note 127-ter dalla scadenza già nel fascicolo (bozza o confermata), solo se futura."""
    passaggi: list[Passaggio] = []
    visti: set[date] = set()
    decisioni: dict[str, list[Adempimento]] = {}
    for voce in conclusioni or ():
        if voce.get("codice") != "note_127ter" or not voce.get("perche"):
            continue
        scadenza = str((voce.get("termine") or {}).get("scadenza_iso") or "")
        articoli = {str(n.get("norma") or "") for n in voce.get("norme") or ()}
        speciale = next((codice for norma, codice in (("art. 631 c.p.c.", "cpc_631"), ("art. 181 c.p.c.", "cpc_181"))
                         if norma in articoli), "")
        if scadenza and speciale:
            decisioni.setdefault(scadenza, []).append(Adempimento(
                "decisione", "Conseguenza del mancato deposito delle note", voce["perche"], ("cpc_127ter", speciale),
            ))
    for scadenza in scadenze:
        stato = str(scadenza.get("stato") or "").upper()
        try:
            giorno = date.fromisoformat(str(scadenza.get("data") or scadenza.get("data_scadenza") or "")[:10])
        except ValueError:
            continue
        if stato not in {"APERTO", "BOZZA"} or not _e_note(scadenza) or giorno < oggi or giorno in visti:
            continue
        visti.add(giorno)
        oggetto = str(scadenza.get("id") or giorno.isoformat())
        confermato = stato == "APERTO"
        prova = Prova("fascicolo", str(scadenza.get("titolo") or TITOLO_NOTE_127_TER), "scadenziario", oggetto)
        ora = _ora(scadenza)
        passaggi.append(_termine(40, contesto, oggetto, giorno, ora, "eseguito" if confermato else "da_confermare", (prova,),
                                 (Dato("Data assegnata per le note", _it(giorno), "scadenziario"),)))
        passaggi.append(_cartolare(50, contesto, oggetto, giorno, confermato=confermato))
        voci = adempimenti_note(None, giorno, rg=rg, giudice=contesto.giudice, ufficio=contesto.ufficio, ora_limite=ora if ora != FINE_GIORNO else "")
        decisioni_del_giorno = decisioni.get(giorno.isoformat(), [])
        if conclusioni is None or len(decisioni_del_giorno) > 1:
            voci = [voce for voce in voci if voce.codice != "decisione"]
        elif decisioni_del_giorno:
            voci = [decisioni_del_giorno[0] if voce.codice == "decisione" else voce for voce in voci]
        passaggi.extend(_adempimenti(60, contesto, oggetto, voci))
        passaggi.append(_bozza(90, contesto, oggetto, giorno))
    return passaggi


__all__ = [
    "PREFISSO_ADEMPIMENTO", "PRODUTTORE", "REGOLA_BOZZA", "REGOLA_CARTOLARE", "REGOLA_COLLEGAMENTO", "REGOLA_EQUIVALENTE",
    "REGOLA_RICONOSCIMENTO", "REGOLA_TERMINE", "REGOLA_UDIENZA", "passaggi_da_esame", "passaggi_da_scadenza",
]
