"""Verifica CMS e restituisce solo il contenuto coperto dalla firma PEC."""

from pathlib import Path
import subprocess

from pct.sdi_pec_trust import PecTrustError


def estrai_contenuto_cms(executable: str, message: Path, content: Path, signer: Path) -> None:
    """Controlla l'integrità. Il chiamante deve verificare catena e revoche."""
    result = subprocess.run(
        [executable, "cms", "-verify", "-verify_retcode", "-inform", "SMIME",
         "-in", str(message), "-noverify", "-out", str(content), "-signer", str(signer)],
        capture_output=True, timeout=12, check=False,
    )
    if result.returncode:
        raise PecTrustError("envelope_signature_invalid", "La firma della busta PEC non supera la verifica di integrità.")
