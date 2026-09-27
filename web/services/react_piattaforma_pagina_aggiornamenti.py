"""Pagina «Aggiornamenti legali» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/aggiornamenti-legali/` (rotta `dashboard`,
modello `admin/legal_updates_dashboard.html`): indicatori del motore,
conversione da letture a schede, qualità delle fonti, mappa operativa, presidi,
fonti monitorate, coda revisioni, ultime notizie, ultimi documenti letti e
archivio strutturato. Le tre azioni (`/esegui/scan`, `/esegui/autopublish`,
`/esegui/cleanup`) chiamano `run_legal_update_action` come la rotta storica.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_aggiornamenti_comune import (
    INDIRIZZI,
    TONI_STATO_REVISIONE,
    azione_motore,
    collegamenti,
    confidenza,
    data,
    esegui_motore,
    etichetta_classificazione,
    etichetta_stato,
    leggibile,
    motore,
    superficie,
    unisci,
)
from web.services.react_piattaforma_sezioni import (
    _t,
    actions,
    data_ora,
    esito,
    facts,
    link,
    metrics,
    notes,
    shortcuts,
    status,
    table,
)

# Il servizio qualità fonti usa due etichette inglesi: si mostrano in italiano.
CLASSI_QUALITA = {"verde_abilitata": ("Attiva", "success"), "osservazione": ("In osservazione", "warning"), "rag_only": ("Solo ricerca (RAG)", "info")}
POLITICHE = {"guarded": "Pubblicazione presidiata", "no_publish": "Non pubblica", "blocked": "Bloccata"}
CLASSI_FIDUCIA = {"A": "success", "B": "info"}


def costruisci() -> dict[str, Any]:
    """Gli stessi passi della rotta storica `dashboard`."""
    return superficie(motore())


def _tono_conteggio(valore: Any, tono: str) -> str:
    try:
        return tono if int(valore or 0) else "success"
    except (TypeError, ValueError):
        return "neutral"


def _indicatori(p: dict[str, Any]) -> dict[str, Any]:
    h, v, arch = p.get("headline") or {}, p.get("truth_metrics") or {}, p.get("official_archives") or {}
    normattiva, gazzetta = arch.get("normattiva") or {}, arch.get("gazzetta") or {}
    return metrics([
        {"label": "Fonti monitorate", "value": h.get("sources", 0), "note": "Canali governati dal superamministratore"},
        {"label": "Documenti letti", "value": h.get("raw_documents", 0), "note": "Letti dalle fonti, non tutti già usabili"},
        {"label": "Evidenze lette", "value": h.get("web_evidence", 0), "note": "Pagine e allegati già collaudati per Ricerca legale e Lex"},
        {"label": "PDF e allegati", "value": h.get("web_evidence_attachments", 0), "note": "Allegati ufficiali seguiti, letti o messi in coda OCR"},
        {"label": "Documenti analizzati", "value": v.get("documents_analyzed", 0), "note": "Letture già passate dalla classificazione"},
        {"label": "Da verificare", "value": h.get("review_pending", 0), "note": "Elementi da non usare senza controllo", "tone": _tono_conteggio(h.get("review_pending"), "warning")},
        {"label": "Notizie in Ricerca legale", "value": h.get("published_news", 0), "note": "Aggiornamenti pubblicati negli studi", "tone": "info"},
        {"label": "Scartati", "value": v.get("discarded", 0), "note": "Duplicati o contenuti fuori perimetro già chiusi", "tone": _tono_conteggio(v.get("discarded"), "danger")},
        {"label": "Schede pubblicate", "value": v.get("published_cards", 0), "note": "Consultabili in Ricerca legale, Notizie e Archivio"},
        {"label": "Indice Normattiva", "value": normattiva.get("documents", 0), "note": f"{_t(normattiva.get('articles', 0))} articoli interrogabili dalla ricerca", "tone": "success"},
        {"label": "Indice Gazzetta", "value": gazzetta.get("documents", 0), "note": f"{_t(gazzetta.get('chunks', 0))} estratti interrogabili dalla ricerca", "tone": "success"},
    ])


def _conversione(p: dict[str, Any]) -> list[dict[str, Any]]:
    h, v = p.get("headline") or {}, p.get("truth_metrics") or {}
    percentuale = _t(v.get("conversion_rate", 0)).replace(".", ",")
    return [
        metrics([
            {"label": "Documenti letti", "value": v.get("documents_read", 0)},
            {"label": "Analizzati", "value": v.get("documents_analyzed", 0)},
            {"label": "Con testo fonte o PDF", "value": h.get("web_evidence_verified", 0)},
            {"label": "Allegati collegati", "value": h.get("documents_with_attachments", 0)},
            {"label": "Schede pubblicate", "value": v.get("published_cards", 0)},
            {"label": "Da verificare", "value": v.get("to_verify", 0)},
            {"label": "Scartati", "value": v.get("discarded", 0)},
        ], title=f"Conversione da letture a schede · {percentuale}%"),
        notes("Conversione da letture a schede", [f"{_t(v.get('conversion_label'))}. Le letture sono materiale di lavorazione; diventano schede solo dopo analisi, verifica e pubblicazione."], tone="info"),
    ]


def _qualita(p: dict[str, Any]) -> list[dict[str, Any]]:
    cruscotto = p.get("source_quality_dashboard") or {}
    t = cruscotto.get("totals") or {}
    righe = []
    for fonte in (cruscotto.get("rows") or [])[:8]:
        classe, tono = CLASSI_QUALITA.get(_t(fonte.get("classification")), (_t(fonte.get("classification_label")), ""))
        righe.append({
            "source": unisci(fonte.get("source_name"), fonte.get("last_error")),
            "class": unisci(classe, POLITICHE.get(_t(fonte.get("publication_policy")), fonte.get("publication_policy_label"))),
            "checked": data_ora(fonte.get("last_check_at")) or "mai",
            "signals": f"OCR {_t(fonte.get('ocr_failed'))} · allegati vuoti {_t(fonte.get('empty_attachments'))} · riferimenti {_t(fonte.get('missing_references'))} · domande {_t(fonte.get('missing_questions'))}",
            "reviews": f"{_t(fonte.get('review_pending'))} in verifica · {_t(fonte.get('guarded_publications'))} pubblicazioni presidiate",
            "_tone": "danger" if _t(fonte.get("last_error")) else tono,
        })
    return [
        metrics([
            {"label": "Fonti attive", "value": t.get("fonti_attive", 0)},
            {"label": "In osservazione", "value": t.get("fonti_in_osservazione", 0)},
            {"label": "Solo ricerca (RAG)", "value": t.get("fonti_rag_only", 0)},
            {"label": "Non pubblicabili", "value": t.get("fonti_non_pubblicabili", 0)},
            {"label": "Errori", "value": t.get("errors", 0), "tone": _tono_conteggio(t.get("errors"), "danger")},
            {"label": "OCR falliti", "value": t.get("ocr_failed", 0), "tone": _tono_conteggio(t.get("ocr_failed"), "danger")},
            {"label": "Allegati vuoti", "value": t.get("empty_attachments", 0), "tone": _tono_conteggio(t.get("empty_attachments"), "warning")},
            {"label": "Riferimenti mancanti", "value": t.get("missing_references", 0), "tone": _tono_conteggio(t.get("missing_references"), "warning")},
            {"label": "Domande mancanti", "value": t.get("missing_questions", 0), "tone": _tono_conteggio(t.get("missing_questions"), "warning")},
            {"label": "Pubblicazioni presidiate", "value": t.get("guarded_publications", 0)},
        ], title="Qualità delle fonti · regime controllato"),
        table(
            "Qualità delle fonti",
            [("source", "Fonte"), ("class", "Classe"), ("checked", "Ultimo controllo"), ("signals", "Segnali di qualità"), ("reviews", "Revisioni")],
            righe,
            subtitle="Le prime otto fonti del cruscotto qualità.",
            empty="Nessuna fonte censita.",
        ),
    ]


def _mappa_e_presidi(p: dict[str, Any]) -> list[dict[str, Any]]:
    qualita = p.get("quality") or {}
    duplicati = qualita.get("duplicates") or {}
    ciclo = p.get("progressive_scheduler") or {}
    finestra = _t(qualita.get("auto_publish_window"))
    return [
        status("Dove finiscono i dati", [
            {"title": "1. Fonti", "summary": "Elenco dei canali ufficiali o istituzionali da cui parte il monitoraggio.", "status": "info", "statusLabel": "Passo 1"},
            {"title": "2. Acquisizione", "summary": "Materiale letto dalle fonti: è inventario di lavorazione, non ancora scheda citabile.", "status": "info", "statusLabel": "Passo 2"},
            {"title": "3. Verifica", "summary": "Qui restano gli elementi con fonte, materia o utilità non abbastanza chiari.", "status": "info", "statusLabel": "Passo 3"},
            {"title": "4. Ricerca legale", "summary": "Risultati consultabili dallo studio, con contesto, fonte originale e azioni reali.", "status": "ok", "statusLabel": "Passo 4"},
        ], subtitle="Mappa operativa del ciclo delle fonti."),
        shortcuts("Sezioni del motore", [
            ("Fonti", "Catalogo dei canali monitorati", INDIRIZZI["fonti"]),
            ("Acquisizione", "Documenti letti dalle fonti", INDIRIZZI["acquisizione"]),
            ("Catalogazione", "Classificazione e decisione operativa", INDIRIZZI["catalogazione"]),
            ("Coda revisioni", "Proposte da verificare", INDIRIZZI["revisione"]),
            ("Archivio", "Normative, giurisprudenza, prassi, notizie e registro", INDIRIZZI["archivio"]),
        ]),
        status("Presidi del motore", [
            {"title": "Controllo ripetizioni", "summary": "Prima di creare una proposta il motore confronta titolo, fonte, numero, anno, autorità e collegamenti ufficiali con l'archivio già pubblicato.", "detail": f"Elementi da accorpare: {_t(duplicati.get('duplicate_items', 0))} · gruppi rilevati: {_t(duplicati.get('groups', 0))}", "status": "info", "statusLabel": "attivo"},
            {"title": "Ricerca notturna", "summary": f"Lo scheduler automatico lavora nella fascia {finestra} e nel passo 1 usa solo le fonti verdi già confermate.", "detail": f"Fonti del passo 1: {', '.join(_t(c) for c in ciclo.get('enabled_source_codes') or [])} · {_t(ciclo.get('source_budget'))} fonti per ciclo, {_t(ciclo.get('publish_max_items'))} pubblicazioni massime, pubblicazione presidiata", "status": "info", "statusLabel": finestra},
            {"title": "Perimetro utile", "summary": "Entrano in archivio solo norme, pronunce, prassi e notizie istituzionali riconducibili a materie di lavoro dello studio legale.", "detail": f"Regola attiva: {_t(qualita.get('auto_publish_scope'))}", "status": "info", "statusLabel": "regola"},
        ]),
    ]


def _fonti_e_presidio(p: dict[str, Any]) -> list[dict[str, Any]]:
    arch, runtime = p.get("official_archives") or {}, p.get("runtime") or {}
    normattiva, gazzetta = arch.get("normattiva") or {}, arch.get("gazzetta") or {}
    fonti = p.get("sources") or []
    return [
        table(
            f"Fonti monitorate ({len(fonti)} fonti)",
            [("name", "Fonte"), ("trust", "Classe"), ("category", "Categoria"), ("polling", "Frequenza"), ("checked", "Ultimo controllo")],
            [{
                "name": unisci(s.get("name"), s.get("base_url")),
                "trust": s.get("trust_class"),
                "category": leggibile(s.get("category")),
                "polling": f"{_t(s.get('polling_minutes'))} min",
                "checked": data_ora(s.get("last_check_at")) or "mai",
                "_href": _t(s.get("base_url")),
                "_external": True,
                "_tone": CLASSI_FIDUCIA.get(_t(s.get("trust_class")).upper(), ""),
            } for s in fonti],
            empty="Nessuna fonte censita.",
        ),
        facts("Presidio operativo · pubblicazione automatica", [
            ("Perimetro", "Condiviso da tutti gli studi"),
            ("Archivio operativo", "Pronto e condiviso"),
            ("Archivio aggiornamenti", "Controllo ripetizioni attivo"),
            ("Archivio Normattiva", f"{_t(normattiva.get('documents', 0))} documenti, {_t(normattiva.get('chunks', 0))} estratti"),
            ("Archivio Gazzetta", f"{_t(gazzetta.get('documents', 0))} uscite, {_t(gazzetta.get('chunks', 0))} estratti"),
            ("Lettura assistente", "Attiva sull'archivio legale condiviso"),
            ("Esportazione amministrativa", "pronta per i report interni" if runtime.get("json_export_enabled") else "disattivata nel ciclo operativo"),
            ("Catalogazione assistita", "servizio locale attivo" if runtime.get("ollama_model") else "regole interne attive"),
            ("Archivio giurisprudenza storico", "copia di compatibilità attiva" if runtime.get("giurisprudenza_json_mirror_enabled") else "disattivato: le pubblicazioni restano nell'archivio condiviso"),
        ]),
    ]


def _ultimi(p: dict[str, Any]) -> list[dict[str, Any]]:
    h = p.get("headline") or {}
    return [
        table(
            "Coda revisioni",
            [("title", "Proposta"), ("state", "Stato"), ("detail", "Classificazione, fonte e confidenza")],
            [{
                "title": r.get("title"),
                "state": etichetta_stato(r.get("status")),
                "detail": unisci(etichetta_classificazione(r.get("classification_type")), r.get("source_name"), f"confidenza {confidenza(r.get('confidence_score'))}"),
                "_href": INDIRIZZI["revisione"],
                "_tone": TONI_STATO_REVISIONE.get(_t(r.get("status")).lower(), ""),
            } for r in (p.get("review_queue") or [])[:6]],
            empty="Nessuna proposta in coda al momento.",
        ),
        table(
            "Ultime notizie pubblicate",
            [("title", "Notizia"), ("kind", "Tipo e materia"), ("summary", "Sintesi")],
            [{"title": n.get("title"), "kind": unisci(leggibile(n.get("news_type")), n.get("matter_name") or "materia da verificare"), "summary": n.get("short_summary")} for n in (p.get("news") or [])[:6]],
            empty="Nessuna notizia pubblicata.",
        ),
        table(
            "Ultimi documenti letti",
            [("title", "Documento"), ("state", "Stato"), ("detail", "Fonte, classificazione e data")],
            [{
                "title": d.get("title"),
                "state": etichetta_stato(d.get("review_status")) if _t(d.get("review_status")) else "",
                "detail": unisci(d.get("source_name"), etichetta_classificazione(d.get("classification_type") or "INCERTO"), data(d.get("published_at"))),
                "_href": f"{INDIRIZZI['acquisizione']}/{_t(d.get('id'))}",
            } for d in (p.get("raw_documents") or [])[:6]],
            empty="Nessun documento letto.",
        ),
        metrics([
            {"label": "Normative", "value": h.get("published_normative", 0)},
            {"label": "Giurisprudenza", "value": h.get("published_jurisprudence", 0)},
            {"label": "Prassi", "value": h.get("published_prassi", 0)},
            {"label": "Eventi del registro", "value": len(p.get("audit") or [])},
        ], title="Archivio strutturato"),
    ]


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    qualita = payload.get("quality") or {}
    duplicati = qualita.get("duplicates") or {}
    return {
        "title": "Motore di aggiornamento normativo e giurisprudenziale",
        "subtitle": "Controlla l'archivio, scarta le ripetizioni e rende consultabili solo gli aggiornamenti con fonte e contesto leggibili.",
        "links": [
            link("Coda revisioni", INDIRIZZI["revisione"], tone="primary"),
            *collegamenti("cruscotto"),
            link("Notizie in Ricerca legale", "/legal-intelligence/news", external=True),
            link("Ricerca legale", "/ricerca-legale", external=True),
        ],
        "sections": [
            actions("Comandi del motore", [azione_motore("scan"), azione_motore("autopublish"), azione_motore("cleanup")], subtitle="Le stesse operazioni della console storica: ricerca nelle fonti verdi, pubblicazione presidiata e pulizia dei duplicati."),
            notes("Archivio legale condiviso da tutti gli studi", [
                "Questa è la cabina tecnica del ciclo fonti. I numeri grandi sono indici e passaggi di lavorazione; le schede usabili dall'avvocato finiscono in Ricerca legale, Notizie, Giurisprudenza e Archivio.",
                f"Finestra automatica: {_t(qualita.get('auto_publish_window'))} · duplicati rilevati: {_t(duplicati.get('duplicate_items', 0))}.",
            ], tone="info"),
            _indicatori(payload),
            *_conversione(payload),
            *_qualita(payload),
            *_mappa_e_presidi(payload),
            *_fonti_e_presidio(payload),
            *_ultimi(payload),
        ],
    }


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    if chiave in {"scan", "autopublish", "cleanup"}:
        return esegui_motore(chiave)
    return esito(False, "Azione non disponibile in questa pagina.")


AZIONI = {"scan", "autopublish", "cleanup"}

__all__ = ["AZIONI", "adatta", "costruisci", "esegui"]
