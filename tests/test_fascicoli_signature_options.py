from web.services.fascicoli_signature_options import nota_con_firma_visibile


def test_nota_con_firma_visibile_sostituisce_suffisso_precedente():
    nota = "Versione firmata. Posizione firma visibile: In basso a destra"

    aggiornata = nota_con_firma_visibile(
        nota,
        "laterale",
        place="Roma",
        datetime_mode="solo_data",
    )

    assert aggiornata.count("Posizione firma visibile:") == 1
    assert "Laterale verticale" in aggiornata
    assert "Luogo firma: Roma" in aggiornata
    assert "Data/ora firma visibile: Solo data" in aggiornata


def test_nota_con_firma_visibile_non_taglia_note_multiriga():
    nota = "Prima riga\nPosizione firma visibile: testo della nota originaria"

    aggiornata = nota_con_firma_visibile(nota, "basso_sinistra")

    assert "testo della nota originaria" in aggiornata
    assert aggiornata.count("Posizione firma visibile:") == 2
