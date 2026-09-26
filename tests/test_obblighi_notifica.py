"""Il presidio notifiche che legge i documenti: obblighi, destinatari e termini (dati sintetici)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from pct.obblighi_notifica import (
    STATO_DA_NOTIFICARE,
    STATO_DA_VERIFICARE,
    STATO_FACOLTATIVO,
    STATO_NOTIFICATO,
    DocumentoCatalogato,
    Parte,
    Termine,
    avvocatura_distrettuale,
    obblighi_del_fascicolo,
    scadenza,
)
from pct.registro_letture.fatti_repository import Fatto

OGGI = date(2026, 9, 26)


def test_termini_liberi_e_mesi():
    assert scadenza(Termine("udienza", giorni=120, prima=True, liberi=True), date(2027, 3, 1)) == date(2026, 10, 31)
    assert scadenza(Termine("pronuncia", giorni=60), date(2026, 9, 1)) == date(2026, 10, 31)
    assert scadenza(Termine("pubblicazione", mesi=6), date(2026, 8, 31)) == date(2027, 2, 28)


def test_decreto_ingiuntivo_nostro_si_notifica_entro_60_giorni():
    di = DocumentoCatalogato("d1", "decreto.pdf", "Decreto ingiuntivo", data="2026-09-10", nostro=True)
    obblighi = obblighi_del_fascicolo([di], [Parte("Alfa S.r.l.", "controparte")], oggi=OGGI)
    assert len(obblighi) == 1
    obbligo = obblighi[0]
    assert obbligo.stato == STATO_DA_NOTIFICARE
    assert obbligo.scadenza == "2026-11-09"
    assert obbligo.natura == "perentorio"
    assert obbligo.destinatari[0]["nome"] == "Alfa S.r.l."
    assert "3-bis L. 53/1994" in obbligo.destinatari[0]["fonte"]
    assert "art. 644 c.p.c." in obbligo.regola.fonti


def test_decreto_ingiuntivo_della_controparte_non_si_notifica():
    di = DocumentoCatalogato("d1", "decreto.pdf", "Decreto ingiuntivo", data="2026-09-10", nostro=False)
    assert obblighi_del_fascicolo([di], [Parte("Alfa S.r.l.", "controparte")], oggi=OGGI) == []


def test_lato_non_letto_resta_da_verificare():
    citazione = DocumentoCatalogato("c1", "citazione.pdf", "Atto di citazione", udienze=("2027-03-01",), nostro=None)
    obbligo = obblighi_del_fascicolo([citazione], [Parte("Blu Franco", "controparte")], oggi=OGGI)[0]
    assert obbligo.stato == STATO_DA_VERIFICARE
    assert obbligo.scadenza == "2026-10-31"


def test_lavoro_contro_ministero_presso_avvocatura_letta_negli_atti():
    ricorso = DocumentoCatalogato("r1", "ricorso.pdf", "Ricorso in materia di lavoro (art. 414 c.p.c.)", nostro=True)
    parti = [
        Parte("Ministero dell'Istruzione e del Merito", "controparte", difensore="Avvocatura Distrettuale dello Stato di Reggio Calabria"),
    ]
    obbligo = obblighi_del_fascicolo([ricorso], parti, contesto={"udienze_future": ["2026-12-15"]}, oggi=OGGI)[0]
    assert obbligo.scadenza == "2026-11-14"  # 30 giorni liberi prima dell'udienza
    destinatario = obbligo.destinatari[0]
    assert "Avvocatura Distrettuale dello Stato di Reggio Calabria" in destinatario["presso"]
    assert "415, settimo comma" in destinatario["fonte"]


def test_avvocatura_dal_distretto_dell_ufficio():
    assert avvocatura_distrettuale("Tribunale di Palmi").startswith("Avvocatura distrettuale dello Stato di Reggio")
    assert "competente" in avvocatura_distrettuale("")


def test_ricorso_tar_amministrazione_e_controinteressati_con_deposito_successivo():
    ricorso = DocumentoCatalogato("t1", "ricorso_tar.pdf", "Ricorso al TAR", nostro=True)
    parti = [Parte("Comune di Alfa", "controparte"), Parte("Beta Gamma", "controinteressato")]
    obbligo = obblighi_del_fascicolo([ricorso], parti, contesto={"data_provvedimento_impugnato": "2026-09-01"}, oggi=OGGI)[0]
    assert obbligo.scadenza == "2026-10-31"
    assert {d["nome"] for d in obbligo.destinatari} == {"Comune di Alfa", "Beta Gamma"}
    assert "art. 144" in obbligo.destinatari[0]["fonte"]
    assert "art. 45 c.p.a." in obbligo.regola.dopo


def test_prova_di_notifica_successiva_chiude_l_obbligo():
    di = DocumentoCatalogato("d1", "decreto.pdf", "Decreto ingiuntivo", data="2026-09-10", nostro=True)
    obbligo = obblighi_del_fascicolo([di], [Parte("Alfa S.r.l.", "controparte")],
                                     contesto={"prove_notifica": [{"documento_id": "r9", "data": "2026-09-20"}]}, oggi=OGGI)[0]
    assert obbligo.stato == STATO_NOTIFICATO


def test_sentenza_notifica_facoltativa_presso_difensore():
    sentenza = DocumentoCatalogato("s1", "sentenza.pdf", "Sentenza", data="2026-09-01")
    obbligo = obblighi_del_fascicolo([sentenza], [Parte("Blu Franco", "controparte", difensore="Rosa Neri")], oggi=OGGI)[0]
    assert obbligo.stato == STATO_FACOLTATIVO
    assert obbligo.destinatari[0]["presso"] == "presso il difensore costituito Rosa Neri"


def test_raccolta_dal_catalogo_e_dall_archivio_esclude_i_precedenti():
    from web.services.obblighi_notifica_runtime import raccogli

    fascicolo = SimpleNamespace(id="F1", controparte="", avvocato_controparte="", documenti=[
        SimpleNamespace(id="ric", nome="ricorso_di.pdf"), SimpleNamespace(id="di", nome="decreto.pdf"), SimpleNamespace(id="prec", nome="precedente.pdf"),
    ])

    def fatto(oggetto: str, categoria: str, campo: str, valore: str, prove=None) -> Fatto:
        return Fatto(categoria=categoria, campo=campo, valore=valore, valore_letto=valore, oggetto_id=oggetto, prove=prove or [])

    fatti = [
        fatto("ric", "parte", "assistito", "Verdi Giulia", [{"codice": "lato", "esito": "ok", "dettaglio": "agisce"}]),
        fatto("ric", "parte", "controparte", "Alfa S.r.l.", [{"codice": "lato", "esito": "ok", "dettaglio": "resiste"}]),
        fatto("di", "data", "provvedimento", "2026-09-10"),
        fatto("prec", "evento", "natura_documentale", "precedente_giurisprudenziale"),
    ]
    etichette = {"ric": "Ricorso per decreto ingiuntivo", "di": "Decreto ingiuntivo", "prec": "Sentenza"}
    documenti, parti, contesto = raccogli(fascicolo, fatti, etichette)
    per_id = {d.id: d for d in documenti}
    assert "prec" not in per_id
    assert per_id["di"].nostro is True and per_id["di"].data == "2026-09-10"
    obblighi = obblighi_del_fascicolo(documenti, parti, contesto=contesto, oggi=OGGI)
    assert [(o.regola.id, o.scadenza) for o in obblighi] == [("decreto_ingiuntivo_644", "2026-11-09")]
