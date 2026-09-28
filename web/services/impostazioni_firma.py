"""Impostazioni → Firma digitale: canale, prestatore, dispositivo e firma remota.

Il catalogo (pct/data/cataloghi/firma_digitale.json) dà l'elenco AgID dei prestatori,
i protocolli di firma remota che ciascuno pubblica e i produttori dei dispositivi con le
librerie PKCS#11. Qui si validano le scelte dello studio; password, PIN e OTP di firma
non passano mai da qui (si digitano a ogni firma).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable
from urllib.parse import urlparse

from pct import firma_catalogo
from pct.config_studio import BACKEND_FIRMA, ConfigFirma

TIPI_OTP = ("app", "sms", "chiamata", "notifica")
#: Valori «nessuna scelta» delle tendine (il componente di selezione non ammette il valore vuoto).
SENTINELLE = {"prestatore": "nessuno", "dispositivo_produttore": "automatico", "remota_protocollo": "predefinito"}


def _testo(valore: Any, predefinito: str = "") -> str:
    testo = str(valore if valore is not None else "").strip()
    return testo or predefinito


def _scelta(data: dict[str, Any], campo: str, attuale: str) -> str:
    valore = str(data.get(campo) if data.get(campo) is not None else attuale or "").strip().lower()
    return "" if valore == SENTINELLE[campo] else valore


def _endpoint(valore: str) -> tuple[str, str]:
    if not valore:
        return "", ""
    parti = urlparse(valore)
    if parti.scheme != "https" or not parti.hostname:
        return "", "L'indirizzo del servizio deve iniziare con https://."
    return valore.rstrip("/"), ""


def valida_gestore(data: dict[str, Any], attuale: Any, backend: str) -> tuple[dict[str, str], dict[str, str]]:
    """Gestore, dispositivo e dati della firma remota scelti, validati sul catalogo AgID.

    Vale per la firma dello studio e per quella personale dell'avvocato: il prestatore decide
    quali protocolli, quali codici OTP e quali campi servono.
    """
    errori: dict[str, str] = {}
    prestatore = _scelta(data, "prestatore", getattr(attuale, "prestatore", ""))
    if prestatore and firma_catalogo.prestatore(prestatore) is None:
        errori["prestatore"] = "Prestatore non presente nell'elenco AgID."
    produttore = _scelta(data, "dispositivo_produttore", getattr(attuale, "dispositivo_produttore", ""))
    if produttore and firma_catalogo.produttore(produttore) is None:
        errori["dispositivo_produttore"] = "Produttore del dispositivo non riconosciuto."
    protocollo = _scelta(data, "remota_protocollo", getattr(attuale, "remota_protocollo", ""))
    if protocollo and protocollo not in firma_catalogo.PROTOCOLLI_REMOTI:
        errori["remota_protocollo"] = "Protocollo di firma remota non riconosciuto."
    elif protocollo and prestatore and protocollo not in firma_catalogo.protocolli_remoti(prestatore):
        errori["remota_protocollo"] = "Il prestatore scelto non usa questo protocollo."
    endpoint, errore = _endpoint(_testo(data.get("remota_endpoint"), getattr(attuale, "remota_endpoint", "")))
    if errore:
        errori["remota_endpoint"] = errore
    tipo_otp = _testo(data.get("remota_tipo_otp"), getattr(attuale, "remota_tipo_otp", "") or "app").lower()
    if tipo_otp not in TIPI_OTP:
        errori["remota_tipo_otp"] = "Tipo di codice OTP non riconosciuto."
    if backend == "remota":
        if not prestatore:
            errori["prestatore"] = "Per la firma remota scegli il prestatore."
        elif "prestatore" not in errori:
            protocolli = firma_catalogo.protocolli_remoti(prestatore)
            effettivo = protocollo or (protocolli[0] if protocolli else "")
            if not protocolli:
                errori["prestatore"] = (f"{firma_catalogo.prestatore(prestatore)['nome']} non pubblica un servizio di firma "
                                        "remota per i gestionali: firma dalla sua app e carica il file con «Firma esterna».")
            elif effettivo in firma_catalogo.PROTOCOLLI_REMOTI:
                ammessi = firma_catalogo.catalogo()["protocolli_remoti"][effettivo].get("otp") or list(TIPI_OTP)
                if tipo_otp in TIPI_OTP and tipo_otp not in ammessi:
                    errori["remota_tipo_otp"] = "Questo servizio non invia il codice in questo modo."
                if effettivo == "csc" and endpoint and not endpoint.endswith(("/csc/v1", "/csc/v2")):
                    errori["remota_endpoint"] = "L'indirizzo del servizio CSC termina con /csc/v1 o /csc/v2."
                if not endpoint and "remota_endpoint" not in errori \
                        and not firma_catalogo.endpoint_predefinito(prestatore, effettivo):
                    errori["remota_endpoint"] = "Inserisci l'indirizzo del servizio rilasciato dal prestatore con il contratto."
    campi = {
        "prestatore": prestatore,
        "dispositivo_produttore": produttore,
        "remota_protocollo": protocollo,
        "remota_endpoint": endpoint,
        "remota_utente": _testo(data.get("remota_utente"), getattr(attuale, "remota_utente", "")),
        "remota_dominio": _testo(data.get("remota_dominio"), getattr(attuale, "remota_dominio", "")),
        "remota_credenziale": _testo(data.get("remota_credenziale"), getattr(attuale, "remota_credenziale", "")),
        "remota_tipo_otp": tipo_otp,
    }
    return campi, errori


def firma_da_richiesta(firma: ConfigFirma, data: dict[str, Any], *, percorso_caricato: Callable[..., str],
                       normalizza_modo: Callable[[str], str]) -> tuple[ConfigFirma, dict[str, str]]:
    """La nuova configurazione della firma (tutti i campi esistenti conservati) e gli eventuali errori."""
    backend = _testo(data.get("backend_preferito") or data.get("firma_formato"), "auto").lower()
    if backend not in BACKEND_FIRMA:
        backend = "auto"
    campi, errori = valida_gestore(data, firma, backend)
    if errori:
        return firma, errori

    password = _testo(data.get("password") or data.get("firma_password"))
    password_chiave = _testo(data.get("key_pem_password") or data.get("firma_key_pem_password"))
    nuova = replace(
        firma,
        p12_path=percorso_caricato("firma_p12_file", "firma", {".p12", ".pfx"}, _testo(data.get("p12_path"), firma.p12_path)),
        password=password or firma.password,
        cert_pem_path=percorso_caricato("firma_cert_pem_file", "firma_cert", {".crt", ".cer", ".pem"},
                                        _testo(data.get("cert_pem_path"), firma.cert_pem_path)),
        key_pem_path=percorso_caricato("firma_key_pem_file", "firma_key", {".key", ".pem"},
                                       _testo(data.get("key_pem_path"), firma.key_pem_path)),
        key_pem_password=password_chiave or firma.key_pem_password,
        pkcs11_library=_testo(data.get("pkcs11_library")),
        pkcs11_slot=_testo(data.get("pkcs11_slot")),
        pkcs11_label=_testo(data.get("pkcs11_label")),
        cf_avvocato=_testo(data.get("cf_avvocato") or data.get("firma_cf_avvocato")).upper(),
        backend_preferito=backend,
        visible_signature_mode=normalizza_modo(_testo(data.get("visible_signature_mode"), firma.visible_signature_mode)),
        **campi,
    )
    return nuova, {}


def firma_payload(firma: ConfigFirma) -> dict[str, Any]:
    """Campi e aiuti per la sezione: scelte salvate, cosa offre il prestatore, librerie del dispositivo."""
    voce = firma_catalogo.prestatore(firma.prestatore) or {}
    remota = voce.get("remota") or {}
    protocolli = firma_catalogo.protocolli_remoti(firma.prestatore)
    protocollo = firma.remota_protocollo or (protocolli[0] if protocolli else "")
    return {
        "prestatore": firma.prestatore or SENTINELLE["prestatore"],
        "dispositivo_produttore": firma.dispositivo_produttore or SENTINELLE["dispositivo_produttore"],
        "remota_protocollo": firma.remota_protocollo or SENTINELLE["remota_protocollo"],
        "remota_endpoint": firma.remota_endpoint,
        "remota_utente": firma.remota_utente,
        "remota_dominio": firma.remota_dominio,
        "remota_credenziale": firma.remota_credenziale,
        "remota_tipo_otp": firma.remota_tipo_otp or "app",
        "remota_configurata": firma.remota_configurata,
        "prestatore_info": {
            "nome": voce.get("nome", ""),
            "sito": voce.get("sito", ""),
            "protocolli": protocolli,
            "protocollo_effettivo": protocollo,
            "endpoint_predefinito": firma_catalogo.endpoint_predefinito(firma.prestatore, protocollo) if protocollo else "",
            "nota": remota.get("nota", ""),
            "dispositivi_abituali": voce.get("dispositivi") or [],
        },
        "librerie_dispositivo": {
            sistema: firma_catalogo.librerie_candidate(firma.dispositivo_produttore, sistema)[:6]
            for sistema in ("windows", "linux", "macos")
        } if firma.dispositivo_produttore else {},
    }


def opzioni() -> dict[str, list[dict[str, str]]]:
    return firma_catalogo.opzioni_impostazioni()


__all__ = ["TIPI_OTP", "firma_da_richiesta", "firma_payload", "opzioni"]
