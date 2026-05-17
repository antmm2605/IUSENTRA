"""Italian response composer for deterministic operational answers."""

from __future__ import annotations

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
        gaps = _unique_strings([gap for result in results for gap in result.coverage_gaps])
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

        answer_lines = self._answer_lines(route, ok_results, gaps)
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

    def _answer_lines(self, route: OperationalRoute, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        if route.intent in {"client_situation", "client_fascicoli", "client_economic_summary"}:
            return self._client_lines(route, results, gaps)
        if route.intent in {"fascicolo_summary", "documenti_fascicolo"}:
            return self._fascicolo_lines(route, results, gaps)
        if route.intent in {"deadlines_overview", "agenda_overview"}:
            return self._calendar_lines(route, results, gaps)
        if route.intent in {"preventivo_summary", "conferimento_summary", "billing_summary", "tariffario_lookup", "unbilled_activity"}:
            return self._economic_lines(route, results, gaps)
        if route.intent in {"legal_update_overview", "official_sources_lookup"}:
            return self._legal_sources_lines(results, gaps)
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
            lines.append(f"Cliente: {_label(cliente)}.")
            contacts = []
            for key, label in (("email", "email"), ("pec", "PEC"), ("telefono", "telefono")):
                if clean_spaces(cliente.get(key)):
                    contacts.append(f"{label} {cliente.get(key)}")
            if contacts:
                lines.append("Recapiti autorizzati: " + "; ".join(contacts) + ".")
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

    def _legal_sources_lines(self, results: list[OperationalToolResult], gaps: list[str]) -> list[str]:
        rows = []
        for source_id in ("legal_intelligence", "update_intelligence", "fonti_ufficiali"):
            rows.extend(_data_for(results, source_id))
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
    for key in ("nome_completo", "titolo", "oggetto", "numero", "nome", "ragione_sociale", "id"):
        value = clean_spaces(row.get(key))
        if value:
            return value
    return "Elemento"


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
