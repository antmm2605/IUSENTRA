"""L'archivio di alimentazione: i motori leggono, il collaudo prova, i presìdi consultano.

Una data è un fatto solo se è vera, ancorata e supera il collaudo; una data di
nascita, una tabella di date, una legge citata non lo diventano mai. Il
verdetto è del software: verificata con riscontro, plausibile senza,
respinta se smentita. Le decisioni dell'avvocato sopravvivono alle riletture.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from pct.archivio_letture import collauda, fatti_da_messaggio, leggi_testo, prove_notifica_per_oggetto, riassunto_archivio, ruoli_letti, udienze_e_termini
from pct.archivio_letture.ancoraggio import ancora_per
from pct.archivio_letture.collaudo import Contesto, contesto_da_fascicolo
from pct.archivio_letture.estrazione_date import estrai_date
from pct.archivio_letture.estrazione_notifiche import estrai_prove_notifica
from pct.archivio_letture.estrazione_ruolo import estrai_ruoli
from pct.registro_letture import Fatto, Oggetto, RegistroLetture

OGGI = date(2026, 9, 15)
FASCICOLO = SimpleNamespace(id="F1", numero_rg="1234", anno_rg="2026", data_apertura="2026-01-15", nome_cliente="Anna Bianchi")
DECRETO = (
    "TRIBUNALE DI MILANO - R.G. n. 1234/2026\n"
    "Il Giudice fissa l'udienza di comparizione per il giorno 1O/11/2O26 alle ore 9.30,\n"
    "assegna termine perentorio fino al 31/10/2026 per il deposito di memorie.\n"
    "Il ricorso è stato notificato il 15/08/2026 ai sensi dell'art. 3-bis L. 53/1994 (RELATA DI NOTIFICA allegata).\n"
    "Nato a Roma il 12/03/1980, carta d'identità rilasciata il 03/02/2020. Prot. n. 55/2026. Versione 1.2.34.\n"
    "Milano, lì 20/09/2026. Sentenza n. 88/2026 pubblicata il 05/09/2026.\n"
    "Tabella: 01/01/2020 02/02/2021 03/03/2022. Periodo dal 01/02/2026 al 28/02/2026.\n"
    "Udienza rinviata al 12 marzo 2027."
)


def _contesto(**extra) -> Contesto:
    return contesto_da_fascicolo(FASCICOLO, oggi=OGGI, **extra)


def test_le_date_sono_fatti_solo_se_ancorate_e_vere():
    fatti = {(f.campo, f.valore) for f in estrai_date(DECRETO, origine="nativo")}
    assert ("udienza", "2026-11-10T09:30") in fatti
    assert ("termine", "2026-10-31") in fatti
    assert ("notifica", "2026-08-15") in fatti
    assert ("data_atto", "2026-09-20") in fatti
    assert ("provvedimento", "2026-09-05") in fatti
    assert ("udienza", "2027-03-12") in fatti
    valori = {v.split("T")[0] for _, v in fatti}
    # nascita, documento d'identità, tabella, periodo «dal…al», protocollo, versione: mai fatti.
    assert not valori & {"1980-03-12", "2020-02-03", "2020-01-01", "2021-02-02", "2022-03-03", "2026-02-01", "2026-02-28", "2034-02-01"}


def test_sentenza_istruttoria_non_alimenta_importi_del_fascicolo():
    testo = """
    TRIBUNALE ORDINARIO DI VICENZA
    Sentenza n. 99/2026 pubbl. il 20/04/2026
    RG n. 1234/2026
    nella causa promossa da Roberta Montagnese contro Ministero dell'Istruzione.
    P.Q.M. condanna il Ministero alla rifusione delle spese di lite,
    liquidando la complessiva somma di € 500,00 oltre accessori.
    """

    fatti = leggi_testo(
        testo,
        origine="nativo",
        contesto=_contesto(),
        nome="Sentenza_Tribunale_Vicenza_20-04-2023.PDF",
        metadata={"fascicolo": FASCICOLO, "tipo_documento": "SENTENZA", "documento_id": "DOC-VICENZA"},
    )

    assert [f for f in fatti if f.categoria == "importo"] == []
    assert [f for f in fatti if f.campo == "controllo_economico"] == []


def test_sentenza_del_cliente_alimenta_importi_del_fascicolo():
    testo = """
    TRIBUNALE ORDINARIO DI MILANO
    Sentenza n. 100/2026 pubbl. il 20/04/2026
    RG n. 1234/2026
    nella causa promossa da Anna Bianchi contro Ministero dell'Istruzione.
    P.Q.M. condanna il Ministero alla rifusione delle spese di lite,
    liquidando la complessiva somma di € 500,00 oltre accessori.
    """

    fatti = leggi_testo(
        testo,
        origine="nativo",
        contesto=_contesto(),
        nome="Sentenza_Bianchi_RG_1234_2026.pdf",
        metadata={"fascicolo": FASCICOLO, "tipo_documento": "SENTENZA", "documento_id": "DOC-SENTENZA"},
    )

    importi = [f for f in fatti if f.categoria == "importo" and f.campo == "liquidazione_giudice"]
    assert importi and importi[0].valore == "500.00"


def test_versione_motore_documenti_include_versione_importi():
    from pct.archivio_letture.estrazione_importi import VERSIONE_ESTRAZIONE_IMPORTI
    from pct.archivio_letture.motore_documenti import VERSIONE_MOTORE_DOCUMENTI

    assert VERSIONE_ESTRAZIONE_IMPORTI in VERSIONE_MOTORE_DOCUMENTI


def test_la_citazione_della_carta_non_rende_identita_un_decreto():
    from pct.archivio_letture.pertinenza_documentale import natura_documentale

    assert natura_documentale(DECRETO, "1234", "2026") == ("", "")
    scansione = (
        "REPUBBLICA ITALIANA MINISTERO DELL'INTERNO\nCARTA DI IDENTITA' / IDENTITY CARD\n"
        "COGNOME ROSSI NOME MARIO CITTADINANZA ITALIANA SCADENZA 01/01/2030"
    )
    assert natura_documentale(scansione, "", "")[0] == "documento_identita"


def test_ancore_negative_e_ancora_consumata():
    testo = "ai sensi della legge 21 gennaio 1994 n. 53, udienza del 10/03/2026 e 11/03/2026"
    assert ancora_per(testo, testo.index("21 gennaio"), testo.index("21 gennaio") + 15) is None
    prima = testo.index("10/03/2026")
    assert ancora_per(testo, prima, prima + 10).campo == "udienza"
    seconda = testo.index("11/03/2026")
    assert ancora_per(testo, seconda, seconda + 10, limite=prima + 10) is None  # l'ancora vale per la prima data


def test_prove_di_notifica_e_ruoli_dal_testo():
    prove = {f.campo: f for f in estrai_prove_notifica("RELATA DI NOTIFICA ai sensi dell'art. 3-bis L. 53/1994. Ricevuta di avvenuta consegna: il messaggio è stato consegnato.", origine="nativo")}
    assert prove["relata"].confidenza >= 0.9 and prove["rdac"].confidenza >= 0.9
    assert "attestazione" not in prove
    ruoli = estrai_ruoli("R.G. n. 12S4/2O26 e R.G.N.R. 5678/2025 e procedimento 999/2026", origine="ocr")
    assert [(f.campo, f.valore) for f in ruoli] == [("numero_ruolo", "1254/2026"), ("numero_ruolo_penale", "5678/2025")]


def test_il_collaudo_decide_verificata_plausibile_respinta():
    nativo = {(f.campo, f.verifica) for f in leggi_testo(DECRETO, origine="nativo", contesto=_contesto()) if f.categoria == "data"}
    assert ("udienza", "verificata") in nativo and ("termine", "verificata") in nativo
    def per_data(fatti):
        return {(f.campo, f.valore.split("T")[0]): f for f in fatti if f.categoria == "data"}

    ocr = per_data(leggi_testo(DECRETO, origine="ocr", contesto=_contesto()))
    assert ocr[("termine", "2026-10-31")].verifica == "plausibile"  # letto dall'OCR, nessun riscontro
    prove_termine = [p["codice"] for p in ocr[("termine", "2026-10-31")].prove]
    assert prove_termine[:5] == ["calendario", "forma", "ancoraggio", "orizzonte", "concordanza"]
    assert {"base_normativa", "procedura"} <= set(prove_termine)
    # Con l'agenda che conosce la data, l'udienza letta dall'OCR è verificata.
    con_agenda = per_data(leggi_testo(DECRETO, origine="ocr", contesto=_contesto(date_note={"2026-11-10": ["agenda"]})))
    udienza = con_agenda[("udienza", "2026-11-10")]
    assert udienza.verifica == "verificata" and any(p["codice"] == "concordanza" and p["esito"] == "ok" for p in udienza.prove)
    assert con_agenda[("udienza", "2027-03-12")].verifica == "plausibile"
    # Con una seconda lettura indipendente concorde, anche il termine è verificato.
    contesto = _contesto()
    contesto.testo_secondario, contesto.etichetta_secondario = "termine fino al 31/10/2026", "testo nativo del PDF"
    doppia = per_data(leggi_testo(DECRETO, origine="ocr", contesto=contesto))
    assert doppia[("termine", "2026-10-31")].verifica == "verificata" and doppia[("udienza", "2026-11-10")].verifica == "plausibile"
    # Un'udienza prima dell'apertura del fascicolo o fuori calendario è respinta e non si propone.
    respinta = leggi_testo("udienza del 10/03/2024", origine="nativo", contesto=_contesto())
    assert respinta[0].verifica == "respinta" and udienze_e_termini(respinta) == []
    ruolo = [f for f in leggi_testo(DECRETO, origine="ocr", contesto=_contesto()) if f.categoria == "ruolo"][0]
    assert ruolo.verifica == "verificata" and ruolo.valore == "1234/2026"


def test_il_motore_pec_traduce_il_presidio_in_fatti():
    messaggio = {
        "id": "M1", "received_at": "2026-09-10T10:15:00+02:00", "subject": "POSTA CERTIFICATA: Consegna: notifica ricorso", "from": "posta-certificata@pec.aruba.it",
        "udienze": [{"hearing_date": "2026-11-10", "hearing_time": "09:30", "mode": "presenza", "human_review_required": 0}, {"hearing_date": "2026-09-01", "hearing_time": "", "mode": "", "human_review_required": 0}],
        "termini": [{"dies_a_quo_date": "2026-09-10", "deadline_type": "memorie_171_ter", "norm_ref": "art. 171-ter c.p.c.", "human_review_required": 1}],
        "eventi": [{"primary_event": "fissazione_udienza", "family": "udienza", "priority": "alta", "human_review_required": 0}],
    }
    fatti = fatti_da_messaggio(messaggio, _contesto())
    per = {(f.categoria, f.campo, f.valore): f for f in fatti}
    assert per[("prova_notifica", "rdac", "rdac")].verifica == "verificata"
    assert per[("data", "consegna", "2026-09-10T10:15")].verifica == "verificata"
    assert per[("data", "udienza", "2026-11-10T09:30")].verifica == "verificata"
    assert per[("data", "udienza", "2026-09-01")].verifica == "respinta"  # prima della PEC che la comunica
    assert per[("data", "decorrenza", "2026-09-10")].verifica == "plausibile"  # il presidio la vuole rivedere
    assert per[("evento", "fissazione_udienza", "udienza")].verifica == "verificata"
    prove_decorrenza = per[("data", "decorrenza", "2026-09-10")].prove
    assert any(prova.get("codice") == "base_normativa" and "171-ter" in prova.get("dettaglio", "") for prova in prove_decorrenza)
    assert any(prova.get("codice") == "procedura" and "REGISTRO_LETTURE" in prova.get("dettaglio", "") for prova in prove_decorrenza)


def test_le_viste_per_i_presidi():
    fatti = leggi_testo(DECRETO, origine="nativo", contesto=_contesto())
    for fatto in fatti:
        fatto.oggetto_id, fatto.tipo, fatto.motore = "d1", "documento", "documenti"
    azioni = udienze_e_termini(fatti, oggi=OGGI)
    # «1O/11/2O26» ha tre segni corretti: anche da testo nativo resta plausibile finché nessuno la riscontra.
    assert [(a["type"], a["dateIso"], a["time"], a["verifica"]) for a in azioni] == [("termine_documento", "2026-10-31", "", "verificata"), ("udienza_documento", "2026-11-10", "09:30", "plausibile"), ("udienza_documento", "2027-03-12", "", "verificata")]
    assert azioni[1]["requiresConfirmation"] and not azioni[0]["requiresConfirmation"]
    assert prove_notifica_per_oggetto(fatti)["d1"]["kind"] == "relata"
    assert ruoli_letti(fatti)[0]["valore"] == "1234/2026"
    riassunto = riassunto_archivio(fatti)
    assert riassunto["udienze"] == 2 and riassunto["termini"] == 1 and riassunto["prove_notifica"] == 1
    assert [voce["valore"] for voce in riassunto["da_confermare"]] == ["2026-11-10T09:30"]


def test_l_archivio_conserva_le_decisioni_dell_avvocato_e_rimuove_i_fatti_scomparsi(tmp_path: Path):
    registro = RegistroLetture(tmp_path / "registro.db")
    oggetto = Oggetto(tipo="documento", oggetto_id="d1", sha256="a" * 64)
    registro.registra_inventario("t", "F1", [oggetto])
    prima = leggi_testo(DECRETO, origine="ocr", contesto=_contesto())
    assert registro.registra_fatti("t", "F1", oggetto, "documenti", prima, versione="v1")["nuovi"] == len(prima)
    termine = next(f for f in registro.fatti("t", "F1") if f.campo == "termine")
    assert termine.verifica == "plausibile"
    corretto = registro.decidi_fatto("t", termine.id, verifica="corretta", valore="2026-11-02", utente_id="avv")
    assert corretto.verifica == "corretta" and corretto.valore == "2026-11-02"
    # Rilettura dello stesso contenuto senza il termine: la decisione resta, l'udienza del 2027 (assente) sparisce.
    seconda = [f for f in leggi_testo(DECRETO.replace("Udienza rinviata al 12 marzo 2027.", ""), origine="ocr", contesto=_contesto())]
    esito = registro.registra_fatti("t", "F1", oggetto, "documenti", seconda, versione="v1")
    assert esito["conservati"] == 1 and esito["rimossi"] == 1
    assert next(f for f in registro.fatti("t", "F1") if f.campo == "termine").verifica == "corretta"
    assert all(f.valore != "2027-03-12" for f in registro.fatti("t", "F1", verifiche=None))
    # La decisione presa sul pannello delle anomalie si propaga ai fatti con lo stesso dato letto.
    udienza = next(f for f in registro.fatti("t", "F1") if f.campo == "udienza")
    anomalia = registro.registra_anomalie("t", "F1", oggetto, "ocr", [{"campo": "udienza", "valore_letto": udienza.valore_letto, "motivo": "x", "codice": "corretta_da_ocr", "gravita": "bassa"}])[0]
    registro.risolvi_anomalia("t", anomalia.id, esito="confermata", utente_id="avv")
    assert next(f for f in registro.fatti("t", "F1") if f.campo == "udienza").verifica == "verificata"
    assert registro.riassunto_fatti("t", "F1")["per_verifica"]["corretta"] == 1


def test_rilettura_oggetto_rimuove_fatti_di_impronta_precedente(tmp_path: Path):
    registro = RegistroLetture(tmp_path / "registro.db")
    vecchio = Oggetto(tipo="documento", oggetto_id="d1", sha256_archivio="a" * 64)
    corrente = Oggetto(tipo="documento", oggetto_id="d1", sha256="a" * 64)
    registro.registra_inventario("t", "F1", [corrente])
    registro.registra_fatti("t", "F1", vecchio, "documenti", [
        Fatto(categoria="importo", campo="liquidazione_giudice", valore="500.00", valore_letto="€ 500,00", etichetta="Compenso liquidato dal giudice € 500,00", verifica="verificata"),
    ], versione="v1")

    esito = registro.registra_fatti("t", "F1", corrente, "documenti", [], versione="v2")

    assert esito["rimossi"] == 1
    assert registro.fatti("t", "F1", verifiche=None) == []


def test_collauda_non_tocca_le_decisioni():
    fatto = Fatto(categoria="data", campo="udienza", valore="2026-11-10", verifica="corretta")
    assert collauda(fatto, _contesto()).verifica == "corretta"


_RT_PAGOPA = """<?xml version="1.0" encoding="UTF-8"?>
<pay_j:RT xmlns:pay_j="http://www.digitpa.gov.it/schemas/2011/Pagamenti/">
  <pay_j:dataOraMessaggioRicevuta>2026-05-14T09:10:00</pay_j:dataOraMessaggioRicevuta>
  <pay_j:datiPagamento>
    <pay_j:codiceEsitoPagamento>{esito}</pay_j:codiceEsitoPagamento>
    <pay_j:importoTotalePagato>98.00</pay_j:importoTotalePagato>
    <pay_j:datiSingoloPagamento>
      <pay_j:singoloImportoPagato>98.00</pay_j:singoloImportoPagato>
      <pay_j:dataEsitoSingoloPagamento>2026-05-12</pay_j:dataEsitoSingoloPagamento>
      <pay_j:causaleVersamento>/RFB/300039//98.00/TXT/Contributo unificato</pay_j:causaleVersamento>
      <pay_j:datiSpecificiRiscossione>9/0702100TS/CONTRIB</pay_j:datiSpecificiRiscossione>
    </pay_j:datiSingoloPagamento>
  </pay_j:datiPagamento>
</pay_j:RT>"""


def test_data_del_versamento_letta_dallo_schema_della_ricevuta_telematica():
    """La RT non ha prosa: il giorno del versamento si legge dal campo dedicato."""
    from pct.archivio_letture.estrazione_importi import data_del_versamento

    assert data_del_versamento(_RT_PAGOPA.format(esito="0")) == "12/05/2026"


def test_ricevuta_telematica_senza_pagamento_eseguito_non_da_una_data_di_pagamento():
    """Esito diverso da «eseguito»: la RT non prova un versamento, quindi niente data."""
    from pct.archivio_letture.estrazione_importi import data_del_versamento

    assert data_del_versamento(_RT_PAGOPA.format(esito="4")) == ""


def test_importo_del_contributo_da_ricevuta_telematica_porta_stato_e_giorno():
    from pct.archivio_letture.estrazione_importi import estrai_importi

    fatti = estrai_importi(
        _RT_PAGOPA.format(esito="0"),
        metadata={"filename": "RT contributo.xml"},
        origine="nativo",
    )
    contributo = next(f for f in fatti if f.campo == "contributo_unificato")
    prove = {prova["codice"]: prova["dettaglio"] for prova in contributo.prove}

    assert contributo.valore == "98.00"
    assert prove["stato"] == "pagato"
    assert prove["data"] == "12/05/2026"
    assert prove["norma"] == "D.P.R. 115/2002 art. 13"


def test_data_del_versamento_resta_ancorata_nella_prosa_di_una_ricevuta_cartacea():
    """Fuori dalla RT vale la regola di prima: solo la data ancorata alla formula."""
    from pct.archivio_letture.estrazione_importi import data_del_versamento

    assert data_del_versamento("Data pagamento: 17/03/2026 - esito positivo.") == "17/03/2026"
    assert data_del_versamento("Sentenza del 28/04/2026 pubblicata in cancelleria.") == ""
    assert data_del_versamento("Data pagamento: 31/02/2026") == ""
