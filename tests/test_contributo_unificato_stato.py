"""Stato unico del contributo unificato (art. 13 e art. 9, comma 1-bis, D.P.R. 115/2002) e sue fonti."""

from __future__ import annotations

import json

from pct.contributo_unificato_stato import e_fonte_del_contributo, solo_fonti_del_contributo, stato_contributo
from pct.fascicolo_conto_economico import riga_contributo

def test_correzione_catalogo_collega_autocertificazione_e_riusa_lettura_e_deposito(monkeypatch):
    from types import SimpleNamespace

    from pct.document_intelligence.sezioni import NATURA_AUTOCERTIFICAZIONE_CU
    from web.services import contributo_stato_runtime as runtime

    documento = SimpleNamespace(id="D1", nome="Autocertificazione.PDF", data_deposito_portale="")
    fascicolo = SimpleNamespace(id="F1", tipo="LAVORO", documenti=[documento])
    prova = {"id": "D1", "etichetta": "Dichiarazione dell’assistito", "natura": NATURA_AUTOCERTIFICAZIONE_CU,
             "confermato": True, "nome": documento.nome, "href": runtime.href_documento("F1", "D1")}
    monkeypatch.setattr(runtime, "documenti_contributo", lambda _: [prova])
    monkeypatch.setattr(
        "web.services.archivio_letture_runtime.testi_indice_archivio",
        lambda _: {"D1": "Dichiaro per l’anno 2022 un reddito non superiore a euro 38.514,03."},
    )

    senza_deposito = runtime.stato_contributo_fascicolo(fascicolo, {})
    assert senza_deposito["etichetta"] == "Da verificare"
    assert senza_deposito["documento"]["href"] == prova["href"]
    assert "deposito" in senza_deposito["dettaglio"]

    documento.data_deposito_portale = "2023-09-13"
    esito = runtime.stato_contributo_fascicolo(fascicolo, {})
    assert esito["etichetta"] == "Esente"
    assert "2022" in esito["dettaglio"]
    assert esito["documento"]["id"] == "D1"


_AUTOCERT = {"etichetta": "Contributo unificato / esenzione", "id": "D1", "nome": "AUTOCERTIFICAZIONE_REDDITO.PDF",
             "href": "/fascicoli/F1/documenti/D1/visualizza", "confermato": False}
_RICEVUTA = {"etichetta": "Contributo unificato / pagamento", "id": "D2", "nome": "Ricevuta pagoPA.pdf",
             "href": "/fascicoli/F1/documenti/D2/visualizza", "confermato": True}


def test_esente_con_autocertificazione_depositata_da_confermare():
    stato = stato_contributo({"status": "non_previsto"}, [_AUTOCERT])
    assert stato["codice"] == "esente_da_confermare" and stato["categoria"] == "esente"
    assert stato["etichetta"] == "Esente, da confermare"
    assert stato["norma"] == "art. 9, comma 1-bis, D.P.R. 115/2002"
    assert stato["documento"] == {"id": "D1", "nome": "AUTOCERTIFICAZIONE_REDDITO.PDF", "href": "/fascicoli/F1/documenti/D1/visualizza"}


def test_esenzione_dalla_voce_del_fascicolo_senza_catalogo():
    # Caso 9A681FDF: la voce economica indica la copia di deposito dell'autocertificazione, il catalogo non la ha.
    stato = stato_contributo({"status": "non_previsto", "documento_fonte": "COPIA ... AUTOCERTIFICAZIONE_...ESENZIONE_CONTRIBUTO_UNIFICATO_2025.EML",
                              "documento_id": "F1E4404B", "href": "/f"})
    assert stato["etichetta"] == "Esente, da confermare" and stato["documento"]["id"] == "F1E4404B"


def test_esenzione_registrata_dall_avvocato_e_confermata():
    stato = stato_contributo({"status": "non_previsto", "documento_fonte": "autocertificazione.pdf", "manuale": True})
    assert stato["codice"] == "esente" and stato["confermato"] is True


def test_dovuto_e_pagato_con_ricevuta_confermata():
    stato = stato_contributo({"status": "pagato", "importo": 259}, [_RICEVUTA])
    assert stato["codice"] == "pagato" and stato["etichetta"] == "Versato"
    assert stato["importoLabel"] == "€ 259,00" and stato["norma"] == "art. 13 D.P.R. 115/2002"
    assert stato["documento"]["id"] == "D2"


def test_pagato_letto_dall_archivio_resta_da_confermare():
    stato = stato_contributo({"status": "pagato", "importo": 98, "documento_fonte": "Ricevuta telematica.pdf"})
    assert stato["codice"] == "pagato_da_confermare" and stato["categoria"] == "dovuto_pagato"


def test_anticipazione_forfettaria_non_e_contributo():
    stato = stato_contributo({"status": "pagato", "importo": 125, "importiLetti": ["27.00", "98.00"]}, [_RICEVUTA])
    # € 27 è l'anticipazione forfettaria (art. 30): il contributo è € 98, senza chiedere conferma.
    assert stato["codice"] == "pagato" and stato["importo"] == 98.0


def test_tre_importi_letti_restano_da_confermare():
    stato = stato_contributo({"status": "pagato", "importo": 125, "importiLetti": ["27.00", "98.00", "43.00"]}, [_RICEVUTA])
    assert stato["codice"] == "pagato_da_confermare" and stato["importo"] is None
    assert "anticipazione forfettaria" in stato["dettaglio"]


def test_dovuto_e_non_pagato():
    stato = stato_contributo({"status": "da_registrare", "importo": 518})
    assert stato["codice"] == "da_pagare" and stato["etichetta"] == "Da versare" and stato["importoLabel"] == "€ 518,00"


def test_non_dovuto_per_decisione_dell_avvocato():
    stato = stato_contributo({"status": "non_previsto", "manuale": True})
    assert stato["codice"] == "non_dovuto" and stato["etichetta"] == "Non dovuto" and stato["documento"] is None


def test_senza_fonte_da_verificare():
    # «Non previsto» scritto da una lettura automatica senza documento non è un'esenzione.
    for voce in ({}, {"status": "non_previsto"}, {"status": "da_registrare"}):
        stato = stato_contributo(voce)
        assert stato["codice"] == "da_verificare" and stato["etichetta"] == "Da verificare" and stato["documento"] is None


def test_ricevuta_solo_proposta_non_vince_sull_autocertificazione():
    stato = stato_contributo({}, [{**_RICEVUTA, "confermato": False}, _AUTOCERT])
    assert stato["codice"] == "esente_da_confermare"


def test_conto_economico_usa_la_stessa_etichetta():
    voce, documenti = {"status": "non_previsto"}, [_AUTOCERT]
    riga = riga_contributo(voce, documenti)
    assert riga["stato"] == stato_contributo(voce, documenti)["etichetta"]
    assert riga["statoContributo"]["codice"] == "esente_da_confermare"


def _fonte(campo: str, tipo: str = "", documento: str = "D") -> dict:
    prove = [{"codice": "dichiarazione_economica", "dettaglio": json.dumps({"tipo": tipo})}] if tipo else []
    return {"campo": campo, "documentoId": documento, "tipo": "documento", "prove": prove}


def test_verifiche_mostrano_solo_le_fonti_del_contributo():
    fonti = [_fonte("esenzione_cu_dichiarata", "autocertificazione", "A"),
             _fonte("esenzione_cu_dichiarata", "richiamo_nell_atto", "RICORSO"),
             _fonte("esenzione_cu_dichiarata", "richiamo_nell_atto", "NOTIFICA"),
             _fonte("contributo_unificato", documento="RICEVUTA"),
             _fonte("esenzione_cu_dichiarata", "attestazione_registro", "REGISTRO"),
             _fonte("esenzione_cu_dichiarata", "autocertificazione", "A")]
    assert [f["documentoId"] for f in solo_fonti_del_contributo(fonti)] == ["A", "RICEVUTA", "REGISTRO"]


def test_fonte_senza_campo_esclusa_solo_se_e_un_richiamo():
    assert e_fonte_del_contributo({"riscontri": ["Autocertificazione reddituale: riscontrare il dichiarante."]})
    assert not e_fonte_del_contributo({"riscontri": ["L'atto richiama l'esenzione; il richiamo non sostituisce l'autocertificazione reddituale."]})


def test_anticipazione_forfettaria_non_chiede_conferma():
    from pct.contributo_unificato_stato import stato_contributo
    voce = {"status": "pagato", "importo": 27, "importiLetti": [27, 259], "documento_fonte": "ricevuta.pdf"}
    esito = stato_contributo(voce, [{"etichetta": "Contributo unificato / pagamento", "id": "D1", "nome": "ricevuta.pdf",
                                     "confermato": True}])
    assert esito["codice"] == "pagato"
    assert esito["importo"] == 259.0


def test_lettura_certa_dal_contenuto():
    from pct.document_intelligence.certezza_lettura import lettura_certa
    assert lettura_certa("proposed", 98)
    assert lettura_certa("confirmed", 0)
    assert not lettura_certa("proposed", 80)
    assert not lettura_certa("review_required", 97)


def test_invito_rideposito_non_prova_esenzione():
    from pct.esenzione_reddito_cu import invito_rideposito, leggi_autocertificazione

    testo = (
        "TRIBUNALE ORDINARIO DI BRESCIA. SI INVITA A RIDEPOSITARE L’AUTOCERTIFICAZIONE "
        "ATTESTANTE IL DIRITTO ALL’ESENZIONE DAL PAGAMENTO DEL CONTRIBUTO UNIFICATO. "
        "Quella allegata si riferisce ai redditi percepiti nel 2023 e non nel 2022. "
        "La soglia riportata è euro 35.240,04."
    )
    assert invito_rideposito(testo)
    assert leggi_autocertificazione(testo)["soglia"] is None
    fonte = {"id": "INV", "nome": "Invito.pdf", "href": "/invito"}
    stato = stato_contributo(
        {"invitiRideposito": [fonte]},
        [{**fonte, "etichetta": "Contributo unificato / Esenzione", "confermato": True}],
    )
    assert stato["codice"] == "da_verificare"
    assert stato["ruoloFonti"] == "invito al rideposito"
    assert stato["fonti"] == [fonte]
