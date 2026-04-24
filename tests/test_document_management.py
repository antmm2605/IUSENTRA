from types import SimpleNamespace

from pct.document_management import build_document_management_summary, normalize_document_tags


class _FakeSearchResult:
    def __init__(self, *, id, titolo, snippet, url, meta):
        self.id = id
        self.titolo = titolo
        self.snippet = snippet
        self.url = url
        self.meta = meta


class _FakeIndice:
    def cerca(self, query, tipi=None, limit=12):
        return [
            _FakeSearchResult(
                id="fas-1:doc-1",
                titolo="Comparsa conclusionale",
                snippet="...conclusionale...",
                url="/fake/doc-1",
                meta={"id_fasc": "fas-1", "tipo_doc": "COMPARSA"},
            ),
            _FakeSearchResult(
                id="fas-2:doc-9",
                titolo="Documento altro fascicolo",
                snippet="...",
                url="/fake/doc-9",
                meta={"id_fasc": "fas-2", "tipo_doc": "ALLEGATO"},
            ),
        ]

    def get_ocr_cache(self, hash_sha256):
        return {"hash-doc-ocr": "Testo OCR cached"}.get(hash_sha256, "")


def test_normalize_document_tags_rimuove_duplicati():
    assert normalize_document_tags("comparsa, udienza; comparsa, prova") == [
        "comparsa",
        "udienza",
        "prova",
    ]


def test_document_management_summary_costruisce_tag_cloud_e_search_results():
    fascicolo = SimpleNamespace(
        id="fas-1",
        documenti=[
            SimpleNamespace(
                id="doc-1",
                nome="comparsa.pdf",
                tags=["comparsa", "udienza"],
                versioni=[{"v": 1}],
                firmato_digitalmente=True,
                ocr_estratto=True,
                hash_sha256="hash-doc-1",
                id_deposito_pct="dep-1",
                data_caricamento="2026-04-18T09:00:00",
            ),
            SimpleNamespace(
                id="doc-2",
                nome="allegato.pdf",
                tags=[],
                versioni=[],
                firmato_digitalmente=False,
                ocr_estratto=False,
                hash_sha256="hash-doc-2",
                id_deposito_pct="",
                data_caricamento="2026-04-17T09:00:00",
            ),
        ],
    )

    summary = build_document_management_summary(
        fascicolo,
        indice=_FakeIndice(),
        query="conclusionale",
    )

    assert summary["stats"]["totale"] == 2
    assert summary["stats"]["taggati"] == 1
    assert summary["stats"]["versioni"] == 1
    assert summary["stats"]["dal_portale"] == 1
    assert summary["tag_cloud"][0]["label"] == "comparsa"
    assert len(summary["search_results"]) == 1
    assert summary["search_results"][0]["id_doc"] == "doc-1"


def test_document_management_summary_conta_ocr_da_cache_anche_senza_flag():
    fascicolo = SimpleNamespace(
        id="fas-1",
        documenti=[
            SimpleNamespace(
                id="doc-ocr",
                nome="atto.pdf",
                tags=["atto"],
                versioni=[],
                firmato_digitalmente=False,
                ocr_estratto=False,
                hash_sha256="hash-doc-ocr",
                id_deposito_pct="dep-1",
                data_caricamento="2026-04-24T09:00:00",
            )
        ],
    )

    summary = build_document_management_summary(fascicolo, indice=_FakeIndice())

    assert summary["stats"]["ocr_ready"] == 1
    assert summary["next_action"] != "Completa l'indicizzazione OCR dei PDF piu' rilevanti."
