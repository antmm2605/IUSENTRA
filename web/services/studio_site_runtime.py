"""Runtime e surface del modulo Sito Studio."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from flask import abort, current_app, g, request, session, url_for
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from pct.agenda import TipoAppuntamento
from pct.config_studio import ConfigDatiStudio, GestioneConfigStudio
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from pct.studio_site import (
    clean_text,
    default_site_payload,
    normalize_hex_color,
    public_applications_catalog,
    public_legal_tools_catalog,
    studio_site_profile_from_config,
    truthy,
)
from pct.studio_site_theme import theme_snapshot
from pct.studio_site_repository import StudioSiteRepository
from pct.tenant import GestioneTenant
from web.helpers import get_agenda
from web.services.legal_update_surface import build_legal_update_pipeline_runtime


ALLOWED_SITE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"}


def studio_site_repository() -> StudioSiteRepository:
    db_path = str(current_app.config.get("SITE_STUDIO_DB") or "").strip()
    postgres_dsn = resolve_runtime_postgres_dsn(
        config=current_app.config,
        env_url_keys=(
            "PCT_SITE_STUDIO_POSTGRES_URL",
            "PCT_SITE_STUDIO_POSTGRES_DSN",
        ),
    )
    cache_key = f"{db_path}|{postgres_dsn}"
    cache = current_app.extensions.setdefault("studio_site_repository_cache", {})
    repo = cache.get(cache_key)
    if isinstance(repo, StudioSiteRepository):
        return repo
    repo = StudioSiteRepository(db_path, postgres_dsn=postgres_dsn)
    cache[cache_key] = repo
    return repo


def studio_site_assets_root() -> Path:
    configured = str(current_app.config.get("SITE_STUDIO_ASSETS_DIR") or "").strip()
    if configured:
        root = Path(configured).resolve()
    else:
        db_path = Path(str(current_app.config.get("SITE_STUDIO_DB") or current_app.instance_path or "data")).resolve()
        root = (db_path.parent / "site_assets").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _tenant_manager() -> GestioneTenant | None:
    registry = str(current_app.config.get("TENANTS_REGISTRY") or "").strip()
    if not registry:
        return None
    try:
        return GestioneTenant(registry_path=registry)
    except Exception:
        return None


def _current_user_name() -> str:
    user = getattr(g, "utente_corrente", None)
    return str(
        getattr(user, "nome_completo", None)
        or getattr(user, "email", None)
        or getattr(user, "username", None)
        or "Operatore"
    )


def audit_studio_site_action(action: str, *, resource_id: str = "", details: str = "", esito: str = "OK") -> None:
    user = getattr(g, "utente_corrente", None)
    manager = getattr(g, "utente_auth_manager", None)
    if manager is None:
        return
    try:
        manager.registra_evento(
            azione=action,
            id_utente=str(getattr(user, "id", "") or ""),
            username=str(getattr(user, "username", "") or ""),
            risorsa_tipo="sito_studio",
            risorsa_id=str(resource_id or ""),
            dettagli=details,
            ip=request.remote_addr or "",
            esito=esito,
        )
    except Exception:
        current_app.logger.exception("Errore audit Sito Studio: %s", action)


def site_admin_identity_or_403() -> Any:
    user = getattr(g, "utente_corrente", None)
    if user is None:
        abort(403, description="Accesso riservato agli utenti autenticati.")
    if getattr(user, "is_superadmin", False) and not session.get("superadmin_user_id"):
        abort(403, description="Il SUPERADMIN di piattaforma gestisce i siti dal pannello piattaforma o in impersonazione.")
    if not bool(getattr(user, "ha_permesso", lambda _perm: False)("admin.configura")):
        abort(403, description="Permessi insufficienti per gestire il Sito Studio.")
    return user


def superadmin_identity_or_403() -> Any:
    user = getattr(g, "utente_corrente", None)
    if user is not None and getattr(user, "is_superadmin", False):
        return user
    if session.get("superadmin_user_id"):
        return user
    abort(403, description="Area riservata al SUPERADMIN di piattaforma.")


def _tenant_context_from_request() -> dict[str, Any]:
    tenant = getattr(g, "tenant", None)
    if tenant is not None:
        config_path = str((getattr(g, "data_paths", {}) or {}).get("CONFIG_STUDIO_DB") or current_app.config.get("STUDIO_CONFIG") or "")
        return {
            "tenant_slug": str(getattr(tenant, "slug", "") or "").strip().lower(),
            "studio_nome": str(getattr(tenant, "nome", "") or "").strip(),
            "config_path": config_path,
        }

    if current_app.config.get("MULTI_TENANT"):
        manager = _tenant_manager()
        tenant_slug = str(session.get("tenant_slug") or "").strip().lower()
        if manager is not None and tenant_slug:
            studio = manager.get(tenant_slug)
            if studio is not None:
                paths = manager.percorsi_dati(tenant_slug)
                return {
                    "tenant_slug": tenant_slug,
                    "studio_nome": str(getattr(studio, "nome", "") or "").strip(),
                    "config_path": str(paths.get("CONFIG_STUDIO_DB") or current_app.config.get("STUDIO_CONFIG") or ""),
                }

    return {
        "tenant_slug": "studio-locale",
        "studio_nome": str(current_app.config.get("STUDIO_NOME") or "Studio locale"),
        "config_path": str(current_app.config.get("STUDIO_CONFIG") or ""),
    }


def _site_profile_for_context(context: dict[str, Any]) -> tuple[ConfigDatiStudio | None, dict[str, Any]]:
    config_path = Path(str(context.get("config_path") or "")).resolve()
    studio_cfg: ConfigDatiStudio | None = None
    if config_path.is_file():
        try:
            studio_cfg = GestioneConfigStudio(config_path=str(config_path)).config.studio
        except Exception:
            studio_cfg = None
    profile = studio_site_profile_from_config(
        studio_cfg,
        tenant_slug=str(context.get("tenant_slug") or ""),
        fallback_name=str(context.get("studio_nome") or ""),
    )
    defaults = default_site_payload(profile)
    return studio_cfg, {"profile": profile, "defaults": defaults}


def ensure_current_studio_site() -> dict[str, Any]:
    context = _tenant_context_from_request()
    _cfg, profile_bundle = _site_profile_for_context(context)
    return studio_site_repository().bootstrap_site_from_profile(
        tenant_slug=context["tenant_slug"],
        defaults=profile_bundle["defaults"],
        profile=profile_bundle["profile"],
    )


def get_site_for_current_tenant() -> dict[str, Any]:
    site_admin_identity_or_403()
    return ensure_current_studio_site()


def site_assets_dir(public_slug: str) -> Path:
    target = studio_site_assets_root() / clean_text(public_slug)
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_site_asset(site: dict[str, Any], file_storage: FileStorage, *, kind: str) -> str:
    if file_storage is None or not getattr(file_storage, "filename", ""):
        raise ValueError("Seleziona un file immagine valido.")
    filename = secure_filename(file_storage.filename or "")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_SITE_IMAGE_EXTENSIONS:
        raise ValueError("Formato file non supportato. Usa PNG, JPG, WEBP, SVG o ICO.")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    target_name = f"{kind}-{timestamp}{extension}"
    target_path = site_assets_dir(str(site.get("public_slug") or "")) / target_name
    file_storage.save(str(target_path))
    return url_for(
        "studio_site_public.asset",
        public_slug=str(site.get("public_slug") or ""),
        filename=target_name,
    )


def _serialize_article_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row.get("id") or 0),
        "title": str(row.get("title") or ""),
        "slug": str(row.get("slug") or ""),
        "excerpt": str(row.get("excerpt") or ""),
        "cover_url": str(row.get("cover_url") or ""),
        "category": str(row.get("category") or ""),
        "author_name": str(row.get("author_name") or ""),
        "published_at": str(row.get("published_at") or row.get("created_at") or ""),
        "tags": [item.strip() for item in str(row.get("tags_csv") or "").split(",") if item.strip()],
    }


def _serialize_legal_news_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(row.get("title") or row.get("headline") or ""),
        "summary": str(row.get("summary") or row.get("body_short") or ""),
        "publication_date": str(row.get("published_at") or row.get("publication_date") or row.get("created_at") or ""),
        "matter_name": str(row.get("matter_name") or ""),
        "submatter_name": str(row.get("submatter_name") or ""),
        "source_name": str(row.get("source_name") or row.get("source_code") or ""),
        "url": str(row.get("source_url") or row.get("official_url") or ""),
    }


def load_public_legal_news(tenant_slug: str, *, limit: int = 12) -> list[dict[str, Any]]:
    try:
        pipeline = build_legal_update_pipeline_runtime(tenant_slug=tenant_slug)
        rows = pipeline.repository.list_news(limit=limit, include_drafts=False)
        return [_serialize_legal_news_row(row) for row in rows]
    except Exception:
        current_app.logger.exception("Errore caricamento news giuridiche per sito studio: %s", tenant_slug)
        return []


def build_public_site_payload(public_slug: str, *, include_drafts: bool = False) -> dict[str, Any]:
    site = studio_site_repository().get_site_by_public_slug(public_slug)
    if site is None or not site.get("is_active"):
        abort(404, description="Sito studio non trovato.")

    repo = studio_site_repository()
    pages = repo.list_pages(int(site["id"]), published_only=not include_drafts)
    articles = repo.list_articles(int(site["id"]), published_only=not include_drafts, limit=24)
    services = [row for row in repo.list_services(int(site["id"])) if row.get("is_visible")]
    professionals = [row for row in repo.list_professionals(int(site["id"])) if row.get("is_visible")]
    offices = [row for row in repo.list_offices(int(site["id"])) if row.get("is_visible")]
    rules = repo.list_booking_rules(int(site["id"]), active_only=True)
    home_page = next((row for row in pages if row.get("is_home")), None) or next(
        (row for row in pages if str(row.get("slug") or "") == "home"),
        None,
    )
    if home_page is None and pages:
        home_page = pages[0]

    menu_pages = [row for row in pages if row.get("show_in_menu") and not row.get("is_home")]
    booking_enabled = bool(offices and rules)
    payload = {
        "site": site,
        "home_page": home_page,
        "menu_pages": menu_pages,
        "articles": [_serialize_article_summary(row) for row in articles],
        "latest_articles": [_serialize_article_summary(row) for row in articles[:3]],
        "services": services,
        "professionals": professionals,
        "offices": offices,
        "booking_enabled": booking_enabled,
        "public_url": url_for("studio_site_public.home", public_slug=site["public_slug"]),
        "show_legal_tools": bool(site.get("show_legal_tools")),
        "show_applications": bool(site.get("show_applications")),
        "show_legal_news": bool(site.get("show_legal_news")),
        "legal_tools": [],
        "applications": [],
        "legal_news": [],
        "theme": theme_snapshot(site),
    }
    if site.get("show_legal_tools"):
        payload["legal_tools"] = public_legal_tools_catalog(
            limit=8,
            normative_db_path=str(current_app.config.get("NORMATIVE_TABLES_DB") or ""),
        )
    if site.get("show_applications"):
        payload["applications"] = public_applications_catalog(limit=8)
    if site.get("show_legal_news"):
        payload["legal_news"] = load_public_legal_news(str(site.get("tenant_slug") or ""), limit=12)
    return payload


def build_studio_site_dashboard_payload() -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    stats = repo.site_stats(int(site["id"]))
    offices = repo.list_offices(int(site["id"]))
    office_map = {int(item.get("id") or 0): str(item.get("name") or "") for item in offices}
    booking_rules = repo.list_booking_rules(int(site["id"]))
    booking_requests = repo.list_booking_requests(int(site["id"]), limit=10)
    for item in booking_rules:
        item["office_name"] = office_map.get(int(item.get("office_id") or 0), "")
    for item in booking_requests:
        item["office_name"] = office_map.get(int(item.get("office_id") or 0), "")
    warnings: list[str] = []
    if not site.get("is_published"):
        warnings.append("Il sito e' ancora in bozza: attiva la pubblicazione quando i contenuti sono pronti.")
    if not offices:
        warnings.append("Aggiungi almeno una sede per completare contatti, mappa e prenotazioni.")
    if not repo.list_booking_rules(int(site["id"]), active_only=True):
        warnings.append("L'agenda appuntamenti pubblica e' disattivata: configura almeno una regola oraria.")
    if not site.get("show_legal_tools"):
        warnings.append("Strumenti legali pubblici disattivati: attivali solo se vuoi mostrarli sul sito.")
    if not site.get("show_applications"):
        warnings.append("Applicazioni pubbliche disattivate: attivale solo se vuoi esporre il catalogo operativo.")
    if not site.get("show_legal_news"):
        warnings.append("News giuridiche strutturate disattivate: attivale per mostrare gli aggiornamenti pubblicabili.")
    return {
        "site": site,
        "stats": stats,
        "warnings": warnings,
        "public_url": url_for("studio_site_public.home", public_slug=site["public_slug"], _external=True),
        "pages": repo.list_pages(int(site["id"])),
        "articles": repo.list_articles(int(site["id"]), limit=6),
        "services": repo.list_services(int(site["id"])),
        "professionals": repo.list_professionals(int(site["id"])),
        "offices": offices,
        "booking_rules": booking_rules,
        "booking_requests": booking_requests,
        "contact_submissions": repo.list_contact_submissions(int(site["id"]), limit=10),
    }


def build_platform_sites_payload(*, query: str = "") -> dict[str, Any]:
    superadmin_identity_or_403()
    repo = studio_site_repository()
    sites = repo.list_sites(query=query, limit=300)
    rows = []
    for site in sites:
        stats = repo.site_stats(int(site["id"]))
        rows.append(
            {
                **site,
                "stats": stats,
                "public_url": url_for("studio_site_public.home", public_slug=site["public_slug"], _external=True),
            }
        )
    return {
        "stats": repo.platform_stats(),
        "sites": rows,
        "query": query,
    }


def validate_public_contact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    full_name = clean_text(payload.get("full_name"))
    email = clean_text(payload.get("email"))
    message = clean_text(payload.get("message"))
    if not full_name:
        raise ValueError("Inserisci nome e cognome.")
    if not email or "@" not in email:
        raise ValueError("Inserisci un indirizzo email valido.")
    if not message:
        raise ValueError("Inserisci il messaggio da inviare allo studio.")
    if not truthy(payload.get("privacy_accepted")):
        raise ValueError("Devi confermare l'informativa privacy per inviare il modulo.")
    return {
        "full_name": full_name,
        "email": email,
        "phone": clean_text(payload.get("phone")),
        "subject": clean_text(payload.get("subject")),
        "message": message,
        "privacy_accepted": True,
    }


def validate_public_booking_payload(site: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    repo = studio_site_repository()
    site_id = int(site["id"])
    office_id = int(payload.get("office_id") or 0)
    requested_date = clean_text(payload.get("requested_date"))
    requested_time = clean_text(payload.get("requested_time"))
    customer_name = clean_text(payload.get("customer_name"))
    customer_email = clean_text(payload.get("customer_email"))
    if not customer_name:
        raise ValueError("Inserisci il nominativo del cliente.")
    if not customer_email or "@" not in customer_email:
        raise ValueError("Inserisci un indirizzo email valido.")
    if not requested_date:
        raise ValueError("Seleziona la data richiesta.")
    if not requested_time:
        raise ValueError("Seleziona una fascia oraria disponibile.")
    if not truthy(payload.get("privacy_accepted")):
        raise ValueError("Devi confermare l'informativa privacy per richiedere l'appuntamento.")
    office = repo.get_office(site_id, office_id)
    if office is None:
        raise ValueError("La sede selezionata non e' valida.")
    available = repo.available_slots(site_id, requested_date, office_id=office_id)
    if not any(str(row.get("time") or "") == requested_time for row in available):
        raise ValueError("La fascia selezionata non e' piu' disponibile. Aggiorna gli slot e riprova.")
    return {
        "office_id": office_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": clean_text(payload.get("customer_phone")),
        "requested_date": requested_date,
        "requested_time": requested_time,
        "subject": clean_text(payload.get("subject")),
        "notes": clean_text(payload.get("notes")),
        "privacy_accepted": True,
        "status": "pending",
    }


def approve_booking_request_for_current_site(booking_request_id: int) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    booking = repo.get_booking_request(int(site["id"]), booking_request_id)
    if booking is None:
        raise ValueError("Richiesta appuntamento non trovata.")
    office = repo.get_office(int(site["id"]), int(booking.get("office_id") or 0))
    if office is None:
        raise ValueError("La sede collegata alla richiesta non e' piu' disponibile.")

    agenda = get_agenda()
    external_uid = f"site-studio-booking-{site['id']}-{booking['id']}"
    existing = agenda.trova_per_uid_esterno(external_uid, provider="site_studio")
    if existing is None:
        iso_datetime = f"{booking['requested_date']}T{booking['requested_time']}:00"
        luogo = " - ".join(
            [
                part
                for part in (
                    str(office.get("name") or ""),
                    clean_text(" ".join([str(office.get('address') or ''), str(office.get('city') or '')]).strip()),
                )
                if part
            ]
        )
        note = "\n".join(
            [
                f"Richiesta dal sito studio per {booking['customer_name']}.",
                f"Email: {booking['customer_email']}",
                f"Telefono: {booking.get('customer_phone') or '-'}",
                f"Oggetto: {booking.get('subject') or 'Consulenza'}",
                f"Note: {booking.get('notes') or '-'}",
            ]
        )
        appuntamento = agenda.aggiungi(
            titolo=f"Appuntamento sito web - {booking['customer_name']}",
            tipo=TipoAppuntamento.CONSULTAZIONE,
            data_ora=iso_datetime,
            durata_minuti=30,
            luogo=luogo,
            note=note,
            cliente=str(booking["customer_name"]),
            procedimento="Sito Studio",
            avvocato=str(site.get("studio_nome") or ""),
            external_uid=external_uid,
            external_provider="site_studio",
        )
        agenda_event_id = appuntamento.id
    else:
        agenda_event_id = existing.id

    reviewer = _current_user_name()
    updated = repo.update_booking_request(
        int(site["id"]),
        booking_request_id,
        status="approved",
        agenda_event_id=agenda_event_id,
        reviewed_by=reviewer,
        reviewed_at=datetime.now().replace(microsecond=0).isoformat(),
    )
    audit_studio_site_action(
        "sito_studio.approva_prenotazione",
        resource_id=str(booking_request_id),
        details=f"{reviewer} ha approvato la richiesta appuntamento {booking_request_id}.",
    )
    return updated or booking


def create_lead_cliente_from_submission(submission: dict[str, Any]) -> str:
    """Crea un Cliente con stato=POTENZIALE dall'anagrafica di una richiesta contatto.

    Restituisce l'id del cliente creato. Solleva ValueError se i dati non sono
    sufficienti o se il flusso non è disponibile nel contesto corrente.
    """
    from pct.clienti import GestioneClienti, Recapiti, StatoCliente, TipoCliente
    from web.helpers import get_clienti

    full_name = clean_text(submission.get("full_name") or "")
    if not full_name:
        raise ValueError("Nome mittente mancante: impossibile creare il cliente potenziale.")

    parts = full_name.split(None, 1)
    nome = parts[0]
    cognome = parts[1] if len(parts) > 1 else ""

    note_lead_parts = ["Richiesta contatto ricevuta via sito studio."]
    subject = clean_text(submission.get("subject") or "")
    message = clean_text(submission.get("message") or "")
    if subject:
        note_lead_parts.append(f"Oggetto: {subject}")
    if message:
        note_lead_parts.append(f"Messaggio: {message}")

    email = clean_text(submission.get("email") or "")
    phone = clean_text(submission.get("phone") or "")

    clienti: GestioneClienti = get_clienti()
    cliente = clienti.nuovo(
        tipo=TipoCliente.PERSONA_FISICA,
        nome=nome,
        cognome=cognome,
        stato=StatoCliente.POTENZIALE,
        provenienza="sito_web",
        note="\n".join(note_lead_parts),
        recapiti=Recapiti(email=email, cellulare=phone),
    )
    return cliente.id


def reject_booking_request_for_current_site(booking_request_id: int) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    booking = studio_site_repository().update_booking_request(
        int(site["id"]),
        booking_request_id,
        status="rejected",
        reviewed_by=_current_user_name(),
        reviewed_at=datetime.now().replace(microsecond=0).isoformat(),
    )
    if booking is None:
        raise ValueError("Richiesta appuntamento non trovata.")
    audit_studio_site_action(
        "sito_studio.rifiuta_prenotazione",
        resource_id=str(booking_request_id),
        details=f"{_current_user_name()} ha rifiutato la richiesta appuntamento {booking_request_id}.",
    )
    return booking
