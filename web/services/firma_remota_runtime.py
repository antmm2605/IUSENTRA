"""Firma remota dal fascicolo: stato del prestatore, invio del codice OTP e firma del documento.

La chiave è nell'HSM del prestatore qualificato (Reg. eIDAS art. 29); IUSENTRA costruisce la
busta CAdES o PAdES, manda al prestatore solo l'impronta e salva la versione firmata come le
altre firme (verifica, storico, audit). Password, PIN e OTP arrivano con la richiesta e non
vengono salvati né registrati (``FORBIDDEN_SECRET_KEYS`` di pct.digital_signature_workflow).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from flask import current_app, g

from pct.firma_remota import CredenzialiFirmaRemota, FirmaRemotaError, FirmaRemotaNonConfigurata
from pct.firma_remota.prestatori import ConfigurazioneRemota, configurazione_da_firma, firmatario, provider_da_firma


@dataclass
class Dipendenze:
    get_fascicoli: Callable[[], Any]
    get_config_studio: Callable[[], Any]
    decrypt_doc: Callable[[bytes], bytes]
    encrypt_doc: Callable[[bytes], bytes]
    salva_documento_firmato_resiliente: Callable[..., list]
    audit_and_sync_best_effort: Callable[..., list]


def _firma_config(dip: Dipendenze):
    """La firma di chi è collegato: quella dello studio con il suo profilo personale sopra."""
    from web.services.firma_profilo_runtime import firma_utente_corrente

    return firma_utente_corrente(dip.get_config_studio())


def _permesso_negato() -> tuple[dict[str, Any], int] | None:
    from web.services.firma_profilo_runtime import PERMESSI_FIRMA

    utente = getattr(g, "utente_corrente", None)
    controllo = getattr(utente, "ha_permesso", None)
    if utente is not None and callable(controllo) and not any(controllo(p) for p in PERMESSI_FIRMA):
        return {"ok": False, "messaggio": "Serve il permesso di lavorare sui fascicoli per firmare."}, 403
    return None


def stato(dip: Dipendenze) -> dict[str, Any]:
    """Cosa serve all'avvocato per firmare: prestatore, utente e come arriva il codice."""
    cfg = _firma_config(dip)
    if getattr(cfg, "backend_preferito_normalizzato", "") != "remota":
        return {"ok": True, "attiva": False, "messaggio": "La firma remota non è il tuo canale di firma: sceglila in Impostazioni → La mia firma."}
    try:
        conf = configurazione_da_firma(cfg)
    except FirmaRemotaNonConfigurata as exc:
        return {"ok": True, "attiva": False, "messaggio": str(exc)}
    return {
        "ok": True,
        "attiva": True,
        "prestatore": conf.nome_prestatore,
        "protocollo": conf.protocollo,
        "utente": conf.utente,
        "tipo_otp": conf.tipo_otp,
        "invia_codice": conf.tipo_otp in {"sms", "chiamata", "notifica"} or conf.protocollo == "csc",
        "chiede_pin": conf.protocollo == "csc",
        "etichetta_password": "Password di accesso al servizio" if conf.protocollo == "csc" else "Password (PIN) di firma",
    }


def _credenziali(conf: ConfigurazioneRemota, dati: dict[str, Any]) -> CredenzialiFirmaRemota:
    utente = str(dati.get("utente") or conf.utente or "").strip()
    return CredenzialiFirmaRemota(
        username=utente, password=str(dati.get("password") or ""), otp=str(dati.get("otp") or ""),
        pin=str(dati.get("pin") or ""), tipo_otp=conf.tipo_otp, dominio=conf.dominio,
    )


def invia_codice(dip: Dipendenze, dati: dict[str, Any]) -> tuple[dict[str, Any], int]:
    negato = _permesso_negato()
    if negato:
        return negato
    cfg = _firma_config(dip)
    try:
        conf = configurazione_da_firma(cfg)
        messaggio = firmatario(conf).richiedi_otp(_credenziali(conf, dati))
    except ValueError as exc:
        return {"ok": False, "messaggio": str(exc)}, 400
    except FirmaRemotaError as exc:
        return {"ok": False, "messaggio": str(exc)}, 400
    return {"ok": True, "messaggio": messaggio}, 200


def _nome_firmato(nome: str, formato: str) -> str:
    if formato == "pades" or nome.lower().endswith(".p7m"):
        return nome
    return f"{nome}.p7m"


def firma_documento(dip: Dipendenze, dati: dict[str, Any], *, visibile: dict[str, str], nota: str) -> tuple[dict[str, Any], int]:
    from pct.document_signature_state import document_has_real_digital_signature
    from pct.firma import analizza_firma_documento, busta_cades_valida
    from web.services.fascicoli_signature_options import metadata_firma_cades, metadata_firma_pades

    negato = _permesso_negato()
    if negato:
        return negato
    id_fasc = str(dati.get("fascicolo_id") or "").strip()
    id_doc = str(dati.get("documento_id") or "").strip()
    if not id_fasc or not id_doc:
        return {"ok": False, "messaggio": "fascicolo_id e documento_id obbligatori."}, 400
    if not str(dati.get("otp") or "").strip():
        return {"ok": False, "messaggio": "Inserisci il codice OTP."}, 400
    cfg = _firma_config(dip)
    if getattr(cfg, "backend_preferito_normalizzato", "") != "remota":
        return {"ok": False, "messaggio": "La firma remota non è il tuo canale di firma: sceglila in Impostazioni → La mia firma."}, 400
    gestore = dip.get_fascicoli()
    fascicolo = gestore.get(id_fasc)
    documento = next((d for d in getattr(fascicolo, "documenti", []) or [] if d.id == id_doc), None)
    if fascicolo is None or documento is None:
        return {"ok": False, "messaggio": "Documento non trovato."}, 404
    nome = str(documento.nome or "")
    conferma = str(dati.get("confirm_resign") or "").lower() in {"1", "true", "si", "sì"}
    if document_has_real_digital_signature(documento, nome) and not conferma and not nome.lower().endswith(".p7m"):
        return {"ok": False, "already_signed": True, "requires_confirm_resign": True,
                "messaggio": "Documento già firmato: conferma se vuoi aggiungere un'altra firma."}, 409
    contenuto = dip.decrypt_doc(gestore.percorso_documento_lettura(id_fasc, id_doc).read_bytes())
    formato = str(dati.get("formato") or ("pades" if nome.lower().endswith(".pdf") else "cades")).strip().lower()
    if formato not in {"cades", "pades"}:
        return {"ok": False, "messaggio": "Formato di firma non valido: scegli CAdES o PAdES."}, 400
    if formato == "pades" and not nome.lower().endswith(".pdf"):
        return {"ok": False, "messaggio": "La firma PAdES si appone solo sui PDF: per gli altri file usa CAdES (.p7m)."}, 400
    try:
        conf = configurazione_da_firma(cfg)
        provider, _ = provider_da_firma(cfg)
        credenziali = _credenziali(conf, dati)
        esito = (provider.firma_pades(contenuto, credenziali, **visibile) if formato == "pades"
                 else provider.firma_cades(contenuto, credenziali, **visibile))
    except ValueError as exc:
        return {"ok": False, "messaggio": str(exc)}, 400
    except FirmaRemotaError as exc:
        return {"ok": False, "messaggio": str(exc)}, 400
    firmato = esito.contenuto
    nome_firmato = _nome_firmato(nome, formato)
    if formato == "cades":
        if not busta_cades_valida(firmato):
            return {"ok": False, "messaggio": "La busta firmata non è valida: il documento non è stato modificato."}, 502
        metadati = metadata_firma_cades(nome_firmato, source="firma_remota")
    else:
        firme = analizza_firma_documento(firmato, nome_firmato)
        if not firme or not all(f.get("content_digest_verified") and f.get("cryptographic_signature_verified") for f in firme):
            return {"ok": False, "messaggio": "La firma PAdES non risulta verificabile: il documento non è stato modificato."}, 502
        metadati = metadata_firma_pades(nome_firmato, firme, source="firma_remota")
    metadati.update({"remote_provider": conf.prestatore, "remote_protocol": conf.protocollo,
                     "content_sha256": hashlib.sha256(firmato).hexdigest()})
    utente = getattr(g, "utente_corrente", None)
    avvisi = dip.salva_documento_firmato_resiliente(
        gf=gestore, id_fasc=id_fasc, id_doc=id_doc, nome_file=nome_firmato, contenuto=dip.encrypt_doc(firmato),
        hash_contenuto_sha256=hashlib.sha256(firmato).hexdigest(), caricato_da=getattr(utente, "username", "") or "",
        note=nota,
    )
    gestore.segna_firmato(id_fasc, id_doc, signature_metadata=metadati)
    intestatario = esito.dettagli.get("intestatario", "")
    avvisi += dip.audit_and_sync_best_effort(
        audit_azione="firma.remota", audit_risorsa_tipo="documento", audit_risorsa_id=id_doc,
        audit_dettagli=f"Firma remota {formato.upper()} ({conf.nome_prestatore}) di {intestatario} — {nome_firmato}",
        sync_tipo="modifica", sync_modulo="fascicoli", sync_id_risorsa=id_fasc,
    )
    try:
        from web.services.registro_letture_runtime import documento_aggiornato

        documento_aggiornato(id_fasc, None)
    except Exception:
        current_app.logger.debug("Registro letture non aggiornato dopo la firma remota", exc_info=True)
    return {"ok": True, "nome_firmato": nome_firmato, "intestatario": intestatario, "formato": formato,
            "scadenza": esito.dettagli.get("scadenza", ""), "warning": bool(avvisi), "warning_codes": avvisi,
            "messaggio": f"Documento firmato da {intestatario} con la firma remota di {conf.nome_prestatore.rstrip('.')}."}, 200


__all__ = ["Dipendenze", "firma_documento", "invia_codice", "stato"]
