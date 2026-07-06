from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

from pct.formatting import format_date_it, format_euro_it


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = _text(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def _date_iso(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ""


def _date_label(value: Any) -> str:
    parsed = _parse_date(value)
    return format_date_it(parsed) if parsed else ""


def _short(value: Any, limit: int = 220) -> str:
    text = " ".join(_text(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _action(
    *,
    sector: str,
    action_id: str,
    title: str,
    reason: str,
    href: str = "",
    due: Any = "",
    priority: str = "P2",
    tone: str = "warning",
    source: str = "",
    legal_basis: str = "",
    blocking: bool = False,
    evidence: str = "",
) -> dict[str, Any]:
    date_iso = _date_iso(due)
    return {
        "id": f"{sector}-{action_id}",
        "sector": sector,
        "title": _short(title, 140),
        "label": _short(title, 140),
        "reason": _short(reason, 300),
        "href": href,
        "dateIso": date_iso,
        "date": _date_label(due),
        "priority": priority if priority in PRIORITY_RANK else "P2",
        "tone": tone,
        "source": _short(source, 180),
        "legalBasis": _short(legal_basis, 140),
        "blocking": bool(blocking),
        "evidence": _short(evidence or source, 220),
    }


def _sort_actions(actions: Iterable[dict[str, Any]], *, today: date) -> list[dict[str, Any]]:
    sector_rank = {"pec": 0, "doppioni": 1, "documenti": 2, "relata": 3, "economico": 4}

    def key(item: dict[str, Any]) -> tuple[int, int, int, int, str, str]:
        due = _parse_date(item.get("dateIso"))
        overdue_rank = 0 if due and due < today else 1
        danger_rank = 0 if _text(item.get("tone")) == "danger" or bool(item.get("blocking")) else 1
        return (
            PRIORITY_RANK.get(_text(item.get("priority")), 9),
            danger_rank,
            sector_rank.get(_text(item.get("sector")), 9),
            overdue_rank,
            due.isoformat() if due else "9999-12-31",
            _text(item.get("title")).casefold(),
        )

    return sorted(actions, key=key)


def _sector(
    *,
    sector_id: str,
    label: str,
    status: str,
    status_label: str,
    summary: str,
    actions: list[dict[str, Any]] | None = None,
    tone: str = "neutral",
    href: str = "",
    evidence: list[str] | None = None,
    questions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": sector_id,
        "label": label,
        "status": status,
        "statusLabel": status_label,
        "tone": tone,
        "summary": _short(summary, 260),
        "href": href,
        "actions": actions or [],
        "evidence": [_short(item, 160) for item in (evidence or []) if _text(item)][:6],
        "questions": [_short(item, 180) for item in (questions or []) if _text(item)][:8],
    }


def _document_sector(document_presidio: dict[str, Any], *, fid: str, today: date) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for index, item in enumerate(list(document_presidio.get("actions") or [])[:8]):
        priority = "P1"
        due = _parse_date(item.get("dateIso"))
        if bool(item.get("peremptory")) or _text(item.get("priority")) == "urgent":
            priority = "P0"
        elif bool(item.get("requiresCommunicationDate")):
            priority = "P1"
        tone = "danger" if priority == "P0" or (due and due < today) else _text(item.get("tone"), "warning")
        actions.append(
            _action(
                sector="documenti",
                action_id=f"{_text(item.get('type'), 'azione')}-{index}",
                title=_text(item.get("title") or item.get("label"), "Adempimento letto dai documenti"),
                reason=_text(item.get("description"), "Controllo derivato dai documenti indicizzati del fascicolo."),
                due=item.get("dateIso"),
                priority=priority,
                tone=tone,
                href=f"/fascicoli/{fid}#udienze" if fid else "#udienze",
                source=_text(item.get("source"), "Documento fascicolo"),
                legal_basis="127-bis / 127-ter c.p.c." if "127" in _text(item.get("type")) else "Documento del fascicolo",
                blocking=priority == "P0",
                evidence=_text(item.get("source"), "Documento fascicolo"),
            )
        )
        if bool(item.get("requiresCommunicationDate")):
            actions[-1]["blocking"] = True
    if actions:
        status = "presidiato"
        tone = "danger" if any(action["priority"] == "P0" for action in actions) else "warning"
        label = f"{len(actions)} azioni da presidiare"
    else:
        status = _text(document_presidio.get("status"), "non_disponibile")
        tone = _text(document_presidio.get("tone"), "neutral")
        label = "Da leggere" if status in {"lazy_non_caricato", "non_disponibile"} else "Presidio attivo"
    evidence = [_text(item.get("name")) for item in (document_presidio.get("sources") or []) if isinstance(item, dict)]
    evidence.extend(_text(item) for item in (document_presidio.get("warnings") or []))
    return _sector(
        sector_id="documenti",
        label="Presidio documenti",
        status=status,
        status_label=label,
        tone=tone,
        summary=_text(document_presidio.get("summary"), "Documenti da leggere per udienze, decreti e termini."),
        href=f"/fascicoli/{fid}#documenti" if fid else "#documenti",
        actions=actions,
        evidence=evidence,
        questions=[
            "Il decreto sostituisce l'udienza con note scritte o fissa una trattazione audiovisiva?",
            "La data letta è un termine perentorio, una udienza o una semplice data di deposito?",
            "La parte onerata è lo studio, la controparte o entrambe?",
            "La data di udienza/scadenza è già presente in Agenda e Scadenziario con la stessa fonte?",
            "Il documento è quello corretto del fascicolo o una copia/importazione duplicata?",
        ],
    )


def _pec_sector(
    document_presidio: dict[str, Any],
    deposits: list[dict[str, Any]],
    injected_actions: list[dict[str, Any]],
    *,
    fid: str,
) -> dict[str, Any]:
    actions = [item for item in injected_actions if item.get("sector") == "pec"]
    for index, dep in enumerate(deposits[:12]):
        status = _text(dep.get("status")).casefold()
        tone = _text(dep.get("tone"), "neutral")
        if tone in {"danger", "warning"} or any(token in status for token in ("errore", "rifiut", "mancata", "warn")):
            actions.append(
                _action(
                    sector="pec",
                    action_id=f"deposito-{index}",
                    title="Controllare esito PEC o PCT collegato",
                    reason=_text(dep.get("message"), "La comunicazione collegata richiede verifica prima di considerare chiuso il passaggio."),
                    due=dep.get("sentAt") or dep.get("timestamp"),
                    priority="P0" if "rifiut" in status or "errore" in status else "P1",
                    tone="danger" if "rifiut" in status or "errore" in status else "warning",
                    href=f"/fascicoli/{fid}#cancelleria" if fid else "#cancelleria",
                    source=_text(dep.get("source") or dep.get("pec"), "PEC fascicolo"),
                    legal_basis="Presidio PEC / ricevute PCT",
                    blocking=True,
                )
            )
    doc_actions = document_presidio.get("actions") or []
    for index, item in enumerate(doc_actions[:8]):
        if not bool(item.get("requiresCommunicationDate")):
            continue
        actions.append(
            _action(
                sector="pec",
                action_id=f"comunicazione-{index}",
                title="Confermare la data di comunicazione PEC",
                reason="Il termine decorre dalla comunicazione: senza la PEC o il relativo evento non va calcolato come definitivo.",
                priority="P1",
                tone="warning",
                href=f"/email/?fascicolo={fid}" if fid else "/email/",
                source=_text(item.get("source"), "Documento fascicolo"),
                legal_basis="Art. 127-bis / 127-ter c.p.c.",
                blocking=True,
            )
        )
    if any(_text(item.get("type")) == "udienza_127_bis" for item in doc_actions):
        actions.append(
            _action(
                sector="pec",
                action_id="link-udienza-127-bis",
                title="Verificare link audiovisivo e comunicazione dell'udienza",
                reason="L'udienza da remoto richiede collegamento e istruzioni operative: se il link non è nel fascicolo va recuperato dalla PEC o dal portale.",
                priority="P1",
                tone="warning",
                href=f"/fascicoli/{fid}#cancelleria" if fid else "#cancelleria",
                source="Decreto udienza / PEC cancelleria",
                legal_basis="Art. 127-bis c.p.c. e regole DGSIA udienze da remoto",
                blocking=False,
            )
        )
    if actions:
        return _sector(
            sector_id="pec",
            label="Presidio PEC",
            status="da_presidiare",
            status_label=f"{len(actions)} controlli PEC",
            tone="warning" if not any(item["tone"] == "danger" for item in actions) else "danger",
            summary="Controlla comunicazioni, decorrenze e ricevute prima di consolidare termini o depositi.",
            href=f"/fascicoli/{fid}#cancelleria" if fid else "#cancelleria",
            actions=actions,
            evidence=[_text(dep.get("message") or dep.get("pec")) for dep in deposits[:4]],
            questions=[
                "Quale comunicazione PEC fa decorrere il termine e in quale data è arrivata?",
                "L'evento PEC è collegato al fascicolo corretto e non a una pratica duplicata?",
                "Per udienza da remoto sono presenti link, piattaforma, stanza e istruzioni?",
                "Le ricevute PEC/PCT sono complete o esistono esiti di errore, rifiuto o mancata consegna?",
                "L'invio operativo resta dal PC locale dello studio, senza SMTP server-side?",
            ],
        )
    return _sector(
        sector_id="pec",
        label="Presidio PEC",
        status="monitoraggio",
        status_label="Monitoraggio attivo",
        tone="neutral",
        summary="Nessuna anomalia PEC caricata nel fascicolo; le decorrenze restano collegate alle comunicazioni acquisite.",
        href=f"/fascicoli/{fid}#cancelleria" if fid else "#cancelleria",
        questions=[
            "Esiste una PEC di cancelleria non ancora associata a questo fascicolo?",
            "La prossima scadenza deriva da PEC, da documento o da inserimento manuale?",
            "Ci sono ricevute o esiti PCT da acquisire prima di chiudere il controllo?",
        ],
    )


def _relata_sector(notification_relata: dict[str, Any], *, fid: str) -> dict[str, Any]:
    status = _text(notification_relata.get("status"), "monitoraggio")
    tone = _text(notification_relata.get("tone"), "neutral")
    status_label = _text(notification_relata.get("statusLabel"), "Monitoraggio attivo")
    primary_href = _text(notification_relata.get("primaryHref") or notification_relata.get("prepareHref"))
    actions: list[dict[str, Any]] = []
    if status != "monitoraggio":
        priority = "P1" if status in {"da_acquisire", "ricevute_da_completare"} else "P2"
        actions.append(
            _action(
                sector="relata",
                action_id=status,
                title=status_label,
                reason=_text(notification_relata.get("systemNotification"), "Completa il presidio relata e prova notifica."),
                priority=priority,
                tone=tone if tone != "neutral" else "warning",
                href=primary_href or (f"/fascicoli/{fid}#relata-notifica" if fid else "#relata-notifica"),
                source="Presidio relata notifica",
                legal_basis="Notifica PEC / L. 53/1994",
                blocking=status in {"da_acquisire", "ricevute_da_completare"},
            )
        )
    evidence = []
    for key, label in (
        ("pendingPortalDocuments", "documenti portale da scaricare"),
        ("relataDocuments", "relate"),
        ("signedRelataDocuments", "relate firmate"),
        ("proofDocuments", "prove notifica"),
    ):
        count = int(notification_relata.get(key) or 0)
        if count:
            evidence.append(f"{count} {label}")
    return _sector(
        sector_id="relata",
        label="Presidio relata",
        status=status,
        status_label=status_label,
        tone=tone,
        summary=_text(notification_relata.get("systemNotification"), "Relata e prova notifica in monitoraggio."),
        href=primary_href or (f"/fascicoli/{fid}#relata-notifica" if fid else "#relata-notifica"),
        actions=actions,
        evidence=evidence,
        questions=[
            "Il provvedimento da notificare è stato scaricato dal portale e collegato ai documenti?",
            "La relata contiene destinatari, domicilio digitale, atto notificato e attestazioni necessarie?",
            "La relata è firmata digitalmente quando richiesto?",
            "Dopo l'invio sono presenti RAC e RdAC originali e la prova è pronta per il deposito?",
            "Il software sta completando una notifica esistente o rischia di prepararne una doppia?",
        ],
    )


def _economico_sector(
    payment_summary: dict[str, Any],
    sentenze_economiche: dict[str, Any] | None,
    *,
    fid: str,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    items = payment_summary.get("items") if isinstance(payment_summary.get("items"), dict) else {}
    analysis = payment_summary.get("analysis") if isinstance(payment_summary.get("analysis"), dict) else {}
    analysis_status = _text(analysis.get("status"))
    if analysis_status in {"da_rianalizzare", "da_analizzare"}:
        actions.append(
            _action(
                sector="economico",
                action_id="analisi-documentale",
                title=_text(analysis.get("statusLabel"), "Rieseguire analisi documentale del fascicolo"),
                reason=_text(
                    analysis.get("reason"),
                    "Il controllo economico deve essere riallineato ai documenti presenti prima di considerare definitivi importi e scadenze.",
                ),
                priority="P1",
                tone="warning",
                href=f"/fascicoli/{fid}#documenti" if fid else "#documenti",
                source="Impronta documentale fascicolo",
                legal_basis="Presidio documenti/economia fascicolo",
                blocking=False,
            )
        )
    labels = {
        "contributo_unificato": "Registrare contributo unificato",
        "spese_esborsi": "Registrare spese ed esborsi",
        "fondo_spese": "Verificare fondo spese",
        "liquidazione_giudice": "Registrare liquidazione del giudice",
        "parcella": "Emettere o aggiornare parcella",
    }
    for kind, raw in items.items():
        if not isinstance(raw, dict):
            continue
        status = _text(raw.get("status"))
        if status not in {"da_registrare", "da_emettere", "parziale"}:
            continue
        amount_label = _text(raw.get("importoLabel"))
        title = labels.get(kind, _text(raw.get("label"), "Voce economica da completare"))
        if amount_label:
            title = f"{title} ({amount_label})"
        priority = "P1" if kind in {"contributo_unificato", "liquidazione_giudice"} else "P2"
        actions.append(
            _action(
                sector="economico",
                action_id=kind,
                title=title,
                reason=_text(raw.get("note"), "Voce economica prevista ma non ancora consolidata nella sezione economica."),
                due=raw.get("dataPagamentoIso") or raw.get("updatedAt"),
                priority=priority,
                tone=_text(raw.get("tone"), "warning"),
                href=f"/fascicoli/{fid}#economia" if fid else "#economia",
                source=_text(raw.get("documentoFonte") or raw.get("origine"), "Controllo economico"),
                legal_basis="DPR 115/2002 / controllo economico fascicolo" if kind == "contributo_unificato" else "Controllo economico fascicolo",
                blocking=False,
                evidence=_text(raw.get("documentoFonte") or raw.get("origine")),
            )
        )
    if sentenze_economiche:
        totals = sentenze_economiche.get("totals") or {}
        if int(totals.get("da_verificare") or 0):
            actions.append(
                _action(
                    sector="economico",
                    action_id="sentenze-da-verificare",
                    title="Verificare importi liquidati in sentenza",
                    reason="Sono presenti sentenze o provvedimenti con importi economici da confermare prima di attribuire credito o parcella.",
                    priority="P1",
                    tone="warning",
                    href=f"/fascicoli/{fid}#sentenze-economiche" if fid else "#sentenze-economiche",
                    source="Controllo economico sentenze",
                    legal_basis="Artt. 91 e 93 c.p.c.",
                )
            )
    stato = _text(payment_summary.get("stato"), "non_previsto")
    tone = _text(payment_summary.get("tone"), "neutral")
    return _sector(
        sector_id="economico",
        label="Presidio economico",
        status=stato,
        status_label=_text(payment_summary.get("statoLabel"), "Non previsto"),
        tone=tone,
        summary=(
            f"Registrato {payment_summary.get('totaleRegistratoLabel') or format_euro_it(0)}; "
            f"anticipazioni da recuperare {payment_summary.get('anticipazioniDaRecuperareLabel') or format_euro_it(0)}."
        ),
        href=f"/fascicoli/{fid}#economia" if fid else "#economia",
        actions=actions,
        evidence=[_text(item.get("documentoFonte") or item.get("origine")) for item in items.values() if isinstance(item, dict)],
        questions=[
            "Il controllo è aggiornato ai documenti caricati più di recente?",
            "Il contributo unificato è dovuto, esente, pagato o solo da registrare?",
            "Spese ed esborsi sono distinti dal contributo unificato?",
            "La sentenza liquida spese a favore della parte o distrae in favore dell'avvocato antistatario?",
            "La parcella è da emettere, collegata al mandato e coerente con liquidazione/compenso pattuito?",
            "Ci sono anticipazioni da recuperare dal cliente o importi da non attribuire automaticamente allo studio?",
        ],
    )


def _duplicates_sector(duplicate_group: dict[str, Any] | None, *, fid: str) -> dict[str, Any]:
    if not duplicate_group:
        return _sector(
            sector_id="doppioni",
            label="Controllo doppioni",
            status="ok",
            status_label="Nessun doppione rilevato",
            tone="success",
            summary="Cliente e numero di ruolo non risultano duplicati nel perimetro fascicoli caricato.",
            href=f"/fascicoli/{fid}" if fid else "/fascicoli",
            questions=[
                "Cliente e RG identificano una sola pratica operativa?",
                "Le scadenze e gli importi sono registrati sul fascicolo corretto?",
            ],
        )
    count = int(duplicate_group.get("count") or 0)
    label = _text(duplicate_group.get("label"), "Pratica duplicata")
    action = _action(
        sector="doppioni",
        action_id="riconcilia",
        title="Riconciliare pratiche doppie per cliente e RG",
        reason=f"{label}: {count} righe condividono cliente e numero di ruolo. Unire o archiviare la copia non corretta prima di aggiornare scadenze ed economia.",
        priority="P1",
        tone="warning",
        href=_text(duplicate_group.get("href")) or "/fascicoli",
        source="Elenco fascicoli",
        legal_basis="Controllo qualità dati pratica",
        blocking=True,
    )
    return _sector(
        sector_id="doppioni",
        label="Controllo doppioni",
        status="da_riconciliare",
        status_label=f"{count} pratiche uguali",
        tone="warning",
        summary=f"{label}: serve riconciliazione prima di considerare definitiva la lettura del fascicolo.",
        href=action["href"],
        actions=[action],
        evidence=[_text(ref) for ref in (duplicate_group.get("refs") or [])],
        questions=[
            "Quale riga è il fascicolo principale da mantenere?",
            "Documenti, PEC, scadenze ed economia sono distribuiti tra copie da riconciliare?",
            "Prima di inviare, notificare o fatturare, il fascicolo duplicato è stato unito o archiviato?",
        ],
    )


def build_fascicolo_operational_presidio(
    *,
    fascicolo: Any,
    document_presidio: dict[str, Any],
    notification_relata: dict[str, Any],
    payment_summary: dict[str, Any],
    deposits: list[dict[str, Any]] | None = None,
    duplicate_group: dict[str, Any] | None = None,
    sentenze_economiche: dict[str, Any] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    fid = _text(getattr(fascicolo, "id", ""))
    document_sector = _document_sector(document_presidio or {}, fid=fid, today=today)
    pec_sector = _pec_sector(document_presidio or {}, deposits or [], document_sector["actions"], fid=fid)
    sectors = [
        pec_sector,
        document_sector,
        _relata_sector(notification_relata or {}, fid=fid),
        _economico_sector(payment_summary or {}, sentenze_economiche, fid=fid),
        _duplicates_sector(duplicate_group, fid=fid),
    ]
    actions = _sort_actions(
        (action for sector in sectors for action in sector.get("actions", [])),
        today=today,
    )
    if any(action["tone"] == "danger" or action["priority"] == "P0" for action in actions):
        status = "critico"
        tone = "danger"
    elif actions:
        status = "da_presidiare"
        tone = "warning"
    else:
        status = "presidiato"
        tone = "success"
    next_action = actions[0] if actions else None
    active_sectors = sum(1 for sector in sectors if sector.get("actions"))
    if next_action:
        summary = f"{active_sectors} settori richiedono presidio; prossima azione: {next_action['title']}."
    else:
        summary = "Nessuna azione critica rilevata nei settori PEC, documenti, relata, economico e doppioni."
    questions = [
        "Qual è la prossima attività che lo studio deve fare oggi e quale fonte la prova?",
        "Esiste un termine perentorio o una decorrenza da PEC non ancora consolidata?",
        "Udienza, link remoto, note scritte e richiesta di presenza sono completi?",
        "La notifica/relata è pronta, firmata e con prova RAC/RdAC quando serve?",
        "Contributo, esborsi, liquidazione e parcella sono coerenti con documenti e sentenze?",
        "La pratica è unica per cliente e RG o ci sono doppioni da riconciliare prima di agire?",
    ]
    return {
        "schemaVersion": 1,
        "status": status,
        "statusLabel": "Critico" if status == "critico" else "Da presidiare" if status == "da_presidiare" else "Presidiato",
        "tone": tone,
        "summary": summary,
        "nextAction": next_action,
        "actions": actions[:14],
        "sectors": sectors,
        "questions": questions,
        "generatedAt": datetime.now().replace(microsecond=0).isoformat(),
    }


__all__ = ["build_fascicolo_operational_presidio"]
