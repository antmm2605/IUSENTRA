from __future__ import annotations

from datetime import date, datetime
from functools import wraps

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for

from pct.giurisprudenza import (
    ORIENTAMENTI,
    RILEVANZE_PRATICHE,
    TIPI_PROVVEDIMENTO,
    USI_NEL_SOFTWARE,
)
from web.helpers import get_giurisprudenza

giurisprudenza = Blueprint("giurisprudenza", __name__, url_prefix="/giurisprudenza")


def _richiedi_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def _fmt_date_it(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for parser in (datetime.fromisoformat,):
        try:
            return parser(text[:19]).strftime("%d/%m/%Y")
        except Exception:
            continue
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], pattern).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


def _fmt_datetime_it(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text[:19]).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return _fmt_date_it(text)


def _source_handoff(source_id: str) -> tuple[str, str]:
    mapping = {
        "merito_civile_bdp": ("polisWeb_home", "Apri PolisWeb / PST"),
        "giustizia_amministrativa": ("pat_home", "Apri PAT"),
        "giustizia_tributaria": ("sigit_home", "Apri PTT / SIGIT"),
    }
    endpoint = mapping.get(source_id)
    if not endpoint:
        return "", ""
    return url_for(endpoint[0]), endpoint[1]


def _decorate_sources(rows):
    out = []
    for row in rows:
        item = dict(row)
        handoff_url, handoff_label = _source_handoff(item.get("id", ""))
        item["handoff_url"] = handoff_url
        item["handoff_label"] = handoff_label
        item["last_run_fmt"] = _fmt_datetime_it((item.get("last_run") or {}).get("checked_at", ""))
        out.append(item)
    return out


def _decorate_record(row):
    item = dict(row)
    item["data_deposito_fmt"] = _fmt_date_it(item.get("data_deposito", ""))
    item["data_decisione_fmt"] = _fmt_date_it(item.get("data_decisione", ""))
    item["updated_at_fmt"] = _fmt_datetime_it(item.get("updated_at", ""))
    item["ultimo_sync_at_fmt"] = _fmt_datetime_it(item.get("ultimo_sync_at", ""))
    item["parole_chiave_count"] = len(item.get("parole_chiave") or [])
    item["norme_citate_count"] = len(item.get("norme_citate") or [])
    return item


def _form_context(record: dict):
    gestore = get_giurisprudenza()
    tassonomia = gestore.tassonomia()
    return {
        "record": record,
        "fonti": _decorate_sources(gestore.catalogo_fonti()),
        "tassonomia": tassonomia,
        "orientamenti": ORIENTAMENTI,
        "rilevanze": RILEVANZE_PRATICHE,
        "usi_nel_software": USI_NEL_SOFTWARE,
        "tipi_provvedimento": [label.title() for label in TIPI_PROVVEDIMENTO],
        "tassonomia_lookup": {
            area["title"]: {
                branch["title"]: list(branch.get("subbranches") or [])
                for branch in area.get("branches", [])
            }
            for area in tassonomia
        },
    }


@giurisprudenza.route("/", methods=["GET"])
@_richiedi_login
def index():
    gestore = get_giurisprudenza()
    fonti = _decorate_sources(gestore.catalogo_fonti())
    filters = {
        "q": request.args.get("q", ""),
        "source_system": request.args.get("source_system", ""),
        "area": request.args.get("area", ""),
        "branca": request.args.get("branca", ""),
        "sottobranca": request.args.get("sottobranca", ""),
        "grado": request.args.get("grado", ""),
        "giurisdizione": request.args.get("giurisdizione", ""),
        "orientamento": request.args.get("orientamento", ""),
        "uso_nel_software": request.args.get("uso_nel_software", ""),
    }
    results = [_decorate_record(row) for row in gestore.cerca(**filters)]
    return render_template(
        "giurisprudenza/index.html",
        oggi=date.today(),
        statistiche=gestore.statistiche(),
        storage_stats=gestore.storage_stats(),
        fonti=fonti,
        giurisdizioni=sorted({item["giurisdizione"] for item in fonti if item.get("giurisdizione")}),
        tassonomia=gestore.tassonomia(),
        filtri_catalogo=gestore.filtri(),
        filtri_correnti=filters,
        risultati=results,
        run_log=[dict(item, checked_at_fmt=_fmt_datetime_it(item.get("checked_at", ""))) for item in gestore.recent_sync_runs()],
        orientamenti=ORIENTAMENTI,
        usi_nel_software=USI_NEL_SOFTWARE,
        page_title="Archivio Sentenze",
    )


@giurisprudenza.route("/nuova", methods=["GET", "POST"])
@_richiedi_login
def nuova():
    gestore = get_giurisprudenza()
    if request.method == "POST":
        try:
            record = gestore.salva_da_form(request.form.to_dict(flat=True))
            flash("Scheda sentenza salvata correttamente.", "success")
            return redirect(url_for("giurisprudenza.dettaglio", judgment_id=record["id"]))
        except Exception as exc:
            current_app.logger.exception("Errore salvataggio scheda sentenza: %s", exc)
            flash(f"Salvataggio non riuscito: {exc}", "warning")
    source_id = request.args.get("source", "manuale_interno")
    record = gestore.empty_record(source_id)
    record["area"] = request.args.get("area", record.get("area", ""))
    record["branca"] = request.args.get("branca", "")
    record["sottobranca"] = request.args.get("sottobranca", "")
    return render_template("giurisprudenza/form.html", oggi=date.today(), **_form_context(record))


@giurisprudenza.route("/<judgment_id>", methods=["GET"])
@_richiedi_login
def dettaglio(judgment_id: str):
    gestore = get_giurisprudenza()
    record = gestore.get(judgment_id)
    if not record:
        flash("Scheda sentenza non trovata.", "warning")
        return redirect(url_for("giurisprudenza.index"))
    fonti = _decorate_sources(gestore.catalogo_fonti())
    fonte = next((row for row in fonti if row["id"] == record.get("source_system")), None)
    return render_template(
        "giurisprudenza/dettaglio.html",
        oggi=date.today(),
        record=_decorate_record(record),
        fonte=fonte,
        correlati=[_decorate_record(row) for row in gestore.related(judgment_id)],
        text_versions=[dict(item, created_at_fmt=_fmt_datetime_it(item.get("created_at", ""))) for item in gestore.judgment_text_versions(judgment_id)],
        raw_documents=[dict(item, downloaded_at_fmt=_fmt_datetime_it(item.get("downloaded_at", ""))) for item in gestore.raw_documents(judgment_id)],
        practice_links=gestore.practice_links(judgment_id),
    )


@giurisprudenza.route("/<judgment_id>/modifica", methods=["GET", "POST"])
@_richiedi_login
def modifica(judgment_id: str):
    gestore = get_giurisprudenza()
    current = gestore.get(judgment_id)
    if not current:
        flash("Scheda sentenza non trovata.", "warning")
        return redirect(url_for("giurisprudenza.index"))
    if request.method == "POST":
        try:
            payload = request.form.to_dict(flat=True)
            payload["id"] = judgment_id
            record = gestore.salva_da_form(payload)
            flash("Scheda sentenza aggiornata.", "success")
            return redirect(url_for("giurisprudenza.dettaglio", judgment_id=record["id"]))
        except Exception as exc:
            current_app.logger.exception("Errore aggiornamento scheda sentenza: %s", exc)
            flash(f"Aggiornamento non riuscito: {exc}", "warning")
    return render_template("giurisprudenza/form.html", oggi=date.today(), **_form_context(current))


@giurisprudenza.route("/sync", methods=["POST"])
@_richiedi_login
def sync():
    source_id = request.form.get("source_id", "").strip()
    gestore = get_giurisprudenza()
    try:
        report = gestore.sync_sources(source_ids=[source_id] if source_id else None)
        flash(
            (
                "Recupero sentenze completato: "
                f"{report.get('changed_total', 0)} schede toccate "
                f"({report.get('imported_total', 0)} nuove, {report.get('updated_total', 0)} aggiornate)."
            ),
            "success",
        )
    except Exception as exc:
        current_app.logger.exception("Errore sync giurisprudenza: %s", exc)
        flash(f"Recupero sentenze non riuscito: {exc}", "warning")
    return redirect(url_for("giurisprudenza.index", source_system=source_id) if source_id else url_for("giurisprudenza.index"))


@giurisprudenza.route("/importa-url", methods=["POST"])
@_richiedi_login
def importa_url():
    source_id = request.form.get("source_system", "").strip()
    source_url = request.form.get("source_url", "").strip()
    gestore = get_giurisprudenza()
    try:
        record = gestore.importa_da_url(source_url, source_id=source_id)
        flash("Recupero da URL ufficiale completato. Completa ora la classificazione della sentenza.", "success")
        return redirect(url_for("giurisprudenza.modifica", judgment_id=record["id"]))
    except Exception as exc:
        current_app.logger.exception("Errore import URL giurisprudenza: %s", exc)
        flash(f"Importazione URL non riuscita: {exc}", "warning")
        return redirect(url_for("giurisprudenza.index"))


@giurisprudenza.route("/importa-materiale", methods=["POST"])
@_richiedi_login
def importa_materiale():
    gestore = get_giurisprudenza()
    uploaded = request.files.get("materiale_file")
    file_name = getattr(uploaded, "filename", "") or ""
    file_bytes = uploaded.read() if uploaded and file_name else b""
    hints = {
        "area": request.form.get("area_hint", "").strip(),
        "branca": request.form.get("branca_hint", "").strip(),
        "sottobranca": request.form.get("sottobranca_hint", "").strip(),
        "uso_nel_software": request.form.get("uso_nel_software_hint", "").strip(),
        "rilevanza_pratica": request.form.get("rilevanza_pratica_hint", "").strip(),
    }
    try:
        report = gestore.importa_da_materiale(
            source_id=request.form.get("source_system", "").strip(),
            source_url=request.form.get("source_url", "").strip(),
            pasted_text=request.form.get("materiale_text", ""),
            file_name=file_name,
            file_bytes=file_bytes,
            hints=hints,
        )
        imported = int(report.get("imported", 0) or 0)
        updated = int(report.get("updated", 0) or 0)
        records = list(report.get("records") or [])
        flash(
            f"Import assistito completato: {imported} nuove schede, {updated} aggiornate.",
            "success",
        )
        if len(records) == 1:
            return redirect(url_for("giurisprudenza.modifica", judgment_id=records[0]["id"]))
        source_id = request.form.get("source_system", "").strip() or (records[0].get("source_system") if records else "")
        return redirect(url_for("giurisprudenza.index", source_system=source_id) if source_id else url_for("giurisprudenza.index"))
    except Exception as exc:
        current_app.logger.exception("Errore import materiale giurisprudenza: %s", exc)
        flash(f"Import assistito non riuscito: {exc}", "warning")
        return redirect(url_for("giurisprudenza.index"))
