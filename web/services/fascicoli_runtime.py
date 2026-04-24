"""Runtime fascicoli estratto da web.app."""

from __future__ import annotations

import base64
import io
import os
import re
import shutil
import unicodedata
import zipfile as _zipfile
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from urllib.parse import urlencode

from flask import Flask, g, request, url_for

from pct.fascicoli import Documento, Fascicolo, GestioneFascicoli, TipoAttivita, TipoDocumento, TipoFascicolo
from pct.fascicolo_workspace import (
    build_fascicolo_workspace as _shared_build_fascicolo_workspace,
    fascicolo_text as _shared_fascicolo_text,
)
from pct.reginde import ClientReGINde


def build_fascicoli_runtime(
    app: Flask,
    *,
    get_deposito_guidato,
    get_config_studio,
    get_utenti,
    audit,
    sync_pubblica,
    accoda_ocr,
    encrypt_doc,
    decrypt_doc,
) -> dict[str, Any]:
    _accoda_ocr = accoda_ocr
    _encrypt_doc = encrypt_doc
    _decrypt_doc = decrypt_doc
    _sync = SimpleNamespace(pubblica=sync_pubblica)
    def _documento_payload_per_validazione(gf: GestioneFascicoli, fasc: Fascicolo, doc_id: str) -> dict | None:
        doc = next((item for item in fasc.documenti if item.id == doc_id), None)
        if not doc:
            return None
        try:
            percorso = str(gf.percorso_documento(fasc.id, doc_id))
        except KeyError:
            return None
        return {
            "id": doc.id,
            "nome": doc.nome,
            "tipo": doc.tipo.value if hasattr(doc.tipo, "value") else str(doc.tipo),
            "percorso": percorso,
            "dimensione_bytes": doc.dimensione_bytes,
            "firmato_digitalmente": bool(doc.firmato_digitalmente),
            "data_documento": doc.data_documento,
        }

    def _build_deposito_validation_context(form_like, fasc: Fascicolo, operatore: str = "") -> dict:
        anno_rg_raw = (form_like.get("anno_rg", "") or "").strip()
        return {
            "tipo_atto": (form_like.get("tipo_atto", "ATTO_GENERICO") or "ATTO_GENERICO").strip(),
            "codice_registro": (form_like.get("codice_registro", "RG") or "RG").strip(),
            "oggetto": (form_like.get("oggetto", "") or fasc.titolo).strip(),
            "numero_rg": (form_like.get("numero_rg", "") or fasc.numero_rg).strip(),
            "anno_rg": int(anno_rg_raw) if anno_rg_raw.isdigit() else fasc.anno_rg,
            "atto_principale_id": (form_like.get("atto_principale_id", "") or "").strip(),
            "allegati_ids": list(form_like.getlist("allegati_ids")) if hasattr(form_like, "getlist") else list(form_like.get("allegati_ids", []) or []),
            "note": (form_like.get("note", "") or "").strip(),
            "operatore": operatore,
        }

    def _run_deposito_validation(
        fasc: Fascicolo,
        gf: GestioneFascicoli,
        form_like,
        operatore: str = "",
    ):
        ctx = _build_deposito_validation_context(form_like, fasc, operatore=operatore)
        selected_ids = []
        if ctx["atto_principale_id"]:
            selected_ids.append(ctx["atto_principale_id"])
        for doc_id in ctx["allegati_ids"]:
            if doc_id and doc_id not in selected_ids:
                selected_ids.append(doc_id)
        selected_docs = [
            payload
            for doc_id in selected_ids
            for payload in [_documento_payload_per_validazione(gf, fasc, doc_id)]
            if payload
        ]
        all_docs = [
            payload
            for doc in fasc.documenti
            for payload in [_documento_payload_per_validazione(gf, fasc, doc.id)]
            if payload
        ]
        return get_deposito_guidato().valida(
            fascicolo=fasc,
            context=ctx,
            selected_documents=selected_docs,
            all_documents=all_docs,
        )

    def _portale_ufficiale_label(fasc: Fascicolo) -> str:
        if fasc.tipo == TipoFascicolo.PENALE:
            return "PDP"
        if fasc.tipo == TipoFascicolo.AMMINISTRATIVO:
            return "PAT"
        if fasc.tipo == TipoFascicolo.TRIBUTARIO:
            return "SIGIT / PTT"
        return "PolisWeb / PST"

    def _tipo_lotto_portale(fasc: Fascicolo) -> str:
        if fasc.tipo == TipoFascicolo.PENALE:
            return "Acquisizione documenti PDP"
        if fasc.tipo == TipoFascicolo.AMMINISTRATIVO:
            return "Acquisizione documenti PAT"
        if fasc.tipo == TipoFascicolo.TRIBUTARIO:
            return "Acquisizione documenti SIGIT"
        return "Acquisizione documenti PolisWeb"

    def _infer_canale_deposito(fasc: Fascicolo, explicit: str = "") -> str:
        canale = (explicit or "").strip().upper()
        if canale:
            return canale
        if fasc.tipo == TipoFascicolo.PENALE:
            return "PDP_PENALE"
        if fasc.tipo == TipoFascicolo.AMMINISTRATIVO:
            return "PAT_AMMINISTRATIVO"
        if fasc.tipo == TipoFascicolo.TRIBUTARIO:
            return "PTT_TRIBUTARIO"
        return "PCT_TELEMATICO"

    def _resolve_ufficio_destinatario(raw_value: str, *, tipo: str | None = None) -> dict | None:
        try:
            from pct.uffici_giudiziari import risolvi_ufficio

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            return risolvi_ufficio(raw_value, tipo=tipo, cache_path=cache_path)
        except Exception:
            return None

    def _pst_import_dir_for_fascicolo(fasc: Fascicolo) -> Path:
        return Path(app.config["PST_IMPORT_DIR"]) / fasc.id

    def _pst_import_pending_count(fasc: Fascicolo) -> int:
        cartella = _pst_import_dir_for_fascicolo(fasc)
        if not cartella.exists():
            return 0
        return sum(1 for path in cartella.rglob("*") if path.is_file())

    def _fascicolo_text(*parts: object) -> str:
        return _shared_fascicolo_text(*parts)

    def _build_fascicolo_workspace(
        fasc: Fascicolo,
        *,
        apps: Optional[list] = None,
        scadenze: Optional[list] = None,
    ) -> dict:
        return _shared_build_fascicolo_workspace(fasc, apps=apps, scadenze=scadenze)

    def _url_with_query(base_url: str, **params) -> str:
        clean = {
            key: value
            for key, value in params.items()
            if value not in (None, "", [], ())
        }
        if not clean:
            return base_url
        joiner = "&" if "?" in base_url else "?"
        return f"{base_url}{joiner}{urlencode(clean, doseq=True)}"

    def _fascicolo_focus_url(id_fasc: str, *, focus: str = "", open_modal: str = "", **extra_params) -> str:
        base = url_for("dettaglio_fascicolo", id_fasc=id_fasc)
        params: dict[str, Any] = dict(extra_params)
        if focus:
            params["focus"] = focus
        if open_modal:
            params["open_modal"] = open_modal
        full = _url_with_query(base, **params)
        return f"{full}#sezione-{focus}" if focus else full

    def _compiler_correction_url(
        id_fasc: str,
        *,
        model_code: str,
        cliente_id: str = "",
        correction_title: str = "",
        correction_help: str = "",
        **query,
    ) -> str:
        if not model_code:
            return ""
        base = url_for(
            "template_atti.compila",
            model_code=model_code,
            id_cliente=cliente_id,
            id_fascicolo=id_fasc,
        )
        return _url_with_query(
            base,
            correction_title=correction_title,
            correction_help=correction_help,
            **query,
        )

    def _deposito_correction_url(id_fasc: str, **query) -> str:
        return _url_with_query(url_for("deposito_prepara", id_fasc=id_fasc), **query)

    def _fascicolo_edit_url(id_fasc: str, **query) -> str:
        return _url_with_query(url_for("modifica_fascicolo", id_fasc=id_fasc), **query)

    def _prefill_tipo_atto_from_summary(summary: Optional[dict]) -> str:
        summary = summary or {}
        practice_id = str(summary.get("practice_id") or "").strip().lower()
        model_code = str(summary.get("model_code") or "").strip().upper()
        haystack = f"{practice_id} {model_code}"
        if "cit" in haystack:
            return "ATTO_DI_CITAZIONE"
        if "comparsa" in haystack or "com_" in haystack:
            return "COMPARSA_RISPOSTA"
        if "cass" in haystack:
            return "RICORSO_CASSAZIONE"
        if "appello" in haystack:
            return "APPELLO"
        if "decreto" in haystack or "ingiunt" in haystack:
            return "DECRETO_INGIUNTIVO"
        if "ricorso" in haystack:
            return "RICORSO"
        return "ATTO_GENERICO"

    def _rc_normalize_status(value: str, *, default: str = "warning") -> str:
        state = str(value or "").strip().lower()
        if state in {"ok", "success", "passed", "pronto", "ready"}:
            return "ok"
        if state in {"warning", "warn", "avviso"}:
            return "warning"
        if state in {"blocco", "block", "blocked", "danger", "errore", "error"}:
            return "block"
        return default

    def _rc_status_rank(value: str) -> int:
        return {"block": 0, "warning": 1, "ok": 2}.get(_rc_normalize_status(value), 3)

    def _rc_section_meta(
        section_key: str,
        *,
        detail_url: str,
        deposit_url: str,
        compile_url: str,
    ) -> dict[str, str]:
        defaults = {
            "processuale": {
                "where": "Profilo fascicolo",
                "url": f"{detail_url}#sezione-profilo",
                "cta": "Apri profilo",
            },
            "documentale": {
                "where": "Documenti fascicolo",
                "url": f"{detail_url}#sezione-documenti-fascicolo",
                "cta": "Apri allegati",
            },
            "tecnico_pst": {
                "where": "Pre-deposito",
                "url": deposit_url,
                "cta": "Apri pre-deposito",
            },
            "redazionale": {
                "where": "Redattore guidato",
                "url": compile_url or f"{detail_url}#sezione-profilo",
                "cta": "Apri redattore",
            },
        }
        return defaults.get(
            section_key,
            {
                "where": "Fascicolo",
                "url": detail_url,
                "cta": "Apri",
            },
        )

    def _rc_first_section_message(section: dict, *, ok_fallback: str) -> str:
        items = list(section.get("items") or [])
        for wanted in ("block", "warning"):
            row = next((item for item in items if str(item.get("state") or "") == wanted), None)
            if row:
                return str(row.get("detail") or row.get("action") or row.get("title") or "").strip()
        row = next((item for item in items if str(item.get("state") or "") == "ok"), None)
        if row:
            return str(row.get("detail") or row.get("title") or ok_fallback).strip()
        return ok_fallback

    def _rc_gate_status(gate: dict, fallback_state: str) -> str:
        if not gate:
            return _rc_normalize_status(fallback_state)
        if not gate.get("applicable", True):
            return "ok"
        if gate.get("allowed"):
            return "ok"
        return _rc_normalize_status(fallback_state, default="block")

    def _rc_issue_family(issue: dict) -> str:
        haystack = " ".join(
            filter(
                None,
                [
                    str(issue.get("code") or "").lower(),
                    str(issue.get("title") or "").lower(),
                    str(issue.get("detail") or "").lower(),
                ],
            )
        )
        if "procura" in haystack:
            return "procura"
        if "notifica" in haystack or "relata" in haystack:
            return "notifica"
        if "contributo" in haystack:
            return "contributo"
        if "sentenza" in haystack and "mancante" in haystack:
            return "sentenza"
        if "oggetto" in haystack and ("mancante" in haystack or "non definito" in haystack):
            return "oggetto"
        if "firma" in haystack and ("mancante" in haystack or "non firmato" in haystack):
            return "firma"
        if "pdf/a" in haystack or "pdfa" in haystack:
            return "pdfa"
        if "sede" in haystack and "mancante" in haystack or "ufficio" in haystack and "mancante" in haystack:
            return "ufficio"
        if "cliente" in haystack and "mancante" in haystack:
            return "cliente"
        return ""

    def _rc_issue_dedupe_rank(issue: dict) -> int:
        family = _rc_issue_family(issue)
        if not family:
            return 100

        code = str(issue.get("code") or "").strip().lower()
        title = str(issue.get("title") or "").strip().lower()
        service = str(issue.get("service") or "").strip().upper()

        # Priorita per famiglia: il controllo piu specifico vince
        specific_codes = {
            "procura": {"citazione_procura_mancante"},
            "notifica": {"citazione_relata_notifica_mancante"},
            "contributo": {"citazione_contributo_non_rilevato"},
            "sentenza": {"citazione_sentenza_mancante"},
            "oggetto": {"redazione_oggetto_mancante"},
            "firma": {"atto_principale_non_firmato"},
            "pdfa": {"atto_principale_non_pdfa"},
            "ufficio": {"sede_mancante"},
            "cliente": {"citazione_cliente_mancante", "campo_mancante_id_cliente"},
        }
        generic_codes = {
            "procura": {"doc_procura_missing"},
            "notifica": {"doc_notifica_missing"},
            "contributo": {"doc_contributo_missing"},
            "sentenza": {"doc_sentenza_missing"},
            "oggetto": set(),
            "firma": set(),
            "pdfa": set(),
            "ufficio": {"ufficio_non_risolto"},
            "cliente": set(),
        }
        selection_codes = {
            "procura": {"procura_mancante"},
            "notifica": {"prova_notifica_non_rilevata"},
            "contributo": {"contributo_non_evidenziato"},
        }

        if code in specific_codes.get(family, set()):
            return 0
        if code in generic_codes.get(family, set()):
            return 1
        if code in selection_codes.get(family, set()):
            return 2
        # Controlli processuali hanno priorita su redazionali per lo stesso concetto
        if service == "GIURIDICO":
            return 3
        if service == "DOCUMENTALE":
            return 4
        if service == "TECNICO":
            return 5
        if "non inclus" in title or "non selezion" in title:
            return 6
        if "non rilevat" in title:
            return 5
        return 50

    def _rc_prune_redundant_corrections(corrections: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[str]]:
        best_for_family: dict[str, tuple[int, int]] = {}
        for index, correction in enumerate(corrections):
            family = _rc_issue_family(correction)
            if not family:
                continue
            rank = _rc_issue_dedupe_rank(correction)
            current = best_for_family.get(family)
            if current is None or rank < current[0]:
                best_for_family[family] = (rank, index)

        pruned: list[dict[str, Any]] = []
        suppressed_titles: set[str] = set()
        for index, correction in enumerate(corrections):
            family = _rc_issue_family(correction)
            if family:
                _, best_index = best_for_family.get(family, (999, index))
                if index != best_index:
                    title = str(correction.get("title") or "").strip().lower()
                    if title:
                        suppressed_titles.add(title)
                    continue
            pruned.append(correction)
        return pruned, suppressed_titles

    def _rc_state_from_items(items: list[dict[str, Any]], *, default: str = "ok") -> str:
        if any(str(item.get("state") or item.get("status") or "").strip() == "block" for item in items):
            return "block"
        if any(str(item.get("state") or item.get("status") or "").strip() == "warning" for item in items):
            return "warning"
        return default

    def _responsabile_issue_action_meta(
        id_fasc: str,
        issue: dict,
        *,
        cliente=None,
        summary: Optional[dict] = None,
    ) -> dict[str, str]:
        summary = summary or {}
        model_code = str(summary.get("model_code") or "").strip()
        cliente_id = str(getattr(cliente, "id", "") or "").strip()
        registry_suggestion = str(summary.get("registry_suggestion") or "").strip().upper()

        code = str(issue.get("code") or "").strip().lower()
        field = str(issue.get("field") or "").strip().lower()
        service = str(issue.get("service") or "").upper()
        tokens = " ".join(
            filter(
                None,
                [
                    code,
                    field,
                    str(issue.get("title") or "").lower(),
                    str(issue.get("detail") or "").lower(),
                ],
            )
        )

        if code == "citazione_udienza_mancante" or field == "data_prima_udienza":
            return {
                "action_url": _fascicolo_edit_url(
                    id_fasc,
                    intent="prima_udienza",
                    highlight="data_prima_udienza",
                    correction_title="Imposta prima udienza",
                    correction_help="Per l'atto di citazione serve una data di prima comparizione strutturata nel fascicolo.",
                ),
                "action_label": "Imposta prima udienza",
            }

        if code == "citazione_data_notifica_non_strutturata" or field == "data_notifica_citazione":
            return {
                "action_url": _fascicolo_edit_url(
                    id_fasc,
                    intent="data_notifica_citazione",
                    highlight="data_notifica_citazione",
                    correction_title="Inserisci data notifica",
                    correction_help="La data di notificazione della citazione deve essere salvata in modo strutturato per i controlli successivi.",
                ),
                "action_label": "Inserisci data notifica",
            }

        if code in {"citazione_procura_mancante", "doc_procura_missing"} or "procura" in tokens:
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="documenti",
                    open_modal="documento",
                    doc_kind="PROCURA",
                    correction_title="Carica procura alle liti",
                    correction_help="Il controllo ha rilevato l'assenza della procura. Apri il modal già posizionato sul tipo documento corretto.",
                ),
                "action_label": "Carica procura",
            }

        if code in {"citazione_relata_notifica_mancante", "doc_notifica_missing"} or any(
            token in tokens for token in ("notifica", "relata")
        ):
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="documenti",
                    open_modal="documento",
                    doc_kind="NOTIFICA",
                    correction_title="Carica relata o prova di notifica",
                    correction_help="Per superare il blocco documentale serve una relata o prova notificatoria coerente con l'atto introduttivo.",
                ),
                "action_label": "Carica relata / notifica",
            }

        if code in {"citazione_contributo_non_rilevato", "doc_contributo_missing"} or "contributo" in tokens:
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="documenti",
                    open_modal="documento",
                    doc_kind="ALLEGATO",
                    doc_hint="contributo",
                    correction_title="Carica ricevuta contributo unificato",
                    correction_help="Il fascicolo non mostra ancora la ricevuta del contributo o dei diritti quando dovuti.",
                ),
                "action_label": "Carica contributo",
            }

        if code in {"citazione_cliente_mancante", "redazione_assistito_non_strutturato"} or any(
            token in tokens for token in ("assistito", "cliente", "attore")
        ):
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="parti",
                    open_modal="parte",
                    role_hint="ASSISTITO",
                    correction_title="Aggiungi assistito",
                    correction_help="La conformità richiede almeno l'assistito strutturato nella sezione Parti del procedimento.",
                ),
                "action_label": "Aggiungi assistito",
            }

        if code in {"citazione_cf_controparte_non_rilevato", "redazione_controparte_non_strutturata"} or "controparte" in tokens:
            return {
                "action_url": _fascicolo_focus_url(
                    id_fasc,
                    focus="parti",
                    open_modal="parte",
                    role_hint="CONTROPARTE",
                    correction_title="Aggiungi controparte",
                    correction_help="La controparte va strutturata nella pratica prima della redazione o del deposito.",
                ),
                "action_label": "Aggiungi controparte",
            }

        if field in {"tribunale", "numero_rg", "anno_rg", "sezione", "giudice", "valore_causa", "oggetto", "avvocato_referente"}:
            return {
                "action_url": _fascicolo_edit_url(
                    id_fasc,
                    intent=field,
                    highlight=field,
                    correction_title="Completa dati fascicolo",
                    correction_help="Apri la scheda del fascicolo direttamente sul campo che il controllo ha segnalato.",
                ),
                "action_label": "Completa dati fascicolo",
            }

        if service == "TECNICO_PST" or any(token in tokens for token in ("schema", "xml", "datiatto", "registro", "rito", "preview")):
            return {
                "action_url": _deposito_correction_url(
                    id_fasc,
                    intent="registro",
                    correction_title="Configura pre-deposito",
                    correction_help="Il wizard pre-deposito si apre già con i dati tecnici da confermare o correggere.",
                    prefill_tipo_atto=_prefill_tipo_atto_from_summary(summary),
                    prefill_registro=registry_suggestion,
                ),
                "action_label": "Apri pre-deposito",
            }

        if service == "REDAZIONALE" or any(
            token in tokens for token in ("redazione", "fatti", "facts", "requests", "conclusioni", "richieste", "datiatto")
        ):
            focus_field = "facts"
            highlight_fields = ["facts"]
            if any(token in tokens for token in ("conclusioni", "richieste", "requests")):
                focus_field = "requests_or_conclusions"
                highlight_fields = ["requests_or_conclusions"]
            elif any(token in tokens for token in ("datiatto", "xml", "schema")):
                focus_field = "recipient_or_court"
                highlight_fields = ["case_id", "recipient_or_court", "subject"]
            compile_url = _compiler_correction_url(
                id_fasc,
                model_code=model_code,
                cliente_id=cliente_id,
                intent="redazione",
                focus_field=focus_field,
                highlight_fields=",".join(highlight_fields),
                correction_title="Completa il blocco redazionale",
                correction_help="Il redattore guidato si apre sul blocco da completare o correggere.",
            )
            if compile_url:
                return {"action_url": compile_url, "action_label": "Apri redattore guidato"}

        return {
            "action_url": _fascicolo_edit_url(
                id_fasc,
                correction_title="Verifica il fascicolo",
                correction_help="Controlla e completa i dati generali del fascicolo prima di procedere.",
            ),
            "action_label": "Verifica il fascicolo",
        }

    def _build_responsabile_conformita_disattivata(
        *,
        fascicolo: Fascicolo,
    ) -> dict[str, Any]:
        canale_label = _portale_ufficiale_label(fascicolo) or "PCT civile / lavoro / famiglia"
        modello_label = str(
            getattr(fascicolo, "oggetto", "")
            or getattr(fascicolo, "titolo", "")
            or "Atto"
        ).strip()
        summary_text = (
            "I controlli automatici sono disattivati per questo fascicolo. "
            "Riattiva il flag per rigenerare checklist, workflow e controlli rapidi."
        )
        return {
            "available": True,
            "controls_enabled": False,
            "workflow_label": "Controlli automatici disattivati",
            "readiness_label": "Il report di conformita e' momentaneamente sospeso per scelta utente.",
            "summary": summary_text,
            "overall_state": "disabled",
            "badge_class": "secondary",
            "general": {
                "state": "disabled",
                "label": "Disattivati",
                "score": 0,
                "blocking_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "passed_count": 0,
            },
            "practice_id": "",
            "practice_label": modello_label or "Fascicolo",
            "model_code": "",
            "model_name": modello_label,
            "channel": "",
            "channel_label": canale_label,
            "competence_rule": "",
            "registry_suggestion": "",
            "grade_label": "",
            "resolver": {},
            "semaforo": {
                "workflow": "disabled",
                "generale": "disabled",
                "processuale": "disabled",
                "giuridico": "disabled",
                "tecnico_pst": "disabled",
                "tecnico_ministeriale": "disabled",
                "documentale": "disabled",
                "redazionale": "disabled",
            },
            "sections": {},
            "passed_controls": [],
            "corrections": [],
            "action_gates": {},
            "required_documents": [],
            "missing_documents": [],
            "blocking_issues": [],
            "warning_issues": [],
            "info_issues": [],
            "issues": [],
            "next_steps": ["Riattiva i controlli automatici per rieseguire il report."],
            "sources": [],
            "deposit_ready": False,
            "is_blocking": False,
            "score": 0,
            "last_check_at": "",
            "canale_label": canale_label,
            "modello_label": modello_label,
            "summary_text": summary_text,
            "blockers_count": 0,
            "warnings_count": 0,
            "passed_count": 0,
            "missing_docs_count": 0,
            "ready_reason": "Controlli automatici disattivati per questo fascicolo.",
            "next_step": {
                "title": "Riattiva i controlli automatici",
                "reason": summary_text,
                "cta": "Riattiva controlli",
                "url": f"{url_for('dettaglio_fascicolo', id_fasc=fascicolo.id)}#sezione-responsabile-conformita",
            },
            "checklist": [],
            "workflow": [],
            "groups": [],
        }

    def _build_responsabile_conformita_fascicolo(
        *,
        fascicolo: Fascicolo,
        cliente=None,
        preventivo=None,
        conferimento=None,
        parti=None,
    ) -> dict[str, Any]:
        if not bool(getattr(fascicolo, "compliance_controls_enabled", True)):
            return _build_responsabile_conformita_disattivata(fascicolo=fascicolo)

        from pct.responsabile_conformita import build_fascicolo_compliance_summary

        summary = build_fascicolo_compliance_summary(
            fascicolo=fascicolo,
            cliente=cliente,
            preventivo=preventivo,
            conferimento=conferimento,
            config=app.config,
            utente=g.utente_corrente,
            office_cache_path=os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json"),
            parti=parti,
        )
        return _arricchisci_responsabile_conformita(
            summary,
            fascicolo=fascicolo,
            cliente=cliente,
        )

    def _arricchisci_responsabile_conformita(
        summary: Optional[dict],
        *,
        fascicolo: Fascicolo,
        cliente=None,
    ) -> Optional[dict]:
        if not summary or not summary.get("available"):
            return summary

        model_code = str(summary.get("model_code") or "").strip()
        cliente_id = str(getattr(cliente, "id", "") or "").strip()
        compile_url = (
            url_for(
                "template_atti.compila",
                model_code=model_code,
                id_cliente=cliente_id,
                id_fascicolo=fascicolo.id,
            )
            if model_code
            else ""
        )
        detail_url = url_for("dettaglio_fascicolo", id_fasc=fascicolo.id)
        deposit_url = url_for("deposito_prepara", id_fasc=fascicolo.id)

        summary["corrections"] = [
            {
                **issue,
                **_responsabile_issue_action_meta(
                    fascicolo.id,
                    issue,
                    cliente=cliente,
                    summary=summary,
                ),
            }
            for issue in summary.get("corrections", [])
        ]
        summary["corrections"], suppressed_titles = _rc_prune_redundant_corrections(
            list(summary.get("corrections") or [])
        )

        gates = dict(summary.get("action_gates") or {})
        if gates.get("generate_final_act") and compile_url:
            gates["generate_final_act"]["url"] = _compiler_correction_url(
                fascicolo.id,
                model_code=model_code,
                cliente_id=cliente_id,
                intent="redazione_finale",
                focus_field="subject",
                highlight_fields="subject,requests_or_conclusions",
                correction_title="Completa la bozza finale",
                correction_help="Risolvi i blocchi redazionali e strutturali prima della generazione definitiva.",
            )
            gates["generate_final_act"]["url_label"] = "Apri redattore guidato"
        if gates.get("generate_xml") and compile_url:
            gates["generate_xml"]["url"] = _compiler_correction_url(
                fascicolo.id,
                model_code=model_code,
                cliente_id=cliente_id,
                intent="datiatto_xml",
                focus_field="recipient_or_court",
                highlight_fields="case_id,recipient_or_court,subject",
                correction_title="Completa DatiAtto.xml",
                correction_help="Il redattore si apre già sui campi strutturati minimi utili alla generazione XML.",
            )
            gates["generate_xml"]["url_label"] = "Completa DatiAtto.xml"
        if gates.get("prepare_deposit"):
            gates["prepare_deposit"]["url"] = _deposito_correction_url(
                fascicolo.id,
                correction_title="Configura il pre-deposito",
                correction_help="Conferma registro, ufficio, dati atto e documenti prima della preparazione della busta.",
            )
            gates["prepare_deposit"]["url_label"] = "Apri pre-deposito"
        if gates.get("close_review"):
            gates["close_review"]["url"] = f"{detail_url}#sezione-responsabile-conformita"
            gates["close_review"]["url_label"] = "Rivedi controlli"
        summary["action_gates"] = gates

        corrections = list(summary.get("corrections") or [])
        corrections_by_title: dict[str, dict] = {}
        corrections_by_service: dict[str, list[dict]] = {}
        for correction in corrections:
            title_key = str(correction.get("title") or "").strip().lower()
            if title_key and title_key not in corrections_by_title:
                corrections_by_title[title_key] = correction
            service_key = str(correction.get("service") or "").strip().upper()
            if service_key:
                corrections_by_service.setdefault(service_key, []).append(correction)

        section_order = ["processuale", "documentale", "tecnico_pst", "redazionale"]
        checklist: list[dict[str, Any]] = []
        checklist_seen: set[str] = set()
        groups: list[dict[str, Any]] = []
        display_sections: dict[str, dict[str, Any]] = {}
        for section_key in section_order:
            section = dict((summary.get("sections") or {}).get(section_key) or {})
            section_meta = _rc_section_meta(
                section_key,
                detail_url=detail_url,
                deposit_url=deposit_url,
                compile_url=compile_url,
            )
            group_items: list[dict[str, Any]] = []
            section_items: list[dict[str, str]] = []
            raw_items = list(section.get("items") or [])
            for index, item in enumerate(raw_items):
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                if title.lower() in suppressed_titles:
                    continue
                normalized = _rc_normalize_status(item.get("state"))
                correction = corrections_by_title.get(title.lower(), {})
                item_url = str(correction.get("action_url") or (section_meta["url"] if normalized != "ok" else "")).strip()
                item_cta = str(
                    correction.get("action_label")
                    or correction.get("action")
                    or (section_meta["cta"] if item_url else "")
                ).strip()
                item_payload = {
                    "label": title,
                    "title": title,
                    "status": normalized,
                    "note": str(item.get("detail") or "").strip(),
                    "reason": str(item.get("detail") or "").strip(),
                    "source": str(correction.get("source") or section.get("label") or "").strip(),
                    "where": section_meta["where"],
                    "url": item_url,
                    "cta": item_cta,
                    "_sort": (_rc_status_rank(normalized), index),
                }
                group_items.append(item_payload)
                section_items.append(
                    {
                        "state": normalized,
                        "title": title,
                        "detail": str(item.get("detail") or "").strip(),
                        "action": item_cta,
                    }
                )
                # Checklist: solo controlli azionabili (block/warning),
                # i controlli "ok" restano solo nei gruppi di sezione
                if normalized != "ok":
                    checklist_key = title.lower()
                    if checklist_key not in checklist_seen:
                        checklist_seen.add(checklist_key)
                        checklist.append(item_payload.copy())

            group_items.sort(key=lambda row: row["_sort"])
            for row in group_items:
                row.pop("_sort", None)
            display_sections[section_key] = {
                "label": str(section.get("label") or section_key.replace("_", " ").title()).strip(),
                "state": _rc_state_from_items(
                    section_items,
                    default=_rc_normalize_status(section.get("state")),
                ),
                "items": section_items,
            }
            groups.append(
                {
                    "title": display_sections[section_key]["label"],
                    "status": display_sections[section_key]["state"],
                    "items": group_items,
                }
            )

        checklist.sort(key=lambda row: row["_sort"])
        for row in checklist:
            row.pop("_sort", None)

        def _first_correction_for_service(service_name: str) -> dict:
            return dict((corrections_by_service.get(service_name) or [{}])[0] or {})

        next_step_source = next(
            (
                correction
                for correction in corrections
                if _rc_normalize_status(correction.get("state")) == "block"
            ),
            None,
        ) or next(
            (
                correction
                for correction in corrections
                if _rc_normalize_status(correction.get("state")) == "warning"
            ),
            None,
        )
        if next_step_source:
            next_step = {
                "title": str(
                    next_step_source.get("action")
                    or next_step_source.get("title")
                    or "Apri correzione guidata"
                ).strip(),
                "reason": str(
                    next_step_source.get("detail")
                    or next_step_source.get("source")
                    or summary.get("summary")
                    or ""
                ).strip(),
                "cta": str(
                    next_step_source.get("action_label")
                    or next_step_source.get("action")
                    or "Correggi"
                ).strip(),
                "url": str(next_step_source.get("action_url") or detail_url).strip(),
            }
        else:
            prepare_gate = gates.get("prepare_deposit") or {}
            next_step = {
                "title": "Apri il pre-deposito tecnico",
                "reason": str(
                    prepare_gate.get("reason")
                    or summary.get("summary")
                    or "Rivedi il fascicolo prima del deposito."
                ).strip(),
                "cta": str(prepare_gate.get("url_label") or "Apri pre-deposito").strip(),
                "url": str(prepare_gate.get("url") or deposit_url).strip(),
            }

        sections = display_sections
        process_section = dict(sections.get("processuale") or {})
        document_section = dict(sections.get("documentale") or {})
        tech_section = dict(sections.get("tecnico_pst") or {})
        redaction_section = dict(sections.get("redazionale") or {})

        generate_final_gate = dict(gates.get("generate_final_act") or {})
        generate_xml_gate = dict(gates.get("generate_xml") or {})
        prepare_gate = dict(gates.get("prepare_deposit") or {})
        close_gate = dict(gates.get("close_review") or {})
        document_correction = _first_correction_for_service("DOCUMENTALE")

        workflow = [
            {
                "label": "Redazione atto",
                "status": _rc_gate_status(generate_final_gate, redaction_section.get("state")),
                "note": str(
                    generate_final_gate.get("reason")
                    or _rc_first_section_message(
                        redaction_section,
                        ok_fallback="Il blocco redazionale risulta coerente con il fascicolo.",
                    )
                ).strip(),
                "url": str(generate_final_gate.get("url") or compile_url).strip(),
                "cta": str(generate_final_gate.get("url_label") or "Apri redattore").strip(),
            },
            {
                "label": "Allegati obbligatori",
                "status": _rc_normalize_status(document_section.get("state")),
                "note": _rc_first_section_message(
                    document_section,
                    ok_fallback="Gli allegati oggi richiesti risultano presenti o gia censiti.",
                ),
                "url": str(
                    document_correction.get("action_url")
                    or f"{detail_url}#sezione-documenti-fascicolo"
                ).strip(),
                "cta": str(
                    document_correction.get("action_label")
                    or document_correction.get("action")
                    or "Apri allegati"
                ).strip(),
            },
            {
                "label": "XML ministeriale",
                "status": _rc_gate_status(generate_xml_gate, tech_section.get("state")),
                "note": str(
                    generate_xml_gate.get("reason")
                    or "Verifica i dati strutturati necessari alla generazione XML."
                ).strip(),
                "url": str(generate_xml_gate.get("url") or deposit_url).strip(),
                "cta": str(generate_xml_gate.get("url_label") or "Completa XML").strip(),
            },
            {
                "label": "Verifica tecnica PST",
                "status": _rc_normalize_status(tech_section.get("state")),
                "note": _rc_first_section_message(
                    tech_section,
                    ok_fallback="Nessun errore tecnico bloccante rilevato sui controlli PST.",
                ),
                "url": str(close_gate.get("url") or deposit_url).strip(),
                "cta": str(close_gate.get("url_label") or "Rivedi").strip(),
            },
            {
                "label": "Pre-deposito",
                "status": _rc_gate_status(prepare_gate, summary.get("overall_state")),
                "note": str(
                    prepare_gate.get("reason")
                    or "Riesegui il pre-deposito dopo le correzioni."
                ).strip(),
                "url": str(prepare_gate.get("url") or deposit_url).strip(),
                "cta": str(prepare_gate.get("url_label") or "Apri pre-deposito").strip(),
            },
        ]

        general = dict(summary.get("general") or {})
        visible_items = [item for group in groups for item in group.get("items", [])]
        visible_blockers = sum(1 for item in visible_items if item.get("status") == "block")
        visible_warnings = sum(1 for item in visible_items if item.get("status") == "warning")
        visible_passed = sum(1 for item in visible_items if item.get("status") == "ok")
        deposit_ready = bool(prepare_gate.get("allowed")) if prepare_gate.get("applicable", True) else summary.get("overall_state") == "ok"
        blocking_count = visible_blockers or int(general.get("blocking_count") or 0)
        summary.update(
            {
                "deposit_ready": deposit_ready,
                "is_blocking": blocking_count > 0,
                "score": int(general.get("score") or 0),
                "last_check_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "canale_label": str(summary.get("channel_label") or "").strip(),
                "modello_label": str(summary.get("model_name") or "").strip(),
                "summary_text": str(summary.get("summary") or "").strip(),
                "blockers_count": blocking_count,
                "warnings_count": visible_warnings or int(general.get("warning_count") or 0),
                "passed_count": visible_passed or int(general.get("passed_count") or 0),
                "missing_docs_count": len(summary.get("missing_documents") or []),
                "ready_reason": (
                    "Deposito pronto: non risultano blocchi residui sul fascicolo."
                    if deposit_ready
                    else f"Deposito non pronto: {str(summary.get('summary') or '').strip()}"
                ),
                "next_step": next_step,
                "checklist": checklist[:12],
                "workflow": workflow,
                "groups": groups,
            }
        )
        return summary

    def _fascicolo_form_correction_context() -> dict:
        intent = (request.args.get("intent", "") or "").strip()
        highlight = (request.args.get("highlight", "") or "").strip()
        title = (request.args.get("correction_title", "") or "").strip()
        help_text = (request.args.get("correction_help", "") or "").strip()
        if not any([intent, highlight, title, help_text]):
            return {}
        return {
            "active": True,
            "intent": intent,
            "highlight": highlight,
            "title": title or "Correzione guidata del fascicolo",
            "help": help_text or "Completa il campo evidenziato per superare il controllo di conformita'.",
        }

    def _deposito_correction_context(fascicolo: Fascicolo) -> dict:
        correction_title = (request.args.get("correction_title", "") or "").strip()
        correction_help = (request.args.get("correction_help", "") or "").strip()
        prefill_tipo_atto = (request.args.get("prefill_tipo_atto", "") or "").strip()
        prefill_registro = (request.args.get("prefill_registro", "") or "").strip().upper()
        return {
            "active": any([correction_title, correction_help, prefill_tipo_atto, prefill_registro]),
            "title": correction_title or "Pre-deposito guidato",
            "help": correction_help or "Verifica dati atto, registro, ufficio e allegati prima della generazione della busta.",
            "prefill_tipo_atto": prefill_tipo_atto,
            "prefill_registro": prefill_registro,
            "prefill_oggetto": str(getattr(fascicolo, "oggetto", "") or fascicolo.titolo or "").strip(),
        }

    def _tipo_documento_da_nome_portale(nome_file: str) -> TipoDocumento:
        nome = Path(nome_file).name.lower()
        checks = [
            (("sentenza",), TipoDocumento.SENTENZA),
            (("ordinanza",), TipoDocumento.ORDINANZA),
            (("decreto",), TipoDocumento.DECRETO),
            (("verbale", "udienza"), TipoDocumento.VERBALE),
            (("memoria",), TipoDocumento.MEMORIA),
            (("ricorso",), TipoDocumento.RICORSO),
            (("citazione",), TipoDocumento.CITAZIONE),
            (("comparsa",), TipoDocumento.COMPARSA),
            (("procura",), TipoDocumento.PROCURA),
            (("notifica",), TipoDocumento.NOTIFICA),
            (("ricevuta", "accettazione", "consegna", "esito", ".eml", ".msg", ".xml", ".html", ".htm"), TipoDocumento.COMUNICAZIONE),
            (("busta", ".enc", "deposito"), TipoDocumento.DEPOSITO_PCT),
        ]
        for needles, tipo in checks:
            if any(needle in nome for needle in needles):
                return tipo
        if nome.endswith((".pdf", ".p7m")):
            return TipoDocumento.ATTO_GIUDIZIARIO
        return TipoDocumento.ALLEGATO

    def _tipo_documento_da_item_portale(item: dict) -> TipoDocumento:
        nome = str(item.get("nome") or item.get("nome_documento") or "").strip()
        tipo_atto = str(item.get("tipo_atto") or "").strip()
        tipo = str(item.get("tipo") or "").strip()
        testo = _fascicolo_text(nome, tipo_atto, tipo)
        sezione = _sezione_portale_server(item)

        if "procura" in testo:
            return TipoDocumento.PROCURA
        if "sentenza" in testo:
            return TipoDocumento.SENTENZA
        if "ordinanza" in testo:
            return TipoDocumento.ORDINANZA
        if "decreto" in testo:
            return TipoDocumento.DECRETO
        if any(token in testo for token in ("verbale udienza", "verbaleudienza", "verbale", "udienza")):
            return TipoDocumento.VERBALE
        if "memoria" in testo:
            return TipoDocumento.MEMORIA
        if "ricorso" in testo:
            return TipoDocumento.RICORSO
        if "citazione" in testo:
            return TipoDocumento.CITAZIONE
        if "comparsa" in testo:
            return TipoDocumento.COMPARSA
        if "notifica" in testo:
            return TipoDocumento.NOTIFICA
        if any(token in testo for token in ("ricevuta", "accettazione", "consegna", "esito", "comunicazione", "pec")):
            return TipoDocumento.COMUNICAZIONE
        if sezione == "comunicazioni":
            return TipoDocumento.COMUNICAZIONE
        if sezione == "udienze":
            return TipoDocumento.VERBALE
        if sezione == "istanze":
            return TipoDocumento.ALLEGATO

        return _tipo_documento_da_nome_portale(nome)

    def _espandi_file_importato_portale(
        nome_file: str,
        contenuto: bytes,
        data_documento: str = "",
        origine: str = "",
    ) -> list[dict]:
        nome_sicuro = Path(nome_file).name or "documento"
        data_fallback = data_documento or date.today().isoformat()
        if nome_sicuro.lower().endswith(".zip"):
            try:
                with _zipfile.ZipFile(io.BytesIO(contenuto)) as archivio:
                    estratti = []
                    for info in archivio.infolist():
                        if info.is_dir():
                            continue
                        if info.filename.startswith("__MACOSX/"):
                            continue
                        nome_interno = Path(info.filename).name
                        if not nome_interno or nome_interno.lower() in {".ds_store", "thumbs.db"}:
                            continue
                        payload = archivio.read(info)
                        if not payload:
                            continue
                        data_info = data_fallback
                        try:
                            anno, mese, giorno = info.date_time[:3]
                            if anno >= 1980:
                                data_info = date(anno, mese, giorno).isoformat()
                        except Exception:
                            pass
                        estratti.append({
                            "nome": nome_interno,
                            "contenuto": payload,
                            "data_documento": data_info,
                            "origine": f"{origine or nome_sicuro}:{info.filename}",
                        })
                    if estratti:
                        return estratti
            except (_zipfile.BadZipFile, RuntimeError, ValueError):
                pass
        return [{
            "nome": nome_sicuro,
            "contenuto": contenuto,
            "data_documento": data_fallback,
            "origine": origine or nome_sicuro,
        }]

    def _salva_documento_fascicolo(
        gf: GestioneFascicoli,
        id_fasc: str,
        nome_file: str,
        raw: bytes,
        tipo_doc: TipoDocumento,
        note: str = "",
        tags: list[str] | None = None,
        data_documento: str = "",
        firmato: bool = False,
        caricato_da: str = "",
        fonte_documento: str = "",
        nome_originale: str = "",
        nome_portale: str = "",
        classificazione_portale: str = "",
        tipo_atto_portale: str = "",
        servizio_portale: str = "",
        mittente_portale: str = "",
        data_deposito_portale: str = "",
        id_documento_portale: str = "",
        id_cat_portale: str = "",
        id_repeatto_portale: str = "",
        msg_id_portale: str = "",
    ) -> Documento:
        contenuto = _encrypt_doc(raw)
        doc = gf.aggiungi_documento(
            id_fasc,
            nome_file=nome_file,
            tipo=tipo_doc,
            contenuto=contenuto,
            note=note,
            tags=tags,
            data_documento=data_documento,
            firmato=firmato,
            caricato_da=caricato_da,
            fonte_documento=fonte_documento,
            nome_originale=nome_originale,
            nome_portale=nome_portale,
            classificazione_portale=classificazione_portale,
            tipo_atto_portale=tipo_atto_portale,
            servizio_portale=servizio_portale,
            mittente_portale=mittente_portale,
            data_deposito_portale=data_deposito_portale,
            id_documento_portale=id_documento_portale,
            id_cat_portale=id_cat_portale,
            id_repeatto_portale=id_repeatto_portale,
            msg_id_portale=msg_id_portale,
        )
        # ── Conversione automatica PDF → PDF/A-2B (D.M. 44/2011 art. 12) ──
        # Se il file è un PDF non firmato, lo converte in PDF/A tramite
        # Ghostscript per garantire conformità al deposito telematico.
        percorso_doc = str(gf.percorso_documento(id_fasc, doc.id))
        if nome_file.lower().endswith(".pdf") and not firmato:
            try:
                from pct.validazione import verifica_pdfa, converti_pdfa
                esito_pdfa = verifica_pdfa(percorso_doc)
                if esito_pdfa.get("conforme") is False:
                    conv = converti_pdfa(percorso_doc)
                    if conv.get("ok"):
                        app.logger.info(
                            "PDF/A auto-conversione: %s → PDF/A-2B (%s)",
                            nome_file, conv.get("messaggio", ""),
                        )
                    else:
                        app.logger.warning(
                            "PDF/A auto-conversione fallita per %s: %s",
                            nome_file, conv.get("messaggio", ""),
                        )
            except Exception as exc:
                app.logger.warning("PDF/A auto-conversione errore per %s: %s", nome_file, exc)
        _accoda_ocr(
            percorso=percorso_doc,
            hash_sha256=doc.hash_sha256,
            id_fasc=id_fasc,
            id_doc=doc.id,
            nome_doc=nome_file,
            tipo_doc=tipo_doc.value,
            index_path=app.config["SEARCH_INDEX"],
        )
        return doc

    def _leggi_staging_documenti_portale(fasc: Fascicolo) -> tuple[list[dict], Path]:
        cartella = _pst_import_dir_for_fascicolo(fasc)
        items: list[dict] = []
        if not cartella.exists():
            return items, cartella
        for path in sorted(cartella.rglob("*")):
            if not path.is_file():
                continue
            if path.name.lower() in {".ds_store", "thumbs.db"}:
                continue
            payload = path.read_bytes()
            if not payload:
                continue
            data_doc = date.fromtimestamp(path.stat().st_mtime).isoformat()
            origine = str(path.relative_to(cartella)).replace("\\", "/")
            items.extend(_espandi_file_importato_portale(
                nome_file=path.name,
                contenuto=payload,
                data_documento=data_doc,
                origine=origine,
            ))
        return items, cartella

    def _archivia_staging_documenti_portale(cartella: Path) -> str:
        if not cartella.exists():
            return ""
        has_files = any(path.is_file() for path in cartella.rglob("*"))
        if not has_files:
            return ""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destinazione = cartella.parent / "_importati" / f"{cartella.name}_{stamp}"
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(cartella), str(destinazione))
        cartella.mkdir(parents=True, exist_ok=True)
        return str(destinazione)

    def _slug_portale_chunk(value: str, fallback: str = "n.d.") -> str:
        testo = str(value or "").strip()
        if not testo:
            return fallback
        testo = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode("ascii")
        testo = re.sub(r"[^a-zA-Z0-9._-]+", "-", testo).strip("-._").lower()
        return testo or fallback

    def _sezione_portale_server(item: dict) -> str:
        tipo_atto = str(item.get("tipo_atto") or item.get("tipo") or "").lower()
        nome = str(item.get("nome") or item.get("nome_documento") or "").lower()
        testo = " ".join(part for part in (tipo_atto, nome) if part)
        if "istanza" in testo:
            return "istanze"
        if any(token in testo for token in ("verbaleudienza", "verbale udienza", "udienza", "verbale")):
            return "udienze"
        if any(token in testo for token in ("ordinanza", "decreto", "sentenza", "provvedimento")):
            return "provvedimenti"
        if (
            nome.endswith(".eml")
            or nome.endswith(".msg")
            or nome.endswith(".xml")
            or "ricevuta" in nome
            or "esito" in nome
            or "comunicazione" in testo
            or "pec" in testo
        ):
            return "comunicazioni"
        return "atti"

    def _scrivi_file_univoco(destinazione: Path, payload: bytes) -> Path:
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        candidato = destinazione
        indice = 1
        while candidato.exists():
            candidato = destinazione.with_name(
                f"{destinazione.stem}_{indice}{destinazione.suffix}"
            )
            indice += 1
        candidato.write_bytes(payload)
        return candidato

    def _salva_albero_originale_documenti_portale(fasc: Fascicolo, items: list[dict]) -> str:
        if not items:
            return ""
        base_root = _pst_import_dir_for_fascicolo(fasc).parent / "_alberi_originali" / fasc.id
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = base_root / stamp
        scritti = 0
        for idx, item in enumerate(items, start=1):
            nome = Path(str(item.get("nome") or f"documento_{idx}")).name or f"documento_{idx}"
            payload = item.get("contenuto", b"")
            if not payload:
                continue
            sezione = _slug_portale_chunk(_sezione_portale_server(item), "atti")
            deposito_src = (
                str(item.get("id_deposito_pct") or "").strip()
                or str(item.get("id_deposito_esterno") or "").strip()
                or "_".join(
                    part for part in (
                        str(item.get("data_documento") or "").strip(),
                        str(item.get("tipo_atto") or "").strip(),
                    ) if part
                )
            )
            deposito = _slug_portale_chunk(deposito_src, "senza_deposito")
            tipo = _slug_portale_chunk(str(item.get("tipo_atto") or Path(nome).stem), "documento")
            _scrivi_file_univoco(root / sezione / f"{deposito}_{tipo}" / nome, payload)
            scritti += 1
        return str(root) if scritti else ""

    def _decode_portale_downloaded_items(files: list[dict]) -> list[dict]:
        items: list[dict] = []
        for file_item in files or []:
            nome = str((file_item or {}).get("nome") or "").strip()
            contenuto_b64 = str((file_item or {}).get("contenuto_b64") or "").strip()
            if not nome or not contenuto_b64:
                continue
            try:
                payload = base64.b64decode(contenuto_b64)
            except Exception:
                continue
            espansi = _espandi_file_importato_portale(
                nome_file=nome,
                contenuto=payload,
                data_documento=str((file_item or {}).get("data_documento") or date.today().isoformat()),
                origine=str((file_item or {}).get("origine") or f"local-signer:{nome}"),
            )
            for item in espansi:
                item["id_deposito_esterno"] = str((file_item or {}).get("id_deposito_esterno") or "").strip()
                item["id_deposito_pct"] = str((file_item or {}).get("id_deposito_pct") or "").strip()
                item["id_documento_portale"] = str((file_item or {}).get("id_documento_portale") or "").strip()
                item["tipo_atto"] = str((file_item or {}).get("tipo_atto") or "").strip()
                item["tipo"] = str((file_item or {}).get("tipo") or "").strip()
                item["mittente"] = str((file_item or {}).get("mittente") or "").strip()
                item["servizio_portale"] = str((file_item or {}).get("servizio_portale") or "").strip()
                item["id_cat"] = str((file_item or {}).get("id_cat") or "").strip()
                item["id_repeatto"] = str((file_item or {}).get("id_repeatto") or "").strip()
                item["msg_id"] = str((file_item or {}).get("msg_id") or "").strip()
                item["content_type"] = str((file_item or {}).get("content_type") or "").strip()
                item["nome_file_originale"] = str((file_item or {}).get("nome_file_originale") or "").strip()
                original_documento_portale = bool((file_item or {}).get("original_documento_portale", True))
                item["original_documento_portale"] = original_documento_portale
                item["modalita_documento_portale"] = (
                    str((file_item or {}).get("modalita_documento_portale") or "").strip()
                    or ("originale" if original_documento_portale else "copia")
                )
            items.extend(espansi)
        return items

    def _normalizza_nome_match_portale(nome_file: str) -> str:
        testo = Path(str(nome_file or "")).name.strip().lower()
        if not testo:
            return ""
        testo = re.sub(r"\s+\(\d+\)(?=(\.[^.]+)+$|$)", "", testo)
        while True:
            cambiato = False
            for suffix in (".p7m", ".pdf", ".txt", ".eml", ".msg", ".xml", ".html", ".htm", ".zip"):
                if testo.endswith(suffix):
                    testo = testo[: -len(suffix)]
                    cambiato = True
            if not cambiato:
                break
        testo = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^a-z0-9]+", "", testo)

    def _nome_preview_documento(nome_file: str) -> str:
        nome = Path(str(nome_file or "")).name.strip()
        if nome.lower().endswith(".p7m"):
            nome = nome[:-4]
        return nome

    def _mime_preview_documento(nome_file: str, payload: bytes | None = None) -> tuple[str, str] | None:
        nome_preview = _nome_preview_documento(nome_file)
        lower = nome_preview.lower()

        if payload is not None:
            if payload.startswith(b"%PDF"):
                return "application/pdf", nome_preview or "documento.pdf"
            if payload.startswith(b"\xff\xd8\xff"):
                return "image/jpeg", nome_preview or "documento.jpg"
            if payload.startswith(b"\x89PNG\r\n\x1a\n"):
                return "image/png", nome_preview or "documento.png"
            if payload.startswith((b"GIF87a", b"GIF89a")):
                return "image/gif", nome_preview or "documento.gif"
            return None

        if lower.endswith(".pdf"):
            return "application/pdf", nome_preview
        if lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg", nome_preview
        if lower.endswith(".png"):
            return "image/png", nome_preview
        if lower.endswith(".gif"):
            return "image/gif", nome_preview
        return None

    def _estrai_contenuto_p7m_per_preview(data: bytes) -> bytes | None:
        try:
            from asn1crypto import cms
        except Exception:
            return None

        try:
            content_info = cms.ContentInfo.load(data)
            if content_info["content_type"].native != "signed_data":
                return None
            signed_data = content_info["content"]
            encap = signed_data["encap_content_info"]
            contenuto = encap["content"]
            if contenuto is None:
                return None
            native = getattr(contenuto, "native", None)
            if isinstance(native, bytes):
                return native
            if isinstance(contenuto, bytes):
                return contenuto
            if native is not None:
                try:
                    return bytes(native)
                except Exception:
                    return None
        except Exception:
            return None
        return None

    def _payload_preview_da_versioni_documento(gf, doc: Documento) -> bytes | None:
        nome_preview = _nome_preview_documento(doc.nome)
        for versione in reversed(doc.versioni or []):
            try:
                percorso = gf.documents_dir / str(versione.percorso or "")
                if not percorso.exists():
                    continue
                contenuto = _decrypt_doc(percorso.read_bytes())
                if _mime_preview_documento(nome_preview, contenuto):
                    return contenuto
            except Exception:
                continue
        return None

    def _firma_payload_corrente_o_sibling(percorso: Path, nome_file: str, data_corrente: bytes) -> bytes:
        """Restituisce il payload firmato reale (.p7m) anche nei flussi legacy PKCS#11."""
        nome = str(nome_file or "").strip().lower()
        if not nome.endswith(".p7m"):
            return data_corrente
        try:
            from pct.firma import _is_cades as _is_cades_payload
        except Exception:
            _is_cades_payload = None
        try:
            if _is_cades_payload and _is_cades_payload(data_corrente):
                return data_corrente
        except Exception:
            pass
        sibling = Path(str(percorso) + ".p7m")
        if sibling.exists():
            try:
                return _decrypt_doc(sibling.read_bytes())
            except Exception:
                return data_corrente
        return data_corrente

    def _luogo_timbro_firma_visibile() -> str:
        from visible_signature import resolve_visible_signature_place

        try:
            studio_cfg = get_config_studio().config.studio
        except Exception:
            studio_cfg = None
        return resolve_visible_signature_place(
            city=getattr(studio_cfg, "city", "") if studio_cfg else "",
            province=getattr(studio_cfg, "province", "") if studio_cfg else "",
            address=getattr(studio_cfg, "indirizzo", "") if studio_cfg else "",
        )

    def _formatta_data_firma_visibile(valore: str) -> str:
        from visible_signature import format_visible_signature_datetime

        return format_visible_signature_datetime(valore)

    def _normalizza_modalita_firma_visibile(valore: str) -> str:
        from visible_signature import normalize_visible_signature_mode

        return normalize_visible_signature_mode(valore)

    def _testo_timbro_firma_visibile(firme: list[dict]) -> str:
        from visible_signature import build_visible_signature_text

        if not firme:
            return ""
        firma = (firme or [{}])[0] or {}
        return build_visible_signature_text(
            intestatario=str(firma.get("intestatario") or firma.get("cn") or "").strip(),
            data_firma=firma.get("data_firma"),
            luogo=_luogo_timbro_firma_visibile(),
        )

    def _applica_timbro_firma_visibile(pdf_data: bytes, firme: list[dict]) -> bytes:
        from visible_signature import (
            apply_visible_signature_stamp_from_firme,
            has_visible_signature_stamp,
        )

        try:
            studio_cfg = get_config_studio().config.studio
        except Exception:
            studio_cfg = None

        stamped = apply_visible_signature_stamp_from_firme(
            pdf_data,
            firme,
            city=getattr(studio_cfg, "city", "") if studio_cfg else "",
            address=getattr(studio_cfg, "indirizzo", "") if studio_cfg else "",
        )
        if stamped != pdf_data or has_visible_signature_stamp(pdf_data):
            return stamped
        if not pdf_data.startswith(b"%PDF"):
            return pdf_data
        testo = _testo_timbro_firma_visibile(firme)
        if not testo:
            return pdf_data
        app.logger.warning("Impossibile applicare il timbro firma visibile: fallback non disponibile")
        return pdf_data

    def _catalogo_documenti_portale_fascicolo(fasc: Fascicolo) -> list[dict]:
        documenti_locali_per_deposito: dict[str, dict[str, list[Documento]]] = {}
        for doc in fasc.documenti or []:
            dep_id = str(getattr(doc, "id_deposito_pct", "") or "").strip()
            if not dep_id:
                continue
            key = _normalizza_nome_match_portale(str(getattr(doc, "nome", "") or ""))
            if not key:
                continue
            documenti_locali_per_deposito.setdefault(dep_id, {}).setdefault(key, []).append(doc)

        catalogo: list[dict] = []
        for dep in fasc.depositi_pct or []:
            imported_docs = documenti_locali_per_deposito.get(dep.id, {})
            for pdoc in getattr(dep, "documenti_portale", []) or []:
                nome = str((pdoc or {}).get("nome") or "").strip()
                key = _normalizza_nome_match_portale(nome)
                if not nome or not key:
                    continue
                docs_locali = list(imported_docs.get(key, []))
                docs_locali.sort(
                    key=lambda row: (
                        getattr(row, "data_caricamento", "") or "",
                        getattr(row, "nome", "") or "",
                    ),
                    reverse=True,
                )
                doc_locale = docs_locali[0] if docs_locali else None
                preview_info = _mime_preview_documento(getattr(doc_locale, "nome", "") or nome)
                catalogo.append({
                    "id_deposito_pct": dep.id,
                    "id_deposito_esterno": str(getattr(dep, "id_deposito_esterno", "") or "").strip(),
                    "tipo_atto": str((pdoc or {}).get("tipo_atto") or getattr(dep, "tipo_atto", "") or "").strip(),
                    "id_documento_portale": str((pdoc or {}).get("id_documento") or "").strip(),
                    "id_cat": str((pdoc or {}).get("id_cat") or "").strip(),
                    "id_repeatto": str((pdoc or {}).get("id_repeatto") or "").strip(),
                    "msg_id": str((pdoc or {}).get("msg_id") or "").strip(),
                    "data_documento": str((pdoc or {}).get("data_deposito") or "").strip(),
                    "data_deposito": str((pdoc or {}).get("data_deposito") or "").strip(),
                    "nome": nome,
                    "tipo": str((pdoc or {}).get("tipo") or "Documento").strip(),
                    "mittente": str((pdoc or {}).get("mittente") or "").strip(),
                    "dimensione_bytes": int((pdoc or {}).get("dimensione_bytes") or 0),
                    "disponibile": bool((pdoc or {}).get("disponibile", True)),
                    "key": key,
                    "gia_importato": bool(docs_locali),
                    "local_doc_id": getattr(doc_locale, "id", "") if doc_locale else "",
                    "local_doc_nome": getattr(doc_locale, "nome", "") if doc_locale else "",
                    "local_doc_firmato": bool(getattr(doc_locale, "firmato_digitalmente", False)) if doc_locale else False,
                    "local_doc_previewabile": bool(preview_info),
                })
        return catalogo

    def _gruppa_catalogo_documenti_portale(catalogo: list[dict]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for row in catalogo or []:
            dep_id = str(row.get("id_deposito_pct") or "").strip()
            if not dep_id:
                data_key = str(row.get("data_deposito") or "").strip()
                mittente_key = str(row.get("mittente") or "").strip()
                dep_id = f"__{data_key}__{mittente_key}"
            if not dep_id:
                continue
            grouped.setdefault(dep_id, []).append(row)
        for dep_id, items in grouped.items():
            items.sort(
                key=lambda item: (
                    item.get("data_deposito") or "",
                    item.get("nome") or "",
                    item.get("id_documento_portale") or "",
                ),
                reverse=True,
            )
            grouped[dep_id] = items
        return grouped

    def _match_catalogo_documento_portale(
        fasc: Fascicolo,
        item: dict,
        catalogo: list[dict],
    ) -> dict | None:
        dep_ids_validi = {dep.id for dep in (fasc.depositi_pct or [])}
        dep_pct = str(item.get("id_deposito_pct") or "").strip()
        if dep_pct and dep_pct in dep_ids_validi:
            return next((row for row in catalogo if row["id_deposito_pct"] == dep_pct), None)

        doc_portale_id = str(item.get("id_documento_portale") or "").strip()
        if doc_portale_id:
            row = next((entry for entry in catalogo if entry["id_documento_portale"] == doc_portale_id), None)
            if row:
                return row

        dep_esterno = str(item.get("id_deposito_esterno") or item.get("id_deposito") or "").strip()
        if dep_esterno:
            by_dep = [entry for entry in catalogo if entry["id_deposito_esterno"] == dep_esterno]
            if len(by_dep) == 1:
                return by_dep[0]
            item_key = _normalizza_nome_match_portale(str(item.get("nome") or ""))
            if item_key:
                exact = [entry for entry in by_dep if entry["key"] == item_key]
                if len(exact) == 1:
                    return exact[0]

        item_key = _normalizza_nome_match_portale(str(item.get("nome") or ""))
        if len(item_key) < 8:
            return None
        exact = [entry for entry in catalogo if entry["key"] == item_key]
        if len(exact) == 1:
            return exact[0]
        return None

    def _documento_portale_payload_da_item(
        item: dict,
        *,
        id_deposito_esterno: str,
        doc_locale: Documento | None = None,
    ) -> dict[str, object]:
        return {
            "id_documento": str(item.get("id_documento_portale") or item.get("id_documento") or item.get("id_cat") or "").strip(),
            "id_cat": str(item.get("id_cat") or item.get("id_documento_portale") or "").strip(),
            "id_repeatto": str(item.get("id_repeatto") or "").strip(),
            "msg_id": str(item.get("msg_id") or "").strip(),
            "nome": str(item.get("nome") or item.get("nome_file_originale") or "").strip(),
            "tipo": str(item.get("tipo") or "").strip(),
            "data_deposito": str(item.get("data_documento") or item.get("data_deposito") or "").strip(),
            "mittente": str(item.get("mittente") or "").strip(),
            "dimensione_bytes": int((doc_locale.dimensione_bytes if doc_locale else 0) or 0),
            "disponibile": True,
            "id_deposito": id_deposito_esterno,
            "tipo_atto": str(item.get("tipo_atto") or item.get("tipo") or "").strip(),
        }

    def _importa_documenti_portale_items(
        *,
        gf: GestioneFascicoli,
        fasc: Fascicolo,
        items: list[dict],
        note_importazione: str = "",
        usa_staging: bool = False,
        staging_dir: Path | None = None,
    ) -> dict:
        fonte = _portale_ufficiale_label(fasc)
        u = g.utente_corrente
        documenti_creati: list[dict] = []

        # Indice dei nomi normalizzati già presenti nel fascicolo (dedup import ripetuto)
        nomi_esistenti: dict[str, Documento] = {
            _normalizza_nome_match_portale(d.nome): d
            for d in fasc.documenti
            if d.nome
        }

        for item in items:
            nome = item.get("nome", "").strip()
            payload = item.get("contenuto", b"")
            if not nome or not payload:
                continue
            # Deduplicazione: se il file (per nome normalizzato) è già nel fascicolo,
            # riutilizza il documento esistente senza crearne un duplicato.
            nome_norm = _normalizza_nome_match_portale(nome)
            doc_esistente = nomi_esistenti.get(nome_norm)
            if doc_esistente:
                documenti_creati.append({"doc": doc_esistente, "item": item})
                continue
            tipo_doc = _tipo_documento_da_item_portale(item)
            note_doc = [f"Importato da {fonte} il {date.today().isoformat()}"]
            if note_importazione:
                note_doc.append(note_importazione)
            origine = (item.get("origine", "") or "").strip()
            if origine and origine != nome:
                note_doc.append(f"Origine: {origine}")
            tipo_atto = str(item.get("tipo_atto") or item.get("tipo") or "").strip()
            if tipo_atto:
                note_doc.append(f"Tipo atto portale: {tipo_atto}")
            doc = _salva_documento_fascicolo(
                gf=gf,
                id_fasc=fasc.id,
                nome_file=nome,
                raw=payload,
                tipo_doc=tipo_doc,
                note=" | ".join(note_doc),
                data_documento=item.get("data_documento", "") or date.today().isoformat(),
                firmato=nome.lower().endswith(".p7m"),
                caricato_da=u.username if u else "",
                fonte_documento="PORTALE_TELEMATICO",
                nome_originale=str(item.get("nome_file_originale") or item.get("origine") or nome).strip(),
                nome_portale=str(item.get("nome") or item.get("nome_documento") or nome).strip(),
                classificazione_portale=str(item.get("tipo") or "").strip(),
                tipo_atto_portale=str(item.get("tipo_atto") or item.get("tipo") or "").strip(),
                servizio_portale=str(item.get("servizio_portale") or "").strip(),
                mittente_portale=str(item.get("mittente") or "").strip(),
                data_deposito_portale=str(item.get("data_documento") or "").strip(),
                id_documento_portale=str(item.get("id_documento_portale") or item.get("id_documento") or "").strip(),
                id_cat_portale=str(item.get("id_cat") or "").strip(),
                id_repeatto_portale=str(item.get("id_repeatto") or "").strip(),
                msg_id_portale=str(item.get("msg_id") or "").strip(),
            )
            documenti_creati.append({"doc": doc, "item": item})
            nomi_esistenti[nome_norm] = doc

        if not documenti_creati:
            raise ValueError("I file selezionati non contengono documenti importabili.")

        catalogo = _catalogo_documenti_portale_fascicolo(fasc)
        docs_per_deposito: dict[str, list[str]] = {}
        documenti_sfusi: list[dict] = []
        for entry in documenti_creati:
            match = _match_catalogo_documento_portale(fasc, entry["item"], catalogo)
            if match and match["id_deposito_pct"]:
                docs_per_deposito.setdefault(match["id_deposito_pct"], []).append(entry["doc"].id)
            else:
                documenti_sfusi.append(entry)

        depositi_agganciati: list[str] = []
        for dep_id, doc_ids in docs_per_deposito.items():
            dep = next((row for row in fasc.depositi_pct if row.id == dep_id), None)
            if not dep:
                for doc_id in doc_ids:
                    entry = next((row for row in documenti_creati if row["doc"].id == doc_id), None)
                    if entry:
                        documenti_sfusi.append(entry)
                continue
            descrizione_link = (
                f"{len(doc_ids)} file ufficiali acquisiti localmente da {fonte}."
                + (f" {note_importazione}" if note_importazione else "")
            ).strip()
            gf.collega_documenti_a_deposito_portale(
                fasc.id,
                dep_id,
                doc_ids,
                note=descrizione_link,
                registrato_da=u.username if u else "",
            )
            depositi_agganciati.append(dep_id)

        deposito_generico = None
        if documenti_sfusi:
            pec_tribunale = ""
            if fasc.tribunale:
                try:
                    uff = ClientReGINde().cerca_ufficio_giudiziario(fasc.tribunale)
                    pec_tribunale = uff.pec if uff else ""
                except Exception:
                    pec_tribunale = ""

            depositi_sfusi: dict[str, dict[str, object]] = {}
            documenti_senza_catalogo: list[dict] = []
            for entry in documenti_sfusi:
                item = dict(entry["item"] or {})
                dep_key = (
                    str(item.get("id_deposito_esterno") or item.get("id_deposito") or "").strip()
                    or (
                        f"__{str(item.get('data_documento') or item.get('data_deposito') or '').strip()}__"
                        f"{str(item.get('mittente') or item.get('tipo_atto') or item.get('tipo') or '').strip()}"
                    )
                )
                has_official_metadata = any(
                    str(item.get(field_name) or "").strip()
                    for field_name in ("id_documento_portale", "id_documento", "id_cat", "msg_id", "tipo_atto", "tipo", "mittente")
                )
                if not dep_key or not has_official_metadata:
                    documenti_senza_catalogo.append(entry)
                    continue
                group = depositi_sfusi.setdefault(
                    dep_key,
                    {
                        "tipo_atto": str(item.get("tipo_atto") or item.get("tipo") or _tipo_lotto_portale(fasc)).strip(),
                        "data_deposito": str(item.get("data_documento") or item.get("data_deposito") or "").strip(),
                        "mittente": str(item.get("mittente") or "").strip(),
                        "documenti_portale": [],
                        "doc_ids": [],
                    },
                )
                if not group["tipo_atto"] and str(item.get("tipo_atto") or item.get("tipo") or "").strip():
                    group["tipo_atto"] = str(item.get("tipo_atto") or item.get("tipo") or "").strip()
                if not group["data_deposito"] and str(item.get("data_documento") or item.get("data_deposito") or "").strip():
                    group["data_deposito"] = str(item.get("data_documento") or item.get("data_deposito") or "").strip()
                if not group["mittente"] and str(item.get("mittente") or "").strip():
                    group["mittente"] = str(item.get("mittente") or "").strip()
                group["documenti_portale"].append(
                    _documento_portale_payload_da_item(
                        item,
                        id_deposito_esterno=dep_key,
                        doc_locale=entry["doc"],
                    )
                )
                group["doc_ids"].append(entry["doc"].id)

            for dep_key, payload in depositi_sfusi.items():
                documenti_portale = list(payload.get("documenti_portale") or [])
                doc_ids = list(payload.get("doc_ids") or [])
                if not documenti_portale or not doc_ids:
                    continue
                principale = next(
                    (
                        row["nome"]
                        for row in documenti_portale
                        if str(row.get("tipo_atto") or "").strip()
                    ),
                    str(documenti_portale[0].get("nome") or ""),
                )
                descrizione_link = (
                    f"{len(doc_ids)} file ufficiali acquisiti localmente da {fonte}."
                    + (f" {note_importazione}" if note_importazione else "")
                ).strip()
                deposito = gf.sincronizza_deposito_portale(
                    fasc.id,
                    fonte=fonte,
                    id_deposito_esterno=dep_key,
                    tipo_atto=str(payload.get("tipo_atto") or _tipo_lotto_portale(fasc)).strip(),
                    data_deposito=str(payload.get("data_deposito") or "").strip(),
                    mittente=str(payload.get("mittente") or "").strip(),
                    documenti_portale=documenti_portale,
                    registrato_da=u.username if u else "",
                    note=descrizione_link,
                    nome_atto_principale=principale,
                    stato="IMPORTATO_DA_PORTALE",
                    servizio_portale=str(documenti_portale[0].get("servizio_portale") or "DocumentiFascicolo"),
                )
                gf.collega_documenti_a_deposito_portale(
                    fasc.id,
                    deposito.id,
                    doc_ids,
                    note=descrizione_link,
                    registrato_da=u.username if u else "",
                )
                depositi_agganciati.append(deposito.id)

            if documenti_senza_catalogo:
                docs_creati_index = {entry["doc"].id: entry["doc"] for entry in documenti_senza_catalogo}
                doc_ids_generici = list(docs_creati_index.keys())
                principali = [
                    docs_creati_index[doc_id].nome
                    for doc_id in doc_ids_generici
                    if docs_creati_index[doc_id].tipo
                    in {
                        TipoDocumento.ATTO_GIUDIZIARIO,
                        TipoDocumento.RICORSO,
                        TipoDocumento.CITAZIONE,
                        TipoDocumento.COMPARSA,
                        TipoDocumento.MEMORIA,
                        TipoDocumento.SENTENZA,
                        TipoDocumento.ORDINANZA,
                        TipoDocumento.DECRETO,
                    }
                ]
                principale = principali[0] if principali else docs_creati_index[doc_ids_generici[0]].nome
                descrizione_lotto = (
                    f"{len(doc_ids_generici)} documenti ufficiali acquisiti da {fonte}."
                    + (f" {note_importazione}" if note_importazione else "")
                ).strip()
                deposito_generico = gf.registra_import_documenti_portale(
                    id_fasc=fasc.id,
                    fonte=fonte,
                    documenti_ids=doc_ids_generici,
                    tipo_atto=_tipo_lotto_portale(fasc),
                    note=descrizione_lotto,
                    registrato_da=u.username if u else "",
                    pec_destinatario=pec_tribunale,
                    nome_atto_principale=principale,
                )

        staging_archived = ""
        if usa_staging and staging_dir is not None:
            staging_archived = _archivia_staging_documenti_portale(staging_dir)

        audit(
            "fascicoli.documento.importa_portale",
            "fascicolo",
            fasc.id,
            dettagli=(
                f"{fonte}: {len(documenti_creati)} file — "
                f"{len(depositi_agganciati)} depositi agganciati"
                + (f", lotto {deposito_generico.id}" if deposito_generico else "")
            ),
        )
        _sync.pubblica("modifica", "fascicoli", fasc.id, utente=u.username if u else "")

        return {
            "fonte": fonte,
            "documenti_importati": len(documenti_creati),
            "depositi_agganciati": depositi_agganciati,
            "lotto_generico": deposito_generico.id if deposito_generico else "",
            "staging_archived": staging_archived,
        }


    return {
        "encrypt_doc": _encrypt_doc,
        "decrypt_doc": _decrypt_doc,
        "run_deposito_validation": _run_deposito_validation,
        "portale_ufficiale_label": _portale_ufficiale_label,
        "infer_canale_deposito": _infer_canale_deposito,
        "resolve_ufficio_destinatario": _resolve_ufficio_destinatario,
        "pst_import_dir_for_fascicolo": _pst_import_dir_for_fascicolo,
        "pst_import_pending_count": _pst_import_pending_count,
        "build_fascicolo_workspace": _build_fascicolo_workspace,
        "fascicolo_form_correction_context": _fascicolo_form_correction_context,
        "deposito_correction_context": _deposito_correction_context,
        "tipo_documento_da_nome_portale": _tipo_documento_da_nome_portale,
        "tipo_documento_da_item_portale": _tipo_documento_da_item_portale,
        "espandi_file_importato_portale": _espandi_file_importato_portale,
        "salva_documento_fascicolo": _salva_documento_fascicolo,
        "leggi_staging_documenti_portale": _leggi_staging_documenti_portale,
        "archivia_staging_documenti_portale": _archivia_staging_documenti_portale,
        "salva_albero_originale_documenti_portale": _salva_albero_originale_documenti_portale,
        "decode_portale_downloaded_items": _decode_portale_downloaded_items,
        "normalizza_nome_match_portale": _normalizza_nome_match_portale,
        "nome_preview_documento": _nome_preview_documento,
        "mime_preview_documento": _mime_preview_documento,
        "estrai_contenuto_p7m_per_preview": _estrai_contenuto_p7m_per_preview,
        "payload_preview_da_versioni_documento": _payload_preview_da_versioni_documento,
        "firma_payload_corrente_o_sibling": _firma_payload_corrente_o_sibling,
        "luogo_timbro_firma_visibile": _luogo_timbro_firma_visibile,
        "normalizza_modalita_firma_visibile": _normalizza_modalita_firma_visibile,
        "applica_timbro_firma_visibile": _applica_timbro_firma_visibile,
        "catalogo_documenti_portale_fascicolo": _catalogo_documenti_portale_fascicolo,
        "gruppa_catalogo_documenti_portale": _gruppa_catalogo_documenti_portale,
        "importa_documenti_portale_items": _importa_documenti_portale_items,
        "build_responsabile_conformita_fascicolo": _build_responsabile_conformita_fascicolo,
        "fascicolo_text": _fascicolo_text,
    }
