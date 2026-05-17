from __future__ import annotations

from pathlib import Path

from lex.normativa.normattiva_client import DOWNLOAD_COLLECTION_URL, NormattivaClient


class _FakeResponse:
    def __init__(self, *, json_data=None, content: bytes = b"PK\x03\x04test", url: str = "https://download.example/file.zip"):
        self._json_data = json_data
        self.content = content
        self.headers = {"content-type": "application/zip"}
        self.url = url
        self.request = type("Req", (), {"url": url})()

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._json_data

    def iter_content(self, chunk_size: int):
        yield self.content


class _FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "collection-predefinite" in url:
            return _FakeResponse(json_data=[{"nome": "Codici"}, {"nome": "Testi Unici"}])
        params = kwargs.get("params") or {}
        return _FakeResponse(url=f"{url}?nome={params.get('nome')}&formatoRichiesta={params.get('formatoRichiesta')}")


def test_normattiva_list_collections_from_api_shape():
    client = NormattivaClient(session=_FakeSession())

    assert client.list_collection_names() == ["Codici", "Testi Unici"]


def test_normattiva_download_builds_expected_params_and_zip(tmp_path: Path):
    session = _FakeSession()
    client = NormattivaClient(session=session, sleep_seconds=0)

    result = client.download_collection("Codici", output_dir=tmp_path, vigenza="ORIGINALE")

    url, kwargs = session.calls[-1]
    assert url == DOWNLOAD_COLLECTION_URL
    assert kwargs["params"] == {"nome": "Codici", "formato": "XML", "formatoRichiesta": "O"}
    assert Path(result.output_path).exists()
    assert Path(result.output_path).read_bytes().startswith(b"PK")


def test_normattiva_download_replace_existing_non_accumula_zip(tmp_path: Path):
    old = tmp_path / "Codici_XML_ORIGINALE_2026-05-16.zip"
    old.write_bytes(b"PK\x03\x04old")
    session = _FakeSession()
    client = NormattivaClient(session=session, sleep_seconds=0)

    result = client.download_collection(
        "Codici",
        output_dir=tmp_path,
        vigenza="ORIGINALE",
        replace_existing=True,
    )

    assert not old.exists()
    assert Path(result.output_path).exists()
    assert len(list(tmp_path.glob("Codici_XML_ORIGINALE_*.zip"))) == 1
