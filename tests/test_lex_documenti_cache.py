"""Memoria del testo estratto dai documenti per le domande a Lex.

Lex rileggeva ogni documento del fascicolo a ogni domanda: con dodici PDF di
quattro pagine servivano circa nove secondi per rispondere, e la domanda
successiva ricominciava da capo.
"""

from __future__ import annotations

import time
from pathlib import Path

from lex.retrieval.documenti_cache import MemoriaEstrazioni


def test_un_documento_immutato_viene_letto_una_volta_sola(tmp_path: Path):
    atto = tmp_path / "memoria.pdf"
    atto.write_bytes(b"%PDF contenuto dell'atto")
    letture: list[str] = []

    memoria = MemoriaEstrazioni()

    def leggi() -> str:
        letture.append("lettura")
        return "testo estratto"

    for _ in range(5):
        assert memoria.ottieni(atto, "testo", leggi) == "testo estratto"

    assert letture == ["lettura"], "il documento non doveva essere riletto"
    assert memoria.statistiche()["riusi"] == 4


def test_un_documento_sostituito_viene_riletto(tmp_path: Path):
    """Se l'avvocato sostituisce l'atto, Lex deve vedere il nuovo testo."""

    atto = tmp_path / "memoria.pdf"
    atto.write_bytes(b"%PDF prima versione")
    memoria = MemoriaEstrazioni()

    assert memoria.ottieni(atto, "testo", lambda: "prima versione") == "prima versione"

    #  La firma comprende data di modifica e dimensione: serve che cambino
    #  davvero, non basta riscrivere gli stessi byte nello stesso istante.
    time.sleep(0.01)
    atto.write_bytes(b"%PDF seconda versione, piu' lunga")

    assert memoria.ottieni(atto, "testo", lambda: "seconda versione") == "seconda versione"


def test_ambiti_diversi_non_si_sovrappongono(tmp_path: Path):
    """Testo semplice e analisi Docling sono due letture distinte."""

    atto = tmp_path / "memoria.pdf"
    atto.write_bytes(b"%PDF contenuto")
    memoria = MemoriaEstrazioni()

    assert memoria.ottieni(atto, "testo", lambda: "solo testo") == "solo testo"
    assert memoria.ottieni(atto, "docling:D1", lambda: "analisi") == "analisi"
    #  Ogni ambito conserva il proprio valore.
    assert memoria.ottieni(atto, "testo", lambda: "mai chiamata") == "solo testo"


def test_un_documento_sparito_non_viene_memorizzato(tmp_path: Path):
    """Meglio rifare il lavoro che servire un documento che non c'e' piu'."""

    assente = tmp_path / "mai-esistito.pdf"
    letture: list[str] = []
    memoria = MemoriaEstrazioni()

    def leggi() -> str:
        letture.append("lettura")
        return ""

    memoria.ottieni(assente, "testo", leggi)
    memoria.ottieni(assente, "testo", leggi)

    assert len(letture) == 2
    assert memoria.statistiche()["voci"] == 0


def test_la_memoria_non_cresce_oltre_la_capacita(tmp_path: Path):
    """Un processo che lavora su molti fascicoli non deve gonfiarsi."""

    memoria = MemoriaEstrazioni(capacita=3)
    for indice in range(10):
        atto = tmp_path / f"atto_{indice}.pdf"
        atto.write_bytes(b"%PDF " + str(indice).encode())
        memoria.ottieni(atto, "testo", lambda i=indice: f"testo {i}")

    statistiche = memoria.statistiche()
    assert statistiche["voci"] == 3
    assert statistiche["capacita"] == 3


def test_la_voce_piu_vecchia_esce_per_prima(tmp_path: Path):
    memoria = MemoriaEstrazioni(capacita=2)
    atti = []
    for indice in range(3):
        atto = tmp_path / f"atto_{indice}.pdf"
        atto.write_bytes(b"%PDF " + str(indice).encode())
        atti.append(atto)

    memoria.ottieni(atti[0], "testo", lambda: "zero")
    memoria.ottieni(atti[1], "testo", lambda: "uno")
    #  Rileggo il primo: torna in coda e non deve essere il prossimo a uscire.
    memoria.ottieni(atti[0], "testo", lambda: "mai chiamata")
    memoria.ottieni(atti[2], "testo", lambda: "due")

    riletture: list[str] = []
    memoria.ottieni(atti[0], "testo", lambda: riletture.append("zero") or "zero")
    assert riletture == [], "il primo atto doveva essere ancora in memoria"


#  ---------------------------------------------------------------------------
#  Atti firmati: il registro e il disco possono non concordare sul suffisso
#  ---------------------------------------------------------------------------


def test_latto_firmato_viene_letto_anche_se_su_disco_manca_il_suffisso(tmp_path: Path):
    """Il registro dichiara `.pdf.p7m`, su disco c'e' il PDF.

    Finche' si cercava solo il percorso esatto, gli atti depositati risultavano
    privi di contenuto: Lex li elencava senza poterli leggere, cioe' proprio i
    documenti che contano di piu' in un fascicolo.
    """

    from types import SimpleNamespace

    from lex.retrieval.documenti import _document_path

    documenti = tmp_path / "documenti"
    (documenti / "F1").mkdir(parents=True)
    su_disco = documenti / "F1" / "SentenzaDefinitiva.pdf"
    su_disco.write_bytes(b"%PDF sentenza")

    doc = SimpleNamespace(percorso="F1/SentenzaDefinitiva.pdf.p7m")

    assert _document_path(doc, documenti) == su_disco


def test_latto_viene_letto_anche_se_su_disco_c_e_la_busta_di_firma(tmp_path: Path):
    """Caso opposto: il registro dichiara il PDF, su disco c'e' il `.p7m`."""

    from types import SimpleNamespace

    from lex.retrieval.documenti import _document_path

    documenti = tmp_path / "documenti"
    (documenti / "F1").mkdir(parents=True)
    su_disco = documenti / "F1" / "Ricorso.pdf.p7m"
    su_disco.write_bytes(b"busta di firma")

    doc = SimpleNamespace(percorso="F1/Ricorso.pdf")

    assert _document_path(doc, documenti) == su_disco


def test_un_documento_davvero_assente_resta_assente(tmp_path: Path):
    from types import SimpleNamespace

    from lex.retrieval.documenti import _document_path

    documenti = tmp_path / "documenti"
    documenti.mkdir()

    assert _document_path(SimpleNamespace(percorso="F1/mai-esistito.pdf"), documenti) is None
    assert _document_path(SimpleNamespace(percorso=""), documenti) is None
