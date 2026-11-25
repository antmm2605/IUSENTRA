"""Usi dei calcolatori con le parole dell'avvocato, normalizzazione tollerante e scelta per categoria di richiesta.

Le frasi sono scritte per categoria (calcolo descritto senza «calcola», termini con «notificata/scade/udienza»,
calcolatori confondibili, pratica nominata, norma a una data, voci economiche, modelli e norme, ricerca nello studio,
filtri facoltativi, nome dell'istituto, sequenze, refusi); non vengono da nessun banco di misura.
"""
from __future__ import annotations

import re

import pytest

from lex.strumenti.mappa import mappa, valida_chiamata
from lex.strumenti.normalizzazione import normalizza_domanda
from lex.strumenti.scelta import scegli
from lex.strumenti.scelta_calcoli import calcolatore
from lex.strumenti.usi_calcolatori import CAMPI_DA_USO, USI
from legal_ocr.lessico.italiano import vocabolario_completo

# Correggere un refuso richiede il dizionario italiano (hunspell-it, nell'immagine e nella CI): senza, non si corregge.
CON_DIZIONARIO = pytest.mark.skipif(not vocabolario_completo(), reason="dizionario italiano hunspell-it non installato")


def test_ogni_calcolatore_ha_un_uso_e_le_scelte_esistono():
    calc = mappa()["calcolatori"]
    con_uso = {i for i, _, _ in USI}
    assert set(calc) - con_uso <= {"tabella_istat", "tabella_tassi"} or not set(calc) - con_uso, sorted(set(calc) - con_uso)
    assert con_uso <= set(calc)
    for ident, campo, valore, schema in CAMPI_DA_USO:
        re.compile(schema)
        assert campo in calc[ident]["campi"] and valore in calc[ident]["campi"][campo]["valori"], (ident, campo, valore)


@pytest.mark.parametrize("scritto,atteso", [
    pytest.param("qunato costa il contributo unifcato", "quanto costa il contributo unificato", marks=CON_DIZIONARIO),
    pytest.param("sentneza notificta il 2/2/2026", "sentenza notificata il 2/2/2026", marks=CON_DIZIONARIO),
    ("Come si procede per ricorso al TAR?", "Come si procede per ricorso al TAR?"),
    ("lavoratore licenziato", "lavoratore licenziato"),
    ("accertamento tecnico preventivo", "accertamento tecnico preventivo"),
])
def test_normalizzazione_corregge_solo_refusi(scritto, atteso):
    assert normalizza_domanda(scritto).split(" [")[0] == atteso


@pytest.mark.parametrize("scritto", ["Ho saltato la scadenza dell'F24", "la quarta PEC del deposito",
                                     "qunato costa il contributo unifcato"])
def test_senza_dizionario_italiano_non_si_corregge_nessuna_parola(scritto, monkeypatch):
    """CI del 25/11/2026, senza hunspell-it: «saltato» diventava «saldato» e «quarta» «quaranta». Senza dizionario non si
    può distinguere un refuso da una parola vera, quindi la domanda resta com'è scritta."""
    import lex.strumenti.normalizzazione as normalizzazione

    monkeypatch.setattr(normalizzazione, "_vocabolario_completo", lambda: False)
    normalizzazione._corretta.cache_clear()
    try:
        assert normalizzazione.correggi_refusi(scritto) == scritto
    finally:
        normalizzazione._corretta.cache_clear()


@pytest.mark.parametrize("domanda,atteso", [
    ("Incidente stradale del 12/04/2024, 38 anni e 7 punti di invalidità: che risarcimento?", "danno_biologico"),
    ("Morto senza testamento, lascia moglie e due figli: come si divide l'eredità di 400.000 euro?", "successione_legittima"),
    ("Quanto pagano di imposta di successione i figli su 1.500.000 euro?", "imposte_successione"),
    ("Furto commesso il 10/02/2015: il reato è già prescritto?", "prescrizione_penale"),
    ("Il canone di 900 euro va aggiornato all'ISTAT: a quanto arriva?", "canone_locazione"),
    ("Reddito 2025 di 60.000 euro: quanti contributi alla Cassa Forense?", "contributi_cassa_forense"),
    ("Il CTU ha lavorato 14 vacazioni: quanto gli spetta?", "ctu"),
    ("Qual è il giudice di pace competente per il comune di Pavia?", "uffici_competenti"),
    ("Una causa da 4.000 euro per un'auto difettosa va dal giudice di pace o in tribunale?", "competenza_valore"),
    ("Ricevuto avviso 415-bis il 05/11/2026: entro quando la memoria?", "termini_penali"),
    ("Delibera condominiale del 10/10/2026, sono assente: entro quando la impugno?", "termini_processuali"),
    ("Quanto costa iscrivere a ruolo un decreto ingiuntivo di 25.000 euro?", "contributo_unificato"),
    ("Ho versato l'IMU con 40 giorni di ritardo: quanto pago con il ravvedimento?", "ravvedimento_operoso"),
    ("Sentenza notificata il 03/03/2026: fino a quando posso appellare?", "impugnazioni"),
    ("Udienza del 15/01/2027 con termine per note scritte: quando scade il deposito?", "termini_processuali"),
    ("La vedova ha diritto alla pensione del marito: che percentuale le spetta?", "reversibilita"),
    ("Due figli e il coniuge, testamento che lascia tutto a un estraneo: legittima lesa?", "quote_riserva"),
    ("Mi serve la tabella del catasto per il gruppo C, quali categorie comprende?", "categorie_catastali"),
    ("Cosa prevede l'art. 1284 c.c.?", ""),
    ("Prassi dell'Agenzia delle Entrate sul ravvedimento operoso", ""),
    ("Quanto abbiamo fatturato su questo incarico?", ""),
])
def test_calcolatore_dal_linguaggio_naturale(domanda, atteso):
    assert calcolatore(normalizza_domanda(domanda)) == atteso or (
        atteso == "" and [c.nome for c in scegli(domanda)][:1] != ["calcolo"])


@pytest.mark.parametrize("domanda,fa,attesi", [
    ("Quando è la prossima udienza della pratica Bertolazzi?", False, [("fascicolo_quadro", {"fascicolo": "Bertolazzi"})]),
    ("Che scadenze ha il fascicolo RG 4521/2025?", False, [("scadenziario", {"fascicolo": "RG 4521/2025"})]),
    ("Come era l'art. 2051 c.c. al 01/01/2010?", False, [("norma_testo_vigente", {"articolo": "2051", "alla_data": "01/01/2010"})]),
    ("La fattura elettronica di questa pratica è stata scartata dallo SDI?", True, [("economia_conto", {"voce": "sdi"})]),
    ("Il cliente non ha ancora pagato la parcella: quanto ci deve?", True, [("economia_conto", {"voce": "pagamenti"})]),
    ("Quali riferimenti normativi richiama il modello di atto di citazione?", False, [("norme_modello", {})]),
    ("Abbiamo mai gestito una causa di responsabilità medica?", False, [("ricerca_studio", {})]),
    ("Cassazione sezione lavoro sul demansionamento nel 2023", False,
     [("giurisprudenza_cassazione_consulta", {"sezione": "lavoro", "anno": 2023})]),
    ("Sentenze del TAR Lombardia sulle interdittive antimafia", False, [("giustizia_amministrativa", {"sede": "Lombardia"})]),
    ("Circolari INPS del 2024 sull'assegno unico", False, [("prassi_ade_inps", {"ente": "inps", "anno": 2024})]),
    ("Mostrami le scadenze ancora aperte", False, [("scadenziario", {"stato": "aperte"})]),
    ("Spiegami come si chiede un'ingiunzione di pagamento europea", False,
     [("procedura_guidata", {"procedura": "ingiunzione di pagamento europea"})]),
    ("Trovami l'art. 1385 c.c. e poi calcola gli interessi legali su 10.000 euro dal 01/01/2024", False,
     [("norma_testo_vigente", {"articolo": "1385"}), ("calcolo", {"strumento": "interessi"})]),
    ("Il ricorso per cassazione contro la sentenza pubblicata il 10/09/2025: ultimo giorno utile?", False,
     [("calcolo", {"strumento": "impugnazioni"})]),
])
def test_scelta_per_categoria(domanda, fa, attesi):
    scelte = scegli(domanda, fascicolo_aperto=fa)
    assert [c.nome for c in scelte] == [n for n, _ in attesi]
    for c, (_, parametri) in zip(scelte, attesi, strict=True):
        assert all(c.parametri.get(k) == v for k, v in parametri.items()), (c.parametri, parametri)
        assert valida_chiamata(c.nome, c.to_dict()["parametri"]) == []


def test_pratica_nominata_non_e_mai_il_fascicolo_corrente():
    for domanda in ("Termini aperti nella vertenza Quartarari contro Fincantieri?", "Documenti della causa RG 77/2024"):
        assert all(c.parametri.get("fascicolo") != "corrente" for c in scegli(domanda))


@pytest.mark.parametrize("domanda,strumento,campi", [
    ("Appello contro sentenza penale di condanna letta in udienza il 12/11/2026", "termini_penali", {"tp_atto": "impugnazione_sentenza"}),
    ("L'assemblea di condominio ha deliberato il 03/11/2026 e io ero contrario: quanto tempo ho per impugnare?",
     "termini_processuali", {"term_modello": "CIV_IMPUGNAZIONE_DELIBERA_1137"}),
    ("Verbale della polizia locale notificato il 15/10/2026 per divieto di sosta: entro quando faccio opposizione?",
     "termini_processuali", {}),
    ("Il giudice del lavoro ha respinto il ricorso con sentenza notificata il 01/08/2026: entro quando appello?",
     "impugnazioni", {"imp_sospensione_feriale": "esclusa", "imp_data_notificazione": "01/08/2026"}),
    ("Sentenza della Corte di giustizia tributaria depositata il 10/06/2026: entro quando l'appello?",
     "termini_processuali", {"term_modello": "TRIB_APPELLO_51"}),
])
def test_il_rito_decide_il_calcolatore_dei_termini(domanda, strumento, campi):
    scelta = scegli(domanda)[0]
    assert (scelta.nome, scelta.parametri["strumento"]) == ("calcolo", strumento)
    assert all(scelta.parametri.get("campi", {}).get(k) == v for k, v in campi.items())


@pytest.mark.parametrize("domanda,fa,attesi", [
    ("Prossima udienza del procedimento R.G. 3321/2024?", False, [("fascicolo_quadro", {"fascicolo": "RG 3321/2024"})]),
    ("Documenti caricati nella causa iscritta al n. 908/2025 R.G.", False, [("documenti_fascicolo", {"fascicolo": "RG 908/2025"})]),
    ("Mi serve un fac simile di atto di opposizione a decreto ingiuntivo", False, [("modelli_atto", {})]),
    ("Quali articoli di legge stanno alla base del modello di comparsa di costituzione?", False, [("norme_modello", {})]),
    ("Cerca in tutto lo studio la parola usucapione", False, [("ricerca_studio", {})]),
    ("Il preventivo inviato a Cerruti è stato accettato?", False, [("economia_conto", {"cliente": "Cerruti", "voce": "preventivi"})]),
    ("Ci sono mail di Maltoni della settimana scorsa?", False, [("pec_comunicazioni", {"mittente": "Maltoni"})]),
    ("Modelli di ricorso in materia di famiglia", False, [("modelli_atto", {"materia": "famiglia"})]),
    ("Prassi delle Entrate del 2022 sul superbonus", False, [("prassi_ade_inps", {"ente": "agenzia_entrate", "anno": 2022})]),
    ("Il PDF della memoria è troppo grande per il PCT?", False, [("deposito_telematico", {"controllo": "pdf"})]),
    ("Scadenze imminenti dello studio", False, [("scadenziario", {"stato": "aperte"})]),
    ("Apri il fascicolo Tognazzi e poi calcola entro quando appellare la sentenza notificata il 05/11/2026", False,
     [("fascicolo_quadro", {"fascicolo": "Tognazzi"}), ("calcolo", {"strumento": "impugnazioni"})]),
    ("Guarda il conto economico di questa pratica e calcola gli interessi legali su 3.000 euro dal 01/02/2026", True,
     [("economia_conto", {"voce": "conto"}), ("calcolo", {"strumento": "interessi"})]),
])
def test_categorie_della_seconda_rimisura(domanda, fa, attesi):
    scelte = scegli(domanda, fascicolo_aperto=fa)
    assert [c.nome for c in scelte] == [n for n, _ in attesi]
    for c, (_, parametri) in zip(scelte, attesi, strict=True):
        assert all(c.parametri.get(k) == v for k, v in parametri.items()), (c.parametri, parametri)


@pytest.mark.parametrize("domanda,fa,attesi", [
    ("Mi è stato notificato il 06/11/2026 l'avviso della richiesta di archiviazione: entro quando l'opposizione?", False,
     [("calcolo", {"strumento": "termini_penali"})]),
    ("Quanto dovrà pagare il cliente di contributo unificato per l'appello su una causa da 60.000 euro?", False,
     [("calcolo", {"strumento": "contributo_unificato"})]),
    ("Quanto ha già pagato il cliente di contributo unificato in questa causa?", True,
     [("economia_conto", {"voce": "contributo_unificato"})]),
    ("Udienze del proc. n. 2210/2023", False, [("fascicolo_quadro", {"fascicolo": "RG 2210/2023"})]),
    ("Termini aperti nella causa 451/2024", False,
     [("scadenziario", {"fascicolo": "RG 451/2024", "stato": "aperte"}), ("fascicolo_catena", {"fascicolo": "RG 451/2024"})]),
    ("Decodifica il codice fiscale MRCPLA80A01F205X", False, [("calcolo", {"strumento": "codice_fiscale"})]),
    ("Qual era il tasso legale nel 2015?", False, [("calcolo", {"strumento": "tabella_tassi"})]),
    ("10 milioni di lire del 1995 quanto valgono oggi rivalutati?", False, [("calcolo", {"strumento": "rivalutazione_istat"})]),
    ("Pignoramento notificato il 03/11/2026, voglio fare opposizione agli atti esecutivi: termine?", False,
     [("calcolo", {"strumento": "termini_processuali"})]),
    ("Interessi legali su 10.000 euro dal 01/01/2023 tenendo conto di due acconti versati", False,
     [("calcolo", {"strumento": "interessi_acconti"})]),
    ("Massime della Cassazione sull'art. 1226 c.c.", False, [("sentenze_per_norma", {"norma": "art. 1226 c.c."})]),
    ("Cosa dice la Cassazione sull'art. 2059 c.c.?", False, [("sentenze_per_norma", {"norma": "art. 2059 c.c."})]),
    ("In quale pagina di IUSENTRA vedo le ricevute dei depositi?", False, [("pagine_software", {})]),
    ("Atti pubblicati nella quarta serie speciale di ottobre 2026", False,
     [("gazzetta_ufficiale", {"serie": "S4", "dal": "01/10/2026", "al": "31/10/2026"})]),
    ("Testo dell'art. 40 c.p.a.", False, [("norma_testo_vigente", {"atto": "d.lgs. 104/2010", "articolo": "40"})]),
    ("Sentenza della Corte di giustizia tributaria di primo grado depositata il 10/06/2026: entro quando l'appello?", False,
     [("calcolo", {"strumento": "termini_processuali"})]),
    ("Multa per eccesso di velocità notificata il 16/12/2024: termine per il ricorso al prefetto?", False,
     [("calcolo", {"strumento": "termini_processuali", "campi": {"term_modello": "CDS_RICORSO_PREFETTO_60GG",
                                                                    "term_data_evento": "16/12/2024"}})]),
])
def test_categorie_della_terza_rimisura(domanda, fa, attesi):
    scelte = scegli(domanda, fascicolo_aperto=fa)
    assert [c.nome for c in scelte] == [n for n, _ in attesi]
    for c, (_, parametri) in zip(scelte, attesi, strict=True):
        assert all(c.parametri.get(k) == v for k, v in parametri.items()), (c.parametri, parametri)


def test_le_parole_giuridiche_non_si_correggono():
    assert "prefetto" in normalizza_domanda("ricorso al prefetto")


@pytest.mark.parametrize("domanda,fa,attesi", [
    ("Il cliente ha pagato in ritardo una cartella di 2.400 euro scaduta il 30/06/2026: quanto deve con il ravvedimento operoso?",
     False, [("calcolo", {"strumento": "ravvedimento_operoso"})]),
    ("Calcolami il TFR del cliente Moretti, 26.000 euro annui dal 2014", False, [("calcolo", {"strumento": "tfr"})]),
    ("Il risarcimento per l'incidente del 2017 si è già prescritto?", False, [("calcolo", {"strumento": "prescrizione"})]),
    ("Cosa è cambiato con la riforma della mediazione civile?", False, [("aggiornamenti_normativi", {})]),
    ("Il contributo unificato di questa causa risulta pagato?", True, [("economia_conto", {"voce": "contributo_unificato"})]),
    ("Giurisprudenza del Consiglio di Stato sull'art. 21-octies l. 241/1990. Entro quando posso impugnare il diniego del 05/11/2026?",
     False, [("sentenze_per_norma", {"norma": "art. 21-octies l. 241/1990"}), ("calcolo", {"strumento": "termini_processuali"})]),
    ("Bollo e contributo per un appello su 70.000 euro?", False, [("calcolo", {"strumento": "contributo_unificato"})]),
    ("Per quanto tempo può restare in carcere un indagato per rapina in attesa del processo?", False,
     [("calcolo", {"strumento": "custodia_durata"})]),
    ("Patrimonio di 250.000 euro, restano la moglie e due fratelli del defunto: a chi va cosa?", False,
     [("calcolo", {"strumento": "successione_legittima"})]),
    ("Quali allegati servono secondo il modello di ricorso per decreto ingiuntivo?", False, [("norme_modello", {})]),
    ("Mi fai la scheda pratica dello sfratto per morosità?", False, [("procedura_guidata", {})]),
    ("Controlla la coerenza della pratica Gualtieri", False, [("fascicolo_catena", {"fascicolo": "Gualtieri"})]),
    ("Cerca nel fascicolo Pedrazzini il contratto di appalto", False, [("documenti_fascicolo", {"fascicolo": "Pedrazzini"})]),
    ("In che fase è la causa Vercellotti?", False, [("fascicolo_lettura", {"fascicolo": "Vercellotti", "parte": "fase"})]),
    ("Avevamo una pratica con un certo Gianfranco, una lite su un muro di confine", False, [("ricerca_studio", {})]),
    ("Cosa ho da fare oggi?", False, [("scadenziario", {}), ("agenda_udienze", {})]),
    ("Dov'è la sezione delle PEC nel programma?", False, [("pagine_software", {})]),
    ("Messaggio INPS n. 2500 del 10 luglio 2025", False, [("prassi_ade_inps", {"ente": "inps", "numero": 2500, "anno": 2025})]),
    ("Il deposito telematico della memoria sul processo civile telematico è stato scartato", False,
     [("deposito_telematico", {"canale": "pct", "controllo": "errore"})]),
])
def test_categorie_della_quarta_rimisura(domanda, fa, attesi):
    scelte = scegli(domanda, fascicolo_aperto=fa)
    assert [c.nome for c in scelte] == [n for n, _ in attesi]
    for c, (_, parametri) in zip(scelte, attesi, strict=True):
        assert all(c.parametri.get(k) == v for k, v in parametri.items()), (c.parametri, parametri)


@pytest.mark.parametrize("domanda,fa,attesi", [
    ("Il cliente ha pagato la cartella con 20 giorni di ritardo, quanto deve in più?", False,
     [("calcolo", {"strumento": "ravvedimento_operoso"})]),
    ("La rata della rottamazione l'abbiamo pagata tardi: c'è un modo per ridurre la sanzione?", False,
     [("calcolo", {"strumento": "ravvedimento_operoso"})]),
    ("Per il cliente Gatti calcola la buonuscita", False, [("calcolo", {"strumento": "tfr"})]),
    ("Il nostro assistito chiede quanto gli verrà liquidato a fine rapporto dopo 9 anni", False, [("calcolo", {"strumento": "tfr"})]),
    ("Quanto abbiamo pagato di contributo unificato in questo fascicolo?", True, [("economia_conto", {"voce": "contributo_unificato"})]),
    ("Il contributo unificato di questa causa è già stato pagato?", True, [("economia_conto", {"voce": "contributo_unificato"})]),
    ("Quanto si paga di contributo unificato per un ricorso di 8.000 euro?", False, [("calcolo", {"strumento": "contributo_unificato"})]),
    ("Avviso di accertamento IVA notificato il 02/10/2026", False, [("calcolo", {"strumento": "termini_processuali"})]),
    ("Eredità di 420.000 euro, due figli e il coniuge superstite", False, [("calcolo", {"strumento": "successione_legittima"})]),
    ("È in carcere dal 15/08/2026 per estorsione, ancora in fase di indagini", False,
     [("calcolo", {"strumento": "custodia_durata"}), ("calcolo", {"strumento": "custodia_cautelare"})]),
    ("Controlla che scadenze e udienze della pratica Bonamici coincidano", False, [("fascicolo_catena", {"fascicolo": "Bonamici"})]),
    ("Mi serve la sentenza di primo grado della causa Scardovelli", False, [("documenti_fascicolo", {"fascicolo": "Scardovelli"})]),
    ("Com'è andato l'esito della cancelleria sul deposito di ieri?", False, [("notifiche_ricevute", {"tipo": "ricevute_deposito"})]),
    ("Novità di prassi dell'Agenzia delle Entrate sulla rottamazione", False, [("prassi_ade_inps", {"ente": "agenzia_entrate"})]),
    ("Ultime sentenze della Cassazione sul danno da vacanza rovinata", False, [("giurisprudenza_cassazione_consulta", {})]),
    ("Come si procede per l'accertamento tecnico preventivo ai fini della composizione della lite?", False,
     [("procedura_guidata", {})]),
    ("Qual è la regola del codice civile sulla responsabilità dei genitori per i danni dei figli minori?", False,
     [("norma_per_argomento", {})]),
    ("Prima apri il fascicolo Damiani, poi verifica le ricevute del deposito e infine calcola il termine per la replica", False,
     [("fascicolo_quadro", {"fascicolo": "Damiani"}), ("notifiche_ricevute", {}), ("calcolo", {"strumento": "termini_processuali"})]),
    ("In quali pratiche abbiamo già trattato assegno divorzile?", False, [("ricerca_studio", {})]),
])
def test_categorie_della_quinta_rimisura(domanda, fa, attesi):
    scelte = scegli(domanda, fascicolo_aperto=fa)
    assert [c.nome for c in scelte] == [n for n, _ in attesi]
    for c, (_, parametri) in zip(scelte, attesi, strict=True):
        assert all(c.parametri.get(k) == v for k, v in parametri.items()), (c.parametri, parametri)


@pytest.mark.parametrize("domanda,fa,attesi", [
    # TFR per conto del cliente con i verbi del ricevere: mai l'anagrafica
    ("Il cliente vuole sapere quanto prende di TFR dopo 12 anni da magazziniere a 1.800 euro al mese", False,
     [("calcolo", {"strumento": "tfr"})]),
    ("Quanto riceve di liquidazione la signora Ferrabosco che lascia il lavoro dopo 7 anni?", False, [("calcolo", {"strumento": "tfr"})]),
    ("Il mio assistito si è dimesso: quanto gli danno di trattamento di fine rapporto?", False, [("calcolo", {"strumento": "tfr"})]),
    ("Quanto porta a casa di liquidazione un operaio dopo vent'anni di lavoro?", False, [("calcolo", {"strumento": "tfr"})]),
    ("Lavoratrice part-time da 8 anni, 1.100 euro al mese: a quanto ammonta la sua liquidazione?", False, [("calcolo", {"strumento": "tfr"})]),
    ("Ho saltato la scadenza dell'F24 del 16 settembre, quanto mi costa mettermi in regola?", False,
     [("calcolo", {"strumento": "ravvedimento_operoso"})]),
    ("Il cliente vuole sapere quanto paga in più se versa adesso l'IMU scaduta a giugno", False,
     [("calcolo", {"strumento": "ravvedimento_operoso"})]),
    # calcoli con soli dati
    ("Ricorso contro l'avviso di accertamento IRPEF ricevuto il 14/10/2026", False, [("calcolo", {"strumento": "termini_processuali"})]),
    ("Due fratelli e una sorella, il padre vedovo è morto lasciando 90.000 euro", False, [("calcolo", {"strumento": "successione_legittima"})]),
    ("Un credito di 9.000 euro scaduto nel 2016 si può ancora chiedere?", False, [("calcolo", {"strumento": "prescrizione"})]),
    ("Risarcimento per un tamponamento del 2021: siamo ancora in tempo?", False, [("calcolo", {"strumento": "prescrizione"})]),
    ("Lavoratore con 6 anni di anzianità licenziato senza giusta causa da un'azienda con 40 dipendenti, retribuzione 2.100 euro", False,
     [("calcolo", {"strumento": "indennita_licenziamento"})]),
    # fascicolo: coerenza e documenti
    ("Le date delle udienze della causa Montecalvi corrispondono a quelle dello scadenziario?", False,
     [("fascicolo_catena", {"fascicolo": "Montecalvi"})]),
    ("Verifica se nel fascicolo Sbardellati ci sono incongruenze fra termini e atti", False, [("fascicolo_catena", {"fascicolo": "Sbardellati"})]),
    ("Dove si trova la procura alle liti della pratica Borsellini?", False, [("documenti_fascicolo", {"fascicolo": "Borsellini"})]),
    ("C'è la CTU nella causa Lanzavecchia?", False, [("documenti_fascicolo", {"fascicolo": "Lanzavecchia"})]),
    # esito del deposito: ricevute; errore: controllo del deposito
    ("La cancelleria ha accettato la memoria depositata venerdì?", False, [("notifiche_ricevute", {"tipo": "ricevute_deposito"})]),
    ("È arrivata la quarta PEC del deposito in questa causa?", True, [("notifiche_ricevute", {"tipo": "ricevute_deposito"})]),
    ("Il deposito è stato scartato con errore fatale, cosa significa?", False, [("deposito_telematico", {"controllo": "errore"})]),
    # sequenze e filtri
    ("Apri la pratica Cavalcanti e poi dimmi le prossime udienze", False,
     [("fascicolo_quadro", {"fascicolo": "Cavalcanti"}), ("agenda_udienze", {"fascicolo": "Cavalcanti"})]),
    ("Controlla le ricevute del deposito e dopo aggiorna lo scadenziario della causa", True, [("notifiche_ricevute", {}), ("scadenziario", {})]),
    ("Trova il modello di comparsa di risposta e poi le norme che il modello richiama", False, [("modelli_atto", {}), ("norme_modello", {})]),
    ("Termini ancora aperti per tutte le pratiche del cliente Zanardelli", False,
     [("scadenziario", {"cliente": "Zanardelli", "stato": "aperte"})]),
    ("Udienze di dicembre della pratica Castelnuovo", False, [("agenda_udienze", {"fascicolo": "Castelnuovo", "tipo": "udienze"})]),
    ("PEC ordinarie, non certificate, arrivate dal cliente Mazzoleni", False, [("pec_comunicazioni", {"casella": "ordinaria"})]),
])
def test_categorie_della_sesta_rimisura(domanda, fa, attesi):
    scelte = scegli(domanda, fascicolo_aperto=fa)
    assert [c.nome for c in scelte] == [n for n, _ in attesi]
    for c, (_, parametri) in zip(scelte, attesi, strict=True):
        assert all(c.parametri.get(k) == v for k, v in parametri.items()), (c.parametri, parametri)


@pytest.mark.parametrize("domanda,fa,attesi", [
    # termini aperti di una pratica: lo scadenziario filtrato, poi la catena (termini letti negli atti ma non registrati)
    ("Termini aperti nel fascicolo Gherardeschi", False,
     [("scadenziario", {"fascicolo": "Gherardeschi", "stato": "aperte"}), ("fascicolo_catena", {"fascicolo": "Gherardeschi"})]),
    ("Cosa scade in questa causa?", True, [("fascicolo_quadro", {})]),
    # custodia: la persona appena fermata; la durata chiesta per una persona detenuta, poi la misura
    ("Mio figlio è stato arrestato ieri per furto, cosa succede adesso?", False, [("calcolo", {"strumento": "custodia_cautelare"})]),
    ("Il mio cliente è in carcere da agosto per tentato omicidio, quanto ci può restare prima del processo?", False,
     [("calcolo", {"strumento": "custodia_durata"}), ("calcolo", {"strumento": "custodia_cautelare"})]),
    # sequenze
    ("Dimmi cosa prevede l'art. 1453 c.c. e poi cerca le sentenze della Cassazione che lo applicano", False,
     [("norma_testo_vigente", {}), ("sentenze_per_norma", {"norma": "art. 1453 c.c."})]),
    ("Trovami le norme sul sequestro conservativo e la relativa giurisprudenza", False,
     [("norma_per_argomento", {}), ("giurisprudenza_cassazione_consulta", {"cerca": "sequestro conservativo"})]),
    ("Mi servono il modello di atto di precetto e i passaggi della procedura di pignoramento presso terzi", False,
     [("modelli_atto", {}), ("procedura_guidata", {})]),
    ("Calcola gli interessi su 7.000 euro dal 10/01/2024, poi la rivalutazione ISTAT della stessa somma", False,
     [("calcolo", {"strumento": "interessi"}), ("calcolo", {"strumento": "rivalutazione_istat"})]),
    ("Leggi il fascicolo Albertazzi, quindi controlla che i termini siano tutti nello scadenziario", False,
     [("fascicolo_lettura", {"fascicolo": "Albertazzi"}), ("fascicolo_catena", {"fascicolo": "Albertazzi"})]),
    ("Leggimi l'art. 1218 c.c. e dimmi come lo interpreta la Cassazione", False,
     [("norma_testo_vigente", {}), ("sentenze_per_norma", {"norma": "art. 1218 c.c."})]),
    ("Fammi il quadro della causa Sansoni e calcola quanto manca alla prossima udienza", False,
     [("fascicolo_quadro", {"fascicolo": "Sansoni"}), ("calcolo", {"strumento": "conta_giorni"})]),
    ("Verifica il deposito della comparsa nel fascicolo Ruggerini e poi controlla le ricevute", False,
     [("deposito_telematico", {}), ("notifiche_ricevute", {"tipo": "ricevute_deposito"})]),
    ("Ultime sentenze della Cassazione sul mobbing e poi le norme che lo disciplinano", False,
     [("giurisprudenza_cassazione_consulta", {}), ("norma_per_argomento", {})]),
    ("Calcola il contributo unificato per un appello da 30.000 euro e i compensi secondo i parametri", False,
     [("calcolo", {"strumento": "contributo_unificato"}), ("calcolo", {"strumento": "onorari_forensi"})]),
    # siti ufficiali e novità di una fonte
    ("Trova sul portale della giustizia tributaria le istruzioni per il deposito", False, [("web_ufficiale", {})]),
    ("Novità INPS di questo mese sulla NASpI", False, [("prassi_ade_inps", {"ente": "inps"})]),
    ("Ultimi provvedimenti dell'Agenzia delle Entrate sul concordato preventivo biennale", False,
     [("prassi_ade_inps", {"ente": "agenzia_entrate"})]),
    # norma descritta con una perifrasi
    ("La norma secondo cui chi cagiona un danno ingiusto deve risarcirlo", False, [("norma_per_argomento", {})]),
    ("C'è un articolo che vieta il patto di non concorrenza oltre i cinque anni?", False, [("norma_per_argomento", {})]),
    # calcoli con soli dati
    ("Contributo tributario per impugnare una cartella da 3.500 euro", False, [("calcolo", {"strumento": "contributo_unificato"})]),
    ("Eredità: conto corrente da 45.000 euro e un appartamento da 200.000, eredi il marito e una figlia", False,
     [("calcolo", {"strumento": "successione_legittima"})]),
    ("Sentenza penale di condanna letta in udienza il 03/11/2026 con motivazione riservata a 90 giorni", False,
     [("calcolo", {"strumento": "termini_penali"})]),
    # filtri opzionali
    ("Ricevute dei depositi di questa pratica dal 01/11/2026", True, [("notifiche_ricevute", {"tipo": "ricevute_deposito", "dal": "01/11/2026"})]),
    ("Mail ordinarie dell'avvocato di controparte della causa Bellincioni", False, [("pec_comunicazioni", {"casella": "ordinaria"})]),
])
def test_categorie_della_settima_rimisura(domanda, fa, attesi):
    scelte = scegli(domanda, fascicolo_aperto=fa)
    assert [c.nome for c in scelte] == [n for n, _ in attesi]
    for c, (_, parametri) in zip(scelte, attesi, strict=True):
        assert all(c.parametri.get(k) == v for k, v in parametri.items()), (c.parametri, parametri)


@pytest.mark.parametrize("domanda,fa,attesi", [
    # termini da un evento del processo: si calcolano, non si leggono dati dello studio
    ("Siamo convenuti, udienza fissata al 15/04/2027: ultimo giorno per la comparsa di risposta?", False,
     [("calcolo", {"strumento": "termini_processuali", "campi": {"term_modello": "CIV_COSTITUZIONE_CONVENUTO_166"}})]),
    ("Il verbale dell'assemblea condominiale è arrivato al cliente il 02/11/2026, lui era assente", False,
     [("calcolo", {"strumento": "termini_processuali"})]),
    ("Ordinanza cautelare comunicata il 12/11/2026: termine per il reclamo?", False, [("calcolo", {"strumento": "termini_processuali"})]),
    ("Provvedimento di aggiudicazione definitiva ricevuto via PEC il 03/11/2026", False, [("calcolo", {"strumento": "termini_processuali"})]),
    ("Cassazione contro la sentenza d'appello del fascicolo Corradini, notificata il 01/11/2026", False,
     [("fascicolo_quadro", {"fascicolo": "Corradini"}), ("calcolo", {"strumento": "impugnazioni"})]),
    ("Notifica a mezzo posta ricevuta dal destinatario il 06/11/2026: da quando decorrono i termini?", False,
     [("calcolo", {"strumento": "perfezionamento_notifica"})]),
    # motivi nuovi in appello penale: termini penali, non impugnazioni civili
    ("Ultimo giorno per i motivi nuovi ex art. 585 c.p.p., udienza il 05/03/2027", False, [("calcolo", {"strumento": "termini_penali"})]),
    # contributo già versato: la contabilità del fascicolo
    ("CU già pagato per l'appello?", True, [("economia_conto", {"voce": "contributo_unificato"})]),
    ("Il cliente ha già pagato il contributo unificato di 759 euro del decreto ingiuntivo?", True,
     [("economia_conto", {"voce": "contributo_unificato"})]),
    # il cliente chiede della sua causa o della sua pena: il quadro della pratica, non l'anagrafica
    ("Il cliente Ravagnani chiede quanta pena gli resta da scontare", False, [("fascicolo_quadro", {"fascicolo": "Ravagnani"})]),
    ("Il cliente Moschetti vuole sapere se ha vinto la causa", False, [("fascicolo_quadro", {"fascicolo": "Moschetti"})]),
    # prossimi passi di una pratica nominata: il quadro, non la procedura guidata
    ("Prossimi passi della pratica Stellacci", False, [("fascicolo_quadro", {"fascicolo": "Stellacci", "sezione": "prossimi_passi"})]),
    ("Pratica Lombrici: prossime mosse?", False, [("fascicolo_quadro", {"fascicolo": "Lombrici", "sezione": "prossimi_passi"})]),
])
def test_classi_pericolose_del_banco_nuovo(domanda, fa, attesi):
    scelte = scegli(domanda, fascicolo_aperto=fa)
    assert [c.nome for c in scelte] == [n for n, _ in attesi]
    for c, (_, parametri) in zip(scelte, attesi, strict=True):
        for k, v in parametri.items():
            if k == "campi":
                assert all(c.parametri.get("campi", {}).get(a) == b for a, b in v.items()), c.parametri
            else:
                assert c.parametri.get(k) == v, (c.parametri, parametri)
