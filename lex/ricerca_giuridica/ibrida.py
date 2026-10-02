"""Ricerca ibrida sui chunk Normattiva: bm25 (FTS5) + vettori, fusione RRF, ordinamento per pertinenza.

Ordinamento finale:

1. riferimento esatto «art. N + codice/atto» sempre in testa (anche senza parole in comune);
2. poi la fusione RRF (k=60) delle due classifiche, normalizzata sul migliore: è la pertinenza e
   pesa più di ogni altro fattore;
3. a parità, la versione VIGENTE prima dell'ORIGINALE; di ogni articolo resta una sola versione.

Senza indice vettoriale (o con Ollama non raggiungibile, o con un indice costruito da un modello
diverso da quello configurato) la ricerca resta lessicale e lo dichiara nei metadati.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .embedding import EmbedderDomande, EmbedderNonDisponibile, OllamaEmbedder
from .indice_fts import (
    BONUS_ARTICOLO_SENZA_CODICE,
    BONUS_ESATTO,
    BONUS_VIGENTE,
    _info_per_id,
    candidati_esatti,
    carica_chunk,
    cerca_fts,
    deduplica_versioni,
    indice_fts_presente,
)
from .indice_vettoriale import IndiceIncompatibile, IndiceVettoriale
from .testo import AnalisiDomanda, analizza_domanda

logger = logging.getLogger(__name__)

RRF_K = 60
_FALSI = {"0", "false", "no", "off", "disabilitato"}


def cartella_vettori_predefinita(db_path: str | Path) -> Path:
    configurata = str(os.getenv("LEX_NORMATTIVA_VETTORI_DIR", "") or "").strip()
    if configurata:
        return Path(configurata)
    return Path(db_path).parent / "vettori_normattiva"


def ricerca_semantica_abilitata() -> bool:
    return str(os.getenv("LEX_RICERCA_SEMANTICA", "1") or "1").strip().lower() not in _FALSI


@dataclass(slots=True)
class RisultatoIbrido:
    chunk_id: int
    punteggio: float = 0.0
    rrf: float = 0.0
    rango_lessicale: int = 0
    rango_semantico: int = 0
    coseno: float = 0.0
    bm25: float = 0.0
    esatto: bool = False
    articolo: str = ""
    codice: str = ""
    vigenza: str = ""
    identita: str = ""
    parte: int = 1


def fondi_rrf(
    lessicali: list[Any],
    semantici: list[tuple[int, float]],
    info: dict[int, tuple],
    *,
    analisi: AnalisiDomanda,
    esatti: set[int],
    vigenza: str | None = None,
    k: int = RRF_K,
) -> list[RisultatoIbrido]:
    risultati: dict[int, RisultatoIbrido] = {}
    for posizione, voce in enumerate(lessicali, start=1):
        r = risultati.setdefault(voce.chunk_id, RisultatoIbrido(chunk_id=voce.chunk_id))
        r.rango_lessicale = posizione
        r.bm25 = float(getattr(voce, "bm25", 0.0) or 0.0)
        r.rrf += 1.0 / (k + posizione)
    for posizione, (chunk_id, coseno) in enumerate(semantici, start=1):
        r = risultati.setdefault(chunk_id, RisultatoIbrido(chunk_id=chunk_id))
        r.rango_semantico = posizione
        r.coseno = float(coseno)
        r.rrf += 1.0 / (k + posizione)
    filtro = str(vigenza or "").strip().upper()
    migliore = max((r.rrf for r in risultati.values()), default=0.0) or 1.0
    uscita: list[RisultatoIbrido] = []
    for r in risultati.values():
        dati = info.get(r.chunk_id)
        if dati is None:
            continue
        r.articolo, r.codice, _atto_numero, _atto_anno, r.vigenza, r.identita, parte = dati
        r.parte = int(parte or 1)
        if filtro and r.vigenza != filtro:
            continue
        r.esatto = r.chunk_id in esatti and bool(analisi.codice or analisi.atto_numero)
        punteggio = r.rrf / migliore
        if r.chunk_id in esatti:
            punteggio += BONUS_ESATTO if r.esatto else BONUS_ARTICOLO_SENZA_CODICE
        if r.vigenza == "VIGENTE":
            punteggio += BONUS_VIGENTE / 2
        elif r.vigenza == "ORIGINALE":
            punteggio -= BONUS_VIGENTE / 2
        r.punteggio = round(punteggio, 6)
        uscita.append(r)
    uscita.sort(key=lambda item: (-item.punteggio, item.chunk_id))
    return deduplica_versioni(uscita)


@dataclass
class MotoreRicercaNormattiva:
    """Ricerca su un database Normattiva con indice FTS5 ed eventuale indice vettoriale."""

    db_path: Path
    cartella_vettori: Path | None = None
    embedder: Any = None
    usa_semantica: bool = True
    _indice: IndiceVettoriale | None = field(default=None, init=False, repr=False)
    _motivo_semantica: str = field(default="", init=False)
    _versione_verificata: bool = field(default=False, init=False)
    _domande: EmbedderDomande | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        if self.cartella_vettori is None:
            self.cartella_vettori = cartella_vettori_predefinita(self.db_path)
        self.cartella_vettori = Path(self.cartella_vettori)
        if not self.usa_semantica:
            self._motivo_semantica = "ricerca semantica disattivata"
            return
        indice = IndiceVettoriale.apri(self.cartella_vettori)
        if indice is None:
            self._motivo_semantica = f"indice vettoriale assente in {self.cartella_vettori}"
            return
        if self.embedder is None:
            timeout = float(str(os.getenv("LEX_EMBED_TIMEOUT_S", "4") or "4").replace(",", "."))
            self.embedder = OllamaEmbedder(timeout=timeout, dimensioni=indice.dimensioni)
        compatibile, motivo = indice.verifica_modello(self.embedder.modello)
        if not compatibile:
            self._motivo_semantica = f"indice vettoriale ignorato: {motivo}"
            logger.warning("Lex ricerca Normattiva: %s.", self._motivo_semantica)
            return
        self._indice = indice
        self._domande = EmbedderDomande(self.embedder)

    # ----------------------------------------------------------------------------------------
    def stato(self) -> dict[str, Any]:
        return {
            "db": str(self.db_path),
            "indice_vettoriale": str(self.cartella_vettori),
            "semantica_attiva": self._indice is not None,
            "motivo_semantica": self._motivo_semantica,
            "modello": getattr(self.embedder, "modello", ""),
            "righe_vettori": self._indice.righe if self._indice else 0,
        }

    def _vettore_domanda(self, domanda: str):
        if self._indice is None or self._domande is None:
            return None
        try:
            vettore = self._domande.vettore(domanda)
        except EmbedderNonDisponibile as exc:
            self._motivo_semantica = f"embedding della domanda non disponibile ({exc})"
            return None
        if not self._versione_verificata:
            self._versione_verificata = True
            try:
                versione = str(self.embedder.versione() or "")
            except Exception:
                versione = ""
            compatibile, motivo = self._indice.verifica_modello(self.embedder.modello, versione)
            if not compatibile:
                self._motivo_semantica = f"indice vettoriale ignorato: {motivo}"
                logger.warning("Lex ricerca Normattiva: %s.", self._motivo_semantica)
                self._indice = None
                return None
        return vettore

    def cerca_id(
        self,
        conn: sqlite3.Connection,
        domanda: str,
        *,
        limite: int = 10,
        vigenza: str | None = None,
        modalita: str = "ibrida",
        usa_tesauro: bool = True,
    ) -> tuple[list[RisultatoIbrido], dict[str, Any]]:
        analisi = analizza_domanda(domanda, usa_tesauro=usa_tesauro)
        quanti = max(50, limite * 5)
        lessicali = [] if modalita == "semantica" else cerca_fts(conn, analisi, limite=quanti, vigenza=vigenza)
        semantici: list[tuple[int, float]] = []
        if modalita in {"ibrida", "semantica"} and self._indice is not None:
            vettore = self._vettore_domanda(domanda)
            if vettore is not None:
                try:
                    semantici = self._indice.cerca(vettore, k=quanti)
                except IndiceIncompatibile as exc:
                    self._motivo_semantica = f"indice vettoriale ignorato: {exc}"
                    self._indice = None
                    semantici = []
        esatti = set(candidati_esatti(conn, analisi)) if modalita != "semantica" else set()
        ids = list(dict.fromkeys([*(r.chunk_id for r in lessicali), *(i for i, _ in semantici)]))
        info = _info_per_id(conn, ids)
        fusi = fondi_rrf(lessicali, semantici, info, analisi=analisi, esatti=esatti, vigenza=vigenza)
        dettagli = {
            "modalita_richiesta": modalita,
            "modalita_usata": (
                "ibrida" if lessicali and semantici else "semantica" if semantici else "lessicale"
            ),
            "lessicali": len(lessicali),
            "semantici": len(semantici),
            "riferimento_esatto": analisi.riferimento_esatto,
            "articoli": analisi.articoli,
            "codice": analisi.codice,
            "termini": analisi.termini,
            "espansioni": analisi.espansioni,
            "motivo_semantica": "" if semantici else self._motivo_semantica,
        }
        return fusi[: max(1, int(limite))], dettagli

    def cerca(
        self,
        domanda: str,
        *,
        limite: int = 10,
        vigenza: str | None = None,
        modalita: str = "ibrida",
    ) -> list[dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            risultati, dettagli = self.cerca_id(conn, domanda, limite=limite, vigenza=vigenza, modalita=modalita)
            righe = carica_chunk(conn, [r.chunk_id for r in risultati])
        finally:
            conn.close()
        uscita: list[dict[str, Any]] = []
        migliore = max((r.punteggio for r in risultati), default=0.0) or 1.0
        for r in risultati:
            riga = righe.get(r.chunk_id)
            if riga is None:
                continue
            riga = dict(riga)
            riga["punteggio"] = r.punteggio
            riga["pertinenza"] = round(min(1.0, max(0.0, r.punteggio / migliore)), 4)
            riga["riferimento_esatto"] = r.esatto
            riga["ricerca"] = {
                "modalita": dettagli["modalita_usata"],
                "rango_lessicale": r.rango_lessicale,
                "rango_semantico": r.rango_semantico,
                "coseno": round(r.coseno, 4),
                "bm25": round(r.bm25, 4),
                "motivo_semantica": dettagli["motivo_semantica"],
            }
            uscita.append(riga)
        return uscita


_MOTORI: dict[tuple[str, str, float], MotoreRicercaNormattiva] = {}
_LOCK = threading.Lock()


def motore_per_db(db_path: str | Path) -> MotoreRicercaNormattiva:
    """Motore condiviso per database (ricreato se l'indice vettoriale cambia su disco)."""

    percorso = Path(db_path)
    cartella = cartella_vettori_predefinita(percorso)
    meta = cartella / "meta.json"
    try:
        firma = meta.stat().st_mtime if meta.exists() else 0.0
    except OSError:
        firma = 0.0
    chiave = (str(percorso.resolve()), str(cartella), firma)
    with _LOCK:
        motore = _MOTORI.get(chiave)
        if motore is None:
            for vecchia in [k for k in _MOTORI if k[0] == chiave[0]]:
                _MOTORI.pop(vecchia, None)
            motore = MotoreRicercaNormattiva(percorso, cartella, usa_semantica=ricerca_semantica_abilitata())
            _MOTORI[chiave] = motore
        return motore


def cerca_normattiva_indicizzata(
    domanda: str,
    db_path: str | Path,
    *,
    limite: int = 10,
    vigenza: str | None = None,
) -> list[dict[str, Any]] | None:
    """Ricerca con gli indici di Lex; ``None`` se il database non ha ancora l'indice FTS5."""

    percorso = Path(db_path)
    if not percorso.exists():
        return None
    conn = sqlite3.connect(str(percorso))
    try:
        if not indice_fts_presente(conn):
            return None
    finally:
        conn.close()
    return motore_per_db(percorso).cerca(domanda, limite=limite, vigenza=vigenza)


__all__ = [
    "MotoreRicercaNormattiva",
    "RRF_K",
    "RisultatoIbrido",
    "cartella_vettori_predefinita",
    "cerca_normattiva_indicizzata",
    "fondi_rrf",
    "motore_per_db",
    "ricerca_semantica_abilitata",
]
