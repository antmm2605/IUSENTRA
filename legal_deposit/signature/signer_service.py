from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SignatureResult:
    ok: bool
    signed_path: str = ""
    signature_format: str = ""
    verification_status: str = "not_verified"
    message: str = ""


class MockSignerAdapter:
    def sign(self, path: str, *, signature_format: str = "PADES") -> SignatureResult:
        source = Path(path)
        if not source.exists():
            return SignatureResult(False, message="File da firmare non trovato.")
        target = source.with_suffix(source.suffix + ".mock-signed")
        target.write_bytes(source.read_bytes())
        return SignatureResult(
            ok=True,
            signed_path=str(target),
            signature_format=signature_format,
            verification_status="valid_mock",
            message="Firma mock applicata e verificata.",
        )


class SignerService:
    def __init__(self, adapter=None) -> None:
        self.adapter = adapter or MockSignerAdapter()

    def sign(self, path: str, *, signature_format: str = "PADES") -> SignatureResult:
        return self.adapter.sign(path, signature_format=signature_format)
