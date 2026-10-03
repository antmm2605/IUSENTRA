"""Diagnosi di Lex sulle domande di prova (eseguita DENTRO il container, nessuna chiamata al modello).

Uso sul server:
    cd /opt/iusentra/repo/deploy/hetzner
    sudo docker compose --env-file /opt/iusentra/.env.hetzner -f docker-compose.hetzner.yml \
        exec -T app python - < diagnosi_lex_domande.py
    # domande proprie: ... exec -T app python - "Prima domanda?" "Seconda domanda?" < diagnosi_lex_domande.py

Per ogni domanda: classificazione, tema della conversazione, percorso scelto, fonti previste e i primi
risultati dell'archivio Normattiva con la pertinenza (quelli con «scartato» non arrivano al modello).
"""

from __future__ import annotations

import sys
import time

DOMANDE = [
    "Scrivi tre frasi sull'organizzazione della giornata lavorativa con le pause",
    "Qual è il termine per proporre appello contro una sentenza civile?",
    "Quali sono gli elementi della responsabilità extracontrattuale?",
    "Entro quanto si propone opposizione a decreto ingiuntivo?",
    "Quando si prescrive il risarcimento del danno da fatto illecito?",
    "Entro quale termine va presentata la querela?",
]


def main() -> int:
    sys.path.insert(0, "/app")
    from lex.contracts import LexRequest
    from lex.http_bounded_bridge import _resolve_intent, _resolve_workflow_hint
    from lex.research.request_profile import classify_request
    from lex.retrieval.official_sources_retriever import search_normattiva
    from lex.retrieval.source_router import SourceRouter
    from lex.ricerca_giuridica.classificatore import classifica_domanda
    from lex.ricerca_giuridica.pertinenza import copertura_termini, e_pertinente
    from web.services.assistente_conversation_focus import resolve_conversation_focus

    domande = [d for d in sys.argv[1:] if d.strip()] or DOMANDE
    for domanda in domande:
        focus = resolve_conversation_focus(domanda, messages=[])
        profilo = classify_request(focus["effective_question"], requested_mode="chat")
        contesto = {"focus_topic": focus["topic"], "effective_question": focus["effective_question"]}
        rp = {"intent": profilo.intent, "source_mode": profilo.source_mode}
        hint = _resolve_workflow_hint(contesto, rp)
        intento = _resolve_intent(domanda, contesto, rp)
        c = classifica_domanda(domanda)
        workflow = hint or {"research_normativa": "normativa", "research_giurisprudenza": "giurisprudenza"}.get(intento, "question_answering")
        richiesta = LexRequest(tenant_id="diagnosi", user_id="diagnosi", session_id="diagnosi", query=domanda)
        fonti = [s.__class__.__name__ for s in SourceRouter().resolve(richiesta, {}, workflow)]
        print(f"\n=== {domanda}")
        print(f"tipo={c.tipo} ricerca={c.tipo_ricerca or '-'} tema={focus['topic'] or '-'} intento={profilo.intent} "
              f"percorso={workflow} ({intento})")
        print("fonti: " + ", ".join(fonti))
        if c.giuridica or workflow in {"normativa", "giurisprudenza"}:
            inizio = time.monotonic()
            righe = search_normattiva(domanda, limit=8)
            ms = int((time.monotonic() - inizio) * 1000)
            print(f"Normattiva ({ms} ms):")
            for r in righe:
                testo = " ".join(str(r.get(k) or "") for k in ("titolo", "testo", "excerpt"))
                meta = r.get("metadata") or {}
                ok = e_pertinente(domanda, testo, riferimento_esatto=bool(r.get("riferimento_esatto")))
                ricerca = r.get("ricerca") or {}
                print(f"  {'ok      ' if ok else 'scartato'} art. {meta.get('article_number') or '?':<6} "
                      f"{str(r.get('titolo') or '')[:60]:<60} punt={r.get('punteggio')} "
                      f"cop={copertura_termini(domanda, testo):.2f} {ricerca.get('modalita', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
