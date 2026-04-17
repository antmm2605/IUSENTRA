"""Registry tecnico di governance prodotto per storage, autorizzazioni e audit."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from pct.auth import DESCRIZIONI_RUOLI, PERMESSI, TUTTI_PERMESSI, RuoloUtente


@dataclass(frozen=True)
class StorageParityEntry:
    module_id: str
    domain: str
    label: str
    source_of_truth: str
    json_read: bool
    json_write: bool
    sqlite_read: bool
    sqlite_write: bool
    postgres_read: bool
    postgres_write: bool
    parity_note: str
    migration_wave: str
    fallback_mode: str
    consistency_checks: tuple[str, ...] = field(default_factory=tuple)
    test_refs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AuthorizationSurface:
    surface_id: str
    label: str
    scope: str
    risk: str
    permission_keys: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class MigrationPhase:
    phase_id: str
    title: str
    objective: str
    entry_criteria: tuple[str, ...]
    consistency_checks: tuple[str, ...]
    fallback_rules: tuple[str, ...]


@dataclass(frozen=True)
class E2EFlow:
    flow_id: str
    label: str
    coverage: str
    systems: tuple[str, ...]
    test_refs: tuple[str, ...]


@dataclass(frozen=True)
class ObservabilityCapability:
    capability_id: str
    label: str
    surface: str
    sources: tuple[str, ...]
    outcome: str
    audit_depth: str
    status: str


STORAGE_PARITY_REGISTRY: tuple[StorageParityEntry, ...] = (
    StorageParityEntry(
        module_id="auth_audit",
        domain="Identita'",
        label="Autenticazione e audit",
        source_of_truth="GestioneUtenti + audit_log tenant-aware",
        json_read=True,
        json_write=True,
        sqlite_read=True,
        sqlite_write=True,
        postgres_read=False,
        postgres_write=False,
        parity_note="JSON e SQLite sono operativi; PostgreSQL e' solo configurabile a livello tenant e non ancora sorgente attiva del dominio.",
        migration_wave="Wave 1 - identita' e audit",
        fallback_mode="Fallback immediato a JSON tenant-aware se studio.db e' vuoto o non disponibile.",
        consistency_checks=(
            "Conteggio utenti attivi e per ruolo coerente tra sorgente e destinazione.",
            "Conteggio eventi audit e ultimo timestamp coerenti dopo il cutover.",
        ),
        test_refs=("tests/test_auth.py",),
    ),
    StorageParityEntry(
        module_id="clienti_condivisioni",
        domain="Core operativo",
        label="Clienti e condivisioni",
        source_of_truth="GestioneClienti + condivisioni tenant-aware",
        json_read=True,
        json_write=True,
        sqlite_read=True,
        sqlite_write=True,
        postgres_read=False,
        postgres_write=False,
        parity_note="Parita' R/W chiusa su JSON e SQLite. PostgreSQL non e' ancora attivo per il repository applicativo.",
        migration_wave="Wave 2 - core operativo",
        fallback_mode="Ritorno automatico a JSON se SQLite non e' seedato.",
        consistency_checks=(
            "Totale anagrafiche, codici fiscali e email univoci invariati.",
            "Condivisioni e riferimenti a cartelle condivise preservati.",
        ),
        test_refs=("tests/test_web_bootstrap.py",),
    ),
    StorageParityEntry(
        module_id="fascicoli_documenti",
        domain="Core operativo",
        label="Fascicoli e documenti",
        source_of_truth="GestioneFascicoli + filesystem documentale",
        json_read=True,
        json_write=True,
        sqlite_read=True,
        sqlite_write=True,
        postgres_read=False,
        postgres_write=False,
        parity_note="I metadati hanno parita' JSON/SQLite; l'archivio documentale resta filesystem-first anche in caso di rollout esterno.",
        migration_wave="Wave 2 - core operativo",
        fallback_mode="Metadati su JSON/SQLite, documenti sempre sul filesystem tenant.",
        consistency_checks=(
            "Numero fascicoli e id_cliente coerenti.",
            "Conteggio documenti e percorsi allegati non degradati dal passaggio.",
        ),
        test_refs=("tests/test_web_bootstrap.py",),
    ),
    StorageParityEntry(
        module_id="agenda_sync",
        domain="Programmazione",
        label="Agenda e sincronizzazione calendario",
        source_of_truth="Agenda + calendar_sync tenant-aware",
        json_read=True,
        json_write=True,
        sqlite_read=True,
        sqlite_write=True,
        postgres_read=False,
        postgres_write=False,
        parity_note="Agenda e sync sono allineati su JSON/SQLite; PostgreSQL resta da chiudere con repository dedicato.",
        migration_wave="Wave 2 - core operativo",
        fallback_mode="JSON operativo se il runtime SQL locale non e' disponibile.",
        consistency_checks=(
            "Numero appuntamenti, date ISO e link a fascicoli invariati.",
            "Ultimo sync calendario e token locali preservati.",
        ),
        test_refs=("tests/test_web_bootstrap.py",),
    ),
    StorageParityEntry(
        module_id="scadenziario",
        domain="Programmazione",
        label="Scadenziario",
        source_of_truth="GestioneScadenziario tenant-aware",
        json_read=True,
        json_write=True,
        sqlite_read=True,
        sqlite_write=True,
        postgres_read=False,
        postgres_write=False,
        parity_note="Dominio gia' vicino al core operativo; manca il backend PostgreSQL nativo.",
        migration_wave="Wave 2 - core operativo",
        fallback_mode="Fallback a JSON con guardia su riferimenti a fascicolo/appuntamento.",
        consistency_checks=(
            "Scadenze aperte e priorita' coerenti.",
            "Riferimenti a fascicoli e appuntamenti validi dopo la migrazione.",
        ),
        test_refs=("tests/test_web_bootstrap.py",),
    ),
    StorageParityEntry(
        module_id="template_atti",
        domain="Produzione atti",
        label="Template atti e preferenze editor",
        source_of_truth="GestioneTemplateAtti tenant-aware",
        json_read=True,
        json_write=True,
        sqlite_read=True,
        sqlite_write=True,
        postgres_read=False,
        postgres_write=False,
        parity_note="Repository e preferenze editor sono governati su JSON/SQLite; PostgreSQL non e' ancora sorgente attiva.",
        migration_wave="Wave 3 - workspace professionali",
        fallback_mode="JSON per compatibilita' immediata dei layout editor.",
        consistency_checks=(
            "Conteggio template built-in e custom invariato.",
            "Preferenze di layout e collezioni verticali coerenti.",
        ),
        test_refs=("tests/test_template_atti_workspace.py", "tests/test_template_atti_repository.py"),
    ),
    StorageParityEntry(
        module_id="preventivi",
        domain="Commerciale",
        label="Preventivi e workflow commerciale",
        source_of_truth="Repository preventivi tenant-aware",
        json_read=True,
        json_write=True,
        sqlite_read=False,
        sqlite_write=False,
        postgres_read=False,
        postgres_write=False,
        parity_note="Dominio ancora JSON-first: serve repository SQLite/SQL esterno dedicato prima del cutover cloud.",
        migration_wave="Wave 4 - economico",
        fallback_mode="JSON tenant-aware come backend canonico corrente.",
        consistency_checks=(
            "Preventivi per stato e pratica coerenti.",
            "Confronto preventivato vs realizzato invariato nel report di controllo.",
        ),
        test_refs=(),
    ),
    StorageParityEntry(
        module_id="fatturazione_pagamenti",
        domain="Economico",
        label="Fatturazione e pagamenti",
        source_of_truth="Repository parcelle tenant-aware",
        json_read=True,
        json_write=True,
        sqlite_read=False,
        sqlite_write=False,
        postgres_read=False,
        postgres_write=False,
        parity_note="Dominio amministrativo reale ma non ancora portato sul percorso SQLite/SQL esterno.",
        migration_wave="Wave 4 - economico",
        fallback_mode="JSON tenant-aware con report di consistenza prima del cutover.",
        consistency_checks=(
            "Totale documenti emessi, incassato e residui coerenti.",
            "Collegamenti a preventivi e fascicoli preservati.",
        ),
        test_refs=(),
    ),
    StorageParityEntry(
        module_id="legal_intelligence",
        domain="Motori legali",
        label="Legal intelligence, monitoraggio e audit fonti",
        source_of_truth="Repository motori + snapshot fonti ufficiali",
        json_read=True,
        json_write=True,
        sqlite_read=False,
        sqlite_write=False,
        postgres_read=False,
        postgres_write=False,
        parity_note="Dominio AI/prodotto pienamente operativo su JSON; non ancora migrato su repository SQL transazionale.",
        migration_wave="Wave 5 - intelligence",
        fallback_mode="JSON tenant-aware con snapshot e audit traces locali.",
        consistency_checks=(
            "Numero motori, fonti, alert e audit traces invariati.",
            "Hash e timestamp delle fonti ufficiali preservati.",
        ),
        test_refs=("tests/test_legal_intelligence.py",),
    ),
    StorageParityEntry(
        module_id="giurisprudenza",
        domain="Motori legali",
        label="Giurisprudenza e corpus interno",
        source_of_truth="GestioneGiurisprudenza tenant-aware",
        json_read=True,
        json_write=True,
        sqlite_read=False,
        sqlite_write=False,
        postgres_read=False,
        postgres_write=False,
        parity_note="Archivio strutturato su JSON tenant-aware; manca il repository SQL dedicato.",
        migration_wave="Wave 5 - intelligence",
        fallback_mode="JSON tenant-aware come corpus canonico corrente.",
        consistency_checks=(
            "Conteggio sentenze, massime e tag invariato.",
            "Riferimenti ufficiali e deduplica coerenti dopo il trasferimento.",
        ),
        test_refs=(),
    ),
    StorageParityEntry(
        module_id="telematico",
        domain="Telematico",
        label="Telematico, PST, PDP, PAT e PTT/SIGIT",
        source_of_truth="Workflow locale + repository telematico + filesystem upload",
        json_read=True,
        json_write=True,
        sqlite_read=True,
        sqlite_write=True,
        postgres_read=False,
        postgres_write=False,
        parity_note="Workflow e capability repository hanno una base locale forte; il path PostgreSQL non e' ancora chiuso.",
        migration_wave="Wave 3 - workspace professionali",
        fallback_mode="Metadati su JSON/SQLite, file e buste sempre su filesystem tenant.",
        consistency_checks=(
            "Stati deposito, id_deposito e gruppi documento coerenti.",
            "Repository capability e fonti telematiche allineati tra runtime e storage.",
        ),
        test_refs=("tests/test_polisweb.py", "tests/test_simulazione_deposito.py"),
    ),
    StorageParityEntry(
        module_id="workspace_intelligence",
        domain="Cabina intelligente",
        label="Workspace intelligence e cockpit operativi",
        source_of_truth="Snapshot workspace_intelligence tenant-aware",
        json_read=True,
        json_write=True,
        sqlite_read=False,
        sqlite_write=False,
        postgres_read=False,
        postgres_write=False,
        parity_note="Snapshot reale su JSON; da portare su repository SQL solo dopo chiusura dei domini sorgente.",
        migration_wave="Wave 5 - intelligence",
        fallback_mode="JSON come vista derivata fino a consolidamento dei repository sorgente.",
        consistency_checks=(
            "Headline, alert e KPI invariati a parita' di sorgenti.",
            "Nessuna divergenza tra snapshot e domini di origine.",
        ),
        test_refs=(),
    ),
    StorageParityEntry(
        module_id="local_ai",
        domain="AI locale",
        label="Local AI, modelli e RAG locale",
        source_of_truth="SQLite locale + filesystem modelli/embeddings",
        json_read=False,
        json_write=False,
        sqlite_read=True,
        sqlite_write=True,
        postgres_read=False,
        postgres_write=False,
        parity_note="Il runtime AI locale resta host-first: PostgreSQL non e' backend primario per modelli, cache e artefatti locali.",
        migration_wave="Fuori scope come backend primario",
        fallback_mode="SQLite locale e filesystem sullo stesso host del runtime.",
        consistency_checks=(
            "Stato runtime, modelli risolti e cache embedding coerenti.",
            "Assenza di blocchi sulle funzioni core se il runtime locale non e' disponibile.",
        ),
        test_refs=("tests/test_web_bootstrap.py",),
    ),
)


AUTHORIZATION_SURFACES: tuple[AuthorizationSurface, ...] = (
    AuthorizationSurface(
        surface_id="tenant_platform",
        label="Tenant e superfici di piattaforma",
        scope="Piattaforma / multi-tenant",
        risk="critico",
        permission_keys=("tenant.leggi", "tenant.configura", "tenant.impersona"),
        note="Separazione netta tra superadmin di piattaforma e ruoli di tenant.",
    ),
    AuthorizationSurface(
        surface_id="admin_surfaces",
        label="Superfici amministrative",
        scope="Studio / configurazione",
        risk="alto",
        permission_keys=("admin.leggi", "admin.configura", "autorizzazioni.leggi", "autorizzazioni.scrivi"),
        note="Policy, storage, bootstrap e pannelli di governance devono restare presidiati.",
    ),
    AuthorizationSurface(
        surface_id="telematico_flows",
        label="Consultazione, import e deposito telematico",
        scope="Operativo / telematico",
        risk="critico",
        permission_keys=("telematico.leggi", "telematico.importa", "telematico.valida", "telematico.deposita"),
        note="Separazione esplicita tra consultazione, sincronizzazione, predeposito e deposito.",
    ),
    AuthorizationSurface(
        surface_id="ai_surfaces",
        label="Assistenti AI, policy e audit",
        scope="Operativo / AI",
        risk="alto",
        permission_keys=("ai.usa", "ai.configura", "ai.audit"),
        note="Lex e gli assistenti devono usare policy separate da quelle amministrative e con audit esplicito.",
    ),
    AuthorizationSurface(
        surface_id="audit_compliance",
        label="Audit, export e compliance",
        scope="Controllo / conformita'",
        risk="alto",
        permission_keys=("audit.leggi", "audit.esporta"),
        note="La lettura e soprattutto l'esportazione dei log devono essere tracciate e ristrette.",
    ),
)


MIGRATION_PROGRAM: tuple[MigrationPhase, ...] = (
    MigrationPhase(
        phase_id="inventory",
        title="Inventario e precheck",
        objective="Mappare sorgenti JSON/SQLite per dominio e fermare il cutover se esistono criticita' bloccanti.",
        entry_criteria=(
            "Storage manifest coerente con selected_mode ed effective_runtime_kind.",
            "Verifica integrita' JSON senza errori critici aperti.",
        ),
        consistency_checks=(
            "Conteggi per modulo da JSON e SQLite raccolti prima del cutover.",
            "Hash e timestamp dei file di lavoro congelati nel report di precheck.",
        ),
        fallback_rules=(
            "Nessun cutover se StudioDB e' vuoto ma i JSON legacy contengono dati.",
            "Se il precheck fallisce, il tenant resta in effective_mode corrente.",
        ),
    ),
    MigrationPhase(
        phase_id="mirror",
        title="Mirror repository e read parity",
        objective="Accendere repository SQL dominio per dominio e verificare la parita' di lettura.",
        entry_criteria=(
            "Repository dominio disponibile con test di lettura e serializzazione.",
            "UI e servizi applicativi in grado di leggere senza dipendere da JSON hardcoded.",
        ),
        consistency_checks=(
            "Liste, dettaglio e statistiche restituiscono gli stessi record del backend sorgente.",
            "Id, relazioni e ordinamenti principali coincidono.",
        ),
        fallback_rules=(
            "Se la parity in lettura non e' chiusa, il dominio non passa alla wave successiva.",
        ),
    ),
    MigrationPhase(
        phase_id="shadow_write",
        title="Shadow write e report di consistenza",
        objective="Scrivere in parallelo su backend nuovo e backend corrente per domini ad alto rischio.",
        entry_criteria=(
            "Read parity chiusa per il dominio.",
            "Audit attivo per azioni scrittura del dominio.",
        ),
        consistency_checks=(
            "Conteggi read/write parity per operazione e checksum dei payload serializzati.",
            "Riconciliazione automatica di differenze su chiavi e riferimenti forti.",
        ),
        fallback_rules=(
            "Alla prima divergenza bloccante, la scrittura resta canonica sul backend corrente.",
        ),
    ),
    MigrationPhase(
        phase_id="cutover",
        title="Cutover tenant per tenant",
        objective="Portare il tenant sul backend target con rollback documentato e senza fermare i moduli core.",
        entry_criteria=(
            "Shadow write stabile per una finestra minima di osservazione.",
            "Test end-to-end verdi sui flussi principali del tenant.",
        ),
        consistency_checks=(
            "Smoke test applicativo dopo il cutover e confronto headline governance prima/dopo.",
            "Verifica login, clienti, fascicoli, agenda, telematico e audit.",
        ),
        fallback_rules=(
            "Rollback immediato alla sorgente precedente se healthcheck o report consistenza falliscono.",
            "I documenti su filesystem non vengono spostati durante il rollback.",
        ),
    ),
)


E2E_FLOWS: tuple[E2EFlow, ...] = (
    E2EFlow(
        flow_id="bootstrap_admin",
        label="Bootstrap applicazione, login e superfici admin",
        coverage="integrato",
        systems=("Flask factory", "auth", "template globals", "admin"),
        test_refs=("tests/test_web_bootstrap.py", "tests/test_observability_runtime.py"),
    ),
    E2EFlow(
        flow_id="storage_migration",
        label="Migrazione dati JSON -> SQLite con fallback",
        coverage="nuovo presidio",
        systems=("pct.database", "tenant storage", "auth", "runtime storage"),
        test_refs=("tests/test_storage_governance.py",),
    ),
    E2EFlow(
        flow_id="telematico_portali",
        label="Consultazione, import e regole portali telematici",
        coverage="integrato",
        systems=("telematico runtime", "portali ufficiali", "repository capability"),
        test_refs=("tests/test_polisweb.py", "tests/test_simulazione_deposito.py"),
    ),
    E2EFlow(
        flow_id="template_workspace",
        label="Workspace template atti e collezioni verticali",
        coverage="integrato",
        systems=("catalogo built-in", "workspace atti", "repository template"),
        test_refs=("tests/test_template_atti_workspace.py", "tests/test_template_atti_repository.py"),
    ),
    E2EFlow(
        flow_id="governance_surface",
        label="Governance prodotto: storage, autorizzazioni, audit e osservabilita'",
        coverage="nuovo presidio",
        systems=("admin", "runtime metrics", "auth audit", "registry governance"),
        test_refs=("tests/test_product_governance_surface.py",),
    ),
)


OBSERVABILITY_CAPABILITIES: tuple[ObservabilityCapability, ...] = (
    ObservabilityCapability(
        capability_id="runtime_http_lex",
        label="Metriche runtime HTTP e Lex",
        surface="Admin / osservabilita'",
        sources=("runtime_metrics", "lex first token"),
        outcome="Latenza media, p95, endpoint bucket e first token.",
        audit_depth="runtime tecnico",
        status="attivo",
    ),
    ObservabilityCapability(
        capability_id="storage_governance",
        label="Storage parity e programma di migrazione",
        surface="Admin / governance prodotto",
        sources=("storage manifest", "registry parity", "migration phases"),
        outcome="Matrice read/write parity, fallback e wave di migrazione.",
        audit_depth="prodotto",
        status="attivo",
    ),
    ObservabilityCapability(
        capability_id="auth_audit",
        label="Audit accessi, ruoli e superfici sensibili",
        surface="Admin / governance prodotto",
        sources=("GestioneUtenti", "audit_log", "permission catalog"),
        outcome="Conteggi audit, superfici presidiate e ruoli autorizzati.",
        audit_depth="prodotto",
        status="attivo",
    ),
    ObservabilityCapability(
        capability_id="telematico_catalog",
        label="Capability telematiche e monitoraggio fonti",
        surface="Centro Servizi Telematici / Motori legali",
        sources=("telematico_repository", "legal_intelligence"),
        outcome="Capacita' ufficiali, fonti, warning e stato canali.",
        audit_depth="prodotto",
        status="attivo",
    ),
    ObservabilityCapability(
        capability_id="deploy_health",
        label="Salute sistema e readiness deploy",
        surface="Admin / salute sistema",
        sources=("healthcheck", "OCR runtime", "provider locali", "backup"),
        outcome="Stato deploy, backup, AI locale e coda OCR.",
        audit_depth="runtime + prodotto",
        status="attivo",
    ),
)


def _mode_status(read_enabled: bool, write_enabled: bool) -> str:
    if read_enabled and write_enabled:
        return "R/W"
    if read_enabled:
        return "R"
    if write_enabled:
        return "W"
    return "-"


def _postgres_parity_label(entry: StorageParityEntry) -> str:
    if entry.postgres_read and entry.postgres_write:
        return "parita' completa"
    if entry.postgres_read or entry.postgres_write:
        return "parita' parziale"
    return "non attiva"


def build_storage_parity_payload() -> dict[str, Any]:
    rows = []
    postgres_full = 0
    for entry in STORAGE_PARITY_REGISTRY:
        row = asdict(entry)
        row["json_mode"] = _mode_status(entry.json_read, entry.json_write)
        row["sqlite_mode"] = _mode_status(entry.sqlite_read, entry.sqlite_write)
        row["postgres_mode"] = _mode_status(entry.postgres_read, entry.postgres_write)
        row["postgres_parity"] = _postgres_parity_label(entry)
        rows.append(row)
        if entry.postgres_read and entry.postgres_write:
            postgres_full += 1
    return {
        "summary": {
            "domains_total": len(rows),
            "sqlite_rw_ready": sum(1 for item in STORAGE_PARITY_REGISTRY if item.sqlite_read and item.sqlite_write),
            "postgres_rw_ready": postgres_full,
            "fallback_ready": sum(1 for item in STORAGE_PARITY_REGISTRY if item.fallback_mode),
        },
        "rows": rows,
    }


def build_authorization_model_payload() -> dict[str, Any]:
    catalog_by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    for category, key, label in TUTTI_PERMESSI:
        catalog_by_category[category].append({"key": key, "label": label})

    role_rows = []
    for role in RuoloUtente:
        desc = DESCRIZIONI_RUOLI.get(role, {})
        permissions = sorted(PERMESSI.get(role, [])) if role != RuoloUtente.SUPERADMIN else sorted({perm for _, perm, _ in TUTTI_PERMESSI})
        role_rows.append(
            {
                "role": role.value,
                "label": role.value.replace("_", " ").title(),
                "description": str(desc.get("descrizione") or "").strip(),
                "color": str(desc.get("colore") or "secondary"),
                "permissions_count": len(permissions),
                "permissions": permissions,
            }
        )

    surface_rows = []
    for surface in AUTHORIZATION_SURFACES:
        allowed_roles = []
        for role in RuoloUtente:
            permissions = set(PERMESSI.get(role, []))
            if role == RuoloUtente.SUPERADMIN or all(key in permissions for key in surface.permission_keys):
                allowed_roles.append(role.value)
        surface_rows.append(
            {
                **asdict(surface),
                "allowed_roles": allowed_roles,
            }
        )

    return {
        "summary": {
            "roles_total": len(role_rows),
            "permission_families": len(catalog_by_category),
            "surfaces_total": len(surface_rows),
            "high_risk_surfaces": sum(1 for surface in AUTHORIZATION_SURFACES if surface.risk in {"alto", "critico"}),
        },
        "permission_catalog": dict(catalog_by_category),
        "roles": role_rows,
        "surfaces": surface_rows,
    }


def build_migration_program_payload() -> dict[str, Any]:
    return {
        "summary": {
            "phases_total": len(MIGRATION_PROGRAM),
            "domains_sqlite_ready": sum(1 for item in STORAGE_PARITY_REGISTRY if item.sqlite_read and item.sqlite_write),
            "domains_postgres_pending": sum(1 for item in STORAGE_PARITY_REGISTRY if not (item.postgres_read and item.postgres_write)),
        },
        "phases": [asdict(phase) for phase in MIGRATION_PROGRAM],
    }


def build_e2e_flow_payload() -> dict[str, Any]:
    return {
        "summary": {
            "flows_total": len(E2E_FLOWS),
            "new_presidi": sum(1 for flow in E2E_FLOWS if flow.coverage == "nuovo presidio"),
        },
        "rows": [asdict(flow) for flow in E2E_FLOWS],
    }


def build_observability_capabilities_payload(*, audit_events: int = 0, runtime_ok: bool = True) -> dict[str, Any]:
    rows = [asdict(capability) for capability in OBSERVABILITY_CAPABILITIES]
    return {
        "summary": {
            "capabilities_total": len(rows),
            "product_level_capabilities": sum(1 for item in OBSERVABILITY_CAPABILITIES if "prodotto" in item.audit_depth),
            "audit_events": int(audit_events or 0),
            "runtime_ok": bool(runtime_ok),
        },
        "rows": rows,
    }
