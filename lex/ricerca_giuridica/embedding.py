"""Embedding per la ricerca semantica: Ollama (embeddinggemma) e un embedder finto deterministico per i test.

Configurazione (stesso Ollama e stesso modello di embedding del server):

- ``LEX_EMBED_MODEL``, altrimenti ``PCT_LOCAL_AI_EMBED_MODEL``, altrimenti ``embeddinggemma:300m``;
- ``LEX_EMBED_URL``, altrimenti ``PCT_LOCAL_AI_BASE_URL``, ``OLLAMA_URL``, ``http://127.0.0.1:11434``;
- ``LEX_EMBED_TIMEOUT_S`` (domanda, default 4 s) — la ricerca semantica non deve mai bloccare Lex.

EmbeddingGemma è addestrato con prefissi di compito: ``task: search result | query: `` per la
domanda e ``title: … | text: `` per il documento. I prefissi fanno parte dei metadati dell'indice.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import math
import os
import re
import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from .testo import termini_indice

logger = logging.getLogger(__name__)

MODELLO_PREDEFINITO = "embeddinggemma:300m"
_RE_CONTROLLO = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffe\uffff]")


_SEGNI_GUASTO_SERVER = (
    "llama-server", "process has terminated", "segmentation fault", "timed out waiting",
    "unable to load", "failed to load", "cuda error", "out of memory", "no compatible gpu",
)


def _errore_del_contenuto(exc: BaseException) -> bool:
    """True se Ollama ha risposto con un errore HTTP (il problema e' nel testo), False se non risponde."""

    causa = exc.__cause__ or exc
    risposta = getattr(causa, "response", None)
    if risposta is None or getattr(risposta, "status_code", 0) < 400:
        return False
    try:
        dettaglio = str(getattr(risposta, "text", "") or "").lower()
    except Exception:
        dettaglio = ""
    # il modello non si carica (GPU non disponibile, driver, memoria): il problema non e' nel testo
    return not any(segno in dettaglio for segno in _SEGNI_GUASTO_SERVER)
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


class IstanzeOllamaDiverse(RuntimeError):
    """Le istanze Ollama indicate hanno pesi diversi dello stesso modello."""


def _digest_istanza(url: str, modello: str, timeout: float) -> str:
    import requests

    try:
        risposta = requests.get(f"{url}/api/tags", timeout=min(timeout, 10.0))
        risposta.raise_for_status()
        for voce in list((risposta.json() or {}).get("models") or []):
            nomi = {str(voce.get("name") or ""), str(voce.get("model") or "")}
            if modello in nomi or f"{modello}:latest" in nomi:
                return str(voce.get("digest") or "")
    except Exception:
        return ""
    return ""


@dataclass
class OllamaEmbedder:
    """Embedding via Ollama ``/api/embed`` (batch); ``/api/embeddings`` per le versioni vecchie."""

    modello: str = ""
    url: str = ""
    timeout: float = 120.0
    tentativi: int = 3
    attesa_s: float = 1.0
    dimensioni: int = 0  # >0: troncamento Matryoshka (embeddinggemma supporta 768/512/256/128)
    keep_alive: str = ""  # "" = LEX_EMBED_KEEP_ALIVE o 24h: il modello resta caricato e la domanda non aspetta il caricamento
    testi_ridotti: list = field(default_factory=list)  # (inizio testo, caratteri originali, caratteri usati)
    paralleli: int = 0  # richieste contemporanee per batch (0 = LEX_EMBED_PARALLELI o 1); serve OLLAMA_NUM_PARALLEL sul server Ollama

    def __post_init__(self) -> None:
        self.modello = self.modello or modello_configurato()
        self.keep_alive = str(self.keep_alive or os.getenv("LEX_EMBED_KEEP_ALIVE", "") or "24h").strip()
        # piu' istanze Ollama separate da virgola (stesso modello): le richieste vengono distribuite a turno.
        # Misurato: una singola istanza non accelera con OLLAMA_NUM_PARALLEL; piu' istanze lavorano davvero insieme.
        indirizzi = [base_ollama(u) for u in str(self.url or url_configurato()).split(",") if u.strip()]
        self.urls: list[str] = indirizzi or [base_ollama("")]
        self.url = self.urls[0]
        self._turno = itertools.count()
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
        if versione and len(self.urls) > 1:
            for altro in self.urls[1:]:
                diverso = _digest_istanza(altro, self.modello, self.timeout)
                if diverso != versione:
                    raise IstanzeOllamaDiverse(
                        f"l'istanza Ollama {altro} ha una versione diversa del modello {self.modello} "
                        f"({diverso or 'assente'} invece di {versione}): non si mescolano vettori diversi"
                    )
        self._digest = versione
        return versione

    def _prossimo_url(self) -> str:
        return self.urls[next(self._turno) % len(self.urls)]

    def _embed_una_volta(self, testi: list[str]) -> np.ndarray:
        import requests

        corpo: dict[str, Any] = {"model": self.modello, "input": list(testi), "truncate": True, "keep_alive": self.keep_alive}
        url = self._prossimo_url()
        risposta = requests.post(f"{url}/api/embed", json=corpo, timeout=self.timeout)
        if risposta.status_code == 404:
            vettori = []
            for testo in testi:
                vecchia = requests.post(
                    f"{url}/api/embeddings",
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
            return self.embed_singolo(testi)
        # Il batch viene diviso in `parti` richieste contemporanee; l'ordine dei risultati e' preservato.
        from concurrent.futures import ThreadPoolExecutor

        passo = -(-len(testi) // parti)
        blocchi = [testi[i : i + passo] for i in range(0, len(testi), passo)]
        with ThreadPoolExecutor(max_workers=len(blocchi)) as esecutore:
            risultati = list(esecutore.map(self.embed_singolo, blocchi))
        return np.vstack(risultati)

    def embed_singolo(self, testi: list[str]) -> np.ndarray:
        """Una richiesta (con tentativi). Se Ollama rifiuta il lotto con un errore HTTP, il lotto viene
        diviso a meta' fino a isolare il testo che lo fa fallire, che viene poi accorciato
        (``_embed_testo_difficile``): un solo chunk anomalo non ferma la costruzione dell'indice."""

        try:
            return self._embed_con_tentativi(testi)
        except RuntimeError as exc:
            if not _errore_del_contenuto(exc):
                raise  # Ollama spento o irraggiungibile: inutile dividere
            if len(testi) > 1:
                meta = len(testi) // 2
                return np.vstack([self.embed_singolo(testi[:meta]), self.embed_singolo(testi[meta:])])
            return self._embed_testo_difficile(testi[0], exc)

    def _embed_testo_difficile(self, testo: str, errore: Exception) -> np.ndarray:
        pulito = _RE_CONTROLLO.sub(" ", str(testo or ""))
        for limite in (len(pulito), 1500, 800, 300):
            ridotto = pulito[:limite]
            try:
                vettore = self._embed_una_volta([ridotto])
            except Exception:
                continue
            self.testi_ridotti.append((testo[:120], len(testo), len(ridotto)))
            logger.warning(
                "embedding: testo rifiutato da Ollama (%s), indicizzato accorciato a %d caratteri su %d: %r",
                errore, len(ridotto), len(testo), testo[:120],
            )
            return vettore
        raise RuntimeError(f"embedding non riuscito anche accorciando il testo: {testo[:120]!r}") from errore

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
    """Embedding della domanda con timeout breve e pausa dopo un errore (Ollama spento o lento).

    Se la domanda scade perche' il modello si sta ancora caricando (primo uso, server appena
    riavviato), in sottofondo parte un riscaldamento con timeout lungo: appena il modello e'
    pronto la pausa finisce e le domande successive usano di nuovo la ricerca semantica.
    """

    def __init__(self, embedder: Embedder, *, pausa_dopo_errore_s: float = 60.0, timeout_riscaldamento_s: float = 180.0) -> None:
        self.embedder = embedder
        self.pausa = pausa_dopo_errore_s
        self.timeout_riscaldamento = timeout_riscaldamento_s
        self._fermo_fino_a = 0.0
        self.ultimo_errore = ""
        self._riscaldamento: threading.Thread | None = None
        self._lock = threading.Lock()

    def vettore(self, domanda: str) -> np.ndarray:
        if time.monotonic() < self._fermo_fino_a:
            raise EmbedderNonDisponibile(self.ultimo_errore or "embedding temporaneamente non disponibile")
        try:
            return self.embedder.embed([PREFISSO_DOMANDA + str(domanda or "")])[0]
        except Exception as exc:
            self.ultimo_errore = f"{type(exc).__name__}: {exc}"
            self._fermo_fino_a = time.monotonic() + self.pausa
            if _e_timeout(exc):  # il modello si sta caricando: lo si aspetta in sottofondo
                self.riscalda_in_sottofondo()
            raise EmbedderNonDisponibile(self.ultimo_errore) from exc

    def riscalda(self, timeout: float | None = None) -> bool:
        """Carica il modello in Ollama con un timeout lungo; True se pronto (e la pausa viene tolta)."""

        lento = _copia_con_timeout(self.embedder, float(timeout or self.timeout_riscaldamento))
        try:
            lento.embed([PREFISSO_DOMANDA + "riscaldamento"])
        except Exception as exc:
            self.ultimo_errore = f"{type(exc).__name__}: {exc}"
            return False
        self._fermo_fino_a = 0.0
        self.ultimo_errore = ""
        return True

    def riscalda_in_sottofondo(self) -> None:
        with self._lock:
            if self._riscaldamento is not None and self._riscaldamento.is_alive():
                return
            self._riscaldamento = threading.Thread(target=self.riscalda, name="lex-embed-riscaldamento", daemon=True)
            self._riscaldamento.start()


def _e_timeout(exc: BaseException | None) -> bool:
    visti = 0
    while exc is not None and visti < 6:
        nome = type(exc).__name__.lower()
        if "timeout" in nome or "timed out" in str(exc).lower():
            return True
        exc = exc.__cause__ or exc.__context__
        visti += 1
    return False


def _copia_con_timeout(embedder: Any, timeout: float) -> Any:
    if not hasattr(embedder, "timeout"):
        return embedder
    copia = copy.copy(embedder)
    copia.timeout = max(float(getattr(embedder, "timeout", 0) or 0), timeout)
    if hasattr(copia, "tentativi"):
        copia.tentativi = 1
    return copia


def testo_documento(titolo: str, testo: str, *, massimo: int = 2400) -> str:
    titolo_pulito = " ".join(str(titolo or "").split()) or "none"
    corpo = " ".join(str(testo or "").split())[:massimo]
    return PREFISSO_DOCUMENTO.format(titolo=titolo_pulito) + corpo


__all__ = [
    "EmbedderDomande",
    "EmbedderFinto",
    "EmbedderNonDisponibile",
    "IstanzeOllamaDiverse",
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
