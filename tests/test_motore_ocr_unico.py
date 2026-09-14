"""Il motore di lettura unico: strategia, consenso, impaginazione e provisioning.

Nessun Tesseract reale: il motore viene sostituito da un finto runtime che
risponde per configurazione, cosi' la strategia (prima passata sicura, altre
passate solo se serve, binarizzazione per le copie sbiadite) e' verificabile
in modo deterministico.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from legal_ocr.formato import ALLINEAMENTO_GIUSTIFICATO, blocchi_con_formato
from legal_ocr.motore import consenso, lettura, provisioning
from legal_ocr.motore.consenso import LetturaSecondaria, applica_consenso
from legal_ocr.motore.lettura import CONFIGURAZIONI, leggi_immagine
from legal_ocr.page_layout import ELENCO, NUMERO_PAGINA, PARAGRAFO, analizza_pagina, gruppi_di_elenco


def _dati(parole: list[tuple[str, float]], *, riga: int = 1) -> dict:
    return {
        "text": [testo for testo, _ in parole],
        "conf": [str(round(conf * 100)) for _, conf in parole],
        "left": [10 + 60 * indice for indice in range(len(parole))],
        "top": [100 + 30 * riga] * len(parole),
        "width": [50] * len(parole),
        "height": [20] * len(parole),
        "block_num": [1] * len(parole),
        "par_num": [1] * len(parole),
        "line_num": [riga] * len(parole),
    }


class FintoTesseract:
    """Risponde per configurazione e conta le passate."""

    class Output:
        DICT = "dict"

    def __init__(self, risposte: dict[str, list[tuple[str, float]]], *, binarizzata: list[tuple[str, float]] | None = None):
        self.risposte = risposte
        self.binarizzata = binarizzata
        self.passate: list[str] = []
        self.pdf_config = ""

    def get_languages(self, config=""):
        return ["ita", "eng", "osd"]

    def image_to_data(self, image, lang, config, output_type, timeout):
        self.passate.append(config)
        if getattr(image, "mode", "") == "1" and self.binarizzata is not None:
            return _dati(self.binarizzata)
        for chiave, parole in self.risposte.items():
            if chiave in config:
                return _dati(parole)
        return _dati([])

    def image_to_pdf_or_hocr(self, image, lang, extension, config, timeout):
        self.pdf_config = config
        return b"%PDF-1.4 finto"


def _immagine() -> Image.Image:
    return Image.new("L", (400, 200), 255)


def test_la_prima_passata_sicura_basta_e_costa_una_sola_lettura():
    parole = [(p, 0.96) for p in "TRIBUNALE DI MILANO Sezione IV civile atto di citazione ai sensi".split()]
    motore = FintoTesseract({"--psm 6": parole})
    esito = leggi_immagine(_immagine(), pytesseract=motore, dpi=300)
    assert esito.configurazione == "blocco unico"
    assert len(motore.passate) == 1
    assert esito.pdf.startswith(b"%PDF-") and "--psm 6" in motore.pdf_config and "--dpi 300" in motore.pdf_config
    assert esito.passate == ("blocco unico",)


def test_una_prima_passata_incerta_apre_le_altre_configurazioni_e_vince_la_migliore():
    incerta = [(p, 0.55) for p in "TRIBUNALE DI MILANO Sezione IV civile atto di citazione ai sensi".split()]
    sicura = [(p, 0.97) for p in "TRIBUNALE DI MILANO Sezione IV civile atto di citazione ai sensi".split()]
    motore = FintoTesseract({"--psm 6": incerta, "--psm 4": sicura})
    esito = leggi_immagine(_immagine(), pytesseract=motore, dpi=300)
    assert esito.configurazione == "colonne"
    assert len(motore.passate) >= len(CONFIGURAZIONI)
    assert "--psm 4" in motore.pdf_config


def test_la_copia_sbiadita_si_legge_binarizzata():
    motore = FintoTesseract({}, binarizzata=[("TRIBUNALE", 0.93), ("DI", 0.9), ("VICENZA", 0.94), ("CONTRATTO", 0.92), ("2024", 0.95)])
    esito = leggi_immagine(_immagine(), pytesseract=motore, dpi=300)
    assert esito.testo == "TRIBUNALE DI VICENZA CONTRATTO 2024"
    assert esito.variante.startswith("contrasto-")


def test_il_dizionario_italiano_mancante_ferma_il_motore_con_messaggio_chiaro(monkeypatch):
    class SenzaItaliano(FintoTesseract):
        def get_languages(self, config=""):
            return ["eng"]

    monkeypatch.setattr(provisioning, "assicura_dizionario", lambda lingua="ita": "")
    with pytest.raises(lettura.MotoreNonDisponibile, match="dizionario italiano"):
        leggi_immagine(_immagine(), pytesseract=SenzaItaliano({}), dpi=300)


# ── Secondo lettore ───────────────────────────────────────────────────────


def _parole(*coppie: tuple[str, float]) -> list[dict]:
    return [
        {"text": testo, "conf": conf, "left": 10 + 60 * i, "top": 100, "width": 50, "height": 20, "block": 1, "par": 1, "line": 1}
        for i, (testo, conf) in enumerate(coppie)
    ]


def test_il_secondo_lettore_corregge_solo_le_parole_incerte():
    parole = _parole(("Tribunale", 0.95), ("di", 0.9), ("Miiano", 0.41), ("Sezione", 0.96), ("Vl", 0.5))
    secondaria = LetturaSecondaria("Tribunale di Milano Sezione VI", 0.99, "pdf-inspector:pp-ocr", 0.4)
    nuove, sostituite = applica_consenso(parole, secondaria)
    assert sostituite == 2
    assert [p["text"] for p in nuove] == ["Tribunale", "di", "Milano", "Sezione", "VI"]
    assert nuove[2]["consenso"] is True and nuove[0].get("consenso") is None


def test_il_secondo_lettore_incerto_o_diverso_non_tocca_nulla():
    parole = _parole(("Tribunale", 0.95), ("di", 0.9), ("Miiano", 0.41))
    assert applica_consenso(parole, LetturaSecondaria("Tribunale di Milano", 0.6, "x", 0.1))[1] == 0
    assert applica_consenso(parole, LetturaSecondaria("Corte di Cassazione sezione lavoro", 0.99, "x", 0.1))[1] == 0
    assert applica_consenso(parole, None)[1] == 0


def test_il_secondo_lettore_e_disponibile_solo_con_modelli_installati(monkeypatch, tmp_path: Path):
    consenso.azzera_verifica()
    monkeypatch.setenv("IUSENTRA_PDF_OCR_MODEL_DIR", str(tmp_path / "assente"))
    monkeypatch.setattr(consenso, "CARTELLA_MODELLI_PREDEFINITA", str(tmp_path / "assente2"))
    assert consenso.secondo_lettore_disponibile() is False
    consenso.azzera_verifica()
    monkeypatch.setenv("IUSENTRA_OCR_SECONDO_LETTORE", "0")
    assert consenso.secondo_lettore_disponibile() is False
    consenso.azzera_verifica()


# ── Impaginazione: elenchi, numeri di pagina, giustificato ───────────────


def _riga(parole: list[str], alto: int, *, sinistra: int = 100, riga: int = 1, blocco: int = 1, larghezza: int = 60) -> list[dict]:
    return [
        {"text": p, "left": sinistra + i * (larghezza + 10), "top": alto, "width": larghezza, "height": 20, "conf": 0.95, "block": blocco, "par": 1, "line": riga}
        for i, p in enumerate(parole)
    ]


def test_le_voci_di_elenco_portano_il_marcatore_e_formano_un_solo_elenco():
    parole = _riga(["Motivi:"], 100)
    parole += _riga(["a)", "primo", "motivo"], 130, riga=2)
    parole += _riga(["b)", "secondo", "motivo"], 160, riga=3)
    parole += _riga(["c)", "terzo", "motivo"], 190, riga=4)
    blocchi = analizza_pagina(parole)
    voci = [b for b in blocchi if b.tipo == ELENCO]
    assert [v.marcatore.valore for v in voci] == [1, 2, 3]
    assert voci[0].voce == "primo motivo" and voci[0].marcatore.tipo == "lettera"
    assert gruppi_di_elenco(blocchi) == [[1, 2, 3]]
    assert blocchi[1].come_dizionario()["marcatore"]["testo"] == "a)"


def test_la_riga_di_continuazione_rientrata_resta_nella_stessa_voce():
    parole = _riga(["1)", "la", "prima", "voce", "continua"], 100)
    parole += _riga(["sulla", "riga", "seguente"], 122, sinistra=135, riga=2)
    parole += _riga(["2)", "seconda", "voce"], 152, riga=3)
    blocchi = analizza_pagina(parole)
    assert [b.tipo for b in blocchi] == [ELENCO, ELENCO]
    assert blocchi[0].testo == "1) la prima voce continua sulla riga seguente"


def test_il_numero_di_pagina_in_coda_esce_dal_testo():
    parole = _riga(["Il", "testo", "dell'atto", "prosegue", "regolarmente."], 100)
    parole += _riga(["Seconda", "riga", "del", "corpo", "dell'atto."], 130, riga=2)
    parole += _riga(["3"], 1400, sinistra=400, riga=3, blocco=2)
    blocchi = analizza_pagina(parole)
    assert blocchi[-1].tipo == NUMERO_PAGINA
    assert blocchi[0].tipo == PARAGRAFO


def test_il_capoverso_a_filo_di_entrambi_i_margini_e_giustificato():
    parole: list[dict] = []
    for riga in range(1, 5):
        parole += _riga(["parola"] * 8, 100 + 24 * riga, riga=riga, larghezza=60)
    parole += _riga(["fine."], 220, riga=5)
    blocchi = analizza_pagina(parole)
    formati = blocchi_con_formato(blocchi, parole)
    assert formati[0]["formato"]["allineamento"] == ALLINEAMENTO_GIUSTIFICATO


# ── Provisioning ──────────────────────────────────────────────────────────


def test_il_dizionario_scaricato_vale_solo_con_impronta_verificata(monkeypatch, tmp_path: Path):
    provisioning._TENTATO.clear()
    buono = b"x" * 1_000_001
    impronta = hashlib.sha256(buono).hexdigest()
    monkeypatch.setitem(provisioning.DIZIONARI, "ita", (("https://esempio.invalid/ita",), impronta, 1_000_000))
    monkeypatch.setenv("IUSENTRA_TESSDATA_PREFIX", str(tmp_path / "tessdata"))
    monkeypatch.setattr(provisioning, "cartella_tessdata_di_sistema", lambda: None)
    monkeypatch.setattr(provisioning, "_scarica", lambda url, timeout=120: b"y" * 1_000_001)
    assert provisioning.assicura_dizionario("ita") == ""
    provisioning._TENTATO.clear()
    monkeypatch.setattr(provisioning, "_scarica", lambda url, timeout=120: buono)
    cartella = provisioning.assicura_dizionario("ita")
    assert cartella == str(tmp_path / "tessdata")
    assert (tmp_path / "tessdata" / "ita.traineddata").read_bytes() == buono
    provisioning._TENTATO.clear()


def test_il_provisioning_si_puo_disattivare(monkeypatch):
    monkeypatch.setenv("IUSENTRA_OCR_AUTOPROVISION", "0")
    assert provisioning.assicura_dizionario("ita") == ""
