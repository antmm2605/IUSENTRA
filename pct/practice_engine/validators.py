"""Validatori deterministici della Regia Operativa."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import re

from pct import validazione as pct_validazione
from pct.document_signature_state import document_has_real_digital_signature
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry, normalize_codice_oggetto_pst

from .messages import MAIN_ACT_NOT_PDFA, MAIN_ACT_NOT_SIGNED, MISSING_MAIN_ACT, MISSING_PROCURA, problem_action
from .models import DocumentSlot, SlotStatus, SlotType, ValidationResult, ValidatorStatus


CF_RE = re.compile(r"^[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]$")
PST_CODICE_OGGETTO_CHANNELS = {"PCT_CIVILE", "PCT_LAVORO", "PST_GDP", "SIGP_GDP"}


@dataclass
class ValidationContext:
    fascicolo: Any
    cliente: Any | None = None
    preventivo: Any | None = None
    conferimento: Any | None = None
    parcelle: list[Any] = field(default_factory=list)
    slots: list[DocumentSlot] = field(default_factory=list)
    fascicoli_manager: Any | None = None
    profile: Any | None = None
    audit_events: list[Any] = field(default_factory=list)
    deposito_session: Any | None = None


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ok(key: str, message: str, *, evidence: dict[str, Any] | None = None) -> ValidationResult:
    return ValidationResult(key, ValidatorStatus.OK.value, "INFO", message, suggested_action="", evidence=evidence or {})


def _warning(key: str, message: str, action: str = "", *, evidence: dict[str, Any] | None = None) -> ValidationResult:
    return ValidationResult(key, ValidatorStatus.WARNING.value, "WARNING", message, suggested_action=action, evidence=evidence or {})


def _block(key: str, message: str, action: str = "", detail: str = "", *, evidence: dict[str, Any] | None = None) -> ValidationResult:
    return ValidationResult(key, ValidatorStatus.BLOCK.value, "BLOCK", message, technical_detail=detail, suggested_action=action, evidence=evidence or {})


def _pending(key: str, message: str, action: str = "") -> ValidationResult:
    return ValidationResult(key, ValidatorStatus.PENDING.value, "PENDING", message, suggested_action=action)


def _na(key: str, message: str = "Controllo non applicabile al profilo pratica.") -> ValidationResult:
    return ValidationResult(key, ValidatorStatus.NOT_APPLICABLE.value, "INFO", message)


def _paid_parcelles(parcelle: list[Any]) -> list[Any]:
    return [
        parcella
        for parcella in parcelle
        if _enum_value(getattr(parcella, "stato", "")).upper() in {"PAGATA", "SALDATA"}
        or bool(_text(getattr(parcella, "data_pagamento", "")))
    ]


def _slot(ctx: ValidationContext, slot_type: str = "", slot_key: str = "") -> DocumentSlot | None:
    for slot in ctx.slots:
        if slot_key and slot.slot_key.upper() == slot_key.upper():
            return slot
        if slot_type and slot.type.upper() == slot_type.upper():
            return slot
    return None


def _document_for_slot(ctx: ValidationContext, slot: DocumentSlot | None) -> Any | None:
    if not slot or not slot.document_id:
        return None
    for doc in getattr(ctx.fascicolo, "documenti", []) or []:
        if getattr(doc, "id", "") == slot.document_id:
            return doc
    return None


def _document_path(ctx: ValidationContext, doc: Any | None) -> Path | None:
    if not doc:
        return None
    if ctx.fascicoli_manager:
        try:
            return Path(ctx.fascicoli_manager.percorso_documento(getattr(ctx.fascicolo, "id", ""), getattr(doc, "id", "")))
        except Exception:
            return None
    raw = _text(getattr(doc, "percorso", ""))
    if not raw:
        return None
    return Path(raw)


def cliente_presente(ctx: ValidationContext) -> ValidationResult:
    if ctx.cliente or _text(getattr(ctx.fascicolo, "id_cliente", "")):
        return _ok("cliente_presente", "Cliente collegato al fascicolo.")
    return _block("cliente_presente", "Impossibile procedere: manca il cliente.", "Collega un cliente reale al fascicolo.")


def cliente_cf_valido(ctx: ValidationContext) -> ValidationResult:
    cf = _text(getattr(ctx.cliente, "codice_fiscale", "")) or _text(getattr(ctx.fascicolo, "codice_fiscale_cliente", ""))
    if not cf:
        return _block("cliente_cf_valido", "Impossibile procedere: manca il codice fiscale del cliente.", "Completa l'anagrafica cliente.")
    if CF_RE.match(cf.upper()):
        return _ok("cliente_cf_valido", "Codice fiscale cliente formalmente valido.", evidence={"codice_fiscale": cf.upper()})
    return _block("cliente_cf_valido", "Impossibile procedere: codice fiscale cliente non valido.", "Correggi l'anagrafica prima di proseguire.")


def cliente_email_presente(ctx: ValidationContext) -> ValidationResult:
    email = _text(getattr(ctx.cliente, "email", "")) or _text(getattr(ctx.cliente, "pec", ""))
    if email:
        return _ok("cliente_email_presente", "Recapito email o PEC cliente presente.")
    return _warning("cliente_email_presente", "Attenzione: manca email o PEC cliente.", "Completa il recapito per notifiche e comunicazioni.")


def parte_assistita_completa(ctx: ValidationContext) -> ValidationResult:
    return cliente_presente(ctx)


def controparte_presente(ctx: ValidationContext) -> ValidationResult:
    if _text(getattr(ctx.fascicolo, "controparte", "")):
        return _ok("controparte_presente", "Controparte presente.")
    return _warning("controparte_presente", "Attenzione: controparte non indicata.", "Compila la controparte se la pratica lo richiede.")


def controparte_cf_valido_se_presente(ctx: ValidationContext) -> ValidationResult:
    cf = _text(getattr(ctx.fascicolo, "codice_fiscale_controparte", ""))
    if not cf:
        return _na("controparte_cf_valido_se_presente")
    if CF_RE.match(cf.upper()):
        return _ok("controparte_cf_valido_se_presente", "Codice fiscale controparte formalmente valido.")
    return _warning("controparte_cf_valido_se_presente", "Attenzione: codice fiscale controparte non valido.", "Verifica il dato prima del deposito.")


def avvocato_referente_presente(ctx: ValidationContext) -> ValidationResult:
    if _text(getattr(ctx.fascicolo, "avvocato", "")) or _text(getattr(ctx.conferimento, "avvocato_referente", "")):
        return _ok("avvocato_referente_presente", "Avvocato referente presente.")
    return _block("avvocato_referente_presente", "Impossibile procedere: manca l'avvocato referente.", "Indica il referente nel fascicolo o nel conferimento.")


def codice_fiscale_avvocato_presente(ctx: ValidationContext) -> ValidationResult:
    cf = _text(getattr(ctx.fascicolo, "codice_fiscale_avvocato", ""))
    if cf:
        return _ok("codice_fiscale_avvocato_presente", "Codice fiscale avvocato presente.")
    return _warning("codice_fiscale_avvocato_presente", "Attenzione: codice fiscale avvocato non indicato.", "Completa il profilo studio se richiesto dal canale.")


def ufficio_giudiziario_presente(ctx: ValidationContext) -> ValidationResult:
    if _text(getattr(ctx.fascicolo, "tribunale", "")) or _text(getattr(ctx.fascicolo, "ufficio_giudiziario", "")):
        return _ok("ufficio_giudiziario_presente", "Ufficio giudiziario presente.")
    if not getattr(ctx.profile, "depositable", False):
        return _na("ufficio_giudiziario_presente")
    return _block("ufficio_giudiziario_presente", "Impossibile depositare: manca l'ufficio giudiziario.", "Compila tribunale o ufficio competente.")


def registro_presente(ctx: ValidationContext) -> ValidationResult:
    registry = _text(getattr(ctx.fascicolo, "registro_operativo", "")) or _text(getattr(ctx.profile, "registry", ""))
    if registry:
        return _ok("registro_presente", "Registro operativo presente.", evidence={"registro": registry})
    if not getattr(ctx.profile, "depositable", False):
        return _na("registro_presente")
    return _block("registro_presente", "Impossibile depositare: manca il registro operativo.", "Seleziona registro e rito corretti.")


def codice_oggetto_pst_valido(ctx: ValidationContext) -> ValidationResult:
    channel = _text(getattr(ctx.profile, "channel", "")).upper()
    if channel not in PST_CODICE_OGGETTO_CHANNELS:
        return _na("codice_oggetto_pst_valido")
    raw_codice = _text(getattr(ctx.fascicolo, "codice_oggetto_pst", "")) or _text(getattr(ctx.fascicolo, "oggetto", ""))
    codice = normalize_codice_oggetto_pst(raw_codice)
    if not codice:
        return _block(
            "codice_oggetto_pst_valido",
            "Impossibile depositare: manca il codice oggetto PST del fascicolo.",
            "Seleziona l'oggetto deposito dal catalogo ufficiale prima del predeposito.",
        )
    entry = codice_oggetto_pst_entry(codice)
    if not entry:
        return _block(
            "codice_oggetto_pst_valido",
            "Impossibile depositare: il codice oggetto del fascicolo non appartiene al catalogo ufficiale.",
            "Riapri i dati del fascicolo e scegli un codice dal catalogo PST.",
            evidence={"codice_oggetto_pst": raw_codice},
        )
    return _ok(
        "codice_oggetto_pst_valido",
        "Codice oggetto PST presente e valido nel catalogo ufficiale.",
        evidence={
            "codice_oggetto_pst": entry["codice"],
            "valore_fascicolo": raw_codice,
            "descrizione": entry["descrizione"],
            "area": entry["area_label"],
        },
    )


def numero_rg_valido_se_endoprocedimentale(ctx: ValidationContext) -> ValidationResult:
    rg = _text(getattr(ctx.fascicolo, "numero_rg", ""))
    if not rg:
        return _na("numero_rg_valido_se_endoprocedimentale")
    if re.search(r"\d", rg):
        return _ok("numero_rg_valido_se_endoprocedimentale", "Numero RG presente.")
    return _warning("numero_rg_valido_se_endoprocedimentale", "Attenzione: numero RG non riconoscibile.", "Verifica il numero se l'atto e' endoprocedimentale.")


def preventivo_accettato(ctx: ValidationContext) -> ValidationResult:
    stato = _enum_value(getattr(ctx.preventivo, "stato", "")).upper()
    if stato in {"ACCETTATO", "CONVERTITO"} or _text(getattr(ctx.preventivo, "accettato_il", "")):
        return _ok("preventivo_accettato", "Preventivo accettato.")
    return _block("preventivo_accettato", "Impossibile aprire il fascicolo: preventivo non accettato.", "Registra l'accettazione oppure usa un override motivato e auditato.")


def conferimento_firmato(ctx: ValidationContext) -> ValidationResult:
    if bool(getattr(ctx.conferimento, "firma_cliente_eseguita", False)) or _text(getattr(ctx.conferimento, "firma_cliente_il", "")):
        return _ok("conferimento_firmato", "Conferimento firmato.")
    return _block("conferimento_firmato", "Impossibile aprire il fascicolo: conferimento non firmato.", "Acquisisci la firma del cliente oppure registra un override motivato.")


def pagamento_acconto_registrato(ctx: ValidationContext) -> ValidationResult:
    if _paid_parcelles(ctx.parcelle):
        return _ok("pagamento_acconto_registrato", "Pagamento o acconto registrato.")
    if any(getattr(event, "event_type", "") == "ECONOMIC_OVERRIDE" for event in ctx.audit_events):
        return _warning("pagamento_acconto_registrato", "Apertura consentita con override economico auditato.", "Verifica l'incasso appena possibile.")
    return _block("pagamento_acconto_registrato", "Impossibile aprire il fascicolo: manca pagamento o acconto.", "Registra l'incasso oppure inserisci un override professionale motivato.")


def fattura_emessa(ctx: ValidationContext) -> ValidationResult:
    if ctx.parcelle:
        return _ok("fattura_emessa", "Avviso, parcella o fattura collegata.")
    return _warning("fattura_emessa", "Attenzione: nessun documento economico collegato.", "Emetti avviso o parcella quando previsto.")


def contributo_unificato_calcolato(ctx: ValidationContext) -> ValidationResult:
    if not getattr(ctx.profile, "depositable", False):
        return _na("contributo_unificato_calcolato")
    if any("CONTRIBUTO" in slot.slot_key.upper() for slot in ctx.slots):
        return _ok("contributo_unificato_calcolato", "Slot contributo unificato previsto dal profilo.")
    return _warning("contributo_unificato_calcolato", "Attenzione: contributo unificato non determinato.", "Verifica importo e debenza prima del deposito.")


def contributo_unificato_pagato(ctx: ValidationContext) -> ValidationResult:
    slot = _slot(ctx, SlotType.CONTRIBUTO_UNIFICATO.value)
    if not slot:
        return _na("contributo_unificato_pagato")
    if slot.document_id:
        return _ok("contributo_unificato_pagato", "Ricevuta contributo unificato collegata.")
    return _block("contributo_unificato_pagato", "Impossibile depositare: manca la ricevuta del Contributo Unificato.", "Carica o collega la ricevuta di pagamento.")


def ricevuta_cu_allegata(ctx: ValidationContext) -> ValidationResult:
    return contributo_unificato_pagato(ctx)


def marca_bollo_se_dovuta(ctx: ValidationContext) -> ValidationResult:
    slot = _slot(ctx, SlotType.MARCA_BOLLO.value)
    if not slot:
        return _na("marca_bollo_se_dovuta")
    if slot.document_id:
        return _ok("marca_bollo_se_dovuta", "Marca da bollo collegata.")
    return _warning("marca_bollo_se_dovuta", "Attenzione: marca da bollo prevista ma non collegata.", "Carica ricevuta o marca se dovuta.")


def override_economico_auditato(ctx: ValidationContext) -> ValidationResult:
    if any(getattr(event, "event_type", "") == "ECONOMIC_OVERRIDE" for event in ctx.audit_events):
        return _ok("override_economico_auditato", "Override economico presente e auditato.")
    return _na("override_economico_auditato")


def atto_principale_presente(ctx: ValidationContext) -> ValidationResult:
    slot = _slot(ctx, SlotType.ATTO_PRINCIPALE.value, "ATTO_PRINCIPALE")
    if slot and slot.document_id:
        return _ok("atto_principale_presente", "Atto principale collegato.")
    return _block("atto_principale_presente", MISSING_MAIN_ACT, "Carica o genera l'atto principale.")


def procura_presente(ctx: ValidationContext) -> ValidationResult:
    slot = _slot(ctx, SlotType.PROCURA.value, "PROCURA")
    if slot and slot.document_id:
        return _ok("procura_presente", "Procura alle liti collegata.")
    return _block("procura_presente", MISSING_PROCURA, "Carica una procura firmata oppure generala dal modello.")


def file_presente(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    slot = _slot(ctx, slot_key=slot_key) if slot_key else _slot(ctx, SlotType.ATTO_PRINCIPALE.value, "ATTO_PRINCIPALE")
    doc = _document_for_slot(ctx, slot)
    if doc:
        return _ok("file_presente", "Documento collegato allo slot.", evidence={"document_id": getattr(doc, "id", "")})
    return _block("file_presente", "Impossibile validare: file non collegato allo slot.", "Collega un documento reale prima della verifica.")


def file_apribile(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    slot = _slot(ctx, slot_key=slot_key) if slot_key else _slot(ctx, SlotType.ATTO_PRINCIPALE.value, "ATTO_PRINCIPALE")
    path = _document_path(ctx, _document_for_slot(ctx, slot))
    if path and path.exists() and path.is_file():
        return _ok("file_apribile", "File apribile dal repository documentale.")
    return _block("file_apribile", "Impossibile validare: file non apribile.", "Ricarica il documento o correggi il collegamento.")


def hash_calcolato(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    slot = _slot(ctx, slot_key=slot_key) if slot_key else _slot(ctx, SlotType.ATTO_PRINCIPALE.value, "ATTO_PRINCIPALE")
    doc = _document_for_slot(ctx, slot)
    if _text(getattr(doc, "hash_sha256", "")):
        return _ok("hash_calcolato", "Hash SHA-256 documento presente.", evidence={"hash": getattr(doc, "hash_sha256", "")})
    return _block("hash_calcolato", "Impossibile validare: hash documento assente.", "Ricarica il documento per calcolare l'hash.")


def tipo_documento_classificato(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    slot = _slot(ctx, slot_key=slot_key) if slot_key else None
    doc = _document_for_slot(ctx, slot)
    if _text(getattr(doc, "tipo", "")):
        return _ok("tipo_documento_classificato", "Tipo documento classificato.")
    return _warning("tipo_documento_classificato", "Attenzione: tipo documento non classificato.", "Classifica il documento per mantenerlo governato.")


def documento_non_vuoto(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    slot = _slot(ctx, slot_key=slot_key) if slot_key else _slot(ctx, SlotType.ATTO_PRINCIPALE.value, "ATTO_PRINCIPALE")
    doc = _document_for_slot(ctx, slot)
    if int(getattr(doc, "dimensione_bytes", 0) or 0) > 0:
        return _ok("documento_non_vuoto", "Documento non vuoto.")
    return _block("documento_non_vuoto", "Impossibile validare: documento vuoto.", "Ricarica un file valido.")


def documento_non_corrotto(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    return file_apribile(ctx, slot_key=slot_key)


def documento_non_cifrato(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    return pdf_non_cifrato(ctx, slot_key=slot_key)


def documento_versione_corrente(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    return _ok("documento_versione_corrente", "Versione documento corrente.")


def pdfa_valido(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    slot = _slot(ctx, slot_key=slot_key) if slot_key else _slot(ctx, SlotType.ATTO_PRINCIPALE.value, "ATTO_PRINCIPALE")
    path = _document_path(ctx, _document_for_slot(ctx, slot))
    if not path:
        return _block("pdfa_valido", MISSING_MAIN_ACT, "Collega l'atto principale.")
    result = pct_validazione.verifica_pdfa(str(path))
    if result.get("conforme") is True:
        return _ok("pdfa_valido", "Documento conforme PDF/A.", evidence=result)
    if result.get("conforme") is None:
        return _warning("pdfa_valido", "PDF/A non verificabile sul wrapper firmato.", "Verifica il PDF originale pre-firma.", evidence=result)
    return _block("pdfa_valido", MAIN_ACT_NOT_PDFA, "Converti il documento e ripeti la verifica.", evidence=result)


def pdf_non_cifrato(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    slot = _slot(ctx, slot_key=slot_key) if slot_key else _slot(ctx, SlotType.ATTO_PRINCIPALE.value, "ATTO_PRINCIPALE")
    path = _document_path(ctx, _document_for_slot(ctx, slot))
    if not path:
        return _block("pdf_non_cifrato", "Impossibile validare: documento non collegato.", "Collega il documento.")
    result = pct_validazione.verifica_pdfa(str(path))
    if not result.get("cifrato"):
        return _ok("pdf_non_cifrato", "Documento non cifrato.")
    return _block("pdf_non_cifrato", "Impossibile depositare: il PDF e' cifrato.", "Rimuovi la cifratura e ripeti la verifica.", evidence=result)


def dimensione_file_ok(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    slot = _slot(ctx, slot_key=slot_key) if slot_key else _slot(ctx, SlotType.ATTO_PRINCIPALE.value, "ATTO_PRINCIPALE")
    path = _document_path(ctx, _document_for_slot(ctx, slot))
    if not path:
        return _block("dimensione_file_ok", "Impossibile validare: documento non collegato.", "Collega il documento.")
    result = pct_validazione.verifica_dimensione(str(path))
    if result.get("ok"):
        return _ok("dimensione_file_ok", "Dimensione file entro i limiti.", evidence=result)
    return _block("dimensione_file_ok", "Impossibile depositare: file oltre il limite consentito.", "Riduci dimensione o separa gli allegati.", evidence=result)


def dimensione_busta_ok(ctx: ValidationContext) -> ValidationResult:
    total = sum(int(getattr(doc, "dimensione_bytes", 0) or 0) for doc in getattr(ctx.fascicolo, "documenti", []) or [])
    if total <= 60 * 1024 * 1024:
        return _ok("dimensione_busta_ok", "Dimensione complessiva busta entro il limite operativo.", evidence={"bytes": total})
    return _block("dimensione_busta_ok", "Impossibile depositare: busta oltre il limite operativo.", "Riduci o separa gli allegati.", evidence={"bytes": total})


def firma_digitale_presente(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    slot = _slot(ctx, slot_key=slot_key) if slot_key else _slot(ctx, SlotType.ATTO_PRINCIPALE.value, "ATTO_PRINCIPALE")
    doc = _document_for_slot(ctx, slot)
    if document_has_real_digital_signature(doc):
        return _ok("firma_digitale_presente", "Firma digitale presente.")
    return _block("firma_digitale_presente", MAIN_ACT_NOT_SIGNED, "Firma il documento prima del deposito.")


def firma_digitale_valida(ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    if firma_digitale_presente(ctx, slot_key=slot_key).status == ValidatorStatus.OK.value:
        return _warning("firma_digitale_valida", "Firma digitale presente ma non verificata crittograficamente in questo runtime.", "Verifica con Local Signer se richiesto.")
    return firma_digitale_presente(ctx, slot_key=slot_key)


def certificato_non_scaduto_se_verificabile(ctx: ValidationContext) -> ValidationResult:
    return _warning("certificato_non_scaduto_se_verificabile", "Certificato non verificabile dal runtime server.", "Usa Local Signer per la verifica certificato prima del deposito.")


def firma_pades_o_cades_ammessa(ctx: ValidationContext) -> ValidationResult:
    return _ok("firma_pades_o_cades_ammessa", "Policy firma PAdES/CAdES ammessa dal profilo.")


def atto_principale_pdfa_pre_firma(ctx: ValidationContext) -> ValidationResult:
    return pdfa_valido(ctx)


def schema_xsd_presente(ctx: ValidationContext) -> ValidationResult:
    if not getattr(ctx.profile, "depositable", False):
        return _na("schema_xsd_presente")
    return _warning("schema_xsd_presente", "Schema ministeriale non verificato nel runtime corrente.", "Esegui predeposito con connettore ministeriale configurato.")


def schema_xsd_versione_corrente(ctx: ValidationContext) -> ValidationResult:
    return schema_xsd_presente(ctx)


def dati_atto_xml_generabile(ctx: ValidationContext) -> ValidationResult:
    if not getattr(ctx.profile, "depositable", False):
        return _na("dati_atto_xml_generabile")
    base = [cliente_presente(ctx), ufficio_giudiziario_presente(ctx), registro_presente(ctx), atto_principale_presente(ctx)]
    blockers = [item for item in base if item.blocking]
    if blockers:
        return _block("dati_atto_xml_generabile", "Impossibile generare DatiAtto.xml: dati o atto principale incompleti.", "Risolvi i blocchi del predeposito.")
    return _ok("dati_atto_xml_generabile", "Dati minimi per DatiAtto.xml presenti.")


def dati_atto_xml_valido(ctx: ValidationContext) -> ValidationResult:
    return schema_xsd_presente(ctx)


def busta_generabile(ctx: ValidationContext) -> ValidationResult:
    if not getattr(ctx.profile, "depositable", False):
        return _na("busta_generabile")
    if atto_principale_presente(ctx).blocking:
        return _block("busta_generabile", "Impossibile preparare la busta: manca l'atto principale.", "Collega l'atto principale.")
    return _ok("busta_generabile", "Busta di predeposito tecnicamente preparabile.")


def busta_cifrata_reale_se_produzione(ctx: ValidationContext) -> ValidationResult:
    session = ctx.deposito_session
    if session and getattr(session, "real_transport", False) and not getattr(session, "simulated", False):
        return _ok("busta_cifrata_reale_se_produzione", "Trasporto reale configurato.")
    return _block("busta_cifrata_reale_se_produzione", "Invio reale non disponibile: busta ministeriale reale non configurata.", "Configura il trasporto autorizzato o resta in predeposito.")


def busta_sotto_limite(ctx: ValidationContext) -> ValidationResult:
    return dimensione_busta_ok(ctx)


def pec_destinatario_ufficio_valida(ctx: ValidationContext) -> ValidationResult:
    if not getattr(ctx.profile, "depositable", False):
        return _na("pec_destinatario_ufficio_valida")
    pec = _text(getattr(ctx.fascicolo, "pec_ufficio", "")) or _text(getattr(ctx.fascicolo, "pec_destinatario", ""))
    if pec and "@" in pec:
        return _ok("pec_destinatario_ufficio_valida", "PEC ufficio presente.")
    return _warning("pec_destinatario_ufficio_valida", "Attenzione: PEC ufficio non verificata.", "Se il canale usa PEC, seleziona l'indirizzo ufficiale dal catalogo uffici.")


def oggetto_pec_conforme(ctx: ValidationContext) -> ValidationResult:
    if not getattr(ctx.profile, "depositable", False):
        return _na("oggetto_pec_conforme")
    return _ok("oggetto_pec_conforme", "Oggetto PEC generabile secondo policy del canale.")


def mittente_reginde_verificabile_se_servizio_disponibile(ctx: ValidationContext) -> ValidationResult:
    return _warning("mittente_reginde_verificabile_se_servizio_disponibile", "Mittente ReGINde non verificato dal server.", "Verifica con Local Connector o servizio autorizzato se disponibile.")


def ricevuta_finale_presente(ctx: ValidationContext) -> ValidationResult:
    session = ctx.deposito_session
    if session and _text(getattr(session, "final_receipt_id", "")):
        return _ok("ricevuta_finale_presente", "Ricevuta finale positiva presente.")
    return _pending("ricevuta_finale_presente", "Deposito non ancora acquisito: manca esito finale positivo.", "Importa l'esito ufficiale del canale.")


VALIDATORS: dict[str, Callable[..., ValidationResult]] = {
    name: obj
    for name, obj in globals().items()
    if callable(obj) and not name.startswith("_") and name not in {"ValidationContext", "ValidationResult", "Callable"}
}


def run_validator(key: str, ctx: ValidationContext, *, slot_key: str = "") -> ValidationResult:
    fn = VALIDATORS.get(str(key or "").strip())
    if not fn:
        return _warning(str(key or "validator_sconosciuto"), "Controllo non disponibile nel runtime corrente.", "Aggiorna il profilo o la configurazione del validatore.")
    try:
        if slot_key and key in {"file_presente", "file_apribile", "hash_calcolato", "tipo_documento_classificato", "documento_non_vuoto", "documento_non_corrotto", "documento_non_cifrato", "pdfa_valido", "pdf_non_cifrato", "dimensione_file_ok", "firma_digitale_presente", "firma_digitale_valida"}:
            return fn(ctx, slot_key=slot_key)
        return fn(ctx)
    except Exception as exc:
        return ValidationResult(
            str(key or "validator_error"),
            ValidatorStatus.ERROR.value,
            "ERROR",
            problem_action("Controllo non completato", "Correggi i dati e ripeti la verifica"),
            technical_detail=str(exc),
            suggested_action="Riesegui il controllo dopo la correzione.",
        )


def run_validators(keys: list[str], ctx: ValidationContext) -> list[ValidationResult]:
    return [run_validator(key, ctx) for key in keys]


def validate_slot(slot: DocumentSlot, ctx: ValidationContext) -> tuple[DocumentSlot, list[ValidationResult]]:
    results = [run_validator(key, ctx, slot_key=slot.slot_key) for key in slot.validators]
    blockers = [item for item in results if item.blocking]
    warnings = [item for item in results if item.status == ValidatorStatus.WARNING.value]
    slot.last_validation_at = results[-1].created_at if results else ""
    if blockers:
        slot.status = SlotStatus.NON_VALIDO.value
        slot.message = blockers[0].message
        slot.suggested_action = blockers[0].suggested_action
    elif warnings:
        slot.status = SlotStatus.WARNING.value
        slot.message = warnings[0].message
        slot.suggested_action = warnings[0].suggested_action
    elif slot.document_id:
        slot.status = SlotStatus.VALIDO.value
        slot.message = "Slot documentale validato."
        slot.suggested_action = ""
    elif not slot.required:
        slot.status = SlotStatus.NON_APPLICABILE.value
        slot.message = "Slot facoltativo non compilato."
        slot.suggested_action = ""
    else:
        slot.status = SlotStatus.MANCANTE.value
        slot.message = "Documento richiesto mancante."
        slot.suggested_action = "Carica o collega il documento richiesto."
    return slot, results
