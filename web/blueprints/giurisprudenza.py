from __future__ import annotations

from datetime import date, datetime
from functools import wraps
import sqlite3

from flask import Response, Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from pct.giurisprudenza import (
    ORIENTAMENTI,
    RILEVANZE_PRATICHE,
    TIPI_PROVVEDIMENTO,
    USI_NEL_SOFTWARE,
)
from web.helpers import get_giurisprudenza, get_giurisprudenza_readonly
from web.services.giurisprudenza_sync_runtime import (
    resolve_giurisprudenza_db_path,
    start_giurisprudenza_sync_job,
)

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


def _richiedi_corpus_lettura(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from web.services.operational_read_revision import DOMAIN_PERMISSIONS
        permission = getattr(g.get("utente_corrente"), "ha_permesso", lambda _name: False)
        required = DOMAIN_PERMISSIONS["normativa"]
        if not any(permission(name) for name in required):
            return Response("Permesso di consultazione delle fonti richiesto.", status=403)
        return fn(*args, **kwargs)
    return _richiedi_login(wrapper)


def _native_corpus_owner():
    from web.helpers import get_giurisprudenza_corpus_readonly
    return get_giurisprudenza_corpus_readonly()


@giurisprudenza.get("/corpus/api")
@_richiedi_corpus_lettura
def native_corpus_search():
    from web.services.giurisprudenza_native_runtime import search
    try:
        response=jsonify(search(_native_corpus_owner(),source=request.args.get("fonte",""),query=request.args.get("q","")))
    except ValueError:
        response=jsonify({"ok":False,"message":"Fonte o ricerca non valida.","records":[]});response.status_code=400
    except (OSError,sqlite3.Error):
        response=jsonify({"ok":False,"message":"Corpus locale non disponibile. Nessuno scaricamento avviato.","records":[]});response.status_code=503
    response.headers["Cache-Control"]="private, no-store"
    return response


@giurisprudenza.get("/corpus/<int:record_id>/testo")
@_richiedi_corpus_lettura
def native_corpus_text(record_id):
    from web.services.giurisprudenza_native_runtime import reader_document
    if request.args.get("embed")!="source":
        return redirect(url_for("giurisprudenza.index",corpus_documento=record_id))
    try:
        document=reader_document(_native_corpus_owner(),record_id)
        if not document:return Response("Testo non disponibile nell'archivio dello studio.",status=404)
        response=Response(document["text"],mimetype="text/plain") if request.args.get("format")=="txt" else Response(render_template("giurisprudenza/corpus_lettore.html",documento=document),mimetype="text/html")
    except (ValueError,OSError,sqlite3.Error):
        return Response("Lettura del testo conservato non riuscita. Nessuna acquisizione avviata.",status=503)
    response.headers.update({"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff","Content-Security-Policy":"default-src 'none'; style-src 'self'; frame-ancestors 'self'; sandbox allow-same-origin"})
    return response


@giurisprudenza.get("/corpus/<int:record_id>/documenti/<int:document_id>/pdf")
@_richiedi_corpus_lettura
def native_corpus_pdf(record_id,document_id):
    import os
    from flask import send_file
    from web.services.giurisprudenza_native_runtime import open_pdf
    stream=None
    try:
        stream=open_pdf(_native_corpus_owner(),record_id,document_id)
        if stream is None:return Response("Documento non disponibile nell'archivio dello studio.",status=404)
        if request.args.get("viewer") == "mobile":
            from pct.rendering_pdf import dimensioni_pagine
            from web.bootstrap.fascicoli_document_helpers import pdf_mobile_preview_html
            dimensions = dimensioni_pagine(stream)
            pages = [url_for("giurisprudenza.native_corpus_pdf_page", record_id=record_id,
                             document_id=document_id, page_number=page.numero) for page in dimensions]
            html, status, headers = pdf_mobile_preview_html(nome_documento="Provvedimento conservato",
                page_urls=pages, scarica_url=url_for("giurisprudenza.native_corpus_pdf",
                record_id=record_id, document_id=document_id), page_dimensions=dimensions)
            headers.update({"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src 'self'; base-uri 'none'; frame-ancestors 'self'; form-action 'none'"})
            return html, status, headers
        size=os.fstat(stream.fileno()).st_size
        response=send_file(stream,mimetype="application/pdf",download_name="provvedimento.pdf",as_attachment=False,conditional=False)
        response.content_length=size
        response.make_conditional(request.environ,accept_ranges=True,complete_length=size)
        response.call_on_close(stream.close)
    except (ValueError,OSError,sqlite3.Error):
        if stream:stream.close()
        return Response("Integrità del PDF conservato non confermata.",status=503)
    finally:
        if stream and request.args.get("viewer") == "mobile":
            stream.close()
    response.headers.update({"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff","Content-Security-Policy":"frame-ancestors 'self'"})
    return response


@giurisprudenza.get("/corpus/<int:record_id>/documenti/<int:document_id>/pagine/<int:page_number>.png")
@_richiedi_corpus_lettura
def native_corpus_pdf_page(record_id, document_id, page_number):
    from pct.rendering_pdf import RenderingPdfError, pagina_png
    from web.services.giurisprudenza_native_runtime import open_pdf
    stream = None
    try:
        stream = open_pdf(_native_corpus_owner(), record_id, document_id)
        if stream is None:
            return Response("Documento non disponibile nell'archivio dello studio.", status=404)
        try:
            data = pagina_png(stream, numero_pagina=page_number, scala=1.5)
        except RenderingPdfError:
            return Response("Pagina del PDF non disponibile.", status=422)
        response = Response(data, mimetype="image/png")
        response.headers.update({"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
        return response
    except (ValueError, OSError, sqlite3.Error):
        return Response("Integrità del PDF conservato non confermata.", status=503)
    finally:
        if stream:
            stream.close()


def _translation_reply(action):
    try:
        response = jsonify(action())
    except KeyError:
        response = jsonify(ok=False, message="Fonte o traduzione non presente nello studio.")
        response.status_code = 404
    except ValueError as exc:
        response = jsonify(ok=False, message=str(exc))
        response.status_code = 409
    except (OSError, sqlite3.Error):
        response = jsonify(ok=False, message="Servizio di traduzione locale non disponibile. Nessun documento originale è stato modificato.")
        response.status_code = 503
    response.headers["Cache-Control"] = "private, no-store"
    return response


@giurisprudenza.get("/corpus/<int:record_id>/traduzione-info")
@_richiedi_corpus_lettura
def native_translation_info(record_id):
    from web.services.giurisprudenza_translation import original, LANGUAGES
    def read():
        record, _text = original(_native_corpus_owner(), record_id)
        languages = sorted({str(item.get("lingua") or "").lower() for item in record.get("documenti", [])
            if item.get("valido", True) and str(item.get("lingua") or "").lower() in LANGUAGES})
        return {"ok": True, "title": record.get("titolo") or "Provvedimento", "languages": languages}
    return _translation_reply(read)


@giurisprudenza.post("/corpus/<int:record_id>/traduzioni")
@_richiedi_corpus_lettura
def native_translation_start(record_id):
    from web.services.giurisprudenza_translation import start
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(ok=False, message="Richiesta di traduzione non valida."), 400
    return _translation_reply(lambda: start(_native_corpus_owner(), current_app.config, record_id,
        str(payload.get("lingua") or ""), retry=payload.get("riprova") is True))


@giurisprudenza.post("/corpus/<int:record_id>/traduzioni/<identity>/passo")
@_richiedi_corpus_lettura
def native_translation_step(record_id, identity):
    from web.services.giurisprudenza_translation import step
    return _translation_reply(lambda: step(_native_corpus_owner(), current_app.config, record_id, identity))


@giurisprudenza.get("/corpus/<int:record_id>/traduzioni/<identity>/stato")
@_richiedi_corpus_lettura
def native_translation_status(record_id, identity):
    from web.services.giurisprudenza_translation import status
    return _translation_reply(lambda: status(_native_corpus_owner(), record_id, identity))


@giurisprudenza.get("/corpus/<int:record_id>/traduzioni/<identity>")
@_richiedi_corpus_lettura
def native_translation_reader(record_id, identity):
    import re
    from web.services.giurisprudenza_translation import document
    if not re.fullmatch(r"[0-9a-f]{32}", identity):
        return Response("Traduzione non trovata.", status=404)
    if request.args.get("embed") != "source":
        return redirect(url_for("giurisprudenza.index", corpus_documento=record_id, corpus_traduzione=identity))
    try:
        data = document(_native_corpus_owner(), record_id, identity)
        response = Response(render_template("giurisprudenza/traduzione_lettore.html", documento=data), content_type="text/html; charset=utf-8")
    except KeyError:
        return Response("Traduzione non presente nello studio.", status=404)
    except ValueError:
        return Response("Traduzione non completa o integrità non riscontrata. Apri l'originale o riprendi la traduzione.", status=409)
    except (OSError, sqlite3.Error):
        return Response("Archivio delle traduzioni non disponibile.", status=503)
    response.headers.update({"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'self'; base-uri 'none'; frame-ancestors 'self'; sandbox allow-same-origin"})
    return response


@giurisprudenza.get("/sentenzeweb/api")
@_richiedi_login
def sentenzeweb_search():
    from web.services.sentenzeweb_runtime import search
    try:
        result = jsonify(search(current_app.config, request.args.get("q", "")))
    except (ValueError, OSError, sqlite3.Error):
        result = jsonify({"ok": False, "message": "Archivio SentenzeWeb non disponibile. Nessun recupero esterno avviato."})
        result.status_code = 503
    result.headers["Cache-Control"] = "private, no-store"
    return result


@giurisprudenza.get("/sentenzeweb/<int:record_id>/documenti")
@_richiedi_login
def sentenzeweb_variants(record_id: int):
    from web.services.sentenzeweb_runtime import variants
    response = jsonify(variants(current_app.config, record_id))
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _sentenzeweb_reader_response(record_id: int, document_id: int | None = None):
    from web.services.sentenzeweb_reader import reader_document
    from web.services.sentenzeweb_runtime import read_text, read_variant
    if request.args.get("format") == "txt":
        text = (read_variant(current_app.config, record_id, document_id) if document_id is not None
                else read_text(current_app.config, record_id))
        response = Response(text or "Testo archiviato non disponibile.", status=200 if text else 404,
                            content_type="text/plain; charset=utf-8")
    else:
        if request.args.get("embed") != "source":
            return redirect(url_for("giurisprudenza.index", sentenzeweb=record_id, **({"documento": document_id} if document_id is not None else {})))
        try:
            document = reader_document(current_app.config, record_id, document_id)
        except (ValueError, OSError, sqlite3.Error):
            response = Response("Il testo non può essere mostrato: verifica di integrità non completata.",
                                status=503, content_type="text/plain; charset=utf-8")
        else:
            response = (Response(render_template("giurisprudenza/sentenzeweb_lettore.html", documento=document),
                                 content_type="text/html; charset=utf-8") if document else
                        Response("Testo archiviato non disponibile.", status=404,
                                 content_type="text/plain; charset=utf-8"))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = ("default-src 'none'; style-src 'self'; "
        "base-uri 'none'; frame-ancestors 'self'; sandbox allow-same-origin")
    return response


@giurisprudenza.get("/sentenzeweb/<int:record_id>/documenti/<int:document_id>/testo")
@_richiedi_login
def sentenzeweb_variant_text(record_id: int, document_id: int):
    return _sentenzeweb_reader_response(record_id, document_id)


@giurisprudenza.get("/sentenzeweb/<int:record_id>/testo")
@_richiedi_login
def sentenzeweb_text(record_id: int):
    return _sentenzeweb_reader_response(record_id)


@giurisprudenza.get("/<judgment_id>/testo")
@_richiedi_login
def testo_archiviato(judgment_id: str):
    """Read the stored text in the current tenant, without external fetch or writes."""
    record = get_giurisprudenza_readonly().get(judgment_id)
    text = str((record or {}).get("testo_integrale") or (record or {}).get("testo_normalizzato") or "")
    response = Response(
        text if text else "Testo archiviato non disponibile.",
        status=200 if text else 404,
        content_type="text/plain; charset=utf-8",
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response.headers["Content-Disposition"] = 'inline; filename="provvedimento.txt"'
    return response


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
        selected_source_ids = [source_id] if source_id else [
            row["id"] for row in gestore.catalogo_fonti() if row.get("supports_auto_sync")
        ]
        sync_job = start_giurisprudenza_sync_job(
            current_app._get_current_object(),
            giurisprudenza_db_path=resolve_giurisprudenza_db_path(
                current_app.config,
                dict(getattr(g, "data_paths", {}) or {}),
            ),
            source_ids=selected_source_ids,
        )
        if sync_job.get("started"):
            if source_id:
                source_label = next(
                    (row["nome"] for row in gestore.catalogo_fonti() if row.get("id") == source_id),
                    source_id,
                )
                flash(
                    f"Recupero automatico da fonte ufficiale avviato in background per {source_label}. Aggiorna la pagina tra qualche istante.",
                    "success",
                )
            else:
                flash(
                    "Recupero automatico da fonti ufficiali avviato in background. Le fonti non ufficiali restano in handoff prudente o import assistito.",
                    "success",
                )
        else:
            flash(
                "Una sincronizzazione giurisprudenziale e gia in corso per questo archivio. Attendi il completamento e aggiorna la pagina.",
                "info",
            )
    except Exception as exc:
        current_app.logger.exception("Errore sync giurisprudenza: %s", exc)
        flash(f"Recupero sentenze non riuscito: {exc}", "warning")
    redirect_args = {"source_system": source_id} if source_id else {}
    if (request.args.get("_legacy") or "").strip().lower() in {"1", "true", "si", "yes", "on"}:
        redirect_args["_legacy"] = "1"
    return redirect(url_for("giurisprudenza.index", **redirect_args))


@giurisprudenza.route("/api/classificazione-suggerita", methods=["POST"])
@_richiedi_login
def classificazione_suggerita():
    try:
        gestore = get_giurisprudenza()
        uploaded = request.files.get("materiale_file")
        file_name = getattr(uploaded, "filename", "") or ""
        file_bytes = uploaded.read() if uploaded and file_name else b""
        suggestion = gestore.suggerisci_classificazione_materiale(
            source_id=request.form.get("source_system", "").strip(),
            source_url=request.form.get("source_url", "").strip(),
            pasted_text=request.form.get("materiale_text", ""),
            file_name=file_name,
            file_bytes=file_bytes,
        )
        return jsonify({"ok": True, "suggestion": suggestion})
    except Exception as exc:
        current_app.logger.exception("Errore suggerimento classificazione giurisprudenza: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 200


@giurisprudenza.route("/importa-url", methods=["POST"])
@_richiedi_login
def importa_url():
    source_id = request.form.get("source_system", "").strip()
    source_url = request.form.get("source_url", "").strip()
    gestore = get_giurisprudenza()
    try:
        record = gestore.importa_da_url(source_url, source_id=source_id)
        flash("URL ufficiale registrato. Completa ora classificazione e testo della sentenza.", "success")
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

@giurisprudenza.get("/testo-ufficiale/<job_id>")
@_richiedi_login
def testo_ufficiale(job_id):
    """Read only: open a previously acquired document of the current study."""
    from web.services.openga_document_jobs import status
    try:
        result = status(str(get_giurisprudenza().db_path), job_id)
    except KeyError:
        return "Testo non presente in questo studio.", 404
    document = result.get("documento")
    if result.get("stato") != "acquisito" or not document:
        return "Il testo non è ancora disponibile o non ha superato la verifica.", 409
    response = current_app.make_response(render_template(
        "giurisprudenza/testo_ufficiale.html", documento=document))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
