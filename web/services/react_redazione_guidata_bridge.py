"""Bridge React per la Redazione Atti guidata.

Costruisce i payload del flusso reale: selezione cliente, fascicoli del
cliente, contesto del fascicolo con suggerimento del tipo atto, anteprima dei
campi compilati/mancanti con riferimenti normativi, preparazione della
generazione. Nessun dato finto: tutto proviene dai repository reali.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Callable, Optional

from pct.redazione_contesto import (
    anteprima_campi_modello,
    applica_marcatori_dati_mancanti,
    condizioni_dal_fascicolo,
    estrai_contesto_fascicolo,
)
from pct.redazione_normativa import (
    riferimenti_per_modello,
    testo_diritto_da_riferimenti,
)
from pct.redazione_suggerimenti import catalogo_per_scelta_manuale, suggerisci_modelli


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _testo(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    return str(value).strip()


def _etichetta_cliente(cliente: Any) -> str:
    return _testo(getattr(cliente, "nome_completo", "")) or _testo(getattr(cliente, "ragione_sociale", "")) or _testo(getattr(cliente, "nome", ""))


def build_redazione_clienti_payload(
    *,
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
) -> dict[str, Any]:
    """Clienti reali selezionabili nel passo 1 con il conteggio dei fascicoli attivi."""
    clienti = list(get_clienti().tutti() or [])
    conteggio_fascicoli: dict[str, int] = {}
    try:
        for fascicolo in get_fascicoli().tutti(archiviati=False) or []:
            id_cliente = _testo(getattr(fascicolo, "id_cliente", ""))
            if id_cliente:
                conteggio_fascicoli[id_cliente] = conteggio_fascicoli.get(id_cliente, 0) + 1
    except Exception:
        conteggio_fascicoli = {}
    voci = []
    for cliente in clienti:
        id_cliente = _testo(getattr(cliente, "id", ""))
        if not id_cliente:
            continue
        voci.append(
            {
                "id": id_cliente,
                "label": _etichetta_cliente(cliente) or id_cliente,
                "tipo": _testo(getattr(cliente, "tipo", "")),
                "codiceFiscale": _testo(getattr(cliente, "codice_fiscale", "")),
                "fascicoli": conteggio_fascicoli.get(id_cliente, 0),
            }
        )
    voci.sort(key=lambda voce: voce["label"].lower())
    return {"ok": True, "generatedAt": _iso_now(), "clienti": voci, "totale": len(voci)}


def build_redazione_fascicoli_payload(
    *,
    get_fascicoli: Callable[[], Any],
    cliente_id: str,
) -> dict[str, Any]:
    """Solo i fascicoli associati al cliente selezionato (passo 2)."""
    cliente_id = _testo(cliente_id)
    if not cliente_id:
        return {"ok": False, "errore": "Seleziona prima un cliente.", "fascicoli": []}
    fascicoli = list(get_fascicoli().tutti(id_cliente=cliente_id, archiviati=False) or [])
    voci = []
    for fascicolo in fascicoli:
        voci.append(
            {
                "id": _testo(getattr(fascicolo, "id", "")),
                "numero": _testo(getattr(fascicolo, "numero", "")),
                "titolo": _testo(getattr(fascicolo, "titolo", "")),
                "materia": _testo(getattr(fascicolo, "tipo", "")),
                "areaPratica": _testo(getattr(fascicolo, "area_pratica", "")),
                "oggetto": _testo(getattr(fascicolo, "oggetto", "")),
                "ufficio": _testo(getattr(fascicolo, "tribunale", "")),
                "rg": _testo(getattr(fascicolo, "rg_completo", "")) or _testo(getattr(fascicolo, "numero_rg", "")),
                "stato": _testo(getattr(fascicolo, "stato", "")),
                "valoreCausa": getattr(fascicolo, "valore_causa", 0) or 0,
                "prossimaUdienza": _testo(getattr(fascicolo, "data_prossima_udienza", "")) or _testo(getattr(fascicolo, "data_prima_udienza", "")),
                "controparte": _testo(getattr(fascicolo, "controparte", "")),
            }
        )
    voci.sort(key=lambda voce: voce["numero"], reverse=True)
    return {"ok": True, "generatedAt": _iso_now(), "clienteId": cliente_id, "fascicoli": voci, "totale": len(voci)}


def verifica_fascicolo_del_cliente(fascicolo: Any, cliente_id: str) -> bool:
    """Isolamento: il fascicolo deve appartenere al cliente dichiarato."""
    if not cliente_id:
        return True
    return _testo(getattr(fascicolo, "id_cliente", "")) == _testo(cliente_id)


def build_redazione_contesto_payload(
    *,
    fascicolo: Any,
    cliente: Any,
    parti: Any = None,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Passo 3: contesto reale del fascicolo + tipi atto suggeriti + catalogo completo."""
    contesto = estrai_contesto_fascicolo(fascicolo=fascicolo, cliente=cliente, parti=parti, config=config)
    suggerimenti = suggerisci_modelli(fascicolo)
    return {
        "ok": True,
        "generatedAt": _iso_now(),
        "contesto": contesto,
        "suggerimenti": suggerimenti,
        "catalogo": catalogo_per_scelta_manuale(),
    }


def build_redazione_anteprima_payload(
    *,
    model_code: str,
    fascicolo: Any,
    cliente: Any,
    parti: Any = None,
    utente: Any = None,
    config: Optional[dict[str, Any]] = None,
    studio_timbro: Any = None,
    normativa_db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Passo 4-5: campi compilati dai dati reali, campi mancanti, normativa suggerita."""
    from pct.compilatore_atti import get_modello, prefill_payload

    modello = get_modello(model_code)
    if not modello:
        return {"ok": False, "errore": "Modello atto non riconosciuto.", "campiTrovati": [], "campiMancanti": []}
    payload = prefill_payload(
        model_code,
        fascicolo=fascicolo,
        cliente=cliente,
        utente=utente,
        config=config or {},
        studio_timbro=studio_timbro,
        parti=parti,
    )
    resolution = payload.get("_prefill_resolution") if isinstance(payload.get("_prefill_resolution"), dict) else {}
    anteprima = anteprima_campi_modello(model_code, payload, prefill_resolution=resolution)
    condizioni = condizioni_dal_fascicolo(fascicolo)
    materia = _testo(getattr(fascicolo, "tipo", ""))
    normativa = riferimenti_per_modello(
        model_code,
        materia=materia,
        condizioni=condizioni,
        db_path=normativa_db_path,
    )
    valori_iniziali = {
        voce["name"]: voce["value"]
        for voce in anteprima["trovati"]
    }
    return {
        "ok": True,
        "generatedAt": _iso_now(),
        "model": {
            "code": _testo(modello.get("code")) or model_code,
            "name": _testo(modello.get("name")) or model_code,
            "area": _testo(modello.get("area")),
        },
        "campiTrovati": anteprima["trovati"],
        "campiMancanti": anteprima["mancanti"],
        "valori": valori_iniziali,
        "normativa": normativa,
        "testoDirittoSuggerito": testo_diritto_da_riferimenti(normativa),
        "condizioniAttive": sorted([chiave for chiave, attiva in condizioni.items() if attiva]),
    }


def prepara_payload_generazione(
    *,
    model_code: str,
    fascicolo: Any,
    cliente: Any,
    parti: Any = None,
    utente: Any = None,
    config: Optional[dict[str, Any]] = None,
    studio_timbro: Any = None,
    valori_utente: Optional[dict[str, Any]] = None,
    riferimenti_selezionati: Optional[list[dict[str, Any]]] = None,
    conferma_bozza: bool = False,
) -> dict[str, Any]:
    """Prefill reale + valori dell'avvocato + validazione + marcatori dati mancanti.

    Restituisce {"ok", "payload", "errors", "mancanti", "marcati"}.
    Con campi obbligatori vuoti e senza conferma esplicita non si genera nulla;
    con conferma, i campi vuoti diventano marcatori visibili [DATO MANCANTE: ...]
    e l'atto nasce come bozza da completare: nessun valore viene inventato.
    """
    from pct.compilatore_atti import merge_payload_with_form, prefill_payload, validate_payload

    payload = prefill_payload(
        model_code,
        fascicolo=fascicolo,
        cliente=cliente,
        utente=utente,
        config=config or {},
        studio_timbro=studio_timbro,
        parti=parti,
    )
    valori = {str(k): v for k, v in (valori_utente or {}).items() if str(k).strip()}
    if valori:
        payload = merge_payload_with_form(model_code, initial_payload=payload, form_data=valori)
    if riferimenti_selezionati:
        testo_diritto = testo_diritto_da_riferimenti(
            {
                "processuali": [r for r in riferimenti_selezionati if r.get("ambito") == "processuale"],
                "sostanziali": [r for r in riferimenti_selezionati if r.get("ambito") != "processuale"],
            }
        )
        if testo_diritto:
            campo_diritto = "legal_arguments" if "legal_arguments" in payload else ""
            if campo_diritto:
                esistente = _testo(payload.get(campo_diritto))
                payload[campo_diritto] = f"{esistente}\n\n{testo_diritto}".strip() if esistente else testo_diritto
    payload["id_cliente"] = _testo(getattr(cliente, "id", "")) if cliente is not None else _testo(payload.get("id_cliente"))
    etichetta_cliente = _etichetta_cliente(cliente) if cliente is not None else _testo(getattr(fascicolo, "nome_cliente", ""))
    payload["_editor_filename_hint"] = " ".join(
        parte for parte in (
            etichetta_cliente,
            _testo(getattr(fascicolo, "numero", "")),
            _testo(payload.get("title")) or model_code,
        ) if parte
    )
    errors = validate_payload(model_code, payload)
    resolution = payload.get("_prefill_resolution") if isinstance(payload.get("_prefill_resolution"), dict) else {}
    anteprima = anteprima_campi_modello(model_code, payload, prefill_resolution=resolution)
    if errors and not conferma_bozza:
        return {
            "ok": False,
            "payload": payload,
            "errors": errors,
            "mancanti": anteprima["mancanti"],
            "marcati": [],
        }
    marcati: list[str] = []
    if errors and conferma_bozza:
        payload, marcati = applica_marcatori_dati_mancanti(model_code, payload)
    return {
        "ok": True,
        "payload": payload,
        "errors": {},
        "mancanti": anteprima["mancanti"],
        "marcati": marcati,
    }


def evidenzia_dati_mancanti_html(html: str) -> str:
    """Evidenzia i marcatori [DATO MANCANTE: ...] nell'HTML dell'editor."""
    testo = str(html or "")
    marker = "[DATO MANCANTE:"
    parti: list[str] = []
    posizione = 0
    while True:
        inizio = testo.find(marker, posizione)
        if inizio < 0:
            parti.append(testo[posizione:])
            break
        fine = testo.find("]", inizio + len(marker))
        if fine < 0:
            parti.append(testo[posizione:])
            break
        parti.append(testo[posizione:inizio])
        etichetta = testo[inizio + len(marker):fine].strip()
        if not etichetta:
            parti.append(testo[inizio:fine + 1])
        else:
            etichetta_sicura = escape(etichetta[:160], quote=False)
            parti.append(
                '<mark class="iu-dato-mancante" data-campo-mancante="1">'
                f"DATO MANCANTE: {etichetta_sicura}"
                "</mark>"
            )
        posizione = fine + 1
    return "".join(parti)
