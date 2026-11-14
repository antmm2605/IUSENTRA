"""Rito, fase e udienze della Lettura del fascicolo (collaudo dell'avvocato del 10/11/2026). Esempi fittizi.

- Il rito si decide dal profilo, dal codice oggetto ministeriale PST e dagli atti: espropriazione presso terzi
  (artt. 543 ss. c.p.c.), monitorio (artt. 633 ss.), volontaria giurisdizione (artt. 737 ss.), lavoro (artt. 409 ss.).
- Un termine non è mai un'udienza: «costituzione almeno dieci giorni prima dell'udienza» (art. 416) e «notifica almeno
  trenta giorni prima» (art. 415, c. 5) non sono la prossima udienza.
- Il monitorio non ha udienze: d.i. emesso, notificato, termine di opposizione (art. 641 e art. 155 c.p.c.),
  esecutorietà (art. 647), precetto (art. 654).
- Le udienze di un'altra causa dello stesso cliente non entrano nel fascicolo.
- Il ruolo e il deposito che risultano dal messaggio di deposito telematico dello studio (art. 13 D.M. 44/2011).
- La data del provvedimento non è l'udienza che il provvedimento fissa.
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from pct.agenda_del_fascicolo import appuntamento_del_fascicolo, chiavi_fascicolo, udienze_in_agenda
from pct.fascicolo_lettura import DatiLettura, costruisci_lettura
from pct.procedura_fasi.monitorio import (FASE_ESECUTIVO, FASE_ESECUTORIETA, FASE_OPPOSIZIONE, FASE_OPPOSTO, stato_monitorio,
                                          termine_opposizione)
from pct.procedura_fasi.riti import rito_da_codice_oggetto, rito_per_fascicolo
from pct.procedura_fasi.ruolo_dagli_atti import depositi_dalle_copie_pec, ruolo_dagli_atti
from pct.procedura_fasi.udienze import data_di_emissione, e_udienza, prossima_udienza

OGGI = date(2026, 11, 10)


@pytest.mark.parametrize("codice,atteso", [
    ("510002", "esecuzione"), ("610001", "esecuzione"), ("010001", "decreto_ingiuntivo"), ("210001", "decreto_ingiuntivo"),
    ("413014", "volontaria"), ("222050", "lavoro"), ("011001", "cautelare"), ("140001", ""),
])
def test_rito_dal_codice_oggetto_ministeriale(codice, atteso):
    assert rito_da_codice_oggetto(codice) == atteso


def test_rito_dalla_fonte_piu_certa():
    assert rito_per_fascicolo("civile", "", codice_oggetto="510002") == "esecuzione"
    assert rito_per_fascicolo("civile", "", codice_oggetto="010001") == "decreto_ingiuntivo"
    assert rito_per_fascicolo("civile", "", codice_oggetto="413014") == "volontaria"
    assert rito_per_fascicolo("civile", "", area="Volontaria giurisdizione") == "volontaria"
    assert rito_per_fascicolo("civile", "", oggetto="Espropriazione mobiliare presso terzi") == "esecuzione"
    assert rito_per_fascicolo("civile", "", etichette_atti=["Atto di pignoramento"]) == "esecuzione"
    # Il tipo di procedimento dichiarato e specifico prevale; il generico «ordinario» no.
    assert rito_per_fascicolo("civile", "Rito semplificato", codice_oggetto="140001") == "semplificato"
    assert rito_per_fascicolo("civile", "ordinario", codice_oggetto="510002") == "esecuzione"
    assert rito_per_fascicolo("civile", "") == "ordinario"
    assert rito_per_fascicolo("lavoro", "retribuzione", codice_oggetto="222050") == "lavoro"


def test_un_termine_riferito_all_udienza_non_e_un_udienza():
    costituzione = {"tipo": "DEPOSITO_ATTO", "titolo": "Costituzione del convenuto con memoria difensiva - almeno 10 giorni prima dell'udienza",
                    "data": "2026-11-12", "stato": "BOZZA"}
    notifica = {"tipo": "", "titolo": "Notifica di ricorso e decreto - almeno 30 giorni prima dell'udienza", "data": "2027-01-08", "stato": "BOZZA"}
    udienza = {"tipo": "UDIENZA", "titolo": "Riassegnazione termine per note in sostituzione udienza", "data": "2026-11-23", "stato": "APERTO"}
    senza_tipo = {"titolo": "Udienza di discussione", "data": "2026-12-01", "stato": "APERTO"}
    assert not e_udienza(costituzione) and not e_udienza(notifica)
    assert e_udienza(udienza) and e_udienza(senza_tipo)
    assert prossima_udienza(scadenze=[costituzione, notifica, udienza], oggi=OGGI) == date(2026, 11, 23)
    agenda = [{"tipo": "UDIENZA", "titolo": "Udienza", "data_ora": "2027-02-09T14:00:00", "stato": "PROGRAMMATO"},
              {"tipo": "UDIENZA", "titolo": "Udienza", "data_ora": "2026-11-20T09:00:00", "stato": "ANNULLATO"}]
    assert prossima_udienza(scadenze=[notifica], appuntamenti=agenda, oggi=OGGI) == date(2027, 2, 9)


def test_la_data_del_provvedimento_non_e_l_udienza():
    brano = "Fissazione udienza discussione n. cronol. 1918/2026 del 02/02/2026 RG n. 161/2026"
    assert data_di_emissione(brano, date(2026, 2, 2))
    assert data_di_emissione("Visto il decreto ingiuntivo emesso in data 20-12-2024, notificato", date(2024, 12, 20))
    assert data_di_emissione("Decreto fissazione udienza, emesso dal Tribunale di Palmi Sez. Lavoro in data 18/05/2026, sono conformi",
                             date(2026, 5, 18))
    assert not data_di_emissione("fissa l'udienza del 16/04/2026 e dispone", date(2026, 4, 16))
    # Note scritte e verbali portano in calce il giorno dell'udienza: non è la data di un provvedimento.
    assert not data_di_emissione("Reggio Calabria, 18/01/2024. Udienza del 18.01.2024 Note scritte in sostituzione", date(2024, 1, 18))
    assert not data_di_emissione("provvedimento emesso in data 19.04.2024, comunicato via pec il 24.04.2024", date(2024, 4, 24))


def _monitorio(*, esecutivo=True, notificato=True, nome_decreto="accoglimentoDecretoIngiuntivoNonEsecutivo.pdf"):
    documenti = [
        {"id": "R1", "nome": "Ricorso.pdf", "etichetta": "Ricorso per decreto ingiuntivo", "sezione": "atti", "natura": "atto_principale"},
        {"id": "D1", "nome": nome_decreto, "etichetta": "Decreto ingiuntivo", "sezione": "provvedimenti", "natura": "provvedimento"},
        {"id": "I1", "nome": "Istanza esecutorietà.pdf", "etichetta": "Istanza per la concessione del decreto esecutorietà ex art.647 c.p.c",
         "sezione": "atti", "natura": "istanza"},
    ]
    fonti = [{"oggetto_id": "D1", "campo": "data_atto", "categoria": "data", "valore": "2024-12-20", "verifica": "verificata",
              "contesto": "in difetto il decreto diventerà esecutivo. Si comunichi. CITTÀ, 20-12-2024", "posizione": 900},
             {"oggetto_id": "I1", "campo": "data_atto", "categoria": "data", "valore": "2025-02-10", "verifica": "verificata",
              "contesto": "CHIEDE Dichiararsi esecutivo e definitivo il suddetto decreto. Città, 10.02.2025", "posizione": 800}]
    if notificato:
        fonti.append({"oggetto_id": "I1", "campo": "notifica", "categoria": "data", "valore": "2024-12-23", "verifica": "verificata",
                      "contesto": "che l'anzidetto decreto è stato notificato all'ingiunto in data 23/12/2024"})
    if esecutivo:
        documenti.append({"id": "E1", "nome": "decretoGenerico.pdf", "etichetta": "Contenuto da verificare", "sezione": "da-verificare", "natura": ""})
        fonti.append({"oggetto_id": "E1", "campo": "data_atto", "categoria": "data", "valore": "2025-03-10", "verifica": "verificata",
                      "contesto": "visto l'art. 647 c.p.c.; DICHIARA esecutivo il decreto ingiuntivo n. 1/2024. Si comunichi CITTÀ, 10-03-2025",
                      "posizione": 700})
    return documenti, fonti


def test_monitorio_dichiarato_esecutivo_il_passo_e_il_precetto():
    documenti, fonti = _monitorio()
    stato = stato_monitorio(documenti, fonti, oggi=OGGI)
    assert stato.codice == FASE_ESECUTIVO
    assert (stato.emesso_il, stato.notificato_il, stato.opposizione_fino_al, stato.esecutivo_il) == (
        date(2024, 12, 20), date(2024, 12, 23), date(2025, 2, 3), date(2025, 3, 10))
    assert stato.passi[0]["azione"].startswith("Notificare il precetto") and "cpc_654" in stato.passi[0]["fonti"]


def test_monitorio_senza_esecutorieta_dopo_il_termine_si_chiede_l_esecutorieta():
    documenti, fonti = _monitorio(esecutivo=False)
    assert stato_monitorio(documenti, fonti, oggi=OGGI).codice == FASE_ESECUTORIETA
    assert stato_monitorio(documenti, fonti, oggi=date(2025, 1, 20)).codice == FASE_OPPOSIZIONE


def test_monitorio_provvisoriamente_esecutivo_e_opposto():
    documenti, fonti = _monitorio(esecutivo=False, notificato=False, nome_decreto="accoglimentoDecretoIngiuntivoEsecutivo.pdf")
    assert stato_monitorio(documenti, fonti, oggi=OGGI).codice == FASE_ESECUTIVO
    documenti.append({"id": "O1", "nome": "Citazione.pdf", "etichetta": "Atto di citazione in opposizione a decreto ingiuntivo", "sezione": "atti"})
    assert stato_monitorio(documenti, fonti, oggi=OGGI).codice == FASE_OPPOSTO


def test_termine_di_opposizione_con_sospensione_feriale_e_proroga():
    assert termine_opposizione(date(2024, 12, 23)) == date(2025, 2, 3)  # 01/02/2025 è sabato (art. 155 c.p.c.)
    # 40 giorni dal 20/07: la sospensione feriale salta agosto; nel lavoro non si applica (art. 3 L. 742/1969).
    assert termine_opposizione(date(2026, 7, 20)) == date(2026, 9, 29)
    assert termine_opposizione(date(2026, 7, 20), lavoro=True) == date(2026, 8, 31)


def test_le_udienze_di_un_altra_causa_dello_stesso_cliente_non_entrano():
    fascicolo = SimpleNamespace(id="F1", numero="2026/175", numero_rg="4202", anno_rg="2024", rg_completo="RG 4202/2024", id_cliente="C1")
    chiavi = chiavi_fascicolo(fascicolo)
    altra = SimpleNamespace(procedimento="RG 792/2025", id_cliente="C1", tipo=SimpleNamespace(value="UDIENZA"))
    propria = SimpleNamespace(procedimento="RG 4202/2024", id_cliente="C1", tipo=SimpleNamespace(value="UDIENZA"))
    colloquio = SimpleNamespace(procedimento="", id_cliente="C1", tipo=SimpleNamespace(value="APPUNTAMENTO"))
    udienza_senza_ruolo = SimpleNamespace(procedimento="", id_cliente="C1", tipo=SimpleNamespace(value="UDIENZA"))
    assert not appuntamento_del_fascicolo(altra, chiavi)
    assert appuntamento_del_fascicolo(propria, chiavi) and appuntamento_del_fascicolo(colloquio, chiavi)
    assert not appuntamento_del_fascicolo(udienza_senza_ruolo, chiavi)
    agenda = [SimpleNamespace(tipo="UDIENZA", stato="PROGRAMMATO", data_ora="2026-04-16T09:00:00"),
              SimpleNamespace(tipo="UDIENZA", stato="ANNULLATO", data_ora="2026-05-16T09:00:00")]
    assert udienze_in_agenda(agenda) == {"2026-04-16"}


def test_ruolo_e_deposito_dal_messaggio_di_deposito_dello_studio():
    documenti = [
        {"id": "P1", "nome": "COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO: Istanza_autorizzazione [JQ1] [RefID_001_a].EML",
         "etichetta": "PEC di deposito telematico", "data": "2025-08-26"},
        {"id": "P2", "nome": "DEPOSITO TELEMATICO: ricevuta RG: 14848 - 2025 [JQ1] [RefID_001_b].eml", "etichetta": "Comunicazione", "data": "2025-09-02"},
    ]
    fonti = [{"oggetto_id": "P2", "categoria": "ruolo", "campo": "numero_ruolo", "valore": "14848/2025", "verifica": "verificata",
              "contesto": "Oggetto: DEPOSITO TELEMATICO: ricevuta RG: 14848/2025"},
             {"oggetto_id": "S1", "categoria": "ruolo", "campo": "numero_ruolo", "valore": "99/2019", "verifica": "verificata",
              "contesto": "Sentenza n. 1/2020 nella causa iscritta al n. 99/2019"},
             {"oggetto_id": "P1", "categoria": "data", "campo": "deposito", "valore": "2025-08-26", "verifica": "plausibile"}]
    assert ruolo_dagli_atti(fonti) == "14848/2025"
    depositi = depositi_dalle_copie_pec(documenti, fonti)
    assert [(d["atto"], d["data"], d["rg"]) for d in depositi] == [("Istanza_autorizzazione", "2025-08-26", ""), ("ricevuta", "2025-09-02", "14848/2025")]


def _dati(**campi) -> DatiLettura:
    base = {"id": "F9", "numero": "2026/1", "titolo": "Prova", "tipo": "CIVILE", "stato": "IN_CORSO", "nome_cliente": "Alfa Srl"}
    base.update(campi.pop("fascicolo", {}))
    return DatiLettura(fascicolo=base, oggi=OGGI, **campi)


def test_lettura_monitorio_senza_udienze_e_con_il_precetto():
    documenti, fonti = _monitorio()
    dati = _dati(fascicolo={"numero_rg": "4202", "anno_rg": "2024", "codice_oggetto_pst": "010001",
                            "oggetto": "010001 - Decreto Ingiuntivo (Giudice di Pace)"},
                 documenti=[{"id": d["id"], "nome": d["nome"]} for d in documenti],
                 catalogo=[{"document_id": d["id"], "document_label": d["etichetta"], "document_section": d["sezione"],
                            "document_nature": d.get("natura", ""), "status": "catalogued"} for d in documenti],
                 archivio={"fonti_documenti": fonti})
    lettura = costruisci_lettura(dati)
    assert lettura["conoscenza"]["rito"]["codice"] == "decreto_ingiuntivo"
    assert lettura["fase"]["codice"] == FASE_ESECUTIVO and "10/03/2025" in lettura["fase"]["descrizione"]
    azioni = [passo["azione"] for passo in lettura["prossimi_passi"]]
    assert any(azione.startswith("Notificare il precetto") for azione in azioni)
    assert not any("udienza" in azione.lower() for azione in azioni)


def test_lettura_lavoro_la_costituzione_della_controparte_non_e_la_prossima_udienza():
    giorno = OGGI + timedelta(days=13)
    dati = _dati(fascicolo={"tipo": "LAVORO", "numero_rg": "901", "anno_rg": "2026", "codice_oggetto_pst": "222050"},
                 scadenze=[{"tipo": "DEPOSITO_ATTO", "titolo": "Costituzione del convenuto con memoria difensiva - almeno 10 giorni prima dell'udienza",
                            "data": (OGGI + timedelta(days=2)).isoformat(), "stato": "BOZZA"},
                           {"tipo": "UDIENZA", "titolo": "Udienza di discussione", "data": giorno.isoformat(), "stato": "APERTO"}])
    lettura = costruisci_lettura(dati)
    assert lettura["fase"]["prossima_udienza"] == giorno.strftime("%d/%m/%Y")
    azioni = [passo["azione"] for passo in lettura["prossimi_passi"]]
    assert f"Preparare l'udienza del {giorno:%d/%m/%Y}" in azioni
    assert not any(azione == f"Preparare l'udienza del {OGGI + timedelta(days=2):%d/%m/%Y}" for azione in azioni)


def test_lettura_volontaria_con_deposito_e_ruolo_dagli_atti():
    documenti = [{"id": "P1", "nome": "COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO: Istanza_autorizzazione [JQ1] [RefID_001_a].EML",
                  "data_documento": "2025-08-26"},
                 {"id": "P2", "nome": "DEPOSITO TELEMATICO: ricevuta RG: 14848 - 2025 [JQ1] [RefID_001_b].eml", "data_documento": "2025-09-02"}]
    fonti = [{"oggetto_id": "P2", "categoria": "ruolo", "campo": "numero_ruolo", "valore": "14848/2025", "verifica": "verificata",
              "contesto": "Oggetto: DEPOSITO TELEMATICO: ricevuta RG: 14848/2025"}]
    dati = _dati(fascicolo={"codice_oggetto_pst": "413014", "oggetto": "413014 - Autorizzazioni del giudice tutelare"},
                 documenti=documenti,
                 catalogo=[{"document_id": "P1", "document_label": "PEC di deposito telematico", "document_section": "comunicazioni", "status": "catalogued"}],
                 archivio={"fonti_documenti": fonti})
    lettura = costruisci_lettura(dati)
    assert lettura["intestazione"]["rg"] == "14848/2025"
    assert lettura["conoscenza"]["rito"]["codice"] == "volontaria"
    assert lettura["fase"]["codice"] == "iscritta_a_ruolo"
    assert "in attesa del provvedimento del giudice" in lettura["fase"]["descrizione"]
    assert any("26/08/2025" in prova for prova in lettura["fase"]["prove"])


def test_atto_dello_studio_dal_difensore_nominato():
    from pct.atti_dello_studio import atto_dello_studio

    studio = ["Avv. Mario Rossi"]
    decreto = "letto il ricorso per la concessione del decreto ingiuntivo depositato da ALFA S.R.L.-Avv. MARIO ROSSI (CF RSSMRA80A01H501U)"
    assert atto_dello_studio(decreto, studio) is True
    assert atto_dello_studio("Io sottoscritto Avv. ROSSI MARIO C.F: RSSMRA80A01H501U, con studio in Roma", studio) is True
    assert atto_dello_studio("rappresentata e difesa dall'Avv. Luigi Verdi, come da procura", studio) is False
    assert atto_dello_studio("Il Giudice, letti gli atti, rinvia", studio) is None


def test_la_notifica_ordinata_dal_giudice_non_si_chiede_se_sia_necessaria():
    from pct.fascicolo_lettura.prossimi_passi import _passi_notifiche

    notifiche = {"fallite": [], "aperte": [{"stato": "DETECTED", "atto": "ricorso.zip", "stato_etichetta": "Rilevato",
                                            "prossima_azione": "Esamina e conferma se la notifica è necessaria"}]}
    scadenze = [{"titolo": "Notifica di ricorso e decreto - almeno 30 giorni prima dell'udienza", "data": "2027-01-08", "stato": "BOZZA"}]
    passi = _passi_notifiche(notifiche, scadenze, OGGI)
    assert passi[0].azione == "Completare la notifica ordinata dal giudice entro il 08/01/2027 («ricorso.zip»)"
    assert "cpc_415" in passi[0].fonti
    assert _passi_notifiche(notifiche, [], OGGI)[0].azione.startswith("Esamina e conferma")


def test_rettifica_dell_udienza_che_e_la_data_del_decreto():
    from web.services.rettifiche_letture_storiche import pianifica_rettifiche

    def attivita(identificativo, giorno, brano):
        return SimpleNamespace(id=identificativo, tipo="UDIENZA", esito="IN_ATTESA", avvocato="", data=giorno, id_documento="D1",
                               descrizione=f"Attività per l'avvocato: Udienza di discussione. Contesto letto: {brano}",
                               note=f"PEC_DOCUMENT_PRESIDIO:docpresidio:F1:D1:udienza:{giorno}\nFonte: documento fascicolo indicizzato da Lex AI.")
    fascicolo = SimpleNamespace(id="F1", anno_rg="2026", numero_rg="161", attivita=[
        attivita("A1", "2026-02-02", "Fissazione udienza discussione n. cronol. 1918/2026 del 02/02/2026 RG n. 161/2026"),
        attivita("A2", "2026-04-16", "fissa l'udienza del 16/04/2026 e dispone che sia sostituita"),
        attivita("A3", "2026-10-16", "All'udienza del 16.10.2026 le parti hanno discusso; sentenza n. cronol. 10/2026 del 16/10/2026"),
    ])
    piano = pianifica_rettifiche(fascicolo, fatti=[], oggetti=[], scadenze=[], testi={})
    assert [voce["id"] for voce in piano] == ["A1"]
    assert "emissione del provvedimento" in piano[0]["motivo"]


def test_fascicolo_senza_ruolo_prende_le_udienze_del_cliente_che_non_sono_di_altre_cause():
    from pct.agenda_del_fascicolo import ruoli_dei_fascicoli

    senza_ruolo = SimpleNamespace(id="F2", numero="2026/9", numero_rg="", anno_rg="", rg_completo="", id_cliente="C1")
    altro = SimpleNamespace(id="F3", numero="2026/8", numero_rg="792", anno_rg="2025", rg_completo="", id_cliente="C1")
    ruoli = ruoli_dei_fascicoli([senza_ruolo, altro])
    assert ruoli == {"792/2025"}
    chiavi = chiavi_fascicolo(senza_ruolo)
    nuova_causa = SimpleNamespace(procedimento="RG 1100/2026", id_cliente="C1", tipo="UDIENZA")
    di_altra_causa = SimpleNamespace(procedimento="RG 792/2025", id_cliente="C1", tipo="UDIENZA")
    assert appuntamento_del_fascicolo(nuova_causa, chiavi, ruoli_dello_studio=ruoli)
    assert not appuntamento_del_fascicolo(di_altra_causa, chiavi, ruoli_dello_studio=ruoli)
