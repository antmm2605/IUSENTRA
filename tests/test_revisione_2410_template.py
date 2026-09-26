"""Revisione 2.410.0: gli atti generati dai template contengono ciò che la norma richiede."""

from __future__ import annotations

from types import SimpleNamespace as N

from pct import compilatore_atti as ca
from pct.clienti import Indirizzo
from pct.riscrittura_ancorata import riscrivi_passaggio, valori_non_ancorati

CONFIG = {"STUDIO_INDIRIZZO": "Via Sparano da Bari 100, 70121 Bari (BA)", "STUDIO_AVVOCATO": "Marco Rinaldi", "STUDIO_CF": "RNLMRC80A01A662P"}


def _fascicolo(**extra):
    base = dict(
        id="F1", rg_completo="RG 1234/2026", titolo="Alfa c/ Beta", numero="1", tipo=N(value="CIVILE"),
        tribunale="Tribunale di Bari", controparte="Beta S.p.A.", oggetto="recupero credito da fornitura",
        note="Forniture non pagate.", documenti=[N(nome="fattura 12-2025.pdf")], valore_causa=45000, codice_oggetto_pst="",
    )
    base.update(extra)
    return N(**base)


CLIENTE = N(nome_completo="Alfa S.r.l.", codice_fiscale="", partita_iva="06123450725", indirizzo_sede_legale="Via Amendola 45, 70126 Bari (BA)")
UTENTE = N(id="u1", username="marco", nome_completo="Marco Rinaldi")
PARTI = {"controparte_principale": N(nome_completo="Beta S.p.A.", partita_iva="08123450721", indirizzo="Corso Vittorio Emanuele 12, 70122 Bari (BA)", pec="beta@legalmail.it")}


def _atto(codice, **campi):
    payload = ca.prefill_payload(codice, fascicolo=_fascicolo(), cliente=CLIENTE, utente=UTENTE, config=CONFIG, parti=PARTI)
    payload.update(campi)
    return payload, ca.render_compiled_act(codice, payload)


def test_importi_non_copiati_dal_valore_della_causa():
    payload, _ = _atto("CIV_PREC_001")
    assert payload["principal_amount"] == payload["interest_amount"] == payload["costs_amount"] == ""
    payload, _ = _atto("CIV_RDI_001")
    assert payload["requested_amount"] == ""


def test_decreto_ingiuntivo_completo():
    _, testo = _atto(
        "CIV_RDI_001",
        requested_amount="42350",
        credit_source="fatture n. 12/2025 e 18/2025 per forniture",
        credit_due_date="2025-12-31",
        written_evidence=["fattura n. 12/2025", "fattura n. 18/2025", "estratto autentico delle scritture contabili"],
        interest_requested="moratori ex D.Lgs. 231/2002",
        provisional_enforceability_request="sì",
    )
    for atteso in ("RICORSO PER DECRETO INGIUNTIVO", "42.350,00", "art. 634 c.p.c.", "quaranta giorni", "art. 642 c.p.c.",
                   "31/12/2025", "estratto autentico", "Beta S.p.A. (P.IVA 08123450721)", "art. 13, comma 3"):
        assert atteso in testo, atteso
    assert "45.000" not in testo


def test_precetto_con_avvertimenti_di_legge():
    _, testo = _atto("CIV_PREC_001", enforcement_title="decreto ingiuntivo n. 555/2026 del Tribunale di Bari",
                     title_service_date="2026-06-01", principal_amount="42350", interest_amount="1200,50", costs_amount="800")
    for atteso in ("INTIMA E FA PRECETTO", "dieci giorni", "01/06/2026", "sovraindebitamento", "art. 480, comma 3",
                   "novanta giorni", "44.350,50"):
        assert atteso in testo, atteso


def test_procura_conferisce_il_mandato_senza_dati_di_causa_inventati():
    _, testo = _atto("CIV_PROC_001")
    assert "nomina e costituisce proprio difensore l'Avv. Marco Rinaldi" in testo
    assert "D.Lgs. 28/2010" in testo and "Regolamento UE 2016/679" in testo
    assert "Dichiarazione di valore" not in testo
    assert "R.G. n. 1234/2026" in testo


def test_comparsa_con_ruoli_invertiti_e_art_167():
    payload, testo = _atto("CIV_COM_001")
    assert payload["defendant"] == "Alfa S.r.l." and payload["plaintiff"] == "Beta S.p.A."
    assert "– convenuto –" in testo and "art. 167" in testo
    assert testo.index("Alfa S.r.l.") < testo.index("– convenuto –")


def test_memoria_171_ter_e_date_mancanti_non_diventano_oggi():
    _, testo = _atto("CIV_SUC_002")
    assert "ART. 171-TER" in testo and "venti giorni" in testo
    _, citazione = _atto("CIV_CIT_001")
    assert "centoventi giorni" in citazione
    assert "Tutto ciò premesso" in citazione


def test_dati_compilati_non_si_perdono():
    _, testo = _atto("CIV_NOT_009", documents_list_detailed=["atto di citazione notificato", "procura"], attachments_numbering="da 1 a 2")
    assert "NOTA DI ISCRIZIONE A RUOLO" in testo
    assert "atto di citazione notificato" in testo and "da 1 a 2" in testo
    assert "45.000,00" in testo  # valore della causa dal fascicolo


def test_indirizzo_cliente_con_parentesi_chiusa():
    assert str(Indirizzo(via="Via Amendola", civico="45", cap="70126", comune="Bari", provincia="BA")) == "Via Amendola 45, 70126 Bari (BA)"
    assert str(Indirizzo(cap="70126", comune="Bari")) == "70126 Bari"


def test_riscrittura_con_dato_inventato_scartata():
    originale = "Il convenuto deve pagare euro 42.350,00 entro il 12/11/2026 ai sensi dell'art. 1218 c.c."
    buona = riscrivi_passaggio(originale, "rendi_formale", genera=lambda p, s: ("Ecco il testo riscritto: Il convenuto è tenuto a corrispondere € 42.350,00 entro il 12 novembre 2026, ex art. 1218 c.c.", "test"))
    assert buona.ok and buona.testo.startswith("Il convenuto è tenuto")
    cattiva = riscrivi_passaggio(originale, "rendi_formale", genera=lambda p, s: ("Il convenuto deve pagare € 45.000,00 ex art. 2043 c.c.", "test"))
    assert not cattiva.ok and "45.000,00" in cattiva.non_ancorati
    assert valori_non_ancorati(originale, "Pagamento entro il 3 dicembre 2026.") == ["3 dicembre 2026"]
    guasto = riscrivi_passaggio(originale, "rendi_formale", genera=lambda p, s: (_ for _ in ()).throw(RuntimeError("off")))
    assert not guasto.ok and "non è stato modificato" in guasto.messaggio
