"""Passaggi confrontabili delle pagine lette con una domanda comune.

L'inventario completo resta distinto dal sottoinsieme inviato al modello:
non dichiarare lettura semantica integrale quando il contesto è selettivo.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from lex.contracts import EvidenceItem
from lex.ricerca_giuridica.testo import termini_indice


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


def _block_priority(block: dict, question: str) -> int:
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
    return 1


def semantic_block_scores(pages: list[dict], question: str, *, embedder, max_candidates: int = 64) -> dict:
    """Riusa il motore embedding nativo su un lotto pubblico, senza indice SQL.

    Una sola domanda e una sola chiamata per il lotto; i limiti e i blocchi
    esclusi sono dichiarati. Nessun modello viene scaricato o sostituito.
    """
    from lex.ricerca_giuridica.embedding import PREFISSO_DOMANDA, testo_documento

    import numpy as np

    if getattr(embedder, "modello", "") != "embeddinggemma:300m":
        raise ValueError("La selezione pubblica richiede il modello embedding governato 300M.")
    pools = []
    for page in pages:
        pool = [block for block in page.get("blocks", []) if block.get("kind") != "heading"
                and not block.get("form_context") and not block.get("link_only_context")
                and _block_priority(block, question) <= 1 and len(str(block.get("text") or "")) >= 60]
        query_terms = _terms(question)
        pool.sort(key=lambda block: (-len(query_terms & _terms(block["text"] + " " + " ".join(block.get("section") or []))), block["index"]))
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
    if len(_terms(semantic_question)) < 4 and titles:
        semantic_question += " Titoli delle pagine: " + " | ".join(titles)[:2000]
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
    for (page_index, block), similarity in zip(selected, similarities):
        scores.setdefault(page_index, {})[block["index"]] = float(similarity)
    return {"scores": scores, "candidate_count": len(selected),
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
    phrases = {" ".join(pair) for pair in zip(phrase_words, phrase_words[1:])}
    blocks = [block for block in page.get("blocks", []) if block.get("kind") != "heading"
              and block.get("text") and not block.get("form_context") and not block.get("link_only_context")]
    if blocks and len(text) > max_chars:
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
                if not piece.strip() or re.fullmatch(r"[\d\s().;:\-]+", piece):
                    continue
                score = len(tokens & _terms(piece))
                semantic = (semantic_scores or {}).get(block["index"])
                if semantic_scores is not None and semantic is None:
                    continue
                if semantic is not None and semantic < semantic_floor and _block_priority(block, question) > 0:
                    continue
                if semantic is not None:
                    score = semantic + 0.03 * len(tokens & _terms(" ".join(block.get("section") or [])))
                elif score:
                    score += 6 * len(tokens & _terms(" ".join(block.get("section") or [])))
                    score += 4 * sum(phrase in piece.casefold() for phrase in phrases)
                if score:
                    candidates.append({**block, "text": piece, "piece_index": piece_index, "score": score})
        candidates.sort(key=lambda block: (_block_priority(block, question), -block["score"],
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
        primary = [block for block in candidates if _block_priority(block, question) == 0]
        secondary = [block for block in [*heads, *rest] if _block_priority(block, question) != 0]
        for block in [*primary, *secondary]:
            passage = str(block["text"])
            if not semantic_scores and not tokens & _terms(passage):
                continue
            cost = len(_render_passage({"text": passage, "section": block.get("section")})) + (2 if passages else 0)
            if cost > remaining:
                continue
            passages.append({"block_index": block["index"], "piece_index": block["piece_index"], "text": passage,
                             "section": list(block.get("section") or [])})
            remaining -= cost
        if passages:
            passages.sort(key=lambda passage: (passage["block_index"], passage["piece_index"]))
            return {"passages": passages, "total_characters": len(text),
                    "selected_characters": sum(len(passage["text"]) for passage in passages),
                    "selection_method": "shared_query_semantic_blocks_v1" if semantic_scores else "shared_query_complete_blocks_v1",
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
    return semantic_block_scores(pages, question, embedder=embedder)


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
    if any(page.get("status") == "read" and len(page.get("text") or "") > max_chars and page.get("blocks") for page in pages):
        try:
            ranking = (passage_ranker or _native_semantic_ranking)(pages, question)
        except Exception as exc:
            ranking = {"status": "semantic_unavailable", "scores": {}, "error_type": type(exc).__name__}
    for page_index, (page, visit) in enumerate(zip(pages, visits)):
        scores = ranking.get("scores", {}).get(page_index) if ranking.get("status") == "ranked" else None
        item = page_evidence(page, question, max_chars=max_chars, semantic_scores=scores)
        if item is not None:
            evidence.append(item)
            visit["selection"] = {key: value for key, value in item.metadata["selection"].items()
                                  if key != "passages"}
            item.metadata["semantic_selection_status"] = ranking["status"]
    return {"items": evidence, "visits": visits, "pages": pages,
            "saved_to_db": False, "question_used": question,
            "semantic_selection": {key: value for key, value in ranking.items() if key != "scores"},
            "read_count": len(evidence), "visited_count": len(visits)}
