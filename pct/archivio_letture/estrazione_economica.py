"""Il motore documenti conserva anche il controllo economico, con la fonte."""
from __future__ import annotations
import json
from typing import Any
from pct.registro_letture.fatti_repository import Fatto

def estrai_controllo_economico(testo: str, *, origine: str, metadata: dict[str, Any]) -> list[Fatto]:
    fascicolo = metadata.get("fascicolo")
    tipo = str(metadata.get("tipo_documento") or "").upper().split(".")[-1]
    if fascicolo is None or tipo not in {"SENTENZA", "ORDINANZA", "DECRETO", "VERBALE"}:
        return []
    from pct.sentenza_economic_audit import build_audit
    audit = build_audit(
        fascicolo=fascicolo, testo=testo, fonte="ARCHIVIO_LETTURE",
        documento_id=str(metadata.get("documento_id") or ""),
        document_hash_sha256=str(metadata.get("document_hash_sha256") or ""),
        valore_causa=float(getattr(fascicolo, "valore_causa", 0) or 0),
        cu_tiers=metadata.get("cu_tiers"),
    )
    # Una sentenza istruttoria o un precedente giurisprudenziale è conoscenza,
    # non una fonte economica del fascicolo: richiede match pieno RG + cliente.
    if not audit.match.safe_to_attach:
        return []
    return [Fatto(categoria="evento", campo="controllo_economico",
        valore="analizzato", etichetta="Controllo economico del provvedimento",
        origine=origine, verifica="verificata" if origine == "nativo" else "plausibile",
        contesto="Esito automatico conservato con il documento; le scelte economiche restano da confermare.",
        prove=[{"codice":"audit_economico", "esito":"ok",
                "dettaglio":json.dumps(audit.to_dict(), ensure_ascii=False)}])]
