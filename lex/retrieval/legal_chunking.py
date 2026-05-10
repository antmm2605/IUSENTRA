"""Chunking documentale per sezioni giuridiche - IUSENTRA Lex.

Suddivide atti, sentenze e documenti legali in chunk strutturati per
sezione (intestazione, parti, fatto, diritto, PQM, ecc.) in modo che
il retrieval possa restituire porzioni pertinenti invece di blocchi
arbitrari di testo.

Ogni chunk ha metadati sufficienti per essere usato come EvidenceItem
nel pipeline Lex senza perdere il contesto di provenienza.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Tipi di sezione giuridica riconosciuti
# ---------------------------------------------------------------------------

SEZIONI_GIURIDICHE = (
    "intestazione",
    "parti",
    "fatto",
    "diritto",
    "motivi",
    "pqm",           # Per Questi Motivi / dispositivo
    "richieste",
    "eccezioni",
    "allegati",
    "date",
    "importi",
    "norme_citate",
    "sentenze_citate",
    "scadenze",
    "prove",
    "ricevute_telematiche",
    "sconosciuta",
)

# Pattern per identificare l'inizio di ogni sezione
_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "pqm",
        re.compile(
            r"(?:^|\n)\s*(?:P\.?\s*Q\.?\s*M\.?|PER\s+QUESTI\s+MOTIVI|DISPOSITIVO|DICHIARA\s+e\s+CONDANNA)\s*[:\n]?",
            re.I | re.M,
        ),
    ),
    (
        "fatto",
        re.compile(
            r"(?:^|\n)\s*(?:FATTO|IN\s+FATTO|SVOLGIMENTO\s+DEL\s+PROCESSO|PREMESSO\s+IN\s+FATTO)\s*[:\n]?",
            re.I | re.M,
        ),
    ),
    (
        "diritto",
        re.compile(
            r"(?:^|\n)\s*(?:DIRITTO|IN\s+DIRITTO|MOTIVI\s+DI\s+DIRITTO|CONSIDERATO\s+IN\s+DIRITTO)\s*[:\n]?",
            re.I | re.M,
        ),
    ),
    (
        "motivi",
        re.compile(
            r"(?:^|\n)\s*(?:MOTIVI|MOTIVI\s+D'APPELLO|MOTIVI\s+DI\s+RICORSO|CENSURE)\s*[:\n]?",
            re.I | re.M,
        ),
    ),
    (
        "richieste",
        re.compile(
            r"(?:^|\n)\s*(?:CHIEDE|RICHIEDE|CONCLUSIONI|PARTE\s+CONCLUDE|SI\s+CHIEDE)\s*[:\n]?",
            re.I | re.M,
        ),
    ),
    (
        "eccezioni",
        re.compile(
            r"(?:^|\n)\s*(?:ECCEZIONI|ECCEZIONE\s+DI|ECCEPISCE|IN\s+VIA\s+PREGIUDIZIALE|PRELIMINARMENTE)\s*[:\n]?",
            re.I | re.M,
        ),
    ),
    (
        "parti",
        re.compile(
            r"(?:^|\n)\s*(?:TRA\s+LE\s+PARTI|PARTI\s+IN\s+CAUSA|RICORRENTE|RESISTENTE|ATTORE|CONVENUTO|OPPONENTE|OPPOSTO)\s*[:\n]?",
            re.I | re.M,
        ),
    ),
    (
        "allegati",
        re.compile(
            r"(?:^|\n)\s*(?:ALLEGAT[OI]|DOC\.|DOCUMENTO\s+N\.|PRODUZIONE\s+DOCUMENTALE)\s*[:\n]?",
            re.I | re.M,
        ),
    ),
    (
        "ricevute_telematiche",
        re.compile(
            r"(?:^|\n)\s*(?:RICEVUTA\s+DI\s+ACCETTAZIONE|RICEVUTA\s+DI\s+CONSEGNA|ESITO\s+DEPOSITO|AVVISO\s+DI\s+MANCATA\s+CONSEGNA)\s*[:\n]?",
            re.I | re.M,
        ),
    ),
]

# Pattern per estrarre norme citate nel testo
_NORMA_RE = re.compile(
    r"(?:art(?:icolo)?\.?\s*\d+(?:\s*(?:co\.?|comma)\s*\d+)?(?:\s*(?:lett\.?|lettera)\s*[a-z]\)?)?(?:\s+(?:del|della|dello|degli)\s+)?(?:codice\s+civile|c\.c\.|codice\s+penale|c\.p\.|codice\s+di\s+procedura\s+civile|c\.p\.c\.|codice\s+di\s+procedura\s+penale|c\.p\.p\.|l\.?\s+n\.?\s*\d+/\d{4}|d\.lgs\.?\s+n\.?\s*\d+/\d{4}|d\.l\.?\s+n\.?\s*\d+/\d{4}|d\.p\.r\.?\s+n\.?\s*\d+/\d{4}|regio\s+decreto|r\.d\.))",
    re.I,
)

# Pattern per estrarre sentenze citate
_SENTENZA_RE = re.compile(
    r"(?:cass\.?\s+(?:sez\.?\s+\w+\s+)?(?:n\.?\s*)?\d+/\d{4}|"
    r"tribunale\s+(?:di\s+\w+\s+)?(?:n\.?\s*)?\d+/\d{4}|"
    r"corte\s+d'appello\s+(?:di\s+\w+\s+)?(?:n\.?\s*)?\d+/\d{4}|"
    r"ecli:[a-z]{2}:[a-z:]+:\d{4}:\d+)",
    re.I,
)

# Pattern importi monetari
_IMPORTO_RE = re.compile(
    r"(?:euro|eur|€)\s*[\d.,]+(?:\.\d{3})*(?:,\d{2})?|\d{1,3}(?:\.\d{3})*,\d{2}\s*(?:euro|eur|€)",
    re.I,
)

# Pattern date
_DATA_RE = re.compile(
    r"\b\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}\b|\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{4}\b",
    re.I,
)


@dataclass
class LegalChunk:
    """Chunk strutturato di un documento legale."""

    tenant_id: str
    fascicolo_id: str
    document_id: str
    source_path: str            # basename sanificato (NON path assoluto)
    content_hash: str
    page: int | None
    section: str                # uno di SEZIONI_GIURIDICHE
    text: str
    extraction_method: str      # "regex_sections" | "structural" | "ocr" | "fallback"
    extraction_confidence: float
    created_at: str
    updated_at: str
    norme_citate: list[str] = field(default_factory=list)
    sentenze_citate: list[str] = field(default_factory=list)
    importi: list[str] = field(default_factory=list)
    date_trovate: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_evidence_dict(self) -> dict[str, Any]:
        """Converte in dict compatibile con EvidenceItem."""
        return {
            "source_type": "documento",
            "source_id": f"{self.document_id}#{self.section}#{self.page or 0}",
            "title": f"[{self.section.upper()}] {self.source_path}",
            "content": self.text,
            "score": self.extraction_confidence,
            "trust_score": self.extraction_confidence,
            "freshness_score": 0.5,
            "context_fit_score": 0.7,
            "consensus_score": 0.5,
            "verified_reference": False,
            "authority": "documento_fascicolo",
            "metadata": {
                "tenant_id": self.tenant_id,
                "fascicolo_id": self.fascicolo_id,
                "document_id": self.document_id,
                "page": self.page,
                "section": self.section,
                "norme_citate": self.norme_citate,
                "sentenze_citate": self.sentenze_citate,
                "importi": self.importi,
                "content_hash": self.content_hash,
                "extraction_method": self.extraction_method,
            },
        }


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _detect_norme(text: str) -> list[str]:
    """Estrae riferimenti normativi dal testo."""
    return list({m.group(0).strip() for m in _NORMA_RE.finditer(text)})[:20]


def _detect_sentenze(text: str) -> list[str]:
    """Estrae riferimenti giurisprudenziali dal testo."""
    return list({m.group(0).strip() for m in _SENTENZA_RE.finditer(text)})[:10]


def _detect_importi(text: str) -> list[str]:
    """Estrae importi monetari dal testo."""
    return list({m.group(0).strip() for m in _IMPORTO_RE.finditer(text)})[:10]


def _detect_date(text: str) -> list[str]:
    """Estrae date dal testo."""
    return list({m.group(0).strip() for m in _DATA_RE.finditer(text)})[:10]


def _split_by_sections(text: str) -> list[tuple[str, str]]:
    """Suddivide il testo per sezioni giuridiche riconosciute.

    Restituisce lista di (section_name, section_text).
    """
    # Trova tutte le posizioni di inizio sezione
    boundaries: list[tuple[int, str]] = []
    for section_name, pattern in _SECTION_PATTERNS:
        for match in pattern.finditer(text):
            boundaries.append((match.start(), section_name))

    if not boundaries:
        return [("sconosciuta", text)]

    boundaries.sort(key=lambda x: x[0])

    # Prima sezione: intestazione = tutto prima della prima boundary
    result: list[tuple[str, str]] = []
    first_pos = boundaries[0][0]
    if first_pos > 100:
        intro = text[:first_pos].strip()
        if intro:
            result.append(("intestazione", intro))

    # Sezioni intermedie
    for i, (pos, section_name) in enumerate(boundaries):
        end_pos = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        section_text = text[pos:end_pos].strip()
        if len(section_text) > 20:
            result.append((section_name, section_text))

    return result or [("sconosciuta", text)]


def chunk_legal_document(
    text: str,
    *,
    tenant_id: str,
    fascicolo_id: str,
    document_id: str,
    source_path: str,
    page: int | None = None,
    extraction_method: str = "fallback",
    extraction_confidence: float = 0.70,
    max_chunk_chars: int = 2000,
) -> list[LegalChunk]:
    """Suddivide un documento legale in chunk strutturati per sezione.

    Se il documento non contiene sezioni riconoscibili (es. una email o
    una scansione senza OCR strutturato), cade in modalità fallback con
    chunking sequenziale.

    Args:
        text: Testo estratto del documento.
        tenant_id: ID tenant (obbligatorio per isolamento dati).
        fascicolo_id: ID fascicolo di appartenenza.
        document_id: ID univoco del documento.
        source_path: Percorso/nome file (sarà sanificato a basename).
        page: Numero pagina di partenza (None se intero documento).
        extraction_method: Metodo usato per estrarre il testo.
        extraction_confidence: Confidenza dell'estrazione (0.0–1.0).
        max_chunk_chars: Lunghezza massima di ogni chunk in caratteri.

    Returns:
        Lista di LegalChunk pronti per l'indicizzazione.
    """
    if not text or not str(text).strip():
        return []

    # Sanifica source_path: usa solo il basename
    import os
    safe_source = os.path.basename(str(source_path or "documento"))

    now = _now_iso()
    chunks: list[LegalChunk] = []
    sections = _split_by_sections(text)

    for section_name, section_text in sections:
        # Suddividi sezione in sotto-chunk se troppo lunga
        sub_chunks = _split_large_section(section_text, max_chars=max_chunk_chars)

        for sub_idx, sub_text in enumerate(sub_chunks):
            if not sub_text.strip():
                continue

            chunks.append(
                LegalChunk(
                    tenant_id=tenant_id,
                    fascicolo_id=fascicolo_id,
                    document_id=document_id,
                    source_path=safe_source,
                    content_hash=_compute_hash(sub_text),
                    page=page,
                    section=section_name,
                    text=sub_text,
                    extraction_method=extraction_method,
                    extraction_confidence=extraction_confidence,
                    created_at=now,
                    updated_at=now,
                    norme_citate=_detect_norme(sub_text),
                    sentenze_citate=_detect_sentenze(sub_text),
                    importi=_detect_importi(sub_text),
                    date_trovate=_detect_date(sub_text),
                    metadata={
                        "section_index": len(chunks),
                        "sub_chunk_index": sub_idx,
                        "total_sections": len(sections),
                    },
                )
            )

    if not chunks:
        # Fallback: un unico chunk con tutto il testo
        chunks.append(
            LegalChunk(
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                document_id=document_id,
                source_path=safe_source,
                content_hash=_compute_hash(text),
                page=page,
                section="sconosciuta",
                text=text[:max_chunk_chars],
                extraction_method=extraction_method,
                extraction_confidence=extraction_confidence * 0.7,
                created_at=now,
                updated_at=now,
                norme_citate=_detect_norme(text),
                sentenze_citate=_detect_sentenze(text),
                importi=_detect_importi(text),
                date_trovate=_detect_date(text),
                metadata={"fallback": True},
            )
        )

    return chunks


def _split_large_section(text: str, max_chars: int = 2000) -> list[str]:
    """Suddivide una sezione troppo lunga in paragrafi."""
    if len(text) <= max_chars:
        return [text]

    # Prova prima a spezzare per paragrafo (doppio newline)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if all(len(p) <= max_chars for p in paragraphs) and len(paragraphs) > 1:
        return paragraphs

    # Altrimenti chunking semplice per lunghezza
    result: list[str] = []
    for i in range(0, len(text), max_chars):
        chunk = text[i: i + max_chars].strip()
        if chunk:
            result.append(chunk)
    return result


def chunks_need_indexing(
    document_id: str,
    fascicolo_id: str,
    tenant_id: str,
    existing_chunk_ids: set[str] | None = None,
) -> bool:
    """Verifica se un documento deve essere indicizzato.

    Se non ci sono chunk esistenti per questo documento, restituisce True.
    Questo aiuta Lex a sapere quando proporre l'indicizzazione all'utente.
    """
    if existing_chunk_ids is None:
        return True
    doc_prefix = f"{document_id}#"
    return not any(cid.startswith(doc_prefix) for cid in existing_chunk_ids)


def make_indexing_needed_response(
    document_id: str,
    source_path: str,
    *,
    fascicolo_id: str = "",
) -> dict[str, Any]:
    """Costruisce il payload da restituire quando un documento non è indicizzato.

    Lex deve usare questo invece di generare una sintesi inventata.
    """
    import os
    safe_name = os.path.basename(str(source_path or document_id))
    return {
        "answer_mode": "needs_review",
        "answer": (
            f"Il documento «{safe_name}» non è ancora indicizzato come evidenza citabile. "
            "Per usarlo nel ragionamento legale è necessario indicizzarlo prima."
        ),
        "confidence": 0.12,
        "missing_evidence": [
            f"Documento {safe_name} non indicizzato.",
            "Esegui l'indicizzazione dal pannello documenti del fascicolo.",
        ],
        "next_actions": [
            f"Apri il fascicolo {fascicolo_id or ''} e indicizza il documento «{safe_name}».",
            "Dopo l'indicizzazione, ripeti la domanda per ottenere evidenze citabili.",
        ],
        "warnings": [
            "Documento non indicizzato: risposta basata su evidenze insufficienti.",
        ],
        "document_id": document_id,
        "fascicolo_id": fascicolo_id,
    }
