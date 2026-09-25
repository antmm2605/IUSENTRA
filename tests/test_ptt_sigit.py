"""Dominio del Processo Tributario Telematico: catalogo, CUT, termini, regole dei file, parti, scheda."""

from __future__ import annotations

from datetime import date

from pct.ptt_sigit import catalogo, cut, parti, regole, scheda, termini
from tests.test_pat_formweb import pdf_pades
from tests.test_penale_pdp import pdf_testo


def test_corti_dal_dgt_e_competenza():
    sedi = catalogo.sedi()
    assert sum(1 for s in sedi if s["grado"] == "1") == 103 and sum(1 for s in sedi if s["grado"] == "2") == 36
    bari = catalogo.sede("PBA")
    assert bari["nome"] == "Corte di Giustizia Tributaria di primo grado di Bari" and bari["pec"].endswith("@pce.finanze.it")
    assert catalogo.sede_da_testo("Commissione tributaria provinciale di Reggio Calabria") == "PRC"
    assert catalogo.sede_da_testo("CGT di secondo grado della Sicilia sezione staccata di Catania") == "SCT"
    assert catalogo.sede_da_testo("Corte di giustizia tributaria di secondo grado del Lazio") == "RRM"
    assert catalogo.sede_da_testo("Tribunale di Roma") == ""
    assert catalogo.sede_per_provincia("MB") == "PMI" and catalogo.sede_per_provincia("RC") == "PRC"
    assert "PROCURA-NOMINA DEL DIFENSORE" in catalogo.ALTRI_ATTI and len(catalogo.ATTI_PRINCIPALI) == 12


def test_cut_scaglioni_somma_e_maggiorazione():
    assert [cut.per_atto(v) for v in (2582.28, 2582.29, 5000, 25000, 75000, 200000, 200000.01)] == [30, 60, 60, 120, 250, 500, 1500]
    assert cut.per_atto(None) == 1500 and cut.per_atto(None, indeterminabile=True) == 120
    assert cut.valore_lite("", "1.200,50") == 1200.5
    esito = cut.calcola([{"tributo": "3000"}, {"tributo": "80.000,00"}], pec_difensore=False)
    assert esito["base"] == 560 and esito["maggiorazione"] == 280 and esito["totale"] == 840
    assert cut.calcola([{"tributo": "3000"}], esenzione="Prenotazione a debito")["totale"] == 0


def test_termini_costituzione_con_sospensione_feriale():
    # Notifica il 20 luglio: 11 giorni a luglio, agosto sospeso, 19 a settembre → sabato 19, prorogato a lunedì 21.
    voce = termini.termini({"notificaRicorso": "2026-07-20"}, oggi=date(2026, 7, 21))[0]
    assert voce["id"] == "costituzione" and voce["scadenza"] == "2026-09-21" and voce["perentorio"]
    controdeduzioni = termini.termini({"notificaRicorso": "2026-03-02", "posizione": "resistente"})[0]
    assert controdeduzioni["id"] == "controdeduzioni" and controdeduzioni["scadenza"] == "2026-05-04"
    ricorso = termini.termini({"atti": [{"dataNotifica": "2026-01-10", "numero": "TK1"}]})[0]
    assert ricorso["id"] == "ricorso-1" and ricorso["scadenza"] == "2026-03-11"


def test_regole_dei_file_del_ptt():
    assert regole.formato("Ricorso.pdf.p7m") == "pdf" and regole.tipo_firma("Ricorso.pdf.p7m", True) == "cades"
    atto = regole.controlla_metadati("Ricorso.pdf", 1000, "atto", firmato=False)
    assert atto.bloccante and atto.esiti[0].codice == "FIRMA"
    assert not regole.controlla_metadati("Ricorso.pdf", 1000, "atto", firmato=True).bloccante
    assert regole.controlla_metadati("Documenti.zip", 1000, "allegato", False).esiti[0].codice == "ZIP"
    assert regole.controlla_metadati("Foto.png", 1000, "allegato", False).esiti[0].codice == "CONSERVAZIONE"
    assert regole.controlla_metadati("x" * 101 + ".pdf", 1000, "allegato", False).bloccante
    assert [e.codice for e in regole.controlla_contenuto(pdf_testo("Ricorso"))] == ["PDFA"]
    esiti = regole.controlla_deposito([{"ruolo": "allegato", "dimensione": 60 * 1024 * 1024}] * 2)
    assert {e.codice for e in esiti} == {"DIMENSIONE_DEPOSITO", "ATTO"}


def test_collegamenti_ipertestuali_bloccanti():
    import io

    from pypdf import PdfWriter
    from pypdf.annotations import Link
    from pypdf.generic import RectangleObject

    scrittore = PdfWriter()
    scrittore.add_blank_page(200, 200)
    scrittore.add_annotation(0, Link(rect=RectangleObject((10, 10, 50, 50)), url="https://example.org"))
    uscita = io.BytesIO()
    scrittore.write(uscita)
    assert "COLLEGAMENTI" in {e.codice for e in regole.controlla_contenuto(uscita.getvalue())}
    assert not {e.codice for e in regole.controlla_contenuto(pdf_pades(pdf_testo("Firmato")))} & {"COLLEGAMENTI", "ELEMENTI_ATTIVI"}


def test_parti_e_scheda_nir():
    elenco = parti.parti_nir(
        {"tipo": "PERSONA_GIURIDICA", "ragione_sociale": "Rossi Costruzioni S.r.l.", "partita_iva": "01234567890", "pec": ""},
        [("CONTROPARTE", {"id": "S1", "ragione_sociale": "Agenzia delle Entrate - Direzione provinciale di Bari"}),
         ("CONTROPARTE", {"id": "S2", "ragione_sociale": "Agenzia delle Entrate - Riscossione"}),
         ("TESTIMONE", {"id": "S3", "nome": "Mario", "cognome": "Neri"})])
    assert elenco["ricorrenti"][0]["natura"] == "G08"
    assert [p["tipoEnte"] for p in elenco["resistenti"]] == ["Agenzie fiscali", ""]
    ctx = {"procedimento": {"corte": "PBA", "atti": [{"tipo": "AVVISO DI ACCERTAMENTO", "numero": "TK1", "dataNotifica": "2026-06-01",
                                                      "tributo": "12000.00", "materia": "Accertamento imposte", "tributo_tipo": "IRES (ex IRPEG)"}],
                            "cutModalita": "F23"},
           "parti": elenco, "avvocato": {"nome": "Avv. Bianchi", "pec": "bianchi@pec.it", "codiceFiscale": "BNCMRA70A01A662X"},
           "documenti": [], "cut": cut.calcola([{"tributo": "12000"}])}
    esito = scheda.scheda(ctx, "ricorso")
    righe = {(s["titolo"], r["etichetta"]): r for s in esito["sezioni"] for r in s["righe"]}
    assert righe[("Dati generali", "Corte di giustizia tributaria")]["valore"].endswith("di Bari")
    assert righe[("Contributo unificato", "CUT dovuto")]["valore"] == "€ 120,00"
    assert righe[("Contributo unificato", "Codice ufficio F23")]["valore"] == catalogo.sede("PBA")["codiceF23"]
    assert righe[("Parti resistenti", "Parte resistente")]["stato"] in {"ok", "verifica"}
    assert "Documenti allegati: Atto principale firmato" in esito["mancanti"]
    assert scheda.scheda(ctx, "altri-atti")["sezioni"][0]["righe"][2]["etichetta"] == "Numero di ruolo (RGR/RGA)"


def test_tributario_non_scambiato_per_tar():
    """«tributario» contiene «tar»: il tipo del fascicolo non deve diventare amministrativo."""
    from pct.fascicoli import TipoFascicolo
    from pct.workflow_onboarding import _infer_tipo_fascicolo

    assert _infer_tipo_fascicolo(tipo_procedimento="Ricorso tributario") == TipoFascicolo.TRIBUTARIO
    assert _infer_tipo_fascicolo(tipo_procedimento="Ricorso al TAR Lazio") == TipoFascicolo.AMMINISTRATIVO
    assert _infer_tipo_fascicolo(tipo_procedimento="Atto notarile") != TipoFascicolo.AMMINISTRATIVO
