"""Italian response composer for deterministic operational answers."""

from __future__ import annotations

import re
from typing import Any

from .models import OperationalAnswer, OperationalRoute, OperationalSourceReference, OperationalToolResult
from .serializers import clean_spaces


class OperationalResponseComposer:
    def compose(
        self,
        *,
        question: str,
        route: OperationalRoute,
        results: list[OperationalToolResult],
        blocked_reason: str = "",
    ) -> OperationalAnswer:
        sources = _unique_sources([source for result in results for source in result.sources])
        objects = _unique_objects([obj for result in results for obj in result.objects])
        gaps = _user_facing_gaps(_unique_strings([gap for result in results for gap in result.coverage_gaps]))
        warnings = _unique_strings([warning for result in results for warning in result.warnings])
        permissions = _unique_strings(
            [
                source.permission_applied
                for source in sources
                if clean_spaces(source.permission_applied)
            ]
        )

        if route.blocks_legal_action:
            answer = (
                "Non posso eseguire direttamente questa azione. Posso aiutarti a preparare un riepilogo, "
                "una checklist o una bozza da far validare all'avvocato, ma invii, depositi, firme, pagamenti "
                "e cancellazioni restano azioni operative soggette a conferma umana."
            )
            return OperationalAnswer(
                handled=True,
                answer=answer,
                route=route,
                confidence=0.9,
                coverage_gaps=["Richiesta dispositiva bloccata dalla policy Lex."],
                warnings=["Revisione dell'avvocato richiesta per azioni dispositive o ad alto rischio."],
                next_actions=["Riformula la richiesta come consultazione o preparazione di bozza."],
                permissions_applied=permissions,
                blocked_reason=blocked_reason or "legal_action_blocked",
                metadata={"operational_layer": True},
            )

        ok_results = [result for result in results if result.ok]
        if not ok_results:
            if route.intent in {"deadlines_overview", "agenda_overview"} and results:
                answer_lines = self._calendar_lines(route, results, gaps)
                return OperationalAnswer(
                    handled=True,
                    answer="\n".join(line for line in answer_lines if clean_spaces(line)),
                    route=route,
                    sources=sources,
                    objects=objects,
                    confidence=0.55,
                    coverage_gaps=gaps,
                    warnings=warnings,
                    next_actions=["Verifica se l'udienza e' registrata in agenda o importata dal fascicolo telematico."],
                    permissions_applied=permissions,
                    blocked_reason=blocked_reason,
                    metadata={"operational_layer": True, "empty_authorized_lookup": True},
                )
            return OperationalAnswer(
                handled=True,
                answer="Non ho trovato dati reali sufficienti nelle sorgenti operative autorizzate per rispondere.",
                route=route,
                confidence=0.25,
                coverage_gaps=gaps or ["Nessuna sorgente operativa ha restituito dati consultabili."],
                warnings=warnings,
                next_actions=["Indica un identificativo, un cliente, un fascicolo o un periodo piu' preciso."],
                permissions_applied=permissions,
                blocked_reason=blocked_reason,
                metadata={"operational_layer": True},
            )

        answer_lines = self._answer_lines(route, ok_results, gaps, question=question)
        confidence = self._confidence(ok_results, gaps)
        next_actions = self._next_actions(route, gaps)
        return OperationalAnswer(
            handled=True,
            answer="\n".join(line for line in answer_lines if clean_spaces(line)),
            route=route,
            sources=sources,
            objects=objects,
            confidence=confidence,
            coverage_gaps=gaps,
            warnings=warnings,
            next_actions=next_actions,
            permissions_applied=permissions,
            fallback_triggered=False,
            metadata={
                "operational_layer": True,
                "question": clean_spaces(question),
                "result_count": sum(len(list(result.data or [])) if isinstance(result.data, list) else int(bool(result.data)) for result in ok_results),
            },
        )

    def _answer_lines(
        self,
        route: OperationalRoute,
        results: list[OperationalToolResult],
        gaps: list[str],
        *,
        question: str = "",
    ) -> list[str]:
        if route.intent in {"client_situation", "client_fascicoli", "client_economic_summary"}:
            return self._client_lines(route, results, gaps)
        if route.intent == "soggetti_lookup":
            return self._soggetti_lines(results, gaps)
        if route.intent in {"fascicolo_summary", "documenti_fascicolo"}:
            return self._fascicolo_lines(route, results, gaps)
        if route.intent in {"deadlines_overview", "agenda_overview"}:
            return self._calendar_lines(route, results, gaps)
        if route.intent in {"preventivo_summary", "conferimento_summary", "billing_summary", "tariffario_lookup", "unbilled_activity"}:
            return self._economic_lines(route, results, gaps)
        if route.intent in {"legal_update_overview", "official_sources_lookup"}:
            return self._legal_sources_lines(results, gaps, question=question)
        if route.intent == "communications_lookup":
            return self._communications_lines(results, gaps)
        if route.intent == "sources_overview":
            return self._sources_overview(results, gaps)
        if route.intent == "template_lookup":
            return self._template_editor_lines(results, gaps)
        return self._generic_lines(results, gaps)

    def _client_lines(self, route: OperationalRoute, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        clienti = _data_for(results, "clienti")
        lines: list[str] = []
        if len(clienti) > 1:
            names = ", ".join(_label(row) for row in clienti[:5])
            return [
                "Ho trovato piu' clienti compatibili.",
                f"Risultati: {names}.",
                "Restringi con codice fiscale, email, fascicolo o identificativo cliente.",
            ]
        if clienti:
            cliente = clienti[0]
            lines.append(f"Scheda cliente: {_label(cliente)}.")
            lines.extend(_cliente_identity_lines(cliente))
            contacts = []
            for key, label in (
                ("email", "email"),
                ("pec", "PEC"),
                ("telefono", "telefono"),
                ("cellulare", "cellulare"),
                ("fax", "fax"),
                ("sito_web", "sito web"),
            ):
                if clean_spaces(cliente.get(key)):
                    contacts.append(f"{label} {cliente.get(key)}")
            if contacts:
                lines.append("Recapiti autorizzati: " + "; ".join(contacts) + ".")
            lines.extend(_cliente_address_lines(cliente))
            lines.extend(_cliente_document_lines(cliente))
            lines.extend(_cliente_studio_lines(cliente))
            lines.extend(_cliente_privacy_lines(cliente))
            lines.extend(_cliente_note_lines(cliente))
        fascicoli = _data_for(results, "fascicoli")
        if fascicoli:
            lines.append(f"Fascicoli collegati: {len(fascicoli)}.")
            lines.extend(f"- {_label(row)}" for row in fascicoli[:5])
        scadenze = _data_for(results, "scadenziario")
        if scadenze:
            lines.append(f"Scadenze aperte rilevate: {len(scadenze)}.")
            lines.extend(f"- {_label(row)}" for row in scadenze[:4])
        agenda = _data_for(results, "agenda")
        if agenda:
            lines.append(f"Impegni in agenda collegati: {len(agenda)}.")
        preventivi = _data_for(results, "preventivi")
        conferimenti = _data_for(results, "conferimenti")
        parcelle = _data_for(results, "fatturazione")
        if route.intent in {"client_situation", "client_economic_summary"} and (preventivi or conferimenti or parcelle):
            lines.append(
                f"Quadro economico: preventivi {len(preventivi)}, conferimenti {len(conferimenti)}, parcelle {len(parcelle)}."
            )
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        lines.append("Fonti interne: dati del tenant corrente con permessi applicati.")
        return lines

    def _soggetti_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        rows = _data_for(results, "soggetti")
        parti = [row for row in rows if row.get("record_kind") == "parte"]
        soggetti = [row for row in rows if row.get("record_kind") != "parte"]
        lines: list[str] = []

        if parti:
            lines.append(f"Parti del fascicolo: {len(parti)}.")
            for parte in parti[:8]:
                role = clean_spaces(parte.get("ruolo")) or "Ruolo non indicato"
                label = _label(parte)
                details = _soggetto_identity_summary(parte)
                suffix = f" - {details}" if details else ""
                lines.append(f"- {role}: {label}{suffix}.")
                note = clean_spaces(parte.get("note_parte") or parte.get("note_soggetto"))
                if note:
                    lines.append(f"  Nota: {_short_text(note)}.")
            if len(parti) > 8:
                lines.append(f"Altre parti non mostrate: {len(parti) - 8}.")

        if len(soggetti) > 1 and not parti:
            names = ", ".join(_label(row) for row in soggetti[:6])
            return [
                "Ho trovato più soggetti compatibili.",
                f"Risultati: {names}.",
                "Restringi con codice fiscale, ruolo, fascicolo o recapito.",
            ]

        if soggetti:
            soggetto = soggetti[0]
            lines.append(f"Scheda soggetto: {_label(soggetto)}.")
            lines.extend(_soggetto_detail_lines(soggetto))

        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        if lines:
            lines.append("Fonti interne: soggetti, parti e fascicoli del tenant corrente con permessi applicati.")
            return lines
        return ["Non ho trovato soggetti o parti reali consultabili nelle sorgenti autorizzate."]

    def _fascicolo_lines(self, route: OperationalRoute, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        fascicoli = _data_for(results, "fascicoli")
        documenti = _data_for(results, "documenti_fascicolo")
        lines = []
        if len(fascicoli) > 1:
            lines.append("Ho trovato piu' fascicoli compatibili.")
            lines.extend(f"- {_label(row)}" for row in fascicoli[:5])
            lines.append("Indica numero RG, cliente o identificativo fascicolo per un riepilogo puntuale.")
            return lines
        if fascicoli:
            fascicolo = fascicoli[0]
            lines.append(f"Fascicolo: {_label(fascicolo)}.")
            for key, label in (("stato", "Stato"), ("tribunale", "Ufficio"), ("nome_cliente", "Cliente"), ("controparte", "Controparte")):
                if clean_spaces(fascicolo.get(key)):
                    lines.append(f"{label}: {fascicolo.get(key)}.")
        if documenti:
            lines.append(f"Documenti collegati o indicizzati: {len(documenti)}.")
            lines.extend(f"- {_label(row)}" for row in documenti[:5])
        for source_id, label in (("scadenziario", "Scadenze"), ("agenda", "Agenda"), ("preventivi", "Preventivi"), ("fatturazione", "Parcelle")):
            rows = _data_for(results, source_id)
            if rows:
                lines.append(f"{label}: {len(rows)} elementi.")
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        lines.append("Fonti interne: fascicolo e moduli collegati autorizzati.")
        return lines

    def _calendar_lines(self, route: OperationalRoute, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        scadenze = _data_for(results, "scadenziario")
        agenda = _data_for(results, "agenda")
        lines = [f"Scadenze consultabili: {len(scadenze)}.", f"Impegni agenda consultabili: {len(agenda)}."]
        for row in scadenze[:5]:
            lines.append(f"- Scadenza: {_label(row)}")
        for row in agenda[:5]:
            lines.append(f"- Agenda: {_label(row)}")
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        lines.append("Fonti interne: agenda e scadenziario del tenant corrente.")
        return lines

    def _communications_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        pec_rows = _sort_communications(_data_for(results, "email_pec"))
        ordinary_rows = _sort_communications(_data_for(results, "email_ordinaria"))
        messages = _sort_communications(_data_for(results, "messaggi"))
        lines: list[str] = []
        if pec_rows:
            latest = pec_rows[0]
            lines.append(f"Ultima PEC trovata: {_label(latest)}.")
            details = _communication_details(latest, include_folder=True)
            if details:
                lines.extend(details)
            if len(pec_rows) > 1:
                lines.append(f"Altre PEC consultabili: {len(pec_rows) - 1}.")
        if ordinary_rows:
            latest = ordinary_rows[0]
            heading = "Ultima email ordinaria trovata" if not pec_rows else "Ultima email ordinaria"
            lines.append(f"{heading}: {_label(latest)}.")
            lines.extend(_communication_details(latest, include_folder=True))
        if messages:
            lines.append(f"Messaggi interni collegati: {len(messages)}.")
            lines.extend(f"- {_label(row)}" for row in messages[:4])
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        if lines:
            lines.append("Fonti interne: comunicazioni del tenant corrente con permessi applicati.")
            return lines
        return ["Non ho trovato comunicazioni reali consultabili nelle caselle autorizzate."]

    def _economic_lines(self, route: OperationalRoute, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        labels = {
            "preventivi": "Preventivi",
            "conferimenti": "Conferimenti",
            "fatturazione": "Parcelle/fatture",
            "timesheet": "Attivita' timesheet",
            "tariffario": "Tariffario",
        }
        lines = []
        for source_id, label in labels.items():
            rows = _data_for(results, source_id)
            if rows:
                lines.append(f"{label}: {len(rows)} elementi.")
                lines.extend(f"- {_label(row)}" for row in rows[:4])
        if not lines:
            lines.append("Non ho trovato elementi economici reali consultabili per questa richiesta.")
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        lines.append("Fonti interne: moduli economici IUSENTRA, senza stime inventate.")
        return lines

    def _legal_sources_lines(
        self,
        results: list[OperationalToolResult],
        gaps: list[str],
        *,
        question: str = "",
    ) -> list[str]:
        rows = []
        for source_id in ("legal_intelligence", "update_intelligence", "fonti_ufficiali"):
            rows.extend(_data_for(results, source_id))
        attachment_rows = [row for row in rows if clean_spaces(row.get("attachment_url") or row.get("url_allegato"))]
        if attachment_rows:
            primary = attachment_rows[0]
            title = _label(primary)
            attachment_url = clean_spaces(primary.get("attachment_url") or primary.get("url_allegato"))
            page_url = clean_spaces(
                primary.get("official_url")
                or primary.get("source_url")
                or primary.get("url")
                or primary.get("page_url")
            )
            source_name = clean_spaces(
                primary.get("source_name")
                or primary.get("authority")
                or primary.get("fonte")
                or primary.get("source_id")
            )
            excerpt = clean_spaces(
                primary.get("excerpt")
                or primary.get("summary")
                or primary.get("content")
                or primary.get("text")
                or primary.get("context")
            )
            lines = [f"Allegato ufficiale trovato: {title}."]
            if source_name:
                lines.append(f"Fonte: {source_name}.")
            if attachment_url:
                lines.append(f"PDF: {attachment_url}")
            if page_url and page_url != attachment_url:
                lines.append(f"Pagina ufficiale: {page_url}")
            mismatch = _reference_mismatch_note(question, primary)
            if mismatch:
                lines.append(mismatch)
            if excerpt:
                lines.append(f"Estratto leggibile: {_short_text(excerpt)}.")
            display_gaps = [
                gap
                for gap in gaps
                if gap != "Una sorgente secondaria non è disponibile nel contesto corrente."
                and "Nessuna fonte ufficiale citabile trovata nell'indice locale configurato" not in gap
            ]
            if display_gaps:
                lines.append("Limiti: " + "; ".join(display_gaps[:3]) + ".")
            lines.append("Le fonti pubbliche restano distinte dai dati riservati dello studio.")
            return lines
        lines = [f"Fonti pubbliche/interne consultabili: {len(rows)}."]
        lines.extend(f"- {_label(row)}" for row in rows[:6])
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        lines.append("Le fonti pubbliche restano distinte dai dati riservati dello studio.")
        return lines

    def _template_editor_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        templates = _data_for(results, "template_atti")
        editor = _data_for(results, "editor_ai")
        fascicoli = _data_for(results, "fascicoli")
        documenti = _data_for(results, "documenti_fascicolo")
        lines: list[str] = []
        if templates:
            lines.append(f"Template atti compatibili: {len(templates)}.")
            lines.extend(f"- {_label(row)}" for row in templates[:5])
        if editor:
            row = editor[0]
            lines.append(f"Editor Lex: {_label(row)}.")
            capabilities = list(row.get("capabilities") or [])
            if capabilities:
                lines.append("Supporto disponibile: " + "; ".join(str(item) for item in capabilities[:4]) + ".")
        if fascicoli:
            lines.append(f"Fascicoli di contesto: {len(fascicoli)}.")
        if documenti:
            lines.append(f"Documenti citabili per la bozza: {len(documenti)}.")
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        lines.append("Lex deve proporre bozze e modifiche dentro l'editor, con fonti e accettazione umana.")
        return lines

    def _sources_overview(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        used = [result.source_id for result in results if result.ok]
        lines = ["Per questa risposta posso usare solo sorgenti autorizzate e citabili."]
        if used:
            lines.append("Sorgenti disponibili: " + ", ".join(sorted(set(used))) + ".")
        if gaps:
            lines.append("Sorgenti non disponibili o non autorizzate: " + "; ".join(gaps[:5]) + ".")
        return lines

    def _generic_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        labels = {
            "email_pec": "Email PEC",
            "email_ordinaria": "Email ordinaria",
            "editor_ai": "Editor Lex",
            "template_atti": "Template atti",
        }
        lines = []
        for result in results:
            rows = list(result.data or []) if isinstance(result.data, list) else ([result.data] if result.data else [])
            if rows:
                lines.append(f"{labels.get(result.source_id, result.source_id)}: {len(rows)} elementi reali.")
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        return lines or ["Non ho trovato dati operativi sufficienti."]

    def _confidence(self, results: list[OperationalToolResult], gaps: list[str]) -> float:
        ok_count = sum(1 for result in results if result.ok)
        data_count = sum(len(list(result.data or [])) if isinstance(result.data, list) else int(bool(result.data)) for result in results)
        value = 0.45 + min(0.35, ok_count * 0.07) + min(0.15, data_count * 0.02)
        value -= min(0.25, len(gaps) * 0.04)
        return round(max(0.1, min(0.92, value)), 4)

    def _next_actions(self, route: OperationalRoute, gaps: list[str]) -> list[str]:
        if route.intent in {"client_situation", "client_fascicoli"}:
            return ["Apri la scheda cliente o il fascicolo collegato per verificare il dato prima di agire."]
        if route.intent == "soggetti_lookup":
            return ["Verifica ruolo, recapiti e collegamento al fascicolo prima di usare i dati in un atto."]
        if route.intent in {"deadlines_overview", "agenda_overview"}:
            return ["Controlla la scadenza nel modulo originale prima di comunicare o depositare atti."]
        if route.intent in {"preventivo_summary", "conferimento_summary", "billing_summary", "tariffario_lookup"}:
            return ["Verifica importi, stato e collegamenti nel modulo economico prima di inviare documenti al cliente."]
        if gaps:
            return ["Restringi la richiesta o aggiungi identificativi per colmare i dati mancanti."]
        return []


def _data_for(results: list[OperationalToolResult], source_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        if result.source_id != source_id:
            continue
        if isinstance(result.data, list):
            rows.extend(dict(item) for item in result.data if isinstance(item, dict))
        elif isinstance(result.data, dict):
            rows.append(dict(result.data))
    return rows


def _label(row: dict[str, Any]) -> str:
    for key in ("nome_completo", "titolo", "title", "oggetto", "numero", "number", "nome", "name", "ragione_sociale", "id"):
        value = clean_spaces(row.get(key))
        if value:
            return value
    return "Elemento"


_REFERENCE_RE = re.compile(
    r"\b(?:r\.?\s*g\.?|rg)?\s*(?P<number>\d{2,7})\s*/\s*(?P<year>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)


def _reference_pairs(value: Any) -> list[str]:
    text = clean_spaces(value)
    result: list[str] = []
    for match in _REFERENCE_RE.finditer(text):
        ref = f"{match.group('number')}/{match.group('year')}"
        if ref not in result:
            result.append(ref)
    return result


def _reference_mismatch_note(question: str, row: dict[str, Any]) -> str:
    asked_refs = _reference_pairs(question)
    if not asked_refs:
        return ""
    row_text = " ".join(
        clean_spaces(row.get(key))
        for key in (
            "title",
            "titolo",
            "attachment_url",
            "url_allegato",
            "official_url",
            "source_url",
            "url",
            "excerpt",
            "summary",
            "content",
            "text",
            "context",
        )
        if clean_spaces(row.get(key))
    )
    found_refs = _reference_pairs(row_text)
    if not found_refs:
        return ""
    for asked in asked_refs:
        if asked not in found_refs:
            return (
                "Attenzione: nella domanda compare R.G. "
                f"{asked}, mentre nell'allegato acquisito risulta R.G. {found_refs[0]}."
            )
    return ""


def _cliente_identity_lines(cliente: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, label in (
        ("tipo", "Tipo"),
        ("stato", "Stato"),
        ("codice_fiscale", "Codice fiscale"),
        ("partita_iva", "Partita IVA"),
        ("forma_giuridica", "Forma giuridica"),
        ("codice_ateco", "Codice ATECO"),
        ("rappresentante_legale", "Rappresentante legale"),
        ("cf_rappresentante", "CF rappresentante"),
    ):
        value = clean_spaces(cliente.get(key))
        if value:
            lines.append(f"{label}: {value}.")
    birth = clean_spaces(cliente.get("data_nascita"))
    place = clean_spaces(cliente.get("luogo_nascita"))
    province = clean_spaces(cliente.get("provincia_nascita"))
    if birth or place or province:
        place_text = f"{place} ({province})" if place and province else place or province
        suffix = f" a {place_text}" if place_text else ""
        lines.append(f"Nascita: {birth or 'data non indicata'}{suffix}.")
    for key, label in (("nazionalita", "Nazionalità"), ("sesso", "Sesso"), ("data_costituzione", "Data costituzione")):
        value = clean_spaces(cliente.get(key))
        if value:
            lines.append(f"{label}: {value}.")
    return lines


def _cliente_address_lines(cliente: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, label in (
        ("indirizzo_residenza", "Residenza"),
        ("indirizzo_domicilio", "Domicilio"),
        ("indirizzo_sede_legale", "Sede legale"),
    ):
        value = clean_spaces(cliente.get(key))
        if value:
            lines.append(f"{label}: {value}.")
    return lines


def _cliente_document_lines(cliente: dict[str, Any]) -> list[str]:
    values = {
        "tipo": clean_spaces(cliente.get("documento_tipo")),
        "numero": clean_spaces(cliente.get("documento_numero")),
        "rilasciato": clean_spaces(cliente.get("documento_rilasciato_da")),
        "rilascio": clean_spaces(cliente.get("documento_data_rilascio")),
        "scadenza": clean_spaces(cliente.get("documento_data_scadenza")),
    }
    if not any(values.values()):
        return []
    parts = []
    if values["tipo"]:
        parts.append(values["tipo"])
    if values["numero"]:
        parts.append(f"n. {values['numero']}")
    if values["rilasciato"]:
        parts.append(f"rilasciato da {values['rilasciato']}")
    if values["rilascio"]:
        parts.append(f"il {values['rilascio']}")
    if values["scadenza"]:
        parts.append(f"scadenza {values['scadenza']}")
    if cliente.get("documento_scaduto") is True:
        parts.append("scaduto")
    return ["Documento: " + ", ".join(parts) + "."]


def _cliente_studio_lines(cliente: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, label in (
        ("avvocato_referente", "Referente studio"),
        ("data_prima_acquisizione", "Prima acquisizione"),
        ("provenienza", "Provenienza"),
    ):
        value = clean_spaces(cliente.get(key))
        if value:
            lines.append(f"{label}: {value}.")
    tags = [clean_spaces(tag) for tag in list(cliente.get("tag") or []) if clean_spaces(tag)]
    if tags:
        lines.append("Tag: " + ", ".join(tags[:8]) + ".")
    procedimenti = [item for item in list(cliente.get("procedimenti") or []) if isinstance(item, dict)]
    if procedimenti:
        lines.append(f"Procedimenti in scheda: {len(procedimenti)}.")
        for item in procedimenti[:4]:
            numero = clean_spaces(item.get("numero_rg"))
            anno = clean_spaces(item.get("anno"))
            tribunale = clean_spaces(item.get("tribunale"))
            attivo = "attivo" if item.get("attivo", True) else "chiuso"
            label = clean_spaces(" ".join(part for part in (f"RG {numero}/{anno}" if numero or anno else "", tribunale, attivo) if part))
            if label:
                lines.append(f"- {label}.")
    missing = [clean_spaces(item) for item in list(cliente.get("campi_mancanti_per_conferimento") or []) if clean_spaces(item)]
    if missing:
        lines.append("Dati da completare per conferimento: " + ", ".join(missing[:8]) + ".")
    return lines


def _cliente_privacy_lines(cliente: dict[str, Any]) -> list[str]:
    consent = cliente.get("consenso_trattamento")
    if consent is None:
        return []
    pieces = ["registrato" if bool(consent) else "non registrato"]
    date = clean_spaces(cliente.get("data_consenso"))
    mode = clean_spaces(cliente.get("modalita_consenso"))
    if date:
        pieces.append(f"data {date}")
    if mode:
        pieces.append(f"modalità {mode}")
    return ["Privacy: consenso trattamento " + ", ".join(pieces) + "."]


def _cliente_note_lines(cliente: dict[str, Any]) -> list[str]:
    note = clean_spaces(cliente.get("note"))
    if not note:
        return []
    return [f"Note operative: {_short_text(note)}."]


def _soggetto_detail_lines(soggetto: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, label in (
        ("tipo", "Tipo"),
        ("codice_fiscale", "Codice fiscale"),
        ("partita_iva", "Partita IVA"),
        ("forma_giuridica", "Forma giuridica"),
        ("rappresentante_legale", "Rappresentante legale"),
        ("qualifica", "Qualifica"),
        ("ordine", "Ordine"),
        ("numero_iscrizione", "Numero iscrizione"),
    ):
        value = clean_spaces(soggetto.get(key))
        if value:
            lines.append(f"{label}: {value}.")
    birth = clean_spaces(soggetto.get("data_nascita"))
    place = clean_spaces(soggetto.get("luogo_nascita"))
    province = clean_spaces(soggetto.get("provincia_nascita"))
    if birth or place or province:
        place_text = f"{place} ({province})" if place and province else place or province
        suffix = f" a {place_text}" if place_text else ""
        lines.append(f"Nascita: {birth or 'data non indicata'}{suffix}.")
    sex = clean_spaces(soggetto.get("sesso"))
    if sex:
        lines.append(f"Sesso: {sex}.")
    contacts = []
    for key, label in (
        ("email", "email"),
        ("pec", "PEC"),
        ("telefono", "telefono"),
        ("cellulare", "cellulare"),
        ("fax", "fax"),
        ("sito_web", "sito web"),
    ):
        value = clean_spaces(soggetto.get(key))
        if value:
            contacts.append(f"{label} {value}")
    if contacts:
        lines.append("Recapiti autorizzati: " + "; ".join(contacts) + ".")
    address = clean_spaces(soggetto.get("indirizzo"))
    if address:
        lines.append(f"Indirizzo: {address}.")
    if clean_spaces(soggetto.get("id_cliente")):
        lines.append("Collegato a una scheda cliente dello studio.")
    tags = [clean_spaces(tag) for tag in list(soggetto.get("tag") or []) if clean_spaces(tag)]
    if tags:
        lines.append("Tag: " + ", ".join(tags[:8]) + ".")
    note = clean_spaces(soggetto.get("note"))
    if note:
        lines.append(f"Note operative: {_short_text(note)}.")
    return lines


def _soggetto_identity_summary(soggetto: dict[str, Any]) -> str:
    parts = []
    for key, label in (("codice_fiscale", "CF"), ("partita_iva", "P.IVA"), ("pec", "PEC"), ("email", "email")):
        value = clean_spaces(soggetto.get(key))
        if value:
            parts.append(f"{label} {value}")
    return "; ".join(parts)


def _short_text(value: Any, *, max_length: int = 260) -> str:
    text = clean_spaces(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _communication_details(row: dict[str, Any], *, include_folder: bool = False) -> list[str]:
    details: list[str] = []
    sender = clean_spaces(row.get("mittente_nome") or row.get("mittente"))
    sent_at = clean_spaces(row.get("data") or row.get("ricevuta_il") or row.get("inviato_il"))
    recipients = row.get("destinatari")
    recipients_text = clean_spaces(", ".join(str(item) for item in recipients) if isinstance(recipients, list) else recipients)
    if sender:
        details.append(f"Mittente: {sender}.")
    if recipients_text:
        details.append(f"Destinatari: {recipients_text}.")
    if sent_at:
        details.append(f"Data: {sent_at}.")
    if include_folder:
        folder = clean_spaces(row.get("cartella"))
        if folder:
            details.append(f"Cartella: {folder}.")
    attachments = row.get("allegati_count")
    try:
        attachments_count = int(attachments or 0)
    except Exception:
        attachments_count = 0
    details.append(f"Allegati: {attachments_count}.")
    pct_state = clean_spaces(row.get("stato_pct"))
    if pct_state:
        details.append(f"Esito telematico rilevato: {pct_state}.")
    return details


def _sort_communications(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_communication_sort_key, reverse=True)


def _communication_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    for key in ("data", "ricevuta_il", "inviato_il", "creato_il"):
        value = clean_spaces(row.get(key))
        if value:
            return (1, value)
    return (0, "")


def _unique_strings(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        clean = clean_spaces(value)
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _user_facing_gaps(values: list[str]) -> list[str]:
    sanitized: list[str] = []
    for value in values:
        clean = clean_spaces(value)
        if not clean:
            continue
        lower = clean.lower()
        if any(
            marker in lower
            for marker in (
                "working outside of application context",
                "traceback",
                "exception",
                "no module named",
                "object has no attribute",
                "current_app",
                "flask",
            )
        ):
            clean = "Una sorgente secondaria non è disponibile nel contesto corrente."
        sanitized.append(clean)
    return _unique_strings(sanitized)


def _unique_sources(values: list[OperationalSourceReference]) -> list[OperationalSourceReference]:
    seen = set()
    result = []
    for value in values:
        key = (value.source_id, value.object_type, value.object_id, value.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _unique_objects(values: list[Any]) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        key = (getattr(value, "object_type", ""), getattr(value, "object_id", ""), getattr(value, "label", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
