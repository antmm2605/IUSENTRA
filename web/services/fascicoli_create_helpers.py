"""Helpers for the fascicolo creation routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pct.fascicoli import TipoDocumento, TipoFascicolo
from pct.guida_pratica import GuidaPraticaError, get_guida_pratica_service, normalize_codice_materia
from pct.pratiche_collegate_catalog import (
    codice_oggetto_pst_entry,
    looks_like_codice_oggetto_pst,
    resolve_codice_oggetto_pst_payload,
)
from pct.profilo_deposito import costruisci_profilo_deposito


def tipo_documento_upload_iniziale(nome_file: str, *, email: bool = False) -> TipoDocumento:
    if email:
        return TipoDocumento.COMUNICAZIONE
    nome = Path(nome_file or "").name.lower()
    if "procura" in nome:
        return TipoDocumento.PROCURA
    if "ricorso" in nome:
        return TipoDocumento.RICORSO
    if "citazione" in nome:
        return TipoDocumento.CITAZIONE
    if "comparsa" in nome:
        return TipoDocumento.COMPARSA
    if "memoria" in nome:
        return TipoDocumento.MEMORIA
    if "notifica" in nome or "relata" in nome:
        return TipoDocumento.NOTIFICA
    if nome.endswith((".eml", ".msg")) or "ricevuta" in nome:
        return TipoDocumento.COMUNICAZIONE
    if nome.endswith((".pdf", ".p7m")):
        return TipoDocumento.ATTO_GIUDIZIARIO
    return TipoDocumento.ALLEGATO


def salva_upload_fascicolo_veloce(
    gestore_fascicoli: Any,
    id_fasc: str,
    documenti_fascicolo: list[Any],
    email_fascicolo: list[Any],
) -> tuple[int, int, int]:
    documenti_caricati = 0
    email_caricate = 0
    email_scartate = 0

    for storage in documenti_fascicolo:
        if not storage or not storage.filename:
            continue
        raw = storage.read()
        if not raw:
            continue
        gestore_fascicoli.aggiungi_documento(
            id_fasc,
            Path(storage.filename).name,
            tipo_documento_upload_iniziale(storage.filename),
            raw,
            note="Caricato all'apertura con Fascicolo Veloce.",
            tags=["fascicolo-veloce", "documenti-iniziali"],
            fonte_documento="APERTURA_FASCICOLO_VELOCE",
            nome_originale=storage.filename,
        )
        documenti_caricati += 1

    for storage in email_fascicolo:
        if not storage or not storage.filename:
            continue
        if not Path(storage.filename).name.lower().endswith(".eml"):
            email_scartate += 1
            continue
        raw = storage.read()
        if not raw:
            continue
        gestore_fascicoli.aggiungi_documento(
            id_fasc,
            Path(storage.filename).name,
            tipo_documento_upload_iniziale(storage.filename, email=True),
            raw,
            note="Email EML caricata all'apertura con Fascicolo Veloce.",
            tags=["fascicolo-veloce", "email-iniziali", "eml"],
            fonte_documento="APERTURA_FASCICOLO_VELOCE",
            nome_originale=storage.filename,
        )
        email_caricate += 1

    return documenti_caricati, email_caricate, email_scartate


def form_bool(form: Any, name: str) -> bool:
    return form.get(name) in {"1", "true", "on", "si", "sì", "SI", "Si"}


def codice_oggetto_da_workflow(form: Any, gestore_preventivi: Any) -> str:
    source_conferimento = str(form.get("source_conferimento", "") or "").strip()
    if source_conferimento:
        try:
            conferimento = gestore_preventivi.get_conferimento(source_conferimento)
        except Exception:
            conferimento = None
        if conferimento:
            codice = str(getattr(conferimento, "codice_oggetto_pst", "") or "").strip()
            if codice:
                return codice
            id_preventivo = str(getattr(conferimento, "id_preventivo", "") or "").strip()
            if id_preventivo:
                try:
                    preventivo = gestore_preventivi.get_preventivo(id_preventivo)
                except Exception:
                    preventivo = None
                codice = str(getattr(preventivo, "codice_oggetto_pst", "") or "").strip() if preventivo else ""
                if codice:
                    return codice

    source_preventivo = str(form.get("source_preventivo", "") or "").strip()
    if source_preventivo:
        try:
            preventivo = gestore_preventivi.get_preventivo(source_preventivo)
        except Exception:
            preventivo = None
        codice = str(getattr(preventivo, "codice_oggetto_pst", "") or "").strip() if preventivo else ""
        if codice:
            return codice
    return ""


def codice_oggetto_pst_da_form(form: Any, *, oggetto: str, gestore_preventivi: Any) -> dict[str, str]:
    explicit = str(form.get("codice_oggetto_pst", "") or "").strip()
    workflow = codice_oggetto_da_workflow(form, gestore_preventivi)
    oggetto_candidate = str(oggetto or "").strip()
    candidate = explicit or workflow or (oggetto_candidate if looks_like_codice_oggetto_pst(oggetto_candidate) else "")
    if not candidate:
        return {
            "codice_oggetto_pst": "",
            "fonte_codice_oggetto": str(form.get("fonte_codice_oggetto", "") or "").strip(),
            "file_fonte_codice_oggetto": str(form.get("file_fonte_codice_oggetto", "") or "").strip(),
            "descrizione": "",
        }
    entry = codice_oggetto_pst_entry(candidate)
    if not entry:
        raise ValueError("Codice oggetto PST non valido. Scegli una voce del catalogo ufficiale.")
    resolved = resolve_codice_oggetto_pst_payload(candidate)
    return {
        "codice_oggetto_pst": resolved["codice_oggetto_pst"],
        "fonte_codice_oggetto": str(form.get("fonte_codice_oggetto", "") or resolved["fonte_codice_oggetto"]).strip(),
        "file_fonte_codice_oggetto": str(form.get("file_fonte_codice_oggetto", "") or resolved["file_fonte_codice_oggetto"]).strip(),
        "descrizione": str(entry.get("descrizione", "") or "").strip(),
    }


def profilo_deposito_da_form(
    form: Any,
    *,
    tipo_fascicolo: TipoFascicolo,
    tribunale: str,
    codice_oggetto: dict[str, str],
    gestore_preventivi: Any,
) -> dict[str, Any]:
    conferimento = None
    preventivo = None
    source_conferimento = str(form.get("source_conferimento", "") or "").strip()
    source_preventivo = str(form.get("source_preventivo", "") or "").strip()
    if source_conferimento:
        try:
            conferimento = gestore_preventivi.get_conferimento(source_conferimento)
        except Exception:
            conferimento = None
    if conferimento and getattr(conferimento, "id_preventivo", ""):
        try:
            preventivo = gestore_preventivi.get_preventivo(conferimento.id_preventivo)
        except Exception:
            preventivo = None
    if not preventivo and source_preventivo:
        try:
            preventivo = gestore_preventivi.get_preventivo(source_preventivo)
        except Exception:
            preventivo = None
    origine = (
        getattr(conferimento, "profilo_deposito", {})
        or getattr(preventivo, "profilo_deposito", {})
        or {}
    )
    return costruisci_profilo_deposito(
        id_pratica=(
            str(form.get("id_pratica", "") or "").strip()
            or str(getattr(conferimento, "id_pratica", "") or "").strip()
            or str(getattr(preventivo, "id_pratica", "") or "").strip()
        ),
        area_pratica=(
            str(form.get("area_pratica", "") or "").strip()
            or str(getattr(conferimento, "area_pratica", "") or "").strip()
            or str(getattr(preventivo, "area_pratica", "") or "").strip()
        ),
        tipo_procedimento=(
            str(form.get("tipo_procedimento", "") or "").strip()
            or str(getattr(conferimento, "tipo_procedimento", "") or "").strip()
            or str(getattr(preventivo, "tipo_procedimento", "") or "").strip()
        ),
        tipo=tipo_fascicolo.value,
        canale_operativo=(
            str(form.get("canale_operativo", "") or "").strip()
            or str(getattr(conferimento, "canale_operativo", "") or "").strip()
            or str(getattr(preventivo, "canale_operativo", "") or "").strip()
        ),
        registro_operativo=(
            str(form.get("registro_operativo", "") or "").strip()
            or str(getattr(conferimento, "registro_operativo", "") or "").strip()
            or str(getattr(preventivo, "registro_operativo", "") or "").strip()
        ),
        procedura_operativa_codice=(
            str(form.get("procedura_operativa_codice", "") or "").strip()
            or str(getattr(conferimento, "procedura_operativa_codice", "") or "").strip()
            or str(getattr(preventivo, "procedura_operativa_codice", "") or "").strip()
        ),
        codice_oggetto_pst=codice_oggetto["codice_oggetto_pst"],
        fonte_codice_oggetto=codice_oggetto["fonte_codice_oggetto"],
        file_fonte_codice_oggetto=codice_oggetto["file_fonte_codice_oggetto"],
        ufficio=tribunale,
        tipo_ufficio=str(form.get("tipo_ufficio_autorita", "") or form.get("tipo_ufficio", "") or "").strip(),
        pec_ufficio=str(form.get("pec_ufficio_autorita", "") or form.get("pec_ufficio", "") or "").strip(),
        codice_ufficio=str(form.get("codice_ufficio_autorita", "") or form.get("codice_ufficio", "") or "").strip(),
        codice_ministero=str(
            form.get("codice_ministero_autorita", "")
            or form.get("codice_pst_autorita", "")
            or form.get("codice_ministero", "")
            or ""
        ).strip(),
        verifica_certificato=bool(tribunale),
        richiedi_ufficio=bool(tribunale or form_bool(form, "fascicolo_veloce")),
        profilo_origine=origine,
    )


def codice_guida_pratica_da_form(form: Any, *, codice_oggetto_pst: str, context: dict[str, Any]) -> str:
    explicit = normalize_codice_materia(form.get("codice_guida_pratica", ""))
    if explicit:
        try:
            get_guida_pratica_service().get_guidance(explicit, fascicolo=context)
        except GuidaPraticaError as exc:
            raise ValueError("Codice Guida Pratica non valido. Scegli una scheda esistente.") from exc
        return explicit
    if codice_oggetto_pst:
        return ""
    try:
        match = get_guida_pratica_service().suggest_guidance_from_fascicolo(context)
    except Exception:
        return ""
    return normalize_codice_materia(match.get("codice")) if match else ""
