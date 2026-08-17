from __future__ import annotations


from pct.formatting import format_euro_it
from collections import Counter
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional

from flask import current_app, g, request, url_for

from pct.applicazioni_runtime import build_tool_result, resolve_runtime
from pct.checklist_atti import TUTTI_I_TEMPLATE as CHECKLIST_TEMPLATES
from pct.template_atti import GestioneTemplateAtti
from pct.uffici_giudiziari import get_gestore as get_gestore_uffici
from web.helpers import (
    get_agenda,
    get_clienti,
    get_fascicoli,
    get_fatturazione,
    get_giurisprudenza,
    get_legal_intelligence,
    get_normative_tables,
    get_preventivi,
    get_scadenziario,
)


def _cfg_path(key: str, default: str = "") -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if key in paths:
        return str(paths[key] or default)
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    return str(current_app.config.get(key, default) or default)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _fmt_money(value: Any) -> str:
    return format_euro_it(value)


def _fmt_date_it(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    raw = _clean_text(value)
    if not raw:
        return ""
    for parser in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:19], parser).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return raw


def _metric(label: str, value: str, subtext: str = "") -> Dict[str, str]:
    return {"label": label, "value": value, "subtext": subtext}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _studio_context() -> dict:
    return {
        "nome": current_app.config.get("STUDIO_NOME", "IUSENTRA"),
        "avvocato": current_app.config.get("STUDIO_AVVOCATO", ""),
        "cf": current_app.config.get("STUDIO_CF", ""),
        "piva": current_app.config.get("STUDIO_PIVA", ""),
        "indirizzo": current_app.config.get("STUDIO_INDIRIZZO", ""),
        "pec": current_app.config.get("SMTP_FROM", ""),
        "fax": current_app.config.get("STUDIO_FAX", ""),
        "luogo": current_app.config.get("STUDIO_LUOGO", ""),
    }


def _resolve_case_context() -> tuple[list, dict, Any, Any]:
    fascicoli = sorted(
        get_fascicoli().tutti(archiviati=True),
        key=lambda f: ((f.data_apertura or ""), f.numero),
        reverse=True,
    )
    clienti_map = {c.id: c for c in get_clienti().tutti()}
    id_fascicolo = request.values.get("id_fascicolo", "").strip()
    fascicolo_sel = get_fascicoli().get(id_fascicolo) if id_fascicolo else None
    cliente_sel = clienti_map.get(fascicolo_sel.id_cliente) if fascicolo_sel and fascicolo_sel.id_cliente else None
    return fascicoli, clienti_map, fascicolo_sel, cliente_sel


def _template_manager() -> GestioneTemplateAtti:
    return GestioneTemplateAtti(
        db_path=_cfg_path("TEMPLATE_ATTI_DB", "./template_atti/templates.json")
    )


def _carica_portali():
    from pct.portale import GestionePortale

    try:
        gestore = GestionePortale(
            db_path=_cfg_path("PORTALE_DB", "./portale/portali.json"),
            uploads_dir=_cfg_path("PORTALE_UPLOADS", "./portale/uploads"),
        )
        return gestore.tutti(includi_inattivi=False)
    except Exception:
        return []


def _legal_snapshot() -> dict:
    return get_legal_intelligence().build_dashboard_snapshot(
        fascicoli=get_fascicoli().tutti(archiviati=True),
        clienti=get_clienti().tutti(),
        appuntamenti=get_agenda().tutti(),
        scadenze=get_scadenziario().tutte(),
        portali=_carica_portali(),
    )


def _matching_templates(entry: Mapping[str, Any], limit: int = 6) -> list[dict]:
    manager = _template_manager()
    query_terms = {term for term in _clean_text(entry.get("title")).lower().replace("/", " ").split() if len(term) > 2}
    matches = []
    for template in manager.tutti():
        haystack = " ".join(
            [
                template.titolo,
                template.categoria,
                template.area,
                template.branca,
                template.sottobranca,
                template.microtema,
                " ".join(template.parole_chiave or []),
            ]
        ).lower()
        score = sum(3 for term in query_terms if term in template.titolo.lower())
        score += sum(1 for term in query_terms if term in haystack)
        if score <= 0:
            continue
        matches.append(
            {
                "id": template.id,
                "titolo": template.titolo,
                "categoria": template.categoria,
                "area": template.area,
                "branca": template.branca,
                "sottobranca": template.sottobranca,
                "canale_telematico": template.canale_telematico,
                "score": score,
                "scheda_url": url_for("template_atti.scheda", id_template=template.id),
                "usa_url": url_for("template_atti.usa", id_template=template.id),
            }
        )
    matches.sort(key=lambda row: (-row["score"], row["titolo"]))
    return matches[:limit]


def _matching_checklists(entry: Mapping[str, Any], limit: int = 4) -> list[dict]:
    query_terms = {term for term in _clean_text(entry.get("title")).lower().replace("/", " ").split() if len(term) > 2}
    rows = []
    for template in CHECKLIST_TEMPLATES:
        haystack = " ".join(
            [
                template.nome,
                template.categoria,
                template.area,
                template.branca,
                template.sottobranca,
                template.descrizione,
            ]
        ).lower()
        score = sum(3 for term in query_terms if term in template.nome.lower())
        score += sum(1 for term in query_terms if term in haystack)
        if score <= 0:
            continue
        rows.append(
            {
                "id": template.id,
                "nome": template.nome,
                "area": template.area,
                "branca": template.branca,
                "sottobranca": template.sottobranca,
                "canale": template.canale,
                "url": url_for("checklist_dettaglio", id_template=template.id),
                "score": score,
            }
        )
    rows.sort(key=lambda row: (-row["score"], row["nome"]))
    return rows[:limit]


def _lookup_uffici(query: str, limit: int = 8) -> list[dict]:
    cache_path = current_app.config.get("UFFICI_GIUDIZIARI_DB") or current_app.config.get("REGINDE_DB") or ""
    if not query:
        return []
    gestore = get_gestore_uffici(cache_path=cache_path) if cache_path else get_gestore_uffici()
    return gestore.cerca(query, limit=limit)


def _utility_form(entry_id: str) -> list[dict]:
    if entry_id in {"calcolo_percentuale", "percentuali_e_quote", "calcolo_proporzione"}:
        return [
            {"name": "utility_base", "label": "Base", "type": "number", "step": "0.01"},
            {"name": "utility_percentuale", "label": "Percentuale", "type": "number", "step": "0.01"},
        ]
    if entry_id == "scorporo_iva":
        return [
            {"name": "utility_lordo", "label": "Importo lordo", "type": "number", "step": "0.01"},
            {
                "name": "utility_iva",
                "label": "IVA %",
                "type": "select",
                "options": [
                    {"value": "22", "label": "22%"},
                    {"value": "10", "label": "10%"},
                    {"value": "4", "label": "4%"},
                ],
            },
        ]
    if entry_id in {"conta_giorni_tra_date_e_ricorrenze", "calcolo_giorni_lavorativi", "calcolo_tempo_trascorso", "calcolo_eta_anagrafica"}:
        return [
            {"name": "utility_data_inizio", "label": "Data iniziale", "type": "date"},
            {"name": "utility_data_fine", "label": "Data finale", "type": "date"},
        ]
    if entry_id == "conversione_minuti_in_centesimi":
        return [{"name": "utility_minuti", "label": "Minuti", "type": "number", "step": "1"}]
    if entry_id in {"verifica_partita_iva", "verifica_iban", "calcolo_codice_fiscale", "decodifica_codice_fiscale"}:
        return [{"name": "utility_codice", "label": "Valore da verificare", "type": "text"}]
    if entry_id == "variazione_media_fatturato":
        return [
            {
                "name": "utility_valori",
                "label": "Importi per periodo (separati da ;)",
                "type": "text",
            }
        ]
    if entry_id == "calcolo_ora_inizio_fine_attivita":
        return [
            {"name": "utility_ora_inizio", "label": "Ora di inizio (HH:MM)", "type": "text"},
            {"name": "utility_ora_fine", "label": "Ora di fine (HH:MM)", "type": "text"},
            {"name": "utility_pausa", "label": "Pausa (minuti)", "type": "number", "step": "1"},
        ]
    if entry_id == "calcolatore_per_frazioni":
        return [
            {"name": "utility_frazione_a", "label": "Prima frazione (es. 3/4)", "type": "text"},
            {
                "name": "utility_operazione",
                "label": "Operazione",
                "type": "select",
                "options": [
                    {"value": "+", "label": "Somma"},
                    {"value": "-", "label": "Differenza"},
                    {"value": "*", "label": "Prodotto"},
                    {"value": "/", "label": "Divisione"},
                ],
            },
            {"name": "utility_frazione_b", "label": "Seconda frazione (es. 1/6)", "type": "text"},
        ]
    if entry_id == "conversione_unita_di_misura":
        return [
            {"name": "utility_valore", "label": "Valore", "type": "number", "step": "0.0001"},
            {
                "name": "utility_conversione",
                "label": "Conversione",
                "type": "select",
                "options": [{"value": chiave, "label": voce["label"]} for chiave, voce in _CONVERSIONI.items()],
            },
        ]
    return [{"name": "utility_query", "label": "Richiesta operativa", "type": "text"}]


# Fattori di conversione esatti per definizione delle unita' (SI e catastali).
_CONVERSIONI: Dict[str, Dict[str, Any]] = {
    "mq_ettari": {"label": "Metri quadrati → ettari", "fattore": 0.0001, "unita": "ha"},
    "ettari_mq": {"label": "Ettari → metri quadrati", "fattore": 10_000.0, "unita": "m²"},
    "mq_are": {"label": "Metri quadrati → are", "fattore": 0.01, "unita": "a"},
    "are_mq": {"label": "Are → metri quadrati", "fattore": 100.0, "unita": "m²"},
    "km_miglia": {"label": "Chilometri → miglia terrestri", "fattore": 1 / 1.609344, "unita": "mi"},
    "miglia_km": {"label": "Miglia terrestri → chilometri", "fattore": 1.609344, "unita": "km"},
    "kg_libbre": {"label": "Chilogrammi → libbre", "fattore": 1 / 0.45359237, "unita": "lb"},
    "libbre_kg": {"label": "Libbre → chilogrammi", "fattore": 0.45359237, "unita": "kg"},
    "litri_galloni": {"label": "Litri → galloni US", "fattore": 1 / 3.785411784, "unita": "gal"},
    "galloni_litri": {"label": "Galloni US → litri", "fattore": 3.785411784, "unita": "l"},
}


def _pasqua(anno: int) -> date:
    """Domenica di Pasqua col metodo di Gauss (calendario gregoriano)."""

    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = ((h + l - 7 * m + 114) % 31) + 1
    return date(anno, mese, giorno)


def _festivita_nazionali(anno: int) -> set[date]:
    """Festività nazionali italiane (L. 260/1949 e successive)."""

    pasqua = _pasqua(anno)
    return {
        date(anno, 1, 1), date(anno, 1, 6), pasqua,
        date.fromordinal(pasqua.toordinal() + 1),  # lunedì dell'Angelo
        date(anno, 4, 25), date(anno, 5, 1), date(anno, 6, 2),
        date(anno, 8, 15), date(anno, 11, 1), date(anno, 12, 8),
        date(anno, 12, 25), date(anno, 12, 26),
    }


def _parse_date(raw: Any) -> Optional[date]:
    text = _clean_text(raw)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _validate_partita_iva(value: str) -> bool:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 11:
        return False
    total = 0
    for index, char in enumerate(digits[:10]):
        num = int(char)
        if index % 2 == 0:
            total += num
        else:
            doubled = num * 2
            total += doubled if doubled < 10 else doubled - 9
    check = (10 - (total % 10)) % 10
    return check == int(digits[-1])


def _validate_iban(value: str) -> bool:
    iban = "".join(ch for ch in value.upper() if ch.isalnum())
    if len(iban) < 15:
        return False
    rearranged = iban[4:] + iban[:4]
    converted = ""
    for char in rearranged:
        converted += str(ord(char) - 55) if char.isalpha() else char
    return int(converted) % 97 == 1


def _utility_result(entry: Mapping[str, Any], form: Mapping[str, Any]) -> Dict[str, Any]:
    entry_id = _clean_text(entry.get("id"))
    metrics: List[Dict[str, str]] = []
    notes: List[str] = []
    if entry_id in {"calcolo_percentuale", "percentuali_e_quote", "calcolo_proporzione"}:
        base = _safe_float(form.get("utility_base"))
        percentuale = _safe_float(form.get("utility_percentuale"))
        quota = base * percentuale / 100
        metrics = [
            _metric("Base", f"{_fmt_money(base)}"),
            _metric("Percentuale", f"{percentuale:.2f}%".replace(".", ",")),
            _metric("Quota", f"{_fmt_money(quota)}"),
        ]
    elif entry_id == "scorporo_iva":
        lordo = _safe_float(form.get("utility_lordo"))
        iva = _safe_float(form.get("utility_iva"), 22.0)
        imponibile = lordo / (1 + iva / 100) if iva >= 0 else lordo
        imposta = lordo - imponibile
        metrics = [
            _metric("Lordo", f"{_fmt_money(lordo)}"),
            _metric("Imponibile", f"{_fmt_money(imponibile)}"),
            _metric("IVA", f"{_fmt_money(imposta)}"),
        ]
    elif entry_id in {"conta_giorni_tra_date_e_ricorrenze", "calcolo_giorni_lavorativi", "calcolo_tempo_trascorso", "calcolo_eta_anagrafica"}:
        data_inizio = _parse_date(form.get("utility_data_inizio"))
        data_fine = _parse_date(form.get("utility_data_fine")) or date.today()
        if data_inizio and data_fine:
            delta = (data_fine - data_inizio).days
            metrics = [
                _metric("Data iniziale", _fmt_date_it(data_inizio)),
                _metric("Data finale", _fmt_date_it(data_fine)),
                _metric("Giorni", str(delta)),
            ]
            if entry_id == "calcolo_giorni_lavorativi":
                festivi = set()
                for anno in range(data_inizio.year, data_fine.year + 1):
                    festivi |= _festivita_nazionali(anno)
                lavorativi = 0
                solo_feriali = 0
                for offset in range(delta + 1):
                    giorno = date.fromordinal(data_inizio.toordinal() + offset)
                    if giorno.weekday() < 5:
                        solo_feriali += 1
                        if giorno not in festivi:
                            lavorativi += 1
                metrics.append(_metric("Giorni lavorativi", str(lavorativi), "escluse le festività nazionali"))
                metrics.append(_metric("Solo lun-ven", str(solo_feriali)))
                notes.append(
                    "Escluse le festività nazionali (incl. Pasqua e lunedì dell'Angelo); "
                    "eventuali patroni locali non sono considerati."
                )
            if entry_id == "calcolo_eta_anagrafica":
                anni = data_fine.year - data_inizio.year
                mesi = data_fine.month - data_inizio.month
                if (data_fine.month, data_fine.day) < (data_inizio.month, data_inizio.day):
                    anni -= 1
                if data_fine.day < data_inizio.day:
                    mesi -= 1
                mesi = mesi % 12
                metrics.append(_metric("Età", f"{anni} anni e {mesi} mesi"))
        else:
            notes.append("Inserisci entrambe le date in formato valido.")
    elif entry_id == "conversione_minuti_in_centesimi":
        minuti = _safe_float(form.get("utility_minuti"))
        metrics = [
            _metric("Minuti", str(int(minuti))),
            _metric("Ore centesimali", f"{minuti / 60:.2f}".replace(".", ",")),
        ]
    elif entry_id == "verifica_partita_iva":
        codice = _clean_text(form.get("utility_codice"))
        metrics = [
            _metric("Valore", codice or "n/d"),
            _metric("Esito", "Formalmente valida" if _validate_partita_iva(codice) else "Non valida"),
        ]
    elif entry_id == "verifica_iban":
        codice = _clean_text(form.get("utility_codice"))
        metrics = [
            _metric("Valore", codice or "n/d"),
            _metric("Esito", "Formalmente valido" if _validate_iban(codice) else "Non valido"),
        ]
    elif entry_id == "variazione_media_fatturato":
        grezzi = [v.strip() for v in _clean_text(form.get("utility_valori")).split(";") if v.strip()]
        valori = [_safe_float(v) for v in grezzi]
        if len(valori) < 2 or any(v <= 0 for v in valori):
            notes.append("Inserisci almeno due importi positivi separati da punto e virgola (es. 50000; 62000; 58000).")
        else:
            variazioni = [(valori[i] / valori[i - 1] - 1) * 100 for i in range(1, len(valori))]
            media = sum(variazioni) / len(variazioni)
            metrics = [
                _metric("Periodi", str(len(valori))),
                _metric("Variazione media", f"{media:+.2f}%".replace(".", ",")),
                _metric("Complessiva", f"{(valori[-1] / valori[0] - 1) * 100:+.2f}%".replace(".", ",")),
            ]
            notes.append(
                "Media aritmetica delle variazioni percentuali tra periodi consecutivi; "
                "la variazione complessiva confronta primo e ultimo periodo."
            )
    elif entry_id == "calcolo_ora_inizio_fine_attivita":
        def _parse_ora(raw: Any) -> Optional[int]:
            testo = _clean_text(raw).replace(".", ":")
            parti = testo.split(":")
            try:
                ore, minuti = int(parti[0]), int(parti[1]) if len(parti) > 1 else 0
            except (ValueError, IndexError):
                return None
            if 0 <= ore < 24 and 0 <= minuti < 60:
                return ore * 60 + minuti
            return None

        inizio = _parse_ora(form.get("utility_ora_inizio"))
        fine = _parse_ora(form.get("utility_ora_fine"))
        pausa = max(int(_safe_float(form.get("utility_pausa"))), 0)
        if inizio is None or fine is None:
            notes.append("Inserisci le ore nel formato HH:MM (es. 09:30).")
        else:
            durata = fine - inizio if fine >= inizio else fine + 24 * 60 - inizio
            netta = max(durata - pausa, 0)
            metrics = [
                _metric("Durata lorda", f"{durata // 60}h {durata % 60:02d}m"),
                _metric("Pausa", f"{pausa} min"),
                _metric("Durata netta", f"{netta // 60}h {netta % 60:02d}m"),
                _metric("Ore centesimali", f"{netta / 60:.2f}".replace(".", ",")),
            ]
            if fine < inizio:
                notes.append("Ora di fine precedente all'inizio: calcolo a cavallo di mezzanotte.")
    elif entry_id == "calcolatore_per_frazioni":
        from fractions import Fraction

        def _parse_frazione(raw: Any) -> Optional[Fraction]:
            testo = _clean_text(raw).replace(",", ".").replace(" ", "")
            try:
                return Fraction(testo)
            except (ValueError, ZeroDivisionError):
                return None

        fa = _parse_frazione(form.get("utility_frazione_a"))
        fb = _parse_frazione(form.get("utility_frazione_b"))
        op = _clean_text(form.get("utility_operazione")) or "+"
        if fa is None or fb is None:
            notes.append("Inserisci frazioni nel formato numeratore/denominatore (es. 3/4) o numeri decimali.")
        elif op == "/" and fb == 0:
            notes.append("Divisione per zero non ammessa.")
        else:
            esito = {"+": fa + fb, "-": fa - fb, "*": fa * fb, "/": fa / fb if fb else Fraction(0)}[op]
            metrics = [
                _metric("Operazione", f"{fa} {op} {fb}"),
                _metric("Risultato", str(esito)),
                _metric("Decimale", f"{float(esito):.6g}".replace(".", ",")),
            ]
    elif entry_id == "conversione_unita_di_misura":
        valore = _safe_float(form.get("utility_valore"))
        chiave = _clean_text(form.get("utility_conversione")) or "mq_ettari"
        voce_conv = _CONVERSIONI.get(chiave)
        if voce_conv is None:
            notes.append("Conversione non riconosciuta.")
        else:
            metrics = [
                _metric("Valore", f"{valore:g}".replace(".", ",")),
                _metric("Conversione", str(voce_conv["label"])),
                _metric("Risultato", f"{valore * voce_conv['fattore']:.6g} {voce_conv['unita']}".replace(".", ",")),
            ]
            notes.append("Fattori di conversione esatti per definizione delle unità.")
    else:
        query = _clean_text(form.get("utility_query"))
        metrics = [
            _metric("Richiesta", query or entry.get("title", "")),
            _metric("Stato", "Presidio operativo attivo"),
        ]
        notes.append("L'area operativa ha preso in carico la voce e la collega ai moduli reali del dominio corretto.")
    return {"metrics": metrics, "notes": notes, "tables": [], "preview_text": ""}


def _build_dynamic_options(schema: Mapping[str, Any], gestore) -> Dict[str, list[dict]]:
    normative = get_normative_tables()
    usura_table = normative.get_table("tasso_usura")
    usura_options = [
        {"value": row.get("category", ""), "label": row.get("label", row.get("category", ""))}
        for row in list(usura_table.get("rows") or [])
    ]
    onorari = gestore.opzioni_onorari_forensi()
    return {
        "contributo_unificato": [
            {"value": row["value"], "label": row["label"]}
            for row in gestore.opzioni_contributo_unificato()
        ],
        "usura": usura_options,
        "onorari_materie": onorari["materie"],
        "onorari_gradi": onorari["gradi"],
        "onorari_complessita": onorari["complessita"],
        "onorari_fasi": onorari["fasi"],
    }


def _tool_panel(entry: Mapping[str, Any], runtime: Mapping[str, Any], fascicolo_sel, cliente_sel) -> Dict[str, Any]:
    from pct.strumenti_legali import GestioneStrumentiLegali

    gestore = GestioneStrumentiLegali(
        normative_db_path=current_app.config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json")
    )
    prefill = gestore.build_prefill(
        fascicolo=fascicolo_sel,
        cliente=cliente_sel,
        studio=_studio_context(),
        utente=g.get("utente_corrente"),
    )
    defaults = gestore.build_form_state(prefill, None)
    defaults.update(dict(runtime.get("preset_overrides") or {}))
    schema = dict(runtime.get("schema") or {})
    field_values = dict(defaults)
    options_map = _build_dynamic_options(schema, gestore)
    result_payload = None
    render_payload = None

    if request.method == "POST" and request.form.get("app_id", "").strip() == entry.get("id"):
        render_payload = dict(defaults)
        for field in schema.get("fields", []):
            name = field["name"]
            if field.get("type") == "multiselect":
                render_payload[name] = request.form.getlist(name)
            else:
                render_payload[name] = request.form.get(name, defaults.get(name, ""))
        try:
            method_name = schema.get("method")
            result_payload = getattr(gestore, method_name)(render_payload)
            field_values = dict(render_payload)
        except Exception as exc:
            current_app.logger.exception("Errore applicazioni tool %s: %s", entry.get("id"), exc)
            result_payload = {
                "warnings": [str(exc)],
                "notes": [],
                "sources": [],
            }
            field_values = dict(render_payload)

    normalized = build_tool_result(str(runtime.get("tool_id") or ""), result_payload or {})
    fields = []
    for field in schema.get("fields", []):
        item = dict(field)
        source = field.get("options")
        if isinstance(source, str):
            item["options"] = list(options_map.get(source, []))
        else:
            item["options"] = list(source or [])
        item["value"] = field_values.get(field["name"], "" if field.get("type") != "multiselect" else [])
        fields.append(item)

    return {
        "kind": "tool",
        "title": entry.get("title"),
        "subtitle": schema.get("subtitle") or entry.get("summary"),
        "submit_label": schema.get("submit_label", "Esegui"),
        "fields": fields,
        "metrics": normalized["metrics"],
        "tables": normalized["tables"],
        "preview_text": normalized["preview_text"],
        "notes": list(result_payload.get("notes") or []) if result_payload else [],
        "warnings": list(result_payload.get("warnings") or []) if result_payload else [],
        "sources": list(result_payload.get("sources") or []) if result_payload else [],
    }


def _template_panel(entry: Mapping[str, Any]) -> Dict[str, Any]:
    matches = _matching_templates(entry)
    checklists = _matching_checklists(entry)
    counts = Counter(row["categoria"] for row in matches)
    metrics = [
        _metric("Modelli compatibili", str(len(matches))),
        _metric("Checklist correlate", str(len(checklists))),
        _metric("Categorie coperte", str(len(counts))),
    ]
    return {
        "kind": "template_atti",
        "title": entry.get("title"),
        "subtitle": "Modelli, controlli e percorsi di redazione coerenti con la voce selezionata.",
        "metrics": metrics,
        "matches": matches,
        "checklists": checklists,
        "actions": [
            {"label": "Apri Catalogo Atti e Modelli", "url": url_for("template_atti.catalogo"), "variant": "primary"},
            {"label": "Apri Controlli Atti", "url": url_for("checklist_atti"), "variant": "outline-secondary"},
        ],
    }


def _rassegna_panel(entry: Mapping[str, Any]) -> Dict[str, Any]:
    snapshot = _legal_snapshot()
    source_rows = list(snapshot.get("source_rows") or [])[:8]
    alerts = list(snapshot.get("stored_alerts") or [])[:6]
    metrics = [
        _metric("Fonti monitorate", str(len(snapshot.get("source_rows") or []))),
        _metric("Alert registrati", str(len(snapshot.get("stored_alerts") or []))),
        _metric("News archiviate", str(len(snapshot.get("news_items") or []))),
    ]
    return {
        "kind": "rassegna",
        "title": entry.get("title"),
        "subtitle": "Fonti ufficiali, alert, audit e monitor normativi nello stesso presidio operativo.",
        "metrics": metrics,
        "feed_rows": source_rows,
        "alert_rows": alerts,
        "actions": [
            {"label": "Apri Ricerca legale", "url": url_for("legal_intelligence.index"), "variant": "primary"},
            {"label": "Apri aggiornamenti legali", "url": url_for("legal_updates_admin.dashboard"), "variant": "outline-secondary"},
        ],
    }


def _scadenze_panel(entry: Mapping[str, Any]) -> Dict[str, Any]:
    gestore = get_scadenziario()
    stats = gestore.statistiche()
    imminenti = gestore.imminenti(15)[:8]
    metrics = [
        _metric("Scadenze aperte", str(stats.get("aperte", 0))),
        _metric("Imminenti 15 gg", str(len(imminenti))),
        _metric("Critiche", str(stats.get("critiche", 0))),
        _metric("Completate", str(stats.get("completate", 0))),
    ]
    rows = [
        {
            "titolo": item.titolo,
            "data": _fmt_date_it(item.data_scadenza),
            "priorita": item.priorita.value,
            "fascicolo": item.id_fascicolo,
        }
        for item in imminenti
    ]
    return {
        "kind": "scadenze",
        "title": entry.get("title"),
        "subtitle": "Scadenze, termini imminenti e raccordo operativo con il fascicolo.",
        "metrics": metrics,
        "rows": rows,
        "actions": [
            {"label": "Apri scadenziario", "url": url_for("scadenziario"), "variant": "primary"},
            {"label": "Apri Controlli Atti", "url": url_for("checklist_atti"), "variant": "outline-secondary"},
        ],
    }


def _economico_panel(entry: Mapping[str, Any]) -> Dict[str, Any]:
    fatturazione = get_fatturazione()
    preventivi = get_preventivi()
    fatt_stats = fatturazione.statistiche()
    recent_parcelle = fatturazione.tutte()[:6]
    recent_preventivi = preventivi.tutti_preventivi()[:6]
    recent_conferimenti = preventivi.tutti_conferimenti()[:6]
    metrics = [
        _metric("Fatture emesse", str(fatt_stats.get("totale_emesse", 0))),
        _metric("Incassato", f"{_fmt_money(fatt_stats.get('incassato'))}"),
        _metric("Preventivi", str(len(preventivi.tutti_preventivi()))),
        _metric("Conferimenti", str(len(preventivi.tutti_conferimenti()))),
    ]
    return {
        "kind": "economico",
        "title": entry.get("title"),
        "subtitle": "Preventivi, conferimenti, parcelle e stato economico nello stesso pannello operativo.",
        "metrics": metrics,
        "parcelle": recent_parcelle,
        "preventivi": recent_preventivi,
        "conferimenti": recent_conferimenti,
        "actions": [
            {"label": "Apri Parcelle e Fatture", "url": url_for("fatturazione.lista"), "variant": "primary"},
            {"label": "Apri Preventivi e Incarichi", "url": url_for("preventivi.wizard"), "variant": "outline-secondary"},
        ],
    }


def _telematico_panel(entry: Mapping[str, Any]) -> Dict[str, Any]:
    portali = _carica_portali()
    fascicoli = get_fascicoli().tutti(archiviati=True)[:8]
    metrics = [
        _metric("Portali attivi", str(len(portali))),
        _metric("Fascicoli presidiati", str(len(get_fascicoli().tutti(archiviati=True)))),
        _metric("Documenti studio", str(sum(len(f.documenti) for f in get_fascicoli().tutti(archiviati=True)))),
    ]
    portal_rows = [
        {
            "nome": row.nome,
            "stato": "attivo" if row.attivo else "inattivo",
            "categoria": row.categoria,
        }
        for row in portali[:6]
    ]
    fascicolo_rows = [
        {
            "id": fascicolo.id,
            "numero": fascicolo.numero,
            "titolo": fascicolo.titolo,
            "tribunale": fascicolo.tribunale,
            "documenti": len(fascicolo.documenti),
        }
        for fascicolo in fascicoli
    ]
    return {
        "kind": "telematico",
        "title": entry.get("title"),
        "subtitle": "PST, PDP, PAT e fascicoli collegati con portali attivi e documenti disponibili.",
        "metrics": metrics,
        "portali": portal_rows,
        "fascicoli": fascicolo_rows,
        "actions": [
            {"label": "Apri Centro Servizi Telematici", "url": url_for("telematico_dashboard"), "variant": "primary"},
            {"label": "Apri PolisWeb / PST", "url": url_for("polisWeb_home"), "variant": "outline-secondary"},
        ],
    }


def _lookup_panel(entry: Mapping[str, Any]) -> Dict[str, Any]:
    entry_id = _clean_text(entry.get("id"))
    query_default = _clean_text(request.values.get("lookup_q"))
    if not query_default:
        if "pec" in entry_id:
            query_default = "pec"
        elif "unep" in entry_id:
            query_default = "UNEP"
        elif "ufficio" in entry_id:
            query_default = "tribunale"
    rows = _lookup_uffici(query_default)
    utility = _utility_result(entry, request.form or request.args)
    fields = (
        _utility_form(entry_id)
        if entry_id in {"verifica_partita_iva", "verifica_iban", "calcolo_codice_fiscale", "decodifica_codice_fiscale"}
        else [{"name": "lookup_q", "label": "Ricerca ufficio / PEC", "type": "text", "value": query_default}]
    )
    normalized_fields = []
    for field in fields:
        item = dict(field)
        item["value"] = item.get("value", request.values.get(item["name"], ""))
        normalized_fields.append(item)
    return {
        "kind": "lookup",
        "title": entry.get("title"),
        "subtitle": "Ricerca operativa su uffici, codici e verifiche formali con esito leggibile.",
        "lookup_query": query_default,
        "fields": normalized_fields,
        "metrics": utility["metrics"] if entry_id in {"verifica_partita_iva", "verifica_iban"} else [
            _metric("Risultati", str(len(rows))),
            _metric("Ricerca", query_default or "n/d"),
        ],
        "rows": rows,
        "notes": utility["notes"],
        "actions": [
            {"label": "Apri ricerca uffici", "url": url_for("tribunali"), "variant": "primary"},
        ],
    }


def _giurisprudenza_panel(entry: Mapping[str, Any]) -> Dict[str, Any]:
    query = _clean_text(request.values.get("q_corpus") or entry.get("title"))
    gestore = get_giurisprudenza()
    archive_rows = gestore.cerca(q=query)[:6]
    corpus_rows = gestore.cerca_corpus_professionale(q=query, limit=6)
    stats = gestore.statistiche()
    metrics = [
        _metric("Sentenze archiviate", str(stats.get("totale_sentenze", 0))),
        _metric("Corpus professionale", str(stats.get("corpus_sentenze", 0))),
        _metric("Fonti attive", str(stats.get("fonti_attive", 0))),
    ]
    return {
        "kind": "giurisprudenza",
        "title": entry.get("title"),
        "subtitle": "Corpus interno, archivio, fonti e ricerca giurisprudenziale coerente con il tema selezionato.",
        "metrics": metrics,
        "query": query,
        "archive_rows": archive_rows,
        "corpus_rows": corpus_rows,
        "actions": [
            {"label": "Apri archivio giurisprudenza", "url": url_for("giurisprudenza.index"), "variant": "primary"},
        ],
    }


def _patrimonio_panel(entry: Mapping[str, Any]) -> Dict[str, Any]:
    templates = _matching_templates(entry, limit=4)
    intelligence = get_legal_intelligence()
    stats = intelligence.statistiche_repository()
    metrics = [
        _metric("Modelli collegati", str(len(templates))),
        _metric("Fonti ufficiali", str(stats.get("legal_sources_repository", 0) or stats.get("legal_sources", 0) or 0)),
        _metric("Motori legali", str(stats.get("legal_engines_repository", 0) or stats.get("legal_engines", 0) or 0)),
    ]
    return {
        "kind": "patrimonio",
        "title": entry.get("title"),
        "subtitle": "Presidio patrimoniale e successorio con modelli, fonti e moduli collegati.",
        "metrics": metrics,
        "matches": templates,
        "actions": [
            {"label": "Apri Strumenti Forensi", "url": url_for("strumenti_legali.index"), "variant": "primary"},
            {"label": "Apri Redazione Atti", "url": url_for("template_atti.catalogo"), "variant": "outline-secondary"},
        ],
    }


def _catalogo_operativo_panel(entry: Mapping[str, Any]) -> Dict[str, Any]:
    matches = _matching_templates(entry, limit=3)
    return {
        "kind": "catalogo_operativo",
        "title": entry.get("title"),
        "subtitle": "Voce riallineata al dominio operativo corretto, con modulo, modello e percorso di lavoro coerenti.",
        "metrics": [
            _metric("Modelli trovati", str(len(matches))),
            _metric("Area", str(entry.get("section_title") or "")),
        ],
        "matches": matches,
        "actions": [
            {"label": entry.get("cta_label", "Apri modulo"), "url": entry.get("href"), "variant": "primary"},
            {"label": "Apri area completa", "url": url_for("applicazioni.index", sezione=entry.get("section_id", "")), "variant": "outline-secondary"},
        ],
    }


def build_active_panel(entry: Mapping[str, Any], fascicolo_sel=None, cliente_sel=None) -> Dict[str, Any]:
    runtime = resolve_runtime(entry)
    kind = runtime.get("kind")
    if kind == "tool":
        return _tool_panel(entry, runtime, fascicolo_sel, cliente_sel)
    if kind == "template_atti":
        return _template_panel(entry)
    if kind == "rassegna":
        return _rassegna_panel(entry)
    if kind == "scadenze":
        return _scadenze_panel(entry)
    if kind == "economico":
        return _economico_panel(entry)
    if kind == "telematico":
        return _telematico_panel(entry)
    if kind == "lookup":
        return _lookup_panel(entry)
    if kind == "giurisprudenza":
        return _giurisprudenza_panel(entry)
    if kind == "utility":
        fields = []
        for field in _utility_form(_clean_text(entry.get("id"))):
            item = dict(field)
            item["value"] = request.values.get(item["name"], "")
            fields.append(item)
        return {
            "kind": "utility",
            "title": entry.get("title"),
            "subtitle": "Utility operativa con verifica o calcolo direttamente nell'area operativa.",
            "fields": fields,
            **_utility_result(entry, request.form if request.method == "POST" else request.args),
        }
    if kind == "patrimonio":
        return _patrimonio_panel(entry)
    return _catalogo_operativo_panel(entry)


def build_workspace_context(entries: Iterable[Mapping[str, Any]], *, active_id: str = "") -> Dict[str, Any]:
    fascicoli, clienti_map, fascicolo_sel, cliente_sel = _resolve_case_context()
    rows = list(entries or [])
    active_entry = next((row for row in rows if row.get("id") == active_id), None) if active_id else None
    if active_entry is None and rows:
        active_entry = rows[0]
    active_panel = build_active_panel(active_entry, fascicolo_sel=fascicolo_sel, cliente_sel=cliente_sel) if active_entry else None
    return {
        "fascicoli": fascicoli,
        "clienti_map": clienti_map,
        "fascicolo_sel": fascicolo_sel,
        "cliente_sel": cliente_sel,
        "studio": _studio_context(),
        "active_entry": active_entry,
        "active_panel": active_panel,
    }
