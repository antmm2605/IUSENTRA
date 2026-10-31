"""V21: l'esito della firma si riusa finché il file non cambia; un file modificato si ricontrolla."""

from __future__ import annotations

import os

from web.services.firma_documento_cache import esito_firma, svuota


def test_stesso_file_non_si_rilegge_file_modificato_si(tmp_path):
    svuota()
    documento = tmp_path / "atto.pdf"
    documento.write_bytes(b"%PDF-1.4 uno")
    chiamate = []

    def calcola():
        chiamate.append(1)
        return {"signed": len(chiamate) > 1}

    assert esito_firma(str(documento), ("atto.pdf",), calcola) == {"signed": False}
    assert esito_firma(str(documento), ("atto.pdf",), calcola) == {"signed": False}
    assert len(chiamate) == 1
    documento.write_bytes(b"%PDF-1.4 due, firmato")
    stato = os.stat(documento)
    os.utime(documento, ns=(stato.st_atime_ns, stato.st_mtime_ns + 1_000_000))
    assert esito_firma(str(documento), ("atto.pdf",), calcola) == {"signed": True}
    assert len(chiamate) == 2
    assert esito_firma(str(tmp_path / "assente.pdf"), (), lambda: {"signed": False}) == {"signed": False}
