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


def test_ottemperanza_riusa_solo_il_ruolo_del_provvedimento_amministrativo():
    from pct.fascicolo_lettura import DatiLettura, costruisci_lettura
    from pct.ragionamento import ragiona
    from pct.ragionamento.ingressi import FontiCausa

    fascicolo = {"id": "F", "tipo": "AMMINISTRATIVO", "stato": "IN_CORSO"}
    tar = "N. 01159/2025 REG.RIC. Il Tribunale Amministrativo Regionale per il Veneto ha pronunciato SENTENZA."
    civile = "TRIBUNALE ORDINARIO di VICENZA Sentenza R.G. 195/2024."
    documenti = [
        {"id": "TAR", "nome": "Sentenza TAR", "testo": tar, "natura": "provvedimento", "etichetta": "Sentenza"},
        {"id": "CIV", "nome": "Titolo civile", "testo": civile, "natura": "provvedimento", "etichetta": "Sentenza"},
        {"id": "CERT", "nome": "Certificato", "testo": civile, "natura": "certificato_cancelleria",
         "etichetta": "Certificato della cancelleria sull'impugnazione della sentenza"},
    ]
    fatti = [{"oggetto_id": oid, "categoria": "ruolo", "campo": "numero_ruolo", "valore": rg,
              "valore_letto": letto, "verifica": "plausibile", "contesto": contesto, "posizione": 0}
             for oid, rg, letto, contesto in (("TAR", "1159/2025", "N. 01159/2025 REG.RIC.", tar),
                                             ("CIV", "195/2024", "R.G. 195/2024", civile))]
    modello = ragiona(FontiCausa(fascicolo=fascicolo, documenti=documenti, fatti=fatti, oggi=OGGI))
    assert modello.rg == "1159/2025"
    assert modello.fase["prove"] == ["Sentenza TAR"]
    assert {c.letto.oggetto_id for c in modello.conclusioni if c.codice == "termine_impugnazione"} == {"TAR"}
    catalogo = [{"document_id": d["id"], "document_nature": d["natura"], "document_label": d["etichetta"],
                 "document_section": "provvedimenti", "status": "catalogued"} for d in documenti]
    lettura = costruisci_lettura(DatiLettura(fascicolo=fascicolo, documenti=documenti, catalogo=catalogo,
                                           archivio={"fonti_documenti": fatti}, ragionamento=modello.come_dizionario(), oggi=OGGI))
    assert lettura["intestazione"]["rg"] == modello.rg
    assert lettura["fase"]["codice"] == "decisa"
    assert lettura["documenti"]["sentenza"]["id"] == "TAR"


def test_ottemperanza_accolta_presenta_l_ordine_del_tar_prima_dell_impugnazione():
    from types import SimpleNamespace

    from pct.ragionamento.modello import Fonte
    from pct.ragionamento.regole.sentenza import _sentenza_amministrativa

    sentenza = SimpleNamespace(id="TAR", nome="Sentenza TAR", copie=[], testo=(
        "Sentenza sul ricorso per l’ottemperanza. P.Q.M. "
        "definitivamente pronunciando sul ricorso, come in epigrafe proposto lo accoglie e, per l’effetto: "
        "ordina all’Amministrazione di dare esecuzione al titolo indicato in epigrafe nel termine di 60 (sessanta) "
        "giorni decorrenti dalla comunicazione o notificazione della presente sentenza; "
        "nomina quale Commissario ad acta il dirigente competente per il caso di inadempimento."
    ))
    prova = {"documenti_allegati": {"TAR"}, "accettazione_id": "RAC",
             "consegne": [{"documento_id": "RDAC", "data": "2025-12-15T11:01:00+01:00"}]}
    ctx = SimpleNamespace(posizione="attiva", prove_notifiche_storiche={
        "PEC-CIV": {**prova, "documenti_allegati": {"CIV"}}, "PEC-TAR": prova})
    esecuzione, appello = _sentenza_amministrativa(sentenza, Fonte("TAR"), grado="primo", ctx=ctx)
    assert esecuzione.codice == "verifica_ottemperanza" and esecuzione.letto.oggetto_id == "TAR"
    assert "60 giorni" in esecuzione.perche and "commissario" in esecuzione.perche and "15/12/2025" in esecuzione.perche
    assert esecuzione.prova_notifica == {"invio_id": "PEC-TAR", "accettazione_id": "RAC", "consegne_ids": ["RDAC"]}
    assert esecuzione.termine is None and appello.stato == "non_dovuto"
    ctx.posizione = "passiva"
    [appello] = _sentenza_amministrativa(sentenza, Fonte("TAR"), grado="primo", ctx=ctx)
    assert appello.stato == "dubbio"


def test_appello_ottemperanza_usa_il_termine_breve_solo_con_prova_della_stessa_sentenza():
    from datetime import date
    from types import SimpleNamespace

    from pct.ragionamento.modello import Fonte, Rito
    from pct.ragionamento.regole.sentenza import _appello_ottemperanza

    timbro = "Pubblicato il 25/07/2026. N. 00543/2026 REG.PROV.COLL. N. 00425/2025 REG.RIC."
    testo = timbro + " Sul ricorso per l’ottemperanza. Visto il ricorso."
    atto = SimpleNamespace(id="TAR", copie=[], testo=testo)
    ctx = SimpleNamespace(oggi=date(2026, 11, 16), rito=Rito("amministrativo", "Ottemperanza", "Sentenza TAR"), consegne_verificate={
        "TAR": {"data": "2026-09-03", "riferimento": "RDAC"},
        "ALTRO": {"data": "2026-07-28", "riferimento": "ALTRA_RDAC"},
    })
    appello = _appello_ottemperanza(atto, Fonte("TAR"), ctx)
    assert appello.termine.scadenza == "2026-10-05"
    assert appello.termine.decorrenza == "2026-09-03"
    atto.testo = (timbro + " Sul ricorso per l’annullamento. Visto il ricorso. "
                 "Parte ricorda di avere agito per l’ottemperanza.")
    assert _appello_ottemperanza(atto, Fonte("TAR"), ctx) is None


def test_il_provvedimento_si_riconosce_in_entrambi_gli_invii_con_prove_verificate():
    from pct.ragionamento.ingressi import FontiCausa
    from pct.ragionamento.motore import _riscontri_notifiche_storiche

    documenti = [{"id": "ORD", "sha256": "ordinanza"}]
    fatti = []
    for invio in ("PRIMO", "RINNOVO", "ALTERATO"):
        eml = {oid: oid.lower() for oid in (invio, f"RAC-{invio}", f"RDAC-{invio}")}
        documenti.extend({"id": oid, "sha256": sha} for oid, sha in eml.items())
        if invio == "ALTERATO":
            eml[invio] = "diverso"
        fatti.append({"campo": "riscontro_notifica_pec_storica", "oggetto_id": invio, "prove": [{
            "accettazione_id": f"RAC-{invio}", "consegne": [{"documento_id": f"RDAC-{invio}"}],
            "impronte_eml": eml, "impronte_allegati": ["ordinanza"],
        }]})
    _, prove = _riscontri_notifiche_storiche(FontiCausa(documenti=documenti, fatti=fatti))
    assert {oid for oid, prova in prove.items() if "ORD" in prova["documenti_allegati"]} == {"PRIMO", "RINNOVO"}


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


def test_trattazione_scritta_con_ora_del_termine_e_data_in_clausole_distinte():
    testo = ("FISSA la prima udienza del procedimento in data 16/12/2025. "
             "PRECISA che l’udienza in questione si terrà nella forma della c.d. “udienza sostituita dal deposito "
             "di note scritte” ex art. 127-ter c.p.c. INVITA le parti a depositare, entro le ore 12.00 della data "
             "in cui si terrà la suddetta udienza, note scritte contenenti esclusivamente le istanze e conclusioni.")
    lettura = leggi_provvedimento(_atto(testo, "2025-04-27"), "2539/2025")
    udienza, = lettura.udienze
    termine, = lettura.termini
    assert (udienza.data, udienza.modalita, udienza.ora) == ("2025-12-16", "note_scritte", "")
    assert (termine.scadenza, termine.ora, termine.perentorio) == ("2025-12-16", "12:00", True)


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
