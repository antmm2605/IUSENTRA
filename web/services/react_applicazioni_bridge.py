"""Dati React delle funzioni del catalogo applicazioni (ex cabina `/applicazioni`).

La pagina React `ApplicazionePage` apre una voce del catalogo
(`pct/applicazioni_catalogo.py`) e, secondo il tipo, mostra il modulo di calcolo
in pagina, rimanda allo strumento forense con il preset della voce o apre la
pagina collegata. Il calcolo non è duplicato: le utility passano da
`_utility_form`/`_utility_result` di `web/services/applicazioni_runtime.py`
(le stesse della vista storica, funzioni pure su un `Mapping`), i preset da
`TOOL_PRESET_OVERRIDES` e il precompilato del fascicolo da
`GestioneStrumentiLegali.build_prefill`/`build_form_state`.

Principio delle fonti certe: una voce che nella vista storica non aveva un
calcolo reale (rispondeva «Presidio operativo attivo» su qualunque input) non
viene simulata: la pagina la dichiara non disponibile e indica dove lavorare.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pct.applicazioni_runtime import TOOL_PRESET_OVERRIDES, resolve_runtime

# Utility con calcolo reale nella vista storica, rese nella pagina React.
# `fonte` riporta solo la base dichiarata dal calcolo storico: le utility
# puramente aritmetiche (frazioni, conversioni, durate) non ne hanno.
CALCOLI_IN_PAGINA: dict[str, dict[str, str]] = {
    "calcolo_giorni_lavorativi": {
        "azione": "Calcola",
        "fonte": "Festività nazionali: L. 27 maggio 1949, n. 260 e successive modificazioni.",
    },
    "calcolo_eta_anagrafica": {"azione": "Calcola", "fonte": ""},
    "calcolo_ora_inizio_fine_attivita": {"azione": "Calcola", "fonte": ""},
    "variazione_media_fatturato": {"azione": "Calcola", "fonte": ""},
    "calcolatore_per_frazioni": {"azione": "Calcola", "fonte": ""},
    "conversione_unita_di_misura": {"azione": "Converti", "fonte": ""},
    "conversione_minuti_in_centesimi": {"azione": "Converti", "fonte": ""},
    "verifica_partita_iva": {
        "azione": "Verifica",
        "fonte": "Art. 35 D.P.R. 633/1972 (numero di partita IVA): verifica formale del carattere di controllo.",
    },
    "verifica_iban": {
        "azione": "Verifica",
        "fonte": "ISO 13616 (struttura IBAN) con cifre di controllo ISO 7064 MOD 97-10: verifica formale.",
    },
}

# Ricerca su banca dati ufficiale già presente nel dominio (`pct/territorio_italia.py`).
RICERCA_COMUNI = "ricerca_comuni"
FONTE_COMUNI = "Elenco ufficiale dei Comuni ISTAT; CAP dalla banca dati Garda Informatica (licenza MIT)."

# Voci senza calcolo nella vista storica: nessun risultato inventato.
NON_DISPONIBILI: dict[str, dict[str, str]] = {
    "decurtazione_punti_patente": {
        "motivo": "Il gestionale non contiene la tabella dei punti dell'art. 126-bis del Codice della strada.",
        "label": "Termini dei verbali CdS",
        "href": "/strumenti-legali/?tool=termini_processuali#funzione-operativa",
    },
    "calcolo_tasso_alcolemico": {
        "motivo": "Il gestionale non contiene un metodo di stima del tasso alcolemico con base normativa certa.",
        "label": "Catalogo delle funzioni",
        "href": "/strumenti-operativi",
    },
    "ricerca_codici_ateco": {
        "motivo": "La classificazione ATECO ISTAT non è ancora caricata nel gestionale.",
        "label": "Catalogo delle funzioni",
        "href": "/strumenti-operativi",
    },
    "cronometro_online": {
        "motivo": "Per misurare e registrare il tempo di lavoro usa il timesheet dello studio.",
        "label": "Apri il timesheet",
        "href": "/timesheet",
    },
}

# Voci del catalogo che aprono Strumenti forensi senza indicare lo strumento:
# qui lo strumento corretto, con l'eventuale opzione iniziale (valore già
# previsto dal catalogo del dominio, nessun calcolo).
VOCI_SENZA_STRUMENTO: dict[str, tuple[str, dict[str, str]]] = {
    "termini_processuali_civili": ("termini_processuali", {}),
    "termini_deposito_atti_appello": ("impugnazioni", {}),
    "calcolo_notula_penale": ("onorari_forensi", {"onorari_materia": "PENALE"}),
    "calcolo_spese_di_mediazione": ("indennita_mediazione", {}),
    "tariffe_mediazione": ("indennita_mediazione", {}),
    "calcolo_compenso_a_ore": ("compenso_a_tempo", {}),
    "calcolo_ravvedimento_operoso": ("ravvedimento_operoso", {}),
}

APPLICAZIONI_IN_PAGINA = frozenset({*CALCOLI_IN_PAGINA, RICERCA_COMUNI, *NON_DISPONIBILI})


def _testo(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).strip()


def _campi_strumento(tool_id: str) -> set[str]:
    from pct.calcolatori.schema import schema_calcolatore

    schema = schema_calcolatore(tool_id) or {}
    return {str(campo.get("name") or "") for campo in schema.get("campi", [])}


def strumento_voce(entry: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    """Strumento forense React della voce e preset da applicare (solo campi dello strumento)."""

    entry_id = _testo(entry.get("id"))
    tool_id = ""
    preset: dict[str, str] = {}
    if entry_id in VOCI_SENZA_STRUMENTO:
        tool_id, extra = VOCI_SENZA_STRUMENTO[entry_id]
        preset.update(extra)
    elif _testo(entry.get("endpoint")) == "strumenti_legali.index":
        tool_id = _testo(dict(entry.get("params") or {}).get("tool"))
    if not tool_id:
        return "", {}
    campi = _campi_strumento(tool_id)
    if not campi:
        return "", {}
    preset.update({k: str(v) for k, v in TOOL_PRESET_OVERRIDES.get(entry_id, {}).items()})
    return tool_id, {k: v for k, v in preset.items() if k in campi}


def href_strumento(tool_id: str, entry_id: str, id_fascicolo: str = "") -> str:
    from urllib.parse import urlencode

    query = {"tool": tool_id, "app": entry_id}
    if id_fascicolo:
        query["id_fascicolo"] = id_fascicolo
    return f"/strumenti-legali/?{urlencode(query)}#funzione-operativa"


def href_react_voce(entry: Mapping[str, Any]) -> str:
    """Percorso React delle voci che la vista storica serviva solo nella cabina.

    Stringa vuota per le voci che seguono le regole di `_catalog_entry_href`.
    """

    entry_id = _testo(entry.get("id"))
    if entry_id in APPLICAZIONI_IN_PAGINA:
        return f"/applicazioni/{entry_id}"
    if entry_id in VOCI_SENZA_STRUMENTO:
        return href_strumento(VOCI_SENZA_STRUMENTO[entry_id][0], entry_id)
    return ""


def tipo_voce(entry: Mapping[str, Any]) -> str:
    entry_id = _testo(entry.get("id"))
    if entry_id in CALCOLI_IN_PAGINA:
        return "lookup" if resolve_runtime(entry).get("kind") == "lookup" else "utility"
    if entry_id == RICERCA_COMUNI:
        return "lookup"
    if entry_id in NON_DISPONIBILI:
        return "non_disponibile"
    if strumento_voce(entry)[0]:
        return "tool"
    return "collegamento"


def campi_modulo(entry_id: str) -> list[dict[str, Any]]:
    """Schema del modulo: `_utility_form` storico normalizzato per React."""

    if entry_id == RICERCA_COMUNI:
        return [{
            "name": "q", "label": "Comune, CAP, codice ISTAT o catastale", "kind": "text",
            "options": [], "required": True, "value": "", "step": "",
        }]
    if entry_id not in CALCOLI_IN_PAGINA:
        return []
    from web.services.applicazioni_runtime import _utility_form

    facoltativi = {"utility_data_fine", "utility_pausa"}
    return [
        {
            "name": str(campo["name"]),
            "label": str(campo.get("label") or campo["name"]),
            "kind": str(campo.get("type") or "text"),
            "options": [
                {"value": str(o.get("value", "")), "label": str(o.get("label", ""))}
                for o in campo.get("options") or []
            ],
            "required": campo["name"] not in facoltativi,
            "value": str(campo.get("options", [{}])[0].get("value", "")) if campo.get("options") else "",
            "step": str(campo.get("step") or ""),
        }
        for campo in _utility_form(entry_id)
    ]


def _esito(righe: list[dict[str, str]], note: list[str], *, messaggio_ok: str) -> dict[str, Any]:
    ok = bool(righe)
    messaggio = messaggio_ok if ok else (note[0] if note else "Verifica i dati inseriti e riprova.")
    return {"ok": ok, "message": messaggio, "rows": righe, "notes": note}


def _ricerca_comuni(query: str) -> dict[str, Any]:
    from pct.territorio_italia import search_comuni

    if len(query) < 2:
        return _esito([], ["Inserisci almeno due caratteri del Comune, del CAP o del codice."], messaggio_ok="")
    comuni = search_comuni(query, limit=20)
    righe = [
        {
            "label": comune.label,
            "value": f"ISTAT {comune.codice_istat} · catastale {comune.codice_belfiore}",
            "note": " · ".join(p for p in (f"CAP {', '.join(comune.cap)}" if comune.cap else "", comune.provincia, comune.regione) if p),
        }
        for comune in comuni
    ]
    if not righe:
        return {"ok": True, "message": "Nessun Comune trovato.", "rows": [], "notes": [FONTE_COMUNI]}
    return {"ok": True, "message": f"{len(righe)} Comuni trovati.", "rows": righe, "notes": [FONTE_COMUNI]}


def esegui(entry: Mapping[str, Any], valori: Mapping[str, Any]) -> dict[str, Any]:
    """Esegue la utility o la ricerca con i soli campi dichiarati dal modulo."""

    entry_id = _testo(entry.get("id"))
    ammessi = {campo["name"] for campo in campi_modulo(entry_id)}
    form = {nome: _testo(valore) for nome, valore in dict(valori or {}).items() if nome in ammessi}
    if entry_id == RICERCA_COMUNI:
        return _ricerca_comuni(form.get("q", ""))
    if entry_id not in CALCOLI_IN_PAGINA:
        return {"ok": False, "message": "Questa funzione non esegue calcoli in pagina.", "rows": [], "notes": []}
    from web.services.applicazioni_runtime import _utility_result

    risultato = _utility_result(entry, form)
    righe = [
        {"label": str(m.get("label", "")), "value": str(m.get("value", "")), "note": str(m.get("subtext", ""))}
        for m in risultato.get("metrics") or []
    ]
    return _esito(righe, [str(n) for n in risultato.get("notes") or []], messaggio_ok="Calcolo completato.")


def scheda(
    entry: Mapping[str, Any],
    *,
    href_catalogo: str,
    id_fascicolo: str = "",
) -> dict[str, Any]:
    """Voce del catalogo con tipo, modulo o destinazione per la pagina React."""

    entry_id = _testo(entry.get("id"))
    tipo = tipo_voce(entry)
    item: dict[str, Any] = {
        "id": entry_id,
        "title": _testo(entry.get("title")),
        "description": _testo(entry.get("summary")),
        "section": _testo(entry.get("section_title")),
        "sectionId": _testo(entry.get("section_id")),
        "status": _testo(entry.get("status_label")),
        "type": tipo,
        "runtimeKind": _testo(resolve_runtime(entry).get("kind")),
        "basis": "",
        "href": href_catalogo,
        "form": None,
        "toolId": "",
        "preset": {},
        "unavailable": None,
    }
    if tipo in {"utility", "lookup"}:
        meta = CALCOLI_IN_PAGINA.get(entry_id, {"azione": "Cerca", "fonte": FONTE_COMUNI})
        item["basis"] = meta["fonte"]
        item["href"] = f"/applicazioni/{entry_id}"
        item["form"] = {
            "action": f"/api/v1/ui/applicazioni/{entry_id}/esegui",
            "submitLabel": meta["azione"],
            "fields": campi_modulo(entry_id),
        }
    elif tipo == "tool":
        tool_id, preset = strumento_voce(entry)
        item.update({"toolId": tool_id, "preset": preset, "href": href_strumento(tool_id, entry_id, id_fascicolo)})
    elif tipo == "non_disponibile":
        dati = NON_DISPONIBILI[entry_id]
        item["href"] = dati["href"]
        item["unavailable"] = {"reason": dati["motivo"], "label": dati["label"], "href": dati["href"]}
    return item


def _voce_fascicolo(fascicolo: Any) -> dict[str, str]:
    numero = _testo(getattr(fascicolo, "numero", ""))
    titolo = _testo(getattr(fascicolo, "titolo", ""))
    return {"id": _testo(getattr(fascicolo, "id", "")), "label": " · ".join(p for p in (numero, titolo) if p)}


def contesto_fascicolo(
    id_fascicolo: str,
    *,
    gestore_strumenti: Any,
    get_fascicoli: Any,
    get_clienti: Any,
    studio: Mapping[str, Any],
    utente: Any,
) -> tuple[dict[str, str] | None, dict[str, str], list[str]]:
    """Campi degli strumenti ricavati dalla pratica (solo quelli che la pratica cambia)."""

    fascicolo = get_fascicoli().get(id_fascicolo) if id_fascicolo else None
    if fascicolo is None:
        return None, {}, ["Pratica non trovata: i campi non sono stati precompilati."]
    id_cliente = _testo(getattr(fascicolo, "id_cliente", ""))
    cliente = get_clienti().get(id_cliente) if id_cliente else None
    con_pratica = gestore_strumenti.build_form_state(
        gestore_strumenti.build_prefill(fascicolo=fascicolo, cliente=cliente, studio=dict(studio), utente=utente),
        None,
    )
    senza_pratica = gestore_strumenti.build_form_state(
        gestore_strumenti.build_prefill(fascicolo=None, cliente=None, studio=dict(studio), utente=utente),
        None,
    )
    prefill = {k: str(v) for k, v in con_pratica.items() if isinstance(v, str | int | float) and v != senza_pratica.get(k)}
    return _voce_fascicolo(fascicolo), prefill, []
