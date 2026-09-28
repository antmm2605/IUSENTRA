"""La firma di ciascun avvocato: canale, gestore e dispositivo scelti dal singolo professionista.

Nello stesso studio ogni avvocato può avere un prestatore diverso (Aruba, InfoCert, Namirial…)
o un dispositivo di un altro produttore: la firma digitale è personale (CAD art. 1 lett. s,
art. 24; Reg. eIDAS art. 26) e il certificato è intestato al titolare. Qui si salva solo
*come* firma l'avvocato; il profilo sostituisce, per quell'avvocato, i campi corrispondenti
della firma dello studio. Password, PIN e codici OTP non passano mai da qui.

Archivio: ``firme_avvocati.json`` accanto alla configurazione dello studio (quindi per tenant).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Campi della firma che l'avvocato sceglie per sé (nessun segreto, nessun percorso di file).
CAMPI_PROFILO = (
    "backend_preferito",
    "prestatore",
    "dispositivo_produttore",
    "remota_protocollo",
    "remota_endpoint",
    "remota_utente",
    "remota_dominio",
    "remota_credenziale",
    "remota_tipo_otp",
)
#: «studio» = usa la firma configurata per lo studio; gli altri sono i canali personali.
CANALI_PERSONALI = ("studio", "pkcs11", "remota")
NOME_ARCHIVIO = "firme_avvocati.json"

_BLOCCO = threading.Lock()
_VIETATI = ("password", "pin", "otp", "segreto", "secret", "token")


def _pulito(profilo: dict[str, Any]) -> dict[str, str]:
    return {campo: str(profilo.get(campo) or "").strip() for campo in CAMPI_PROFILO}


class ArchivioProfiliFirma:
    """Profili di firma per utente, in un file JSON scritto in modo atomico."""

    def __init__(self, percorso: str | Path):
        self.percorso = Path(percorso)

    @classmethod
    def accanto_a(cls, percorso_config: str | Path) -> "ArchivioProfiliFirma":
        return cls(Path(percorso_config).with_name(NOME_ARCHIVIO))

    def _leggi_tutto(self) -> dict[str, Any]:
        try:
            dati = json.loads(self.percorso.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"versione": 1, "profili": {}}
        profili = dati.get("profili") if isinstance(dati, dict) else None
        return {"versione": 1, "profili": profili if isinstance(profili, dict) else {}}

    def _scrivi_tutto(self, dati: dict[str, Any]) -> None:
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        fd, temporaneo = tempfile.mkstemp(prefix=".firme_avvocati.", dir=str(self.percorso.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as uscita:
                json.dump(dati, uscita, ensure_ascii=False, indent=2)
            os.replace(temporaneo, self.percorso)
        except BaseException:
            Path(temporaneo).unlink(missing_ok=True)
            raise

    def leggi(self, utente_id: str) -> dict[str, str] | None:
        utente_id = str(utente_id or "").strip()
        if not utente_id:
            return None
        voce = self._leggi_tutto()["profili"].get(utente_id)
        if not isinstance(voce, dict):
            return None
        profilo = _pulito(voce)
        profilo["aggiornato_il"] = str(voce.get("aggiornato_il") or "")
        return profilo

    def salva(self, utente_id: str, profilo: dict[str, Any]) -> dict[str, str]:
        utente_id = str(utente_id or "").strip()
        if not utente_id:
            raise ValueError("Utente mancante.")
        estranei = [chiave for chiave in profilo
                    if chiave not in CAMPI_PROFILO and any(v in str(chiave).lower() for v in _VIETATI)]
        if estranei:
            raise ValueError("Il profilo di firma non può contenere password, PIN o codici.")
        voce = _pulito(profilo)
        voce["aggiornato_il"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with _BLOCCO:
            dati = self._leggi_tutto()
            dati["profili"][utente_id] = voce
            self._scrivi_tutto(dati)
        return voce

    def rimuovi(self, utente_id: str) -> bool:
        utente_id = str(utente_id or "").strip()
        with _BLOCCO:
            dati = self._leggi_tutto()
            if dati["profili"].pop(utente_id, None) is None:
                return False
            self._scrivi_tutto(dati)
        return True


def firma_effettiva(firma_studio: Any, profilo: dict[str, Any] | None) -> Any:
    """La firma con cui firma l'avvocato: quella dello studio con le sue scelte personali sopra."""
    if not profilo or str(profilo.get("backend_preferito") or "") not in CANALI_PERSONALI[1:]:
        return firma_studio
    return replace(firma_studio, **_pulito(profilo))


__all__ = ["ArchivioProfiliFirma", "CAMPI_PROFILO", "CANALI_PERSONALI", "NOME_ARCHIVIO", "firma_effettiva"]
