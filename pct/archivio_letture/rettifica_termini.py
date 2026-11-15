"""Le scadenze automatiche già create, riallineate alla lettura corrente dello stesso provvedimento.

Quando una regola di lettura si corregge (il termine per le note ex art. 127-ter c.p.c. è quello
assegnato dal giudice, non il giorno dell'udienza sostituita; il termine dichiarato perentorio è
perentorio; il provvedimento collettivo vale solo per il gruppo di cause del fascicolo), la rilettura
mirata riscrive i fatti nell'archivio. Le scadenze che l'archivio aveva già consegnato allo
scadenziario restano però con il titolo e la natura di prima. Qui si decide, per ogni scadenza
**automatica e intatta**, che cosa dice oggi la lettura:

* **aggiorna** — lo stesso giorno porta ora un termine qualificato (istituto e norma) o
  dichiarato perentorio: titolo, tipo e perentorietà diventano quelli del fatto corrente (artt.
  152-153 c.p.c.; art. 127-ter, primo comma, c.p.c.);
* **annulla** — lo stesso giorno non porta più alcun termine utile e la lettura corrente vi legge
  un'udienza (l'udienza sostituita dalle note) oppure respinge il termine perché disposto per altre
  cause: la proposta non ha più fonte.

Intatta vuol dire: aperta, senza responsabile assegnato, con la nota automatica di tre righe
(«Data verificata nell'archivio…», ``ARCHIVIO_FATTO:…``, «Fonte: …») e il titolo nella forma che il
software scrive. Ogni scadenza toccata dall'avvocato resta com'è: si segnala, non si cambia.

Modulo puro: riceve scadenze e fatti correnti, restituisce il piano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from .adempimenti import perentorieta_documentata
from .istituti_processuali import ISTITUTI

PRIMA_RIGA = "Data verificata nell’archivio delle letture."
VERSIONE = "2026.11.15.rettifica-termini.v3"
_VERIFICHE_UTILI = {"verificata", "corretta"}


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _stato(riga: Any) -> str:
    return str(getattr(getattr(riga, "stato", ""), "value", getattr(riga, "stato", ""))).upper()


def _giorno(valore: Any) -> str:
    return _testo(valore)[:10]


def _titolo_automatico(titolo: str, giorno_it: str) -> bool:
    """Il titolo è uno di quelli che il software scrive per una data letta."""
    titolo = _testo(titolo)
    if titolo in {f"Termine del {giorno_it}", f"Costituzione del {giorno_it}"}:
        return True
    if titolo.startswith(f"Deposito note in sostituzione udienza del {giorno_it}"):
        return True
    return any(titolo.startswith(f"{istituto.titolo} — {giorno_it}") for istituto in ISTITUTI)


def riga_intatta(riga: Any) -> bool:
    """Scadenza automatica dell'archivio mai toccata dall'avvocato."""
    if _stato(riga) != "APERTO" or _testo(getattr(riga, "id_utente_responsabile", "")):
        return False
    righe = str(getattr(riga, "note", "") or "").splitlines()
    if len(righe) != 3 or not righe[0].startswith(PRIMA_RIGA) or not righe[1].startswith("ARCHIVIO_FATTO:") or not righe[2].startswith("Fonte: "):
        return False
    giorno = _giorno(getattr(riga, "data_scadenza", ""))
    try:
        giorno_it = date.fromisoformat(giorno).strftime("%d/%m/%Y")
    except ValueError:
        return False
    return _titolo_automatico(getattr(riga, "titolo", ""), giorno_it)


@dataclass(slots=True)
class Rettifica:
    """Che cosa fare di una scadenza automatica, e perché."""

    scadenza_id: str
    azione: str  # "aggiorna" | "annulla"
    motivo: str
    fatto_id: str = ""
    campi: dict[str, Any] = field(default_factory=dict)
    prove: list[dict[str, Any]] = field(default_factory=list)


def _prova(fatto: Any) -> dict[str, Any]:
    return {"fatto_id": fatto.id, "tipo": fatto.tipo, "oggetto_id": fatto.oggetto_id, "sha256": fatto.sha256,
            "campo": fatto.campo, "verifica": fatto.verifica, "estratto": _testo(fatto.contesto)[:300]}


def _qualificato(fatto: Any) -> bool:
    return any(p.get("codice") == "istituto" and p.get("esito") == "ok" for p in fatto.prove)


def _motivo_respinto(fatti: list[Any]) -> str:
    for fatto in fatti:
        for prova in reversed(fatto.prove):
            if prova.get("esito") == "respinta" and prova.get("dettaglio"):
                return str(prova["dettaglio"])
    return ""


def piano_rettifiche(scadenze: Iterable[Any], fatti_correnti: Iterable[Any], *, oggi: date) -> list[Rettifica]:
    """Le rettifiche delle scadenze automatiche intatte secondo i fatti correnti dell'archivio.

    Si annullano anche le proposte già decorse rimaste aperte senza fonte (es. il termine di un altro
    gruppo di cause); si aggiornano solo i termini futuri.

    ``fatti_correnti`` sono i fatti di categoria «data» delle fonti presenti con l'impronta corrente,
    con ogni verdetto (anche respinti): servono a dire perché un termine non c'è più.
    """
    per_giorno: dict[str, list[Any]] = {}
    for fatto in fatti_correnti:
        if getattr(fatto, "categoria", "") == "data":
            per_giorno.setdefault(_giorno(fatto.valore), []).append(fatto)
    piano: list[Rettifica] = []
    for riga in scadenze:
        giorno = _giorno(getattr(riga, "data_scadenza", ""))
        if not giorno or not riga_intatta(riga):
            continue
        del_giorno = per_giorno.get(giorno, [])
        termini = [f for f in del_giorno if f.campo in {"termine", "costituzione"} and f.verifica in _VERIFICHE_UTILI]
        if not termini:
            if any(f.campo in {"termine", "costituzione"} and f.verifica == "plausibile" for f in del_giorno):
                continue  # un termine ancora da confermare: decide l'avvocato
            respinti = [f for f in del_giorno if f.campo in {"termine", "costituzione"} and f.verifica == "respinta"]
            udienze = [f for f in del_giorno if f.campo == "udienza" and f.verifica in _VERIFICHE_UTILI]
            if respinti and _motivo_respinto(respinti):
                piano.append(Rettifica(riga.id, "annulla", _motivo_respinto(respinti), prove=[_prova(f) for f in respinti[:5]]))
            elif udienze and not respinti:
                piano.append(Rettifica(
                    riga.id, "annulla",
                    "Con la lettura corrente del provvedimento la data è l'udienza, non un termine: il termine "
                    "è quello assegnato dal giudice (art. 127-ter, primo comma, c.p.c.).",
                    prove=[_prova(f) for f in udienze[:5]],
                ))
            continue
        if giorno < oggi.isoformat():
            continue  # un termine decorso non si rinomina: resta presidiato dallo scadenziario
        migliore = sorted(termini, key=lambda f: (not _qualificato(f), not perentorieta_documentata(f), f.tipo != "documento", f.id))[0]
        perentorio = perentorieta_documentata(migliore) or any(perentorieta_documentata(f) for f in termini if _qualificato(f) == _qualificato(migliore))
        rischio = next((p for p in migliore.prove if p.get("codice") == "rischio_estinzione"), None)
        titolo = _testo(migliore.etichetta)
        if rischio and titolo.endswith(": senza note si estingue"):
            titolo = titolo.removesuffix(": senza note si estingue") + ": rischio di estinzione"
        titolo = titolo[:120]
        cambia_titolo = _qualificato(migliore) and titolo and titolo != _testo(getattr(riga, "titolo", ""))
        cambia_perentorio = perentorio and not bool(getattr(riga, "perentorio", False))
        if not cambia_titolo and not cambia_perentorio:
            continue
        campi: dict[str, Any] = {}
        if cambia_titolo:
            campi["titolo"] = titolo
        if perentorio:
            campi.update(perentorio=True, tipo="TERMINE_PERENTORIO")
        if any(p.get("codice") == "istituto" and p.get("dettaglio") == "note_127_ter" for p in migliore.prove):
            campi.update(hearing_mode="note_scritte", hearing_mode_source=f"{migliore.tipo}:{migliore.oggetto_id}")
        motivo = "Lettura corrente del provvedimento: " + (titolo if cambia_titolo else "termine dichiarato perentorio") + "."
        if rischio:
            motivo += " " + str(rischio.get("dettaglio") or "")
        piano.append(Rettifica(riga.id, "aggiorna", motivo, fatto_id=migliore.id, campi=campi, prove=[_prova(migliore)]))
    return piano




# ---- agenda: la modalità d'udienza disposta per la causa ------------------------------------------

_RE_IN_PRESENZA = re.compile(r"(?:trattat[ao]|si\s+terr[àa]|celebrat[ao]|svolger[àa])\s+in\s+presenza", re.I)
_LUOGHI_AUTOMATICI = {"trattazione scritta", "modalità udienza da verificare", ""}


def _udienza_in_presenza(fatti_del_giorno: list[Any]) -> list[Any]:
    """Le letture del provvedimento che dispongono l'udienza in presenza, se nessuna dispone le note."""
    primarie = [f for f in fatti_del_giorno if f.tipo in {"documento", "allegato_pec"} and f.verifica in _VERIFICHE_UTILI]
    note = [f for f in primarie if f.campo == "termine" and (_qualificato(f) or "note" in _testo(f.etichetta).casefold())]
    presenza = [f for f in primarie if f.campo == "udienza" and _RE_IN_PRESENZA.search(_testo(f.contesto))]
    return [] if note else presenza


def piano_agenda(appuntamenti: Iterable[Any], fatti_correnti: Iterable[Any], *, tribunale: str = "") -> list[Rettifica]:
    """Le udienze create dal presidio PEC come «trattazione scritta» che il provvedimento dispone in presenza.

    Caso: provvedimento collettivo letto senza distinguere i gruppi di cause (``pct/provvedimenti/
    collettivi``): l'udienza del gruppo del fascicolo «sarà trattata in presenza», le note ex art.
    127-ter c.p.c. riguardano l'altro gruppo. Solo appuntamenti automatici del presidio PEC con il
    luogo scritto dal software; l'agenda modificata dall'avvocato non si tocca.
    """
    per_giorno: dict[str, list[Any]] = {}
    for fatto in fatti_correnti:
        if getattr(fatto, "categoria", "") == "data":
            per_giorno.setdefault(_giorno(fatto.valore), []).append(fatto)
    piano: list[Rettifica] = []
    for appuntamento in appuntamenti:
        tipo = str(getattr(getattr(appuntamento, "tipo", ""), "value", getattr(appuntamento, "tipo", ""))).upper()
        if tipo != "UDIENZA" or _testo(getattr(appuntamento, "external_provider", "")) != "pec_audit":
            continue
        if _testo(getattr(appuntamento, "hearing_mode", "")) != "note_scritte" or _testo(getattr(appuntamento, "luogo", "")).casefold() not in _LUOGHI_AUTOMATICI:
            continue
        prove = _udienza_in_presenza(per_giorno.get(_giorno(getattr(appuntamento, "data_ora", "")), []))
        if not prove:
            continue
        piano.append(Rettifica(
            appuntamento.id, "modalita",
            "Il provvedimento dispone per questa causa l'udienza in presenza; la trattazione scritta (art. 127-ter "
            "c.p.c.) riguardava altre cause dello stesso provvedimento.",
            campi={"hearing_mode": "presenza", "luogo": tribunale or _testo(getattr(appuntamento, "tribunale", "")),
                   "remote_hearing_mode": "", "remote_hearing_platform": "", "remote_hearing_access_info": ""},
            prove=[_prova(f) for f in prove[:3]],
        ))
    return piano


def _appuntamento_pec_intatto(app: Any) -> bool:
    """Confronta l'evento e le note con l'impronta dell'importazione in Agenda."""
    impronta = str(app.external_hash or "").split("|", 4)
    if len(impronta) != 5 or impronta[:4] != [app.titolo, app.data_ora, str(app.durata_minuti), app.luogo]:
        return False
    descrizione = impronta[-1].rsplit("|", 3)
    if len(descrizione) != 4 or descrizione[-1]:
        return False
    testo, _, organizzatore, _ = descrizione
    righe = [testo.strip(), f"Organizzatore: {organizzatore}" if organizzatore else "", "Sincronizzato da: Pec Audit",
             f"Sorgente: {app.external_source_url}" if app.external_source_url else "", f"UID esterno: {app.external_uid}"]
    return app.note == "\n".join(riga for riga in righe if riga)


def sostituzioni_documentate(fatti_correnti: Iterable[Any]) -> dict[tuple[str, str], list[tuple[Any, Any]]]:
    """Le date sostituite e i relativi termini, verificati nello stesso documento."""
    from pct.provvedimenti.termine_scritto import data_udienza_sostituita_nel_brano

    fatti_per_atto: dict[tuple[str, str], list[Any]] = {}
    for fatto in fatti_correnti:
        if fatto.tipo == "documento" and fatto.categoria == "data" and fatto.verifica in _VERIFICHE_UTILI:
            fatti_per_atto.setdefault((fatto.oggetto_id, fatto.sha256), []).append(fatto)
    esito: dict[tuple[str, str], list[tuple[Any, Any]]] = {}
    for (documento, _), fatti in fatti_per_atto.items():
        termini = [
            f for f in fatti if f.campo == "termine"
            and perentorieta_documentata(f) and any(
                p.get("codice") == "istituto" and p.get("esito") == "ok" and p.get("dettaglio") == "note_127_ter"
                for p in f.prove
            )
        ]
        if not termini:
            continue
        for fatto in fatti:
            if fatto.campo != "udienza" or not data_udienza_sostituita_nel_brano(fatto.contesto, fatto.valore_letto):
                continue
            giorno = _giorno(fatto.valore)
            distinti = [(fatto, termine) for termine in termini if _giorno(termine.valore) != giorno]
            if distinti:
                esito.setdefault((documento, giorno), []).extend(distinti)
    return {chiave: coppie for chiave, coppie in esito.items()
            if len({_giorno(termine.valore) for _, termine in coppie}) == 1}


def piano_udienze_sostituite(
    scadenze: Iterable[Any],
    appuntamenti: Iterable[Any],
    sostituzioni: dict[tuple[str, str], list[tuple[Any, Any]]],
    pec_per_documento: dict[str, str],
    *,
    oggi: date,
) -> list[tuple[Rettifica, Rettifica]]:
    """Ritira i promemoria automatici di comparizione se l'atto assegna un termine distinto per le note."""
    scadenze = list(scadenze)
    per_appuntamento: dict[str, list[Any]] = {}
    for riga in scadenze:
        if riferimento := _testo(getattr(riga, "id_appuntamento", "")):
            per_appuntamento.setdefault(riferimento, []).append(riga)

    piano = []
    for app in appuntamenti:
        if (_stato(app) not in {"PROGRAMMATO", "ANNULLATO"}
                or getattr(app, "external_provider", "") != "pec_audit"
                or getattr(app, "external_profile_id", "") != "pec_scadenziario"
                or _testo(getattr(app, "luogo", "")).casefold() != "modalità udienza da verificare"
                or getattr(app, "hearing_mode", "") != "incerta"):
            continue
        tipo_app = getattr(app, "tipo", "")
        if str(getattr(tipo_app, "value", tipo_app)) != "UDIENZA":
            continue
        collegate = per_appuntamento.get(app.id, [])
        if len(collegate) != 1:
            continue
        udienza = collegate[0]
        if _stato(app) == "ANNULLATO" and _stato(udienza) == "ANNULLATO":
            continue
        pec = _testo(getattr(udienza, "source_message_id", ""))
        giorno = _giorno(app.data_ora)
        tipo = str(getattr(getattr(udienza, "tipo", ""), "value", getattr(udienza, "tipo", "")))
        if (not pec or tipo != "UDIENZA" or _giorno(udienza.data_scadenza) != giorno or giorno < oggi.isoformat()
                or getattr(udienza, "deadline_profile_code", "") != "PEC_AUTO_PRESIDIO"
                or _stato(udienza) not in {"APERTO", "ANNULLATO"}
                or getattr(udienza, "id_utente_responsabile", "") not in {"", "scheduler"}
                or _testo(udienza.titolo) != _testo(app.titolo)
                or not str(app.external_uid).startswith(f"PEC_AUDIT:{pec}:")
                or not str(udienza.note).startswith(f"PEC_AUDIT:{pec}\n")):
            continue
        if _stato(udienza) == "APERTO" and _testo(getattr(udienza, "trace_json", "")) not in {"", "[]"}:
            continue
        if _stato(app) == "PROGRAMMATO" and not _appuntamento_pec_intatto(app):
            continue

        concordanti: dict[str, list[Any]] = {}
        for (documento, giorno_udienza), prove in sostituzioni.items():
            if pec_per_documento.get(documento) == pec and giorno_udienza == giorno:
                for sostituita, termine in prove:
                    concordanti.setdefault(_giorno(termine.valore), []).extend((sostituita, termine))
        if len(concordanti) != 1:
            continue

        data_note, prove = next(iter(concordanti.items()))
        documenti = {f"documento:{f.oggetto_id}" for f in prove}
        termini_attivi = [
            r for r in scadenze if _stato(r) == "APERTO" and _giorno(r.data_scadenza) == data_note
            and bool(getattr(r, "perentorio", False))
            and _testo(getattr(r, "hearing_mode_source", "")) in documenti
        ]
        if len(termini_attivi) != 1:
            continue
        giorno_note = date.fromisoformat(data_note)
        motivo = (
            f"Il provvedimento sostituisce l’udienza del {date.fromisoformat(giorno):%d/%m/%Y} "
            f"con il deposito di note entro il {giorno_note:%d/%m/%Y}. "
            "Il termine perentorio è registrato nello scadenziario e vale come data d’udienza "
            "(art. 127-ter c.p.c.)."
        )
        prova = [_prova(f) for f in prove]
        piano.append((
            Rettifica(udienza.id, "annulla", motivo, campi={"stato": "ANNULLATO"}, prove=prova),
            Rettifica(app.id, "sostituita", motivo, campi={"stato": "ANNULLATO"}, prove=prova),
        ))
    return piano


def piano_agenda_documentale_sostituita(
    appuntamenti: Iterable[Any], sostituzioni: dict[tuple[str, str], list[tuple[Any, Any]]], *, oggi: date,
) -> list[Rettifica]:
    """Ritira la sola comparizione scritta automaticamente dall'archivio con la fonte sostitutiva."""
    piano = []
    for app in appuntamenti:
        righe = str(app.note or "").splitlines()
        if (_stato(app) != "PROGRAMMATO" or len(righe) != 3
                or righe[0] != "Data e ora verificate nell’archivio."
                or not righe[1].startswith("ARCHIVIO_FATTO:")
                or not righe[2].startswith("Fonte: documento:")):
            continue
        giorno = _giorno(app.data_ora)
        if giorno < oggi.isoformat() or not giorno:
            continue
        chiave = (righe[2].removeprefix("Fonte: documento:"), giorno)
        coppie = sostituzioni.get(chiave, [])
        titolo = f"Udienza del {date.fromisoformat(giorno):%d/%m/%Y} ore {app.data_ora[11:16]}"
        if not coppie or _testo(app.titolo) != titolo:
            continue
        udienza, termine = coppie[0]
        data_note = date.fromisoformat(_giorno(termine.valore))
        piano.append(Rettifica(
            app.id, "sostituita",
            f"Il provvedimento sostituisce la comparizione con il deposito di note entro il {data_note:%d/%m/%Y}. "
            "Il giorno di scadenza vale come data d’udienza (art. 127-ter c.p.c.).",
            campi={"stato": "ANNULLATO"}, prove=[_prova(udienza), _prova(termine)],
        ))
    return piano


__all__ = ["PRIMA_RIGA", "Rettifica", "VERSIONE", "piano_agenda", "piano_agenda_documentale_sostituita", "piano_rettifiche", "piano_udienze_sostituite", "riga_intatta", "sostituzioni_documentate"]
