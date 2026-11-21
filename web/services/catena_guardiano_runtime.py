"""Il guardiano della catena in esercizio: controlla un fascicolo, ripara con la regola giusta, registra il motivo.

Quando gira (``pct/catena/mappa.py``):
- dopo ogni evento sul fascicolo, a bassa priorità: il calcolatore dei pannelli pronti lo chiama appena ha ricalcolato
  la Lettura (``pannelli_pronti_calcolatore._dopo_lettura``), quindi lo raggiunge ogni fonte che cambia l'impronta
  (documento, PEC, catalogo, fatto, scadenza, appuntamento, parcella o incasso, decisione, giorno, versione);
- alla fine del ciclo delle letture (``prepara_lettura_in_cache``), con la Lettura appena preparata;
- ogni notte su tutti i fascicoli non archiviati (lavoro ``guardiano_catena_notturno``).

Riparazioni: solo su righe automatiche e intatte; mai sulle decisioni dell'avvocato (responsabile assegnato, righe
scritte a mano, stato del fascicolo). Ogni riparazione è registrata (registro del guardiano, traccia e nota della
scadenza o dell'appuntamento). Dopo ``TENTATIVI_MASSIMI`` riparazioni non riuscite l'incoerenza diventa un avviso.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from flask import g, has_request_context

from pct.catena import guardiano as regole
from pct.catena.registro import TENTATIVI_MASSIMI, RegistroGuardiano, percorso

logger = logging.getLogger(__name__)
ATTORE = "guardiano della catena"
IN_AGGIORNAMENTO = "in_aggiornamento"


def registro_corrente(data_paths: dict[str, Any] | None = None) -> RegistroGuardiano | None:
    """Il registro dello studio: accanto a ``studio.db`` (percorsi dello studio o, nello studio unico, configurazione)."""
    from flask import current_app, has_app_context

    percorsi = data_paths if data_paths is not None else (dict(getattr(g, "data_paths", {}) or {}) if has_request_context() else {})
    if not percorsi.get("STUDIO_DB") and has_app_context():
        from pathlib import Path

        studio_db = current_app.config.get("STUDIO_DB") or ""
        fascicoli_db = percorsi.get("FASCICOLI_DB") or current_app.config.get("FASCICOLI_DB") or ""
        if not studio_db and fascicoli_db:
            studio_db = str(Path(str(fascicoli_db)).resolve().parent.parent / "studio.db")
        if studio_db:
            percorsi = {**percorsi, "STUDIO_DB": studio_db}
    file = percorso(percorsi)
    return RegistroGuardiano(file) if file else None


# --- riparazioni -------------------------------------------------------------------------------------------------

def _riga(scadenza: Any) -> dict[str, Any]:
    """La scadenza come la vede il guardiano, con il responsabile riconosciuto fra gli utenti dello studio."""
    from web.services.catena_guardiano_raccolta import responsabile_umano, utenti_dello_studio

    responsabile = getattr(scadenza, "id_utente_responsabile", "") or ""
    return {"note": scadenza.note, "id_utente_responsabile": responsabile,
            "responsabile_umano": responsabile_umano(responsabile, utenti_dello_studio())}


def _tipo_termine(dati: dict[str, Any]):
    from pct.scadenziario import TipoTermine

    codice = str(dati.get("codice_conclusione") or "")
    if dati.get("perentorio"):
        return TipoTermine.TERMINE_PERENTORIO
    if codice.startswith("notifica"):
        return TipoTermine.NOTIFICA
    if codice in {"note_127ter", "deposito_ordinato"}:
        return TipoTermine.DEPOSITO_ATTO
    if codice.startswith("termine_impugnazione"):
        return TipoTermine.IMPUGNAZIONE
    return TipoTermine.ADEMPIMENTO


def _crea_scadenza(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    from web.helpers import get_scadenziario

    dati = voce.dati
    scadenziario = get_scadenziario()
    # Idempotenza: la stessa conclusione dello stesso giorno già scritta dal guardiano non si duplica.
    for s in scadenziario.tutte(id_fascicolo=contesto["fascicolo_id"], solo_aperte=False):
        if regole.MARCATORE + str(dati.get("codice_conclusione")) in (s.note or "") and str(s.data_scadenza or "")[:10] == dati["data"]:
            return f"riparata: già presente ({s.id})"
    nuova = scadenziario.nuova(
        titolo=str(dati.get("cosa") or "Termine")[:160], tipo=_tipo_termine(dati), data_scadenza=dati["data"],
        id_fascicolo=contesto["fascicolo_id"], descrizione=voce.perche[:300],
        note=regole.nota_scadenza(dati, contesto.get("impronta_modello", "")), perentorio=bool(dati.get("perentorio")),
    )
    return f"riparata: scadenza {nuova.id} creata dal modello della causa"


def _conferma_bozza(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    """La proposta certa si conferma con la prova; le proposte doppie dello stesso termine si scartano."""
    from pct.scadenziario import StatoTermine
    from web.helpers import get_scadenziario
    from web.services.termini_certi_runtime import conferma_termini_certi

    conferma_termini_certi(contesto["fascicolo_id"], contesto["lettura"])
    scadenziario = get_scadenziario()
    stesse = [s for s in scadenziario.tutte(id_fascicolo=contesto["fascicolo_id"], solo_aperte=False)
              if str(s.data_scadenza or "")[:10] == voce.dati.get("data")
              and regole.codice_scadenza({"titolo": s.titolo, "note": s.note}) in {voce.dati.get("codice_conclusione"), ""}]
    aperte = [s for s in stesse if s.stato == StatoTermine.APERTO]
    bozze = [s for s in stesse if s.stato == StatoTermine.BOZZA
             and regole.automatica(_riga(s))]
    prova = (f"termine letto in «{voce.dati.get('documento') or ''}» e calcolato dal modello della causa: "
             f"scadenza {regole.data_it(voce.dati.get('data'))}")
    if not aperte and bozze:
        scadenziario.conferma_bozza(bozze[0].id, attore=f"{ATTORE} ({prova})")
        aperte, bozze = [bozze[0]], bozze[1:]
    for doppia in bozze:
        scadenziario.scarta_bozza(doppia.id, motivo=f"doppione del termine confermato «{aperte[0].titolo}»", attore=ATTORE)
    return f"riparata: proposta confermata con la prova ({prova})" if aperte else "non riuscita: nessuna proposta da confermare"


def _scarta_bozza(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    from web.helpers import get_scadenziario

    scadenziario = get_scadenziario()
    scadenza = scadenziario.get(str(voce.dati.get("scadenza_id") or ""))
    if scadenza is None:
        return "riparata: la proposta non c'è più"
    if regole._stato({"stato": getattr(scadenza.stato, "value", scadenza.stato)}) != "BOZZA":
        return _annulla_scadenza(contesto, voce)
    scadenziario.scarta_bozza(scadenza.id, motivo=voce.perche[:300], attore=ATTORE)
    return f"riparata: proposta {scadenza.id} scartata ({voce.codice})"


def _annulla_scadenza(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    from pct.scadenziario import StatoTermine
    from web.helpers import get_scadenziario

    scadenziario = get_scadenziario()
    scadenza = scadenziario.get(str(voce.dati.get("scadenza_id") or ""))
    if scadenza is None:
        return "riparata: la scadenza non c'è più"
    if not regole.automatica(_riga(scadenza)):
        return "non riuscita: la scadenza è dell'avvocato"
    nota = (scadenza.note or "") + f"\nAnnullata dal {ATTORE}: {voce.descrizione} — {voce.perche}"
    scadenziario.aggiorna(scadenza.id, stato=StatoTermine.ANNULLATO, note=nota.strip())
    return f"riparata: scadenza {scadenza.id} annullata ({voce.codice})"


def _crea_udienza(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    from pct.agenda import TipoAppuntamento
    from pct.agenda_eventi_equivalenti import ORA_DA_CONFERMARE, riunisci_fonte, udienza_equivalente
    from web.helpers import get_agenda

    fascicolo, dati = contesto["fascicolo"], voce.dati
    ora = str(dati.get("ora") or "")[:5]
    data_ora = f"{dati['data']}T{ora or '09:00'}:00"
    numero, anno = str(getattr(fascicolo, "numero_rg", "") or ""), str(getattr(fascicolo, "anno_rg", "") or "")
    procedimento = f"RG {numero}/{anno}" if numero and anno else ""
    agenda = get_agenda()
    fonte = f"{regole.MARCATORE}udienza:{dati.get('documento_id') or ''}"
    equivalente = udienza_equivalente(agenda.tutti(), id_fascicolo=contesto["fascicolo_id"], procedimento=procedimento,
                                      data_ora=data_ora, ora_certa=bool(ora))
    if equivalente is not None:
        riunisci_fonte(agenda, equivalente, fonte=fonte, data_ora=data_ora, ora_certa=bool(ora))
        return f"riparata: udienza già in agenda ({equivalente.id}), aggiunta la fonte"
    modalita = dati.get("modalita") or ""
    nuova = agenda.aggiungi(
        titolo=f"Udienza {procedimento}".strip(), tipo=TipoAppuntamento.UDIENZA, data_ora=data_ora, durata_minuti=60,
        luogo=str(getattr(fascicolo, "tribunale", "") or ""), allow_overlap=True, procedimento=procedimento,
        tribunale=str(getattr(fascicolo, "tribunale", "") or ""), cliente=str(getattr(fascicolo, "nome_cliente", "") or ""),
        id_cliente=str(getattr(fascicolo, "id_cliente", "") or ""), id_fascicolo=contesto["fascicolo_id"],
        hearing_mode="note_scritte" if modalita == "note_scritte" else "",
        note="\n".join(filter(None, (
            f"Udienza fissata con «{dati.get('documento') or ''}», letta dal modello della causa.", fonte,
            "Trattazione sostituita dal deposito di note scritte (art. 127-ter c.p.c.)." if modalita == "note_scritte" else "",
            "" if ora else ORA_DA_CONFERMARE))),
    )
    return f"riparata: udienza {nuova.id} in agenda"


def _aggiorna_modalita(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    from web.helpers import get_agenda

    agenda = get_agenda()
    appuntamento = agenda.get(str(voce.dati.get("appuntamento_id") or ""))
    if appuntamento is None:
        return "riparata: l'appuntamento non c'è più"
    note = (appuntamento.note or "") + f"\nModalità riconciliata dal {ATTORE}: trattazione scritta (art. 127-ter c.p.c.), " \
                                       f"fonte «{voce.dati.get('documento') or ''}»."
    agenda.modifica(appuntamento.id, hearing_mode="note_scritte", note=note.strip())
    return f"riparata: modalità dell'udienza {appuntamento.id} aggiornata"


def _riconcilia_adempimenti(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    from web.services.consegna_presidi_runtime import riconcilia_adempimenti, riconcilia_notifiche_ordinate
    from web.services.registro_letture_runtime import registro_corrente as registro_letture, tenant_corrente

    notifiche = riconcilia_notifiche_ordinate(contesto["fascicolo"], contesto["lettura"])
    esito = riconcilia_adempimenti(contesto["fascicolo"], registro_letture(), tenant_corrente(), lettura=contesto["lettura"])
    completate = int(esito.get("completate") or 0) + len(notifiche or [])
    return f"riparata: {completate} scadenze completate con la prova" if completate else "non riuscita: nessuna prova correlata"


def _ricalcolo(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    archivio = contesto.get("archivio")
    if archivio is None:
        return "non riuscita: pannelli pronti non disponibili"
    pannello = str(voce.dati.get("pannello") or "")
    archivio.invalida_pannelli(contesto["fascicolo_id"], (pannello,) if pannello else ("lettura",))
    try:
        from web.services.pannelli_pronti_calcolatore import sveglia_calcolatore

        sveglia_calcolatore()
    except OSError:
        logger.debug("Calcolatore non svegliato per %s", contesto["fascicolo_id"])
    return f"riparata: ricalcolo del pannello «{pannello}» richiesto (nel frattempo «in aggiornamento»)"


def _prepara_bozze(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    from web.services.bozze_passi_runtime import prepara_bozze_fascicolo

    esito = prepara_bozze_fascicolo(contesto["fascicolo_id"], lettura=contesto["lettura"], conto=contesto.get("conto"))
    return f"riparata: bozze riallineate ai passi ({esito})"


def _aggiorna_norma(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    from web.helpers import get_scadenziario

    scadenziario = get_scadenziario()
    scadenza = scadenziario.get(str(voce.dati.get("scadenza_id") or ""))
    if scadenza is None:
        return "riparata: la scadenza non c'è più"
    righe = [f"Norma: {voce.dati.get('norma') or ''}" if r.startswith("Norma: ") else r for r in (scadenza.note or "").splitlines()]
    righe.append(f"Norma aggiornata dal {ATTORE}: {voce.perche}")
    scadenziario.aggiorna(scadenza.id, note="\n".join(righe))
    return f"riparata: norma della scadenza {scadenza.id} allineata al modello"


def _riconvalida_ciclo(contesto: dict[str, Any], voce: regole.Incoerenza) -> str:
    from web.services.registro_letture_runtime import registro_corrente as registro_letture, tenant_corrente

    accodato = registro_letture().accoda_evento(tenant_corrente(), contesto["fascicolo_id"], presidi=True)
    return "riparata: ciclo delle letture rimesso in coda con la consegna ai presìdi" if accodato else \
        "riparata: il ciclo delle letture è già in coda"


RIPARATORI: dict[str, Callable[[dict[str, Any], regole.Incoerenza], str]] = {
    regole.CREA_SCADENZA: _crea_scadenza, regole.CONFERMA_BOZZA: _conferma_bozza, regole.SCARTA_BOZZA: _scarta_bozza,
    regole.ANNULLA_SCADENZA: _annulla_scadenza, regole.CREA_UDIENZA: _crea_udienza,
    regole.AGGIORNA_MODALITA: _aggiorna_modalita, regole.RICONCILIA_ADEMPIMENTI: _riconcilia_adempimenti,
    regole.RICALCOLO: _ricalcolo, regole.PREPARA_BOZZE: _prepara_bozze, regole.RICONVALIDA_CICLO: _riconvalida_ciclo,
    regole.AGGIORNA_NORMA: _aggiorna_norma,
}
# Riparazioni che hanno bisogno della Lettura corrente (le altre bastano i dati dell'incoerenza).
_CON_LETTURA = {regole.CONFERMA_BOZZA, regole.RICONCILIA_ADEMPIMENTI, regole.PREPARA_BOZZE}


# --- controllo del fascicolo -------------------------------------------------------------------------------------

def controlla_fascicolo(fascicolo_id: str, *, origine: str, applica: bool = True, lettura: dict[str, Any] | None = None,
                        conto: dict[str, Any] | None = None, data_paths: dict[str, Any] | None = None,
                        oggi=None, registra: bool = True, anche_superati: bool = False) -> dict[str, Any]:
    """Controlla un fascicolo nel contesto dello studio corrente; con ``applica`` ripara e registra.

    ``lettura``: la Lettura appena calcolata dal chiamante (fine del ciclo delle letture, collaudo); senza, quella
    salvata per l'impronta attuale. ``anche_superati``: per la misura in sola lettura usa anche l'ultimo payload salvato.
    """
    from pct.ora_italiana import oggi_roma
    from web.helpers import get_fascicoli
    from web.services.catena_guardiano_raccolta import stato_fascicolo
    from web.services.pannelli_pronti_runtime import archivio_per_percorsi, fonti_per_percorsi

    percorsi = data_paths if data_paths is not None else dict(getattr(g, "data_paths", {}) or {})
    fascicolo = get_fascicoli().get(fascicolo_id)
    if fascicolo is None:
        return {"ok": False, "fascicolo_id": fascicolo_id, "esito": "fascicolo non trovato", "incoerenze": []}
    archivio, fonti = archivio_per_percorsi(percorsi), fonti_per_percorsi(percorsi)
    stato, impronta = stato_fascicolo(fascicolo, percorsi, archivio=archivio, fonti=fonti, oggi=oggi or oggi_roma(),
                                      lettura=lettura, anche_superati=anche_superati)
    esito = IN_AGGIORNAMENTO if stato.lettura is None else "controllato"
    contesto = {"fascicolo_id": fascicolo_id, "fascicolo": fascicolo, "lettura": stato.lettura, "conto": conto,
                "archivio": archivio,
                "impronta_modello": ((stato.lettura or {}).get("ragionamento") or {}).get("impronta", "")}
    registro = registro_corrente(percorsi) if registra else None
    voci = []
    for incoerenza in regole.controlla(stato):
        voce = incoerenza.come_dizionario()
        tentativi = registro.tentativi(fascicolo_id, incoerenza.chiave) if registro else 0
        riparabile = bool(incoerenza.riparazione) and tentativi < TENTATIVI_MASSIMI and (
            incoerenza.riparazione not in _CON_LETTURA or stato.lettura is not None)
        if incoerenza.riparazione and not riparabile:
            voce["avviso"] = True
            voce["esito_riparazione"] = (f"la regola «{incoerenza.riparazione}» non ha chiuso l'incoerenza dopo "
                                         f"{tentativi} tentativi" if tentativi else "")
        elif riparabile and applica:
            try:
                voce["esito_riparazione"] = RIPARATORI[incoerenza.riparazione](contesto, incoerenza)
            except Exception as exc:  # una riparazione non ferma le altre
                logger.warning("Riparazione %s non riuscita per %s: %s", incoerenza.riparazione, fascicolo_id, exc)
                voce["esito_riparazione"] = f"non riuscita: {type(exc).__name__}: {exc}"[:300]
        voci.append(voce)
    conteggi = registro.registra_giro(fascicolo_id, origine=origine, impronta=impronta or "", esito=esito, voci=voci,
                                      versione=regole.VERSIONE) if registro and applica else {}
    return {"ok": True, "fascicolo_id": fascicolo_id, "esito": esito, "incoerenze": voci, "conteggi": conteggi,
            "oggi": stato.oggi.isoformat()}


def payload_fascicolo(fascicolo_id: str) -> dict[str, Any]:
    """Gli avvisi del guardiano per il fascicolo e il suo registro (pagina del fascicolo)."""
    registro = registro_corrente()
    if registro is None:
        from pct.catena.esito import esito_anelli

        return {"ok": True, "fascicoloId": fascicolo_id, "stato": "non_disponibile", "statoEtichetta": "Controllo non disponibile",
                "anelli": esito_anelli(stato="non_disponibile", avvisi=[], riparate=[]), "avvisi": [], "riparazioni": [],
                "giri": []}
    ultimo = registro.ultimo_giro(fascicolo_id)
    from web.services.pannelli_pronti_runtime import impronta_fascicolo_corrente

    try:
        attuale = impronta_fascicolo_corrente(fascicolo_id) or ""
    except Exception:
        attuale = ""
    aggiornato = bool(ultimo and ultimo.get("esito") != IN_AGGIORNAMENTO and (not attuale or ultimo.get("impronta") == attuale))
    from pct.catena.esito import anello_di, esito_anelli

    stato = "verificato" if aggiornato else IN_AGGIORNAMENTO if ultimo else "mai_controllato"
    avvisi = registro.avvisi(fascicolo_id)
    riparate = registro.incoerenze(fascicolo_id, stato="riparata", limite=20)
    return {
        "ok": True, "fascicoloId": fascicolo_id,
        "stato": stato,
        "statoEtichetta": "Catena verificata" if aggiornato else "Controllo in aggiornamento" if ultimo else "Controllo non ancora eseguito",
        "ultimoControllo": ultimo,
        "anelli": esito_anelli(stato=stato, avvisi=avvisi, riparate=riparate),
        "avvisi": [{"codice": a["codice"], "anello": anello_di(a), "descrizione": a["descrizione"], "perche": a["perche"],
                    "norma": a["norma"], "dal": a["prima_vista"]} for a in avvisi],
        "riparazioni": [{"codice": a["codice"], "anello": anello_di(a), "descrizione": a["descrizione"],
                         "esito": a["esito_riparazione"], "quando": a["ultima_vista"]} for a in riparate],
        "giri": registro.giri(fascicolo_id=fascicolo_id, limite=20),
    }


def payload_studio(limite: int = 200) -> dict[str, Any]:
    """Il registro dei controlli dello studio: riepilogo per tipo e ultimi giri."""
    from pct.catena.mappa import descrizione

    registro = registro_corrente()
    return {"ok": True, "riepilogo": registro.riepilogo() if registro else {},
            "avvisi": registro.incoerenze(stato="avviso", limite=limite) if registro else [],
            "giri": registro.giri(limite=limite) if registro else [], "mappa": descrizione()}


# --- giri in sfondo ----------------------------------------------------------------------------------------------

@contextmanager
def _contesto_studio(app, owner) -> Iterator[None]:
    from pct.tenant import GestioneTenant
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context

    with app.test_request_context("/__scheduler/guardiano-catena"):
        if owner is not None:
            _attach_tenant_context(GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]), owner)
        yield


def _studi(app) -> list[tuple[Any, dict[str, Any]]]:
    """Gli studi attivi come per i pannelli pronti; nello studio unico senza percorsi di studio, la configurazione."""
    from web.services.pannelli_pronti_sfondo import studi

    elenco = list(studi(app))
    if elenco or app.config.get("MULTI_TENANT"):
        return elenco
    with app.test_request_context("/__scheduler/guardiano-catena"):
        registro = registro_corrente()
    return [(None, {"STUDIO_DB": str(registro.file.parent.parent / "studio.db")})] if registro else []


def _non_archiviati() -> list[str]:
    from web.helpers import get_fascicoli

    return sorted(f.id for f in get_fascicoli().tutti()
                  if str(getattr(getattr(f, "stato", ""), "value", getattr(f, "stato", ""))).upper() not in {"ARCHIVIATO", "CHIUSO"})


def giro(app, *, fascicoli: dict[str, set[str]] | None = None, origine: str = "dopo_lettura",
         limite: int | None = None) -> dict[str, int]:
    """Un giro per studio: i fascicoli indicati (dopo un evento) o tutti i non archiviati (notte)."""
    totale = {"fascicoli": 0, "incoerenze": 0, "riparate": 0, "avvisi": 0, "in_aggiornamento": 0, "errori": 0}
    for owner, data_paths in _studi(app):
        slug = str(getattr(owner, "slug", "") or "single-studio")
        if fascicoli is not None and slug not in fascicoli:
            continue
        with _contesto_studio(app, owner):
            elenco = sorted(fascicoli[slug]) if fascicoli is not None else _non_archiviati()
            for fascicolo_id in elenco[:limite] if limite else elenco:
                try:
                    esito = controlla_fascicolo(fascicolo_id, origine=origine, data_paths=data_paths)
                except Exception as exc:  # un fascicolo non blocca gli altri
                    logger.warning("Guardiano della catena non eseguito per %s: %s", fascicolo_id, exc)
                    totale["errori"] += 1
                    continue
                totale["fascicoli"] += 1
                totale["in_aggiornamento"] += esito.get("esito") == IN_AGGIORNAMENTO
                for chiave in ("incoerenze", "riparate", "avvisi"):
                    totale[chiave] += int((esito.get("conteggi") or {}).get(chiave) or 0)
    return totale


__all__ = ["RIPARATORI", "controlla_fascicolo", "giro", "payload_fascicolo", "payload_studio", "registro_corrente"]
