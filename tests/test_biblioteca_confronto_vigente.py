"""La biblioteca confrontata con il testo vigente di Normattiva: grafia, apparato, sostanza, abrogazioni non ancora efficaci."""
from lex.normativa.biblioteca.confronto_vigente import classifica

VIGENTE_2 = ("Art. 2. (Oggetto della giurisdizione tributaria). 1. Appartengono alla giurisdizione tributaria tutte le "
             "controversie aventi ad oggetto i tributi di ogni genere e specie comunque denominati, compresi quelli "
             "regionali, provinciali e comunali e il contributo per il Servizio sanitario nazionale, le sovrimposte e le "
             "addizionali, le relative sanzioni nonche' gli interessi e ogni altro accessorio. Restano escluse dalla "
             "giurisdizione tributaria soltanto le controversie riguardanti gli atti della esecuzione forzata tributaria "
             "successivi alla notifica della cartella di pagamento.")


def test_note_redazionali_avvisi_e_intestazioni_non_sono_sostanza():
    vigente = "Art. 6 Dell'opposizione 1. Le controversie sono regolate dal rito del lavoro. Note all'art. 6: si riporta il testo."
    biblioteca = ("Avviso: l'articolo e' stato oggetto di dichiarazioni di illegittimita' costituzionale. "
                  "Articolo 6 Dell'opposizione 1. Le controversie sono regolate dal rito del lavoro. (12)")
    assert classifica(biblioteca, vigente)[0] == "solo_grafia"
    assert classifica("Art. 1. Testo  uguale.", "Art. 1. Testo uguale.")[0] == "uguale"


def test_lettera_in_piu_o_in_meno_e_sostanza():
    categoria, diverse = classifica("Art. 84. 1. Sono veicoli: a) autobus; b-ter) i veicoli con piu' di nove posti.",
                                    "Art. 84. 1. Sono veicoli: a) autobus.")
    assert categoria == "sostanza" and "nove posti" in diverse[0][1]


def test_abrogazione_non_ancora_efficace_si_riconosce():
    biblioteca = ("Art. 2. ((PROVVEDIMENTO ABROGATO DAL D.LGS. 14 NOVEMBRE 2024, N. 175, COME MODIFICATO DAL "
                  "D.L. 31 DICEMBRE 2025, N. 200))")
    assert classifica(biblioteca, VIGENTE_2)[0] == "abrogato_ma_vigente"
    # Abrogato in entrambi: nessuna differenza da segnalare come vigenza.
    assert classifica("Art. 16. ((ARTICOLO ABROGATO))", "Art. 16. ((ARTICOLO SOPPRESSO))")[0] != "abrogato_ma_vigente"


def test_la_consultazione_mostra_l_edizione_verificata_vigente_oggi(tmp_path):
    """Un'edizione datata con il giorno di una raccolta (09/10/2026) e con abrogazioni non ancora efficaci non prevale
    sul testo scaricato da Normattiva come vigente al 21/11/2026, anche se la sua ultima modifica è del 21/04/2026."""
    import sqlite3
    from lex.normativa.consultazione import ordine_edizione

    conn = sqlite3.connect(tmp_path / "b.sqlite")
    conn.execute("CREATE TABLE normative_documents (id INTEGER PRIMARY KEY, collection_name TEXT, redazione_id TEXT, vigenza TEXT)")
    conn.executemany("INSERT INTO normative_documents VALUES (?,?,?,?)", [
        (76, "Lex fonti: 546/1992", "2026-10-09", "EDIZIONE_ACQUISITA"),
        (856, "Lex fonti: 546/1992", "2026-04-21", "EDIZIONE_ACQUISITA"),
        (1900, "Lex fonti: 546/1992", "2026-04-21", "VIGENTE_AL:2026-11-21"),
        (10, "Lex fonti: 241/1990", "2026-10-09", "EDIZIONE_ACQUISITA"),
    ])
    scelta = dict(conn.execute(
        "SELECT d.collection_name, (SELECT x.id FROM normative_documents x WHERE x.collection_name=d.collection_name "
        "ORDER BY " + ordine_edizione("x") + " LIMIT 1) FROM normative_documents d GROUP BY d.collection_name").fetchall())
    assert scelta == {"Lex fonti: 546/1992": 1900, "Lex fonti: 241/1990": 10}
