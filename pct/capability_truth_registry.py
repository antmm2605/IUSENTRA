"""Catalogo versionato e conservativo della prontezza prodotto.

Questo modulo non decide l'operatività di un flusso legale e non effettua
controlli remoti. Rende invece esplicita la prova che manca: una capability
senza un'evidenza corrente non può risultare ``verificata``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final, Literal


RegistryStatus = Literal["verificata", "parziale", "da_verificare", "bloccata", "non_applicabile"]
EvidenceStatus = Literal["pass", "da_verificare", "non_eseguito", "non_applicabile", "riferimento_disponibile"]

REGISTRY_VERSION: Final = "2026.08.23.1"
P0_CAPABILITY_IDS: Final = (
    "autenticazione-cambio-tenant",
    "apertura-cliente",
    "conflitto",
    "preventivo",
    "mandato",
    "fascicolo",
    "attivita",
    "documento",
    "pec",
    "scadenza",
    "deposito",
    "ricevute",
    "fattura",
    "pagamento",
    "portale",
    "audit",
    "chiusura-fascicolo",
)

_STATUS_LABELS: Final[dict[str, tuple[str, str]]] = {
    "verificata": ("Verificata", "success"),
    "parziale": ("Verifica parziale", "warning"),
    "da_verificare": ("Da verificare", "warning"),
    "bloccata": ("Bloccata", "danger"),
    "non_applicabile": ("Non applicabile", "neutral"),
}


@dataclass(frozen=True, slots=True)
class Evidence:
    kind: str
    status: EvidenceStatus
    label: str
    reference: str
    last_verified: str = ""
    note: str = ""


@dataclass(frozen=True, slots=True)
class Capability:
    capability_id: str
    module: str
    owner: str
    route: str
    api: str
    backend: str
    operations: tuple[str, ...]
    permissions: tuple[str, ...]
    storage: str
    feature_flag: str
    status: RegistryStatus
    status_note: str
    dependencies: tuple[str, ...]
    limitations: str
    rollback: str
    next_action: str
    tests: tuple[str, ...]
    browser_evidence: Evidence
    ci_evidence: Evidence
    provider_evidence: Evidence


def _evidence(
    kind: str,
    status: EvidenceStatus,
    label: str,
    reference: str,
    note: str = "",
) -> Evidence:
    return Evidence(kind=kind, status=status, label=label, reference=reference, note=note)


_BROWSER_PENDING: Final = _evidence(
    "browser",
    "non_eseguito",
    "Prova browser non ancora registrata",
    "Fase 2 — golden journeys",
    "La presenza della UI non equivale a una prova reale sulla copia locale.",
)
_CI_REFERENCE: Final = _evidence(
    "ci",
    "riferimento_disponibile",
    "Test associati censiti; esito corrente da registrare",
    "Inventario test della capability",
    "Il registro non trasforma un file di test in un PASS senza esecuzione corrente.",
)
_PROVIDER_NA: Final = _evidence(
    "provider",
    "non_applicabile",
    "Nessun provider esterno necessario",
    "",
)
_PROVIDER_PENDING: Final = _evidence(
    "provider",
    "da_verificare",
    "Verifica provider non ancora registrata",
    "Fase 2 — tenant sintetico e canary non distruttivo",
)


P0_CAPABILITIES: Final[tuple[Capability, ...]] = (
    Capability(
        "autenticazione-cambio-tenant", "Autenticazione e cambio tenant", "Identità e sicurezza",
        "/login", "/api/v1/ui/sessione e bootstrap", "pct.auth + shell React",
        ("accesso", "chiusura sessione", "cambio tenant autorizzato"), ("sessione autenticata",),
        "GestioneUtenti + audit tenant-aware (SQLite/PostgreSQL)", "routes.appV2.amministrazione",
        "da_verificare", "RBAC e isolamento sono censiti; manca prova golden corrente sui ruoli e tenant A/B.",
        ("sessione", "RBAC", "tenant proprietario"), "Nessuna promozione senza prova multi-ruolo e multi-tenant.",
        "Commit applicativo precedente e ricreazione Docker governata.", "Eseguire matrice login/cambio tenant con quattro ruoli.",
        ("tests/test_auth.py", "tests/test_web_bootstrap.py"), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "apertura-cliente", "Apertura cliente", "Anagrafiche", "/clienti", "/api/v1/ui/clienti",
        "web.services.react_clienti_bridge", ("ricerca", "apertura scheda", "consultazione cartella"),
        ("clienti.leggi",), "GestioneClienti tenant-aware; SQLite/PostgreSQL con mirror governato", "routes.appV2.clienti",
        "da_verificare", "Superficie React censita; manca prova reale per ruoli e tenant separati.",
        ("anagrafiche", "fascicoli"), "Dati e permessi devono restare del tenant corrente.",
        "Commit applicativo precedente e ricreazione Docker governata.", "Golden journey apertura cliente e controllo isolamento.",
        ("tests/test_web_bootstrap.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "conflitto", "Controllo conflitto", "Anagrafiche e fascicoli", "/ricerca-studio", "/api/v1/ui/ricerca-studio",
        "Ricerca Studio e repository tenant-aware", ("ricerca nominativi", "segnalazione potenziale conflitto"),
        ("clienti.leggi", "fascicoli.leggi"), "Repository clienti/fascicoli tenant-aware", "Nessun flag dedicato censito",
        "da_verificare", "Il percorso e il perimetro dati sono censiti; il criterio di conflitto richiede prova e fixture dedicate.",
        ("ricerca studio", "anagrafiche", "fascicoli"), "Non sostituisce la valutazione professionale del conflitto.",
        "Commit applicativo precedente e ripristino dei dati di fixture.", "Definire fixture conflitto positiva, negativa e cross-tenant.",
        ("tests/test_global_search.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "preventivo", "Preventivo", "Commerciale", "/preventivi", "/api/v1/ui/preventivi",
        "web.services.react_preventivi_bridge", ("creazione", "calcolo", "stato", "apertura fascicolo"),
        ("preventivi.leggi", "preventivi.scrivi"), "Repository preventivi tenant-aware; SQLite/PostgreSQL", "routes.appV2.preventivi",
        "da_verificare", "La superficie React e le API sono censite; serve E2E con dati sintetici e ruoli.",
        ("compensi forensi", "clienti", "fascicoli"), "Importi, calcolo e audit vanno provati dal backend canonico.",
        "Commit applicativo precedente e rollback stato documentato.", "Golden journey preventivo da cliente a fascicolo.",
        ("tests/test_preventivi_wizard.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "mandato", "Mandato e conferimento", "Commerciale", "/preventivi/conferimento/nuovo", "/api/v1/ui/preventivi/conferimento/nuovo",
        "Bridge preventivi/conferimenti", ("creazione conferimento", "stato", "apertura fascicolo"),
        ("preventivi.leggi", "preventivi.scrivi"), "Repository conferimenti tenant-aware; SQLite/PostgreSQL", "routes.appV2.preventivi",
        "da_verificare", "Il percorso è censito; firma, dati obbligatori e passaggio a fascicolo attendono prova integrata.",
        ("preventivi", "fascicoli", "audit"), "Non certifica la validità giuridica del mandato senza verifica dei requisiti.",
        "Commit applicativo precedente e rollback stato documentato.", "Golden journey conferimento con controllo audit e permessi.",
        ("tests/test_preventivi_conferimento_route.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "fascicolo", "Fascicolo", "Fascicoli", "/fascicoli", "/api/v1/ui/fascicoli",
        "web.services.react_fascicoli_bridge", ("lista", "creazione", "apertura workspace", "archivio"),
        ("fascicoli.leggi", "fascicoli.scrivi"), "GestioneFascicoli + filesystem tenant-aware; metadati SQLite/PostgreSQL", "routes.appV2.fascicoli",
        "da_verificare", "La UI React è censita; fixture e verifica di apertura multi-ruolo sono previste nella Fase 2.",
        ("clienti", "documenti", "deposito"), "Il lettore e gli allegati richiedono prove formato per formato.",
        "Commit applicativo precedente; nessuna cancellazione dei dati tenant.", "Golden journey fascicolo nuovo/aperto con tenant A/B.",
        ("tests/test_fascicoli.py", "tests/test_web_bootstrap.py"), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "attivita", "Attività operative", "Regia Operativa", "/regia-operativa", "/api/v1/ui/regia-operativa",
        "Bridge Regia Operativa", ("lettura attività", "prioritizzazione", "apertura contesto"),
        ("fascicoli.leggi",), "Repository operativi tenant-aware", "routes.appV2.regiaOperativa",
        "da_verificare", "Le attività sono censite come superficie React; serve prova delle azioni collegate e dello stato vuoto.",
        ("agenda", "scadenziario", "fascicoli"), "Il registro non inferisce la completezza delle singole attività.",
        "Commit applicativo precedente e ricreazione Docker governata.", "Golden journey attività da apertura a contesto collegato.",
        ("tests/test_regia_ui_react.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "documento", "Documento e lettore interno", "Documenti", "/documenti", "/api/v1/ui/documenti",
        "Bridge documenti e preview tenant-aware", ("elenco", "preview interna", "download autorizzato"),
        ("documenti.leggi",), "Filesystem documentale tenant-aware + metadati fascicolo", "routes.appV2.documenti",
        "da_verificare", "Il lettore interno è requisito primario; la matrice PDF/ZIP/XML/EML/DOCX/P7M deve essere provata realmente.",
        ("fascicoli", "PEC", "preview firmata"), "Nessun formato non supportato deve aprire un fallback esterno silenzioso.",
        "Commit applicativo precedente, senza toccare volumi documentali.", "Golden journey lettore con almeno PDF, ZIP e un formato non PDF.",
        ("tests/test_signed_attachment_preview.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "pec", "PEC", "Comunicazioni", "/email", "/api/v1/ui/email",
        "web.services.react_email_bridge + Local Signer", ("lettura", "preview", "preparazione invio locale", "ricevute"),
        ("pec.leggi", "pec.scrivi"), "Repository PEC tenant-aware; credenziali solo sul PC locale", "routes.appV2.email",
        "da_verificare", "La UI è censita; l'invio operativo deve restare locale e richiede tenant sintetico/canary non distruttivo.",
        ("Local Signer", "casella PEC", "lettore documenti"), "Il server non invia PEC operative; nessuna prova provider è registrata in Fase 1.",
        "Commit precedente e mantenimento dei dati/credenziali locali.", "Golden journey PEC con sandbox o canary non distruttivo.",
        ("tests/test_email_client.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_PENDING,
    ),
    Capability(
        "scadenza", "Scadenza e termini", "Programmazione", "/scadenziario", "/api/v1/ui/scadenziario",
        "web.services.react_scadenziario_bridge", ("lista", "creazione", "calcolo", "promemoria"),
        ("scadenze.leggi", "scadenze.scrivi"), "GestioneScadenziario tenant-aware; SQLite/PostgreSQL", "routes.appV2.scadenziario",
        "da_verificare", "La correzione Fase 0 è provata; il journey P0 completo con ruoli, date e collegamenti resta da eseguire.",
        ("agenda", "fascicoli", "calendario"), "Date e orari visibili devono restare Europe/Rome; nessuna data raw in UI.",
        "Commit applicativo precedente e ricreazione Docker governata.", "Golden journey scadenza, calcolo e collegamento fascicolo.",
        ("tests/test_scadenziario.py", "tests/test_react_scadenziario_additions.py"), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "deposito", "Deposito telematico", "Telematico", "/fascicoli/:id/deposito/prepara", "/api/v1/ui/fascicoli/:id/depositi/*",
        "Bridge fascicoli/deposito + Local Signer", ("classificazione", "indice", "firma", "preparazione busta", "invio locale"),
        ("fascicoli.leggi", "fascicoli.scrivi", "pec.scrivi"), "Fascicolo tenant-aware + repository deposito/audit", "Nessun flag dedicato censito",
        "da_verificare", "Non è dichiarato completo: requisiti ministeriali, firma multipla, ricevute e invio locale richiedono prove reali.",
        ("Local Signer", "PEC locale", "PST/portale", "fascicoli"), "Assenza di requisito ministeriale blocca solo il deposito valido con messaggio esplicito.",
        "Commit precedente; nessun invio server-side e nessuna cancellazione delle prove.", "Prova senza invio, firma multipla reale e canary conforme.",
        ("tests/test_deposito.py", "tests/test_deposito_guidato.py"), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_PENDING,
    ),
    Capability(
        "ricevute", "Ricevute telematiche", "Telematico", "/telematico", "/api/v1/ui/fascicoli/:id/depositi/:depositoId/timeline",
        "Repository deposito e bridge fascicoli", ("importazione", "timeline", "evidence pack", "consultazione"),
        ("fascicoli.leggi", "fascicoli.scrivi"), "Repository deposito/audit tenant-aware", "Nessun flag dedicato censito",
        "da_verificare", "La persistenza e la timeline sono censite; servono fixture e prova reale del ciclo ricevuta.",
        ("deposito", "PEC", "lettore documenti"), "Una ricevuta non può essere registrata come esito reale senza fonte verificabile.",
        "Commit precedente e conservazione delle evidenze del fascicolo.", "Golden journey importazione e lettura ricevuta controllata.",
        ("tests/test_deposito_guidato.py", "tests/test_regia_deposito_receipts.py"), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_PENDING,
    ),
    Capability(
        "fattura", "Fattura", "Economico", "/fatturazione", "/api/v1/ui/fatturazione",
        "web.services.react_fatturazione_bridge", ("creazione", "calcolo backend", "stato", "preparazione XML"),
        ("fatturazione.leggi", "fatturazione.scrivi"), "Repository parcelle tenant-aware; SQLite/PostgreSQL", "routes.appV2.fatturazione",
        "da_verificare", "La superficie React e le API sono censite; emissione, firma e canali esterni attendono prove per ruoli.",
        ("clienti", "pagamenti", "SdI", "PEC locale"), "Importi visibili devono restare in formato euro italiano.",
        "Commit precedente e rollback stato senza eliminare documenti fiscali.", "Golden journey fattura con calcolo, permessi e prova non distruttiva.",
        ("tests/test_fatturazione.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_PENDING,
    ),
    Capability(
        "pagamento", "Pagamento e incasso", "Economico", "/incassi-pagamenti", "/api/v1/ui/incassi-pagamenti",
        "web.services.react_incassi_pagamenti_bridge", ("registrazione incasso", "stato", "collegamento fattura"),
        ("fatturazione.leggi", "fatturazione.scrivi"), "Repository pagamenti tenant-aware; SQLite/PostgreSQL", "routes.appV2.incassiPagamenti",
        "da_verificare", "Il percorso è censito; riconciliazione, permessi e collegamento documento vanno provati con dati sintetici.",
        ("fatturazione", "provider pagamento"), "Nessun esito provider è dichiarato senza prova corrente.",
        "Commit precedente e rollback di stato auditato.", "Golden journey incasso, collegamento e lettura saldo.",
        ("tests/test_portale_economici.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_PENDING,
    ),
    Capability(
        "portale", "Portale cliente", "Portale", "/app/portale-clienti", "/api/v1/ui/client-portal/dashboard",
        "web.services.react_client_portal_bridge", ("dashboard studio", "inviti", "chat", "documenti", "appuntamenti"),
        ("portale_clienti.leggi", "portale_clienti.scrivi"), "Repository portale tenant-aware; SQLite/PostgreSQL", "routes.appV2.clientPortal",
        "da_verificare", "Il contratto React è censito; inviti, token hashati e isolamento richiedono prova end-to-end dedicata.",
        ("identità", "documenti", "fascicoli"), "Token e dati personali non sono esposti dal registro.",
        "Commit precedente; i token non vengono rigenerati dal rollback del registro.", "Golden journey invito, accesso e isolamento tenant.",
        ("tests/test_client_portal_api.py", "tests/test_client_portal_access.py"), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "audit", "Audit", "Sicurezza", "/audit", "/api/v1/ui/audit",
        "web.services.react_audit_bridge", ("lista", "filtro", "dettaglio redatto", "export autorizzato"),
        ("audit.leggi",), "audit_log tenant-aware; SQLite/PostgreSQL", "routes.appV2.audit",
        "da_verificare", "La superficie è censita; occorre acquisire una prova che ogni P0 scriva l'evento atteso senza dati sensibili.",
        ("RBAC", "tutti i flussi P0"), "Il registro non sostituisce gli eventi audit del tenant.",
        "Commit precedente e conservazione immutabile degli eventi audit.", "Matrice audit P0 con verifica redazione e permessi.",
        ("tests/test_audit_routes.py",), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
    Capability(
        "chiusura-fascicolo", "Chiusura fascicolo", "Fascicoli", "/fascicoli/:id", "/api/v1/ui/fascicoli/:id",
        "Bridge fascicoli e repository stato", ("verifica requisiti", "archiviazione", "consultazione storico"),
        ("fascicoli.leggi", "fascicoli.scrivi"), "GestioneFascicoli tenant-aware; filesystem + SQLite/PostgreSQL metadati", "routes.appV2.fascicoli",
        "da_verificare", "Il percorso è registrato, ma requisiti di chiusura, allegati e audit devono essere provati senza perdere dati.",
        ("fascicoli", "documenti", "audit", "fatturazione"), "La chiusura non può mascherare dati, ricevute o obblighi ancora aperti.",
        "Commit precedente e ripristino stato senza rimuovere documenti tenant.", "Golden journey requisiti, chiusura, storico e controllo accessi.",
        ("tests/test_fascicoli.py", "tests/test_fascicoli_pagination.py"), _BROWSER_PENDING, _CI_REFERENCE, _PROVIDER_NA,
    ),
)


def _evidence_payload(evidence: Evidence) -> dict[str, str]:
    return {
        "kind": evidence.kind,
        "status": evidence.status,
        "label": evidence.label,
        "reference": evidence.reference,
        "lastVerified": evidence.last_verified,
        "note": evidence.note,
    }


def _capability_payload(capability: Capability) -> dict[str, Any]:
    status_label, status_tone = _STATUS_LABELS[capability.status]
    evidence = (
        _evidence_payload(capability.ci_evidence),
        _evidence_payload(capability.browser_evidence),
        _evidence_payload(capability.provider_evidence),
    )
    return {
        "id": capability.capability_id,
        "module": capability.module,
        "owner": capability.owner,
        "route": capability.route,
        "api": capability.api,
        "backend": capability.backend,
        "operations": list(capability.operations),
        "permissions": list(capability.permissions),
        "storage": capability.storage,
        "featureFlag": capability.feature_flag,
        "status": capability.status,
        "statusLabel": status_label,
        "statusTone": status_tone,
        "statusNote": capability.status_note,
        "version": REGISTRY_VERSION,
        "tests": list(capability.tests),
        "lastSmoke": {
            "status": "non_eseguito",
            "label": "Non ancora eseguito nella matrice Fase 2",
            "verifiedAt": "",
        },
        "environment": {
            "local": "Non ancora verificato per questa capability",
            "production": "Non ancora verificato per questa capability",
        },
        "evidence": list(evidence),
        "dependencies": list(capability.dependencies),
        "limitations": capability.limitations,
        "rollback": capability.rollback,
        "incidents": {
            "status": "non_integrato",
            "label": "Nessun feed incidenti collegato al registro",
        },
        "nextAction": capability.next_action,
    }


def build_capability_truth_registry(*, application_version: str) -> dict[str, Any]:
    """Restituisce il contratto read-only per UI, documentazione e release matrix."""

    capabilities = [_capability_payload(item) for item in P0_CAPABILITIES]
    statuses = {status: sum(item["status"] == status for item in capabilities) for status in _STATUS_LABELS}
    return {
        "ok": True,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "registryVersion": REGISTRY_VERSION,
        "applicationVersion": str(application_version or "").strip(),
        "scope": "P0 — registro di prontezza; non sostituisce il collaudo operativo",
        "contracts": {
            "writes": "none",
            "sourceOfTruth": "catalogo Python versionato",
            "tenantScope": "nessun dato tenant nel payload",
            "providerCalls": False,
            "runtimeScans": False,
            "secretsExposed": False,
        },
        "summary": {
            "total": len(capabilities),
            "verified": statuses["verificata"],
            "partial": statuses["parziale"],
            "pending": statuses["da_verificare"],
            "blocked": statuses["bloccata"],
        },
        "capabilities": capabilities,
        "navigation": build_product_readiness_navigation(),
        "warnings": [
            {
                "code": "prove-p0-da-acquisire",
                "message": "Il registro censisce le superfici P0 ma non le promuove: le prove CI, browser e provider mancanti restano da verificare.",
            },
            {
                "code": "incidenti-non-integrati",
                "message": "Il feed degli incidenti non è ancora collegato: l'assenza di una riga non equivale all'assenza di incidenti.",
            },
        ],
    }


def build_product_readiness_navigation() -> dict[str, str]:
    """Azione menu generata dalla stessa fonte del catalogo."""

    return {
        "id": "product-readiness",
        "label": "Apri prontezza prodotto",
        "href": "/amministrazione?tab=prontezza-prodotto",
        "tone": "primary",
    }


def registry_catalogue_for_generation() -> dict[str, Any]:
    """Catalogo stabile, senza timestamp runtime, usato dai generatori versionati."""

    payload = build_capability_truth_registry(application_version="catalogo")
    payload.pop("generatedAt", None)
    return payload


__all__ = [
    "P0_CAPABILITIES",
    "P0_CAPABILITY_IDS",
    "REGISTRY_VERSION",
    "build_capability_truth_registry",
    "build_product_readiness_navigation",
    "registry_catalogue_for_generation",
]
