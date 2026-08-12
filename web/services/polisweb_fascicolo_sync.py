"""Sincronizzazione on-demand di un fascicolo dai registri di cancelleria (PST).

Base normativa: consultazione dei registri tramite i servizi ufficiali del
Portale Servizi Telematici (D.M. 44/2011; specifiche DGSIA). Doppio canale
conforme, deciso dalla configurazione dello studio:

- certificato P12/PEM configurato sul server (``_polis_auth_mode() == "reale"``)
  → interrogazione diretta QBuilder e aggiornamento del fascicolo;
- solo token PKCS#11 → nessuna interrogazione autonoma: si restituisce una
  indicazione operativa per il percorso assistito (Local Signer / import),
  senza mai usare il ramo demo su superfici reali.

Il download dei documenti resta presidiato: qui si aggiornano solo metadati,
eventi e catalogo (vista a buste), mai i file.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from pct.polisWeb import ClientPolisWebDemo, crea_client
from pct.scadenziario import StatoTermine, TipoTermine
from pct.scadenze_proposte_polisweb import (
    bozza_marker,
    bozza_scadenza_fields,
    select_event_candidates,
)


def _proponi_scadenze_da_eventi(
    client: Any,
    fascicolo: Any,
    *,
    ufficio: str,
    numero_rg: str,
    anno_rg: int,
    get_scadenziario: Callable[[], Any] | None,
    attore: str,
) -> int:
    """Crea proposte in BOZZA dagli eventi/scadenze futuri letti dal registro.

    Fail-closed: nessuna scadenza operativa senza conferma. Idempotente per
    (fascicolo, evento) via marcatore nelle note; deduplica contro le date gia'
    presenti nello scadinziario del fascicolo (incluse quelle create dalla PEC).
    """

    if get_scadenziario is None:
        return 0
    try:
        eventi = client.consulta_scadenze(
            ufficio,
            numero_rg,
            anno_rg,
            registro=str(getattr(fascicolo, "tipo_registro", "") or ""),
            ruolo_polisweb=str(getattr(fascicolo, "ruolo_polisweb", "") or "AVV"),
            sub_procedimento=str(getattr(fascicolo, "sub_procedimento", "") or ""),
            id_dfa=str(getattr(fascicolo, "id_dfa", "") or ""),
            servizio_pst_preferito=str(getattr(fascicolo, "servizio_pst", "") or ""),
        )
    except Exception:
        return 0
    if not eventi:
        return 0
    manager = get_scadenziario()
    fascicolo_id = str(getattr(fascicolo, "id", "") or "")
    esistenti = [
        item for item in manager.tutte(solo_aperte=False)
        if str(getattr(item, "id_fascicolo", "") or "") == fascicolo_id
    ]
    date_gia_presenti = {
        str(getattr(item, "data_scadenza", "") or "")[:10]
        for item in esistenti
        if str(getattr(item, "stato", "")) not in {StatoTermine.ANNULLATO.value, StatoTermine.ANNULLATO}
    }
    date_gia_presenti.discard("")
    note_esistenti = " \n ".join(str(getattr(item, "note", "") or "") for item in esistenti)
    candidati = select_event_candidates(
        eventi,
        today=date.today(),
        date_gia_presenti=date_gia_presenti,
    )
    creati = 0
    for evento in candidati:
        marker = bozza_marker(fascicolo_id, ufficio, f"{numero_rg}/{anno_rg}", evento.chiave())
        if marker in note_esistenti:
            continue
        fields = bozza_scadenza_fields(evento, fascicolo_id=fascicolo_id, ufficio=ufficio, rg=f"{numero_rg}/{anno_rg}")
        try:
            manager.nuova(
                titolo=fields.pop("titolo"),
                tipo=TipoTermine.UDIENZA if getattr(evento, "tipo", "") == "udienza" else TipoTermine.ADEMPIMENTO,
                data_scadenza=fields.pop("data_scadenza"),
                id_fascicolo=fields.pop("id_fascicolo"),
                descrizione=fields.pop("descrizione"),
                note=fields.pop("note"),
                id_utente_responsabile=attore,
                stato=StatoTermine.BOZZA,
                **fields,
            )
            creati += 1
        except Exception:
            continue
    return creati


def sincronizza_fascicolo_da_registro(
    fascicolo_id: str,
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_soggetti: Callable[[], Any] | None = None,
    get_scadenziario: Callable[[], Any] | None = None,
    auth_mode: str = "",
    avvocato_referente: str = "",
) -> dict[str, Any]:
    """Aggiorna un fascicolo dal registro. Ritorna esito con messaggi operativi."""

    gestione_fascicoli = get_fascicoli()
    fascicolo = gestione_fascicoli.get(fascicolo_id)
    if fascicolo is None:
        return {"ok": False, "message": "Fascicolo non trovato."}
    numero_rg = str(getattr(fascicolo, "numero_rg", "") or "").strip()
    anno_rg = int(getattr(fascicolo, "anno_rg", 0) or 0)
    ufficio = str(
        getattr(fascicolo, "codice_ufficio_portale", "")
        or getattr(fascicolo, "tribunale", "")
        or ""
    ).strip()
    if not numero_rg or not anno_rg or not ufficio:
        return {
            "ok": False,
            "rg_mancante": True,
            "message": (
                "Per allinearsi al registro servono numero di ruolo, anno e ufficio: "
                "completa l'RG dal portale o da un provvedimento."
            ),
        }
    if auth_mode != "reale":
        return {
            "ok": False,
            "requires_local_signer": True,
            "message": (
                "Nessun certificato dello studio configurato sul server: la consultazione "
                "del registro avviene con smart card tramite il percorso assistito "
                "(Portali telematici → PolisWeb) oppure configurando il certificato "
                "P12/PEM in Impostazioni → Firma digitale per il sync automatico."
            ),
        }

    client = crea_client(demo=False)
    if isinstance(client, ClientPolisWebDemo):  # difesa in profondita': mai demo qui
        return {"ok": False, "message": "Client PST non configurato: sincronizzazione annullata."}

    fascicoli_pw = client.ricerca_fascicoli(
        ufficio,
        numero_rg=numero_rg,
        anno_rg=anno_rg,
        tipo_registro=str(getattr(fascicolo, "tipo_registro", "") or ""),
        registro_portale=str(getattr(fascicolo, "registro_portale", "") or ""),
        servizio_pst_preferito=str(getattr(fascicolo, "servizio_pst", "") or ""),
        ruolo_polisweb=str(getattr(fascicolo, "ruolo_polisweb", "") or "AVV"),
        max_risultati=5,
    )
    if not fascicoli_pw:
        return {
            "ok": False,
            "message": (
                f"Il registro non ha restituito il fascicolo RG {numero_rg}/{anno_rg} "
                "per l'ufficio indicato: verifica RG, registro e visibilita' del ruolo."
            ),
        }
    fascicolo_pw = fascicoli_pw[0]
    risultato = client.sincronizza_fascicolo_esistente(
        fascicolo_pw,
        fascicolo,
        gestione_fascicoli,
        get_clienti(),
        avvocato_referente=avvocato_referente,
        gestione_soggetti=get_soggetti() if get_soggetti else None,
    )
    aggiornato = gestione_fascicoli.get(fascicolo_id)
    proposte_create = _proponi_scadenze_da_eventi(
        client,
        aggiornato or fascicolo,
        ufficio=ufficio,
        numero_rg=numero_rg,
        anno_rg=anno_rg,
        get_scadenziario=get_scadenziario,
        attore=avvocato_referente,
    )
    messaggio = risultato.messaggio
    if proposte_create:
        messaggio += (
            f" Rilevate {proposte_create} nuove date dal registro: "
            "in attesa di conferma nello scadenziario."
        )
    return {
        "ok": bool(risultato.successo),
        "message": messaggio,
        "avvisi": list(risultato.avvisi or []),
        "depositi_importati": risultato.depositi_importati,
        "documenti_importati": risultato.documenti_importati,
        "proposte_scadenze": proposte_create,
        "last_sync_at": str(getattr(aggiornato, "last_sync_at", "") or ""),
        "sync_status": str(getattr(aggiornato, "sync_status", "") or ""),
    }
