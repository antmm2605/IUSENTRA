"""Passaggi confrontabili delle pagine lette con una domanda comune.

L'inventario completo resta distinto dal sottoinsieme inviato al modello:
non dichiarare lettura semantica integrale quando il contesto è selettivo.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import unquote, urlsplit

from lex.contracts import EvidenceItem
from lex.ricerca_giuridica.testo import termini_indice

_READING_DIRECTIVE_TERMS = frozenset(termini_indice(
    "leggi leggere confronta confrontare queste questi questa questo pagina pagine pubbliche pubblici "
    "indica indicare quali informazioni riesci effettivamente recuperare citando citare separatamente "
    "due link non usare dati studio"
))



def is_plain_source_reading(question: str) -> bool:
    """Solo lettura generica: nessuna domanda di merito o confronto implicito."""
    without_urls = re.sub(r"https?://[^\s<>\'\")\]]+", "", str(question))
    terms = set(termini_indice(without_urls))
    compare_terms = set(termini_indice("confronta confrontare confronto confronti compara comparare sintetizza sintesi fondi fondere"))
    return bool(terms) and not (terms & compare_terms) and not (terms - _READING_DIRECTIVE_TERMS)


def explicit_public_rites(text: str) -> set[str]:
    """Ambiti processuali nominati nel testo, mai ricavati dal percorso URL.

    Recinto della singola lettura pubblica, non un secondo classificatore
    dello studio: riusa le categorie del catalogo fonti esistente.
    """
    from lex.sources.classifier import LEGAL_TOPICS

    clean = re.sub(r"https?://[^\s<>'\")\]]+", "", str(text))
    patterns = {"civile": r"civil[ei]", "penale": r"penal[ei]",
                "amministrativo": r"amministrativ[aoie]", "tributario": r"tributari(?:o|a|e)?"}
    rites = {key for key, pattern in patterns.items()
             if key in LEGAL_TOPICS and re.search(r"\b" + pattern + r"\b", clean, re.I)}
    from lex.ricerca_giuridica.testo import analizza_domanda

    code = analizza_domanda(clean, usa_tesauro=False).codice
    for rite in ("civile", "penale", "amministrativo"):
        if code.endswith("_" + rite):
            rites.add(rite)
    return rites


def explicit_public_remedies(text: str, *, question: bool = False) -> set[str]:
    """Nomi espliciti del quesito: nessun calcolo o nuova regola sui termini."""
    clean = re.sub(r"https?://[^\s<>'\")\]]+", "", str(text))
    patterns = {"appello": r"\bappell[oi]\b", "revocazione": r"\brevocazion[ei]\b",
                "opposizione_terzo": r"\bopposizion[ei]\s+(?:di\s+)?terz[oi]\b",
                "cassazione": r"\bcassazione\b" if question else r"\bricors[oi]\s+(?:per|in)\s+cassazione\b"}
    return {key for key, pattern in patterns.items() if re.search(pattern, clean, re.I)}


def public_response_in_scope(question: str, answer: str, *, validated_quotes=()) -> bool:
    requested = explicit_public_rites(question)
    remedies = explicit_public_remedies(question, question=True)
    narrative = answer
    # Una norma comune può nominare più mezzi: conservare la citazione
    # integrale già verificata, senza autorizzare nuove regole sugli altri.
    # Una semplice etichetta fra virgolette non aggira il recinto.
    for quote in validated_quotes:
        if len(quote.split()) < 12:
            continue
        quote_rites = explicit_public_rites(quote)
        quote_remedies = explicit_public_remedies(quote)
        if requested and quote_rites and not requested & quote_rites:
            continue
        if remedies and quote_remedies and not remedies & quote_remedies:
            continue
        narrative = narrative.replace(quote, "")
    return ((not requested or not (explicit_public_rites(narrative) - requested))
            and (not remedies or not (explicit_public_remedies(narrative) - remedies)))


def _eligible_block(block: dict) -> bool:
    return bool(block.get("kind") != "heading" and block.get("text")
                and not block.get("form_context") and not block.get("link_only_context")
                and not block.get("technical_boilerplate") and not block.get("publisher_chrome"))


def _url_path(match) -> str:
    try:
        return unquote(urlsplit(match.group()).path)
    except ValueError:
        return ""


def _terms(value: str) -> set[str]:
    scaffolding = {"leggi", "confronta", "queste", "questi", "pagine", "pagina", "informazioni",
                   "pubbliche", "pubblici", "citando", "secondo", "libro", "titolo", "capo",
                   "html", "php", "servizi"}
    return set(termini_indice(" ".join(word for word in str(value).split() if word.casefold() not in scaffolding)))


def _block_priority(block: dict, question: str, *, fragment: bool = False) -> int:
    requested = explicit_public_rites(question)
    if requested:
        # Il capitolo più specifico governa il passaggio; il titolo generale
        # può elencare più riti senza renderli tutti oggetto della domanda.
        for heading in reversed(block.get("section") or []):
            rites = explicit_public_rites(heading)
            if rites:
                if not rites & requested:
                    return 5
                break
    remedies = explicit_public_remedies(question, question=True)
    for heading in reversed(block.get("section") or []):
        heading_remedies = explicit_public_remedies(heading)
        if heading_remedies:
            if remedies and not remedies & heading_remedies:
                return 6
            break
    mentioned = explicit_public_remedies(str(block.get("text") or ""))
    if remedies and mentioned and not remedies & mentioned:
        return 6
    last_section = str((block.get("section") or [""])[-1]).casefold()
    if fragment and remedies and mentioned - remedies and "dispositivo" not in last_section:
        return 6
    body_rites = explicit_public_rites(str(block.get("text") or ""))
    if fragment and requested and body_rites - requested and "dispositivo" not in last_section:
        return 5
    section = " ".join(block.get("section") or []).casefold()
    if any(word in question.casefold() for word in ("consulenza", "quesito")):
        return 0 if "consulenz" in section or "quesit" in section else 1
    if any(word in question.casefold() for word in ("massime", "giurisprudenza", "precedenti", "orientamenti")):
        return 0 if "massime" in section else 1
    # Conservare le sezioni storiche e individuali nell'inventario, senza
    # scambiarle per il testo generale della disposizione richiesta.
    if "consulenz" in section or "quesit" in section:
        return 4
    if "massime" in section:
        return 3
    last = str((block.get("section") or [""])[-1]).casefold()
    requested_articles = set(re.findall(r"\bart(?:icolo|\.)?\s*(\d+)", question, re.I))
    article = re.match(r"art(?:icolo|\.)?\s*(\d+)", last)
    if "dispositivo" in last or (article and article.group(1) in requested_articles):
        return 0
    return 0 if remedies & mentioned else 1


def semantic_block_scores(pages: list[dict], question: str, *, embedder, max_candidates: int = 64) -> dict:
    """Riusa il motore embedding nativo su un lotto pubblico, senza indice SQL.

    Una sola domanda e una sola chiamata per il lotto; i limiti e i blocchi
    esclusi sono dichiarati. Nessun modello viene scaricato o sostituito.
    """
    import numpy as np

    from lex.ricerca_giuridica.embedding import PREFISSO_DOMANDA, testo_documento

    if getattr(embedder, "modello", "") != "embeddinggemma:300m":
        raise ValueError("La selezione pubblica richiede il modello embedding governato 300M.")
    pools = []
    for page in pages:
        pool = [block for block in page.get("blocks", []) if _eligible_block(block)
                and _block_priority(block, question) <= 1 and len(str(block.get("text") or "")) >= 60]
        query_terms = _terms(question)
        pool.sort(key=lambda block: (_block_priority(block, question), -len(query_terms & _terms(block["text"] + " " + " ".join(block.get("section") or []))), block["index"]))
        pools.append(pool)
    selected = []
    for rank in range(max((len(pool) for pool in pools), default=0)):
        for page_index, pool in enumerate(pools):
            if rank < len(pool) and len(selected) < max(0, max_candidates):
                selected.append((page_index, pool[rank]))
        if len(selected) >= max(0, max_candidates):
            break
    if not selected:
        return {"scores": {}, "candidate_count": 0, "available_count": sum(map(len, pools)), "status": "no_candidates"}
    semantic_question = re.sub(r"https?://[^\s<>'\")\]]+", "", question).strip()
    titles = [str(page.get("title")) for page in pages if page.get("title")]
    query_origin = "user_question"
    if not (set(termini_indice(semantic_question)) - _READING_DIRECTIVE_TERMS) and titles:
        # La domanda «leggi queste pagine» non è il loro argomento. Usare
        # gli stessi titoli pubblici per tutto il lotto, senza trasformare
        # ogni sito in una ricerca diversa né privilegiare le istruzioni d'uso.
        semantic_question = "Contenuti delle pagine: " + " | ".join(titles)[:2000]
        query_origin = "common_page_titles"
    inputs = [PREFISSO_DOMANDA + semantic_question] + [
        testo_documento(" / ".join(block.get("section") or []), block["text"])
        for _, block in selected]
    vectors = np.asarray(embedder.embed(inputs), dtype=np.float32)
    if vectors.ndim != 2 or len(vectors) != len(inputs) or not np.isfinite(vectors).all():
        raise ValueError("Embedding dei passaggi incompleto o non valido.")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("Embedding dei passaggi nullo.")
    vectors = vectors / norms
    similarities = vectors[1:] @ vectors[0]
    scores = {}
    for (page_index, block), similarity in zip(selected, similarities, strict=True):
        scores.setdefault(page_index, {})[block["index"]] = float(similarity)
    return {"scores": scores, "candidate_count": len(selected),
            "query_origin": query_origin,
            "query_sha256": hashlib.sha256(semantic_question.encode("utf-8")).hexdigest(),
            "available_count": sum(map(len, pools)), "status": "ranked",
            "model": str(getattr(embedder, "modello", "")),
            "truncated_blocks": [{"page_index": page_index, "block_index": block["index"],
                                  "original_characters": len(block["text"]), "embedding_characters": 2400}
                                 for page_index, block in selected if len(block["text"]) > 2400],
            "limited_pool": len(selected) < sum(map(len, pools))}


def _render_passage(passage: dict) -> str:
    section = " / ".join(passage.get("section") or [])
    return f"Sezione: {section}\n{passage['text']}" if section else passage['text']


def select_passages(page: dict, question: str, *, max_chars: int = 6000, semantic_scores: dict | None = None) -> dict:
    text = str(page.get("text") or "")
    # I domini non sono argomenti giuridici; i percorsi possono invece
    # contenere il riferimento chiesto (es. art327.html). Conservare quel
    # numero con la stessa tokenizzazione usata dal ranking Lex.
    intent = re.sub(r"https?://[^\s<>'\")\]]+", _url_path, question)
    intent = re.sub(r"\bart(\d+)", r"articolo \1", intent, flags=re.I)
    tokens = _terms(intent)
    phrase_words = re.findall(r"\b[\wÀ-ÿ]{3,}\b", intent.casefold())
    phrases = {" ".join(pair) for pair in zip(phrase_words, phrase_words[1:], strict=False)}
    blocks = [block for block in page.get("blocks", []) if _eligible_block(block)]
    plain_reading = is_plain_source_reading(question)
    if page.get("blocks"):
        candidates = []
        semantic_floor = max((semantic_scores or {}).values(), default=0.0) - 0.12
        for block in blocks:
            if _block_priority(block, question) > 1:
                continue
            # Porzioni testuali terminate, non tagli a metà di un valore.
            # Una sezione lunga non deve far scartare il dato cercato solo
            # perché il suo paragrafo intero supera il budget del modello.
            pieces = re.split(r"(?<=[.!?;])\s+(?=[A-ZÀ-Ý])", str(block["text"])) if len(block["text"]) > 350 else [str(block["text"])]
            for piece_index, piece in enumerate(pieces):
                priority = _block_priority({**block, "text": piece}, question, fragment=True)
                if priority > 1:
                    continue
                if not piece.strip() or re.fullmatch(r"[\d\s().;:\-]+", piece):
                    continue
                score = 1 if plain_reading else len(tokens & _terms(piece))
                semantic = None if plain_reading else (semantic_scores or {}).get(block["index"])
                if not plain_reading and semantic_scores is not None and semantic is None and _block_priority(block, question) > 0:
                    continue
                if semantic is not None and semantic < semantic_floor and _block_priority(block, question) > 0:
                    continue
                if semantic is not None:
                    score = semantic + 0.03 * len(tokens & _terms(" ".join(block.get("section") or [])))
                elif score and not plain_reading:
                    score += 6 * len(tokens & _terms(" ".join(block.get("section") or [])))
                    score += 4 * sum(phrase in piece.casefold() for phrase in phrases)
                if score or _block_priority(block, question) == 0:
                    candidates.append({**block, "text": piece, "piece_index": piece_index, "score": score, "priority": priority})
        candidates.sort(key=lambda block: (block["priority"], -block["score"],
                                           int(block["index"]), block["piece_index"]))
        # Prima un riscontro per sezione pertinente, poi gli approfondimenti:
        # un unico capitolo prolisso non può consumare tutto il contesto.
        heads, rest, seen_sections = [], [], set()
        for block in candidates:
            section_key = tuple(block.get("section") or [])
            if section_key in seen_sections:
                rest.append(block)
            else:
                seen_sections.add(section_key)
                heads.append(block)
        remaining = max(0, max_chars)
        passages = []
        primary = [block for block in candidates if block["priority"] == 0]
        primary_sections = [tuple(block.get("section") or []) for block in primary if block.get("section")]
        secondary = [block for block in [*heads, *rest] if block["priority"] != 0
                     and (not explicit_public_remedies(question, question=True) or not primary_sections
                          or any(tuple(block.get("section") or [])[:len(section)] == section
                                 for section in primary_sections))]
        for block in [*primary, *secondary]:
            passage = str(block["text"])
            if not plain_reading and not semantic_scores and not tokens & _terms(passage) and _block_priority(block, question) != 0:
                continue
            cost = len(_render_passage({"text": passage, "section": block.get("section")})) + (2 if passages else 0)
            if cost > remaining:
                continue
            passages.append({"block_index": block["index"], "piece_index": block["piece_index"], "text": passage,
                             "section": list(block.get("section") or [])})
            remaining -= cost
        priorities = {(block["index"], block["piece_index"]): block["priority"] for block in candidates}
        passages.sort(key=lambda passage: (
            0 if plain_reading else priorities[(passage["block_index"], passage["piece_index"])],
            passage["block_index"], passage["piece_index"],
        ))
        return {"passages": passages, "total_characters": len(text),
                "selected_characters": sum(len(passage["text"]) for passage in passages),
                "selection_method": "shared_query_semantic_blocks_v2" if semantic_scores and not plain_reading else "shared_query_complete_blocks_v1",
                "selection_status": "selected" if passages else "no_relevant_passages",
                "requested_rites": sorted(explicit_public_rites(question)),
                "requested_remedies": sorted(explicit_public_remedies(question, question=True)),
                "excluded_outside_rite": sum(_block_priority(block, question) == 5 for block in blocks),
                "excluded_outside_remedy": sum(_block_priority(block, question) == 6 for block in blocks),
                "excluded_technical_blocks": sum(bool(block.get("technical_boilerplate")) for block in page.get("blocks", [])),
                "excluded_publisher_blocks": sum(bool(block.get("publisher_chrome")) for block in page.get("blocks", [])),
                "complete_context": False}
    # Stesse finestre, domanda e punteggio per ogni sito; niente euristiche
    # di favore per un dominio e niente frammenti provenienti dagli snippet.
    windows = [(start, text[start:start + 1200]) for start in range(0, len(text), 1200)]
    ranked = sorted(windows, key=lambda item: (-len(tokens & _terms(item[1])), item[0]))
    selected = []
    remaining = max(0, max_chars)
    for start, passage in ranked:
        if remaining <= 0:
            break
        passage = passage[:remaining]
        selected.append({"start": start, "end": start + len(passage), "text": passage})
        remaining -= len(passage)
    selected.sort(key=lambda item: item["start"])
    return {"passages": selected, "total_characters": len(text),
            "selected_characters": sum(len(item["text"]) for item in selected),
            "selection_method": "shared_query_token_windows_v1",
            "complete_context": len(text) <= max_chars}


def page_evidence(page: dict, question: str, *, max_chars: int = 6000, semantic_scores: dict | None = None) -> EvidenceItem | None:
    if page.get("status") != "read" or not page.get("text"):
        return None
    selection = select_passages(page, question, max_chars=max_chars, semantic_scores=semantic_scores)
    if not selection["passages"]:
        return None
    url = str(page.get("final_url") or page.get("url") or "")
    return EvidenceItem(
        source_type="web_libero", source_id=url,
        title=str(page.get("title") or url),
        content="\n\n".join(_render_passage(item) for item in selection["passages"]),
        score=0.0, verified_reference=False, authority="Web libero",
        metadata={"url": url, "requested_url": page.get("url"),
                  "sha256": page.get("sha256"), "fetched_at": page.get("fetched_at"),
                  "read_status": page["status"], "selection": selection,
                  "external_content_is_untrusted": True, "saved_to_db": False},
    )


def _native_semantic_ranking(pages: list[dict], question: str) -> dict:
    from lex.ricerca_giuridica.embedding import OllamaEmbedder

    embedder = OllamaEmbedder(modello="embeddinggemma:300m", timeout=8, tentativi=1, paralleli=1)
    return semantic_block_scores(pages, question, embedder=embedder, max_candidates=16)


def acquire_pages(rows: list[dict], question: str, *, reader=None, passage_ranker=None,
                  max_sources: int = 4, max_chars: int = 1600) -> dict:
    """Legge soltanto gli URL selezionati, senza nuovi job o scansioni.

    Gli esiti negativi sono nell'inventario, mai trasformati in evidenze con
    lo snippet del motore di ricerca. Lo stesso contenuto non costituisce
    una conferma indipendente: si conserva il collegamento fra le copie.
    """
    if reader is None:
        from lex.sources.public_page_reader import PublicPageReader

        reader = PublicPageReader()
    seen_urls = set()
    seen_hashes = {}
    visits = []
    evidence = []
    pages = []
    limit = min(8, max(0, max_sources))
    for row in rows:
        url = str(row.get("url") or row.get("official_url") or "").strip()
        if not url or url in seen_urls:
            continue
        if len(visits) >= limit:
            break
        seen_urls.add(url)
        page = reader.read(url)
        pages.append(page)
        visit = {key: page.get(key) for key in (
            "url", "final_url", "status", "http_status", "fetched_at", "sha256",
            "elapsed_ms", "content_type", "title", "warnings", "reason")}
        digest = page.get("sha256")
        if digest:
            visit["same_content_as"] = seen_hashes.get(digest)
            seen_hashes.setdefault(digest, url)
        visits.append(visit)
    ranking = {"status": "not_needed", "scores": {}}
    if not is_plain_source_reading(question) and any(
        page.get("status") == "read" and len(page.get("text") or "") > max_chars and page.get("blocks") for page in pages
    ):
        try:
            ranking = (passage_ranker or _native_semantic_ranking)(pages, question)
        except Exception as exc:
            ranking = {"status": "semantic_unavailable", "scores": {}, "error_type": type(exc).__name__}
    for page_index, (page, visit) in enumerate(zip(pages, visits, strict=True)):
        scores = ranking.get("scores", {}).get(page_index) if ranking.get("status") == "ranked" else None
        item = page_evidence(page, question, max_chars=max_chars, semantic_scores=scores)
        if item is not None:
            evidence.append(item)
            visit["selection"] = {key: value for key, value in item.metadata["selection"].items()
                                  if key != "passages"}
            item.metadata["semantic_selection_status"] = ranking["status"]
        elif page.get("status") == "read":
            visit["selection_status"] = "no_relevant_passages"
            visit["reason"] = "Pagina letta, ma nessun passaggio pertinente rientra nella selezione richiesta."
    return {"items": evidence, "visits": visits, "pages": pages,
            "saved_to_db": False, "question_used": question,
            "semantic_selection": {key: value for key, value in ranking.items() if key != "scores"},
            "read_count": len(evidence), "visited_count": len(visits)}
