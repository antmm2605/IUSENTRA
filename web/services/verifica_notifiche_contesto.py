"""Validazione dei dati confermati nel pannello: proprietario e fonte documentale."""
from datetime import date


def repository():
    from pct.notifiche_verifica_repository import VerificaNotificheRepository
    from web.helpers import _studio_db
    from web.services.notification_presidia_runtime import _tenant_id
    return VerificaNotificheRepository(_studio_db("FASCICOLI_DB"), _tenant_id())


def valida(fascicolo, documento_id: str, payload: dict) -> dict:
    from pct.archivio_letture.verifiche_atti import impronta_documento
    documenti = {str(d.id): d for d in fascicolo.documenti}
    if documento_id not in documenti:
        raise ValueError("Atto non presente nel fascicolo.")
    fonte = str(payload.get("fonte_documento_id") or "")
    if fonte not in documenti:
        raise ValueError("Seleziona il documento del fascicolo che contiene i dati verificati.")
    if payload.get("dati_verificati") is not True:
        raise ValueError("Conferma di avere verificato i dati nel documento fonte.")
    atto_sha, fonte_sha = impronta_documento(documenti[documento_id]), impronta_documento(documenti[fonte])
    if not atto_sha or not fonte_sha:
        raise ValueError("L’impronta dell’atto o della fonte non è disponibile: completa l’acquisizione documentale prima di salvare la verifica.")
    dati = {"fonte_documento_id": fonte, "dati_verificati": True,
            "atto_sha256": atto_sha, "fonte_sha256": fonte_sha}
    for campo in ("notifica_estero", "sospensione_feriale", "atto_studio", "regime_corrente"):
        if not isinstance(payload.get(campo), bool):
            raise ValueError("Completa le condizioni del caso prima di salvare.")
        dati[campo] = payload[campo]
    for campo in ("udienza", "pronuncia_decreto", "pubblicazione", "conoscenza"):
        valore = str(payload.get(campo) or "")
        if valore:
            try:
                if date.fromisoformat(valore).isoformat() != valore:
                    raise ValueError()
            except ValueError:
                raise ValueError("Data non valida.") from None
        dati[campo] = valore
    return dati
