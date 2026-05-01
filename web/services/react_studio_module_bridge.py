"""Payload React per le superfici Studio e Amministrazione.

Il bridge riusa repository e route operative esistenti: la pagina React mostra
dati reali e invia le scritture ai POST già auditati dal backend storico.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable


def _safe(label: str, loader: Callable[[], Any], fallback: Any) -> Any:
    try:
        return loader()
    except Exception:
        return fallback


def _text(value: Any, fallback: str = "") -> str:
    raw = str(value if value is not None else fallback).strip()
    return raw or fallback


def _enum(value: Any) -> str:
    return _text(getattr(value, "value", value))


def _date_it(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    for sample in (raw[:19], raw[:10]):
        try:
            parsed = datetime.fromisoformat(sample)
            return parsed.strftime("%d/%m/%Y %H:%M") if "T" in sample else parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return raw


def _euro(value: Any) -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {text}"


def _record(
    record_id: Any,
    title: Any,
    subtitle: Any = "",
    *,
    badge: Any = "",
    href: str = "",
    meta: Any = "",
) -> dict[str, str]:
    return {
        "id": _text(record_id, "record"),
        "title": _text(title, "Elemento"),
        "subtitle": _text(subtitle),
        "badge": _text(badge),
        "href": href,
        "meta": _text(meta),
    }


def _metric(label: str, value: Any, note: str = "") -> dict[str, str]:
    return {"label": label, "value": _text(value), "note": _text(note)}


def _action(label: str, href: str, *, method: str = "GET", tone: str = "primary") -> dict[str, str]:
    return {"label": label, "href": href, "method": method, "tone": tone}


def _field(
    name: str,
    label: str,
    field_type: str = "text",
    *,
    required: bool = False,
    options: list[dict[str, str]] | None = None,
    value: str = "",
) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "type": field_type,
        "required": required,
        "options": options or [],
        "value": value,
    }


def _operation(
    operation_id: str,
    title: str,
    body: str,
    *,
    metrics: list[dict[str, str]] | None = None,
    records: list[dict[str, str]] | None = None,
    actions: list[dict[str, str]] | None = None,
    form: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": operation_id,
        "title": title,
        "body": body,
        "metrics": metrics or [],
        "records": records or [],
        "actions": actions or [],
        "form": form,
        "warnings": warnings or [],
    }


def _roles_options() -> list[dict[str, str]]:
    return [
        {"value": "AMMINISTRATORE", "label": "Amministratore"},
        {"value": "AVVOCATO", "label": "Avvocato"},
        {"value": "COLLABORATORE", "label": "Collaboratore"},
        {"value": "PRATICANTE", "label": "Praticante"},
        {"value": "SEGRETERIA", "label": "Segreteria"},
        {"value": "CONTABILE", "label": "Contabile"},
    ]


def _file_metric(path: Any) -> str:
    raw = _text(path)
    if not raw:
        return "non configurato"
    candidate = Path(raw)
    try:
        if not candidate.exists():
            return "non trovato"
        size = candidate.stat().st_size
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"
    except OSError:
        return "non leggibile"


def _build_utenti(get_utenti: Callable[[], Any]) -> dict[str, Any]:
    manager = get_utenti()
    utenti = _safe("utenti", lambda: manager.tutti(), [])
    stats = _safe("statistiche utenti", lambda: manager.statistiche(), {})
    records = [
        _record(
            getattr(user, "id", ""),
            getattr(user, "username", ""),
            getattr(user, "nome_completo", "") or getattr(user, "email", ""),
            badge=_enum(getattr(user, "ruolo", "")),
            href=f"/utenti/{getattr(user, 'id', '')}/modifica",
            meta="Attivo" if getattr(user, "attivo", False) else "Disabilitato",
        )
        for user in utenti[:25]
    ]
    role_counts = stats.get("per_ruolo", {}) if isinstance(stats, dict) else {}
    return {
        "metrics": [
            _metric("Utenti", stats.get("totale_utenti", len(utenti)) if isinstance(stats, dict) else len(utenti)),
            _metric("Attivi", stats.get("attivi", 0) if isinstance(stats, dict) else 0),
            _metric("Override", stats.get("con_override", 0) if isinstance(stats, dict) else 0),
        ],
        "operations": [
            _operation(
                "lista-utenti",
                "Lista utenti",
                "Archivio operatori dello studio con ruolo, stato e accesso.",
                records=records,
                metrics=[_metric(role, count) for role, count in sorted(role_counts.items())],
                actions=[_action("Aggiorna lista", "/utenti")],
            ),
            _operation(
                "nuovo-utente",
                "Nuovo utente",
                "Crea un operatore usando la route POST già auditata.",
                form={
                    "action": "/utenti/nuovo",
                    "method": "POST",
                    "submitLabel": "Crea utente",
                    "fields": [
                        _field("username", "Username", required=True),
                        _field("password", "Password temporanea", "password", required=True),
                        _field("nome_completo", "Nome completo"),
                        _field("email", "Email", "email"),
                        _field("ruolo", "Ruolo", "select", required=True, options=_roles_options(), value="SEGRETERIA"),
                    ],
                },
                warnings=["La password temporanea verrà cambiata al primo accesso."],
            ),
            _operation(
                "profili-e-permessi",
                "Profili e permessi",
                "Matrice RBAC e override individuali collegati agli utenti.",
                records=[_record(role, role, f"{count} utenti", badge="Ruolo", href="/profili") for role, count in sorted(role_counts.items())],
                actions=[_action("Apri matrice ruoli", "/profili")],
            ),
        ],
    }


def _build_fatturazione(get_fatturazione: Callable[[], Any], get_clienti: Callable[[], Any]) -> dict[str, Any]:
    manager = get_fatturazione()
    anno = date.today().year
    parcelle = _safe("parcelle", lambda: manager.tutte(), [])
    stats = _safe("statistiche fatturazione", lambda: manager.statistiche(anno), {})
    clienti = {str(getattr(c, "id", "")): c for c in _safe("clienti", lambda: get_clienti().tutti(), [])}
    records = []
    for parcella in parcelle[:25]:
        cliente = clienti.get(str(getattr(parcella, "id_cliente", "")))
        records.append(_record(
            getattr(parcella, "id", ""),
            getattr(parcella, "numero", "Parcella"),
            getattr(cliente, "nome_completo", "") if cliente else "Cliente non collegato",
            badge=_enum(getattr(parcella, "stato", "")),
            href=f"/fatturazione/{getattr(parcella, 'id', '')}",
            meta=_euro(getattr(parcella, "totale", 0)),
        ))
    clienti_options = [
        {"value": str(getattr(cliente, "id", "")), "label": getattr(cliente, "nome_completo", "")}
        for cliente in clienti.values()
        if getattr(cliente, "id", "")
    ][:80]
    return {
        "metrics": [
            _metric("Fatturato anno", _euro(stats.get("totale_emesso", 0) if isinstance(stats, dict) else 0)),
            _metric("Incassato", _euro(stats.get("totale_pagato", 0) if isinstance(stats, dict) else 0)),
            _metric("Scadute", stats.get("scadute", 0) if isinstance(stats, dict) else 0),
        ],
        "operations": [
            _operation("elenco-parcelle", "Elenco parcelle", "Archivio economico con documenti, stati e importi reali.", records=records, actions=[_action("Esporta contabilità", "/export/fatturazione.csv")]),
            _operation(
                "nuova-parcella",
                "Nuova parcella",
                "Crea una parcella dal form React inviando al POST operativo storico.",
                form={
                    "action": "/fatturazione/nuova",
                    "method": "POST",
                    "submitLabel": "Crea parcella",
                    "fields": [
                        _field("id_cliente", "Cliente", "select", required=True, options=clienti_options),
                        _field("voce_descr[]", "Descrizione voce", required=True),
                        _field("voce_qty[]", "Quantità", "number", required=True, value="1"),
                        _field("voce_prezzo[]", "Prezzo unitario", "number", required=True, value="0.00"),
                        _field("data_emissione", "Data emissione", "date", value=date.today().isoformat()),
                        _field("data_scadenza", "Data scadenza", "date"),
                        _field("note", "Note", "textarea"),
                    ],
                },
            ),
            _operation("incassi-e-pagamenti", "Incassi e pagamenti", "Provider, link pagamento e stato incassi collegati alle parcelle.", actions=[_action("Apri pagamenti", "/incassi-pagamenti")]),
            _operation("esporta-contabilita", "Esporta contabilità", "Download CSV per controllo contabile.", actions=[_action("Scarica CSV", "/export/fatturazione.csv")]),
        ],
    }


def _build_audit(get_utenti: Callable[[], Any]) -> dict[str, Any]:
    manager = get_utenti()
    events = _safe("audit", lambda: manager.audit_log(limit=50), [])
    records = [
        _record(
            getattr(event, "id", ""),
            getattr(event, "azione", ""),
            getattr(event, "username", "") or getattr(event, "risorsa_tipo", ""),
            badge=getattr(event, "esito", ""),
            href="/audit",
            meta=_date_it(getattr(event, "timestamp", "")),
        )
        for event in events[:30]
    ]
    return {
        "metrics": [_metric("Eventi", len(events)), _metric("Ultimo controllo", _date_it(getattr(events[0], "timestamp", "")) if events else "nessuno")],
        "operations": [
            _operation("audit-utenti", "Audit utenti", "Registro reale degli eventi applicativi e di sicurezza.", records=records, actions=[_action("Esporta CSV", "/audit/esporta.csv")]),
            _operation("esporta-audit", "Esporta audit", "Scarica il registro audit in formato CSV.", actions=[_action("Scarica CSV", "/audit/esporta.csv")]),
            _operation("osservabilita", "Osservabilità", "Superficie amministrativa per log e stato servizio.", actions=[_action("Apri osservabilità", "/admin/osservabilita")]),
        ],
    }


def _build_database(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "CLIENTI_DB",
        "FASCICOLI_DB",
        "AGENDA_DB",
        "SCADENZIARIO_DB",
        "EMAIL_CASELLA_DB",
        "MESSAGGI_DB",
        "UTENTI_DB",
    ]
    records = [
        _record(key, key, _text(config.get(key, "")), badge=_file_metric(config.get(key, "")), href="/admin/database")
        for key in keys
    ]
    return {
        "metrics": [_metric("Archivi", len(keys)), _metric("Data root", _text(config.get("DATA_ROOT", "")) or _text(config.get("PCT_DATA_ROOT", "")) or "runtime")],
        "operations": [
            _operation("stato-database", "Stato database", "Verifica archivi runtime, dimensioni e percorsi governati.", records=records, actions=[_action("Apri backup", "/backup"), _action("Registro attività", "/registro-attivita")]),
            _operation("backup", "Backup", "Controlla copie e ripristino prima delle operazioni tecniche.", actions=[_action("Apri backup", "/backup")]),
            _operation("registro-attivita", "Registro attività", "Audit tecnico collegato a storage e migrazioni.", actions=[_action("Apri registro", "/registro-attivita")]),
        ],
    }


def _build_gdpr(get_trattamenti: Callable[[], Any]) -> dict[str, Any]:
    trattamenti = _safe("trattamenti", lambda: get_trattamenti().tutti(), [])
    records = [
        _record(getattr(item, "id", ""), getattr(item, "nome", ""), getattr(item, "finalita", ""), badge=getattr(item, "base_giuridica", ""), href="/privacy/registro", meta="Attivo" if getattr(item, "attivo", False) else "Disattivo")
        for item in trattamenti[:30]
    ]
    return {
        "metrics": [_metric("Trattamenti", len(trattamenti)), _metric("Attivi", sum(1 for item in trattamenti if getattr(item, "attivo", False)))],
        "operations": [
            _operation("registro-trattamenti", "Registro trattamenti", "Registro privacy e trattamenti gestiti.", records=records, actions=[_action("Apri registro", "/privacy/registro")]),
            _operation(
                "nuovo-trattamento",
                "Nuovo trattamento",
                "Registra finalità, base giuridica, dati e misure.",
                form={
                    "action": "/privacy/registro/nuovo",
                    "method": "POST",
                    "submitLabel": "Salva trattamento",
                    "fields": [
                        _field("nome", "Nome trattamento", required=True),
                        _field("finalita", "Finalità", "textarea", required=True),
                        _field("categoria_dati", "Categoria dati"),
                        _field("base_giuridica", "Base giuridica"),
                        _field("soggetti_interessati", "Soggetti interessati"),
                        _field("destinatari", "Destinatari"),
                        _field("termine_conservazione", "Termine conservazione"),
                        _field("misure_sicurezza", "Misure sicurezza", "textarea"),
                    ],
                },
            ),
            _operation("audit-privacy", "Audit privacy", "Esporta e verifica attività collegate ai dati personali.", actions=[_action("Esporta audit", "/audit/esporta.csv")]),
        ],
    }


def _build_impostazioni(config: dict[str, Any]) -> dict[str, Any]:
    safe_rows = [
        _record("studio", "Studio", _text(config.get("STUDIO_NOME", "IUSENTRA")), badge="Dati", href="/impostazioni-studio#dati-studio"),
        _record("pec", "PEC", _text(config.get("PEC_HOST", "")) or _text(config.get("IMAP_HOST", "")) or "configurazione locale", badge="Canale", href="/impostazioni-studio#pec-e-smtp"),
        _record("smtp", "SMTP", _text(config.get("SMTP_HOST", "")) or "Local Signer / provider", badge="Invio", href="/impostazioni-studio#pec-e-smtp"),
        _record("signer", "Local Signer", "http://127.0.0.1:27272", badge="Locale", href="/impostazioni-studio#firma-digitale"),
        _record("scheduler", "Scheduler", "backup, calendari e job pianificati", badge="Automazioni", href="/impostazioni-studio#scheduler"),
    ]
    return {
        "metrics": [_metric("Sezioni", 6), _metric("Controllo token", "Locale"), _metric("Password cloud", "No")],
        "operations": [
            _operation("dati-studio", "Dati studio", "Dati anagrafici e fiscali usati nei documenti.", records=safe_rows[:1]),
            _operation("pec-e-smtp", "PEC e SMTP", "Verifica canali senza esporre password nella UI.", records=safe_rows[1:3], actions=[_action("Test PEC/SMTP", "/impostazioni/test/pec-smtp", method="POST")]),
            _operation("firma-digitale", "Firma digitale", "Il token USB si verifica dal browser tramite Local Signer sul PC dell'avvocato.", records=safe_rows[3:4], actions=[_action("Scarica Local Signer Windows", "/polisWeb/local-signer/setup/windows-exe")]),
            _operation("ai-locale", "AI locale", "Runtime AI locale e reindicizzazione documenti.", actions=[_action("Stato AI locale", "/api/local-ai/status")]),
            _operation("whatsapp", "WhatsApp", "Provider, numeri e promemoria cliente.", actions=[_action("Test WhatsApp", "/impostazioni/test/whatsapp", method="POST")]),
            _operation("scheduler", "Scheduler", "Automazioni, backup e sincronizzazione calendario.", records=safe_rows[4:]),
        ],
    }


_GENERIC_OPERATION_CATALOG: dict[str, list[tuple[str, str, str, list[tuple[str, str, str]]]]] = {
    "preventivi": [
        ("archivio-preventivi", "Archivio preventivi", "Apre la lista operativa di preventivi e conferimenti.", [("Apri archivio", "/preventivi", "GET")]),
        ("nuovo-preventivo", "Nuovo preventivo", "Invia al form operativo di creazione preventivo.", [("Crea preventivo", "/preventivi/nuovo", "GET")]),
        ("conferimento-incarico", "Conferimento incarico", "Predispone il conferimento partendo dal flusso Flask auditato.", [("Crea incarico", "/preventivi/conferimento/nuovo", "GET")]),
        ("wizard-compensi", "Wizard compensi", "Apre il calcolo guidato per compensi e preventivo.", [("Apri wizard", "/preventivi/wizard", "GET")]),
    ],
    "compensi-forensi": [
        ("tariffario", "Tariffario", "Apre parametri forensi e calcoli DM 55.", [("Apri tariffario", "/tariffario", "GET")]),
        ("wizard-preventivo", "Wizard preventivo", "Trasforma il calcolo in preventivo operativo.", [("Genera preventivo", "/preventivi/wizard", "GET")]),
        ("strumenti-forensi", "Strumenti Forensi", "Apre la suite di calcolo forense.", [("Apri strumenti", "/strumenti-legali", "GET")]),
    ],
    "redazione-atti": [
        ("catalogo-atti", "Catalogo atti", "Apre catalogo, filtri e modelli dello studio.", [("Apri catalogo", "/template-atti/catalogo", "GET")]),
        ("nuovo-modello", "Nuovo modello", "Apre il form di creazione modello di studio.", [("Nuovo modello", "/template-atti/nuovo", "GET")]),
        ("checklist-deposito", "Checklist deposito", "Apre controlli atti e allegati prima del deposito.", [("Apri checklist", "/deposito/checklist", "GET")]),
        ("fascicoli", "Fascicoli", "Seleziona pratica, parti e documenti per la redazione.", [("Apri fascicoli", "/fascicoli", "GET")]),
    ],
    "pst-acquisizione": [
        ("acquisizione-pst", "Acquisizione PST", "Apre il presidio React per import autorizzato da PST.", [("Apri acquisizione", "/app-v2/polisweb#acquisizione-portale", "GET")]),
        ("checklist-import-pst", "Checklist import PST", "Porta ai prerequisiti operativi del flusso PST.", [("Verifica flusso", "/app-v2/polisweb#checklist-operativa", "GET")]),
        ("fascicoli", "Fascicoli", "Controlla o crea la pratica locale prima dell'import.", [("Apri fascicoli", "/fascicoli", "GET")]),
        ("centro-telematico", "Centro telematico", "Rientra nel quadro unico dei servizi telematici.", [("Apri centro", "/app-v2/telematico", "GET")]),
    ],
    "statistiche": [
        ("dashboard-grafici", "Dashboard grafici", "Apre KPI, grafici e riepiloghi direzionali.", [("Apri dashboard", "/statistiche", "GET")]),
        ("produttivita", "Produttività", "Filtra gli indicatori sul lavoro dello studio.", [("Vedi analisi", "/statistiche/?view=produttivita", "GET")]),
        ("depositi-trend", "Depositi trend", "Mostra andamento dei canali telematici.", [("Trend depositi", "/statistiche/?view=depositi", "GET")]),
    ],
    "ricerca-legale": [
        ("dashboard-ricerca", "Dashboard ricerca", "Apre monitor normativo e Legal Intelligence.", [("Apri ricerca", "/legal-intelligence", "GET")]),
        ("news-legali", "News legali", "Consulta aggiornamenti e filtri per materia.", [("Apri news", "/legal-intelligence/news", "GET")]),
        ("registro-mediazione", "Registro mediazione", "Apre dati e aggiornamenti sulla mediazione.", [("Apri registro", "/legal-intelligence/mediazione", "GET")]),
    ],
    "giurisprudenza": [
        ("ricerca-sentenze", "Ricerca sentenze", "Apre archivio giurisprudenza e filtri.", [("Apri archivio", "/giurisprudenza", "GET")]),
        ("nuova-scheda", "Nuova scheda", "Registra manualmente una pronuncia.", [("Nuova scheda", "/giurisprudenza/nuova", "GET")]),
        ("importa-materiale", "Importa materiale", "Collega materiale e fonti al repository interno.", [("Importa", "/giurisprudenza", "GET")]),
    ],
    "strumenti-forensi": [
        ("suite-strumenti", "Suite strumenti", "Apre la suite degli strumenti forensi.", [("Apri suite", "/strumenti-legali", "GET")]),
        ("onorari-forensi", "Onorari forensi", "Apre il calcolo compensi forensi.", [("Calcola onorari", "/strumenti-legali/?tool=onorari_forensi", "GET")]),
        ("contributo-unificato", "Contributo unificato", "Apre il calcolo del contributo unificato.", [("Calcola CU", "/strumenti-legali/?tool=contributo_unificato", "GET")]),
    ],
    "timesheet": [
        ("cruscotto-tempi", "Cruscotto tempi", "Apre riepilogo e filtri del timesheet.", [("Apri timesheet", "/timesheet", "GET")]),
        ("nuova-attivita", "Nuova attività", "Collega una voce tempo ad agenda, cliente o fascicolo.", [("Aggancia agenda", "/agenda", "GET")]),
        ("genera-parcella", "Genera parcella", "Porta alla creazione parcella dalle voci validate.", [("Crea parcella", "/fatturazione/nuova", "GET")]),
        ("produttivita", "Produttività", "Apre gli indicatori di produttività.", [("Vedi KPI", "/statistiche/?view=produttivita", "GET")]),
    ],
    "cartelle-condivise": [
        ("cartelle-condivise", "Cartelle condivise", "Apre elenco accessi e cartelle cliente.", [("Apri cartelle", "/cartelle-condivise", "GET")]),
        ("clienti", "Clienti", "Seleziona cliente e cartella operativa.", [("Apri clienti", "/clienti", "GET")]),
        ("registro-attivita", "Registro attività", "Apre audit di condivisioni e accessi.", [("Apri audit", "/audit", "GET")]),
    ],
    "strumenti-operativi": [
        ("timesheet", "Timesheet", "Registra attività e valorizza lavoro fatturabile.", [("Apri timesheet", "/timesheet", "GET")]),
        ("export-dati", "Export dati", "Scarica dati economici per controlli.", [("Esporta", "/export/fatturazione.csv", "GET")]),
        ("condivisioni", "Condivisioni", "Gestisce cartelle condivise e accessi documentali.", [("Apri condivisioni", "/cartelle-condivise", "GET")]),
        ("regia-operativa", "Regia operativa", "Rientra nel quadro operativo dello studio.", [("Apri regia", "/workspace-intelligente", "GET")]),
    ],
    "sito-studio": [
        ("dashboard-sito", "Dashboard sito", "Apre controllo contenuti e pubblicazione del sito.", [("Apri dashboard", "/sito-studio", "GET")]),
        ("builder-pro", "Builder Pro", "Apre il builder visuale del sito.", [("Apri builder", "/sito-studio/builder", "GET")]),
        ("richieste-contatto", "Richieste contatto", "Apre lead e messaggi arrivati dal sito.", [("Apri contatti", "/sito-studio/contatti", "GET")]),
    ],
    "notifiche-whatsapp": [
        ("centro-notifiche", "Centro notifiche", "Apre notifiche e promemoria cliente.", [("Apri notifiche", "/notifiche", "GET")]),
        ("configura-whatsapp", "Configura WhatsApp", "Apre le impostazioni del provider.", [("Apri configurazione", "/impostazioni-studio#whatsapp", "GET")]),
        ("messaggi-clienti", "Messaggi clienti", "Apre conversazioni e nuovo invio.", [("Apri messaggi", "/messaggi", "GET")]),
    ],
    "incassi-pagamenti": [
        ("impostazioni-pagamenti", "Impostazioni pagamenti", "Apre configurazione provider e preferenze.", [("Apri impostazioni", "/impostazioni/pagamenti", "GET")]),
        ("parcelle-aperte", "Parcelle aperte", "Apre le parcelle da incassare.", [("Apri parcelle", "/fatturazione", "GET")]),
        ("statistiche-economiche", "Statistiche economiche", "Apre trend economici e incassi.", [("Apri statistiche", "/statistiche", "GET")]),
    ],
    "backup": [
        ("archivio-backup", "Archivio backup", "Apre lista backup, verifica e download.", [("Apri archivio", "/backup", "GET")]),
        ("scheduler-backup", "Scheduler backup", "Apre configurazione delle automazioni.", [("Apri scheduler", "/impostazioni-studio#scheduler", "GET")]),
        ("database", "Database", "Apre storage e snapshot tecnici.", [("Apri database", "/admin/database", "GET")]),
    ],
    "sincronizzazione-calendari": [
        ("pannello-calendario", "Pannello calendario", "Apre token, feed e profili di sync.", [("Apri pannello", "/impostazioni/calendario", "GET")]),
        ("export-agenda", "Export agenda", "Scarica gli appuntamenti in formato ICS.", [("Scarica agenda", "/agenda/export.ics", "GET")]),
        ("export-scadenze", "Export scadenze", "Scarica le scadenze in formato ICS.", [("Scarica scadenze", "/scadenziario/export.ics", "GET")]),
    ],
    "amministrazione": [
        ("utenti", "Utenti", "Apre gestione operatori e accessi.", [("Apri utenti", "/utenti", "GET")]),
        ("profili-e-permessi", "Profili e permessi", "Apre matrice ruoli e policy.", [("Apri permessi", "/profili", "GET")]),
        ("registro-attivita", "Registro attività", "Apre audit e osservabilità.", [("Apri registro", "/registro-attivita", "GET")]),
        ("database-e-gdpr", "Database e GDPR", "Apre storage e registro trattamenti.", [("Apri database", "/admin/database", "GET")]),
    ],
    "profili": [
        ("matrice-ruoli", "Matrice ruoli", "Apre tabella profili e permessi.", [("Apri matrice", "/profili", "GET")]),
        ("utenti", "Utenti", "Apre operatori e override autorizzativi.", [("Apri utenti", "/utenti", "GET")]),
        ("audit-permessi", "Audit permessi", "Apre audit dei cambi ruolo.", [("Apri audit", "/registro-attivita", "GET")]),
    ],
}


def _catalog_operations(module_id: str, records: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = _GENERIC_OPERATION_CATALOG.get(module_id, [])
    return [
        _operation(
            operation_id,
            title,
            body,
            records=records if index == 0 else [],
            actions=[_action(label, href, method=method) for label, href, method in actions],
        )
        for index, (operation_id, title, body, actions) in enumerate(rows)
    ]


def _build_generic(module_id: str, get_clienti: Callable[[], Any], get_fascicoli: Callable[[], Any]) -> dict[str, Any]:
    clienti = _safe("clienti", lambda: get_clienti().tutti(), [])
    fascicoli = _safe("fascicoli", lambda: get_fascicoli().tutti(), [])
    records = [
        _record(
            getattr(item, "id", ""),
            getattr(item, "titolo", "") or getattr(item, "nome_completo", ""),
            getattr(item, "numero_rg", ""),
            href=f"/fascicoli/{getattr(item, 'id', '')}",
        )
        for item in fascicoli[:12]
    ]
    operations = _catalog_operations(module_id, records)
    if operations:
        return {
            "metrics": [_metric("Clienti", len(clienti)), _metric("Fascicoli", len(fascicoli))],
            "operations": operations,
        }
    return {
        "metrics": [_metric("Clienti", len(clienti)), _metric("Fascicoli", len(fascicoli))],
        "operations": [
            _operation(
                module_id,
                "Funzione operativa",
                "Questa superficie React usa dati reali e route operative già collegate.",
                actions=[_action("Apri modulo", f"/{module_id}")],
                records=[
                    _record(getattr(item, "id", ""), getattr(item, "titolo", "") or getattr(item, "nome_completo", ""), getattr(item, "numero_rg", ""), href=f"/fascicoli/{getattr(item, 'id', '')}")
                    for item in fascicoli[:12]
                ],
            )
        ],
    }


def build_react_studio_module_payload(
    *,
    module_id: str,
    config: dict[str, Any],
    get_utenti: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_trattamenti: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    normalized = _text(module_id).lower()
    if normalized == "utenti":
        data = _build_utenti(get_utenti)
    elif normalized == "fatturazione":
        data = _build_fatturazione(get_fatturazione, get_clienti)
    elif normalized in {"registro-attivita", "audit"}:
        data = _build_audit(get_utenti)
    elif normalized == "database":
        data = _build_database(config)
    elif normalized in {"gdpr", "registro-gdpr"} and get_trattamenti:
        data = _build_gdpr(get_trattamenti)
    elif normalized == "impostazioni-studio":
        data = _build_impostazioni(config)
    else:
        data = _build_generic(normalized, get_clienti, get_fascicoli)
    data.setdefault("metrics", [])
    data.setdefault("operations", [])
    return {
        "source": "repository_reali",
        "moduleId": normalized,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "contracts": {
            "mock_fallback": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        **data,
    }
