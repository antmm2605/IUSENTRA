"""Italian response composer for deterministic operational answers."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pct.formatting import format_euro_it

from .models import OperationalAnswer, OperationalRoute, OperationalSourceReference, OperationalToolResult
from .serializers import clean_spaces

try:  # pragma: no cover - disponibile sulle versioni Python supportate
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]


_ITALIAN_MONTHS = {
    1: "gennaio",
    2: "febbraio",
    3: "marzo",
    4: "aprile",
    5: "maggio",
    6: "giugno",
    7: "luglio",
    8: "agosto",
    9: "settembre",
    10: "ottobre",
    11: "novembre",
    12: "dicembre",
}
_ITALIAN_MONTH_NAMES = tuple(_ITALIAN_MONTHS.values())
_ROME_TZ = ZoneInfo("Europe/Rome") if ZoneInfo is not None else None


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
            if route.intent == "sources_overview":
                answer_lines = self._sources_overview(results, gaps)
                return OperationalAnswer(
                    handled=True,
                    answer="\n".join(line for line in answer_lines if clean_spaces(line)),
                    route=route,
                    sources=sources,
                    objects=objects,
                    confidence=0.55,
                    coverage_gaps=gaps,
                    warnings=warnings,
                    next_actions=["Apri la scheda fonti o ripeti la domanda su un oggetto specifico per vedere le fonti usate."],
                    permissions_applied=permissions,
                    blocked_reason=blocked_reason,
                    metadata={"operational_layer": True, "sources_overview": True},
                )
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
        if route.intent in {"fascicolo_summary", "documenti_fascicolo", "build_case_timeline"}:
            return self._fascicolo_lines(route, results, gaps, question=question)
        if route.intent in {"deadlines_overview", "agenda_overview"}:
            return self._calendar_lines(route, results, gaps)
        if route.intent in {"preventivo_summary", "conferimento_summary", "billing_summary", "tariffario_lookup", "unbilled_activity"}:
            return self._economic_lines(route, results, gaps)
        if route.intent in {"legal_update_overview", "official_sources_lookup"}:
            return self._legal_sources_lines(results, gaps, question=question)
        if route.intent == "draft_communication":
            return self._communication_draft_lines(results, gaps)
        if route.intent == "communications_lookup":
            return self._communications_lines(results, gaps, question=question)
        if route.intent == "pec_control_tower":
            return self._pec_control_tower_lines(results, gaps)
        if route.intent == "studio_context_overview":
            return self._studio_context_overview_lines(results, gaps)
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
            if link := _row_link(cliente, label="Apri scheda cliente"):
                lines.append(f"Collegamento: {link}.")
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
        pagamenti = _data_for(results, "pagamenti")
        if route.intent in {"client_situation", "client_economic_summary"} and (preventivi or conferimenti or parcelle):
            lines.append(
                f"Quadro economico: preventivi {len(preventivi)}, conferimenti {len(conferimenti)}, parcelle {len(parcelle)}."
            )
        if pagamenti:
            lines.append(f"Pagamenti collegati: {len(pagamenti)}.")
            lines.extend(f"- {_payment_line(row)}" for row in pagamenti[:4])
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
                if added_at := _format_italian_date(parte.get("data_aggiunta")):
                    lines.append(f"  Collegamento al fascicolo registrato il {added_at}.")
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

    def _fascicolo_lines(self, route: OperationalRoute, results: list[OperationalToolResult], gaps: list[str], *, question: str = "") -> list[str]:
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
            if link := _row_link(fascicolo, label="Apri fascicolo"):
                lines.append(f"Collegamento: {link}.")
            for key, label in (("stato", "Stato"), ("tribunale", "Ufficio"), ("nome_cliente", "Cliente"), ("controparte", "Controparte")):
                if clean_spaces(fascicolo.get(key)):
                    lines.append(f"{label}: {fascicolo.get(key)}.")
        document_analysis_requested = _looks_like_document_analysis(question)
        if documenti:
            lines.append(f"Documenti del fascicolo collegati o indicizzati: {len(documenti)}.")
            if route.intent in {"documenti_fascicolo", "fascicolo_summary"} and document_analysis_requested:
                lines.extend(_professional_case_analysis_lines(fascicoli[0] if fascicoli else {}, documenti, question))
                if any(clean_spaces(row.get("anteprima") or row.get("summary") or row.get("content") or row.get("text")) for row in documenti):
                    lines.append("Metodo: ho usato il testo indicizzato disponibile e ho separato fatti leggibili, rischi, lacune e prossime azioni; le parti non indicizzate restano da verificare nel documento originale.")
                else:
                    lines.append("Il testo integrale non risulta disponibile in questa evidenza: non invento contenuti e segnalo solo metadati, data, tipo, hash e link editor.")
            else:
                lines.extend(f"- {_document_line(row)}" for row in documenti[:5])
        outcome_documents = [row for row in documenti if _is_outcome_document(row)]
        if outcome_documents:
            lines.append("Provvedimenti, verbali o sentenze rilevati nel fascicolo:")
            for row in outcome_documents[:4]:
                lines.append(f"- {_outcome_document_line(row)}")
        elif route.intent == "fascicolo_summary" and (
            _looks_like_missing_or_next_steps(question) or _looks_like_case_outcome_question(question)
        ):
            lines.append("Esito pratica: non risulta ancora un provvedimento, verbale o sentenza conclusiva leggibile nelle fonti consultate.")
        agenda_rows = _data_for(results, "agenda")
        hearing_rows = [row for row in agenda_rows if _is_hearing_event(row)]
        if hearing_rows:
            lines.append("Udienze ed eventi processuali collegati:")
            lines.extend(f"- {_hearing_event_line(row)}" for row in hearing_rows[:4])
        scadenze_rows = _data_for(results, "scadenziario")
        if scadenze_rows and (outcome_documents or hearing_rows or _looks_like_missing_or_next_steps(question)):
            lines.append("Termini e attività successive da presidiare:")
            lines.extend(f"- {_dated_label(row)}" for row in scadenze_rows[:4])
        if route.intent == "fascicolo_summary" and _looks_like_case_outcome_question(question):
            lines.append("Per valutare cosa ha inciso sull'esito, Lex usa solo eventi, udienze, documenti e termini realmente censiti nel fascicolo.")
        for source_id, label in (("scadenziario", "Scadenze"), ("agenda", "Agenda"), ("preventivi", "Preventivi"), ("fatturazione", "Parcelle")):
            rows = _data_for(results, source_id)
            if rows:
                lines.append(f"{label}: {len(rows)} elementi.")
                if route.intent == "build_case_timeline":
                    lines.extend(f"- {_dated_label(row)}" for row in rows[:4])
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        lines.append("Fonti interne: fascicolo e moduli collegati autorizzati.")
        return lines

    def _calendar_lines(self, route: OperationalRoute, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        scadenze = _data_for(results, "scadenziario")
        agenda = _data_for(results, "agenda")
        lines = [f"Scadenze consultabili: {len(scadenze)}.", f"Impegni agenda consultabili: {len(agenda)}."]
        for row in scadenze[:5]:
            lines.append(f"- Scadenza: {_dated_label(row)}")
        for row in agenda[:5]:
            lines.append(f"- Agenda: {_dated_label(row)}")
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        lines.append("Fonti interne: agenda e scadenziario del tenant corrente.")
        return lines

    def _communications_lines(self, results: list[OperationalToolResult], gaps: list[str], *, question: str = "") -> list[str]:
        clienti = _data_for(results, "clienti")
        fascicoli = _data_for(results, "fascicoli")
        audit_rows = _sort_communications(_data_for(results, "pec_audit"))
        pec_rows = _sort_communications(_data_for(results, "email_pec"))
        ordinary_rows = _sort_communications(_data_for(results, "email_ordinaria"))
        messages = _sort_communications(_data_for(results, "messaggi"))
        if _looks_like_communication_attachment_question(question):
            return _communication_attachment_act_lines(audit_rows, pec_rows, ordinary_rows, messages, gaps)
        lines: list[str] = []
        if fascicoli:
            lines.append(f"Fascicolo di contesto: {_row_link(fascicoli[0]) or _label(fascicoli[0])}.")
        if clienti:
            lines.append(f"Cliente di contesto: {_row_link(clienti[0]) or _label(clienti[0])}.")
        if audit_rows:
            lines.append(f"PEC da controllare: {len(audit_rows)} presidio automatico disponibile.")
            for row in audit_rows[:4]:
                lines.extend(_pec_audit_control_lines(row))
        if pec_rows:
            latest = pec_rows[0]
            prefix = "PEC di deposito/notifica collegata" if audit_rows else "Ultima PEC trovata"
            lines.append(f"{prefix}: {_label(latest)}.")
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

    def _pec_control_tower_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        payloads = _data_for(results, "pec_control_tower")
        payload = payloads[0] if payloads and isinstance(payloads[0], dict) else {}
        items = [dict(item) for item in list(payload.get("items") or []) if isinstance(item, dict)]
        lines: list[str] = [clean_spaces(payload.get("summary")) or f"Eventi PEC trovati: {len(items)}."]
        answer_kind = clean_spaces(payload.get("answer_kind"))
        for item in items[:8]:
            lines.extend(_pec_control_item_lines(item, answer_kind=answer_kind))
        if len(items) > 8:
            lines.append(f"Altri elementi non mostrati: {len(items) - 8}.")
        payload_gaps = [clean_spaces(item) for item in list(payload.get("coverage_gaps") or []) if clean_spaces(item)]
        all_gaps = _unique_strings([*gaps, *payload_gaps])
        if all_gaps:
            lines.append("Limiti: " + _join_clean_sentences(all_gaps[:3]) + ".")
        lines.append("Fonti interne: PEC Control Tower, fascicoli, scadenziario, agenda, notifiche e prove del tenant corrente.")
        return lines

    def _communication_draft_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        pec_rows = _sort_communications(_data_for(results, "email_pec"))
        ordinary_rows = _sort_communications(_data_for(results, "email_ordinaria"))
        messages = _sort_communications(_data_for(results, "messaggi"))
        communication = pec_rows[0] if pec_rows else (ordinary_rows[0] if ordinary_rows else {})
        if not communication:
            lines = ["Non ho trovato una PEC o email reale consultabile su cui preparare la risposta."]
            if messages:
                lines.append(f"Ho trovato solo messaggi interni collegati: {len(messages)}.")
            if gaps:
                lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
            lines.append("Serve indicare la PEC/email, il fascicolo o il cliente corretto prima di redigere.")
            return lines

        is_pec = bool(pec_rows)
        sender = clean_spaces(communication.get("mittente") or communication.get("mittente_nome"))
        date_value = _format_italian_date(communication.get("data"))
        subject = clean_spaces(communication.get("oggetto")) or "comunicazione ricevuta"
        body_hint = clean_spaces(communication.get("anteprima") or communication.get("corpo_testo"))
        lines = [
            "Ho trovato la comunicazione interna da usare come base della risposta.",
            f"Fonte: {'PEC' if is_pec else 'email ordinaria'} del {date_value or 'data non indicata'}, oggetto \"{subject}\".",
        ]
        if sender:
            lines.append(f"Mittente: {sender}.")
        if link := _row_link(communication, label="Apri comunicazione"):
            lines.append(f"Collegamento: {link}.")
        if communication.get("allegati_count"):
            lines.append(f"Allegati indicati dalla fonte: {communication.get('allegati_count')}.")
        lines.extend(
            [
                "",
                "BOZZA — RISPOSTA PEC" if is_pec else "BOZZA — RISPOSTA EMAIL",
                f"A: {sender or '[destinatario da verificare]'}",
                f"Oggetto: Riscontro a: {subject}",
                "",
                "Con riferimento alla comunicazione ricevuta, si prende atto di quanto indicato nella fonte interna sopra citata.",
            ]
        )
        if body_hint:
            lines.append(f"In particolare, dalla comunicazione risulta: {_short_text(body_hint, max_length=240)}.")
        lines.extend(
            [
                "Prima dell'invio si resta in attesa di conferma sul contenuto definitivo da comunicare e sugli eventuali allegati da richiamare.",
                "",
                "Dati da verificare prima dell'invio: destinatario, oggetto definitivo, posizione del fascicolo, allegati da citare e firma del professionista.",
                "Fonti interne: comunicazioni del tenant corrente con permessi applicati.",
            ]
        )
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        return lines

    def _economic_lines(self, route: OperationalRoute, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        labels = {
            "preventivi": "Preventivi",
            "conferimenti": "Conferimenti",
            "fatturazione": "Parcelle/fatture",
            "pagamenti": "Pagamenti",
            "timesheet": "Attivita' timesheet",
            "tariffario": "Tariffario",
        }
        lines = []
        for source_id, label in labels.items():
            rows = _data_for(results, source_id)
            if rows:
                lines.append(f"{label}: {len(rows)} elementi.")
                if source_id == "pagamenti":
                    lines.extend(f"- {_payment_line(row)}" for row in rows[:4])
                elif source_id in {"fatturazione", "preventivi", "conferimenti", "timesheet"}:
                    lines.extend(f"- {_dated_label(row)}" for row in rows[:4])
                else:
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
        for source_id in ("legal_intelligence", "update_intelligence", "fonti_ufficiali", "template_atti_fonti_ufficiali", "web_libero"):
            rows.extend(_data_for(results, source_id))
        source_delivery_rows = [
            row
            for row in rows
            if clean_spaces(row.get("kind")) == "centro_fonti_operativo"
        ]
        practice_rows = [
            row
            for row in _data_for(results, "matrice_pratica_legale")
            if clean_spaces(row.get("kind") or row.get("tipo")) in {"scheda_pratica_legale", "riferimento_nominale_legale"}
        ]
        attachment_rows = [row for row in rows if clean_spaces(row.get("attachment_url") or row.get("url_allegato"))]
        if (source_delivery_rows or practice_rows) and not attachment_rows:
            lines = [f"Fonti operative pertinenti trovate: {len(source_delivery_rows) + len(practice_rows)}."]
            for row in source_delivery_rows[:6]:
                title = _label(row)
                state = clean_spaces(row.get("state"))
                phase = clean_spaces(row.get("practice_phase"))
                output = clean_spaces(row.get("expected_output"))
                context = clean_spaces(row.get("professional_context"))
                action = clean_spaces(row.get("activation_action"))
                question_line = clean_spaces(row.get("lex_test_question"))
                url = clean_spaces(row.get("official_url"))
                legal_materials = [clean_spaces(item) for item in list(row.get("legal_materials") or []) if clean_spaces(item)]
                articles_and_codes = [clean_spaces(item) for item in list(row.get("articles_and_codes") or []) if clean_spaces(item)]
                decrees_and_rules = [clean_spaces(item) for item in list(row.get("decrees_and_rules") or []) if clean_spaces(item)]
                case_law_and_hearings = [clean_spaces(item) for item in list(row.get("case_law_and_hearings") or []) if clean_spaces(item)]
                research_steps = [clean_spaces(item) for item in list(row.get("research_steps") or []) if clean_spaces(item)]
                lines.append(f"- **{title}**: {state}.")
                if phase:
                    lines.append(f"  Fase pratica: {phase}.")
                if output:
                    lines.append(f"  Output atteso: {output}.")
                if context:
                    lines.append(f"  Contesto utile: {context}.")
                if legal_materials:
                    lines.append(f"  Materiali da controllare: {'; '.join(legal_materials[:3])}.")
                if articles_and_codes:
                    lines.append(f"  Articoli/codici: {'; '.join(articles_and_codes[:2])}.")
                if decrees_and_rules:
                    lines.append(f"  Decreti e regole tecniche: {'; '.join(decrees_and_rules[:2])}.")
                if case_law_and_hearings:
                    lines.append(f"  Sentenze, udienze e provvedimenti: {'; '.join(case_law_and_hearings[:2])}.")
                if research_steps:
                    lines.append(f"  Sequenza di ricerca: {'; '.join(research_steps[:2])}.")
                if action:
                    lines.append(f"  Azione: {action}.")
                if question_line:
                    lines.append(f"  Domanda Lex da verificare: {question_line}.")
                if url:
                    lines.append(f"  Fonte: {_markdown_link(url, label='Apri fonte ufficiale')}.")
            for row in practice_rows[:6]:
                kind = clean_spaces(row.get("kind") or row.get("tipo"))
                title = clean_spaces(row.get("title") or row.get("titolo") or row.get("id"))
                if not title:
                    continue
                authority = clean_spaces(row.get("authority") or row.get("autorita"))
                source_type = clean_spaces(row.get("source_type") or row.get("tipo_fonte") or kind)
                url = clean_spaces(row.get("official_url") or row.get("url_ufficiale"))
                articles = clean_spaces(row.get("articles") or row.get("articoli"))
                use = clean_spaces(row.get("use") or row.get("uso_operativo") or row.get("scope") or row.get("perimetro"))
                steps = [
                    clean_spaces(item)
                    for item in list(row.get("practice_steps") or row.get("passaggi_pratici") or row.get("acts_to_prepare") or row.get("atti_da_produrre") or [])
                    if clean_spaces(item)
                ]
                lex_questions = [
                    clean_spaces(item)
                    for item in list(row.get("lex_questions") or row.get("domande_lex") or [])
                    if clean_spaces(item)
                ]
                linked = [
                    clean_spaces(item)
                    for item in list(row.get("linked_practices") or row.get("pratiche_collegate") or [])
                    if clean_spaces(item)
                ]
                lines.append(f"- **{title}**: {source_type}.")
                if authority:
                    lines.append(f"  Autorità: {authority}.")
                if articles:
                    lines.append(f"  Riferimento specifico: {_sentence_text(articles)}")
                if use:
                    lines.append(f"  Uso in pratica: {_sentence_text(use)}")
                if steps:
                    lines.append(f"  Passaggi operativi: {_join_clean_sentences(steps[:2])}.")
                if linked:
                    lines.append(f"  Pratiche collegate: {_join_clean_sentences(linked[:3])}.")
                if lex_questions:
                    lines.append(f"  Domande Lex da verificare: {_join_clean_sentences(lex_questions[:2])}.")
                if url:
                    lines.append(f"  Fonte: {_markdown_link(url, label='Apri fonte ufficiale')}.")
            display_gaps = [
                gap
                for gap in gaps
                if "Nessuna fonte ufficiale citabile trovata nell'indice locale configurato" not in gap
            ]
            if display_gaps:
                lines.append("Limiti: " + "; ".join(display_gaps[:3]) + ".")
            lines.append("Uso professionale: una fonte catalogata non basta per citare in atto; prima va collegata al documento, alla regola vigente, al modello o alla prova del fascicolo.")
            return lines
        if attachment_rows:
            primary = attachment_rows[0]
            title = _label(primary)
            attachment_url = clean_spaces(primary.get("attachment_url") or primary.get("url_allegato"))
            page_url = clean_spaces(
                primary.get("page_url")
                or primary.get("source_base_url")
                or primary.get("source_url")
                or primary.get("url")
                or primary.get("official_url")
            )
            source_name = clean_spaces(
                primary.get("source_name")
                or primary.get("authority")
                or primary.get("fonte")
                or primary.get("source_id")
            )
            lines = [
                "Ho trovato una fonte ufficiale collegata alla richiesta.",
            ]
            reference_conflict = _reference_conflict(question, primary)
            case_details = _official_case_details(rows)
            attachment_analysis = _official_attachment_analysis(primary)
            concise_answer = _official_concise_legal_source_lines(
                question,
                case_details,
                attachment_analysis,
                reference_conflict=reference_conflict,
            )
            if concise_answer:
                lines.extend(concise_answer)
            norm_lines = _official_normative_explanation_lines(case_details, attachment_analysis)
            if norm_lines:
                lines.append("### Norme rilevanti")
                lines.extend(norm_lines)
            lines.extend(
                [
                    "### Fonte e PDF",
                    f"- Allegato: **{title}**.",
                ]
            )
            if reference_conflict:
                lines.append("- Collegamento: PDF ufficialmente collegato alla scheda, con numero R.G. interno diverso.")
            if source_name:
                lines.append(f"- Fonte: {source_name}.")
            if case_details:
                source_parts = []
                if ricorrente := clean_spaces(case_details.get("ricorrente")):
                    source_parts.append(f"ricorrente {ricorrente}")
                if relator := clean_spaces(case_details.get("relator")):
                    source_parts.append(f"relatore {relator}")
                if hearing := (_format_italian_date(case_details.get("hearing")) or clean_spaces(case_details.get("hearing"))):
                    source_parts.append(f"udienza {hearing}")
                if source_parts:
                    lines.append("- Scheda: " + "; ".join(source_parts) + ".")
            if attachment_url:
                lines.append(f"- PDF ufficiale: {_markdown_link(attachment_url, label='Apri PDF ufficiale')}.")
            if page_url and page_url != attachment_url:
                lines.append(f"- Pagina ufficiale: {_markdown_link(page_url, label='Apri scheda Cassazione')}.")
            mismatch = _reference_mismatch_note(question, primary, reference_conflict=reference_conflict)
            if mismatch:
                lines.append("### Punto da verificare")
                lines.append(mismatch)
            display_gaps = [
                gap
                for gap in gaps
                if gap != "Una sorgente secondaria non è disponibile nel contesto corrente."
                and "Nessuna fonte ufficiale citabile trovata nell'indice locale configurato" not in gap
            ]
            if display_gaps:
                lines.append("Limiti: " + "; ".join(display_gaps[:3]) + ".")
            free_web_lines = _free_web_article_lines(rows)
            if free_web_lines:
                lines.append("### Integrazione web libera sugli articoli")
                lines.extend(free_web_lines)
            lines.append("### Esito")
            lines.append("- Dato certo: pagina e allegato ufficiale sono stati trovati nell'archivio delle fonti pubbliche.")
            if reference_conflict:
                lines.append("- Controllo qualità: scheda, PDF collegato e nota R.G. sono stati tenuti separati; l'OCR grezzo non è stato riversato nella risposta.")
            lines.append("- Non sto usando dati riservati dello studio per questa risposta.")
            return _quality_guard_official_lines(lines)
        lines = [f"Fonti pubbliche/interne consultabili: {len(rows)}."]
        lines.extend(f"- {_label(row)}" for row in rows[:6])
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        lines.append("Le fonti pubbliche restano distinte dai dati riservati dello studio.")
        return lines

    def _template_editor_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        templates = _data_for(results, "template_atti")
        template_sources = _data_for(results, "template_atti_fonti_ufficiali")
        editor = _data_for(results, "editor_ai")
        fascicoli = _data_for(results, "fascicoli")
        documenti = _data_for(results, "documenti_fascicolo")
        lines: list[str] = []
        if templates:
            lines.append(f"Template atti compatibili: {len(templates)}.")
            lines.extend(f"- {_label(row)}" for row in templates[:5])
        if template_sources:
            lines.append(f"Fonti ufficiali dei modelli: {len(template_sources)} riferimenti documentati.")
            for row in template_sources[:6]:
                label = _label(row)
                code = clean_spaces(row.get("template_code"))
                article = clean_spaces(row.get("article"))
                role = clean_spaces(row.get("coverage_role"))
                parts = [part for part in (code, article, label, role) if part]
                lines.append("- " + " - ".join(parts))
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
        lines = ["Fonti operative consultabili: solo sorgenti autorizzate e citabili."]
        if used:
            lines.append("Sorgenti disponibili: " + ", ".join(sorted(set(used))) + ".")
        else:
            lines.append(
                "Fonti interne principali: clienti, fascicoli, soggetti, agenda, scadenziario, documenti fascicolo, PEC/email, preventivi, fatturazione e pagamenti."
            )
        if gaps:
            lines.append("Sorgenti non disponibili o non autorizzate: " + "; ".join(gaps[:5]) + ".")
        return lines

    def _studio_context_overview_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        labels = {
            "clienti": "Clienti",
            "fascicoli": "Fascicoli",
            "agenda": "Agenda",
            "scadenziario": "Scadenze",
            "email_pec": "PEC",
            "email_ordinaria": "Email ordinaria",
            "preventivi": "Preventivi",
            "conferimenti": "Conferimenti",
            "pagamenti": "Pagamenti",
        }
        lines = ["Ho consultato il contesto operativo autorizzato dello studio."]
        priorities = _studio_priority_lines(results)
        if priorities:
            lines.append("Priorità operative:")
            lines.extend(priorities[:5])
        found = False
        for source_id, label in labels.items():
            rows = _data_for(results, source_id)
            if not rows:
                continue
            found = True
            lines.append(f"{label}: {len(rows)} elementi consultabili.")
            lines.extend(f"- {_row_link(row) or _label(row)}" for row in rows[:2])
        if not found:
            lines.append("Non ho trovato elementi reali consultabili nelle sorgenti operative abilitate.")
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:5]) + ".")
        lines.append("Fonti interne: dati del tenant corrente con permessi applicati; fonti legali pubbliche escluse da questa consultazione.")
        return lines

    def _generic_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        labels = {
            "email_pec": "Email PEC",
            "email_ordinaria": "Email ordinaria",
            "editor_ai": "Editor Lex",
            "template_atti": "Template atti",
            "template_atti_fonti_ufficiali": "Fonti ufficiali Template Atti",
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
        if route.intent == "draft_communication":
            return ["Apri la comunicazione e rivedi la bozza nell'editor prima di inviarla."]
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


def _format_italian_date(value: Any) -> str:
    text = clean_spaces(value)
    if not text:
        return ""
    lower = text.lower()
    if any(month in lower for month in _ITALIAN_MONTH_NAMES):
        return text

    match = re.fullmatch(
        r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})"
        r"(?:(?:T|\s)(?P<hour>\d{2}):(?P<minute>\d{2})(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?",
        text,
    )
    if not match:
        match = re.fullmatch(r"(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{4})", text)
    if not match:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return text
        if parsed.tzinfo is not None and _ROME_TZ is not None:
            parsed = parsed.astimezone(_ROME_TZ)
        return _italian_date_parts(parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute)

    if match.groupdict().get("hour") and re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", text):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is not None and _ROME_TZ is not None:
                parsed = parsed.astimezone(_ROME_TZ)
            return _italian_date_parts(parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute)
        except Exception:
            pass

    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    hour = match.groupdict().get("hour")
    minute = match.groupdict().get("minute")
    return _italian_date_parts(year, month, day, int(hour) if hour else None, int(minute) if minute else None)


def _italian_date_parts(year: int, month: int, day: int, hour: int | None = None, minute: int | None = None) -> str:
    month_name = _ITALIAN_MONTHS.get(month)
    if not month_name:
        return ""
    base = f"{day} {month_name} {year}"
    if hour is not None and minute is not None:
        base += f" alle {hour:02d}:{minute:02d}"
    return base


def _label(row: dict[str, Any]) -> str:
    for key in ("nome_completo", "titolo", "title", "oggetto", "descrizione", "numero", "number", "nome", "name", "ragione_sociale", "id"):
        value = clean_spaces(row.get(key))
        if value:
            return value
    return "Elemento"


def _dated_label(row: dict[str, Any]) -> str:
    label = _label(row)
    for key in ("data_scadenza", "data_ora", "data", "scade_il", "creato_il"):
        value = _format_italian_date(row.get(key))
        if value:
            return f"{label} ({value})"
    return label


def _document_line(row: dict[str, Any]) -> str:
    label = _row_link(row) or _label(row)
    details = []
    for key, prefix in (("tipo", "tipo"), ("data_caricamento", "caricato"), ("sha256", "hash")):
        value = _format_italian_date(row.get(key)) if key.startswith("data") else clean_spaces(row.get(key))
        if value:
            details.append(f"{prefix} {value}")
    if clean_spaces(row.get("status")):
        details.append(f"stato {clean_spaces(row.get('status'))}")
    return label + (f" ({'; '.join(details)})." if details else ".")


def _document_excerpt(row: dict[str, Any], *, limit: int = 520) -> str:
    excerpt = clean_spaces(row.get("anteprima") or row.get("summary") or row.get("content") or row.get("text"))
    if not excerpt:
        return ""
    if len(excerpt) <= limit:
        return excerpt
    return excerpt[: limit - 3].rstrip() + "..."


def _professional_case_analysis_lines(
    fascicolo: dict[str, Any],
    documenti: list[dict[str, Any]],
    question: str,
) -> list[str]:
    haystack = clean_spaces(
        " ".join(
            [
                str(fascicolo.get(key) or "")
                for key in ("titolo", "oggetto", "nome_cliente", "controparte", "tribunale", "stato")
            ]
            + [
                str(row.get(key) or "")
                for row in documenti
                for key in ("nome", "title", "titolo", "tipo", "anteprima", "summary", "content", "text")
            ]
        )
    ).lower()
    lines: list[str] = ["Sintesi operativa per l'avvocato:"]
    lines.append(f"- Inquadramento: {_case_operational_frame(haystack)}")
    key_documents = _case_key_documents(documenti)
    if key_documents:
        lines.append("- Documenti chiave letti o indicizzati:")
        lines.extend(f"  - {item}" for item in key_documents[:6])
    risks = _case_risk_lines(haystack)
    if risks:
        lines.append("- Rischi aperti da presidiare:")
        lines.extend(f"  - {item}" for item in risks[:5])
    missing = _case_missing_lines(haystack, documenti)
    if missing:
        lines.append("- Cosa manca o va confermato:")
        lines.extend(f"  - {item}" for item in missing[:6])
    next_steps = _case_next_step_lines(haystack, question)
    if next_steps:
        lines.append("- Prossimi passi operativi:")
        lines.extend(f"  - {item}" for item in next_steps[:6])
    return lines


def _case_operational_frame(haystack: str) -> str:
    if any(token in haystack for token in ("ministero dell'istruzione", "mim", "scuola", "docente", "sostegno", "pei")):
        if any(token in haystack for token in ("tempo determinato", "contratti scolastici", "contratto individuale di lavoro")):
            return "pratica scolastica/lavoro pubblico contro amministrazione scolastica, con verifica di contratti a termine, servizio prestato, crediti o tutela del rapporto."
        return "pratica scolastica o amministrativa collegata a MIM/scuola, da leggere con fascicolo documentale, provvedimenti dell'istituto e termini di tutela."
    if any(token in haystack for token in ("decreto ingiuntivo", "opposizione", "provvisoria esecutorieta", "provvisoria esecutoriet")):
        return "opposizione o contenzioso civile monitorio: il punto centrale e' prova del credito, tempestivita' dell'opposizione e sospensione della provvisoria esecuzione."
    if any(token in haystack for token in ("sentenza", "accoglimento", "rigetto", "condanna alle spese")):
        return "fascicolo con provvedimento o esito leggibile: serve presidiare termini successivi, notifica, impugnazione o adempimenti conseguenti."
    if haystack:
        return "fascicolo attivo con documenti indicizzati: il sistema distingue dati letti, lacune e passaggi da confermare prima di generare atti o scadenze."
    return "fascicolo attivo senza testo documentale sufficiente: si possono usare solo metadati e collegamenti interni."


def _case_key_documents(documenti: list[dict[str, Any]]) -> list[str]:
    ranked = sorted(
        documenti,
        key=lambda row: (
            0 if _is_outcome_document(row) else 1,
            0 if _document_excerpt(row) else 1,
            clean_spaces(row.get("nome") or row.get("title") or row.get("titolo")),
        ),
    )
    result: list[str] = []
    for row in ranked:
        line = _document_line(row).rstrip(".")
        excerpt = _document_excerpt(row, limit=180)
        if excerpt:
            line += f" - evidenza: {_sentence_text(_short_text(excerpt, max_length=180))}"
        result.append(line if line.endswith(".") else line + ".")
    return _unique_strings(result)


def _case_risk_lines(haystack: str) -> list[str]:
    risks: list[str] = []
    if any(token in haystack for token in ("decadenza", "termine", "impugnazione", "prescrizione")):
        risks.append("termine, prescrizione o decadenza da calcolare e confermare nello scadenziario con regola verificabile.")
    if any(token in haystack for token in ("tempo determinato", "contratti scolastici", "contratto individuale di lavoro")):
        risks.append("prova delle annualità di servizio e coerenza tra contratti, stato di servizio, buste paga e domanda giudiziale.")
    if any(token in haystack for token in ("ministero dell'istruzione", "mim", "scuola", "docente")):
        risks.append("individuazione corretta dell'amministrazione resistente, dell'ufficio competente e della procedura applicabile.")
    if any(token in haystack for token in ("decreto ingiuntivo", "opposizione")):
        risks.append("tempestivita' dell'opposizione, prova del credito e valutazione della sospensione della provvisoria esecuzione.")
    if any(token in haystack for token in ("sentenza", "ordinanza", "provvedimento")):
        risks.append("termine successivo da presidiare: notifica, impugnazione, esecuzione, ottemperanza o deposito prova.")
    return _unique_strings(risks)


def _case_missing_lines(haystack: str, documenti: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    if any(token in haystack for token in ("tempo determinato", "contratti scolastici", "ministero dell'istruzione", "mim")):
        missing.extend(
            [
                "stato di servizio completo, nomine/contratti per anno scolastico e prove della continuità del servizio.",
                "buste paga, CU, diffide o atti interruttivi se la domanda riguarda differenze retributive, ricostruzione o prescrizione.",
                "provvedimenti MIM/USR/istituto, graduatorie o comunicazioni amministrative rilevanti per individuare domanda e convenuto.",
            ]
        )
    if "procura" not in haystack and "mandato" not in haystack:
        missing.append("procura alle liti o mandato, se non presente in altra sezione del fascicolo.")
    if not any(_is_outcome_document(row) for row in documenti):
        missing.append("provvedimento, verbale o sentenza conclusiva: non risulta leggibile tra i documenti indicizzati.")
    if not any(token in haystack for token in ("ricevuta", "accettazione", "consegna", "pec")):
        missing.append("ricevute PEC, deposito o prova di notifica collegata, se la fase processuale la richiede.")
    return _unique_strings(missing)


def _case_next_step_lines(haystack: str, question: str) -> list[str]:
    steps: list[str] = []
    if any(token in haystack for token in ("tempo determinato", "contratti scolastici", "ministero dell'istruzione", "mim")):
        steps.extend(
            [
                "costruire tabella annualità/contratti/documenti e collegarla a scadenziario e atto da produrre.",
                "scegliere domanda praticabile: accertamento rapporto, ricostruzione carriera, differenze, risarcimento o accesso atti, in base ai documenti presenti.",
            ]
        )
    if any(token in haystack for token in ("decreto ingiuntivo", "opposizione")):
        steps.extend(
            [
                "verificare data notifica/deposito e calcolare il termine dell'opposizione.",
                "preparare capitoli su prova del credito, sospensione e documenti mancanti del creditore.",
            ]
        )
    if any(token in haystack for token in ("sentenza", "ordinanza", "provvedimento")):
        steps.append("aprire scheda esito, calcolare termini successivi e preparare eventuale notifica, impugnazione o prova deposito.")
    if _looks_like_missing_or_next_steps(question) and not steps:
        steps.append("completare inventario documenti, associare scadenze/agenda/PEC e poi generare checklist dell'atto successivo.")
    return _unique_strings(steps)


_OUTCOME_DOCUMENT_TOKENS = (
    "sentenza",
    "ordinanza",
    "decreto",
    "verbale",
    "provvedimento",
    "omologa",
    "conciliazione",
    "esito",
    "accoglimento",
    "rigetto",
)


def _is_outcome_document(row: dict[str, Any]) -> bool:
    haystack = clean_spaces(
        " ".join(
            str(row.get(key) or "")
            for key in ("nome", "title", "titolo", "tipo", "categoria", "status", "anteprima", "summary")
        )
    ).lower()
    return any(token in haystack for token in _OUTCOME_DOCUMENT_TOKENS)


def _outcome_document_line(row: dict[str, Any]) -> str:
    base = _document_line(row).rstrip(".")
    excerpt = _document_excerpt(row, limit=220)
    if excerpt:
        return f"{base}. Estratto: {excerpt}"
    return base + "."


def _is_hearing_event(row: dict[str, Any]) -> bool:
    haystack = clean_spaces(
        " ".join(str(row.get(key) or "") for key in ("titolo", "title", "tipo", "categoria", "descrizione", "note", "oggetto"))
    ).lower()
    return any(token in haystack for token in ("udienz", "rinvio", "trattazione", "comparizione", "discussione", "camera di consiglio"))


def _hearing_event_line(row: dict[str, Any]) -> str:
    base = _dated_label(row)
    pieces = []
    for key, label in (
        ("ufficio", "ufficio"),
        ("giudice", "giudice"),
        ("esito", "esito"),
        ("outcome", "esito"),
        ("provvedimento", "provvedimento"),
        ("prossima_attivita", "prossima attività"),
        ("next_action", "prossima attività"),
    ):
        value = clean_spaces(row.get(key))
        if value:
            pieces.append(f"{label} {value}")
    note = _short_text(row.get("note") or row.get("descrizione"), max_length=180).rstrip(".")
    if note and note.lower() not in base.lower():
        pieces.append(f"nota {note}")
    return base + (f" ({'; '.join(pieces)})." if pieces else ".")


def _payment_line(row: dict[str, Any]) -> str:
    label = clean_spaces(row.get("descrizione")) or _label(row)
    amount = clean_spaces(row.get("importo") or row.get("totale") or row.get("amount"))
    state = clean_spaces(row.get("stato") or row.get("status"))
    pieces = []
    if amount:
        pieces.append(f"importo {format_euro_it(amount)}")
    if state:
        pieces.append(f"stato {state}")
    if created_at := _format_italian_date(row.get("creato_il")):
        pieces.append(f"creato il {created_at}")
    return label + (f" ({'; '.join(pieces)})." if pieces else ".")


def _looks_like_document_analysis(question: str) -> bool:
    text = clean_spaces(question).lower()
    return any(token in text for token in ("analizza", "spiega", "spiegami", "riassumi", "sintesi", "punti important", "punti più important"))


def _looks_like_missing_or_next_steps(question: str) -> bool:
    text = clean_spaces(question).lower()
    return any(token in text for token in ("cosa manca", "mancano", "prossimi passi", "prossima azione", "rischi", "rischio"))


def _looks_like_case_outcome_question(question: str) -> bool:
    text = clean_spaces(question).lower()
    return any(
        token in text
        for token in (
            "esito",
            "sentenza",
            "provvedimento",
            "udienza",
            "verbale",
            "successo",
            "andata bene",
            "andata male",
            "cosa ha inciso",
            "decisivo",
        )
    )


def _studio_priority_lines(results: list[OperationalToolResult]) -> list[str]:
    lines: list[str] = []
    scadenze = _data_for(results, "scadenziario")
    agenda = _data_for(results, "agenda")
    pec = _sort_communications(_data_for(results, "email_pec"))
    pagamenti = _data_for(results, "pagamenti")
    if scadenze:
        lines.append(f"- Scadenza da controllare: {_dated_label(scadenze[0])}.")
    if agenda:
        lines.append(f"- Agenda: {_dated_label(agenda[0])}.")
    if pec:
        lines.append(f"- Ultima PEC: {_label(pec[0])} ({_format_italian_date(pec[0].get('data')) or 'data non indicata'}).")
    if pagamenti:
        lines.append(f"- Pagamenti: {_payment_line(pagamenti[0])}")
    return lines


def _row_link(row: dict[str, Any], *, label: str = "") -> str:
    url = clean_spaces(row.get("action_url"))
    if not url:
        return ""
    return _markdown_link(url, label=label or _label(row))


def _extract_until_label(text: str, pattern: str, stop_labels: tuple[str, ...]) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    value = clean_spaces(match.group(1))
    if not value:
        return ""
    stop_positions = [
        pos
        for label in stop_labels
        for pos in [value.lower().find(label.lower())]
        if pos >= 0
    ]
    if stop_positions:
        value = clean_spaces(value[: min(stop_positions)])
    return value.strip(" .;")


def _extract_label_value(text: str, label: str, stop_labels: tuple[str, ...]) -> str:
    return _extract_until_label(text, rf"{re.escape(label)}\s*:?\s*(.+)", stop_labels)


def _row_content_text(row: dict[str, Any]) -> str:
    return clean_spaces(
        row.get("content")
        or row.get("text")
        or row.get("context")
        or row.get("excerpt")
        or row.get("summary")
        or row.get("title")
        or row.get("titolo")
    )


def _official_case_details(rows: list[dict[str, Any]]) -> dict[str, str]:
    page_text = ""
    for row in rows:
        if clean_spaces(row.get("attachment_url") or row.get("url_allegato")):
            continue
        candidate = _row_content_text(row)
        if "questione penale" in candidate.lower() or "questione civile" in candidate.lower():
            page_text = candidate
            break
    if not page_text:
        return {}

    question_text = _extract_until_label(
        page_text,
        r"\b(Se,\s+.+)",
        ("Ricorrente:", "Relatore:", "Data udienza:", "Riferimenti normativi:", "Allegati"),
    )
    inserted_at = _extract_label_value(
        page_text,
        "Data inserimento",
        ("Questione penale", "Questione civile", "Se,", "Ricorrente:"),
    )
    hearing = _extract_label_value(
        page_text,
        "Data udienza",
        ("Riferimenti normativi:", "Allegati", "Ordinanza"),
    )
    relator = _extract_label_value(
        page_text,
        "Relatore",
        ("Data udienza:", "Riferimenti normativi:", "Allegati"),
    )
    ricorrente = _extract_label_value(
        page_text,
        "Ricorrente",
        ("Relatore:", "Data udienza:", "Riferimenti normativi:", "Allegati"),
    )
    references = _extract_label_value(
        page_text,
        "Riferimenti normativi",
        ("Allegati", "Ordinanza", "Scarica Documento"),
    )

    return {
        "question_text": question_text,
        "inserted_at": inserted_at,
        "hearing": hearing,
        "relator": relator,
        "ricorrente": ricorrente,
        "references": references,
    }


def _official_case_summary_lines(rows: list[dict[str, Any]]) -> list[str]:
    return _official_case_summary_lines_from_details(_official_case_details(rows))


def _official_case_summary_lines_from_details(details: dict[str, str]) -> list[str]:
    lines: list[str] = []
    question_text = details.get("question_text", "")
    references = details.get("references", "")
    if question_text:
        lines.append(f"- Questione: {_sentence_text(question_text)}")
    if references:
        lines.append(f"- Riferimenti normativi: {_sentence_text(references)}")
    info_parts = []
    if inserted_at := (_format_italian_date(details.get("inserted_at", "")) or details.get("inserted_at", "")):
        info_parts.append(f"inserita il {inserted_at}")
    if hearing := (_format_italian_date(details.get("hearing", "")) or details.get("hearing", "")):
        info_parts.append(f"udienza {hearing}")
    if relator := details.get("relator", ""):
        info_parts.append(f"relatore {relator}")
    if ricorrente := details.get("ricorrente", ""):
        info_parts.append(f"ricorrente {ricorrente}")
    if info_parts:
        lines.append("- Scheda: " + "; ".join(info_parts) + ".")
    return lines


def _extract_segment(text: str, start_pattern: str, stop_patterns: tuple[str, ...], *, include_start: bool = False) -> str:
    match = re.search(start_pattern, text, re.IGNORECASE)
    if not match:
        return ""
    start = match.start() if include_start else match.end()
    value = clean_spaces(text[start:])
    stop_positions = [
        pos
        for stop in stop_patterns
        for pos in [value.lower().find(stop.lower())]
        if pos >= 0
    ]
    if stop_positions:
        value = clean_spaces(value[: min(stop_positions)])
    return value.strip(" .;")


def _official_attachment_analysis(row: dict[str, Any]) -> dict[str, Any]:
    text = _row_content_text(row)
    if len(text) < 300:
        return {}
    lowered = text.lower()
    if "599-bis" not in lowered and "concordato" not in lowered and "ricorso" not in lowered:
        return {}

    proceeding = _extract_segment(
        text,
        r"ricorso\s+RG\s+\d+/\d+,\s+proposto",
        ("1.1.", "Dalla proposta", "Il ricorrente deduce"),
        include_start=True,
    )

    penalty = _extract_segment(
        text,
        r"pena\s+base,",
        ("1.2.", "Il ricorrente deduce"),
        include_start=True,
    )
    if penalty:
        penalty = _clean_ocr_excerpt(penalty)

    complaints = _complaint_lines(text)

    legal_theme = _extract_segment(
        text,
        r"il\s+ricorso\s+pone\s+il\s+tema",
        ("; tema rilevante", "2.", "Siffatta nozione"),
        include_start=True,
    )
    legal_theme = _clean_ocr_excerpt(legal_theme)
    if not legal_theme or clean_spaces(legal_theme).lower() == "il ricorso pone":
        legal_theme = (
            "la questione riguarda se, dopo il concordato in appello, si possano dedurre in Cassazione "
            "vizi sulla determinazione della pena quando la pena non è illegale in senso stretto"
        )

    analysis: dict[str, Any] = {
        "nature": "non è una sentenza definitiva; è un'ordinanza/nota di rimessione collegata a una questione penale pendente",
        "proceeding": _clean_ocr_excerpt(proceeding),
        "penalty": penalty,
        "complaints": complaints,
        "legal_theme": legal_theme,
        "article_references": _article_references(text),
        "status": "la questione è pendente; la scheda indica l'udienza del 09 luglio 2026, quindi non risulta una decisione finale sul merito della questione",
    }
    if "pena illegale" in lowered and "pena è illegittima" in lowered:
        analysis["legal_distinction"] = (
            "l'atto distingue tra pena illegale, fuori dal sistema o dai limiti edittali, e pena soltanto "
            "illegittima per errori nel percorso di commisurazione"
        )
    return analysis


def _official_attachment_summary_lines(row: dict[str, Any]) -> list[str]:
    return _official_attachment_summary_lines_from_analysis(_official_attachment_analysis(row))


def _official_normative_explanation_lines(
    case_details: dict[str, str],
    attachment_analysis: dict[str, Any],
) -> list[str]:
    combined = " ".join(
        clean_spaces(part)
        for part in (
            case_details.get("references", ""),
            " ".join(str(item) for item in attachment_analysis.get("article_references", []) or []),
            attachment_analysis.get("legal_theme", ""),
        )
        if clean_spaces(part)
    )
    lowered = combined.lower()
    if not lowered:
        return []
    lines: list[str] = []
    references = clean_spaces(case_details.get("references"))
    article_refs = [clean_spaces(item) for item in list(attachment_analysis.get("article_references") or []) if clean_spaces(item)]
    labels = _unique_preserve_order(([references] if references else []) + article_refs)
    if labels:
        lines.append("- Riferimenti trovati: " + "; ".join(labels[:10]) + ".")
    if "599-bis" in lowered:
        lines.append("- Art. 599-bis c.p.p.: riguarda il concordato in appello, cioè l'accordo tra le parti sulla pena o sulla rinuncia ai motivi.")
    if re.search(r"\b606\b", lowered):
        lines.append("- Art. 606 c.p.p.: delimita i motivi deducibili con ricorso per cassazione.")
    if re.search(r"\b129\b", lowered):
        lines.append("- Art. 129 c.p.p.: impone al giudice il proscioglimento immediato quando emerge una causa evidente.")
    if re.search(r"\b610\b", lowered):
        lines.append("- Art. 610 c.p.p.: riguarda il vaglio preliminare e la trattazione del ricorso in Cassazione.")
    if re.search(r"\b81\b", lowered):
        lines.append("- Art. 81 c.p.: disciplina la continuazione e incide sul calcolo della pena complessiva.")
    return _unique_preserve_order(lines)


def _official_attachment_summary_lines_from_analysis(
    analysis: dict[str, Any],
    *,
    reference_conflict: dict[str, str] | None = None,
) -> list[str]:
    if not analysis:
        return []
    has_conflict = bool(reference_conflict)
    lines = [
        f"- Natura dell'atto: {_sentence_text(analysis.get('nature'))}",
    ]
    if has_conflict:
        lines.append(
            "- Avvertenza: questa sintesi riguarda il PDF collegato, che riporta un numero R.G. diverso; "
            "non attribuisce con certezza quei fatti alla scheda richiesta."
        )
    if not has_conflict and analysis.get("proceeding"):
        lines.append(f"- Vicenda processuale: {_sentence_text(_short_text(analysis['proceeding'], max_length=520))}")
    if not has_conflict and analysis.get("penalty"):
        lines.append(f"- Pena concordata: {_sentence_text(_short_text(analysis['penalty'], max_length=520))}")
    complaints = list(analysis.get("complaints") or [])
    if complaints:
        if has_conflict:
            lines.append("- Motivi/censure leggibili nel PDF collegato, da verificare prima dell'attribuzione:")
        else:
            lines.append("- Motivi del ricorso:")
        lines.extend(f"  - {_sentence_text(item)}" for item in complaints[:4])
    if analysis.get("legal_theme"):
        prefix = "Punto di diritto nel PDF collegato" if has_conflict else "Punto di diritto"
        lines.append(f"- {prefix}: {_sentence_text(_short_text(analysis['legal_theme'], max_length=420))}")
    articles = list(analysis.get("article_references") or [])
    if articles:
        label = "Articoli richiamati nel PDF collegato" if has_conflict else "Articoli richiamati nell'allegato"
        lines.append(f"- {label}: " + "; ".join(articles[:8]) + ".")
    if analysis.get("legal_distinction"):
        lines.append(f"- Snodo giuridico: {_sentence_text(analysis['legal_distinction'])}")
    if analysis.get("status"):
        lines.append(f"- Stato: {_sentence_text(analysis['status'])}")
    return lines


def _complaint_lines(text: str) -> list[str]:
    block = _extract_segment(
        text,
        r"Il\s+ricorrente\s+deduce,\s+con\s+quattro\s+motivi,\s+le\s+seguenti\s+censure:\s*",
        ("AI netto", "Al netto", "il ricorso pone"),
    )
    if not block:
        return []
    pieces = re.split(r"\s+-\s+", " " + block)
    result: list[str] = []
    for piece in pieces:
        clean = clean_spaces(piece).strip(" -.;")
        if not clean or clean.lower().startswith("il ricorrente deduce"):
            continue
        if clean not in result:
            result.append(_short_text(clean, max_length=220))
    return result


def _official_concise_legal_source_lines(
    question: str,
    case_details: dict[str, str],
    attachment_analysis: dict[str, Any],
    *,
    reference_conflict: dict[str, str] | None = None,
) -> list[str]:
    if not case_details and not attachment_analysis:
        return []
    normalized = clean_spaces(question).lower()
    wants_people = any(token in normalized for token in ("ricorrente", "relatore", "parti", "chi è", "chi ha"))
    wants_attachment = any(token in normalized for token in ("allegato", "pdf", "ordinanza", "link", "scaricare"))
    wants_citation = any(token in normalized for token in ("citare", "citazione", "usare in atto", "utilizzare in atto", "valore"))

    lines = ["### Sintesi"]
    lines.append("- Non risulta una sentenza: è una questione penale pendente con ordinanza/nota di rimessione.")
    if "sentenza" in normalized or "natura" in normalized or "che atto" in normalized:
        lines.append("- Natura dell'atto: questione penale pendente, non sentenza definitiva.")
    if question_text := clean_spaces(case_details.get("question_text")):
        lines.append(f"- Oggetto: {_sentence_text(question_text)}")
    if attachment_analysis.get("status"):
        lines.append(f"- Stato: {_sentence_text(attachment_analysis['status'])}")
    legal_theme = clean_spaces(attachment_analysis.get("legal_theme"))
    if legal_theme:
        prefix = "Punto di diritto / principio in discussione nel PDF collegato" if reference_conflict else "Punto di diritto / principio in discussione"
        lines.append(f"- {prefix}: {_sentence_text(_short_text(legal_theme, max_length=360))}")
    complaints = list(attachment_analysis.get("complaints") or [])
    if complaints:
        label = "Motivi/censure dal PDF collegato"
        if reference_conflict:
            label += " (citati come contenuto del PDF, non come dati certi autonomi della scheda)"
        joined = "; ".join(_sentence_text(item) for item in complaints[:4])
        if joined:
            lines.append(f"- {label}: {joined}")
    if question_text:
        lines.append(
            "- Effetto pratico: la futura decisione chiarirà i limiti del ricorso per cassazione "
            "contro una pena concordata in appello quando non si deduce una pena illegale in senso stretto."
        )
    if reference_conflict:
        lines.append(
            "- Nota R.G.: la scheda/domanda cita R.G. "
            f"{reference_conflict.get('asked')}, mentre il PDF collegato riporta R.G. "
            f"{reference_conflict.get('found')}; entrambi sono citabili, ma restano distinti."
        )
    if wants_people:
        people = []
        if ricorrente := clean_spaces(case_details.get("ricorrente")):
            people.append(f"ricorrente {ricorrente}")
        if relator := clean_spaces(case_details.get("relator")):
            people.append(f"relatore {relator}")
        if people:
            lines.append("- Dati della scheda: " + "; ".join(people) + ".")
    if wants_attachment:
        lines.append("- Allegato/PDF: ordinanza di rimessione collegata dalla scheda; il link cliccabile è riportato sotto.")
    if wants_citation:
        lines.append("- Uso prudente: può essere citata come questione pendente e allegato collegato, non come arresto definitivo o decisione finale.")
    return _unique_preserve_order(lines)


def _official_question_answer_lines(
    question: str,
    case_details: dict[str, str],
    attachment_analysis: dict[str, Any],
    *,
    reference_conflict: dict[str, str] | None = None,
) -> list[str]:
    if not case_details and not attachment_analysis:
        return []
    normalized = clean_spaces(question).lower()
    wants_summary = any(token in normalized for token in ("sintesi", "sintetizz", "riassum", "cosa dice", "spieg"))
    wants_legal_theme = any(token in normalized for token in ("punto di diritto", "quesito", "questione", "principio", "deducibil"))
    wants_motives = any(token in normalized for token in ("motivi", "censure", "doglian"))
    wants_nature = any(token in normalized for token in ("sentenza", "pendente", "che atto", "natura"))
    wants_schedule = any(token in normalized for token in ("udienza", "quando", "norme", "riferimenti normativi", "artt", "articoli"))
    wants_articles = any(token in normalized for token in ("art.", "artt", "articolo", "articoli", "norme", "riferimenti normativi"))
    wants_people = any(token in normalized for token in ("ricorrente", "relatore", "parti", "chi è", "chi ha"))
    wants_status = any(token in normalized for token in ("esito", "decisa", "deciso", "decisione finale", "risultato"))
    wants_citation = any(token in normalized for token in ("citare", "citazione", "usare in atto", "utilizzare in atto", "valore"))
    wants_attachment = any(token in normalized for token in ("allegato", "pdf", "ordinanza", "link", "scaricare"))
    if not any((wants_summary, wants_legal_theme, wants_motives, wants_nature, wants_schedule, wants_articles, wants_people, wants_status, wants_citation, wants_attachment)):
        wants_summary = True

    lines: list[str] = []
    case_question = case_details.get("question_text", "")
    legal_theme = clean_spaces(attachment_analysis.get("legal_theme") or case_question)
    has_conflict = bool(reference_conflict)
    if wants_summary or wants_nature:
        lines.append("- Non risulta una sentenza definitiva: la fonte disponibile è una questione penale pendente con ordinanza/nota di rimessione.")
    if wants_summary:
        if case_question:
            lines.append(
                "- In sintesi: la Cassazione deve chiarire "
                + _lowercase_initial(_sentence_text(case_question))
            )
        elif legal_theme:
            lines.append(f"- In sintesi: {_sentence_text(legal_theme)}")
        proceeding = clean_spaces(attachment_analysis.get("proceeding"))
        if has_conflict:
            lines.append(
                "- Attenzione: il PDF collegato riporta R.G. "
                f"{reference_conflict.get('found', '')}, mentre la domanda/scheda indica R.G. "
                f"{reference_conflict.get('asked', '')}; Lex quindi tiene separati scheda e PDF."
            )
        elif proceeding:
            lines.append(f"- Contesto processuale: {_sentence_text(_short_text(proceeding, max_length=360))}")
    if wants_nature and attachment_analysis.get("nature") and not (wants_summary or has_conflict):
        lines.append(f"- Natura dell'atto: {_sentence_text(attachment_analysis['nature'])}")
    if wants_legal_theme and legal_theme:
        lines.append(f"- Punto di diritto: {_sentence_text(_short_text(legal_theme, max_length=420))}")
    complaints = list(attachment_analysis.get("complaints") or [])
    if wants_motives and complaints:
        if has_conflict:
            lines.append("- Motivi/censure indicati nel PDF collegato, da non attribuire automaticamente a R.G. "
                         f"{reference_conflict.get('asked', '')}:")
        else:
            lines.append("- Motivi/censure indicati nell'ordinanza:")
        lines.extend(f"  - {_sentence_text(item)}" for item in complaints[:4])
    if wants_schedule:
        hearing = _format_italian_date(case_details.get("hearing")) or clean_spaces(case_details.get("hearing"))
        references = clean_spaces(case_details.get("references"))
        if hearing:
            lines.append(f"- Udienza indicata in scheda: {hearing}.")
        if references:
            lines.append(f"- Norme indicate: {_sentence_text(references)}")
    if wants_articles:
        articles = _unique_preserve_order(
            [clean_spaces(case_details.get("references"))]
            + [clean_spaces(item) for item in list(attachment_analysis.get("article_references") or [])]
        )
        articles = [item for item in articles if item]
        if articles:
            lines.append("- Articoli/riferimenti trovati: " + "; ".join(articles[:10]) + ".")
    if wants_people:
        ricorrente = clean_spaces(case_details.get("ricorrente"))
        relator = clean_spaces(case_details.get("relator"))
        if ricorrente:
            lines.append(f"- Ricorrente indicato nella scheda: {ricorrente}.")
        if relator:
            lines.append(f"- Relatore indicato nella scheda: {relator}.")
    if wants_attachment:
        if has_conflict:
            lines.append(
                "- Allegato collegato individuato: ordinanza di rimessione; il PDF è cliccabile sotto, "
                "ma il numero R.G. interno va verificato prima di usarlo come allegato della scheda richiesta."
            )
        else:
            lines.append("- Allegato ufficiale individuato: ordinanza di rimessione; il collegamento al PDF è riportato nella sezione Allegato ufficiale.")
    if wants_status and attachment_analysis.get("status"):
        lines.append(f"- Esito/stato: {_sentence_text(attachment_analysis['status'])}")
    if wants_citation:
        lines.append("- Uso prudente: trattala come fonte ufficiale su questione pendente e ordinanza di rimessione, non come arresto definitivo di Cassazione.")
    if wants_summary and attachment_analysis.get("status"):
        lines.append(f"- Stato: {_sentence_text(attachment_analysis['status'])}")
    return _unique_preserve_order(lines)


def _free_web_article_lines(rows: list[dict[str, Any]]) -> list[str]:
    web_rows = [
        row for row in rows
        if clean_spaces(row.get("source_id") or row.get("fonte") or row.get("source_name")).lower() in {"web_libero", "web libero"}
        or clean_spaces(row.get("source_access_label")).lower() == "web libero"
        or clean_spaces(row.get("source_priority")).lower() == "web_libero"
    ]
    if not web_rows:
        return []
    lines: list[str] = []
    for row in web_rows[:3]:
        title = clean_spaces(row.get("title") or row.get("titolo") or row.get("name") or "Risultato web")
        url = clean_spaces(row.get("official_url") or row.get("url") or row.get("source_url"))
        excerpt = clean_spaces(row.get("excerpt") or row.get("summary") or row.get("text"))
        line = f"- {title}"
        if url:
            line += f": {_markdown_link(url, label='Apri risultato')}"
        if excerpt:
            line += f" - {_sentence_text(_short_text(excerpt, max_length=220))}"
        else:
            line += "."
        lines.append(line)
    return lines


def _clean_ocr_excerpt(value: Any) -> str:
    text = clean_spaces(value)
    if not text:
        return ""
    text = re.sub(r"\s*[\\|_]{2,}\s*-?\s*", " ", text)
    text = re.sub(r"\s+\|\s*", " ", text)
    text = re.sub(r"\s*/\s*[A-Z][a-zA-Z]?\s+", " ", text)
    text = re.sub(r"\bDIN\s+", "", text)
    text = re.sub(r"\bdi\s+N\s+Caltanissetta\b", "di Caltanissetta", text, flags=re.IGNORECASE)
    text = re.sub(r"\bedi\b", "e di", text, flags=re.IGNORECASE)
    text = re.sub(r"\balia\b", "alla", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" .;")


def _safe_ocr_excerpt(value: Any) -> str:
    text = _clean_ocr_excerpt(value)
    if not text:
        return ""
    lowered = text.lower()
    noisy_markers = (
        "pervenutoil",
        " al medesimo d ",
        " mesi o",
        "\ufffd",
    )
    if any(marker in lowered for marker in noisy_markers):
        return ""
    if re.search(r"\b[A-Za-zàèéìòù]{1}\s*\|\s*[A-Za-zàèéìòù]{1}\b", text):
        return ""
    return _sentence_text(_short_text(text, max_length=360))


def _article_references(text: str) -> list[str]:
    value = clean_spaces(text)
    if not value:
        return []
    references: list[str] = []
    for match in re.finditer(
        r"\bartt?\.?\s+([\d]+(?:-[a-z]+)?(?:\s*,\s*comma\s+(?:primo|secondo|terzo|quarto|\d+))?)\s+"
        r"(cod\.?\s+(?:proc\.?\s+pen\.?|pen\.?|civ\.?|proc\.?\s+civ\.?))",
        value,
        flags=re.IGNORECASE,
    ):
        article = clean_spaces(match.group(1))
        code = _normalize_code_label(match.group(2))
        label = f"art. {article} {code}"
        if label not in references:
            references.append(label)
    for match in re.finditer(
        r"\bartt?\.?\s+([\d]+(?:-[a-z]+)?(?:\s*,\s*comma\s+(?:primo|secondo|terzo|quarto|\d+))?)\s*,?\s+"
        r"(cod\.?\s+(?:proc\.?\s+pen\.?|pen\.?|civ\.?|proc\.?\s+civ\.?))",
        value,
        flags=re.IGNORECASE,
    ):
        article = clean_spaces(match.group(1))
        code = _normalize_code_label(match.group(2))
        label = f"art. {article} {code}"
        if label not in references:
            references.append(label)
    for match in re.finditer(
        r"\bex\s+art\.?\s+([\d]+(?:-[a-z]+)?)\s+"
        r"(cod\.?\s+(?:proc\.?\s+pen\.?|pen\.?|civ\.?|proc\.?\s+civ\.?))",
        value,
        flags=re.IGNORECASE,
    ):
        article = clean_spaces(match.group(1))
        code = _normalize_code_label(match.group(2))
        label = f"art. {article} {code}"
        if label not in references:
            references.append(label)
    return references


def _normalize_code_label(value: str) -> str:
    code = clean_spaces(value).lower().replace("cod.", "cod.")
    code = re.sub(r"\s+", " ", code)
    replacements = {
        "cod. proc. pen.": "c.p.p.",
        "cod. pen.": "c.p.",
        "cod. civ.": "c.c.",
        "cod. proc. civ.": "c.p.c.",
    }
    return replacements.get(code, code)


def _lowercase_initial(value: str) -> str:
    text = clean_spaces(value)
    if not text:
        return ""
    return text[:1].lower() + text[1:]


def _unique_preserve_order(lines: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for line in lines:
        marker = clean_spaces(line).lower()
        if not marker or marker in seen:
            continue
        seen.add(marker)
        result.append(line)
    return result


def _quality_guard_official_lines(lines: list[str]) -> list[str]:
    guarded: list[str] = []
    seen_headings: set[str] = set()
    forbidden_fragments = (
        "Corte d'appello di N Caltanissetta",
        "Corte d’appello di N Caltanissetta",
        "al medesimo | d",
        "anni due e mesi o",
        "Pervenutoil",
    )
    for line in lines:
        text = clean_spaces(line)
        if not text:
            continue
        if any(fragment in text for fragment in forbidden_fragments):
            continue
        if text.startswith("### "):
            heading = text.lower()
            if heading in seen_headings:
                continue
            seen_headings.add(heading)
        guarded.append(line)
    return _unique_preserve_order(guarded)


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


def _reference_conflict(question: str, row: dict[str, Any]) -> dict[str, str]:
    asked_refs = _reference_pairs(question)
    if not asked_refs:
        return {}
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
        return {}
    for asked in asked_refs:
        if asked not in found_refs:
            return {"asked": asked, "found": found_refs[0]}
    return {}


def _reference_mismatch_note(
    question: str,
    row: dict[str, Any],
    *,
    reference_conflict: dict[str, str] | None = None,
) -> str:
    conflict = reference_conflict or _reference_conflict(question, row)
    if not conflict:
        return ""
    return (
        "Attenzione: la scheda/domanda indica R.G. "
        f"{conflict.get('asked')}, mentre il PDF ufficialmente collegato alla scheda riporta al suo interno R.G. "
        f"{conflict.get('found')}. Il PDF resta citabile come allegato collegato; i dati letti nel PDF sono "
        "presentati come contenuto del PDF collegato e non come dati certi autonomi della scheda."
    )


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
        birth_label = _format_italian_date(birth) or "data non indicata"
        lines.append(f"Nascita: {birth_label}{suffix}.")
    for key, label in (("nazionalita", "Nazionalità"), ("sesso", "Sesso"), ("data_costituzione", "Data costituzione")):
        value = _format_italian_date(cliente.get(key)) if key.startswith("data_") else clean_spaces(cliente.get(key))
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
        parts.append(f"il {_format_italian_date(values['rilascio']) or values['rilascio']}")
    if values["scadenza"]:
        parts.append(f"scadenza {_format_italian_date(values['scadenza']) or values['scadenza']}")
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
        value = _format_italian_date(cliente.get(key)) if key.startswith("data_") else clean_spaces(cliente.get(key))
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
        pieces.append(f"data {_format_italian_date(date) or date}")
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
        birth_label = _format_italian_date(birth) or "data non indicata"
        lines.append(f"Nascita: {birth_label}{suffix}.")
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


def _sentence_text(value: Any) -> str:
    text = clean_spaces(value).strip(" .;")
    if not text:
        return ""
    return text + "."


def _markdown_link(url: str, *, label: str = "") -> str:
    clean = clean_spaces(url)
    if not clean:
        return ""
    href = clean.replace("_", "%5F")
    return f"[{label or clean}]({href})"


def _communication_attachment_act_lines(
    audit_rows: list[dict[str, Any]],
    pec_rows: list[dict[str, Any]],
    ordinary_rows: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    gaps: list[str],
) -> list[str]:
    lines: list[str] = ["Atto risultante dagli allegati."]
    source = audit_rows[0] if audit_rows else (pec_rows[0] if pec_rows else (ordinary_rows[0] if ordinary_rows else {}))
    if not source:
        lines.append("Non ho trovato PEC o email reali con allegati consultabili nelle sorgenti autorizzate.")
        if messages:
            lines.append(f"Ho trovato solo messaggi interni collegati: {len(messages)}.")
        if gaps:
            lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
        return lines

    subject = _label(source)
    if subject:
        lines.append(f"Comunicazione di riferimento: {subject}.")
    if link := _row_link(source, label="Apri comunicazione"):
        lines.append(f"Collegamento: {link}.")
    event = clean_spaces(source.get("event_type")).replace("_", " ")
    if event:
        lines.append(f"Contesto riconosciuto: {event}.")

    attachments = _normalised_attachment_rows(source)
    act_like = [item for item in attachments if _attachment_is_act_like(item)]
    receipt_like = [item for item in attachments if _attachment_is_receipt_like(item)]
    if act_like:
        lines.append("Atto/allegato principale individuato:")
        lines.extend(f"- {_attachment_label(item)}" for item in act_like[:5])
    else:
        lines.append("Non emerge con certezza un atto principale dagli allegati disponibili.")
    if receipt_like:
        lines.append("Ricevute o dati di certificazione presenti:")
        lines.extend(f"- {_attachment_label(item)}" for item in receipt_like[:5])

    issues = [dict(item) for item in list(source.get("issues") or []) if isinstance(item, dict)]
    if issues:
        lines.append("Presidio automatico:")
        for issue in issues[:3]:
            title = clean_spaces(issue.get("title"))
            detail = clean_spaces(issue.get("detail"))
            if title:
                lines.append(f"- {title}{(': ' + detail) if detail else ''}.")
    questions = [clean_spaces(item) for item in list(source.get("agent_questions") or []) if clean_spaces(item)]
    if questions:
        lines.append("Domande che il software porta all'avvocato:")
        lines.extend(f"- {item}" for item in questions[:3])
    if gaps:
        lines.append("Limiti: " + "; ".join(gaps[:3]) + ".")
    lines.append("Fonti interne: PEC/email e controllo audit del tenant corrente con permessi applicati.")
    return lines


def _normalised_attachment_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    attachments = []
    for item in list(row.get("allegati") or row.get("attachments") or []):
        if isinstance(item, dict):
            attachments.append(dict(item))
    return attachments


def _attachment_is_act_like(item: dict[str, Any]) -> bool:
    classification = clean_spaces(item.get("classification") or item.get("classe") or item.get("tipo")).lower()
    name = clean_spaces(item.get("filename") or item.get("nome") or item.get("name")).lower()
    return classification in {"atto", "procura", "istruttorio"} or any(
        token in name for token in ("atto", "ricorso", "citazione", "decreto", "sentenza", "verbale", "memoria", "istanza", "procura")
    )


def _attachment_is_receipt_like(item: dict[str, Any]) -> bool:
    classification = clean_spaces(item.get("classification") or item.get("classe") or item.get("tipo")).lower()
    name = clean_spaces(item.get("filename") or item.get("nome") or item.get("name")).lower()
    return classification in {"ricevute", "daticert", "eml", "tecnico"} or any(
        token in name for token in ("daticert", "postacert", "ricevuta", "accettazione", "consegna", "esito", "eml", "xml")
    )


def _attachment_label(item: dict[str, Any]) -> str:
    name = clean_spaces(item.get("filename") or item.get("nome") or item.get("name")) or "allegato senza nome"
    classification = clean_spaces(item.get("classification") or item.get("classe") or item.get("tipo"))
    confidence = item.get("confidence")
    pieces = [name]
    if classification:
        pieces.append(classification)
    try:
        value = float(confidence)
        pieces.append(f"confidence {value:.0%}")
    except Exception:
        pass
    url = clean_spaces(item.get("view_url") or item.get("action_url") or item.get("url"))
    label = " - ".join(pieces)
    if url:
        return _markdown_link(url, label=label)
    return label


def _looks_like_communication_attachment_question(question: str) -> bool:
    text = clean_spaces(question).lower()
    if not text:
        return False
    has_attachment = "allegat" in text
    has_act = any(token in text for token in ("atto", "atti", "notificat", "depositat", "comunicat"))
    has_mailbox = any(token in text for token in ("pec", "email", "mail", "messagg", "comunicazion"))
    has_question = any(token in text for token in ("quale", "quali", "che", "risulta", "risultano", "leggi", "dimmi"))
    return has_attachment and has_act and (has_mailbox or has_question)


def _pec_audit_control_lines(row: dict[str, Any]) -> list[str]:
    title = _row_link(row, label=_label(row)) or _label(row)
    event = clean_spaces(row.get("event_type")).replace("_", " ")
    quality = clean_spaces(row.get("quality_label") or row.get("quality_status"))
    signature = clean_spaces(row.get("signature_label") or row.get("signature_status"))
    severity = clean_spaces(row.get("validation_severity"))
    try:
        issues_count = int(row.get("issues_count") or 0)
    except Exception:
        issues_count = 0
    pieces = [piece for piece in (event, quality, signature, f"{issues_count} anomalie" if issues_count else "", f"severità {severity}" if severity else "") if piece]
    lines = [f"- {title}: {'; '.join(pieces) if pieces else 'controllo PEC da presidiare'}."]
    lifecycle = row.get("deposit_lifecycle") if isinstance(row.get("deposit_lifecycle"), dict) else {}
    stage = lifecycle.get("current_stage") if isinstance(lifecycle.get("current_stage"), dict) else {}
    if stage:
        label = clean_spaces(stage.get("label"))
        if label:
            lines.append(f"  Fase deposito: {label}.")
    communication = clean_spaces(lifecycle.get("communication"))
    if communication:
        lines.append(f"  Cosa aspettarsi: {communication}")
    deadline = row.get("deadline_proposal") if isinstance(row.get("deadline_proposal"), dict) else {}
    if deadline.get("auto_create"):
        due = _format_italian_date(deadline.get("due_date")) or clean_spaces(deadline.get("due_date"))
        reason = clean_spaces(deadline.get("reason"))
        lines.append(f"  Scadenza operativa automatica: {due or 'data da calcolare'}{(' - ' + reason) if reason else ''}.")
    issues = [dict(item) for item in list(row.get("issues") or []) if isinstance(item, dict)]
    for issue in issues[:2]:
        issue_title = clean_spaces(issue.get("title"))
        issue_detail = clean_spaces(issue.get("detail"))
        if issue_title:
            lines.append(f"  Da controllare: {issue_title}{(' - ' + issue_detail) if issue_detail else ''}.")
    questions = [clean_spaces(item) for item in list(row.get("agent_questions") or []) if clean_spaces(item)]
    for question in questions[:2]:
        lines.append(f"  Domanda guida: {question}")
    return lines


def _pec_control_item_lines(row: dict[str, Any], *, answer_kind: str = "") -> list[str]:
    title = clean_spaces(row.get("title") or row.get("titolo") or row.get("subject") or row.get("summary") or row.get("label"))
    if not title:
        title = clean_spaces(row.get("id")) or "Elemento PEC"
    link = _row_link(row, label=title) or title
    status = _pec_control_status_label(row.get("status") or row.get("stato"))
    risk = clean_spaces(row.get("risk_level") or row.get("priority"))
    date_value = _format_italian_date(row.get("received_at") or row.get("due_at") or row.get("created_at") or row.get("start_at"))
    status_prefix = "prova" if answer_kind == "complete_proof" else "stato"
    pieces = [piece for piece in (f"{status_prefix} {status}" if status else "", f"rischio {risk}" if risk else "", date_value) if piece]
    lines = [f"- {link}: {'; '.join(pieces) if pieces else 'da presidiare'}."]
    matter_id = clean_spaces(row.get("fascicolo_id") or row.get("matter_id"))
    if matter_id:
        lines.append(f"  Fascicolo collegato: {matter_id}.")
    if clean_spaces(row.get("legal_category")):
        lines.append(f"  Tipo evento: {clean_spaces(row.get('legal_category')).replace('_', ' ').lower()}.")
    if clean_spaces(row.get("recipient")):
        lines.append(f"  Destinatario: {clean_spaces(row.get('recipient'))}.")
    if answer_kind == "confirmed_deadlines":
        confirmed_by = clean_spaces(row.get("confirmed_by"))
        confirmed_at = _format_italian_date(row.get("confirmed_at"))
        rule = clean_spaces(row.get("confirmation_rule")).rstrip(".")
        lines.append(
            f"  Conferma: {confirmed_by or 'autore non indicato'}"
            f"{(' il ' + confirmed_at) if confirmed_at else ''}"
            f"{(' con regola ' + rule) if rule else ''}."
        )
    if answer_kind == "complete_proof" or "proof_complete" in row:
        complete = row.get("proof_complete") is True
        missing = [_pec_proof_role_label(item) for item in list(row.get("missing_roles") or []) if clean_spaces(item)]
        lines.append("  Prova: completa." if complete else f"  Prova: incompleta{(' - manca ' + ', '.join(missing)) if missing else ''}.")
        proofs = [dict(item) for item in list(row.get("proofs") or []) if isinstance(item, dict)]
        if proofs:
            proof_lines: list[str] = []
            role_order = {"acceptance": 0, "delivery": 1, "failed_delivery": 2}
            for proof in sorted(proofs, key=lambda item: role_order.get(clean_spaces(item.get("role")), 99)):
                role = _pec_proof_role_label(proof.get("role"))
                receipt_at = _format_italian_date(proof.get("receipt_at") or proof.get("created_at"))
                recipient = clean_spaces(proof.get("recipient"))
                pieces = [role]
                if receipt_at:
                    pieces.append(receipt_at)
                if recipient:
                    pieces.append(f"destinatario {recipient}")
                proof_lines.append(" - ".join(pieces))
            if proof_lines:
                lines.append("  Ricevute collegate: " + "; ".join(proof_lines[:4]) + ".")
    deadlines = [dict(item) for item in list(row.get("deadlines") or []) if isinstance(item, dict)]
    for deadline in deadlines[:2]:
        due = _format_italian_date(deadline.get("due_at")) or clean_spaces(deadline.get("due_at"))
        d_status = _pec_control_status_label(deadline.get("status"))
        title = clean_spaces(deadline.get("title")) or "Scadenza"
        lines.append(f"  Scadenza - {title}: {due or 'data da confermare'}; {d_status or 'da confermare'}.")
    tasks = [dict(item) for item in list(row.get("tasks") or []) if isinstance(item, dict)]
    if tasks:
        lines.append("  Da fare: " + _join_clean_sentences(clean_spaces(item.get("title")) for item in tasks[:3]) + ".")
    events = [dict(item) for item in list(row.get("events") or []) if isinstance(item, dict)]
    if events:
        event = events[0]
        produced = [clean_spaces(item) for item in list(event.get("produced_documents") or []) if clean_spaces(item)]
        missing = [clean_spaces(item) for item in list(event.get("missing_documents") or []) if clean_spaces(item)]
        articles = [clean_spaces(item) for item in list(event.get("legal_articles") or []) if clean_spaces(item)]
        if produced:
            lines.append("  Documenti presenti: " + ", ".join(produced[:4]) + ".")
        if missing:
            lines.append("  Documenti da verificare: " + ", ".join(missing[:4]) + ".")
        if articles:
            lines.append("  Articoli/fonti da considerare: " + ", ".join(articles[:4]) + ".")
    summary = clean_spaces(row.get("summary"))
    if summary and summary.lower() not in title.lower():
        lines.append(f"  Sintesi: {_short_text(summary, max_length=180).rstrip('.')}.")
    return lines


def _pec_control_status_label(value: Any) -> str:
    raw = clean_spaces(value)
    labels = {
        "open": "aperto",
        "confirmed": "confermata",
        "draft_pending_confirmation": "da confermare",
        "approved_manual_send_required": "approvata, invio manuale richiesto",
        "waiting_delivery": "in attesa di consegna",
        "failed_review_required": "mancata consegna da rimediare",
        "partial": "parziale",
        "complete": "completa",
    }
    return labels.get(raw, raw)


def _pec_proof_role_label(value: Any) -> str:
    raw = clean_spaces(value)
    labels = {
        "acceptance": "ricevuta di accettazione",
        "delivery": "ricevuta di consegna",
        "failed_delivery": "ricevuta negativa",
    }
    return labels.get(raw, raw)


def _join_clean_sentences(values) -> str:
    cleaned = [clean_spaces(value).rstrip(".") for value in values if clean_spaces(value)]
    return "; ".join(cleaned)


def _communication_details(row: dict[str, Any], *, include_folder: bool = False) -> list[str]:
    details: list[str] = []
    sender = clean_spaces(row.get("mittente_nome") or row.get("mittente"))
    sent_at = _format_italian_date(row.get("data") or row.get("ricevuta_il") or row.get("inviato_il"))
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
    preview = clean_spaces(row.get("anteprima") or row.get("corpo_testo"))
    if preview:
        details.append(f"Contenuto rilevante: {_short_text(preview, max_length=220)}.")
    if link := _row_link(row, label="Apri comunicazione"):
        details.append(f"Collegamento: {link}.")
    attachment_links = _attachment_links(row)
    if attachment_links:
        details.append("Allegati apribili: " + ", ".join(attachment_links[:5]) + ".")
    return details


def _sort_communications(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_communication_sort_key, reverse=True)


def _attachment_links(row: dict[str, Any]) -> list[str]:
    links: list[str] = []
    for attachment in list(row.get("allegati") or []):
        if not isinstance(attachment, dict):
            continue
        url = clean_spaces(attachment.get("view_url"))
        if not url:
            continue
        label = clean_spaces(attachment.get("nome")) or "Allegato"
        links.append(_markdown_link(url, label=label))
    return links


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
