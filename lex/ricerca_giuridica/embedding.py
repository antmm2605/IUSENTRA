"""Embedding per la ricerca semantica: Ollama (embeddinggemma) e un embedder finto deterministico per i test.

Configurazione (stesso Ollama e stesso modello di embedding del server):

- ``LEX_EMBED_MODEL``, altrimenti ``PCT_LOCAL_AI_EMBED_MODEL``, altrimenti ``embeddinggemma:300m``;
- ``LEX_EMBED_URL``, altrimenti ``PCT_LOCAL_AI_BASE_URL``, ``OLLAMA_URL``, ``http://127.0.0.1:11434``;
- ``LEX_EMBED_TIMEOUT_S`` (domanda, default 4 s) — la ricerca semantica non deve mai bloccare Lex.

EmbeddingGemma è addestrato con prefissi di compito: ``task: search result | query: `` per la
domanda e ``title: … | text: `` per il documento. I prefissi fanno parte dei metadati dell'indice.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from .testo import termini_indice

MODELLO_PREDEFINITO = "embeddinggemma:300m"
PREFISSO_DOMANDA = "task: search result | query: "
PREFISSO_DOCUMENTO = "title: {titolo} | text: "


class Embedder(Protocol):
    modello: str

    def versione(self) -> str: ...

    def embed(self, testi: list[str]) -> np.ndarray: ...


def modello_configurato() -> str:
    return (
        str(os.getenv("LEX_EMBED_MODEL", "") or "").strip()
        or str(os.getenv("PCT_LOCAL_AI_EMBED_MODEL", "") or "").strip()
        or MODELLO_PREDEFINITO
    )


def url_configurato() -> str:
    for nome in ("LEX_EMBED_URL", "PCT_LOCAL_AI_BASE_URL", "OLLAMA_URL"):
        valore = str(os.getenv(nome, "") or "").strip()
        if valore:
            return base_ollama(valore)
    return "http://127.0.0.1:11434"


def base_ollama(url: str) -> str:
    """«http://ollama:11434/api/version» → «http://ollama:11434»."""

    valore = str(url or "").strip().rstrip("/")
    valore = re.sub(r"/api(?:/.*)?$", "", valore)
    return valore or "http://127.0.0.1:11434"


def normalizza_righe(matrice: np.ndarray) -> np.ndarray:
    matrice = np.asarray(matrice, dtype=np.float32)
    if matrice.ndim == 1:
        matrice = matrice[None, :]
    norme = np.linalg.norm(matrice, axis=1, keepdims=True)
    norme[norme == 0] = 1.0
    return matrice / norme


@dataclass
class OllamaEmbedder:
    """Embedding via Ollama ``/api/embed`` (batch); ``/api/embeddings`` per le versioni vecchie."""

    modello: str = ""
    url: str = ""
    timeout: float = 120.0
    tentativi: int = 3
    attesa_s: float = 1.0
    dimensioni: int = 0  # >0: troncamento Matryoshka (embeddinggemma supporta 768/512/256/128)
    paralleli: int = 0  # richieste contemporanee per batch (0 = LEX_EMBED_PARALLELI o 1); serve OLLAMA_NUM_PARALLEL sul server Ollama

    def __post_init__(self) -> None:
        self.modello = self.modello or modello_configurato()
        self.url = base_ollama(self.url or url_configurato())
        self._digest: str | None = None
        if not self.paralleli:
            try:
                self.paralleli = max(1, int(os.getenv("LEX_EMBED_PARALLELI", "1") or 1))
            except ValueError:
                self.paralleli = 1

    def versione(self) -> str:
        """Versione dei pesi: digest da ``/api/tags``, altrimenti ``modified_at`` da ``/api/show``."""

        if self._digest is not None:
            return self._digest
        import requests

        versione = ""
        try:
            risposta = requests.get(f"{self.url}/api/tags", timeout=min(self.timeout, 10.0))
            risposta.raise_for_status()
            for voce in list((risposta.json() or {}).get("models") or []):
                nomi = {str(voce.get("name") or ""), str(voce.get("model") or "")}
                if self.modello in nomi or f"{self.modello}:latest" in nomi:
                    versione = str(voce.get("digest") or "")
                    break
        except Exception:
            versione = ""
        if not versione:
            try:
                risposta = requests.post(f"{self.url}/api/show", json={"model": self.modello}, timeout=min(self.timeout, 10.0))
                risposta.raise_for_status()
                dati = risposta.json() or {}
                versione = str(dati.get("digest") or dati.get("modified_at") or "")
            except Exception:
                versione = ""
        self._digest = versione
        return versione

    def _embed_una_volta(self, testi: list[str]) -> np.ndarray:
        import requests

        corpo: dict[str, Any] = {"model": self.modello, "input": list(testi), "truncate": True, "keep_alive": "15m"}
        risposta = requests.post(f"{self.url}/api/embed", json=corpo, timeout=self.timeout)
        if risposta.status_code == 404:
            vettori = []
            for testo in testi:
                vecchia = requests.post(
                    f"{self.url}/api/embeddings",
                    json={"model": self.modello, "prompt": testo},
                    timeout=self.timeout,
                )
                vecchia.raise_for_status()
                vettori.append(list((vecchia.json() or {}).get("embedding") or []))
        else:
            risposta.raise_for_status()
            vettori = list((risposta.json() or {}).get("embeddings") or [])
        if len(vettori) != len(testi):
            raise RuntimeError(f"Ollama ha restituito {len(vettori)} embedding per {len(testi)} testi")
        matrice = np.asarray(vettori, dtype=np.float32)
        if self.dimensioni and matrice.shape[1] > self.dimensioni:
            matrice = matrice[:, : self.dimensioni]
        return normalizza_righe(matrice)

    def embed(self, testi: list[str]) -> np.ndarray:
        if not testi:
            return np.zeros((0, max(1, self.dimensioni)), dtype=np.float32)
        parti = max(1, min(int(self.paralleli or 1), len(testi)))
        if parti == 1:
            return self._embed_con_tentativi(testi)
        # Il batch viene diviso in `parti` richieste contemporanee; l'ordine dei risultati e' preservato.
        from concurrent.futures import ThreadPoolExecutor

        passo = -(-len(testi) // parti)
        blocchi = [testi[i : i + passo] for i in range(0, len(testi), passo)]
        with ThreadPoolExecutor(max_workers=len(blocchi)) as esecutore:
            risultati = list(esecutore.map(self._embed_con_tentativi, blocchi))
        return np.vstack(risultati)

    def embed_singolo(self, testi: list[str]) -> np.ndarray:
        """Una sola richiesta (con tentativi), senza dividere: usata da chi gestisce le richieste in volo."""

        return self._embed_con_tentativi(testi)

    def _embed_con_tentativi(self, testi: list[str]) -> np.ndarray:
        ultimo: Exception | None = None
        for tentativo in range(max(1, self.tentativi)):
            try:
                return self._embed_una_volta(testi)
            except Exception as exc:  # rete, timeout, 5xx: si riprova con attesa crescente
                ultimo = exc
                if tentativo + 1 < self.tentativi:
                    time.sleep(self.attesa_s * (2**tentativo))
        raise RuntimeError(f"embedding non riuscito dopo {self.tentativi} tentativi: {ultimo}") from ultimo


class EmbedderFinto:
    """Embedding deterministico (hashing delle radici e delle coppie di radici) per i test.

    Non è un modello semantico: misura solo che la pipeline vettoriale funzioni, con numeri
    ripetibili e senza rete.
    """

    def __init__(self, dimensioni: int = 256, *, modello: str = "finto-hash") -> None:
        self.dimensioni = int(dimensioni)
        self.modello = f"{modello}-{self.dimensioni}"

    def versione(self) -> str:
        return "v1"

    def _indice(self, voce: str) -> tuple[int, float]:
        impronta = hashlib.blake2b(voce.encode("utf-8"), digest_size=8).digest()
        valore = int.from_bytes(impronta, "little")
        return valore % self.dimensioni, (1.0 if (valore >> 63) & 1 else -1.0)

    def embed(self, testi: list[str]) -> np.ndarray:
        matrice = np.zeros((len(testi), self.dimensioni), dtype=np.float32)
        for riga, testo in enumerate(testi):
            corpo = re.sub(r"^(task: search result \| query: |title: .*? \| text: )", "", str(testo or ""))
            radici = termini_indice(corpo)
            for voce in [*radici, *(f"{a}_{b}" for a, b in zip(radici, radici[1:]))]:
                colonna, segno = self._indice(voce)
                matrice[riga, colonna] += segno * (1.0 / math.sqrt(1 + voce.count("_")))
        return normalizza_righe(matrice)


class EmbedderNonDisponibile(RuntimeError):
    pass


class EmbedderDomande:
    """Embedding della domanda con timeout breve e pausa dopo un errore (Ollama spento o lento)."""

    def __init__(self, embedder: Embedder, *, pausa_dopo_errore_s: float = 60.0) -> None:
        self.embedder = embedder
        self.pausa = pausa_dopo_errore_s
        self._fermo_fino_a = 0.0
        self.ultimo_errore = ""

    def vettore(self, domanda: str) -> np.ndarray:
        if time.monotonic() < self._fermo_fino_a:
            raise EmbedderNonDisponibile(self.ultimo_errore or "embedding temporaneamente non disponibile")
        try:
            return self.embedder.embed([PREFISSO_DOMANDA + str(domanda or "")])[0]
        except Exception as exc:
            self.ultimo_errore = f"{type(exc).__name__}: {exc}"
            self._fermo_fino_a = time.monotonic() + self.pausa
            raise EmbedderNonDisponibile(self.ultimo_errore) from exc


def testo_documento(titolo: str, testo: str, *, massimo: int = 2400) -> str:
    titolo_pulito = " ".join(str(titolo or "").split()) or "none"
    corpo = " ".join(str(testo or "").split())[:massimo]
    return PREFISSO_DOCUMENTO.format(titolo=titolo_pulito) + corpo


__all__ = [
    "EmbedderDomande",
    "EmbedderFinto",
    "EmbedderNonDisponibile",
    "MODELLO_PREDEFINITO",
    "OllamaEmbedder",
    "PREFISSO_DOCUMENTO",
    "PREFISSO_DOMANDA",
    "base_ollama",
    "modello_configurato",
    "normalizza_righe",
    "testo_documento",
    "url_configurato",
]
