"""Le viste dell'archivio per i presìdi: udienze e termini, prove di notifica, ruoli, riassunto.

I presìdi non rileggono i documenti: chiedono all'archivio i fatti utili
(verificati, plausibili, corretti) e li usano nella forma che già conoscono.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from pct.registro_letture.fatti_repository import Fatto, VERIFICHE_UTILI

FORZA_PROVA = {"deposito_prova": 6, "rdac": 5, "rac": 4, "relata": 3, "attestazione": 2, "atto_notificato": 1, "comunicazione_cancelleria": 0, "errore_consegna": 0}
_ETICHETTA_VERIFICA = {"verificata": "verificata dal software", "plausibile": "da confermare", "corretta": "corretta dall'avvocato", "respinta": "respinta", "ignorata": "ignorata"}


def _giorno(valore: str) -> date | None:
    from pct.registro_letture.verifica_date import interpreta_data

    return interpreta_data(str(valore or "").split("T")[0])


def etichetta_verifica(verifica: str) -> str:
    return _ETICHETTA_VERIFICA.get(verifica, verifica)


def _istituto_del_fatto(fatto: Fatto):
    """L'istituto processuale che i motori hanno riconosciuto per quella data, se c'e'."""
    from .istituti_processuali import istituto_di

    codice = next((str(p.get("dettaglio") or "") for p in fatto.prove
                   if p.get("codice") == "istituto" and p.get("esito") == "ok"), "")
    return istituto_di(codice) if codice else None


def udienze_e_termini(fatti: Iterable[Fatto], *, oggi: date | None = None) -> list[dict[str, Any]]:
    """Le date di udienza e i termini letti, nella forma delle azioni del presidio documentale."""
    from .adempimenti import perentorieta_documentata
    oggi = oggi or date.today()
    fatti = list(fatti)
    azioni: list[dict[str, Any]] = []
    visti: set[tuple[str, str, str]] = set()
    for fatto in fatti:
        if fatto.categoria != "data" or fatto.campo not in {"udienza", "termine", "costituzione"} or fatto.verifica not in VERIFICHE_UTILI:
            continue
        giorno = _giorno(fatto.valore)
        if giorno is None:
            continue
        chiave = (fatto.campo, fatto.oggetto_id, giorno.isoformat())
        if chiave in visti:
            continue
        visti.add(chiave)
        # Se i motori hanno riconosciuto l'istituto, il presidio lo mostra con
        # il suo nome: «deposito di note ex art. 127-ter c.p.c.» dice cosa fare,
        # «termine del 10/09/2026» no.
        istituto = _istituto_del_fatto(fatto)
        etichetta = fatto.etichetta.casefold()
        note_scritte = (
            any(p.get("codice") == "modalita_note" and p.get("esito") == "ok" for p in fatto.prove)
            or (istituto is not None and istituto.codice == "note_127_ter")
            or (fatto.campo == "termine" and any(x in etichetta for x in ("note in sostituzione", "note scritte")))
        )
        tipo = istituto.codice if istituto else ("udienza_documento" if fatto.campo == "udienza" and not note_scritte else "termine_documento")
        ora = fatto.valore.split("T")[1][:5] if "T" in fatto.valore else ""
        azione = {
            "id": f"{tipo}-{fatto.oggetto_id}-{giorno.isoformat()}",
            "type": tipo,
            "title": istituto.titolo if istituto else ("Udienza letta dai documenti del fascicolo" if tipo == "udienza_documento" else "Termine processuale letto dai documenti del fascicolo"),
            "norma": istituto.norma if istituto else "",
            "description": f"Deposito note in sostituzione udienza del {giorno.strftime('%d/%m/%Y')}" if note_scritte else fatto.etichetta,
            "sourceContext": fatto.contesto,
            "dateIso": giorno.isoformat(),
            "date": giorno.strftime("%d/%m/%Y"),
            "time": ora,
            "rawDate": fatto.valore_letto,
            "documentId": fatto.oggetto_id,
            "objectType": fatto.tipo,
            "source": fatto.origine,
            "tone": "neutral" if giorno < oggi else "warning" if fatto.verifica != "plausibile" else "neutral",
            "priority": "normal" if giorno < oggi else "important" if fatto.verifica != "plausibile" else "normal",
            "verifica": fatto.verifica,
            "verificaLabel": etichetta_verifica(fatto.verifica),
            "prove": list(fatto.prove),
            "fattoId": fatto.id,
            "overdue": False,
            "historical": giorno < oggi,
            "dateCorrected": fatto.verifica == "corretta",
            "requiresConfirmation": fatto.verifica == "plausibile",
            "peremptory": perentorieta_documentata(fatto),
        }
        if note_scritte:
            azione.update({"hearingMode": "note_scritte", "hearingTime": ora})
        azioni.append(azione)
    azioni.sort(key=lambda voce: (voce["dateIso"], voce["type"]))
    return azioni


def prove_notifica_per_oggetto(fatti: Iterable[Fatto]) -> dict[str, dict[str, Any]]:
    """Per ogni documento o PEC la prova di notifica che ne dice la natura.

    Vince la prova menzionata per prima (l'intestazione «RELATA DI NOTIFICA»
    dice che cos'è il documento anche se poi cita le ricevute); a parità di
    posizione, la più forte. Tutte le prove lette restano in `tutte`.
    """
    esito: dict[str, dict[str, Any]] = {}
    for fatto in fatti:
        if fatto.categoria != "prova_notifica" or fatto.verifica not in VERIFICHE_UTILI:
            continue
        corrente = esito.get(fatto.oggetto_id)
        forza = FORZA_PROVA.get(fatto.campo, -1)
        chiave = (fatto.posizione, -forza)
        if corrente is None:
            esito[fatto.oggetto_id] = {"kind": fatto.campo, "forza": forza, "posizione": fatto.posizione, "etichetta": fatto.etichetta, "verifica": fatto.verifica, "origine": fatto.origine, "tipo": fatto.tipo, "contesto": fatto.contesto, "tutte": [fatto.campo]}
        else:
            corrente["tutte"].append(fatto.campo)
            if chiave < (corrente["posizione"], -corrente["forza"]):
                corrente.update({"kind": fatto.campo, "forza": forza, "posizione": fatto.posizione, "etichetta": fatto.etichetta, "verifica": fatto.verifica, "origine": fatto.origine, "contesto": fatto.contesto})
    return esito


def ruoli_letti(
    fatti: Iterable[Fatto],
    *,
    ufficio_giudiziario: str = "",
) -> list[dict[str, Any]]:
    from .collaudo import ruolo_compatibile_con_ufficio

    visti: dict[str, dict[str, Any]] = {}
    for fatto in fatti:
        if fatto.categoria != "ruolo" or fatto.verifica not in VERIFICHE_UTILI:
            continue
        if not ruolo_compatibile_con_ufficio(fatto, ufficio_giudiziario):
            continue
        voce = visti.setdefault(fatto.valore, {"valore": fatto.valore, "campo": fatto.campo, "verifica": fatto.verifica, "oggetti": []})
        if fatto.oggetto_id not in voce["oggetti"]:
            voce["oggetti"].append(fatto.oggetto_id)
        if fatto.verifica == "verificata":
            voce["verifica"] = "verificata"
    return sorted(visti.values(), key=lambda voce: (0 if voce["verifica"] == "verificata" else 1, voce["valore"]))


# Solo questi campi, se confermati, cambiano qualcosa per l'avvocato: entrano
# nell'agenda o nello scadenziario. Una data d'atto o di documento letta da un
# vecchio allegato non produce alcuna azione e non va chiesta.
CAMPI_DA_CONFERMARE = frozenset({"udienza", "termine", "costituzione"})


def da_confermare_ora(fatti: Iterable[Fatto], *, oggi: date | None = None) -> list[dict[str, Any]]:
    """Le sole date che, confermate, cambiano l'agenda o lo scadenziario.

    Una data plausibile già passata non si chiede: l'udienza si è tenuta e il
    termine è scaduto, quindi la conferma non produrrebbe alcuna azione. Così
    il riquadro chiede due conferme utili invece di dodici indistinte.
    """
    oggi = oggi or date.today()
    richieste: list[dict[str, Any]] = []
    visti: set[tuple[str, str, str]] = set()
    for fatto in fatti:
        if fatto.verifica != "plausibile" or fatto.categoria != "data" or fatto.campo not in CAMPI_DA_CONFERMARE:
            continue
        giorno = _giorno(fatto.valore)
        if giorno is None or giorno < oggi:
            continue
        chiave = (fatto.campo, giorno.isoformat(), fatto.oggetto_id)
        if chiave in visti:
            continue
        visti.add(chiave)
        richieste.append({
            "id": fatto.id, "campo": fatto.campo, "etichetta": fatto.etichetta, "valore": fatto.valore,
            "valore_letto": fatto.valore_letto, "oggetto_id": fatto.oggetto_id, "tipo": fatto.tipo,
            "contesto": fatto.contesto, "prove": list(fatto.prove),
            "fattoId": fatto.id,
        })
    return sorted(richieste, key=lambda voce: str(voce["valore"]))


def importi_letti(fatti: Iterable[Fatto]) -> dict[str, dict[str, Any]]:
    """Gli importi letti dai documenti, uno per campo: il più solido e il più recente.

    Il presidio economico consulta questa vista invece di riaprire i PDF: per
    ogni voce (contributo unificato, compenso liquidato, spese ed esborsi, fondo
    spese, beneficio) restituisce l'importo, il verdetto del collaudo, il
    documento da cui viene e la norma che lo governa.
    """
    from .estrazione_importi import CAMPI_IMPORTO

    migliori: dict[str, dict[str, Any]] = {}
    for fatto in fatti:
        if fatto.categoria != "importo" or fatto.verifica not in VERIFICHE_UTILI or fatto.campo not in CAMPI_IMPORTO:
            continue
        try:
            importo = float(fatto.valore)
        except (TypeError, ValueError):
            continue
        norma = next((str(prova.get("dettaglio") or "") for prova in fatto.prove if prova.get("codice") == "norma"), "")
        natura = next((str(prova.get("dettaglio") or "") for prova in fatto.prove if prova.get("codice") == "natura"), "")
        voce = {
            "campo": fatto.campo, "importo": importo, "valore": fatto.valore,
            "etichetta": fatto.etichetta, "titolo": fatto.valore_letto, "contesto": fatto.contesto,
            "verifica": fatto.verifica, "verifica_etichetta": etichetta_verifica(fatto.verifica),
            "documento_id": fatto.oggetto_id, "tipo": fatto.tipo, "origine": fatto.origine,
            "norma": norma, "natura": natura, "fatto_id": fatto.id,
            "stato_prova": next((str(p.get("dettaglio") or "") for p in fatto.prove if p.get("codice") == "stato" and p.get("esito") == "ok"), ""),
            # Il giorno del versamento: la ricevuta lo porta, e all'avvocato
            # serve quanto l'importo. Senza, la voce dice «pagato» ma non quando.
            "data_prova": next((str(p.get("dettaglio") or "") for p in fatto.prove if p.get("codice") == "data" and p.get("esito") == "ok"), ""),
        }
        corrente = migliori.get(fatto.campo)
        if corrente is None or _forza_verifica(fatto.verifica) > _forza_verifica(str(corrente["verifica"])):
            migliori[fatto.campo] = voce
    return migliori


def prospetti_letti(fatti: Iterable[Fatto]) -> list[dict[str, Any]]:
    """I prospetti a tabella letti nei documenti: righe, totale e prova dei conti.

    Il presidio economico li mostra per documento, senza sceglierne uno: una
    nota spese, una liquidazione e un precetto dello stesso fascicolo sono
    prospetti diversi, e la voce da registrare la sceglie l'avvocato.
    """
    import json

    voci: list[dict[str, Any]] = []
    for fatto in fatti:
        if fatto.categoria != "importo" or fatto.campo != "prospetto_tabellare" or fatto.verifica not in VERIFICHE_UTILI:
            continue
        tabella = next((p for p in fatto.prove if p.get("codice") == "tabella"), {})
        somma = next((p for p in fatto.prove if p.get("codice") == "somma"), {})
        try:
            dati = json.loads(str(tabella.get("dettaglio") or "{}"))
        except ValueError:
            dati = {}
        voci.append({
            "fattoId": fatto.id, "documentoId": fatto.oggetto_id, "etichetta": fatto.etichetta,
            "totale": fatto.valore, "righe": list(dati.get("righe") or []), "pagina": dati.get("pagina") or 0,
            "origine": str(dati.get("origine") or ""), "somma": str(somma.get("esito") or ""),
            "sommaDettaglio": str(somma.get("dettaglio") or ""),
            "norma": next((str(p.get("dettaglio") or "") for p in fatto.prove if p.get("codice") == "norma"), ""),
            "verifica": fatto.verifica, "verificaEtichetta": etichetta_verifica(fatto.verifica),
        })
    return voci


# Gli eventi che il presidio PEC riconosce sono fatti della causa: il rinvio
# d'ufficio, la fissazione, il deposito del provvedimento. Entrano in cronologia
# con il giorno della PEC che li comunica.
ETICHETTE_EVENTO = {
    "fissazione_note": "Fissazione del termine per note scritte", "riassegnazione_note": "Riassegnazione del termine per note scritte",
    "rinvio": "rinvio", "fissazione_udienza": "fissazione di udienza", "deposito_provvedimento": "deposito del provvedimento",
    "comunicazione_cancelleria": "comunicazione di cancelleria", "notifica": "notifica", "iscrizione_a_ruolo": "iscrizione a ruolo",
    "sentenza": "sentenza", "ordinanza": "ordinanza", "decreto": "decreto", "termine": "termine",
}


def eventi_letti(fatti: Iterable[Fatto], *, oggi: date | None = None) -> list[dict[str, Any]]:
    """Gli eventi processuali letti dalle PEC, datati e pronti per la cronologia.

    Il motore PEC li produce dalla classificazione del presidio (famiglia ed
    evento primario) e vi allega il giorno di ricezione certificato: qui
    diventano voci con una data, così non restano un numero nel riassunto.
    Un evento senza data non si mostra: in cronologia non avrebbe posto.
    """
    oggi = oggi or date.today()
    voci: list[dict[str, Any]] = []
    visti: set[tuple[str, str, str]] = set()
    for fatto in fatti:
        if fatto.categoria != "evento" or fatto.verifica not in VERIFICHE_UTILI:
            continue
        grezza = next((str(prova.get("dettaglio") or "") for prova in fatto.prove if prova.get("codice") == "data"), "")
        giorno = _giorno(grezza)
        if giorno is None:
            continue
        chiave = (fatto.campo, giorno.isoformat(), fatto.oggetto_id)
        if chiave in visti:
            continue
        visti.add(chiave)
        voci.append({
            "id": fatto.id or f"evento-{fatto.oggetto_id}-{giorno.isoformat()}",
            "campo": fatto.campo,
            "famiglia": fatto.valore,
            "etichetta": ETICHETTE_EVENTO.get(fatto.campo, fatto.etichetta or fatto.campo.replace("_", " ")),
            "data_iso": giorno.isoformat(),
            "data": giorno.strftime("%d/%m/%Y"),
            "contesto": fatto.contesto,
            "oggetto_id": fatto.oggetto_id,
            "tipo": fatto.tipo,
            "origine": fatto.origine,
            "verifica": fatto.verifica,
            "verifica_etichetta": etichetta_verifica(fatto.verifica),
            "passato": giorno <= oggi,
        })
    voci.sort(key=lambda voce: (voce["data_iso"], voce["campo"]))
    return voci


def _forza_verifica(verifica: str) -> int:
    return {"corretta": 3, "verificata": 2, "plausibile": 1}.get(verifica, 0)


def riassunto_archivio(fatti: Iterable[Fatto], *, oggi: date | None = None) -> dict[str, Any]:
    """Il riassunto per il pannello: quanti fatti per verdetto, udienze, termini, prove, ruoli, conferme utili."""
    elenco = list(fatti)
    per_verifica = {"verificata": 0, "plausibile": 0, "respinta": 0, "corretta": 0, "ignorata": 0}
    for fatto in elenco:
        per_verifica[fatto.verifica] = per_verifica.get(fatto.verifica, 0) + 1
    utili = [fatto for fatto in elenco if fatto.verifica in VERIFICHE_UTILI]
    da_confermare = da_confermare_ora(elenco, oggi=oggi)
    return {
        "totale": len(elenco),
        "per_verifica": per_verifica,
        "udienze": sum(1 for fatto in utili if fatto.categoria == "data" and fatto.campo == "udienza"),
        "termini": sum(1 for fatto in utili if fatto.categoria == "data" and fatto.campo in {"termine", "costituzione", "decorrenza"}),
        "notifiche": sum(1 for fatto in utili if fatto.categoria == "data" and fatto.campo in {"notifica", "accettazione", "consegna"}),
        "prove_notifica": sum(1 for fatto in utili if fatto.categoria == "prova_notifica"),
        "ruoli": len(ruoli_letti(utili)),
        "eventi": sum(1 for fatto in utili if fatto.categoria == "evento"),
        "importi": len(importi_letti(utili)),
        "per_motore": {"documenti": sum(1 for fatto in utili if fatto.motore == "documenti"), "pec": sum(1 for fatto in utili if fatto.motore == "pec")},
        "da_confermare": da_confermare[:12],
    }


__all__ = ["CAMPI_DA_CONFERMARE", "ETICHETTE_EVENTO", "FORZA_PROVA", "da_confermare_ora", "etichetta_verifica", "eventi_letti", "importi_letti", "prospetti_letti", "prove_notifica_per_oggetto", "riassunto_archivio", "ruoli_letti", "udienze_e_termini"]
