"""La lettura di una pagina: Tesseract, con la strategia che rende di piu'.

Il motore viene interrogato prima con l'impostazione giusta per un atto (un
blocco di testo uniforme). Se la lettura e' sicura ci si ferma: e' il caso
normale e costa una sola passata. Se e' povera o incerta si provano le altre
impostazioni in parallelo (colonne, impaginazione automatica, testo sparso) e
si tiene la migliore; se ancora non basta, si provano le versioni binarizzate
della pagina, che servono alle copie sbiadite. Ogni passata dichiara che cosa
ha fatto, cosi' il risultato dice con quale lettura e' stato ottenuto.

Il motore lavora con un thread per processo (`OMP_THREAD_LIMIT=1`): su una
pagina A4 a 300 dpi una passata costa circa un secondo, e le passate in
parallelo costano quanto una sola.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from .errori import MotoreNonDisponibile
from .immagine import varianti_contrasto
from .punteggio import confidenza_media, punteggio_lettura
from .runtime import configura, lingua_disponibile, lingue_installate

# Un atto puo' essere impaginato in modi diversi: una colonna, due colonne,
# moduli con campi sparsi. La prima e' quella giusta per quasi tutti gli atti.
CONFIGURAZIONI: tuple[tuple[str, str], ...] = (
    ("blocco unico", "--oem 1 --psm 6 -c preserve_interword_spaces=1"),
    ("colonne", "--oem 1 --psm 4 -c preserve_interword_spaces=1"),
    ("automatica", "--oem 1 --psm 3 -c preserve_interword_spaces=1"),
    ("testo sparso", "--oem 1 --psm 11 -c preserve_interword_spaces=1"),
)
# Sotto questa confidenza media la prima lettura non basta e si provano le altre.
CONFIDENZA_SICURA = 0.90
# Sotto questa quantita' di caratteri la pagina non e' stata letta davvero.
CARATTERI_MINIMI = 40
TIMEOUT_SECONDI = 180
LINGUA = "ita"

_LINGUA_VERIFICATA: dict[int, str] = {}
_VERIFICA = threading.Lock()


@dataclass(frozen=True)
class Lettura:
    """Le parole lette, con posizione e confidenza, e il PDF ricercabile della pagina."""

    parole: list[dict[str, Any]]
    testo: str
    configurazione: str
    opzioni: str
    confidenza: float
    pdf: bytes = b""
    passate: tuple[str, ...] = ()
    avvisi: tuple[str, ...] = ()
    secondi: float = 0.0
    variante: str = ""

    @property
    def caratteri(self) -> int:
        return sum(len(str(parola.get("text") or "")) for parola in self.parole)


@dataclass
class _Candidata:
    etichetta: str
    opzioni: str
    parole: list[dict[str, Any]] = field(default_factory=list)
    testo: str = ""
    punteggio: float = 0.0
    variante: str = ""
    immagine: Any = None


def parole_da_dati(dati: dict[str, Any]) -> list[dict[str, Any]]:
    """Parole con posizione e confidenza, dai dati grezzi del motore."""
    testi = list(dati.get("text") or [])
    parole: list[dict[str, Any]] = []
    for indice, grezzo in enumerate(testi):
        testo = str(grezzo or "").strip()
        if not testo:
            continue
        try:
            confidenza = max(0.0, min(1.0, float(dati.get("conf", ["-1"])[indice]) / 100.0))
        except (TypeError, ValueError, IndexError):
            confidenza = 0.0

        def valore(chiave: str) -> int:
            try:
                return int(dati.get(chiave, [0])[indice])
            except (TypeError, ValueError, IndexError):
                return 0

        parole.append({
            "text": testo,
            "left": valore("left"),
            "top": valore("top"),
            "width": valore("width"),
            "height": valore("height"),
            "conf": confidenza,
            "block": valore("block_num"),
            "par": valore("par_num"),
            "line": valore("line_num"),
        })
    return parole


def testo_per_righe(parole: list[dict[str, Any]]) -> str:
    """Le parole ricomposte in righe, nell'ordine dichiarato dal motore."""
    righe: list[list[str]] = []
    chiave_corrente: tuple[int, int, int] | None = None
    for parola in parole:
        chiave = (int(parola.get("block") or 0), int(parola.get("par") or 0), int(parola.get("line") or 0))
        if chiave != chiave_corrente:
            righe.append([])
            chiave_corrente = chiave
        righe[-1].append(str(parola.get("text") or ""))
    return "\n".join(" ".join(riga) for riga in righe)


def motore_pronto(pytesseract: object, *, lingua: str = LINGUA) -> str:
    """Configura il runtime e controlla che il dizionario richiesto esista."""
    identita = id(pytesseract)
    with _VERIFICA:
        pronta = _LINGUA_VERIFICATA.get(identita)
    if pronta:
        return pronta
    configura(pytesseract)
    try:
        lingue = lingue_installate(pytesseract)
    except Exception as exc:
        raise MotoreNonDisponibile("Il motore di riconoscimento del testo non è installato sul server.") from exc
    if not lingue:
        # Alcuni runtime non sanno elencare le lingue: si prova la richiesta.
        return lingua
    if lingua not in lingue:
        # Il dizionario manca: il motore prova a procurarselo dalla fonte
        # ufficiale, con l'impronta verificata, prima di fermarsi.
        from .provisioning import assicura_dizionario

        cartella = assicura_dizionario(lingua)
        if cartella:
            if os.environ.get("TESSDATA_PREFIX", "") != cartella:
                os.environ["TESSDATA_PREFIX"] = cartella
            lingue = lingue_installate(pytesseract)
        if lingua not in lingue:
            if lingua == LINGUA:
                raise MotoreNonDisponibile(
                    "Il dizionario italiano per il riconoscimento del testo non è installato sul server: "
                    "installa il pacchetto tesseract-ocr-ita (Linux) o esegui scripts/installa_tesseract_windows.ps1 (Windows)."
                )
            lingua = lingua_disponibile(pytesseract, lingua, "")
    with _VERIFICA:
        _LINGUA_VERIFICATA[identita] = lingua
    return lingua


def _tipo_dizionario(pytesseract: object) -> Any:
    uscita = getattr(pytesseract, "Output", None)
    if uscita is not None and hasattr(uscita, "DICT"):
        return uscita.DICT
    try:
        from pytesseract import Output  # type: ignore

        return Output.DICT
    except Exception:
        return "dict"


def _parole_da_testo(testo: str) -> list[dict[str, Any]]:
    """Parole senza posizione, da un motore che sa restituire solo il testo."""
    parole: list[dict[str, Any]] = []
    for numero_riga, riga in enumerate(str(testo or "").splitlines(), start=1):
        for parola in riga.split():
            parole.append({"text": parola, "left": 0, "top": 0, "width": max(1, len(parola) * 8), "height": 12, "conf": 0.9, "block": 1, "par": 1, "line": numero_riga})
    return parole


def _leggi(pytesseract: object, immagine: Any, *, lingua: str, opzioni: str, dpi: int, timeout: int) -> tuple[list[dict[str, Any]], str]:
    configurazione = f"{opzioni} --dpi {dpi}"
    leggi_dati = getattr(pytesseract, "image_to_data", None)
    if callable(leggi_dati):
        try:
            dati = leggi_dati(immagine, lang=lingua, config=configurazione, output_type=_tipo_dizionario(pytesseract), timeout=timeout)
        except TypeError:
            dati = leggi_dati(immagine, lang=lingua, config=configurazione, output_type=_tipo_dizionario(pytesseract))
        return parole_da_dati(dati if isinstance(dati, dict) else {}), configurazione
    # Runtime ridotto (o finto nei test) che sa restituire solo il testo.
    leggi_testo = getattr(pytesseract, "image_to_string", None)
    if not callable(leggi_testo):
        raise MotoreNonDisponibile("Il motore di riconoscimento del testo non è utilizzabile su questa installazione.")
    try:
        testo = leggi_testo(immagine, lang=lingua, config=configurazione, timeout=timeout)
    except TypeError:
        testo = leggi_testo(immagine, lang=lingua)
    return _parole_da_testo(str(testo or "")), configurazione


def _candidata(pytesseract: object, immagine: Any, etichetta: str, opzioni: str, *, lingua: str, dpi: int, timeout: int, variante: str = "") -> _Candidata | str:
    try:
        parole, configurazione = _leggi(pytesseract, immagine, lingua=lingua, opzioni=opzioni, dpi=dpi, timeout=timeout)
    except Exception as exc:
        return f"{etichetta}: {exc}"
    testo = testo_per_righe(parole)
    return _Candidata(etichetta, configurazione, parole, testo, punteggio_lettura(parole, testo), variante, immagine)


def _in_parallelo(lavori: list[tuple], funzione, *, paralleli: int) -> list:
    if len(lavori) <= 1 or paralleli <= 1:
        return [funzione(*lavoro) for lavoro in lavori]
    with ThreadPoolExecutor(max_workers=min(paralleli, len(lavori))) as esecutore:
        return list(esecutore.map(lambda lavoro: funzione(*lavoro), lavori))


def _paralleli_ammessi() -> int:
    try:
        return max(1, int(os.environ.get("IUSENTRA_OCR_LETTURE_PARALLELE", "3") or 3))
    except ValueError:
        return 3


def leggi_immagine(
    immagine: Any,
    *,
    pytesseract: object,
    lingua: str = LINGUA,
    dpi: int = 300,
    timeout: int = TIMEOUT_SECONDI,
    configurazioni: tuple[tuple[str, str], ...] = CONFIGURAZIONI,
    con_pdf: bool = True,
    tutte_le_configurazioni: bool = False,
) -> Lettura:
    """Legge la pagina gia' preparata e restituisce la lettura migliore.

    `tutte_le_configurazioni` forza tutte le passate anche quando la prima e'
    sicura: serve ai confronti e ai test, non all'uso normale.
    """
    inizio = time.monotonic()
    lingua = motore_pronto(pytesseract, lingua=lingua)
    avvisi: list[str] = []
    passate: list[str] = []
    candidate: list[_Candidata] = []

    def raccogli(esiti: list) -> None:
        for esito in esiti:
            if isinstance(esito, str):
                avvisi.append(f"Lettura non completata ({esito}).")
            else:
                candidate.append(esito)
                passate.append(esito.etichetta if not esito.variante else f"{esito.etichetta} su {esito.variante}")

    prima_etichetta, prima_opzioni = configurazioni[0]
    raccogli([_candidata(pytesseract, immagine, prima_etichetta, prima_opzioni, lingua=lingua, dpi=dpi, timeout=timeout)])
    prima = candidate[0] if candidate else None
    sicura = (
        prima is not None
        and sum(len(p["text"]) for p in prima.parole) >= CARATTERI_MINIMI
        and confidenza_media(prima.parole) >= CONFIDENZA_SICURA
    )
    if (not sicura or tutte_le_configurazioni) and len(configurazioni) > 1:
        lavori = [(pytesseract, immagine, etichetta, opzioni) for etichetta, opzioni in configurazioni[1:]]
        raccogli(_in_parallelo(lavori, lambda p, i, e, o: _candidata(p, i, e, o, lingua=lingua, dpi=dpi, timeout=timeout), paralleli=_paralleli_ammessi()))

    migliore = max(candidate, key=lambda voce: voce.punteggio) if candidate else None
    if migliore is None or sum(len(p["text"]) for p in migliore.parole) < CARATTERI_MINIMI:
        # Copia sbiadita o a basso contrasto: si prova la pagina binarizzata.
        lavori = [
            (pytesseract, variante, prima_etichetta, prima_opzioni, nome)
            for nome, variante in varianti_contrasto(immagine)
        ]
        raccogli(_in_parallelo(lavori, lambda p, i, e, o, v: _candidata(p, i, e, o, lingua=lingua, dpi=dpi, timeout=timeout, variante=v), paralleli=_paralleli_ammessi()))
        migliore = max(candidate, key=lambda voce: voce.punteggio) if candidate else None

    if migliore is None:
        return Lettura([], "", "", "", 0.0, b"", tuple(passate), tuple(avvisi), time.monotonic() - inizio)

    pdf = b""
    if con_pdf:
        try:
            pdf = bytes(pytesseract.image_to_pdf_or_hocr(migliore.immagine, lang=lingua, extension="pdf", config=migliore.opzioni, timeout=timeout) or b"")
        except Exception as exc:
            avvisi.append(f"PDF ricercabile non generato ({exc}).")
            pdf = b""
    return Lettura(
        parole=migliore.parole,
        testo=migliore.testo,
        configurazione=migliore.etichetta,
        opzioni=migliore.opzioni,
        confidenza=round(confidenza_media(migliore.parole), 4),
        pdf=pdf,
        passate=tuple(passate),
        avvisi=tuple(avvisi),
        secondi=round(time.monotonic() - inizio, 3),
        variante=migliore.variante,
    )


def leggi_testo(immagine: Any, *, pytesseract: object, lingua: str = LINGUA, opzioni: str, dpi: int = 300, timeout: int = 30) -> list[dict[str, Any]]:
    """Una sola passata con opzioni esplicite (riquadri, campi corti): le parole lette."""
    lingua = motore_pronto(pytesseract, lingua=lingua)
    parole, _ = _leggi(pytesseract, immagine, lingua=lingua, opzioni=opzioni, dpi=dpi, timeout=timeout)
    return parole


__all__ = [
    "CARATTERI_MINIMI",
    "CONFIDENZA_SICURA",
    "CONFIGURAZIONI",
    "LINGUA",
    "Lettura",
    "leggi_immagine",
    "leggi_testo",
    "motore_pronto",
    "parole_da_dati",
    "testo_per_righe",
]
