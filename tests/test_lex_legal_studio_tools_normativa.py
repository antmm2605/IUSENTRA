from lex.tools import legal_studio_tools


class _NormativeManager:
    def snapshot(self):
        return {
            "tabelle": [
                {
                    "id": "interesse_legale",
                    "title": "Interessi legali",
                    "category": "tassi",
                    "description": "Saggi di interesse legale per anno e decorrenza.",
                    "sync_status": "sincronizzata",
                    "last_synced_at": "2026-06-06T09:00:00",
                    "sources": [
                        {
                            "code": "interesse_legale_2026",
                            "title": "Gazzetta Ufficiale - saggio interessi legali 2026",
                            "url": "https://www.gazzettaufficiale.it/atto/vediMenuHTML?atto.codiceRedazionale=25A06705",
                        }
                    ],
                }
            ]
        }

    def rows(self, table_id: str):
        assert table_id == "interesse_legale"
        return [
            {
                "label": "Interesse legale 2026",
                "start": "2026-01-01",
                "end": "2026-12-31",
                "rate": 1.6,
            }
        ]

    def catalogo_riferimenti_normativi(self):
        return [
            {
                "reference_code": "dm_55_parametri_compensi",
                "title": "D.M. 55/2014 - parametri compensi forensi",
                "article": "artt. 1-29",
                "description": "Parametri per compensi, fasi, preventivo e liquidazione.",
                "url": "https://www.normattiva.it/",
            }
        ]


def test_search_normativa_usa_db_normativa_operativo(monkeypatch):
    monkeypatch.setattr(legal_studio_tools, "_normative_manager", lambda: _NormativeManager())

    result = legal_studio_tools.search_normativa("interesse legale 2026", limit=5)

    assert result["ok"] is True
    assert result["fonte"] == "DB normativa IUSENTRA tenant-aware"
    table = next(item for item in result["risultati"] if item["tipo"] == "tabella_normativa")
    assert table["id"] == "interesse_legale"
    assert table["fonti"][0]["code"] == "interesse_legale_2026"
    assert table["righe_campione"][0]["label"] == "Interesse legale 2026"


def test_lookup_normativa_table_restituisce_riferimenti_strutturati(monkeypatch):
    monkeypatch.setattr(legal_studio_tools, "_normative_manager", lambda: _NormativeManager())

    result = legal_studio_tools.lookup_normativa_table("parametri compensi")

    assert result["ok"] is True
    reference = next(item for item in result["risultati"] if item["tipo"] == "riferimento_normativo")
    assert reference["id"] == "dm_55_parametri_compensi"
    assert "compensi" in reference["descrizione"]
