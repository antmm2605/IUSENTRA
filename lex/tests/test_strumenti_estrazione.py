"""Estrazione dei parametri della chiamata dalla domanda: solo ciò che la domanda dice."""
from __future__ import annotations

import pytest

from lex.strumenti import estrazione as ex
from lex.strumenti.mappa import mappa, valida_chiamata
from lex.strumenti.scelta import calcolatore, scegli


def test_date_e_importi():
    assert ex.date_it("dal 1/3/2024 al 31 dicembre 2025, non il 31/02/2025") == ["01/03/2024", "31/12/2025"]
    assert ex.importi("capitale di 12.000 euro e spese per € 1.500,50") == [12000.0, 1500.5]
    assert ex.percentuali("tasso del 14% o 3,5 per cento") == [14.0, 3.5]


@pytest.mark.parametrize("testo,atteso", [
    ("art. 163-bis c.p.c.", ("163-bis", "c.p.c.")),
    ("l'articolo 5 del d.lgs. 28/2010", ("5", "d.lgs. 28/2010")),
    ("art. 3 bis della legge 53/1994", ("3-bis", "l. 53/1994")),
    ("art. 473-bis.12 c.p.c.", ("473-bis.12", "c.p.c.")),
    ("articolo 41 della Costituzione", ("41", "cost.")),
    ("art 615 cpc", ("615", "c.p.c.")),
])
def test_articolo_e_atto(testo, atteso):
    assert ex.articolo_citato(testo) == atteso


def test_articolo_senza_atto_non_e_citato():
    assert ex.articolo_citato("l'art. 12 del contratto") is None
    assert ex.comma("il secondo comma dell'art. 2051 c.c.") == "2" and ex.comma("comma 3") == "3"


@pytest.mark.parametrize("testo,atteso", [
    ("Cass. civ. sez. III n. 9449/2016", {"organo": "cassazione", "numero": 9449, "anno": 2016}),
    ("Corte cost. n. 75/2019", {"organo": "consulta", "numero": 75, "anno": 2019}),
    ("C.d.S. n. 5678 del 2020", {"organo": "consiglio_di_stato", "numero": 5678, "anno": 2020}),
    ("TAR Lazio n. 3456/2019", {"organo": "tar", "numero": 3456, "anno": 2019}),
])
def test_estremi_pronuncia(testo, atteso):
    assert ex.estremi_pronuncia(testo) == atteso


def test_numero_di_ruolo_non_e_una_pronuncia():
    assert ex.estremi_pronuncia("ricorso al TAR nel fascicolo R.G. n. 1234/2025") is None
    assert ex.numero_di_ruolo("fascicolo R.G. n. 1234/2025") == "RG 1234/2025"


def test_fonti_pubbliche():
    assert ex.ente_prassi("circolare dell'INPS") == "inps"
    assert ex.ente_prassi("risoluzione dell'Agenzia delle Entrate") == "agenzia_entrate"
    assert ex.ente_prassi("PEC dell'Agenzia delle Entrate Riscossione") == ""
    assert ex.serie_gazzetta("prima serie speciale (Corte costituzionale)") == "S1"
    assert ex.tipo_atto_gazzetta("decreti legislativi pubblicati") == "decreto legislativo"
    assert ex.sede_tar("TAR Lombardia, sez. II") == "Lombardia"


@pytest.mark.parametrize("testo,atteso", [
    ("Quale norma disciplina la caparra confirmatoria?", "caparra confirmatoria"),
    ("Novità normative recenti in materia di mediazione obbligatoria?", "mediazione obbligatoria"),
    ("In quali pratiche abbiamo già trattato onere della prova?", "onere della prova"),
    ("Orientamento della Cassazione su particolare tenuità del fatto", "particolare tenuita del fatto"),
    ("Giurisprudenza amministrativa sulle concessioni balneari", "concessioni balneari"),
    ("Quale norma disciplina inadempimento?", "inadempimento"),
])
def test_argomento(testo, atteso):
    assert ex.argomento(testo) == atteso


def test_campi_dei_calcolatori():
    calc = mappa()["calcolatori"]
    assert ex.campi_calcolatore("interessi legali su 8.500 euro dal 01/02/2023 al 01/02/2025", calc["interessi"]["campi"]) == {
        "int_tipo": "legali", "int_capitale": 8500.0, "int_data_inizio": "01/02/2023", "int_data_fine": "01/02/2025"}
    riv = ex.campi_calcolatore("rivalutazione ISTAT di 12.000 euro dal 10/2015", calc["rivalutazione_istat"]["campi"])
    assert riv["riv_importo"] == 12000.0 and (riv["riv_mese_base"], riv["riv_anno_base"]) == (10, 2015)


@pytest.mark.parametrize("domanda,atteso", [
    ("Entro quando devo fare appello se la sentenza mi è stata notificata il 10/06/2026?", "impugnazioni"),
    ("Quanti giorni passano tra il 03/01/2026 e il 20/03/2026?", "conta_giorni"),
    ("Il tasso del 14% sul credito revolving è usurario?", "usura"),
    ("Calcola la prescrizione di un credito da fatto illecito dal 03/05/2021", "prescrizione"),
    ("Quanto abbiamo fatturato su questo incarico?", ""),
    ("Cosa prevede l'art. 1284 c.c.?", ""),
])
def test_calcolatore(domanda, atteso):
    assert calcolatore(domanda) == atteso


@pytest.mark.parametrize("domanda,fa,strumenti", [
    ("Testo dell'art. 2043 c.c. e giurisprudenza collegata", False, ["norma_testo_vigente", "sentenze_per_norma"]),
    ("Sul sito del Ministero del lavoro trovami il modello di dimissioni telematiche", False, ["web_ufficiale"]),
    ("Risoluzioni dell'Agenzia delle Entrate sul credito d'imposta per ricerca e sviluppo", False, ["prassi_ade_inps"]),
    ("Mostrami le PEC dell'Agenzia delle Entrate Riscossione", False, ["pec_comunicazioni"]),
    ("Trovami il modello di querela e dimmi su quali norme si fonda", False, ["modelli_atto", "norme_modello"]),
    ("Dove si trova nel software l'archivio della Gazzetta?", False, ["pagine_software"]),
    ("Risulta accettato dalla cancelleria l'ultimo deposito?", True, ["notifiche_ricevute"]),
    ("Buonasera Lex", False, []),
])
def test_scelta_per_categoria(domanda, fa, strumenti):
    scelte = scegli(domanda, fascicolo_aperto=fa)
    assert [c.nome for c in scelte] == strumenti
    assert all(valida_chiamata(c.nome, c.to_dict()["parametri"]) == [] for c in scelte)
