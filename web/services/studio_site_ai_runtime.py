"""Redazione AI per articoli del Sito Studio.

Il flusso e' volutamente human-in-the-loop: Lex prepara una bozza, lo studio
revisiona e solo dopo pubblica.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from lex.image_providers import get_image_provider
from pct.studio_site import clean_text, slugify
from web.services.studio_site_assets import create_generated_svg_asset
from web.services.studio_site_builder_runtime import _current_operator_label
from web.services.studio_site_runtime import audit_studio_site_action, get_site_for_current_tenant, studio_site_repository


PROMOTIONAL_PATTERNS = (
    "risultato garantito",
    "vinciamo sempre",
    "miglior avvocato",
    "leader assoluto",
    "casi vinti",
    "clienti famosi",
)


def _feature_enabled(name: str, default: str = "1") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "si", "on"}


def _length_hint(value: str) -> str:
    code = clean_text(value).lower()
    if code == "breve":
        return "circa 450-650 parole"
    if code == "lunga":
        return "circa 1.200-1.600 parole"
    return "circa 750-1.000 parole"


def _risk_checklist(payload: dict[str, Any], result: dict[str, Any]) -> list[dict[str, str]]:
    text = " ".join(
        clean_text(value).lower()
        for value in [
            payload.get("argomento"),
            payload.get("note_interne"),
            result.get("title"),
            result.get("excerpt"),
            result.get("seo_description"),
            " ".join(clean_text(block.get("text")).lower() for block in result.get("body_json") or [] if isinstance(block, dict)),
        ]
    )
    risks: list[dict[str, str]] = []
    for phrase in PROMOTIONAL_PATTERNS:
        if phrase in text:
            risks.append(
                {
                    "area": "deontologia",
                    "severity": "warning",
                    "message": f"Contenuto da rivedere: contiene '{phrase}'.",
                    "suggestion": "Usa formulazioni informative, prudenti e non comparative.",
                }
            )
    if not clean_text(payload.get("fonte_manual")):
        risks.append(
            {
                "area": "fonti",
                "severity": "info",
                "message": "Nessuna fonte normativa o giurisprudenziale indicata manualmente.",
                "suggestion": "Prima della pubblicazione verifica eventuali riferimenti normativi o giurisprudenziali.",
            }
        )
    risks.extend(
        [
            {
                "area": "privacy",
                "severity": "info",
                "message": "Verificare che il testo non contenga dati personali o riferimenti a clienti.",
                "suggestion": "Pubblica solo contenuti generali o anonimizzati.",
            },
            {
                "area": "pubblicazione",
                "severity": "warning",
                "message": "La bozza AI non viene pubblicata automaticamente.",
                "suggestion": "Un professionista dello studio deve rivedere titolo, corpo, SEO e fonti.",
            },
        ]
    )
    return risks


def generate_ai_article_job(form_payload: dict[str, Any]) -> dict[str, Any]:
    if not _feature_enabled("IUSENTRA_AI_ARTICLE_ENABLED", "1"):
        raise ValueError("Redazione AI Sito Studio non abilitata.")
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    topic = clean_text(form_payload.get("argomento") or form_payload.get("topic"))
    if not topic:
        raise ValueError("Inserisci l'argomento dell'articolo.")
    area = clean_text(form_payload.get("area_diritto")) or "diritto civile"
    audience = clean_text(form_payload.get("pubblico_destinatario")) or "clienti dello studio"
    tone = clean_text(form_payload.get("tono")) or "divulgativo"
    length = clean_text(form_payload.get("lunghezza")) or "media"
    service = clean_text(form_payload.get("servizio_collegato"))
    keywords = clean_text(form_payload.get("parole_chiave_seo"))
    cta = clean_text(form_payload.get("call_to_action")) or "Contatta lo studio per valutare il tuo caso concreto."
    source = clean_text(form_payload.get("fonte_manual"))
    title = topic if topic.lower().startswith(("come ", "quando ", "perche ", "perché ")) else f"{topic}: guida pratica"
    slug = slugify(title)
    excerpt = (
        f"Approfondimento {tone} su {topic}, con indicazioni generali per {audience}. "
        "La valutazione del caso concreto richiede sempre verifica professionale."
    )
    body_json = [
        {
            "type": "rich_text",
            "title": "Inquadramento",
            "text": (
                f"Questo articolo affronta il tema '{topic}' nell'area {area}. "
                f"Il taglio e' {tone} e la lunghezza prevista e' { _length_hint(length) }. "
                "Le informazioni hanno carattere generale e non sostituiscono la consulenza sul caso concreto."
            ),
        },
        {
            "type": "feature_grid",
            "title": "Punti da verificare",
            "items": [
                {"title": "Documenti", "text": "Raccogli gli atti e le comunicazioni rilevanti."},
                {"title": "Termini", "text": "Verifica scadenze, decadenze e priorita operative."},
                {"title": "Strategia", "text": "Valuta con il professionista le opzioni concretamente percorribili."},
            ],
        },
        {
            "type": "cta",
            "title": "Hai bisogno di un confronto?",
            "text": cta,
            "button_text": "Richiedi informazioni",
            "button_url": "",
        },
    ]
    if source:
        body_json.insert(
            1,
            {
                "type": "rich_text",
                "title": "Fonte indicata dallo studio",
                "text": f"Riferimento da verificare in revisione: {source}",
            },
        )
    image_prompt = (
        f"Immagine professionale sobria per sito di studio legale italiano, tema {area}, "
        f"argomento {topic}, senza volti realistici, senza dati personali, senza documenti leggibili, "
        "luce naturale, biblioteca giuridica o scrivania ordinata, stile istituzionale."
    )
    result = {
        "title": title,
        "slug": slug,
        "excerpt": excerpt,
        "category": area.title(),
        "tags_csv": keywords or ", ".join(part for part in [area, service, "approfondimento"] if part),
        "seo_title": title[:68],
        "seo_description": excerpt[:155],
        "body_json": body_json,
        "image_prompt": image_prompt,
        "image_alt": f"Immagine editoriale sul tema {topic}",
        "status": "draft",
    }
    risks = _risk_checklist(form_payload, result)
    job = repo.create_ai_article_job(
        int(site["id"]),
        {
            "topic": topic,
            "payload_json": dict(form_payload),
            "result_json": result,
            "risk_checklist_json": risks,
            "status": "draft_generated",
            "image_prompt": image_prompt,
            "created_by": _current_operator_label(),
        },
    )
    audit_studio_site_action(
        "sito_studio.redazione_ai_genera",
        resource_id=str(job.get("id") or ""),
        details=f"Generata bozza AI articolo: {title}. Pubblicazione manuale obbligatoria.",
    )
    return job


def create_article_draft_from_job(job_id: int) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    job = repo.get_ai_article_job(int(site["id"]), int(job_id))
    if job is None:
        raise ValueError("Lavoro AI non trovato.")
    result = job.get("result_json") or {}
    article = repo.save_article(
        int(site["id"]),
        {
            "title": result.get("title"),
            "slug": result.get("slug"),
            "excerpt": result.get("excerpt"),
            "cover_url": result.get("cover_url"),
            "category": result.get("category"),
            "tags_csv": result.get("tags_csv"),
            "author_name": site.get("studio_nome") or site.get("site_name"),
            "body_json": result.get("body_json") or [],
            "status": "draft",
            "published_at": "",
            "seo_title": result.get("seo_title"),
            "seo_description": result.get("seo_description"),
        },
    )
    repo.update_ai_article_job(
        int(site["id"]),
        int(job_id),
        {"status": "draft_created", "article_id": int(article["id"]), "result_json": result},
    )
    audit_studio_site_action(
        "sito_studio.redazione_ai_crea_bozza",
        resource_id=str(article.get("id") or ""),
        details="Creata bozza articolo da Redazione AI. Non pubblicata automaticamente.",
    )
    return article


def generate_article_cover(article_id: int) -> dict[str, Any]:
    if not _feature_enabled("IUSENTRA_AI_IMAGE_ENABLED", "1"):
        raise ValueError("Generazione immagini AI non abilitata.")
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    article = repo.get_article(int(site["id"]), int(article_id))
    if article is None:
        raise ValueError("Articolo non trovato.")
    prompt = (
        f"Immagine sobria e professionale per articolo legale: {article.get('title')}. "
        "No volti realistici, no dati personali, no documenti leggibili, no loghi protetti."
    )
    provider = get_image_provider()
    generated = provider.generate(prompt=prompt, title=str(article.get("title") or ""))
    asset = create_generated_svg_asset(
        site,
        title=str(article.get("title") or "Approfondimento legale"),
        alt_text=f"Immagine editoriale per {article.get('title')}",
        caption=generated.warning or "Placeholder professionale generato localmente.",
        category="redazione_ai",
    )
    updated = repo.save_article(int(site["id"]), {**article, "cover_url": asset.get("url")}, article_id=int(article_id))
    audit_studio_site_action(
        "sito_studio.redazione_ai_immagine",
        resource_id=str(article_id),
        details=f"Associata immagine articolo tramite provider {generated.provider}.",
    )
    return {"article": updated, "asset": asset, "provider": generated.provider, "warning": generated.warning, "prompt": prompt}


def publish_ai_article(article_id: int) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    article = repo.get_article(int(site["id"]), int(article_id))
    if article is None:
        raise ValueError("Articolo non trovato.")
    updated = repo.save_article(
        int(site["id"]),
        {
            **article,
            "status": "published",
            "published_at": article.get("published_at") or datetime.now().replace(microsecond=0).isoformat(),
        },
        article_id=int(article_id),
    )
    audit_studio_site_action(
        "sito_studio.redazione_ai_pubblica",
        resource_id=str(article_id),
        details="Articolo AI pubblicato dopo conferma manuale dello studio.",
    )
    return updated
