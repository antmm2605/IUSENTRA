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
    "dai",
    "dammi",
    "dati",
    "da",
    "de",
    "del",
    "dell",
    "della",
    "delle",
    "dello",
    "dei",
    "di",
    "documenti",
    "domani",
    "dimmi",
    "email",
    "editor",
    "economico",
    "fascicolo",
    "fascicoli",
    "gli",
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
    "messaggi",
    "mi",
    "mostra",
    "mostrami",
    "nel",
    "nella",
    "nelle",
    "nello",
    "nei",
    "oggi",
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
    "preventivo",
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
    "ricevuta",
    "ricevute",
    "ricevuti",
    "scheda",
    "scadenza",
    "scadenze",
    "settimana",
    "situazione",
    "sono",
    "soggetto",
    "soggetti",
    "trovami",
    "template",
    "modello",
    "modelli",
    "un",
    "una",
    "ultima",
    "ultime",
    "ultimo",
    "ultimi",
    "urgenti",
    "assistito",
    "assistiti",
    "controparte",
    "controparti",
}


class OperationalQueryRouter:
    def route(self, question: str, *, metadata: dict[str, Any] | None = None) -> OperationalRoute | None:
        text = clean_spaces(question).lower()
        metadata = dict(metadata or {})
        focus_topic = clean_spaces(metadata.get("focus_topic") or metadata.get("module")).lower()

        if not text:
            return None
        if any(token in text for token in ACTION_BLOCK_TOKENS):
            return OperationalRoute(
                "blocked_legal_action",
                "execute_legal_action",
                (),
                blocks_legal_action=True,
                reason="La richiesta sembra chiedere un'azione dispositiva, non una consultazione.",
            )

        entity_query = self._entity_query(text)
        if "quali fonti" in text or "fonti hai usato" in text or text in {"fonti", "mostra fonti"}:
            return OperationalRoute("sources_overview", "sources_overview", ("clienti", "fascicoli", "fonti_ufficiali"), entity_query)

        if any(token in text for token in ("messagg", "pec", "email", "posta ordinaria")):
            sources = ["clienti", "fascicoli", "messaggi"]
            if "pec" in text:
                sources.append("email_pec")
            if "posta ordinaria" in text or "email ordinaria" in text or "smtp" in text or "imap" in text:
                sources.append("email_ordinaria")
            if ("email" in text or "posta" in text) and not {"email_pec", "email_ordinaria"}.intersection(sources):
                sources.extend(["email_pec", "email_ordinaria"])
            return OperationalRoute("communications_lookup", "communications_lookup", tuple(dict.fromkeys(sources)), entity_query)

        if any(token in text for token in ("cliente", "anagrafica", "recapiti", "situazione di", "situazione del")) or focus_topic == "clienti":
            if "fascicol" in text:
                return OperationalRoute("client_fascicoli", "client_fascicoli", ("clienti", "fascicoli"), entity_query)
            if "quadro economico" in text or any(token in text for token in ("parcelle", "fatture", "saldo", "incassi")):
                return OperationalRoute(
                    "client_economic_summary",
                    "client_economic_summary",
                    ("clienti", "preventivi", "conferimenti", "fatturazione", "timesheet"),
                    entity_query,
                )
            return OperationalRoute(
                "client_situation",
                "client_situation",
                ("clienti", "fascicoli", "scadenziario", "agenda", "preventivi", "conferimenti", "fatturazione"),
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
            return OperationalRoute("billing_summary", "billing_summary", ("fatturazione", "preventivi", "conferimenti", "timesheet"), entity_query)

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
                ("fascicoli", "documenti_fascicolo", "scadenziario", "agenda", "preventivi", "conferimenti", "fatturazione", "timesheet"),
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
