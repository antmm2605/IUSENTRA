"""Pacchetti di installazione (prodotto, studio, aggiornamento) per la shell React.

Sostituisce la pagina storica `/admin/installazione-pack/` (blueprint
`web/blueprints/installation_pack_admin.py`, template
`web/templates/admin/installazione_pack.html`) e il suo invio
`/admin/installazione-pack/refresh`.

I dati restano quelli di `build_installation_pack_surface`; l'azione di
riallineamento chiama lo stesso servizio con lo stesso studio del modulo storico.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_sezioni import _t, actions, azione, facts, metrics, notes, status, table

STATI = {"ok": "OK", "warning": "Attenzione", "danger": "Errore"}

PERCORSI_STUDIO = (
    ("pack_root", "Radice del pacchetto"),
    ("documents_root", "Documenti"),
    ("attachments_root", "Allegati"),
    ("vectors_root", "Indice semantico"),
    ("backup_root", "Backup"),
)

MEMORIA_PRIVATA = (
    ("facts_path", "Fatti"),
    ("timeline_path", "Cronologia"),
    ("profiles_path", "Profili"),
    ("economic_path", "Economico"),
)


# ------------------------------------------------------------------ lettura


def costruisci(slug: str) -> dict[str, Any]:
    """Payload della pagina, come la rotta storica `dashboard()`."""
    from web.services.installation_pack_surface import build_installation_pack_surface

    return build_installation_pack_surface(selected_slug=str(slug or ""))


def _filtro_studio(studi: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not studi:
        return None
    return {
        "name": "slug",
        "label": "Studio",
        "value": next((_t(s.get("slug")) for s in studi if s.get("selected")), ""),
        "options": [{"value": _t(s.get("slug")), "label": _t(s.get("nome")) or _t(s.get("slug"))} for s in studi],
    }


def _stato(voce: dict[str, Any]) -> str:
    """Il template colora verde solo «ok», rosso solo «danger», giallo tutto il resto."""
    valore = _t(voce.get("status"))
    return valore if valore in {"ok", "danger"} else "warning"


def _sezione_macchina(installazione: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        facts("Avvio della macchina", [
            ("Identificativo dell'installazione", installazione.get("installation_id")),
            ("Profilo di cifratura", installazione.get("encryption_profile")),
            ("Chiavi", "Chiave principale unica per installazione, chiavi derivate separate per database, documenti, backup e token locali."),
            ("Archivio di protezione della macchina", _t(installazione.get("secure_material_store")) or "File locali protetti dell'installazione"),
            ("Cartella di sistema", installazione.get("system_root")),
        ]),
        table(
            "Materiale locale governato",
            [("purpose", "Finalità"), ("storage", "Conservazione")],
            list(installazione.get("secure_material_items") or []),
            empty="Nessun materiale locale censito.",
        ),
    ]


def _sezione_prodotto(prodotto: dict[str, Any]) -> list[dict[str, Any]]:
    confine = prodotto.get("knowledge_boundary") or {}
    conoscenza = [
        {"path": c.get("relative_pack_path"), "kind": c.get("kind"), "sha": f"{_t(c.get('sha256'))[:18]}…" if _t(c.get("sha256")) else ""}
        for c in prodotto.get("public_knowledge_manifest") or []
    ]
    return [
        facts("Pacchetto prodotto", [
            ("Versione del prodotto", prodotto.get("version")),
            ("Allineamento", "Applicazione e Lex sono allineati alla versione corrente."),
            ("Impronta del manifesto (SHA-256)", _t(prodotto.get("manifest_hash_sha256")) or prodotto.get("signature")),
        ]),
        notes("Confine del pacchetto prodotto", [confine.get("public_knowledge"), *(confine.get("forbidden_payloads") or [])], tone="info"),
        table("Conoscenza pubblica bonificata", [("path", "Elemento"), ("kind", "Tipo"), ("sha", "SHA-256")], conoscenza, empty="Nessun elemento di conoscenza pubblica."),
    ]


def _sezione_studio(pacchetto: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not pacchetto:
        return [notes("Pacchetto locale dello studio", ["Nessuno studio disponibile al momento."], tone="info")]
    confine = pacchetto.get("knowledge_boundary") or {}
    percorsi = pacchetto.get("paths") or {}
    memoria = pacchetto.get("private_memory") or {}
    compatibilita = pacchetto.get("compatibility_paths") or {}
    return [
        facts("Pacchetto locale dello studio", [
            ("Studio selezionato", pacchetto.get("studio_nome")),
            ("Archivio effettivo", pacchetto.get("database_backend")),
            ("Indirizzo dello studio", pacchetto.get("studio_slug")),
        ]),
        notes("Confine del pacchetto dello studio", [confine.get("private_memory"), confine.get("product_boundary")], tone="info"),
        facts("Percorsi governati", [(etichetta, percorsi.get(chiave)) for chiave, etichetta in PERCORSI_STUDIO]),
        facts("Memoria privata", [(etichetta, memoria.get(chiave)) for chiave, etichetta in MEMORIA_PRIVATA]),
        facts("Compatibilità con l'archivio attuale", [(_t(k), v) for k, v in compatibilita.items()] if isinstance(compatibilita, dict) else []),
    ]


def _sezione_aggiornamento(payload: dict[str, Any]) -> list[dict[str, Any]]:
    aggiornamento = payload.get("update_pack") or {}
    archivio = payload.get("repository") or {}
    migrazioni = (payload.get("headline") or {}).get("update_migrations") or 0
    return [
        facts("Pacchetto di aggiornamento e archivio SQL", [
            ("Aggiornamento corrente", f"{_t(aggiornamento.get('from_version'))} → {_t(aggiornamento.get('to_version'))}"),
            ("Integrità del manifesto", _t(aggiornamento.get("manifest_hash_sha256")) or aggiornamento.get("signature")),
            ("Archivio dei pacchetti", archivio.get("backend_kind")),
            ("Pacchetti registrati", f"prodotto {_t(archivio.get('product_packs')) or '0'} · studio {_t(archivio.get('studio_local_packs')) or '0'} · aggiornamento {_t(archivio.get('update_packs')) or '0'}"),
            ("Percorso dell'archivio", archivio.get("db_path")),
            ("Migrazioni incluse", f"{migrazioni} file SQL tra SQLite e PostgreSQL censiti nel manifesto corrente."),
        ]),
        status("Servizi del prodotto previsti", [
            {"title": s.get("label"), "summary": s.get("detail"), "status": _stato(s), "statusLabel": STATI[_stato(s)]}
            for s in payload.get("service_runtime") or []
        ]),
        status("Dipendenze locali", [
            {"title": d.get("label"), "summary": d.get("detail"), "detail": " · ".join(_t(m) for m in d.get("meta") or [] if _t(m)), "status": _stato(d), "statusLabel": STATI[_stato(d)]}
            for d in payload.get("runtime_dependencies") or []
        ]),
    ]


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    titoli = payload.get("headline") or {}
    pacchetto = payload.get("selected_studio_pack")
    return {
        "title": "Pacchetti di installazione",
        "subtitle": "Separazione netta tra prodotto distribuibile, memoria privata dello studio e aggiornamenti governati dal superamministratore.",
        "filter": _filtro_studio(list(payload.get("studios") or [])),
        "sections": [
            actions("Riallineamento", [
                azione(
                    "refresh",
                    "Rigenera avvio e manifesti",
                    tone="primary",
                    params={"slug": _t((pacchetto or {}).get("studio_slug"))},
                    detail="Ricalcola l'avvio dell'installazione e registra di nuovo i manifesti dei pacchetti.",
                ),
            ]),
            notes("Regola di piattaforma", [payload.get("superadmin_rule")], tone="info"),
            metrics([
                {"label": "Servizi del prodotto", "value": titoli.get("product_services", 0)},
                {"label": "Conoscenza pubblica", "value": titoli.get("public_knowledge_assets", 0)},
                {"label": "Pacchetti degli studi", "value": titoli.get("studio_local_packs", 0)},
                {"label": "Migrazioni di aggiornamento", "value": titoli.get("update_migrations", 0)},
            ]),
            *_sezione_macchina(payload.get("installation") or {}),
            *_sezione_prodotto(payload.get("product_pack") or {}),
            *_sezione_studio(pacchetto),
            *_sezione_aggiornamento(payload),
        ],
    }


# ------------------------------------------------------------------ azioni


def _riallinea(dati: dict[str, Any]) -> dict[str, Any]:
    from flask import current_app

    from web.services.installation_pack_surface import build_installation_pack_surface

    valore = dati.get("slug")
    slug = str("" if valore is None else valore).strip().lower()
    try:
        build_installation_pack_surface(selected_slug=slug)
    except Exception:  # pragma: no cover - difensivo UI
        current_app.logger.exception("Errore refresh pack installazione")
        return {"ok": False, "message": "Errore nel riallineamento dei pacchetti di installazione.", "tone": "danger", "sections": []}
    return {
        "ok": True,
        "message": "Avvio dell'installazione, manifesto del pacchetto prodotto, pacchetti degli studi e pacchetto di aggiornamento riallineati.",
        "tone": "success",
        "sections": [],
    }


AZIONI = {"refresh": _riallinea}


def esegui(azione: str, params: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    gestore = AZIONI.get(str(azione or "").strip())
    if gestore is None:
        return {"ok": False, "message": "Azione non disponibile in questa pagina.", "tone": "danger", "sections": []}
    return gestore({**(values or {}), **(params or {})})


__all__ = ["adatta", "costruisci", "esegui"]
