"""Le regole del motore del ragionamento, una per una, con la norma che le fonda. Dati fittizi."""

from __future__ import annotations

from datetime import date

import pytest

from pct.ragionamento.atti import firmato_dal_giudice
from pct.ragionamento.modello import Atto, Rito
from pct.ragionamento.norme import norme, scheda
from pct.ragionamento.provvedimenti import leggi_provvedimento
from pct.ragionamento.regole.calcolo import a_ritroso, in_avanti
from pct.ragionamento.regole.contesto import chi
from pct.ragionamento.regole.economia import liquidazione
from pct.ragionamento.rito import contro_pa, rito_da_codice
from pct.ragionamento.testo import date_nel_testo, frasi, rg_normale

LAVORO = Rito("lavoro", "rito del lavoro", "test", sospensione_feriale=False)
CIVILE = Rito("cognizione", "cognizione", "test")
OGGI = date(2026, 11, 10)


def test_ogni_norma_citata_ha_url_normattiva_e_testo():
    for voce in norme("cpc_631", "cpc_324", "cc_2909", "cpc_415_notifica", "dpr115_art13", "dpr115_art30", "cpc_91", "cpc_93",
                      "cpc_127ter_testo", "dl669_art14", "cpc_416", "l53_art3bis"):
        assert voce["url"].startswith("https://www.normattiva.it/uri-res/N2Ls?") and voce["estratto"]
    with pytest.raises(KeyError):
        scheda("cpc_inventata")


def test_date_e_ruoli_scritti_negli_atti():
    assert [d for _a, _b, d in date_nel_testo("entro il 16.12.2026 e il 4.5.26; 20-12-2024; 9 febbraio 2027")] == [
        date(2026, 12, 16), date(2026, 5, 4), date(2024, 12, 20), date(2027, 2, 9)]
    assert rg_normale("792/25") == rg_normale("792", "2025") == "792/2025"
    assert len(frasi("Rinvia all'udienza del 2.11.2026. Sostituisce l'udienza ex art. 127 ter c.p.c. entro il 1.11.2026.")) == 2


def test_rito_dal_catalogo_ministeriale_e_pubblica_amministrazione():
    assert rito_da_codice("510002")[0] == "esecuzione_presso_terzi"
    assert rito_da_codice("010001")[0] == "monitorio"
    assert rito_da_codice("413014")[0] == "volontaria_giurisdizione"
    assert rito_da_codice("222050")[0] == "lavoro"
    assert contro_pa("Ministero dell'Istruzione e del Merito") and not contro_pa("Beta s.r.l.")


def test_computo_art_155_e_feriale():
    # 30 giorni dal 20/04/2026: 20/05/2026, senza sospensione feriale nel lavoro (art. 3 L. 742/1969)
    assert in_avanti(date(2026, 4, 20), 30, rito=LAVORO, oggi=OGGI, perentorio=True, evento="notifica", norma="art. 434").scadenza == "2026-05-20"
    # in cognizione la sospensione dal 1° al 31 agosto sposta la scadenza (art. 1 L. 742/1969)
    termine = in_avanti(date(2026, 7, 20), 30, rito=CIVILE, oggi=OGGI, perentorio=True, evento="notifica", norma="art. 325")
    assert termine.scadenza > "2026-08-19" and termine.sospensione_feriale.startswith("si applica")
    # a ritroso: trenta giorni prima del 09/02/2027 è domenica 10/01/2027, si anticipa al venerdì 08/01/2027
    assert a_ritroso(date(2027, 2, 9), 30, rito=LAVORO, oggi=OGGI, perentorio=None, evento="udienza", norma="art. 415").scadenza == "2027-01-08"


def test_termine_scaduto_dice_conseguenze_e_rimedi():
    scaduto = in_avanti(date(2026, 9, 1), 10, rito=LAVORO, oggi=OGGI, perentorio=True, evento="comunicazione", norma="x")
    assert scaduto.scaduto and scaduto.giorni_residui < 0 and "art. 153" in scaduto.rimedi
    ordinatorio = in_avanti(date(2026, 9, 1), 10, rito=LAVORO, oggi=OGGI, perentorio=False, evento="comunicazione", norma="x")
    assert "art. 154" in ordinatorio.rimedi


def test_parte_onerata_riferita_a_noi():
    assert chi("parte_attiva", "attiva") == "noi" and chi("parte_passiva", "attiva") == "controparte"
    assert chi("parte_attiva", "passiva") == "controparte" and chi("tutte_le_parti", "ignota") == "tutte_le_parti"
    assert chi("parte_attiva", "ignota") == "ignoto"


def _atto(testo, data="2026-10-09"):
    return Atto("P", "p.pdf", "provvedimento", "Provvedimento", autore="giudice", data=data, testo=testo)


def test_udienza_non_tenuta_e_udienza_passata_non_sono_udienze_future():
    lettura = leggi_provvedimento(_atto("Comunica che l'udienza del 6.7.2026 non sarà tenuta; la causa è rinviata all'udienza del "
                                        "2.11.2026 che sarà trattata in presenza. Palmi 3.7.2026 Il Giudice", "2026-07-03"), "792/2025")
    assert [(u.data, u.modalita) for u in lettura.udienze] == [("2026-11-02", "presenza")]


def test_onerato_e_perentorieta_lette_nella_frase():
    lettura = leggi_provvedimento(_atto("DISPONE che il presente provvedimento sia notificato, a cura della creditrice, alla "
                                        "debitrice ed ai terzi, entro il 10.1.2027. Palmi 24.11.2026 Il G.E.", "2026-11-24"), "1/2026")
    termine = lettura.termini[0]
    assert termine.onerato == "parte_attiva" and not termine.perentorio and termine.scadenza == "2027-01-10"
    assert termine.adempimento.startswith("Notificare il presente provvedimento")


def test_firma_del_giudice_riconosce_il_provvedimento_non_l_atto_di_parte():
    assert firmato_dal_giudice("rinvia all'udienza del 21.12.2026. Si comunichi Il Giudice O.T. Dott. Bianchi")
    assert not firmato_dal_giudice("Voglia l'Ill.mo Giudice accogliere il ricorso. Avv. Mario Rossi")


def test_liquidazione_delle_spese():
    letta = liquidazione("Le spese di questa procedura, liquidate in € 76,00 per spese non imponibili ed € 300,00 per compensi "
                         "professionali, oltre rimborso spese generali nella misura del 15%")
    assert letta["compensi"] == 300.0 and letta["esborsi"] == 76.0 and letta["accessori"] and not letta["distrazione"]
    assert liquidazione("rigetta il ricorso e compensa le spese") is None


def test_termine_dalla_comunicazione_richiede_la_data_di_consegna():
    from pct.ragionamento.modello import Atto, Fonte, Rito, TermineAssegnato
    from pct.ragionamento.regole.contesto import Contesto
    from pct.ragionamento.regole.termini_assegnati import conclusioni_termini

    fonte = Fonte("ordine", "Decreto.pdf", "Dieci giorni dalla comunicazione", "2026-11-02")
    ordine = Atto("ordine", "Decreto.pdf", "provvedimento", "Decreto", autore="giudice", data=fonte.data)
    termine = TermineAssegnato("", "Depositare i documenti", "parte_attiva", True, fonte, formula="da_comunicazione:10")
    contesto = Contesto(
        fascicolo_id="F1", rg="123/2026", ufficio="Tribunale", rito=Rito("lavoro", "Lavoro", "fascicolo"),
        posizione="attiva", atti=[ordine], udienze=[], termini=[termine], ordini=[], notifiche=[],
        depositi=[], comunicazioni=[], oggi=date(2026, 11, 11),
    )

    (esito,) = conclusioni_termini(contesto)
    assert esito.stato == "dubbio"
    assert esito.termine is None
    assert esito.dubbi[0].codice == "comunicazione_non_trovata"
