"""Identità dell'atto dal titolo: ogni area del diritto, senza falsi positivi.

Il 14/09/2026, su un corpus di 46 documenti tipici di un fascicolo civile, 17
finivano «da verificare» e almeno 6 venivano catalogati con alta confidenza ma
in modo sbagliato: un ricorso letto come «contributo unificato» perché ne
citava l'importo, un'istanza di rinvio letta come «verbale», un'istanza ex art.
186-ter letta come «ordinanza». La causa era una sola: senza una regola
d'identità, il classificatore cercava parole chiave in tutto il corpo.

Qui si verifica che ogni regola scatti sul proprio documento e — la parte che
conta — che una citazione nel corpo non basti mai a cambiare l'identità.
"""

from __future__ import annotations

import re

import pytest

from pct.document_intelligence.catalog_resolver import _SOURCE_INDEX, resolve_document_catalog
from pct.document_intelligence.catalog_sources import CATALOG_SOURCES
from pct.document_intelligence.catalog_titoli import identita_dal_titolo, identita_messaggio
from pct.document_intelligence.titoli import AREE, REGOLE_TITOLO, area_della_regola
from pct.document_intelligence.titoli.fonti import FONTI_TITOLI
from tests.dati_catalogo_titoli import CAMPIONI, CTX_CIVILE


def _cataloga(testo: str, nome: str = "documento.pdf"):
    return resolve_document_catalog(
        tenant_id="t", fascicolo_id="F", document_id=nome, document_sha256="", filename=nome,
        extracted_text=testo, document_metadata={}, fascicolo_context=dict(CTX_CIVILE),
    )


# ── Ogni regola riconosce il proprio documento ─────────────────────────────


def test_ogni_regola_ha_un_documento_di_prova_e_viceversa():
    ids = {regola.id for regola in REGOLE_TITOLO}
    assert ids - set(CAMPIONI) == set(), "regole senza documento di prova"
    assert set(CAMPIONI) - ids == set(), "documenti di prova senza regola"


@pytest.mark.parametrize("rule_id", sorted(CAMPIONI))
def test_il_documento_viene_riconosciuto_dal_suo_titolo(rule_id):
    testo, label, sezione = CAMPIONI[rule_id]
    esito = _cataloga(testo, f"{rule_id}.pdf")
    assert esito.status == "proposed", f"{rule_id}: {esito.reason}"
    assert esito.document_label == label
    assert esito.document_section == sezione
    assert esito.confidence >= 90


def test_le_aree_coperte_sono_tutte_quelle_dello_studio():
    nomi = [nome for nome, _ in AREE]
    for area in ("civile", "esecuzioni", "lavoro", "amministrativo", "tributario", "penale", "famiglia", "locazioni", "crisi", "sinistri", "immigrazione", "studio"):
        assert area in nomi, f"area {area} non coperta"
    assert nomi[-1] == "generiche", "le regole generiche devono chiudere la catena"
    assert len(REGOLE_TITOLO) >= 140


# ── Nessuna citazione nel corpo cambia l'identità ──────────────────────────


FALSI_POSITIVI = {
    # (testo, etichetta che NON deve uscire, etichetta attesa)
    "ricorso_che_cita_il_contributo": (
        "TRIBUNALE DI BARI\nRICORSO EX ART. 281-UNDECIES C.P.C.\nIl ricorrente chiede la condanna della resistente. Si dichiara che il contributo unificato dovuto è di euro 237,00 e si allega la ricevuta pagoPA.",
        "Contributo unificato / pagamento", "Ricorso introduttivo",
    ),
    "comparsa_che_cita_la_citazione": (
        "TRIBUNALE DI BARI\nCOMPARSA DI COSTITUZIONE E RISPOSTA\nPer Alfa S.r.l., convenuta, che si costituisce. Premesso che con atto di citazione notificato il 15/01/2026 l'attore ha convenuto in giudizio la comparente.",
        "Atto di citazione - atto principale", "Comparsa di costituzione e risposta",
    ),
    "istanza_che_chiede_un_ordinanza": (
        "TRIBUNALE DI BARI - R.G. 1234/2026\nISTANZA DI ORDINANZA INGIUNZIONE EX ART. 186-TER C.P.C.\nL'attore chiede che il Giudice pronunci ordinanza di ingiunzione per la somma non contestata.",
        "Ordinanza dell'ufficio giudiziario", "Istanza di ordinanza ingiunzione ex art. 186-ter c.p.c.",
    ),
    "istanza_di_rinvio_che_cita_l_udienza": (
        "TRIBUNALE DI BARI - R.G. 1234/2026\nISTANZA DI RINVIO DELL'UDIENZA\nL'avv. Luca Bianchi chiede che l'udienza fissata per il 20/04/2026 sia rinviata per legittimo impedimento, come da verbale del medico curante.",
        "Verbale", "Istanza di rinvio dell'udienza",
    ),
    "precisazione_che_richiama_la_citazione": (
        "TRIBUNALE DI BARI\nFOGLIO DI PRECISAZIONE DELLE CONCLUSIONI\nL'attore precisa le conclusioni come in atto di citazione.",
        "Atto di citazione - atto principale", "Precisazione delle conclusioni",
    ),
    "pignoramento_che_cita_il_precetto": (
        "ATTO DI PIGNORAMENTO PRESSO TERZI\nex art. 543 c.p.c.\nIl creditore, in forza del titolo esecutivo e dell'atto di precetto notificato il 01/03/2026, PIGNORA le somme dovute dal terzo pignorato.",
        "Atto di precetto", "Atto di pignoramento",
    ),
    "reclamo_al_garante_non_e_cautelare": (
        "RECLAMO AL GARANTE PER LA PROTEZIONE DEI DATI PERSONALI\nex art. 77 Reg. UE 2016/679\nIl sottoscritto lamenta il trattamento illecito dei propri dati personali.",
        "Reclamo cautelare", "Reclamo al Garante per la protezione dei dati",
    ),
}


@pytest.mark.parametrize("caso", sorted(FALSI_POSITIVI))
def test_una_citazione_nel_corpo_non_cambia_l_identita(caso):
    testo, sbagliata, attesa = FALSI_POSITIVI[caso]
    esito = _cataloga(testo)
    assert esito.document_label != sbagliata, f"{caso}: ricaduto nel falso positivo {sbagliata!r}"
    assert esito.document_label == attesa


def test_il_titolo_senza_conferma_nel_corpo_non_basta():
    """«Decreto ingiuntivo» come titolo di un appunto senza la formula del giudice."""
    assert identita_dal_titolo("DECRETO INGIUNTIVO\nAppunti per il cliente: spiegare cos'è e quanto costa.") is None


def test_la_conferma_senza_titolo_non_basta():
    """La formula «ingiunge» dentro un altro atto non lo rende un decreto."""
    esito = identita_dal_titolo("TRIBUNALE DI BARI\nCOMPARSA DI COSTITUZIONE E RISPOSTA\nLa convenuta si costituisce e osserva che il decreto ingiunge il pagamento di una somma non dovuta.")
    assert esito is not None and esito["label"] == "Comparsa di costituzione e risposta"


def test_un_titolo_spezzato_dall_ocr_si_legge_per_intero_ma_non_per_prefisso():
    spezzato = "COMPARSA DI COSTITUZIONE E\nRISPOSTA\nPer Alfa S.r.l., convenuta, che si costituisce in giudizio."
    assert identita_dal_titolo(spezzato)["label"] == "Comparsa di costituzione e risposta"


# ── La busta prima del contenuto ───────────────────────────────────────────


@pytest.mark.parametrize(("oggetto", "label"), [
    ("ESITO CONTROLLI AUTOMATICI DEPOSITO - RICORSO - RG 1234/2026", "Ricevuta PCT — esito controlli automatici"),
    ("ACCETTAZIONE DEPOSITO - MEMORIA - RG 1234/2026", "Ricevuta PCT — accettazione della cancelleria"),
    ("RIFIUTO DEPOSITO - RG 1234/2026", "Ricevuta PCT — rifiuto della cancelleria"),
])
def test_le_ricevute_del_deposito_telematico_si_riconoscono_dall_oggetto(oggetto, label):
    testo = f"Da: pct.tribunale.bari@civile.ptel.giustiziacert.it\nOggetto: {oggetto}\nIl deposito telematico è stato elaborato dalla cancelleria del Tribunale di Bari."
    esito = identita_messaggio(testo)
    assert esito and esito["label"] == label
    assert esito["deposit_candidate"] is False


def test_un_messaggio_pec_che_allega_un_atto_resta_un_messaggio():
    testo = "Da: alfa@pec.it\nA: luca.bianchi@pec.ordineavvocatibari.it\nOggetto: trasmissione decreto ingiuntivo\nGentile avvocato, in allegato il DECRETO INGIUNTIVO con cui il giudice ingiunge il pagamento.\nDistinti saluti"
    esito = _cataloga(testo, "messaggio.eml")
    assert esito.document_label == "Messaggio PEC"
    assert esito.document_section == "comunicazioni"


def test_una_lettera_di_licenziamento_si_riconosce_dall_oggetto():
    esito = _cataloga("ALFA S.R.L.\nRaccomandata A.R.\nOggetto: licenziamento\nEgregio sig. Rossi, la Società recede dal rapporto di lavoro per giustificato motivo oggettivo.")
    assert esito.document_label == "Lettera di licenziamento"


# ── Fonti certe ────────────────────────────────────────────────────────────


def test_ogni_regola_cita_una_fonte_registrata_e_verificata():
    for regola in REGOLE_TITOLO:
        fonte = CATALOG_SOURCES.get(regola.fonte) or _SOURCE_INDEX.get(regola.fonte)
        assert fonte, f"{regola.id}: fonte {regola.fonte!r} non registrata"
        url = str(fonte.get("official_url") or "")
        assert url.startswith("https://"), f"{regola.id}: fonte senza indirizzo ufficiale"
        assert str(fonte.get("verification_status") or "").strip(), f"{regola.id}: fonte senza data di verifica"


def test_le_fonti_nuove_sono_su_normattiva_con_la_data_di_consultazione():
    for identificativo, fonte in FONTI_TITOLI.items():
        assert fonte["official_url"].startswith("https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"), identificativo
        assert re.search(r"\d{2}/\d{2}/\d{4}", fonte["verification_status"]), identificativo
        assert fonte["source_type"] == "normativa"


def test_ogni_regola_appartiene_a_un_area_e_ha_identificativo_unico():
    ids = [regola.id for regola in REGOLE_TITOLO]
    assert len(ids) == len(set(ids))
    for regola in REGOLE_TITOLO:
        assert area_della_regola(regola.id), regola.id


def test_la_fonte_della_regola_entra_fra_le_prove_della_catalogazione():
    esito = _cataloga(CAMPIONI["atto_precetto"][0], "precetto.pdf")
    locatori = {prova.locator for prova in esito.evidence if prova.evidence_type == "legal_source"}
    assert "normattiva_cpc_esecuzione_forzata" in locatori
