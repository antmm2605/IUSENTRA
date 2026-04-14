from web.services.assistente_studio_context import _archivio_sentenze_lines


class _DummyGiurisprudenza:
    def statistiche(self):
        return {
            "totale_sentenze": 14,
            "fonti_attive": 5,
            "corpus_sentenze": 7,
        }

    def cerca(self, q: str = ""):
        return [
            {
                "id": "json-1",
                "titolo": "Cassazione su responsabilita medica",
                "area": "Civile",
                "branca": "Responsabilita civile",
                "massima": "Massima archivio locale.",
                "stato_verifica_fonte": "parzialmente_verificata",
                "url_pagina_ufficiale": "https://www.cortedicassazione.it/archivio-locale",
                "url_pdf_ufficiale": "",
                "pdf_ufficiale_presente": False,
                "organo_giudicante": "Corte di Cassazione",
                "numero_provvedimento": "321/2026",
                "anno": "2026",
            }
        ]

    def cerca_corpus_professionale(self, **kwargs):
        return [
            {
                "id": 101,
                "titolo": "Cassazione su consenso informato",
                "organo_giudicante": "Corte di Cassazione",
                "sezione": "Sez. III",
                "numero_sentenza": "1234",
                "anno_sentenza": 2026,
                "stato_verifica": "verificata",
                "url_pagina_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026",
                "url_pdf_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026.pdf",
                "principio_sintetico": "Il consenso informato va provato in modo specifico.",
                "massima_ufficiale": "Massima ufficiale.",
                "abstract": "Abstract strutturato.",
                "pdf_ufficiale_presente": 1,
                "ecli": "ECLI:IT:CASS:2026:1234",
            }
        ]

    def scheda_corpus_professionale(self, sentenza_id):
        return {
            "id": int(sentenza_id),
            "titolo": "Cassazione su consenso informato",
            "organo_giudicante": "Corte di Cassazione",
            "sezione": "Sez. III",
            "numero_sentenza": "1234",
            "anno_sentenza": 2026,
            "stato_verifica": "verificata",
            "url_pagina_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026",
            "url_pdf_ufficiale": "https://www.cortedicassazione.it/sentenza-1234-2026.pdf",
            "principio_sintetico": "Il consenso informato va provato in modo specifico.",
            "massima_ufficiale": "Massima ufficiale.",
            "abstract": "Abstract strutturato.",
            "pdf_ufficiale_presente": 1,
            "ecli": "ECLI:IT:CASS:2026:1234",
        }

    def riferimento_professionale_verificato(self, sentenza_id):
        return True

    def pdf_professionale_disponibile(self, sentenza_id):
        return True


def test_archivio_sentenze_lines_integra_corpus_professionale(monkeypatch):
    monkeypatch.setattr(
        "web.services.assistente_studio_context.get_giurisprudenza",
        lambda: _DummyGiurisprudenza(),
    )

    lines, sources = _archivio_sentenze_lines("consenso informato")

    assert any("Corpus professionale: 7 schede strutturate." in line for line in lines)
    assert any("Corpus giurisprudenziale verificabile:" in line for line in lines)
    assert any(source["id"] == "corpus-sentenza:101" for source in sources)
    assert any(source.get("verified_reference") is True for source in sources if source["id"] == "corpus-sentenza:101")
    assert any(source.get("downloadable_pdf") is True for source in sources if source["id"] == "corpus-sentenza:101")
