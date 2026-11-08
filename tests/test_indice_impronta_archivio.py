"""Indice e catalogo registrano l'esito con l'impronta dell'inventario (documenti cifrati, 08/11/2026)."""

from types import SimpleNamespace

from pct.registro_letture import Oggetto
from web.services.document_intelligence_runtime import _oggetto_del_registro


def _fonte(sha="", oid="d1"):
    return SimpleNamespace(metadata={"documento_id": oid}, source_id=oid, filename="atto.pdf", sha256=sha, size_bytes=10)


def test_documento_cifrato_usa_impronta_archivio():
    noto = Oggetto(tipo="documento", oggetto_id="d1", nome="atto.pdf", sha256_archivio="ab" * 32, dimensione=10)
    oggetto = _oggetto_del_registro({"d1": noto}, _fonte())
    assert oggetto.impronta == noto.impronta and oggetto.impronta.startswith("archivio:")


def test_contenuto_cambiato_non_eredita_impronta():
    noto = Oggetto(tipo="documento", oggetto_id="d1", sha256="aa" * 32)
    oggetto = _oggetto_del_registro({"d1": noto}, _fonte(sha="bb" * 32))
    assert oggetto.impronta == "bb" * 32


def test_documento_fuori_inventario():
    assert _oggetto_del_registro({}, _fonte(sha="cc" * 32)).impronta == "cc" * 32
