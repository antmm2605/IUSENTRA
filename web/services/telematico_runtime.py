"""Runtime telematico e portali estratto da web.app."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from flask import Flask, g, url_for

from pct.fascicoli import Fascicolo, TipoAttivita, stato_fascicolo_da_descrizione_portale
from pct.scadenziario import TipoTermine


def build_telematico_runtime(
    app: Flask,
    *,
    cfg_data_path,
    get_config_studio,
    get_pdp_penale,
    get_telematico,
    get_fascicoli,
    get_clienti,
    get_soggetti,
    get_scadenziario,
    audit,
    sync_pubblica,
    normalizza_nome_match_portale,
    tipo_documento_da_item_portale,
    salva_documento_fascicolo,
    salva_albero_originale_documenti_portale,
    catalogo_documenti_portale_fascicolo,
    gruppa_catalogo_documenti_portale,
    decode_portale_downloaded_items,
    importa_documenti_portale_items,
    portale_ufficiale_label,
    ensure_pdp_penale_case_after_import,
) -> dict[str, Any]:
    _normalizza_nome_match_portale = normalizza_nome_match_portale
    _tipo_documento_da_item_portale = tipo_documento_da_item_portale
    _salva_documento_fascicolo = salva_documento_fascicolo
    _salva_albero_originale_documenti_portale = salva_albero_originale_documenti_portale
    _catalogo_documenti_portale_fascicolo = catalogo_documenti_portale_fascicolo
    _gruppa_catalogo_documenti_portale = gruppa_catalogo_documenti_portale
    _decode_portale_downloaded_items = decode_portale_downloaded_items
    _importa_documenti_portale_items = importa_documenti_portale_items
    _portale_ufficiale_label = portale_ufficiale_label
    _ensure_pdp_penale_case_after_import = ensure_pdp_penale_case_after_import
    _cfg_data_path = cfg_data_path
    def _polis_auth_mode() -> str:
        """
        Restituisce la modalità di autenticazione PST:
          'reale'  — certificato P12/PEM configurato, SOAP mTLS disponibile
          'pkcs11' — token PKCS#11 locale, autenticazione gestita dal dispositivo
          'demo'   — nessun certificato, modalità demo offline
        """
        # Controllo config studio (impostazioni UI)
        try:
            cfg = get_config_studio().config.firma
            preferito = getattr(cfg, "backend_preferito_normalizzato", "auto")
            fmt = getattr(cfg, "backend_firma_effettivo_safe", "nessuno")
            if fmt == "pkcs11":
                # Token USB: la chiave privata non è esportabile e non è accessibile
                # dal container Linux su Windows → autenticazione PST solo via browser
                return "pkcs11"
            if fmt in ("p12", "pem"):
                return "reale"
            if preferito != "auto":
                return "demo"
        except Exception:
            pass
        # Fallback legacy su variabili d'ambiente solo in assenza di scelta esplicita
        if os.getenv("PCT_FIRMA_P12"):
            return "reale"
        if os.getenv("PCT_FIRMA_CERT") and os.getenv("PCT_FIRMA_KEY"):
            return "reale"
        return "demo"

    def _polis_demo_mode() -> bool:
        """True solo se non esiste alcun canale reale configurato (né P12/PEM né token PKCS#11)."""
        return _polis_auth_mode() == "demo"

    def _portale_usa_local_signer(portale: str) -> bool:
        return (portale or "").strip().lower() in {"pst", "pdp", "pat", "ptt"} and _polis_auth_mode() == "pkcs11"

    def _portale_browser_channel_required(portale: str) -> bool:
        """PAT/PTT sono sempre browser-guided; PDP lo diventa quando manca un backend server reale."""
        portale_norm = (portale or "").strip().lower()
        if portale_norm not in {"pdp", "pat", "ptt"}:
            return False
        if portale_norm in {"pat", "ptt"}:
            return True
        truthy = {"1", "true", "yes", "on"}
        if (
            str(os.getenv("PCT_PORTALI_BROWSER_ONLY", "") or "").strip().lower() in truthy
            or str(os.getenv(f"PCT_{portale_norm.upper()}_BROWSER_ONLY", "") or "").strip().lower() in truthy
        ):
            return True
        return _polis_auth_mode() == "demo"

    def _portale_demo_mode(portale: str) -> bool:
        """I portali browser-guided non devono ricadere nel banner demo del PST."""
        if _portale_browser_channel_required(portale):
            return False
        return _polis_demo_mode()

    def _portale_local_channel_enabled(portale: str) -> bool:
        return _portale_usa_local_signer(portale) or _portale_browser_channel_required(portale)

    def _codice_fiscale_avvocato_portale() -> str:
        try:
            cfg = get_config_studio().config
            return (
                str(getattr(cfg.firma, "cf_avvocato", "") or "").strip().upper()
                or str(getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
            )
        except Exception:
            return ""

    def _polis_cert_preferences() -> dict:
        prefer_cf = ""
        try:
            cfg = get_config_studio().config
            prefer_cf = (
                str(getattr(cfg.firma, "cf_avvocato", "") or "").strip().upper()
                or str(getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
            )
        except Exception:
            prefer_cf = ""

        if not prefer_cf:
            prefer_cf = str(os.getenv("PCT_CF_AVVOCATO", "") or "").strip().upper()

        match = re.search(r"\b([A-Z]{6}[0-9A-Z]{2}[A-Z][0-9A-Z]{2}[A-Z][0-9A-Z]{3}[A-Z])\b", prefer_cf)
        prefer_cf = match.group(1) if match else ""

        return {
            "auto": True,
            "prefer_issuer": "ArubaPEC EU Authentica Certificates CA G1|ArubaPEC EU Qualified Certificates CA G1|ArubaPEC",
            "prefer_subject": "auth|autent|autentica|client|tls|web",
            "prefer_cf": prefer_cf,
        }

    _PORTALE_ACQUISIZIONE_SPECS: dict[str, dict[str, Any]] = {
        "pst": {
            "id": "pst",
            "label": "PST / PolisWeb",
            "title": "Importa pratica da PST",
            "subtitle": "Ricerca, verifica e acquisizione guidata del fascicolo telematico",
            "color": "primary",
            "icon": "bi-building-fill-check",
            "home_endpoint": "polisWeb_home",
            "source_label": "Portale Servizi Telematici",
            "requires_local_signer": True,
            "quick_filters": ["civile", "lavoro", "famiglia", "esecuzioni", "volontaria", "recenti"],
        },
        "pdp": {
            "id": "pdp",
            "label": "PDP Penale",
            "title": "Importa pratica da PDP Penale",
            "subtitle": "Ricerca, verifica e integrazione guidata del fascicolo penale",
            "color": "danger",
            "icon": "bi-shield-exclamation",
            "home_endpoint": "pdp_home",
            "source_label": "Portale Deposito Atti Penale",
            "requires_local_signer": True,
            "quick_filters": ["dibattimento", "gip", "gup", "esecuzioni", "attivi", "recenti"],
            "search_ui": {
                "assistito_label": "Imputato / indagato",
                "assistito_placeholder": "Nome imputato o indagato...",
                "show_controparte": False,
                "show_cf": False,
                "show_oggetto": False,
            },
        },
        "pat": {
            "id": "pat",
            "label": "PAT Amministrativo",
            "title": "Importa pratica da PAT",
            "subtitle": "Acquisizione guidata del fascicolo amministrativo con verifica conflitti",
            "color": "success",
            "icon": "bi-building-check",
            "home_endpoint": "pat_home",
            "source_label": "Processo Amministrativo Telematico",
            "requires_local_signer": True,
            "quick_filters": ["appalti", "urbanistica", "personale", "tributi", "attivi", "recenti"],
        },
        "ptt": {
            "id": "ptt",
            "label": "PTT Tributario",
            "title": "Importa pratica da PTT",
            "subtitle": "Acquisizione guidata del fascicolo tributario con controllo dati e scadenze",
            "color": "warning",
            "icon": "bi-receipt-cutoff",
            "home_endpoint": "sigit_home",
            "source_label": "Processo Tributario Telematico",
            "requires_local_signer": True,
            "quick_filters": ["iva", "irpef", "imu", "registro", "attivi", "recenti"],
        },
    }

    def _spec_portale_acquisizione(portale: str) -> dict[str, Any]:
        spec = _PORTALE_ACQUISIZIONE_SPECS.get((portale or "").strip().lower())
        if not spec:
            raise KeyError(f"Portale non supportato: {portale}")
        return spec

    def _portale_import_log_path() -> Path:
        return Path(_cfg_data_path("PORTALE_IMPORT_LOG_DB"))

    def _read_json_list(path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8") or "[]")
        except Exception:
            return []
        return raw if isinstance(raw, list) else []

    def _write_json_list(path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def _new_import_log_id(portale: str) -> str:
        return f"{portale.upper()}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(3).hex().upper()}"

    def _append_portale_import_log(entry: dict[str, Any]) -> str:
        path = _portale_import_log_path()
        rows = _read_json_list(path)
        payload = dict(entry)
        log_id = str(payload.get("id") or _new_import_log_id(str(payload.get("portale") or "PORT")))
        payload["id"] = log_id
        payload.setdefault("created_at", datetime.now().isoformat())
        rows.append(payload)
        _write_json_list(path, rows)
        return log_id

    def _last_portale_import_log(portale: str) -> dict[str, Any]:
        sorgente = _portale_source_name(portale).strip().upper()
        for row in reversed(_read_json_list(_portale_import_log_path())):
            if str(row.get("portale") or "").strip().upper() == sorgente:
                return dict(row)
        return {}

    def _resolve_ufficio_nome(codice: str) -> str:
        codice = str(codice or "").strip()
        if not codice:
            return ""
        try:
            from pct.uffici_giudiziari import get_gestore as _get_uff

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            uff = next((u for u in _get_uff(cache_path).carica() if u.get("codice") == codice), None)
            return str((uff or {}).get("nome") or codice).strip()
        except Exception:
            return codice

    def _portale_source_name(portale: str) -> str:
        return {
            "pst": "PST",
            "pdp": "PDP",
            "pat": "PAT",
            "ptt": "PTT",
        }.get((portale or "").strip().lower(), (portale or "").upper())

    def _telematico_channel_family(portale: str) -> str:
        return {
            "pst": "ministero",
            "pdp": "ministero",
            "pat": "amministrativo",
            "ptt": "tributario",
        }.get((portale or "").strip().lower(), "ministero")

    def _telematico_service_code(portale: str) -> str:
        return {
            "pst": "polisweb_consultazione",
            "pdp": "pdp_penale",
            "pat": "pat_siga",
            "ptt": "ptt_sigit",
        }.get((portale or "").strip().lower(), "polisweb_consultazione")

    def _telematico_internal_status(
        *,
        sync_status: str = "",
        native_status: str = "",
        has_documents: bool = False,
        documents_imported: bool = False,
        needs_manual_review: bool = False,
    ) -> str:
        native = str(native_status or "").strip().upper()
        sync = str(sync_status or "").strip().upper()
        if native in {"RIFIUTATO", "ERRORE_TECNICO"}:
            return "rejected" if native == "RIFIUTATO" else "technical_error"
        if needs_manual_review:
            return "manual_review_required"
        if documents_imported or sync in {"IMPORTATO", "SINCRONIZZATO"}:
            return "import_completed"
        if has_documents:
            return "download_available"
        if native in {"ACCETTATO", "AUTHORIZED"}:
            return "accepted"
        if native in {"INVIATO", "IN_TRANSITO", "IN_VERIFICA"}:
            return "submitted"
        return "draft"

    def _telematico_transmission_status(native_status: str = "", has_documents: bool = False) -> str:
        native = str(native_status or "").strip().upper()
        if native == "RIFIUTATO":
            return "rejected"
        if native == "ERRORE_TECNICO":
            return "technical_error"
        if native in {"INVIATO", "IN_TRANSITO", "IN_VERIFICA"}:
            return "submitted"
        if native in {"ACCETTATO", "AUTHORIZED"} or has_documents:
            return "accepted"
        return "closed"

    def _telematico_document_role(doc: dict[str, Any]) -> str:
        tipo = str((doc or {}).get("tipo_atto") or (doc or {}).get("tipo") or "").upper()
        nome = str((doc or {}).get("nome") or "").upper()
        testo = f"{tipo} {nome}"
        if "SENTENZA" in testo:
            return "judgment"
        if "ORDINANZA" in testo or "DECRETO" in testo or "PROVVEDIMENTO" in testo:
            return "judicial_order"
        if "VERBALE" in testo or "UDIENZA" in testo:
            return "hearing_minutes"
        return "main_act" if "RICORSO" in testo or "ATTO" in testo or "MEMORIA" in testo else "attachment"

    def _is_portale_dns_error(exc: Exception) -> bool:
        text = str(exc or "").lower()
        return any(
            marker in text
            for marker in (
                "nameresolutionerror",
                "failed to resolve",
                "getaddrinfo failed",
                "impossibile risolvere il nome remoto",
                "name or service not known",
                "nodename nor servname provided",
            )
        )

    def _portale_browser_guided_message(portale: str) -> str:
        labels = {
            "pst": "PST / PolisWeb",
            "pdp": "PDP Penale",
            "pat": "PAT",
            "ptt": "PTT",
        }
        label = labels.get((portale or "").strip().lower(), (portale or "").upper())
        if (portale or "").strip().lower() == "pat":
            return (
                "Per PAT la consultazione pratica passa dal Portale dell'Avvocato ufficiale. "
                "Usa l'acquisizione guidata, poi importa nel fascicolo interno documenti, ricevute ed esiti "
                "gia consultati o scaricati dal portale."
            )
        if (portale or "").strip().lower() == "ptt":
            return (
                "Per PTT / SIGIT IUSENTRA non promette una sincronizzazione live del fascicolo ministeriale. "
                "Usa l'acquisizione guidata, apri il portale ufficiale o Telecontenzioso nel browser, "
                "consulta o scarica il fascicolo processuale e poi importa nel fascicolo tributario interno "
                "documenti, ricevute, provvedimenti ed esiti."
            )
        if (portale or "").strip().lower() == "pdp":
            return (
                "Per PDP Penale il fascicolo si consulta dal canale ufficiale MinGiust con le stesse credenziali "
                "CNS del PCT civile. Usa l'acquisizione guidata, completa il download nel browser e poi importa in "
                "IUSENTRA i file gia scaricati nel workflow PDP."
            )
        return (
            f"L'endpoint ufficiale di {label} non è raggiungibile dal backend server. "
            "Usa l'acquisizione guidata dal browser con Local Signer su questo PC."
        )

    def _normalize_portale_documents(documenti: list[dict]) -> list[dict]:
        def _effective_id_cat(item: dict[str, Any]) -> str:
            explicit = str(item.get("id_cat") or "").strip()
            if explicit:
                return explicit
            candidates = []
            for value in list(item.get("id_documento_candidates") or []):
                candidate = str(value or "").strip()
                if candidate and candidate not in candidates:
                    candidates.append(candidate)
            for value in (
                item.get("id_documento"),
                item.get("id_documento_portale"),
                item.get("numero_documento"),
                item.get("id_doc_mittente"),
            ):
                candidate = str(value or "").strip()
                if candidate and candidate not in candidates:
                    candidates.append(candidate)
            return candidates[0] if candidates else ""

        rows: list[dict] = []
        for row in documenti or []:
            item = dict(row or {})
            candidates = [
                str(value or "").strip()
                for value in list(item.get("id_documento_candidates") or [])
                if str(value or "").strip()
            ]
            id_documento = str(item.get("id_documento") or item.get("id_documento_portale") or "").strip()
            if id_documento and id_documento not in candidates:
                candidates.insert(0, id_documento)
            id_cat = _effective_id_cat(item)
            rows.append(
                {
                    "id_documento": id_documento,
                    "nome": str(item.get("nome") or item.get("nome_documento") or "").strip(),
                    "tipo": str(item.get("tipo") or "").strip(),
                    "tipo_atto": str(item.get("tipo_atto") or item.get("tipo") or "").strip(),
                    "data_deposito": str(item.get("data_deposito") or item.get("data_documento") or "").strip(),
                    "mittente": str(item.get("mittente") or "").strip(),
                    "dimensione_bytes": int(item.get("dimensione_bytes") or 0),
                    "disponibile": bool(item.get("disponibile", True)),
                    "id_deposito": str(item.get("id_deposito") or item.get("id_deposito_esterno") or "").strip(),
                    "id_cat": id_cat,
                    "id_repeatto": str(item.get("id_repeatto") or "").strip(),
                    "msg_id": str(item.get("msg_id") or "").strip(),
                    "numero_documento": str(item.get("numero_documento") or "").strip(),
                    "id_doc_mittente": str(item.get("id_doc_mittente") or "").strip(),
                    "id_documento_candidates": candidates,
                }
            )
        rows.sort(
            key=lambda doc: (
                doc.get("data_deposito") or "",
                doc.get("nome") or "",
                doc.get("id_documento") or "",
            ),
            reverse=True,
        )
        return rows

    def _group_portale_documents(documenti: list[dict]) -> list[dict]:
        from collections import OrderedDict

        def _solo_data(d: str) -> str:
            """Normalizza a YYYY-MM-DD (coerente con _chiave_deposito_polisweb).

            Gestisce formati multipli (ISO, italiano dd/mm/yyyy, dd-mm-yyyy)
            esattamente come _parse_data in polisWeb.py — altrimenti le chiavi
            di raggruppamento differiscono e lo stesso deposito appare duplicato.
            """
            if not d:
                return ""
            testo = str(d).strip()
            if isinstance(d, date):
                return d.strftime("%Y-%m-%d")
            # Strip parte oraria (T o spazio)
            for sep in ("T", " "):
                if sep in testo:
                    testo = testo.split(sep)[0]
                    break
            candidati = [testo]
            if len(testo) >= 10:
                candidati.append(testo[:10])
            for candidato in candidati:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(candidato, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        continue
            return testo[:10] if len(testo) >= 10 else testo

        gruppi: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        for doc in _normalize_portale_documents(documenti):
            chiave = doc["id_deposito"] or f"__{_solo_data(doc['data_deposito'])}__{doc['mittente']}"
            group = gruppi.setdefault(
                chiave,
                {
                    "id_deposito": chiave,
                    "tipo_atto": doc.get("tipo_atto") or doc.get("tipo") or "Deposito",
                    "data_deposito": doc.get("data_deposito") or "",
                    "mittente": doc.get("mittente") or "",
                    "documenti": [],
                },
            )
            group["documenti"].append(doc)
        return list(gruppi.values())

    def _serialize_portale_search_item(portale: str, fascicolo: Any) -> dict[str, Any]:
        portale = (portale or "").lower()
        if portale == "pst":
            payload = {
                "id_fascicolo": getattr(fascicolo, "id_fascicolo", ""),
                "numero_rg": fascicolo.numero_rg,
                "anno_rg": fascicolo.anno_rg,
                "ruolo": fascicolo.ruolo,
                "stato": fascicolo.stato,
                "oggetto": fascicolo.oggetto,
                "sezione": fascicolo.sezione,
                "giudice": fascicolo.giudice,
                "data_iscrizione": fascicolo.data_iscrizione,
                "data_udienza": fascicolo.data_udienza,
                "parti": list(fascicolo.parti or []),
                "parti_dettaglio": list(fascicolo.parti_dettaglio or []),
                "note": fascicolo.note,
                "codice_ufficio": fascicolo.codice_ufficio,
                "nome_ufficio": fascicolo.nome_ufficio,
                "sub_procedimento": getattr(fascicolo, "sub_procedimento", ""),
            }
            numero = fascicolo.numero_rg
            anno = fascicolo.anno_rg
            uff_cod = fascicolo.codice_ufficio
            uff_nome = fascicolo.nome_ufficio
            procedimento = fascicolo.ruolo.replace("_", " ").title()
            oggetto = fascicolo.oggetto
            assistiti = list(fascicolo.parti or [])
            controparti = []
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_iscrizione
            stato = fascicolo.stato
        elif portale == "pdp":
            payload = {
                "numero_rg": fascicolo.numero_rg,
                "anno_rg": fascicolo.anno_rg,
                "tipo_registro": fascicolo.tipo_registro,
                "fase": fascicolo.fase,
                "stato": fascicolo.stato,
                "reato": fascicolo.reato,
                "sezione": fascicolo.sezione,
                "giudice": fascicolo.giudice,
                "data_iscrizione": fascicolo.data_iscrizione,
                "data_udienza": fascicolo.data_udienza,
                "imputati": list(fascicolo.imputati or []),
                "parti_offese": list(fascicolo.parti_offese or []),
                "note": fascicolo.note,
                "codice_ufficio": fascicolo.codice_ufficio,
                "nome_ufficio": fascicolo.nome_ufficio,
            }
            numero = fascicolo.numero_rg
            anno = fascicolo.anno_rg
            uff_cod = fascicolo.codice_ufficio
            uff_nome = fascicolo.nome_ufficio
            procedimento = fascicolo.tipo_registro
            oggetto = fascicolo.reato
            assistiti = list(fascicolo.imputati or [])
            controparti = list(fascicolo.parti_offese or [])
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_iscrizione
            stato = fascicolo.stato
        elif portale == "pat":
            payload = {
                "numero_ricorso": fascicolo.numero_ricorso,
                "anno": fascicolo.anno,
                "tipo": fascicolo.tipo,
                "stato": fascicolo.stato,
                "materia": fascicolo.materia,
                "sezione": fascicolo.sezione,
                "giudice_relatore": fascicolo.giudice_relatore,
                "data_deposito": fascicolo.data_deposito,
                "data_udienza": fascicolo.data_udienza,
                "ricorrenti": list(fascicolo.ricorrenti or []),
                "resistenti": list(fascicolo.resistenti or []),
                "controinteressati": list(getattr(fascicolo, "controinteressati", []) or []),
                "oggetto": fascicolo.oggetto,
                "note": fascicolo.note,
                "codice_ufficio": fascicolo.codice_ufficio,
                "nome_ufficio": fascicolo.nome_ufficio,
            }
            numero = fascicolo.numero_ricorso
            anno = fascicolo.anno
            uff_cod = fascicolo.codice_ufficio
            uff_nome = fascicolo.nome_ufficio
            procedimento = fascicolo.tipo
            oggetto = fascicolo.oggetto or fascicolo.materia
            assistiti = list(fascicolo.ricorrenti or [])
            controparti = list(fascicolo.resistenti or [])
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_deposito
            stato = fascicolo.stato
        else:
            payload = {
                "numero_rgt": fascicolo.numero_rgt,
                "anno_rgt": fascicolo.anno_rgt,
                "tipo": fascicolo.tipo,
                "stato": fascicolo.stato,
                "materia": fascicolo.materia,
                "sezione": fascicolo.sezione,
                "giudice_relatore": fascicolo.giudice_relatore,
                "data_deposito": fascicolo.data_deposito,
                "data_udienza": fascicolo.data_udienza,
                "ricorrenti": list(fascicolo.ricorrenti or []),
                "resistenti": list(fascicolo.resistenti or []),
                "oggetto_controversia": fascicolo.oggetto_controversia,
                "valore_controversia": getattr(fascicolo, "valore_controversia", 0.0),
                "note": fascicolo.note,
                "codice_commissione": fascicolo.codice_commissione,
                "nome_commissione": fascicolo.nome_commissione,
            }
            numero = fascicolo.numero_rgt
            anno = fascicolo.anno_rgt
            uff_cod = fascicolo.codice_commissione
            uff_nome = fascicolo.nome_commissione
            procedimento = fascicolo.tipo
            oggetto = fascicolo.oggetto_controversia or fascicolo.materia
            assistiti = list(fascicolo.ricorrenti or [])
            controparti = list(fascicolo.resistenti or [])
            ultima_attivita = fascicolo.data_udienza or fascicolo.data_deposito
            stato = fascicolo.stato

        return {
            "external_id": f"{uff_cod}:{numero}:{anno}:{procedimento}",
            "id_fascicolo": str(payload.get("id_fascicolo") or "").strip(),
            "numero": str(numero or "").strip(),
            "anno": int(anno or 0),
            "ufficio_codice": str(uff_cod or "").strip(),
            "ufficio_nome": str(uff_nome or _resolve_ufficio_nome(str(uff_cod or ""))).strip(),
            "procedimento": str(procedimento or "").strip(),
            "sub_procedimento": str(payload.get("sub_procedimento") or "").strip(),
            "sezione": str(payload.get("sezione") or "").strip(),
            "stato": str(stato or "").strip(),
            "oggetto": str(oggetto or "").strip(),
            "parti": assistiti,
            "controparti": controparti,
            "ultima_attivita": str(ultima_attivita or "").strip(),
            "payload": payload,
        }

    def _build_portale_preview(portale: str, selection: dict[str, Any], documenti: list[dict]) -> dict[str, Any]:
        payload = dict((selection or {}).get("payload") or {})
        docs = _normalize_portale_documents(documenti or [])
        depositi = _group_portale_documents(docs)
        def _clean(value: Any) -> str:
            return str(value or "").strip()

        def _first_value(*values: Any) -> str:
            for value in values:
                cleaned = _clean(value)
                if cleaned:
                    return cleaned
            return ""

        def _sortable_date(raw: Any) -> tuple[int, datetime]:
            value = _clean(raw)
            if not value:
                return (0, datetime.min)
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S.%f",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y",
            ):
                try:
                    return (1, datetime.strptime(value, fmt))
                except ValueError:
                    continue
            return (0, datetime.min)

        provvedimenti_count = sum(
            1
            for doc in docs
            if any(token in (doc.get("tipo_atto") or doc.get("tipo") or "").upper() for token in ("SENTENZA", "ORDINANZA", "DECRETO", "PROVVEDIMENTO"))
        )
        data_iscrizione = _first_value(payload.get("data_iscrizione"), payload.get("data_deposito"))
        data_udienza = _first_value(payload.get("data_udienza"))
        latest_doc_date = ""
        doc_dates = [_clean(doc.get("data_deposito")) for doc in docs if _clean(doc.get("data_deposito"))]
        if doc_dates:
            latest_doc_date = max(doc_dates, key=_sortable_date)
        procedimento = _first_value(
            selection.get("procedimento"),
            payload.get("ruolo"),
            payload.get("tipo_registro"),
            payload.get("tipo"),
            payload.get("sub_procedimento"),
        )
        stato = _first_value(selection.get("stato"), payload.get("stato"), payload.get("fase"))
        oggetto = _first_value(
            selection.get("oggetto"),
            payload.get("oggetto"),
            payload.get("reato"),
            payload.get("oggetto_controversia"),
            payload.get("materia"),
        )
        ultima_attivita = _first_value(
            selection.get("ultima_attivita"),
            latest_doc_date,
            data_udienza,
            data_iscrizione,
        )
        eventi = []
        if data_iscrizione:
            eventi.append({"label": "Iscrizione / deposito originario", "data": data_iscrizione, "tipo": "iscrizione"})
        if data_udienza:
            eventi.append({"label": "Udienza rilevata", "data": data_udienza, "tipo": "udienza"})
        return {
            "identity": {
                "id_fascicolo": _first_value(selection.get("id_fascicolo"), payload.get("id_fascicolo")),
                "numero": str(selection.get("numero") or "").strip(),
                "anno": int(selection.get("anno") or 0),
                "ufficio_nome": str(selection.get("ufficio_nome") or "").strip(),
                "ufficio_codice": str(selection.get("ufficio_codice") or "").strip(),
                "procedimento": procedimento,
                "sub_procedimento": _first_value(selection.get("sub_procedimento"), payload.get("sub_procedimento")),
                "sezione": _first_value(selection.get("sezione"), payload.get("sezione")),
                "oggetto": oggetto,
                "stato": stato,
                "data_iscrizione": data_iscrizione,
                "data_udienza": data_udienza,
                "ultima_attivita": ultima_attivita,
            },
            "parti": list(selection.get("parti") or []),
            "controparti": list(selection.get("controparti") or []),
            "difensori": [x for x in list(payload.get("difensori") or []) if str(x).strip()],
            "eventi": eventi,
            "documenti": docs,
            "depositi": depositi,
            "counts": {
                "parti": len(list(selection.get("parti") or [])) + len(list(selection.get("controparti") or [])),
                "difensori": len(list(payload.get("difensori") or [])),
                "eventi": len(eventi),
                "udienze": 1 if data_udienza else 0,
                "documenti": len(docs),
                "provvedimenti": provvedimenti_count,
                "depositi": len(depositi),
                "esiti": len(depositi),
            },
        }

    def _portale_doc_is_provvedimento(doc: dict[str, Any]) -> bool:
        tipo = str((doc or {}).get("tipo_atto") or (doc or {}).get("tipo") or "").upper()
        return any(token in tipo for token in ("SENTENZA", "ORDINANZA", "DECRETO", "PROVVEDIMENTO"))

    def _preview_richiede_file_portale(options: dict[str, bool]) -> bool:
        return bool(options.get("importa_documenti") or options.get("importa_provvedimenti"))

    def _filter_portale_preview_by_options(preview: dict[str, Any], options: dict[str, bool]) -> dict[str, Any]:
        view = dict(preview or {})
        docs = _normalize_portale_documents(list(view.get("documenti") or []))
        include_docs = bool(options.get("importa_documenti", True))
        include_provvedimenti = bool(options.get("importa_provvedimenti", True))
        if include_docs and include_provvedimenti:
            filtered_docs = docs
        else:
            filtered_docs = [
                doc
                for doc in docs
                if (
                    _portale_doc_is_provvedimento(doc) and include_provvedimenti
                ) or (
                    not _portale_doc_is_provvedimento(doc) and include_docs
                )
            ]
        filtered_depositi = _group_portale_documents(filtered_docs)
        counts = dict(view.get("counts") or {})
        counts["documenti"] = len(filtered_docs)
        counts["provvedimenti"] = sum(1 for doc in filtered_docs if _portale_doc_is_provvedimento(doc))
        counts["depositi"] = len(filtered_depositi)
        view["documenti"] = filtered_docs
        view["depositi"] = filtered_depositi
        view["counts"] = counts
        return view

    def _normalize_portale_match_text(value: Any) -> str:
        text = str(value or "").strip().upper()
        text = re.sub(r"\s+", " ", text)
        return text

    def _expected_fascicolo_types_for_portale(
        portale: str, selection: dict[str, Any] | None = None
    ) -> set[str]:
        portale_norm = str(portale or "").strip().lower()
        selection = selection or {}
        procedimento = _normalize_portale_match_text(selection.get("procedimento"))
        if portale_norm == "pdp":
            return {"PENALE"}
        if portale_norm == "pat":
            return {"AMMINISTRATIVO"}
        if portale_norm == "ptt":
            return {"TRIBUTARIO", "ALTRO"}
        if procedimento == "PENALE":
            return {"PENALE"}
        if procedimento == "LAVORO":
            return {"LAVORO", "CIVILE"}
        if procedimento in {"FAMIGLIA", "MINORI"}:
            return {"FAMIGLIA", "CIVILE"}
        return {"CIVILE", "LAVORO", "FAMIGLIA", "ALTRO"}

    def _is_fascicolo_type_compatible_for_portale(
        fasc: Fascicolo, portale: str, selection: dict[str, Any] | None = None
    ) -> bool:
        expected = _expected_fascicolo_types_for_portale(portale, selection)
        fasc_type = _normalize_portale_match_text(getattr(getattr(fasc, "tipo", None), "value", ""))
        return not expected or fasc_type in expected

    def _selection_rg_identity(selection: dict[str, Any]) -> dict[str, Any]:
        numero = str(selection.get("numero") or "").strip()
        try:
            anno = int(selection.get("anno") or 0)
        except (TypeError, ValueError):
            anno = 0
        ufficio_nome = str(
            selection.get("ufficio_nome")
            or _resolve_ufficio_nome(str(selection.get("ufficio_codice") or ""))
        ).strip()
        external_id = str(selection.get("external_id") or "").strip()
        return {
            "numero": numero,
            "anno": anno,
            "ufficio_nome": ufficio_nome,
            "external_id": external_id,
        }

    def _fascicolo_matches_selection(
        fasc: Fascicolo,
        portale: str,
        selection: dict[str, Any],
        *,
        strict: bool,
    ) -> bool:
        if not _is_fascicolo_type_compatible_for_portale(fasc, portale, selection):
            return False
        identity = _selection_rg_identity(selection)
        sel_numero = identity["numero"]
        sel_anno = int(identity["anno"] or 0)
        sel_ufficio = _normalize_portale_match_text(identity["ufficio_nome"])
        fasc_numero = str(getattr(fasc, "numero_rg", "") or "").strip()
        try:
            fasc_anno = int(getattr(fasc, "anno_rg", 0) or 0)
        except (TypeError, ValueError):
            fasc_anno = 0
        fasc_ufficio = _normalize_portale_match_text(getattr(fasc, "tribunale", ""))
        if strict:
            return bool(
                sel_numero
                and sel_anno
                and sel_ufficio
                and fasc_numero == sel_numero
                and fasc_anno == sel_anno
                and fasc_ufficio == sel_ufficio
            )
        if fasc_numero and sel_numero and fasc_numero != sel_numero:
            return False
        if fasc_anno and sel_anno and fasc_anno != sel_anno:
            return False
        if fasc_ufficio and sel_ufficio and fasc_ufficio != sel_ufficio:
            return False
        return True

    def _find_exact_fascicolo_locale_portale(
        portale: str, selection: dict[str, Any]
    ) -> Optional[Fascicolo]:
        identity = _selection_rg_identity(selection)
        expected_external_id = identity["external_id"]
        fascicoli = list(get_fascicoli().tutti())
        if expected_external_id:
            for fasc in fascicoli:
                if not _is_fascicolo_type_compatible_for_portale(fasc, portale, selection):
                    continue
                if str(getattr(fasc, "source_external_id", "") or "").strip() == expected_external_id:
                    return fasc
        for fasc in fascicoli:
            if _fascicolo_matches_selection(fasc, portale, selection, strict=True):
                return fasc
        return None

    def _resolve_portale_import_target(
        portale: str,
        selection: dict[str, Any],
        mapping: dict[str, str],
    ) -> tuple[str, Optional[Fascicolo], bool]:
        gf = get_fascicoli()
        requested_mode = mapping.get("mode") or "create_new"
        target_id = str(mapping.get("target_fascicolo_id") or "").strip()
        if requested_mode in {"attach_existing", "update_existing"}:
            if not target_id:
                raise ValueError("Fascicolo locale selezionato non trovato.")
            target = gf.get(target_id)
            if not target:
                raise ValueError("Fascicolo locale selezionato non trovato.")
            if not _fascicolo_matches_selection(target, portale, selection, strict=False):
                raise ValueError("Il fascicolo locale selezionato non è compatibile con il fascicolo del portale.")
            resolved_mode = "update_existing" if requested_mode == "update_existing" else "attach_existing"
            return resolved_mode, target, False
        exact = _find_exact_fascicolo_locale_portale(portale, selection)
        if exact:
            return "update_existing", exact, True
        return "create_new", None, False

    def _find_matching_fascicoli_locali(selection: dict[str, Any]) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        numero = str(selection.get("numero") or "").strip()
        anno = int(selection.get("anno") or 0)
        ufficio_nome = str(selection.get("ufficio_nome") or "").strip().upper()
        tokens = [token.strip().upper() for token in list(selection.get("parti") or [])[:2] if token.strip()]
        for fasc in get_fascicoli().tutti():
            same_rg = numero and fasc.numero_rg == numero and int(getattr(fasc, "anno_rg", 0) or 0) == anno
            same_ufficio = ufficio_nome and str(fasc.tribunale or "").strip().upper() == ufficio_nome
            text_hit = any(token in str(fasc.titolo or "").upper() for token in tokens)
            if same_rg or (same_ufficio and text_hit):
                matches.append(
                    {
                        "id": fasc.id,
                        "numero": fasc.numero,
                        "titolo": fasc.titolo,
                        "rg_completo": fasc.rg_completo,
                        "tribunale": fasc.tribunale,
                        "stato": fasc.stato.value,
                        "source": getattr(fasc, "source", "") or "",
                    }
                )
        return matches

    def _sync_existing_fascicolo_from_portale(
        portale: str,
        target: Fascicolo,
        selection: dict[str, Any],
        preview: dict[str, Any],
        *,
        preserve_blank: bool,
        append_import_note: bool,
        user_name: str,
        log_id: str = "",
    ) -> Fascicolo:
        identity = dict(preview.get("identity") or {})
        payload = dict(selection.get("payload") or {})

        def _take(current: Any, incoming: Any) -> Any:
            if preserve_blank and str(current or "").strip():
                return current
            return incoming

        tipo_procedimento = (
            str(selection.get("procedimento") or "").strip()
            or str(payload.get("tipo_registro") or payload.get("tipo") or "").strip()
            or str(target.tipo_procedimento or "").strip()
        )
        update_fields: dict[str, Any] = {
            "tribunale": _take(
                target.tribunale,
                selection.get("ufficio_nome") or identity.get("ufficio_nome") or target.tribunale,
            ),
            "numero_rg": _take(target.numero_rg, selection.get("numero") or target.numero_rg),
            "anno_rg": target.anno_rg or int(selection.get("anno") or 0),
            "oggetto": _take(target.oggetto, identity.get("oggetto") or target.oggetto),
            "sezione": _take(target.sezione, identity.get("sezione") or target.sezione),
            "giudice": _take(
                target.giudice,
                payload.get("giudice") or payload.get("giudice_relatore") or target.giudice,
            ),
            "tipo_procedimento": _take(target.tipo_procedimento, tipo_procedimento),
        }
        if append_import_note:
            nota_import = f"Sincronizzato da {_portale_source_name(portale)} il {date.today().isoformat()}"
            update_fields["note"] = " | ".join(part for part in [target.note.strip(), nota_import] if part)
        stato_portale = stato_fascicolo_da_descrizione_portale(
            identity.get("stato") or selection.get("stato") or payload.get("stato"),
            default=None,
        )
        if stato_portale and stato_portale != target.stato:
            update_fields["stato"] = stato_portale
        updated = get_fascicoli().aggiorna(target.id, **update_fields)
        get_fascicoli().registra_onboarding(
            target.id,
            f"Acquisizione guidata da {_portale_source_name(portale)}",
            note=f"Import log {log_id}" if log_id else "",
            avvocato=user_name,
        )
        return updated

    def _coerce_import_options(data: dict[str, Any]) -> dict[str, bool]:
        def _b(key: str, default: bool = False) -> bool:
            value = data.get(key, default)
            if isinstance(value, bool):
                return value
            return str(value or "").strip().lower() in {"1", "true", "yes", "si", "s", "on"}

        return {
            "importa_dati_pratica": _b("importa_dati_pratica", True),
            "importa_parti": _b("importa_parti", True),
            "importa_difensori": _b("importa_difensori", True),
            "importa_eventi": _b("importa_eventi", True),
            "importa_udienze": _b("importa_udienze", True),
            "importa_scadenze": _b("importa_scadenze", True),
            "importa_documenti": _b("importa_documenti", True),
            "importa_provvedimenti": _b("importa_provvedimenti", True),
            "importa_cronologia_depositi": _b("importa_cronologia_depositi", True),
            "importa_esiti_telematici": _b("importa_esiti_telematici", True),
            "solo_nuovi": _b("solo_nuovi", True),
            "aggiorna_pratica_esistente": _b("aggiorna_pratica_esistente", False),
            "sovrascrivi_solo_vuoti": _b("sovrascrivi_solo_vuoti", True),
            "non_toccare_note_interne": _b("non_toccare_note_interne", True),
            "non_duplicare_documenti": _b("non_duplicare_documenti", True),
            "conserva_log_origine_pst": _b("conserva_log_origine_pst", True),
            "scarica_originale_portale": _b("scarica_originale_portale", True),
            "mantieni_albero_originale": _b("mantieni_albero_originale", False),
        }

    def _coerce_mapping(data: dict[str, Any]) -> dict[str, str]:
        return {
            "mode": str(data.get("mode") or "create_new").strip() or "create_new",
            "target_fascicolo_id": str(data.get("target_fascicolo_id") or "").strip(),
            "area_pratica": str(data.get("area_pratica") or "").strip(),
            "materia": str(data.get("materia") or "").strip(),
            "procedimento": str(data.get("procedimento") or "").strip(),
            "grado": str(data.get("grado") or "").strip(),
            "stato_iniziale": str(data.get("stato_iniziale") or "").strip(),
        }

    def _analyze_portale_import(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        options: dict[str, bool],
        mapping: dict[str, str],
    ) -> dict[str, Any]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        oks: list[dict[str, Any]] = []
        candidates = _find_matching_fascicoli_locali(selection)
        resolved_mode = mapping.get("mode") or "create_new"
        auto_target: Optional[Fascicolo] = None
        auto_integrated = False
        try:
            resolved_mode, auto_target, auto_integrated = _resolve_portale_import_target(portale, selection, mapping)
        except Exception as target_error:
            if (mapping.get("mode") or "create_new") in {"attach_existing", "update_existing"}:
                blockers.append(
                    {
                        "label": "Pratica locale non compatibile",
                        "detail": str(target_error),
                        "tone": "danger",
                    }
                )
        counts = dict(preview.get("counts") or {})
        mode = mapping.get("mode") or "create_new"
        target_id = mapping.get("target_fascicolo_id") or ""
        payload = dict(selection.get("payload") or {})
        manual_mode = bool(selection.get("manual_mode") or payload.get("manual_mode"))

        if not selection.get("ufficio_codice"):
            blockers.append({"label": "Ufficio giudiziario mancante", "detail": "Seleziona un ufficio valido prima di proseguire.", "tone": "danger"})
        else:
            oks.append({"label": "Ufficio giudiziario risolto", "detail": selection.get("ufficio_nome") or selection.get("ufficio_codice"), "tone": "success"})

        if not selection.get("numero") or not selection.get("anno"):
            blockers.append({"label": "RG incompleto", "detail": "Numero e anno del fascicolo sono obbligatori per una pratica governabile.", "tone": "danger"})
        else:
            oks.append({"label": "Identità fascicolo pronta", "detail": f"{selection.get('numero')}/{selection.get('anno')}", "tone": "success"})

        if options.get("importa_parti") and counts.get("parti", 0) <= 0:
            if manual_mode and portale in {"pdp", "pat", "ptt"}:
                warnings.append({
                    "label": "Parti da completare manualmente",
                    "detail": "Il portale non ha restituito parti strutturate: completa assistiti e controparti dal browser ufficiale o direttamente nel gestionale dopo l'importazione.",
                    "tone": "warning",
                })
            else:
                blockers.append({"label": "Parti non disponibili", "detail": "Il fascicolo remoto non espone parti sufficienti per l'importazione guidata.", "tone": "danger"})
        elif counts.get("parti", 0) > 0:
            oks.append({"label": "Parti rilevate", "detail": f"{counts.get('parti', 0)} soggetti disponibili", "tone": "success"})

        if options.get("importa_documenti") and counts.get("documenti", 0) == 0:
            warnings.append({
                "label": "Nessun documento disponibile",
                "detail": (
                    "Puoi importare la pratica anche senza documenti, ma la vista fascicolo restera' parziale."
                    if not manual_mode
                    else "Il catalogo documentale non e' stato esposto dal servizio remoto: importa la pratica e completa documenti e depositi dal portale ufficiale."
                ),
                "tone": "warning",
            })
        elif counts.get("documenti", 0) > 0:
            oks.append({"label": "Catalogo documentale disponibile", "detail": f"{counts.get('documenti', 0)} documenti / {counts.get('depositi', 0)} buste", "tone": "success"})

        if mode in {"attach_existing", "update_existing"} and not target_id:
            blockers.append({"label": "Pratica locale non selezionata", "detail": "Per collegare o aggiornare devi scegliere un fascicolo esistente.", "tone": "danger"})

        if auto_integrated and auto_target is not None:
            warnings.append(
                {
                    "label": "Pratica locale già presente",
                    "detail": f"L'importazione aggiornerà automaticamente {auto_target.titolo} invece di creare un duplicato.",
                    "tone": "warning",
                }
            )
        elif mode == "create_new" and candidates:
            warnings.append({"label": "Possibile duplicato locale", "detail": f"Esistono {len(candidates)} fascicoli con RG o parti compatibili.", "tone": "warning"})

        if options.get("importa_scadenze") and not preview.get("identity", {}).get("data_udienza"):
            warnings.append({"label": "Nessuna udienza importabile", "detail": "Il portale non espone una prossima udienza da tradurre in scadenziario.", "tone": "warning"})

        score = max(0, min(100, 100 - len(blockers) * 18 - len(warnings) * 7))
        status = "ok" if not blockers and not warnings else ("warning" if not blockers else "block")
        return {
            "status": status,
            "score": score,
            "blockers": blockers,
            "warnings": warnings,
            "ok": oks,
            "existing_matches": candidates,
            "resolved_mode": resolved_mode,
            "auto_integrated": auto_integrated,
            "auto_target_fascicolo_id": getattr(auto_target, "id", "") if auto_target else "",
            "summary_text": (
                "Importazione pronta: nessun blocco rilevato."
                if not blockers
                else f"Risolvi {len(blockers)} blocchi e verifica {len(warnings)} avvisi prima dell'importazione."
            ),
            "next_step": blockers[0] if blockers else (warnings[0] if warnings else {"label": "Pronto per importare", "detail": "Puoi procedere con l'acquisizione guidata.", "tone": "success"}),
        }

    def _selection_to_fascicolo_dataclass(portale: str, selection: dict[str, Any]) -> Any:
        payload = dict((selection or {}).get("payload") or {})
        if portale == "pst":
            from pct.polisWeb import FascicoloPolisWeb

            return FascicoloPolisWeb(
                numero_rg=str(payload.get("numero_rg") or selection.get("numero") or "").strip(),
                anno_rg=int(payload.get("anno_rg") or selection.get("anno") or 0),
                ruolo=str(payload.get("ruolo") or selection.get("procedimento") or "").strip(),
                stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
                oggetto=str(payload.get("oggetto") or selection.get("oggetto") or "").strip(),
                sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
                giudice=str(payload.get("giudice") or "").strip(),
                data_iscrizione=str(payload.get("data_iscrizione") or "").strip(),
                data_udienza=str(payload.get("data_udienza") or "").strip(),
                parti=list(payload.get("parti") or selection.get("parti") or []),
                parti_dettaglio=list(payload.get("parti_dettaglio") or []),
                note=str(payload.get("note") or "").strip(),
                codice_ufficio=str(payload.get("codice_ufficio") or selection.get("ufficio_codice") or "").strip(),
                nome_ufficio=str(payload.get("nome_ufficio") or selection.get("ufficio_nome") or "").strip(),
            )
        if portale == "pdp":
            from pct.pdp import FascicoloPDP

            return FascicoloPDP(
                numero_rg=str(payload.get("numero_rg") or selection.get("numero") or "").strip(),
                anno_rg=int(payload.get("anno_rg") or selection.get("anno") or 0),
                tipo_registro=str(payload.get("tipo_registro") or selection.get("procedimento") or "").strip(),
                fase=str(payload.get("fase") or "").strip(),
                stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
                reato=str(payload.get("reato") or selection.get("oggetto") or "").strip(),
                sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
                giudice=str(payload.get("giudice") or "").strip(),
                data_iscrizione=str(payload.get("data_iscrizione") or "").strip(),
                data_udienza=str(payload.get("data_udienza") or "").strip(),
                imputati=list(payload.get("imputati") or selection.get("parti") or []),
                parti_offese=list(payload.get("parti_offese") or selection.get("controparti") or []),
                note=str(payload.get("note") or "").strip(),
                codice_ufficio=str(payload.get("codice_ufficio") or selection.get("ufficio_codice") or "").strip(),
                nome_ufficio=str(payload.get("nome_ufficio") or selection.get("ufficio_nome") or "").strip(),
            )
        if portale == "pat":
            from pct.pat import FascicoloPAT

            return FascicoloPAT(
                numero_ricorso=str(payload.get("numero_ricorso") or selection.get("numero") or "").strip(),
                anno=int(payload.get("anno") or selection.get("anno") or 0),
                tipo=str(payload.get("tipo") or selection.get("procedimento") or "").strip(),
                stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
                materia=str(payload.get("materia") or "").strip(),
                sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
                giudice_relatore=str(payload.get("giudice_relatore") or "").strip(),
                data_deposito=str(payload.get("data_deposito") or payload.get("data_iscrizione") or "").strip(),
                data_udienza=str(payload.get("data_udienza") or "").strip(),
                ricorrenti=list(payload.get("ricorrenti") or selection.get("parti") or []),
                resistenti=list(payload.get("resistenti") or selection.get("controparti") or []),
                controinteressati=list(payload.get("controinteressati") or []),
                oggetto=str(payload.get("oggetto") or selection.get("oggetto") or "").strip(),
                note=str(payload.get("note") or "").strip(),
                codice_ufficio=str(payload.get("codice_ufficio") or selection.get("ufficio_codice") or "").strip(),
                nome_ufficio=str(payload.get("nome_ufficio") or selection.get("ufficio_nome") or "").strip(),
            )
        from pct.sigit import FascicoloSIGIT

        return FascicoloSIGIT(
            numero_rgt=str(payload.get("numero_rgt") or selection.get("numero") or "").strip(),
            anno_rgt=int(payload.get("anno_rgt") or selection.get("anno") or 0),
            tipo=str(payload.get("tipo") or selection.get("procedimento") or "").strip(),
            stato=str(payload.get("stato") or selection.get("stato") or "").strip(),
            materia=str(payload.get("materia") or "").strip(),
            sezione=str(payload.get("sezione") or selection.get("sezione") or "").strip(),
            giudice_relatore=str(payload.get("giudice_relatore") or "").strip(),
            data_deposito=str(payload.get("data_deposito") or payload.get("data_iscrizione") or "").strip(),
            data_udienza=str(payload.get("data_udienza") or "").strip(),
            ricorrenti=list(payload.get("ricorrenti") or selection.get("parti") or []),
            resistenti=list(payload.get("resistenti") or selection.get("controparti") or []),
            oggetto_controversia=str(payload.get("oggetto_controversia") or selection.get("oggetto") or "").strip(),
            valore_controversia=float(payload.get("valore_controversia") or 0),
            note=str(payload.get("note") or "").strip(),
            codice_commissione=str(payload.get("codice_commissione") or selection.get("ufficio_codice") or "").strip(),
            nome_commissione=str(payload.get("nome_commissione") or selection.get("ufficio_nome") or "").strip(),
        )

    def _documents_to_portale_dataclasses(portale: str, rows: list[dict]) -> list[Any]:
        docs = _normalize_portale_documents(rows)
        if portale != "pst":
            return []
        from pct.polisWeb import DocumentoPolisWeb

        return [
            DocumentoPolisWeb(
                id_documento=row["id_documento"],
                nome=row["nome"],
                tipo=row["tipo"],
                data_deposito=row["data_deposito"],
                mittente=row["mittente"],
                dimensione_bytes=row["dimensione_bytes"],
                disponibile=row["disponibile"],
                id_deposito=row["id_deposito"],
                tipo_atto=row["tipo_atto"],
            )
            for row in docs
        ]

    def _sync_portale_metadata_on_fascicolo(
        portale: str,
        id_fasc: str,
        preview: dict[str, Any],
        registrato_da: str = "",
    ) -> int:
        gf = get_fascicoli()
        synced = 0
        for deposito in list(preview.get("depositi") or []):
            docs = list(deposito.get("documenti") or [])
            if not docs:
                continue
            gf.sincronizza_deposito_portale(
                id_fasc,
                fonte=_portale_source_name(portale),
                id_deposito_esterno=str(deposito.get("id_deposito") or "").strip(),
                tipo_atto=str(deposito.get("tipo_atto") or "").strip(),
                data_deposito=str(deposito.get("data_deposito") or "").strip(),
                mittente=str(deposito.get("mittente") or "").strip(),
                documenti_portale=docs,
                registrato_da=registrato_da,
                note=f"Catalogo ufficiale importato da {_portale_source_name(portale)}",
                nome_atto_principale=str((docs[0] or {}).get("nome") or "").strip(),
                stato="IMPORTATO_DA_PORTALE",
                servizio_portale="DocumentiFascicolo",
            )
            synced += 1
        return synced

    def _sync_udienza_e_scadenza(
        id_fasc: str,
        preview: dict[str, Any],
        *,
        crea_attivita: bool,
        crea_scadenza: bool,
        avvocato: str = "",
    ) -> dict[str, int]:
        gf = get_fascicoli()
        gs = get_scadenziario()
        fasc = gf.get(id_fasc)
        if not fasc:
            return {"attivita": 0, "scadenze": 0}
        data_udienza = str(preview.get("identity", {}).get("data_udienza") or "").strip()
        if not data_udienza:
            return {"attivita": 0, "scadenze": 0}
        created = {"attivita": 0, "scadenze": 0}
        if crea_attivita:
            exists = any(att.tipo == TipoAttivita.UDIENZA and att.data == data_udienza for att in fasc.attivita)
            if not exists:
                gf.aggiungi_attivita(
                    id_fasc,
                    tipo=TipoAttivita.UDIENZA,
                    data=data_udienza,
                    titolo="Udienza sincronizzata da portale",
                    descrizione=f"Evento importato da {fasc.source or 'portale'}",
                    avvocato=avvocato,
                )
                created["attivita"] += 1
        if crea_scadenza:
            exists = [
                sc for sc in gs.tutte(id_fascicolo=id_fasc, solo_aperte=False)
                if sc.data_scadenza == data_udienza and "udienza" in sc.titolo.lower()
            ]
            if not exists:
                gs.nuova(
                    titolo="Udienza da portale",
                    tipo=TipoTermine.UDIENZA,
                    data_scadenza=data_udienza,
                    id_fascicolo=id_fasc,
                    descrizione=f"Scadenza generata da sincronizzazione {fasc.source or 'portale'}",
                    id_utente_responsabile=getattr(g.utente_corrente, "id", "") if getattr(g, "utente_corrente", None) else "",
                )
                created["scadenze"] += 1
        return created

    def _update_fascicolo_sync_metadata(
        id_fasc: str,
        *,
        portale: str,
        selection: dict[str, Any],
        import_log_id: str,
        has_conflicts: bool,
        document_sync_enabled: bool,
        events_sync_enabled: bool,
        sync_status: str,
    ) -> Fascicolo:
        return get_fascicoli().aggiorna(
            id_fasc,
            source=_portale_source_name(portale),
            source_external_id=str(selection.get("external_id") or "").strip(),
            last_sync_at=datetime.now().isoformat(),
            sync_status=sync_status,
            import_log_id=import_log_id,
            has_conflicts=has_conflicts,
            document_sync_enabled=document_sync_enabled,
            events_sync_enabled=events_sync_enabled,
        )

    def _selection_preview_from_existing_fascicolo_telematico(fasc: Fascicolo) -> tuple[str, dict[str, Any], dict[str, Any]]:
        source_map = {
            "PST": "pst",
            "PDP": "pdp",
            "PAT": "pat",
            "PTT": "ptt",
        }
        portale = source_map.get(str(getattr(fasc, "source", "") or "").strip().upper(), "")
        if not portale:
            return "", {}, {}
        documenti: list[dict[str, Any]] = []
        for dep in list(getattr(fasc, "depositi_pct", []) or []):
            if getattr(dep, "documenti_portale", None):
                documenti.extend(list(dep.documenti_portale or []))
        if not documenti:
            for doc in list(getattr(fasc, "documenti", []) or []):
                if not str(getattr(doc, "id_deposito_pct", "") or "").strip():
                    continue
                documenti.append(
                    {
                        "id_documento": str(doc.id),
                        "nome": str(doc.nome or "").strip(),
                        "tipo": getattr(getattr(doc, "tipo", None), "value", ""),
                        "data_deposito": str(getattr(doc, "data_documento", "") or "").strip(),
                        "mittente": str(fasc.avvocato_referente or fasc.avvocato_dominus or "").strip(),
                        "dimensione_bytes": int(getattr(doc, "dimensione_bytes", 0) or 0),
                        "disponibile": True,
                        "id_deposito": str(getattr(doc, "id_deposito_pct", "") or "").strip(),
                        "tipo_atto": "",
                    }
                )
        selection = {
            "external_id": str(getattr(fasc, "source_external_id", "") or "").strip()
            or f"{fasc.tribunale}:{fasc.numero_rg}:{fasc.anno_rg}:{fasc.tipo_procedimento or getattr(getattr(fasc, 'tipo', None), 'value', '')}",
            "numero": str(getattr(fasc, "numero_rg", "") or "").strip(),
            "anno": int(getattr(fasc, "anno_rg", 0) or 0),
            "ufficio_codice": "",
            "ufficio_nome": str(getattr(fasc, "tribunale", "") or "").strip(),
            "procedimento": str(getattr(fasc, "tipo_procedimento", "") or getattr(getattr(fasc, "tipo", None), "value", "")).strip(),
            "sezione": str(getattr(fasc, "sezione", "") or "").strip(),
            "stato": str(getattr(fasc, "sync_status", "") or getattr(getattr(fasc, "stato", None), "value", "")).strip(),
            "oggetto": str(getattr(fasc, "oggetto", "") or "").strip(),
            "parti": [str(getattr(fasc, "nome_cliente", "") or "").strip()] if str(getattr(fasc, "nome_cliente", "") or "").strip() else [],
            "controparti": [str(getattr(fasc, "controparte", "") or "").strip()] if str(getattr(fasc, "controparte", "") or "").strip() else [],
            "ultima_attivita": str(getattr(fasc, "last_sync_at", "") or getattr(fasc, "modificato_il", "") or "").strip(),
            "payload": {},
        }
        preview = _build_portale_preview(portale, selection, documenti)
        return portale, selection, preview

    def _sync_telematico_case_from_portale(
        portale: str,
        *,
        id_fasc: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        import_log_id: str = "",
        sync_status: str = "",
        document_sync_enabled: bool = False,
        workflow_url: str = "",
        user_name: str = "",
        backfill: bool = False,
    ) -> dict[str, Any]:
        fasc = get_fascicoli().get(id_fasc)
        if not fasc:
            return {}
        repo = get_telematico()
        cfg = get_config_studio().config
        identity = dict((preview or {}).get("identity") or {})
        native_status = str(identity.get("stato") or selection.get("stato") or "").strip().upper()
        has_documents = int((preview.get("counts") or {}).get("documenti", 0) or 0) > 0
        portal_case_ref = str(selection.get("external_id") or getattr(fasc, "source_external_id", "") or "").strip()
        existing_case = repo.find_case(
            practice_id=id_fasc,
            service_code=_telematico_service_code(portale),
            portal_case_ref=portal_case_ref or None,
            office_name=str(selection.get("ufficio_nome") or getattr(fasc, "tribunale", "") or "").strip() or None,
            register_type=str(selection.get("procedimento") or getattr(fasc, "tipo_procedimento", "") or "").strip() or None,
            register_number=str(selection.get("numero") or getattr(fasc, "numero_rg", "") or "").strip() or None,
            register_year=int(selection.get("anno") or getattr(fasc, "anno_rg", 0) or 0) or None,
        )
        counsel_name = (
            str(getattr(fasc, "avvocato_referente", "") or "").strip()
            or str(getattr(fasc, "avvocato_dominus", "") or "").strip()
            or str(getattr(cfg.studio, "nome_avvocato", "") or "").strip()
            or str(user_name or "").strip()
        )
        counsel_cf = (
            str(getattr(cfg.firma, "cf_avvocato", "") or "").strip().upper()
            or str(getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper()
        )
        case = repo.upsert_case(
            id=str((existing_case or {}).get("id") or "").strip() or None,
            practice_id=id_fasc,
            channel_family=_telematico_channel_family(portale),
            service_code=_telematico_service_code(portale),
            office_name=str(selection.get("ufficio_nome") or getattr(fasc, "tribunale", "") or "").strip() or "Ufficio da completare",
            office_type="",
            district="",
            register_type=str(selection.get("procedimento") or getattr(fasc, "tipo_procedimento", "") or "").strip(),
            register_number=str(selection.get("numero") or getattr(fasc, "numero_rg", "") or "").strip(),
            register_year=int(selection.get("anno") or getattr(fasc, "anno_rg", 0) or 0),
            subject_name=str((selection.get("parti") or [getattr(fasc, "nome_cliente", "")])[0] or getattr(fasc, "nome_cliente", "")).strip() or "Parte non definita",
            subject_cf="",
            counterparty_name=str((selection.get("controparti") or [getattr(fasc, "controparte", "")])[0] or getattr(fasc, "controparte", "")).strip(),
            counsel_name=counsel_name or "Difensore da completare",
            counsel_cf=counsel_cf or "N/D",
            portal_case_ref=portal_case_ref or None,
            portal_case_url="",
            workflow_url=workflow_url or None,
            internal_status=_telematico_internal_status(
                sync_status=sync_status or getattr(fasc, "sync_status", ""),
                native_status=native_status,
                has_documents=has_documents,
                documents_imported=bool(document_sync_enabled),
                needs_manual_review=bool(getattr(fasc, "has_conflicts", False)),
            ),
            native_status=native_status or None,
            import_log_id=import_log_id or getattr(fasc, "import_log_id", "") or None,
            notes=str(getattr(fasc, "note", "") or "").strip() or None,
            last_sync_at=str(getattr(fasc, "last_sync_at", "") or datetime.now().isoformat()),
        )
        if not (backfill and existing_case):
            repo.add_event(
                str(case["id"]),
                event_type="telematico_sync",
                event_source="import" if not backfill else "system",
                title=f"{_portale_source_name(portale)} sincronizzato nel core telematico",
                description=f"Pratica {getattr(fasc, 'numero', '')} allineata con il canale {_portale_source_name(portale)}.",
                payload_json={
                    "practice_id": id_fasc,
                    "import_log_id": import_log_id,
                    "documents": int((preview.get('counts') or {}).get('documenti', 0) or 0),
                },
                created_by_user_id=getattr(getattr(g, "utente_corrente", None), "id", "") or None,
            )
        depositi = list(preview.get("depositi") or [])
        if not depositi and list(preview.get("documenti") or []):
            depositi = _group_portale_documents(list(preview.get("documenti") or []))
        for deposito in depositi:
            transmission = repo.upsert_transmission(
                str(case["id"]),
                transmission_type="case_import",
                act_type=str(deposito.get("tipo_atto") or "Deposito ufficiale").strip(),
                portal_reference=str(deposito.get("id_deposito") or import_log_id or portal_case_ref or "").strip() or None,
                internal_status=_telematico_transmission_status(native_status, has_documents=bool(deposito.get("documenti"))),
                native_status=native_status or None,
                submitted_at=str(deposito.get("data_deposito") or identity.get("data_iscrizione") or "").strip() or None,
                outcome_at=str(identity.get("ultima_attivita") or deposito.get("data_deposito") or "").strip() or None,
                notes=f"Catalogo {_portale_source_name(portale)} allineato nel core telematico.",
            )
            for doc in list(deposito.get("documenti") or []):
                doc_ref = str(doc.get("id_cat") or doc.get("id_documento") or "").strip()
                tele_doc = repo.upsert_document(
                    str(case["id"]),
                    document_role=_telematico_document_role(doc),
                    document_category=str(doc.get("tipo") or "").strip() or None,
                    title=str(doc.get("nome") or "Documento ufficiale").strip(),
                    original_filename=str(doc.get("nome") or "").strip() or None,
                    file_size_bytes=int(doc.get("dimensione_bytes") or 0) or None,
                    source_type="portal",
                    signed=1 if str(doc.get("nome") or "").lower().endswith(".p7m") else 0,
                    portal_document_ref=doc_ref or None,
                    portal_document_date=str(doc.get("data_deposito") or "").strip() or None,
                    id_deposito=str(deposito.get("id_deposito") or "").strip(),
                    tipo_atto=str(deposito.get("tipo_atto") or doc.get("tipo_atto") or "").strip(),
                    data_deposito=str(doc.get("data_deposito") or deposito.get("data_deposito") or "").strip() or None,
                    mittente=str(doc.get("mittente") or deposito.get("mittente") or "").strip() or None,
                    notes=f"Documento censito da {_portale_source_name(portale)}.",
                )
                repo.link_document_to_transmission(
                    str(transmission["id"]),
                    str(tele_doc["id"]),
                    relation_type="main_act" if tele_doc.get("document_role") == "main_act" else "attachment",
                )
        if has_documents and not document_sync_enabled:
            repo.ensure_task(
                str(case["id"]),
                task_type="download_case_file",
                title="Completare acquisizione documenti dal portale ufficiale",
                description=f"Il fascicolo {_portale_source_name(portale)} ha documenti censiti ma non ancora integrati nel fascicolo locale.",
                priority="high",
                assigned_user_id=getattr(getattr(g, "utente_corrente", None), "id", "") or "",
            )
        else:
            repo.close_tasks(str(case["id"]), task_type="download_case_file")
        return case

    def _backfill_telematico_from_existing_fascicoli() -> dict[str, int]:
        summary = {"processed": 0, "failed": 0}
        for fasc in get_fascicoli().tutti():
            if str(getattr(fasc, "source", "") or "").strip().upper() not in {"PST", "PDP", "PAT", "PTT"}:
                continue
            portale, selection, preview = _selection_preview_from_existing_fascicolo_telematico(fasc)
            if not portale or not selection:
                continue
            try:
                _sync_telematico_case_from_portale(
                    portale,
                    id_fasc=fasc.id,
                    selection=selection,
                    preview=preview,
                    import_log_id=str(getattr(fasc, "import_log_id", "") or ""),
                    sync_status=str(getattr(fasc, "sync_status", "") or ""),
                    document_sync_enabled=bool(getattr(fasc, "document_sync_enabled", False)),
                    user_name=getattr(getattr(g, "utente_corrente", None), "username", "") or "",
                    backfill=True,
                )
                summary["processed"] += 1
            except Exception as e:
                summary["failed"] += 1
                app.logger.exception(
                    "Errore backfill telematico fascicolo %s (%s): %s",
                    getattr(fasc, "id", ""),
                    getattr(fasc, "numero", ""),
                    e,
                )
        return summary

    def _telematico_dashboard_warning_message(error: Exception) -> str:
        message = str(error).strip().lower()
        if "archivio telematico temporaneamente non disponibile" in message or "database or disk is full" in message:
            return (
                "Archivio telematico temporaneamente non disponibile. IUSENTRA ha messo in pausa "
                "l'aggiornamento SQLite e continuera' a riprovare automaticamente."
            )
        if "temporaneamente occupato" in message or "database is locked" in message:
            return (
                "Archivio telematico temporaneamente occupato da un aggiornamento in corso. "
                "La pagina resta disponibile e il sistema riprovera' automaticamente."
            )
        return (
            "Cabina telematica disponibile in modalita' ridotta. "
            "Il sistema ha intercettato un errore tecnico e continuera' a lavorare in sicurezza."
        )

    def _importa_o_collega_fascicolo_portale(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        options: dict[str, bool],
        mapping: dict[str, str],
        downloaded_files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        user_name = getattr(getattr(g, "utente_corrente", None), "username", "") or ""
        selection_dc = _selection_to_fascicolo_dataclass(portale, selection)
        analysis = _analyze_portale_import(portale, selection, preview, options, mapping)
        if analysis["blockers"]:
            raise ValueError("Sono presenti blocchi da risolvere prima dell'importazione.")

        preview_for_files = _filter_portale_preview_by_options(preview, options)
        importa_file_portale = _preview_richiede_file_portale(options)
        files = list(downloaded_files or [])
        counts = preview_for_files.get("counts") or {}
        documenti_attesi = int(counts.get("documenti", 0) or 0)
        selected_doc_ids = {
            str(doc.get("id_documento") or "").strip()
            for doc in list(preview_for_files.get("documenti") or [])
            if str(doc.get("id_documento") or "").strip()
        }
        decoded_items: list[dict[str, Any]] = []
        if importa_file_portale and portale == "pst" and documenti_attesi > 0:
            if not files:
                raise ValueError(
                    "Hai scelto di importare i documenti, ma il wizard non ha ricevuto alcun file scaricato dal portale. "
                    "Riprova l'acquisizione con download batch attivo."
                )
            decoded_items = _decode_portale_downloaded_items(files)
            if selected_doc_ids:
                decoded_items = [
                    item
                    for item in decoded_items
                    if str(item.get("id_documento_portale") or "").strip() in selected_doc_ids
                ]
            if not decoded_items:
                raise ValueError("Il lotto scaricato dal portale non contiene file importabili.")

        log_id = _append_portale_import_log(
            {
                "portale": _portale_source_name(portale),
                "selection": selection,
                "preview_counts": preview.get("counts") or {},
                "options": options,
                "mapping": mapping,
                "analysis": analysis,
                "utente": user_name,
            }
        )

        gf = get_fascicoli()
        gc = get_clienti()
        gsog = get_soggetti()
        mode, resolved_target, auto_integrated = _resolve_portale_import_target(portale, selection, mapping)
        id_fasc = ""
        created = False

        if mode == "create_new":
            if portale == "pst":
                from pct.polisWeb import ClientPolisWebImportOnly, crea_client

                if _portale_local_channel_enabled(portale):
                    client = ClientPolisWebImportOnly()
                else:
                    client = crea_client(demo=_portale_demo_mode(portale))
                documenti_pw = _documents_to_portale_dataclasses(portale, preview_for_files.get("documenti") or []) if importa_file_portale else None
                risultato = client.importa_fascicolo(
                    fascicolo_pw=selection_dc,
                    gestione_fascicoli=gf,
                    gestione_clienti=gc,
                    avvocato_referente=user_name,
                    gestione_soggetti=gsog,
                    documenti_pw=documenti_pw,
                )
            elif portale == "pdp":
                if _portale_local_channel_enabled(portale):
                    from pct.pdp import ClientPDP

                    client = ClientPDP(
                        codice_fiscale_avvocato=str(
                            getattr(get_config_studio().config.firma, "cf_avvocato", "") or ""
                        ).strip().upper()
                    )
                else:
                    from pct.pdp import crea_client_pdp

                    client = crea_client_pdp(demo=_portale_demo_mode(portale))
                risultato = client.importa_fascicolo(selection_dc, gf, gc, user_name)
            elif portale == "pat":
                if _portale_local_channel_enabled(portale):
                    from pct.pat import ClientPAT

                    client = ClientPAT(
                        codice_fiscale_avvocato=str(
                            getattr(get_config_studio().config.firma, "cf_avvocato", "") or ""
                        ).strip().upper()
                    )
                else:
                    from pct.pat import crea_client_pat

                    client = crea_client_pat(demo=_portale_demo_mode(portale))
                risultato = client.importa_fascicolo(selection_dc, gf, gc, user_name)
            else:
                if _portale_local_channel_enabled(portale):
                    from pct.sigit import ClientSIGIT

                    client = ClientSIGIT(
                        codice_fiscale_avvocato=str(
                            getattr(get_config_studio().config.firma, "cf_avvocato", "") or ""
                        ).strip().upper()
                    )
                else:
                    from pct.sigit import crea_client_sigit

                    client = crea_client_sigit(demo=_portale_demo_mode(portale))
                risultato = client.importa_fascicolo(selection_dc, gf, gc, user_name)
            if not risultato.successo or not risultato.id_fascicolo_locale:
                raise ValueError(risultato.messaggio or "Importazione non riuscita.")
            id_fasc = risultato.id_fascicolo_locale
            created = True
        else:
            target = resolved_target
            if not target:
                raise ValueError("Fascicolo locale selezionato non trovato.")
            if portale == "pst":
                from pct.polisWeb import ClientPolisWebImportOnly, crea_client

                if _portale_local_channel_enabled(portale):
                    client = ClientPolisWebImportOnly()
                else:
                    client = crea_client(demo=_portale_demo_mode(portale))
                documenti_pw = _documents_to_portale_dataclasses(portale, preview_for_files.get("documenti") or []) if importa_file_portale else None
                risultato = client.sincronizza_fascicolo_esistente(
                    fascicolo_pw=selection_dc,
                    fascicolo_locale=target,
                    gestione_fascicoli=gf,
                    gestione_clienti=gc,
                    avvocato_referente=user_name,
                    gestione_soggetti=gsog,
                    documenti_pw=documenti_pw,
                )
                if not risultato.successo or not risultato.id_fascicolo_locale:
                    raise ValueError(risultato.messaggio or "Sincronizzazione PST non riuscita.")
                id_fasc = risultato.id_fascicolo_locale
            else:
                target = _sync_existing_fascicolo_from_portale(
                    portale,
                    target,
                    selection,
                    preview,
                    preserve_blank=options.get("sovrascrivi_solo_vuoti", True),
                    append_import_note=not options.get("non_toccare_note_interne", True),
                    user_name=user_name,
                    log_id=log_id,
                )
                id_fasc = target.id

        import_result: dict[str, Any] = {
            "documenti_importati": 0,
            "depositi_agganciati": [],
            "lotto_generico": "",
            "staging_archived": "",
        }
        albero_originale_salvato = ""
        if importa_file_portale:
            _sync_portale_metadata_on_fascicolo(portale, id_fasc, preview_for_files, registrato_da=user_name)
            if files:
                fasc_import = gf.get(id_fasc)
                if not fasc_import:
                    raise ValueError("Fascicolo importato non trovato durante l'acquisizione documenti.")
                if not decoded_items:
                    decoded_items = _decode_portale_downloaded_items(files)
                    if selected_doc_ids:
                        decoded_items = [
                            item
                            for item in decoded_items
                            if str(item.get("id_documento_portale") or "").strip() in selected_doc_ids
                        ]
                if not decoded_items:
                    raise ValueError("Il lotto scaricato dal portale non contiene file importabili.")
                if options.get("mantieni_albero_originale"):
                    albero_originale_salvato = _salva_albero_originale_documenti_portale(fasc_import, decoded_items)
                import_result = _importa_documenti_portale_items(
                    gf=gf,
                    fasc=fasc_import,
                    items=decoded_items,
                    note_importazione=f"Acquisizione guidata da {_portale_source_name(portale)}",
                )
            elif portale == "pst" and documenti_attesi > 0:
                raise ValueError(
                    "Hai scelto di importare i documenti, ma il wizard non ha ricevuto alcun file scaricato dal portale. "
                    "Riprova l'acquisizione con download batch attivo."
                )

        udienza_result = _sync_udienza_e_scadenza(
            id_fasc,
            preview,
            crea_attivita=options.get("importa_eventi") or options.get("importa_udienze"),
            crea_scadenza=options.get("importa_scadenze", False),
            avvocato=user_name,
        )

        _update_fascicolo_sync_metadata(
            id_fasc,
            portale=portale,
            selection=selection,
            import_log_id=log_id,
            has_conflicts=bool(analysis["warnings"]),
            document_sync_enabled=importa_file_portale,
            events_sync_enabled=options.get("importa_eventi", False) or options.get("importa_udienze", False),
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
        )

        workflow_url = ""
        if portale == "pdp":
            case = _ensure_pdp_penale_case_after_import(
                id_fasc=id_fasc,
                selection=selection,
                preview=preview,
                user_name=user_name,
                imported_documents=int(import_result.get("documenti_importati", 0) or 0),
                downloaded_files=decoded_items or files,
            )
            if case:
                workflow_url = url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case["id"])

        _sync_telematico_case_from_portale(
            portale,
            id_fasc=id_fasc,
            selection=selection,
            preview=preview_for_files if preview_for_files else preview,
            import_log_id=log_id,
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
            document_sync_enabled=bool(importa_file_portale),
            workflow_url=workflow_url,
            user_name=user_name,
        )

        fasc = gf.get(id_fasc)
        return {
            "id_fascicolo": id_fasc,
            "created": created,
            "resolved_mode": mode,
            "auto_integrated": auto_integrated,
            "import_log_id": log_id,
            "quadro_url": url_for("quadro_fascicolo", id_fasc=id_fasc),
            "dettaglio_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc),
            "scadenziario_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-udienze-scadenze",
            "timeline_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-attivita-processuali",
            "documenti_url": url_for("dettaglio_fascicolo", id_fasc=id_fasc) + "#sezione-documenti-fascicolo",
            "workflow_url": workflow_url,
            "summary": {
                "numero_pratica": getattr(fasc, "numero", ""),
                "titolo": getattr(fasc, "titolo", ""),
                "documenti": int(import_result.get("documenti_importati", 0) or 0),
                "depositi": len(import_result.get("depositi_agganciati") or [])
                or int(preview.get("counts", {}).get("depositi", 0) or 0),
                "scadenze_generate": udienza_result["scadenze"],
                "eventi_generati": udienza_result["attivita"],
                "conflitti_risolti": len(analysis["warnings"]),
                "lotto_generico": str(import_result.get("lotto_generico") or ""),
                "modalita_documento_portale": "originale" if options.get("scarica_originale_portale", True) else "copia",
                "albero_originale_salvato": bool(albero_originale_salvato),
            },
        }

    def _register_direct_portale_import_sync(
        portale: str,
        selection: dict[str, Any],
        preview: dict[str, Any],
        *,
        id_fasc: str,
        created: bool,
        user_name: str,
    ) -> str:
        log_id = _append_portale_import_log(
            {
                "portale": _portale_source_name(portale),
                "selection": selection,
                "preview_counts": preview.get("counts") or {},
                "options": {"direct_import": True},
                "mapping": {"mode": "create_new"},
                "analysis": {},
                "utente": user_name,
            }
        )
        fasc = get_fascicoli().get(id_fasc)
        if not fasc:
            return log_id
        _update_fascicolo_sync_metadata(
            id_fasc,
            portale=portale,
            selection=selection,
            import_log_id=log_id,
            has_conflicts=False,
            document_sync_enabled=False,
            events_sync_enabled=False,
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
        )
        if portale == "pdp":
            case = _ensure_pdp_penale_case_after_import(
                id_fasc=id_fasc,
                selection=selection,
                preview=preview,
                user_name=user_name,
                imported_documents=0,
                downloaded_files=[],
            )
            workflow_url = url_for("pdp_penale_workspace", id_fasc=id_fasc, case_id=case["id"]) if case else ""
        else:
            workflow_url = ""
        _sync_telematico_case_from_portale(
            portale,
            id_fasc=id_fasc,
            selection=selection,
            preview=preview,
            import_log_id=log_id,
            sync_status="IMPORTATO" if created else "SINCRONIZZATO",
            document_sync_enabled=False,
            workflow_url=workflow_url,
            user_name=user_name,
        )
        return log_id

    def _build_access_status_payload(portale: str) -> dict[str, Any]:
        spec = _spec_portale_acquisizione(portale)
        cfg = get_config_studio().config
        firma_cfg = cfg.firma
        auth_mode = _polis_auth_mode()
        browser_channel_required = _portale_browser_channel_required(portale)
        demo_mode = _portale_demo_mode(portale)
        pkcs11_mode = _portale_usa_local_signer(portale) and not demo_mode
        ultimo_log = _last_portale_import_log(portale)
        if browser_channel_required:
            if portale == "pat":
                status_text = "Consultazione via Portale dell'Avvocato"
            elif portale == "pdp":
                status_text = "Consultazione via PDP Penale ufficiale"
            elif portale == "ptt":
                status_text = "Consultazione via PTT / SIGIT"
            else:
                status_text = "Consultazione via browser ufficiale"
            environment_label = "Produzione guidata assistita"
        elif demo_mode:
            status_text = "Modalita demo / fallback"
            environment_label = "Simulazione / compatibilita"
        elif pkcs11_mode:
            status_text = "Accesso via Local Signer / Aruba Key"
            environment_label = "Produzione guidata via browser locale"
        else:
            status_text = "Connessione pronta"
            environment_label = "Produzione guidata"
        return {
            "portale": portale,
            "spec": spec,
            "avvocato": str(getattr(cfg.studio, "nome_avvocato", "") or getattr(g.utente_corrente, "username", "") or "").strip(),
            "codice_fiscale_avvocato": str(getattr(firma_cfg, "cf_avvocato", "") or getattr(cfg.studio, "codice_fiscale_avvocato", "") or "").strip().upper(),
            "backend_firma": str(getattr(firma_cfg, "backend_firma_effettivo_safe", "nessuno") or "").strip(),
            "auth_mode": auth_mode,
            "demo_mode": demo_mode,
            "pkcs11_mode": pkcs11_mode,
            "browser_channel_required": browser_channel_required,
            "cert_preferences": _polis_cert_preferences() if (pkcs11_mode or browser_channel_required) else {},
            "status_text": status_text,
            "test_ok": not demo_mode,
            "last_sync_at": str(ultimo_log.get("created_at") or "").strip(),
            "last_import_log_id": str(ultimo_log.get("id") or "").strip(),
            "environment_label": environment_label,
        }

    def _search_fascicoli_portale_server(portale: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        portale = (portale or "").strip().lower()
        numero = str(query.get("numero") or "").strip() or None
        anno_raw = str(query.get("anno") or "").strip()
        anno = int(anno_raw) if anno_raw.isdigit() else None
        assistito = str(query.get("assistito") or "").strip() or None
        controparte = str(query.get("controparte") or "").strip() or None
        cf = str(query.get("cf") or "").strip() or None
        oggetto = str(query.get("oggetto") or "").strip().lower()
        stato_filter = str(query.get("stato") or "").strip().lower()
        quick = str(query.get("quick_filter") or "").strip().lower()

        try:
            if portale == "pst":
                if _portale_local_channel_enabled(portale):
                    raise ValueError("Per PST la ricerca guidata usa il Local Signer dal browser.")
                from pct.polisWeb import crea_client

                ufficio = str(query.get("ufficio_codice") or "").strip()
                if not ufficio:
                    raise ValueError("Seleziona un ufficio giudiziario.")
                fascicoli = crea_client(demo=_portale_demo_mode(portale)).ricerca_fascicoli(
                    tribunale=ufficio,
                    numero_rg=numero,
                    anno_rg=anno,
                    nome_parte=assistito or controparte,
                    codice_fiscale_parte=cf,
                )
            elif portale == "pdp":
                if _portale_browser_channel_required(portale):
                    raise ValueError(_portale_browser_guided_message(portale))
                if _portale_usa_local_signer(portale):
                    raise ValueError("Per PDP Penale la ricerca guidata usa il Local Signer dal browser.")
                from pct.pdp import crea_client_pdp

                ufficio = str(query.get("ufficio_codice") or "").strip()
                if not ufficio:
                    raise ValueError("Seleziona un ufficio giudiziario.")
                fascicoli = crea_client_pdp(demo=_portale_demo_mode(portale)).ricerca_fascicoli(
                    ufficio=ufficio,
                    numero_rg=numero,
                    anno_rg=anno,
                    nome_imputato=assistito,
                    tipo_registro=str(query.get("registro") or "").strip() or None,
                )
            elif portale == "pat":
                raise ValueError(
                    "Per PAT l'acquisizione guidata non promette una ricerca live diretta da SIGA. "
                    "Apri il Portale dell'Avvocato ufficiale dal browser e usa IUSENTRA per il fascicolo interno, "
                    "le ricevute e l'import guidato dei file gia scaricati."
                )
            else:
                raise ValueError(
                    "Per PTT / SIGIT l'acquisizione guidata non promette una ricerca live diretta del fascicolo. "
                    "Apri il portale ufficiale o Telecontenzioso nel browser, consulta il fascicolo processuale e "
                    "poi usa IUSENTRA per il fascicolo tributario interno e per l'import guidato dei file gia scaricati."
                )
        except Exception as e:
            if _is_portale_dns_error(e):
                raise ValueError(_portale_browser_guided_message(portale)) from e
            raise

        rows = [_serialize_portale_search_item(portale, fascicolo) for fascicolo in fascicoli]
        if oggetto:
            rows = [row for row in rows if oggetto in str(row.get("oggetto") or "").lower()]
        if stato_filter:
            rows = [row for row in rows if stato_filter in str(row.get("stato") or "").lower()]
        if quick:
            rows = [
                row for row in rows
                if quick in str(row.get("procedimento") or "").lower()
                or quick in str(row.get("oggetto") or "").lower()
                or quick in str(row.get("stato") or "").lower()
            ]
        return rows

    def _preview_documenti_portale_server(portale: str, selection: dict[str, Any]) -> list[dict]:
        portale = (portale or "").strip().lower()
        try:
            if portale == "pst":
                if _portale_local_channel_enabled(portale):
                    raise ValueError("Anteprima documenti PST via browser locale richiesta.")
                from pct.polisWeb import crea_client

                docs = crea_client(demo=_portale_demo_mode(portale)).consulta_documenti(
                    str(selection.get("ufficio_codice") or "").strip(),
                    str(selection.get("numero") or "").strip(),
                    int(selection.get("anno") or 0),
                )
            elif portale == "pdp":
                if _portale_browser_channel_required(portale):
                    raise ValueError(_portale_browser_guided_message(portale))
                if _portale_usa_local_signer(portale):
                    raise ValueError("Anteprima documenti PDP via browser locale richiesta.")
                from pct.pdp import crea_client_pdp

                docs = crea_client_pdp(demo=_portale_demo_mode(portale)).consulta_documenti(
                    str(selection.get("ufficio_codice") or "").strip(),
                    str(selection.get("numero") or "").strip(),
                    int(selection.get("anno") or 0),
                )
            elif portale == "pat":
                raise ValueError(
                    "Per PAT la consultazione del fascicolo si completa nel Portale dell'Avvocato ufficiale. "
                    "In IUSENTRA puoi continuare con il fascicolo PAT interno e con l'import guidato di documenti, "
                    "provvedimenti e ricevute gia scaricati dal portale."
                )
            else:
                raise ValueError(
                    "Per PTT / SIGIT la consultazione del fascicolo si completa nel portale ufficiale e nei servizi "
                    "collegati, come Telecontenzioso. In IUSENTRA prosegui con il fascicolo tributario interno e con "
                    "l'import guidato di documenti, ricevute, provvedimenti ed esiti gia scaricati."
                )
        except Exception as e:
            if _is_portale_dns_error(e):
                raise ValueError(_portale_browser_guided_message(portale)) from e
            raise
        return [dict(vars(doc)) for doc in docs]

    def _local_signer_tools_dir() -> Path:
        return Path(__file__).resolve().parents[2] / "tools"

    def _local_signer_dist_dir() -> Path:
        return _local_signer_tools_dir() / "dist"

    def _local_signer_source_path() -> Path:
        return _local_signer_tools_dir() / "local_signer.py"

    def _local_ai_bridge_source_path() -> Path:
        return _local_signer_tools_dir() / "local_ai_host_bridge.py"

    def _local_ai_lex_context_source_path() -> Path:
        return _local_signer_tools_dir() / "lex_document_context.py"

    def _local_signer_visible_signature_source_path() -> Path:
        return Path(__file__).resolve().parents[2] / "visible_signature.py"

    def _local_signer_version() -> str:
        source = _local_signer_source_path().read_text(encoding="utf-8")
        match = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', source)
        if not match:
            raise ValueError("Versione Local Signer non trovata in tools/local_signer.py")
        return match.group(1)

    def _local_signer_windows_cmd_name() -> str:
        return f"SetupLocalSigner-{_local_signer_version()}.cmd"

    def _local_signer_windows_cmd_path() -> Path:
        return _local_signer_dist_dir() / _local_signer_windows_cmd_name()

    def _local_signer_windows_exe_name() -> str:
        return f"SetupLocalSigner-{_local_signer_version()}.exe"

    def _local_signer_windows_ps1_name() -> str:
        return f"InstallaLocalSigner-{_local_signer_version()}.ps1"

    def _local_signer_windows_offline_ps1_name() -> str:
        """PS1 offline self-contained (generato da build_dist.py) — alternativa all'EXE."""
        return f"SetupLocalSigner-{_local_signer_version()}.ps1"

    def _local_signer_windows_offline_ps1_path() -> Path:
        return _local_signer_dist_dir() / _local_signer_windows_offline_ps1_name()

    def _local_signer_macos_name() -> str:
        return f"InstallaLocalSigner-{_local_signer_version()}.command"

    def _local_signer_linux_name() -> str:
        return f"InstallaLocalSigner-{_local_signer_version()}.run"

    def _local_signer_python_name() -> str:
        return f"local_signer-{_local_signer_version()}.py"

    def _local_ai_bridge_python_name() -> str:
        return f"local_ai_host_bridge-{_local_signer_version()}.py"

    def _local_ai_lex_context_python_name() -> str:
        return f"lex_document_context-{_local_signer_version()}.py"

    def _local_signer_visible_signature_python_name() -> str:
        return f"visible_signature-{_local_signer_version()}.py"

    def _local_signer_windows_exe_path() -> Path:
        # Restituisce solo il path dell'exe versionato (es. SetupLocalSigner-1.5.10.exe).
        # NON cade in fallback sul generico SetupLocalSigner.exe (potrebbe essere
        # una versione precedente) — se l'exe versionato non esiste il chiamante
        # deve usare la PS1 offline.
        return _local_signer_dist_dir() / _local_signer_windows_exe_name()

    def _local_signer_uffici_path() -> Path:
        return Path(__file__).resolve().parents[2] / "pct" / "data" / "uffici_ministero.json"

    def _local_signer_macos_installer_path() -> Path:
        preferred = _local_signer_dist_dir() / _local_signer_macos_name()
        legacy = _local_signer_dist_dir() / "InstallaLocalSigner.command"
        if preferred.exists():
            return preferred
        return legacy

    def _local_signer_linux_installer_path() -> Path:
        preferred = _local_signer_dist_dir() / _local_signer_linux_name()
        legacy_run = _local_signer_dist_dir() / "InstallaLocalSigner.run"
        legacy = _local_signer_dist_dir() / "installa_local_signer.sh"
        if preferred.exists():
            return preferred
        if legacy_run.exists():
            return legacy_run
        return legacy

    def _local_signer_allowed_origins(base_url: str) -> str:
        origini = {base_url.rstrip("/")}
        configured = os.getenv("PCT_BASE_URL", "").rstrip("/")
        if configured:
            origini.add(configured)
        origini.add("https://studio-legale-pct-production.up.railway.app")
        return ",".join(sorted(o for o in origini if o))

    def _render_local_signer_windows_ps1(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        version = _local_signer_version()
        return f"""# IUSENTRA Local Signer v{version} - Installazione automatica Windows
# Eseguire in PowerShell come utente normale (non richiede amministratore)
# Punto ufficiale download: https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma

$ErrorActionPreference = 'Stop'
$dir    = "$env:APPDATA\\IUSENTRA\\LocalSigner"
$venv   = "$dir\\.venv"
$py     = "$dir\\local_signer.py"
$aiBridge = "$dir\\local_ai_host_bridge.py"
$lexContext = "$dir\\lex_document_context.py"
$visibleSignature = "$dir\\visible_signature.py"
$dataDir = "$dir\\data"
$uffici = "$dataDir\\uffici_ministero.json"
$starterCmd = "$dir\\\\start_local_signer.cmd"
$starterVbs = "$dir\\\\start_local_signer.vbs"
$pyExe  = "$venv\\\\Scripts\\\\python.exe"
$pywExe = "$venv\\\\Scripts\\\\pythonw.exe"
$allowedOrigins = "{allowed_origins}"
$version = "{version}"

Write-Host "IUSENTRA Local Signer v$version - Installazione..." -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path $dir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

Write-Host "  Scarico local_signer.py..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download" -OutFile $py -UseBasicParsing
Write-Host "  Scarico bridge AI locale..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/local-ai-bridge" -OutFile $aiBridge -UseBasicParsing
Write-Host "  Scarico parser documenti per Lex..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/lex-document-context" -OutFile $lexContext -UseBasicParsing
Write-Host "  Scarico modulo firma visibile..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/visible-signature" -OutFile $visibleSignature -UseBasicParsing
Write-Host "  Scarico registro uffici PST..."
Invoke-WebRequest "{base_url}/polisWeb/local-signer/download/uffici" -OutFile $uffici -UseBasicParsing

try {{
    $v = python --version 2>&1
    Write-Host "  Python trovato: $v"
}} catch {{
    Write-Host "ERRORE: Python non trovato. Scaricarlo da https://python.org" -ForegroundColor Red
    Read-Host "Premere Invio per uscire"
    exit 1
}}

Write-Host "  Creo ambiente virtuale..."
python -m venv $venv

Write-Host "  Aggiorno pip..."
& $pyExe -m pip install --quiet --upgrade pip

Write-Host "  Installo dipendenze Local Signer..."
    & $pyExe -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf

function Test-LocalSignerOnline {{
    try {{
        $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping" -UseBasicParsing -TimeoutSec 2
        return [bool]$resp.ok
    }} catch {{
        return $false
    }}
}}

function Stop-LocalSignerProcesses {{
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {{
            $_.Name -in @("python.exe", "pythonw.exe") -and
            $_.CommandLine -and
            $_.CommandLine -like "*$py*"
        }} |
        ForEach-Object {{
            try {{
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
            }} catch {{
            }}
        }}
}}

Write-Host "  Preparo l'avvio contestuale da IUSENTRA..."
$cmd = @'
@echo off
setlocal
set "DIR=%~dp0"
set "PYW=%DIR%.venv\\Scripts\\pythonw.exe"
set "PY=%DIR%local_signer.py"
set "TARGET=%DIR%local_signer.py"
set "PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=__ALLOWED_ORIGINS__"
set "FORCE_RESTART=0"
set "SILENT_MODE=0"

if /I "%~1"=="--force" set "FORCE_RESTART=1"
if /I "%~1"=="--silent" set "SILENT_MODE=1"
echo %~1 | find /I "hacs-local-signer://restart" >nul 2>&1 && set "FORCE_RESTART=1"

if "%FORCE_RESTART%"=="0" (
powershell -NoProfile -WindowStyle Hidden -Command "try {{ $r = Invoke-RestMethod 'http://127.0.0.1:27272/ping' -UseBasicParsing -TimeoutSec 2; if ($r.ok) {{ exit 0 }} }} catch {{}}; exit 1" >nul 2>&1
if not errorlevel 1 goto :online
)

powershell -NoProfile -WindowStyle Hidden -Command "$target = [regex]::Escape($env:TARGET); Get-CimInstance Win32_Process | Where-Object {{ $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -match $target }} | ForEach-Object {{ try {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }} catch {{}} }}" >nul 2>&1
powershell -NoProfile -WindowStyle Hidden -Command "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {{ try {{ Stop-Process -Id $_ -Force -ErrorAction Stop }} catch {{}} }}" >nul 2>&1

if exist "%PYW%" if exist "%PY%" (
    powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -FilePath $env:PYW -ArgumentList @($env:PY)"
) else (
    exit /b 1
)

:online
if /I "%~1"=="--background" exit /b 0
if "%SILENT_MODE%"=="1" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
exit /b 0
'@
$cmd = $cmd.Replace('__ALLOWED_ORIGINS__', $allowedOrigins)
Set-Content -Path $starterCmd -Value $cmd -Encoding ASCII
$vbs = @"
Set shell = CreateObject("WScript.Shell")
Dim extra
extra = " --background"
If WScript.Arguments.Count > 0 Then
  If InStr(LCase(WScript.Arguments(0)), "hacs-local-signer://restart") > 0 Then
    extra = extra & " --force"
  End If
End If
shell.Run Chr(34) & "$starterCmd" & Chr(34) & extra, 0, False
"@
Set-Content -Path $starterVbs -Value $vbs -Encoding ASCII

Write-Host "  Registro il protocollo locale hacs-local-signer://..."
$protocolRoot = "HKCU:\\Software\\Classes\\hacs-local-signer"
$commandKey = Join-Path $protocolRoot "shell\\open\\command"
$wscriptExe = Join-Path $env:SystemRoot "System32\\wscript.exe"
$command = "`"$wscriptExe`" `"$starterVbs`" `"%1`""
New-Item -Path $commandKey -Force | Out-Null
Set-Item -Path $protocolRoot -Value "URL:IUSENTRA Local Signer Protocol"
New-ItemProperty -Path $protocolRoot -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
Set-Item -Path $commandKey -Value $command

Write-Host "  Registro il servizio nel Task Scheduler..."
$taskName = "IUSENTRA Local Signer"
$cmdExe   = Join-Path $env:SystemRoot "System32\\cmd.exe"
$action   = New-ScheduledTaskAction -Execute $cmdExe -Argument "/c `"$starterCmd`" --background"
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "IUSENTRA Local Signer - firma documenti con smart card e token CNS/CIE" `
    -Force | Out-Null

Write-Host "  Avvio Local Signer..."
Stop-LocalSignerProcesses
Start-Sleep -Milliseconds 500
Start-Process -FilePath $starterCmd -ArgumentList "--background" -WindowStyle Hidden

Write-Host "  Attendo che il servizio risponda su 127.0.0.1:27272..."
$online = $false
for ($i = 0; $i -lt 15; $i++) {{
    try {{
        $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping" -UseBasicParsing -TimeoutSec 2
        if ($resp.ok) {{
            $online = $true
            break
        }}
    }} catch {{
    }}
    Start-Sleep -Seconds 1
}}

Write-Host ""
if ($online) {{
    Write-Host "Installazione completata! Local Signer v$version pronto." -ForegroundColor Green
    Write-Host "  Il Local Signer e' attivo su http://127.0.0.1:27272"
    Write-Host "  Si avviera' automaticamente ad ogni accesso Windows."
    Write-Host "  Da ora IUSENTRA puo' avviarlo automaticamente quando clicchi Cerca."
}} else {{
    Write-Host "Installazione completata con avviso." -ForegroundColor Yellow
    Write-Host "  Il servizio non ha ancora risposto su http://127.0.0.1:27272"
    Write-Host "  Tornare su IUSENTRA e usare 'Avvia Local Signer' oppure rieseguire l installer."
}}
Write-Host ""
Write-Host "Diagnostica locale: http://127.0.0.1:27272/diagnosi" -ForegroundColor Cyan
Read-Host "Premere Invio per chiudere"
"""

    def _render_local_signer_macos_command(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        version = _local_signer_version()
        return f"""#!/bin/bash
set -euo pipefail

BASE_URL="{base_url}"
ALLOWED_ORIGINS="{allowed_origins}"
VERSION="{version}"
DIR="$HOME/Library/Application Support/IUSENTRA/LocalSigner"
DATA_DIR="$DIR/data"
VENV="$DIR/.venv"
PY="$VENV/bin/python3"
PLIST="$HOME/Library/LaunchAgents/it.hacs.local-signer.plist"

echo "IUSENTRA Local Signer v$VERSION - Installazione macOS"

mkdir -p "$DIR" "$DATA_DIR" "$(dirname "$PLIST")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima da https://python.org"
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-ai-bridge" -o "$DIR/local_ai_host_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/lex-document-context" -o "$DIR/lex_document_context.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/visible-signature" -o "$DIR/visible_signature.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>it.hacs.local-signer</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$DIR/local_signer.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PCT_LOCAL_SIGNER_ALLOWED_ORIGINS</key>
    <string>$ALLOWED_ORIGINS</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/it.hacs.local-signer"

echo
echo "Installazione completata. Local Signer v$VERSION pronto."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Pacchetto ufficiale sempre disponibile su: https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma"
echo "Tornare su IUSENTRA e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
"""

    def _render_local_signer_linux_sh(base_url: str) -> str:
        allowed_origins = _local_signer_allowed_origins(base_url)
        version = _local_signer_version()
        return f"""#!/usr/bin/env bash
set -euo pipefail

BASE_URL="{base_url}"
ALLOWED_ORIGINS="{allowed_origins}"
VERSION="{version}"
DIR="${{XDG_DATA_HOME:-$HOME/.local/share}}/hacs/local-signer"
DATA_DIR="$DIR/data"
VENV="$DIR/.venv"
PY="$VENV/bin/python"
SERVICE_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/systemd/user"
SERVICE="$SERVICE_DIR/hacs-local-signer.service"

echo "IUSENTRA Local Signer v$VERSION - Installazione Linux"

mkdir -p "$DIR" "$DATA_DIR" "$SERVICE_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima con il gestore pacchetti della distribuzione."
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-ai-bridge" -o "$DIR/local_ai_host_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/lex-document-context" -o "$DIR/lex_document_context.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/visible-signature" -o "$DIR/visible_signature.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf

cat > "$SERVICE" <<EOF
[Unit]
Description=IUSENTRA Local Signer
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
Environment=PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=$ALLOWED_ORIGINS
ExecStart=$PY $DIR/local_signer.py
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now hacs-local-signer.service

echo
echo "Installazione completata. Local Signer v$VERSION pronto."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Pacchetto ufficiale sempre disponibile su: https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma"
echo "Tornare su IUSENTRA e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
"""

    def _pdp_penale_workspace_url_for_fascicolo_early(id_fasc: str) -> str:
        id_fasc = str(id_fasc or "").strip()
        if not id_fasc:
            return ""
        try:
            cases = get_pdp_penale().list_cases_for_practice(id_fasc)
        except Exception:
            cases = []
        active_case = next((row for row in cases if str(row.get("id") or "").strip()), None)
        if active_case:
            return url_for(
                "pdp_penale_workspace",
                id_fasc=id_fasc,
                case_id=str(active_case["id"]),
            )
        return url_for("pdp_penale_workspace", id_fasc=id_fasc)

    return {
        "polis_auth_mode": _polis_auth_mode,
        "polis_demo_mode": _polis_demo_mode,
        "portale_demo_mode": _portale_demo_mode,
        "portale_browser_channel_required": _portale_browser_channel_required,
        "polis_cert_preferences": _polis_cert_preferences,
        "portale_local_channel_enabled": _portale_local_channel_enabled,
        "portale_browser_guided_message": _portale_browser_guided_message,
        "is_portale_dns_error": _is_portale_dns_error,
        "codice_fiscale_avvocato_portale": _codice_fiscale_avvocato_portale,
        "spec_portale_acquisizione": _spec_portale_acquisizione,
        "build_access_status_payload": _build_access_status_payload,
        "search_fascicoli_portale_server": _search_fascicoli_portale_server,
        "preview_documenti_portale_server": _preview_documenti_portale_server,
        "build_portale_preview": _build_portale_preview,
        "coerce_import_options": _coerce_import_options,
        "coerce_mapping": _coerce_mapping,
        "analyze_portale_import": _analyze_portale_import,
        "importa_o_collega_fascicolo_portale": _importa_o_collega_fascicolo_portale,
        "backfill_telematico_from_existing_fascicoli": _backfill_telematico_from_existing_fascicoli,
        "telematico_dashboard_warning_message": _telematico_dashboard_warning_message,
        "local_signer_python_name": _local_signer_python_name,
        "local_ai_bridge_source_path": _local_ai_bridge_source_path,
        "local_ai_bridge_python_name": _local_ai_bridge_python_name,
        "local_ai_lex_context_source_path": _local_ai_lex_context_source_path,
        "local_ai_lex_context_python_name": _local_ai_lex_context_python_name,
        "local_signer_visible_signature_source_path": _local_signer_visible_signature_source_path,
        "local_signer_visible_signature_python_name": _local_signer_visible_signature_python_name,
        "local_signer_uffici_path": _local_signer_uffici_path,
        "local_signer_windows_cmd_path": _local_signer_windows_cmd_path,
        "local_signer_windows_cmd_name": _local_signer_windows_cmd_name,
        "local_signer_windows_exe_path": _local_signer_windows_exe_path,
        "local_signer_windows_exe_name": _local_signer_windows_exe_name,
        "local_signer_windows_offline_ps1_path": _local_signer_windows_offline_ps1_path,
        "local_signer_windows_offline_ps1_name": _local_signer_windows_offline_ps1_name,
        "render_local_signer_windows_ps1": _render_local_signer_windows_ps1,
        "local_signer_windows_ps1_name": _local_signer_windows_ps1_name,
        "local_signer_macos_installer_path": _local_signer_macos_installer_path,
        "local_signer_macos_name": _local_signer_macos_name,
        "render_local_signer_macos_command": _render_local_signer_macos_command,
        "local_signer_linux_installer_path": _local_signer_linux_installer_path,
        "local_signer_linux_name": _local_signer_linux_name,
        "render_local_signer_linux_sh": _render_local_signer_linux_sh,
        "pdp_penale_workspace_url_for_fascicolo_early": _pdp_penale_workspace_url_for_fascicolo_early,
        "serialize_portale_search_item": _serialize_portale_search_item,
        "find_exact_fascicolo_locale_portale": _find_exact_fascicolo_locale_portale,
        "sync_existing_fascicolo_from_portale": _sync_existing_fascicolo_from_portale,
        "register_direct_portale_import_sync": _register_direct_portale_import_sync,
    }
