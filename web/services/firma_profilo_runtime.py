"""«La mia firma»: l'avvocato sceglie il proprio canale, gestore e dispositivo in Impostazioni.

Ogni utente con permesso di scrittura sui fascicoli salva il proprio profilo (``pct.firma_profili``);
chi firma usa la firma dello studio con le proprie scelte sopra (``firma_utente_corrente``).
La prova di collegamento chiede al prestatore il certificato con la password digitata al momento,
che non viene salvata.
"""

from __future__ import annotations

from typing import Any

from flask import g

from pct import firma_catalogo
from pct.firma_profili import CANALI_PERSONALI, ArchivioProfiliFirma, firma_effettiva

PERMESSI_FIRMA = ("fascicoli.scrivi", "admin.configura")


def _gestore_config():
    from web.blueprints.impostazioni import _get_gestore

    return _get_gestore()


def _utente() -> Any:
    return g.get("utente_corrente")


def _puo_firmare(utente: Any) -> bool:
    controllo = getattr(utente, "ha_permesso", None)
    return bool(utente and callable(controllo) and any(controllo(p) for p in PERMESSI_FIRMA))


def _archivio(gestore: Any) -> ArchivioProfiliFirma:
    return ArchivioProfiliFirma.accanto_a(gestore.percorso)


def firma_utente_corrente(gestore: Any = None) -> Any:
    """La firma con cui firma chi è collegato: studio + profilo personale, se l'ha scelto."""
    gestore = gestore or _gestore_config()
    firma_studio = gestore.config.firma
    utente = _utente()
    utente_id = str(getattr(utente, "id", "") or "")
    if not utente_id or not hasattr(gestore, "percorso"):
        return firma_studio
    try:
        return firma_effettiva(firma_studio, _archivio(gestore).leggi(utente_id))
    except Exception:
        return firma_studio


def _descrizione_studio(firma: Any) -> dict[str, str]:
    voce = firma_catalogo.prestatore(getattr(firma, "prestatore", "")) or {}
    canale = getattr(firma, "backend_preferito_normalizzato", "auto")
    etichette = {"auto": "Automatico", "pkcs11": "Dispositivo", "remota": "Firma remota", "p12": "Certificato P12", "pem": "Certificato PEM"}
    return {"canale": canale, "canale_etichetta": etichette.get(canale, canale), "prestatore": voce.get("nome", "")}


def payload_personale(gestore: Any = None) -> dict[str, Any]:
    """Il profilo dell'utente collegato, con il catalogo che serve alla maschera adattiva."""
    from web.services.impostazioni_firma import SENTINELLE, firma_payload

    gestore = gestore or _gestore_config()
    utente = _utente()
    utente_id = str(getattr(utente, "id", "") or "")
    profilo = _archivio(gestore).leggi(utente_id) if utente_id else None
    effettiva = firma_effettiva(gestore.config.firma, profilo)
    personale = bool(profilo and profilo.get("backend_preferito") in CANALI_PERSONALI[1:])
    dettaglio = firma_payload(effettiva)
    return {
        "ok": True,
        "puo_modificare": _puo_firmare(utente),
        "utente": str(getattr(utente, "nome_completo", "") or getattr(utente, "username", "") or ""),
        "personale": personale,
        "aggiornato_il": (profilo or {}).get("aggiornato_il", ""),
        "studio": _descrizione_studio(gestore.config.firma),
        "valori": {
            "canale": effettiva.backend_preferito_normalizzato if personale else "studio",
            "prestatore": effettiva.prestatore or "",
            "dispositivo_produttore": effettiva.dispositivo_produttore or "",
            "remota_protocollo": effettiva.remota_protocollo or "",
            "remota_endpoint": effettiva.remota_endpoint or "",
            "remota_utente": effettiva.remota_utente or "",
            "remota_dominio": effettiva.remota_dominio or "",
            "remota_credenziale": effettiva.remota_credenziale or "",
            "remota_tipo_otp": effettiva.remota_tipo_otp or "app",
        },
        "prestatore_info": dettaglio["prestatore_info"],
        "librerie_dispositivo": dettaglio["librerie_dispositivo"],
        "sentinelle": SENTINELLE,
    }


def salva_personale(dati: dict[str, Any], gestore: Any = None) -> tuple[dict[str, Any], int]:
    from web.services.impostazioni_firma import valida_gestore

    gestore = gestore or _gestore_config()
    utente = _utente()
    utente_id = str(getattr(utente, "id", "") or "")
    if not utente_id:
        return {"ok": False, "message": "Sessione utente richiesta."}, 403
    if not _puo_firmare(utente):
        return {"ok": False, "message": "Serve il permesso di lavorare sui fascicoli per impostare la propria firma."}, 403
    canale = str(dati.get("canale") or "studio").strip().lower()
    if canale not in CANALI_PERSONALI:
        return {"ok": False, "message": "Canale di firma non valido.", "errors": {"canale": "Scegli dispositivo, firma remota o la firma dello studio."}}, 400
    archivio = _archivio(gestore)
    if canale == "studio":
        archivio.rimuovi(utente_id)
        return {"ok": True, "message": "Userai la firma impostata per lo studio.", "profilo": payload_personale(gestore)}, 200
    firma_studio = gestore.config.firma
    campi, errori = valida_gestore(dati, firma_studio, canale)
    if errori:
        return {"ok": False, "message": "Controlla la tua firma.", "errors": errori}, 400
    if canale == "pkcs11":
        campi.update({"remota_protocollo": "", "remota_endpoint": "",
                      "remota_utente": "", "remota_dominio": "", "remota_credenziale": "", "remota_tipo_otp": "app"})
    else:
        campi["dispositivo_produttore"] = ""
    archivio.salva(utente_id, {"backend_preferito": canale, **campi})
    nome = (firma_catalogo.prestatore(campi["prestatore"]) or {}).get("nome", "")
    messaggio = (f"La tua firma remota {nome} è pronta: al momento di firmare ti chiederà password e codice OTP."
                 if canale == "remota" else "Il tuo dispositivo di firma è salvato: il Local Signer cercherà prima il suo driver.")
    return {"ok": True, "message": messaggio, "profilo": payload_personale(gestore)}, 200


def prova_collegamento(dati: dict[str, Any], gestore: Any = None) -> tuple[dict[str, Any], int]:
    """Chiede al prestatore il certificato dell'avvocato: verifica utente, password e indirizzo."""
    from pct.firma_remota import CredenzialiFirmaRemota, FirmaRemotaError
    from pct.firma_remota.prestatori import configurazione_da_firma, firmatario

    gestore = gestore or _gestore_config()
    if not _puo_firmare(_utente()):
        return {"ok": False, "message": "Permesso insufficiente."}, 403
    firma = firma_utente_corrente(gestore)
    if firma.backend_preferito_normalizzato != "remota":
        return {"ok": False, "message": "Salva prima la firma remota come tuo canale di firma."}, 400
    password = str(dati.get("password") or "")
    if not password:
        return {"ok": False, "message": "Inserisci la password del servizio di firma per la prova."}, 400
    try:
        conf = configurazione_da_firma(firma)
        servizio = firmatario(conf)
        credenziali = CredenzialiFirmaRemota(username=conf.utente, password=password, pin=str(dati.get("pin") or ""),
                                             tipo_otp=conf.tipo_otp, dominio=conf.dominio)
        try:
            certificato = servizio.certificato(credenziali)
        finally:
            servizio.chiudi(credenziali)
        scadenza = certificato.x509().not_valid_after_utc.date()
    except (ValueError, FirmaRemotaError) as exc:
        return {"ok": False, "message": str(exc)}, 400
    return {"ok": True, "message": f"Collegamento riuscito con {conf.nome_prestatore.rstrip('.')}.",
            "intestatario": certificato.intestatario, "emittente": certificato.emittente,
            "scadenza": scadenza.strftime("%d/%m/%Y")}, 200


__all__ = ["firma_utente_corrente", "payload_personale", "prova_collegamento", "salva_personale"]
