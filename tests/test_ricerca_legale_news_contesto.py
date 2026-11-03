"""LEX-21 (riverifica 03/11/2026): le news già pubblicate non mostrano conferme estranee troncate."""

from web.services.react_ricerca_legale_dettagli import scheda_news


def test_news_pubblicata_senza_frammenti_estranei():
    testo = (
        "Sintesi.\n\nContesto ufficiale verificato:\n"
        "- Gazzetta Ufficiale: erminate in unità di valuta estera contro 1 euro (valuta base).\n"
        "- ANAC - atti e documenti: la ricerca Anno: 2026 Delibera n. 171 del 6 maggio 2026"
    )
    item = scheda_news({"title": "Delibera n. 171 del 6 maggio 2026", "content": testo})[0]["item"]
    assert "erminate in unità" not in item["content"]
    assert "Delibera n. 171 del 6 maggio 2026" in item["content"]


def test_news_senza_conferme_pertinenti_perde_l_intestazione():
    testo = "Sintesi.\n\nContesto ufficiale verificato:\n- Gazzetta Ufficiale: ffari esteri e della cooperazione."
    item = scheda_news({"title": "Delibera n. 171 del 6 maggio 2026", "content": testo})[0]["item"]
    assert item["content"] == "Sintesi."
