"""Deterministic query router for operational Lex requests."""

from __future__ import annotations

import re
from typing import Any

from .models import OperationalRoute
from .serializers import clean_spaces

ACTION_BLOCK_TOKENS = (
    "invia pec",
    "manda pec",
    "deposita",
    "effettua deposito",
    "firma digitalmente",
    "paga",
    "emetti fattura",
    "cancella",
    "elimina",
)

OFFICIAL_SOURCE_LOOKUP_TOKENS = (
    "allegato ufficiale",
    "allegato della questione",
    "allegato collegato",
    "questione penale",
    "questione civile",
    "ordinanza di rimessione",
    "corte di cassazione",
    "cassazione",
    "qsp",
    "contentid=",
    "r.g.",
    "rg ",
    "fonte ufficiale",
    "fonti ufficiali",
)

ENTITY_STOPWORDS = {
    "a",
    "ad",
    "al",
    "alla",
    "allo",
    "ai",
    "agli",
    "alle",
    "con",
    "ci",
    "cerca",
    "cliente",
    "clienti",
    "codice",
    "completo",
    "conferimento",
    "contesto",
    "controllare",
    "controlli",
    "dai",
    "dammi",
    "dati",
    "database",
    "da",
    "db",
    "de",
    "devo",
    "del",
    "dell",
    "della",
    "delle",
    "dello",
    "dei",
    "di",
    "deposito",
    "documenti",
    "domani",
    "dimmi",
    "cosa",
    "email",
    "editor",
    "economico",
    "aperti",
    "aperte",
    "fammi",
    "fascicolo",
    "fascicoli",
    "gli",
    "guardare",
    "ha",
    "ho",
    "i",
    "il",
    "incarico",
    "la",
    "le",
    "lo",
    "l'ultima",
    "l'ultime",
    "l'ultimo",
    "l'ultimi",
    "mancano",
    "memoria",
    "messaggi",
    "mi",
    "manca",
    "mostra",
    "mostrami",
    "nel",
    "nella",
    "nelle",
    "nello",
    "nei",
    "oggi",
    "operativa",
    "operativo",
    "ordinaria",
    "parte",
    "parti",
    "per",
    "pec",
    "posta",
    "professionale",
    "pratica",
    "prepara",
    "preparami",
    "precedente",
    "preventivo",
    "prossimi",
    "passi",
    "priorita",
    "priorità",
    "quadro",
    "qual",
    "quale",
    "quali",
    "questa",
    "queste",
    "questi",
    "questo",
    "recapiti",
    "riepilogo",
    "riepiloga",
    "riassumi",
    "rispondi",
    "rispondere",
    "risposta",
    "risulta",
    "risultano",
    "collegata",
    "collegate",
    "collegati",
    "collegato",
    "ricevuta",
    "ricevute",
    "ricevuti",
    "rischi",
    "scheda",
    "scadenza",
    "scadenze",
    "settimana",
    "situazione",
    "sintesi",
    "sono",
    "soggetto",
    "soggetti",
    "scrivi",
    "studio",
    "notificato",
    "notificata",
    "notificati",
    "notificate",
    "depositato",
    "depositata",
    "depositati",
    "depositate",
    "comunicato",
    "comunicata",
    "comunicati",
    "comunicate",
    "allegato",
    "allegati",
    "allegata",
    "allegate",
    "negli",
    "trovami",
    "trova",
    "template",
    "modello",
    "modelli",
    "un",
    "una",
    "usa",
    "verifica",
    "verificare",
    "ultima",
    "ultime",
    "ultimo",
    "ultimi",
    "urgenti",
    "redigi",
    "tutto",
    "chi",
    "è",
    "e",
    "assistito",
    "assistiti",
    "controparte",
    "controparti",
}


def _is_official_source_lookup_text(text: str) -> bool:
    clean = clean_spaces(text).lower()
    if not clean:
        return False
    if any(token in clean for token in OFFICIAL_SOURCE_LOOKUP_TOKENS):
        return True
    return re.search(r"\br\.?\s*g\.?\s*(?:n\.?\s*)?\d{1,7}/\d{4}\b", clean) is not None and any(
        token in clean for token in ("questione", "cassazione", "ordinanza", "allegato")
    )


class OperationalQueryRouter:
    def route(self, question: str, *, metadata: dict[str, Any] | None = None) -> OperationalRoute | None:
        text = clean_spaces(question).lower()
        metadata = dict(metadata or {})
        focus_topic = clean_spaces(metadata.get("focus_topic") or metadata.get("module")).lower()

        if not text:
            return None
        if _contains_action_block_token(text):
            return OperationalRoute(
                "blocked_legal_action",
                "execute_legal_action",
                (),
                blocks_legal_action=True,
                reason="La richiesta sembra chiedere un'azione dispositiva, non una consultazione.",
            )

        entity_query = self._entity_query(text)
        if (
            any(
                token in text
                for token in (
                    "contesto studio",
                    "database studio",
                    "db studio",
                    "ricerca studio",
                    "memoria studio",
                    "quadro studio",
                    "situazione studio",
                )
            )
            or ("tutto il contesto" in text and "studio" in text)
        ):
            return OperationalRoute(
                "studio_context_overview",
                "studio_context_overview",
                (
                    "clienti",
                    "fascicoli",
                    "scadenziario",
                    "agenda",
                    "email_pec",
                    "email_ordinaria",
                    "preventivi",
                    "conferimenti",
                    "pagamenti",
                ),
                entity_query,
            )
        if "quali fonti" in text or "fonti hai usato" in text or text in {"fonti", "mostra fonti"}:
            return OperationalRoute("sources_overview", "sources_overview", ("clienti", "fascicoli", "fonti_ufficiali"), entity_query)

        if any(token in text for token in ("timeline", "cronologia", "linea del tempo")) and (
            "fascicol" in text or "pratica" in text or focus_topic == "fascicoli"
        ):
            return OperationalRoute(
                "build_case_timeline",
                "build_case_timeline",
                (
                    "fascicoli",
                    "documenti_fascicolo",
                    "scadenziario",
                    "agenda",
                    "email_pec",
                    "email_ordinaria",
                    "messaggi",
                    "fatturazione",
                    "pagamenti",
                ),
                entity_query,
            )

        if _looks_like_communication_attachment_question(text):
            return OperationalRoute(
                "communications_lookup",
                "communications_lookup",
                ("email_pec", "pec_audit", "email_ordinaria", "messaggi"),
                entity_query,
            )

        if any(token in text for token in ("messagg", "pec", "email", "posta ordinaria")):
            sources = ["clienti", "fascicoli", "messaggi"]
            if "pec" in text:
                sources.append("email_pec")
                if any(
                    token in text
                    for token in (
                        "deposit",
                        "controll",
                        "valid",
                        "firma",
                        "firme",
                        "audit",
                        "mime",
                        "notific",
                        "cancelleria",
                        "giudice di pace",
                        "d.l. 179",
                    )
                ):
                    sources.append("pec_audit")
            if "posta ordinaria" in text or "email ordinaria" in text or "smtp" in text or "imap" in text:
                sources.append("email_ordinaria")
            if ("email" in text or "posta" in text) and not {"email_pec", "email_ordinaria"}.intersection(sources):
                sources.extend(["email_pec", "email_ordinaria"])
            if _looks_like_communication_draft(text):
                return OperationalRoute("draft_communication", "draft_communication", tuple(dict.fromkeys(sources)), entity_query)
            return OperationalRoute("communications_lookup", "communications_lookup", tuple(dict.fromkeys(sources)), entity_query)

        if any(token in text for token in ("cliente", "anagrafica", "recapiti", "situazione di", "situazione del")) or focus_topic == "clienti":
            if "fascicol" in text:
                return OperationalRoute("client_fascicoli", "client_fascicoli", ("clienti", "fascicoli"), entity_query)
            if "quadro economico" in text or any(token in text for token in ("parcelle", "fatture", "saldo", "incassi")):
                return OperationalRoute(
                    "client_economic_summary",
                    "client_economic_summary",
                    ("clienti", "preventivi", "conferimenti", "fatturazione", "pagamenti", "timesheet"),
                    entity_query,
                )
            return OperationalRoute(
                "client_situation",
                "client_situation",
                ("clienti", "fascicoli", "scadenziario", "agenda", "preventivi", "conferimenti", "fatturazione", "pagamenti"),
                entity_query,
            )

        if any(token in text for token in ("soggett", "parte", "parti", "controparte", "controparti", "assistito")):
            return OperationalRoute("soggetti_lookup", "soggetti_lookup", ("soggetti", "fascicoli"), entity_query)

        if any(token in text for token in ("scadenz", "termine", "urgenti", "questa settimana", "oggi", "domani")):
            sources = ("scadenziario", "agenda")
            if "fascicolo" in text:
                sources = ("fascicoli", "scadenziario", "agenda")
            elif "cliente" in text:
                sources = ("clienti", "fascicoli", "scadenziario", "agenda")
            return OperationalRoute("deadlines_overview", "deadlines_overview", sources, entity_query)

        if any(token in text for token in ("agenda", "appuntamenti", "udienze", "calendario")):
            return OperationalRoute("agenda_overview", "agenda_overview", ("agenda",), entity_query)

        if "notific" in text:
            return OperationalRoute("notifications_lookup", "notifications_lookup", ("notifiche",), entity_query)

        if any(token in text for token in ("tariffario", "compenso", "onorario", "scaglione")):
            return OperationalRoute("tariffario_lookup", "tariffario_lookup", ("tariffario",), entity_query)

        if "preventiv" in text:
            return OperationalRoute("preventivo_summary", "preventivo_summary", ("preventivi", "conferimenti", "tariffario"), entity_query)

        if "conferimento" in text or "incarico" in text:
            return OperationalRoute("conferimento_summary", "conferimento_summary", ("conferimenti", "preventivi", "fascicoli"), entity_query)

        if any(token in text for token in ("fattur", "parcell", "incass", "pagament", "quadro economico")):
            return OperationalRoute("billing_summary", "billing_summary", ("fatturazione", "preventivi", "conferimenti", "pagamenti", "timesheet"), entity_query)

        if _is_official_source_lookup_text(text):
            return OperationalRoute("official_sources_lookup", "official_sources_lookup", ("fonti_ufficiali", "legal_intelligence", "update_intelligence"), entity_query)

        if any(token in text for token in ("template", "modello atto", "modelli atto", "editor", "redazione", "bozza", "atto professionale")):
            return OperationalRoute("template_lookup", "template_lookup", ("template_atti", "editor_ai", "fascicoli", "documenti_fascicolo"), entity_query)

        if any(token in text for token in ("document", "atto", "atti", "mancano", "riassumi gli ultimi")):
            return OperationalRoute("documenti_fascicolo", "documenti_fascicolo", ("fascicoli", "documenti_fascicolo", "template_atti"), entity_query)

        if any(token in text for token in ("attivita", "timesheet", "lavoro svolto", "non fatturat")):
            return OperationalRoute("unbilled_activity", "unbilled_activity", ("timesheet", "fatturazione", "fascicoli"), entity_query)

        if any(token in text for token in ("update normativ", "aggiornamenti normativ", "novita normative", "legal intelligence")):
            return OperationalRoute(
                "legal_update_overview",
                "legal_update_overview",
                ("legal_intelligence", "update_intelligence", "fonti_ufficiali"),
                entity_query,
            )

        if any(token in text for token in ("normativa", "giurisprudenza", "fonti ufficiali", "normattiva", "gazzetta")):
            return OperationalRoute("official_sources_lookup", "official_sources_lookup", ("fonti_ufficiali", "legal_intelligence", "update_intelligence"), entity_query)

        if "fascicolo" in text or "pratica" in text or focus_topic == "fascicoli":
            return OperationalRoute(
                "fascicolo_summary",
                "fascicolo_summary",
                ("fascicoli", "documenti_fascicolo", "scadenziario", "agenda", "preventivi", "conferimenti", "fatturazione", "pagamenti", "timesheet"),
                entity_query,
            )

        return None

    def _entity_query(self, text: str) -> str:
        value = re.sub(r"[^\w'./ -]+", " ", text, flags=re.UNICODE)
        tokens = [
            token
            for token in clean_spaces(value).lower().split()
            if token not in ENTITY_STOPWORDS and len(token) > 1
        ]
        return clean_spaces(" ".join(tokens))


def _contains_action_block_token(text: str) -> bool:
    for token in ACTION_BLOCK_TOKENS:
        clean = clean_spaces(token).lower()
        if not clean:
            continue
        if " " in clean:
            if clean in text:
                return True
            continue
        if re.search(rf"(^|[^\w]){re.escape(clean)}([^\w]|$)", text, flags=re.UNICODE):
            return True
    return False


def _looks_like_communication_draft(text: str) -> bool:
    if not any(token in text for token in ("pec", "email", "posta", "messaggio")):
        return False
    return any(token in text for token in ("scrivi", "redigi", "prepara", "bozza", "risposta", "rispondi"))


def _looks_like_communication_attachment_question(text: str) -> bool:
    if not text:
        return False
    has_attachment = "allegat" in text
    has_act = any(token in text for token in ("atto", "atti", "notificat", "depositat", "comunicat"))
    has_mailbox = any(token in text for token in ("pec", "email", "mail", "messagg", "comunicazion"))
    has_question = any(token in text for token in ("quale", "quali", "che", "risulta", "risultano", "leggi", "dimmi"))
    return has_attachment and has_act and (has_mailbox or has_question)
