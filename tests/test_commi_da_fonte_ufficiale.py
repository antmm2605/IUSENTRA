"""Commi numerati dalla struttura dell'XML ufficiale di Normattiva, mai dividendo per frasi (collaudo 21/11/2026)."""
from lex.normativa.commi import commi_articolo, raggruppa_commi
from lex.normativa.presentazione_articolo import arricchisci

CPC_155 = ("Art. 155. (Computo dei termini). Nel computo dei termini a giorni o ad ore, si escludono il giorno o l'ora "
           "iniziali. Per il computo dei termini a mesi o ad anni, si osserva il calendario comune. I giorni festivi si "
           "computano nel termine. Se il giorno di scadenza e' festivo, la scadenza e' prorogata di diritto al primo "
           "giorno seguente non festivo. La proroga prevista dal quarto comma si applica altresi' ai termini per il "
           "compimento degli atti processuali svolti fuori dell'udienza che scadono nella giornata del sabato.(116) "
           "((125)) Resta fermo il regolare svolgimento delle udienze e di ogni altra attivita' giudiziaria, anche "
           "svolta da ausiliari, nella giornata del sabato, che ad ogni effetto e' considerata lavorativa. (116) ((125)) "
           "----------------- AGGIORNAMENTO (116) La L. 28 dicembre 2005, n. 263 ...")
CC_1284 = ("Art. 1284. (Saggio degli interessi). Il saggio degli interessi legali e' determinato in misura pari al 5 per "
           "cento in ragione d'anno. Il Ministro del tesoro, con proprio decreto pubblicato nella Gazzetta Ufficiale della "
           "Repubblica italiana non oltre il 15 dicembre dell'anno precedente a quello cui il saggio si riferisce, puo' "
           "modificarne annualmente la misura, sulla base del rendimento medio annuo lordo dei titoli di Stato di durata "
           "non superiore a dodici mesi e tenuto conto del tasso di inflazione registrato nell'anno. Qualora entro il 15 "
           "dicembre non sia fissata una nuova misura del saggio, questo rimane invariato per l'anno successivo. (129a) "
           "(140a) (151a) (161a) (193a) (211a) (221a) (237a) (244a) (252a) (260a)(276) (280) (299) (307) (314) (321a) "
           "(327)(336a) ((348)) Allo stesso saggio si computano gli interessi convenzionali, se le parti non ne hanno "
           "determinato la misura. Gli interessi superiori alla misura legale devono essere determinati per iscritto; "
           "altrimenti sono dovuti nella misura legale. Se le parti non ne hanno determinato la misura, dal momento in cui "
           "e' proposta domanda giudiziale il saggio degli interessi legali e' pari a quello previsto dalla legislazione "
           "speciale relativa ai ritardi di pagamento nelle transazioni commerciali. (242) La disposizione del quarto "
           "comma si applica anche all'atto con cui si promuove il procedimento arbitrale. (242)")


def test_art_155_cpc_sei_commi_come_normattiva():
    commi = commi_articolo(CPC_155, "1940-10-28", "1443", "Art. 155.")
    assert [c[:28] for c in commi] == ["Nel computo dei termini a gi", "Per il computo dei termini a", "I giorni festivi si computan",
                                      "Se il giorno di scadenza e' ", "La proroga prevista dal quar", "Resta fermo il regolare svol"]


def test_art_1284_cc_cinque_commi_e_il_primo_ha_tre_frasi():
    commi = commi_articolo(CC_1284, "1942-03-16", "262", "1284")
    assert len(commi) == 5
    assert commi[0].count(". ") >= 2  # tre frasi, un solo comma: nessuna divisione per frasi
    item = arricchisci({"number": "1284", "urn": "urn:nir:stato:regio.decreto:1942-03-16;262", "text": CC_1284,
                        "data_atto": "1942-03-16", "numero": "262"})
    assert [c["numero"] for c in item["commi"]] == ["1", "2", "3", "4", "5"]
    assert item["commi"][0]["testo"].startswith("Il saggio degli interessi legali è determinato")
    assert item["intestazione_lettura"] == "Art. 1284. (Saggio degli interessi)."


def test_testo_diverso_dalla_fonte_resta_intero():
    assert commi_articolo(CPC_155.replace("calendario comune", "calendario civile"), "1940-10-28", "1443", "155") is None


def test_elenchi_e_righe_in_minuscolo_restano_nel_comma():
    assert raggruppa_commi(["Essa deve contenere:", "1) l'indicazione del giudice;", "a) la data;",
                            "per cento per le cause", "(67)(72)", "La sentenza è sottoscritta."]) == [
        "Essa deve contenere: 1) l'indicazione del giudice; a) la data; per cento per le cause (67)(72)",
        "La sentenza è sottoscritta."]


def test_segni_delle_modifiche_e_richiami_di_nota_non_sono_commi():
    # D.M. 55/2014, art. 4 nell'Akoma Ntoso di Normattiva: «((» e «))» stanno in paragrafi a sé.
    assert raggruppa_commi(["((13))", "1. Nelle controversie non si applica.", "2. Il presidente designa.",
                            "((", "2-bis. Il comma aggiunto.", "))", "3. Fermo quanto previsto."]) == [
        "((13)) 1. Nelle controversie non si applica.", "2. Il presidente designa.", "(( 2-bis. Il comma aggiunto. ))",
        "3. Fermo quanto previsto."]


def test_numerazione_dei_commi_coerente_con_la_fonte():
    from lex.normativa.commi import numerazione_coerente

    assert numerazione_coerente(["((13)) 1. Primo.", "(( 1-bis. Aggiunto. ))", "2. Secondo."])
    assert numerazione_coerente(["Nel computo dei termini.", "Per il computo a mesi."])  # codici: commi senza numero
    assert not numerazione_coerente(["((", "1. Primo.", "))"])  # un segno da solo non è un comma
    assert not numerazione_coerente(["1. Primo.", "«2. Testo citato da altra legge.", "2. Secondo."])
    assert not numerazione_coerente(["1. Primo.", "2. Secondo.", "2. Ripetuto."])


def test_la_rubrica_nel_primo_paragrafo_non_diventa_il_comma_1():
    import scripts.normativa_commi_da_akn as akn

    intestazione, commi = akn._separa_rubrica(["Art. 2"], ["(Ambito di applicazione)", "1. Le norme si applicano.", "2. Le spese."])
    assert intestazione == ["Art. 2", "(Ambito di applicazione)"] and commi == ["1. Le norme si applicano.", "2. Le spese."]
