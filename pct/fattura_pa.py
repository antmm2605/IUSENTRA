"""
pct/fattura_pa.py — Generazione XML FatturaPA 1.2 (FPR12/FPA12).

Produce il file XML conforme allo standard SDI dell'Agenzia delle Entrate
a partire da una Parcella esistente, pronto per l'invio manuale tramite:
  - Portale "Fatture e Corrispettivi" (fatture.entrate.gov.it)
  - Provider intermediari (Aruba, Teamsystem, Namirial, ecc.)

Riferimenti normativi:
  - DPR 633/1972 (IVA)
  - D.Lgs. 127/2015 (fatturazione elettronica)
  - Specifiche tecniche SDI v1.2.1
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date
from typing import Optional, TYPE_CHECKING

from lxml import etree
from pct.economico_context import causale_documento_economico

if TYPE_CHECKING:
    from pct.fatturazione import Parcella
    from pct.clienti import Cliente

# Namespace FatturaPA
_NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"
_NSMAP = {None: _NS}

# Codice regime fiscale (RF01 = ordinario, RF19 = forfettario)
REGIME_ORDINARIO   = "RF01"
REGIME_FORFETTARIO = "RF19"
REGIME_MINIMO      = "RF02"

# Modalità di pagamento
MP_BONIFICO      = "MP05"
MP_CONTANTI      = "MP01"
MP_ASSEGNO       = "MP02"
MP_CARTA         = "MP08"
MP_PAYPAL        = "MP12"
MP_SATISPAY      = "MP23"

_METODO_MAP = {
    "Bonifico bancario": MP_BONIFICO,
    "Contanti":          MP_CONTANTI,
    "Assegno":           MP_ASSEGNO,
    "Carta di credito":  MP_CARTA,
    "PayPal":            MP_PAYPAL,
}


def _el(parent: etree._Element, tag: str, text: str = "") -> etree._Element:
    """Crea e aggiunge un sub-element, omette se text è vuoto."""
    e = etree.SubElement(parent, f"{{{_NS}}}{tag}")
    if text:
        e.text = str(text)
    return e


def _progressivo(parcella_numero: str) -> str:
    """Deriva il ProgressivoInvio dal numero parcella (es. '2025/001' → '2025001')."""
    return parcella_numero.replace("/", "").replace("-", "")


def _snapshot(parcella: "Parcella") -> dict:
    raw = getattr(parcella, "dati_personalizzati", None)
    return raw if isinstance(raw, dict) else {}


def _section(data: dict, name: str) -> dict:
    raw = data.get(name)
    return raw if isinstance(raw, dict) else {}


def _clean(value: object, limit: int = 0) -> str:
    text = str(value or "").strip()
    if limit > 0:
        return text[:limit]
    return text


def _digits(value: object, limit: int = 0) -> str:
    digits = re.sub(r"\D+", "", _clean(value))
    if limit > 0:
        return digits[:limit]
    return digits


def _country_code(value: object) -> str:
    raw = _clean(value).upper()
    if not raw or raw in {"IT", "ITALIA"}:
        return "IT"
    return raw[:2] if len(raw) >= 2 else "IT"


def genera_xml_fattura_pa(
    parcella: "Parcella",
    cliente: "Cliente",
    studio_nome: str,
    studio_piva: str,
    studio_cf: str,
    studio_indirizzo: str = "",
    regime_fiscale: str = REGIME_ORDINARIO,
    codice_destinatario: str = "0000000",
    pec_destinatario: str = "",
) -> bytes:
    """
    Genera il file XML FatturaPA 1.2 (FPR12) per una parcella.

    Args:
        parcella:            Oggetto Parcella da convertire.
        cliente:             Oggetto Cliente destinatario.
        studio_nome:         Denominazione dello studio (cedente).
        studio_piva:         P.IVA dello studio (11 cifre).
        studio_cf:           Codice fiscale dello studio.
        studio_indirizzo:    Indirizzo completo dello studio.
        regime_fiscale:      Codice regime IVA (default RF01 = ordinario).
        codice_destinatario: Codice SDI a 7 char del destinatario
                             (usare '0000000' con PEC).
        pec_destinatario:    PEC del destinatario (se CodiceDestinatario='0000000').

    Returns:
        XML in bytes (UTF-8) pronto per il salvataggio come .xml.
    """
    snapshot = _snapshot(parcella)
    transmission = _section(snapshot, "transmission")
    studio_snapshot = _section(snapshot, "studio")
    recipient_snapshot = _section(snapshot, "recipient")
    document_snapshot = _section(snapshot, "document")
    payment_snapshot = _section(snapshot, "payment")

    regime_fiscale = _clean(document_snapshot.get("regime_fiscale") or regime_fiscale or REGIME_ORDINARIO, 4) or REGIME_ORDINARIO
    studio_piva = _digits(studio_snapshot.get("partita_iva") or studio_piva, 11)
    studio_cf = _clean(studio_snapshot.get("codice_fiscale") or studio_cf, 16)
    studio_indirizzo = _clean(studio_snapshot.get("indirizzo_completo") or studio_indirizzo, 240)
    studio_denominazione = _clean(studio_snapshot.get("nome_denominazione") or studio_nome, 80)
    studio_nome_pf = _clean(studio_snapshot.get("nome"), 60)
    studio_cognome_pf = _clean(studio_snapshot.get("cognome"), 60)
    recipient_country = _country_code(recipient_snapshot.get("nazione"))
    recipient_piva = _digits(recipient_snapshot.get("partita_iva") or getattr(cliente, "partita_iva", ""), 16)
    recipient_cf = _clean(recipient_snapshot.get("codice_fiscale") or getattr(cliente, "codice_fiscale", ""), 16)
    recipient_denominazione = _clean(
        recipient_snapshot.get("denominazione")
        or recipient_snapshot.get("nome_denominazione")
        or getattr(cliente, "ragione_sociale", "")
        or getattr(cliente, "nome_completo", ""),
        80,
    )
    recipient_nome = _clean(recipient_snapshot.get("nome") or getattr(cliente, "nome", ""), 60)
    recipient_cognome = _clean(recipient_snapshot.get("cognome") or getattr(cliente, "cognome", ""), 60)
    recipient_address = _clean(recipient_snapshot.get("indirizzo_completo"))
    if not recipient_address and cliente:
        indirizzo_cliente = getattr(cliente, "indirizzo_sede_legale", None) or getattr(cliente, "indirizzo_residenza", None)
        recipient_address = str(indirizzo_cliente or "")
    codice_destinatario = _clean(recipient_snapshot.get("codice_destinatario") or codice_destinatario or "0000000", 7) or "0000000"
    pec_destinatario = _clean(
        recipient_snapshot.get("pec")
        or pec_destinatario
        or (getattr(getattr(cliente, "recapiti", None), "pec", "") if cliente else ""),
        256,
    )
    progressivo_invio = _clean(transmission.get("codice_invio"), 10) or _progressivo(parcella.numero)
    trasmittente_fiscale = _clean(
        transmission.get("identificativo_fiscale")
        or studio_snapshot.get("codice_fiscale")
        or studio_snapshot.get("partita_iva")
        or studio_piva
        or studio_cf,
        16,
    )
    tipo_documento = _clean(document_snapshot.get("tipo_documento"), 4) or "TD01"
    modalita_pagamento_label = _clean(payment_snapshot.get("modalita_pagamento_label") or payment_snapshot.get("modalita_pagamento"))
    modalita_pagamento_codice = _clean(payment_snapshot.get("modalita_pagamento_codice"), 4)
    importo_pagamento_raw = _clean(payment_snapshot.get("importo_pagamento"))
    importo_pagamento = parcella.totale
    if importo_pagamento_raw:
        try:
            importo_pagamento = float(importo_pagamento_raw.replace(",", "."))
        except ValueError:
            importo_pagamento = parcella.totale

    root = etree.Element(f"{{{_NS}}}FatturaElettronica", nsmap=_NSMAP)
    root.set("versione", "FPR12")
    header = _el(root, "FatturaElettronicaHeader")

    dt = _el(header, "DatiTrasmissione")
    id_tx = _el(dt, "IdTrasmittente")
    _el(id_tx, "IdPaese", "IT")
    _el(id_tx, "IdCodice", trasmittente_fiscale[:16])
    _el(dt, "ProgressivoInvio", progressivo_invio)
    _el(dt, "FormatoTrasmissione", "FPR12")
    _el(dt, "CodiceDestinatario", codice_destinatario.upper().ljust(7, "0")[:7])
    if _clean(transmission.get("telefono")) or _clean(transmission.get("email")):
        contatti_tx = _el(dt, "ContattiTrasmittente")
        if _clean(transmission.get("telefono")):
            _el(contatti_tx, "Telefono", _digits(transmission.get("telefono"), 12))
        if _clean(transmission.get("email")):
            _el(contatti_tx, "Email", _clean(transmission.get("email"), 256))
    if pec_destinatario:
        _el(dt, "PECDestinatario", pec_destinatario)

    cp = _el(header, "CedentePrestatore")
    da_cp = _el(cp, "DatiAnagrafici")
    if studio_piva:
        ifiva = _el(da_cp, "IdFiscaleIVA")
        _el(ifiva, "IdPaese", "IT")
        _el(ifiva, "IdCodice", studio_piva[:11])
    if studio_cf:
        _el(da_cp, "CodiceFiscale", studio_cf[:16])
    ana_cp = _el(da_cp, "Anagrafica")
    if studio_denominazione:
        _el(ana_cp, "Denominazione", studio_denominazione)
    else:
        _el(ana_cp, "Nome", studio_nome_pf[:60])
        _el(ana_cp, "Cognome", studio_cognome_pf[:60])
    _el(da_cp, "RegimeFiscale", regime_fiscale)
    sede_cp = _el(cp, "Sede")
    _split_indirizzo(sede_cp, studio_indirizzo, nazione="IT")

    cc = _el(header, "CessionarioCommittente")
    da_cc = _el(cc, "DatiAnagrafici")
    if recipient_piva:
        ifiva_cl = _el(da_cc, "IdFiscaleIVA")
        _el(ifiva_cl, "IdPaese", recipient_country)
        _el(ifiva_cl, "IdCodice", recipient_piva[:16])
    if recipient_cf:
        _el(da_cc, "CodiceFiscale", recipient_cf[:16])
    ana_cc = _el(da_cc, "Anagrafica")
    if recipient_denominazione:
        _el(ana_cc, "Denominazione", recipient_denominazione)
    elif recipient_nome or recipient_cognome:
        _el(ana_cc, "Nome", recipient_nome[:60])
        _el(ana_cc, "Cognome", recipient_cognome[:60])
    else:
        _el(ana_cc, "Denominazione", "Cliente")
    sede_cc = _el(cc, "Sede")
    _split_indirizzo(sede_cc, recipient_address, nazione=recipient_country)

    body = _el(root, "FatturaElettronicaBody")
    dg = _el(body, "DatiGenerali")
    dgd = _el(dg, "DatiGeneraliDocumento")
    _el(dgd, "TipoDocumento", tipo_documento)
    _el(dgd, "Divisa", "EUR")
    _el(dgd, "Data", _clean(document_snapshot.get("data_documento") or parcella.data_emissione, 10))
    _el(dgd, "Numero", parcella.numero)

    iva_applicabile = bool(getattr(parcella, "iva_applicabile", getattr(parcella, "applica_iva", False)))

    if parcella.applica_cassa and parcella.cassa_forense > 0:
        dcp = _el(dgd, "DatiCassaPrevidenziale")
        _el(dcp, "TipoCassa", "CAF")
        _el(dcp, "AlCassa", "4.00")
        _el(dcp, "ImportoContributoCassa", f"{parcella.cassa_forense:.2f}")
        _el(dcp, "ImponibileCassa", f"{parcella.imponibile:.2f}")
        _el(dcp, "AliquotaIVA", "22.00" if iva_applicabile else "0.00")
        _el(dcp, "Ritenuta", "SI" if parcella.applica_ritenuta else "NO")

    if parcella.applica_ritenuta and parcella.ritenuta > 0:
        dr = _el(dgd, "DatiRitenuta")
        _el(dr, "TipoRitenuta", "RT01")
        _el(dr, "ImportoRitenuta", f"{parcella.ritenuta:.2f}")
        _el(dr, "AliquotaRitenuta", "20.00")
        _el(dr, "CausalePagamento", "P")

    if parcella.applica_bollo and parcella.bollo > 0:
        db = _el(dgd, "DatiBollo")
        _el(db, "BolloVirtuale", "SI")
        _el(db, "ImportoBollo", f"{parcella.bollo:.2f}")

    _el(dgd, "ImportoTotaleDocumento", f"{parcella.totale_documento:.2f}")
    causale = causale_documento_economico(
        _clean(document_snapshot.get("causale_oggetto") or parcella.note, 2000),
        getattr(parcella, "log_calcolo", None),
    )
    if causale:
        _el(dgd, "Causale", causale[:200])

    dbs = _el(body, "DatiBeniServizi")
    aliquota = "22.00" if iva_applicabile else "0.00"
    natura = "" if iva_applicabile else "N2.2"
    line_number = 1
    for voce in parcella.voci:
        dl = _el(dbs, "DettaglioLinee")
        _el(dl, "NumeroLinea", str(line_number))
        _el(dl, "Descrizione", voce.descrizione[:1000])
        _el(dl, "Quantita", f"{voce.quantita:.2f}")
        _el(dl, "PrezzoUnitario", f"{voce.prezzo_unitario:.8f}")
        _el(dl, "PrezzoTotale", f"{voce.importo:.2f}")
        if str(getattr(voce, "tipo", "ONORARIO") or "ONORARIO").upper() == "ANTICIPO":
            _el(dl, "AliquotaIVA", "0.00")
            _el(dl, "Natura", "N1")
        else:
            _el(dl, "AliquotaIVA", aliquota)
            if natura:
                _el(dl, "Natura", natura)
        line_number += 1

    if getattr(parcella, "spese_generali", 0.0) > 0:
        dl_spese = _el(dbs, "DettaglioLinee")
        _el(dl_spese, "NumeroLinea", str(line_number))
        _el(dl_spese, "Descrizione", f"Spese generali {float(getattr(parcella, 'percentuale_spese_generali', 0.0) or 0.0):.0f}%")
        _el(dl_spese, "Quantita", "1.00")
        _el(dl_spese, "PrezzoUnitario", f"{parcella.spese_generali:.8f}")
        _el(dl_spese, "PrezzoTotale", f"{parcella.spese_generali:.2f}")
        _el(dl_spese, "AliquotaIVA", aliquota)
        if natura:
            _el(dl_spese, "Natura", natura)
        line_number += 1

    if parcella.applica_cassa and parcella.cassa_forense > 0:
        dl_cassa = _el(dbs, "DettaglioLinee")
        _el(dl_cassa, "NumeroLinea", str(line_number))
        _el(dl_cassa, "Descrizione", "Contributo Cassa Forense 4% (art. 11 L. 576/1980)")
        _el(dl_cassa, "Quantita", "1.00")
        _el(dl_cassa, "PrezzoUnitario", f"{parcella.cassa_forense:.8f}")
        _el(dl_cassa, "PrezzoTotale", f"{parcella.cassa_forense:.2f}")
        _el(dl_cassa, "AliquotaIVA", aliquota)
        if natura:
            _el(dl_cassa, "Natura", natura)

    dr_rie = _el(dbs, "DatiRiepilogo")
    _el(dr_rie, "AliquotaIVA", aliquota)
    if natura:
        _el(dr_rie, "Natura", natura)
        riferimento_normativo = (
            "Operazione in franchigia IVA ex art. 1, co. 54-89, L. 190/2014"
            if regime_fiscale == REGIME_FORFETTARIO
            else "Operazione non soggetta ad IVA in base al regime fiscale applicato"
        )
        _el(dr_rie, "RiferimentoNormativo", riferimento_normativo)
    _el(dr_rie, "ImponibileImporto", f"{parcella.base_iva:.2f}")
    _el(dr_rie, "Imposta", f"{parcella.iva:.2f}")
    _el(dr_rie, "EsigibilitaIVA", _clean(document_snapshot.get("esigibilita_iva"), 1) or "I")
    if parcella.totale_anticipazioni > 0:
        dr_art15 = _el(dbs, "DatiRiepilogo")
        _el(dr_art15, "AliquotaIVA", "0.00")
        _el(dr_art15, "Natura", "N1")
        _el(dr_art15, "ImponibileImporto", f"{parcella.totale_anticipazioni:.2f}")
        _el(dr_art15, "Imposta", "0.00")
        _el(dr_art15, "RiferimentoNormativo", "Anticipazioni escluse ex art. 15 DPR 633/1972")

    dp = _el(body, "DatiPagamento")
    _el(dp, "CondizioniPagamento", "TP02")
    ddp = _el(dp, "DettaglioPagamento")
    codice_mp = modalita_pagamento_codice or _METODO_MAP.get(modalita_pagamento_label or parcella.metodo_pagamento or "", MP_BONIFICO)
    _el(ddp, "ModalitaPagamento", codice_mp)
    if _clean(payment_snapshot.get("beneficiario")):
        _el(ddp, "Beneficiario", _clean(payment_snapshot.get("beneficiario"), 200))
    if _clean(payment_snapshot.get("istituto_finanziario")):
        _el(ddp, "IstitutoFinanziario", _clean(payment_snapshot.get("istituto_finanziario"), 80))
    if _clean(payment_snapshot.get("iban")):
        _el(ddp, "IBAN", _clean(payment_snapshot.get("iban"), 34))
    if _clean(payment_snapshot.get("bic_swift")):
        _el(ddp, "BIC", _clean(payment_snapshot.get("bic_swift"), 11))
    data_scadenza_pagamento = _clean(payment_snapshot.get("data_decorrenza") or parcella.data_scadenza, 10)
    if data_scadenza_pagamento:
        _el(ddp, "DataScadenzaPagamento", data_scadenza_pagamento)
    giorni_termini = _digits(payment_snapshot.get("giorni_termini"), 3)
    if giorni_termini:
        _el(ddp, "GiorniTerminiPagamento", giorni_termini)
    _el(ddp, "ImportoPagamento", f"{importo_pagamento:.2f}")

    return etree.tostring(root, pretty_print=True,
                          xml_declaration=True, encoding="UTF-8",
                          standalone=True)


def nome_file_fattura_pa(
    studio_piva: str,
    progressivo: str,
) -> str:
    """
    Genera il nome file conforme alle specifiche SDI.
    Formato: IT{PIVA}_{PROGRESSIVO}.xml
    Esempio: IT01234567890_00001.xml
    """
    codice = (studio_piva or "00000000000")[:11]
    prog   = progressivo.replace("/", "").replace("-", "")[:5].zfill(5)
    return f"IT{codice}_{prog}.xml"


# ---------------------------------------------------------------- helpers

def _split_indirizzo(parent: etree._Element, indirizzo: str, *, nazione: str = "IT") -> None:
    """
    Parsa un indirizzo libero e popola i campi Sede FatturaPA.
    Formato atteso: "Via Roma 1, 20100 Milano (MI)"
    """
    if not indirizzo:
        _el(parent, "Indirizzo", "Via (non specificata)")
        _el(parent, "CAP", "00000")
        _el(parent, "Comune", "Non specificato")
        _el(parent, "Nazione", nazione or "IT")
        return

    parti = [p.strip() for p in indirizzo.split(",")]
    via = parti[0] if parti else indirizzo
    _el(parent, "Indirizzo", via[:60])

    cap = ""
    comune = ""
    provincia = ""
    if len(parti) > 1:
        resto = parti[1].strip()
        # Cerca CAP (5 cifre)
        import re
        m_cap = re.search(r"\b(\d{5})\b", resto)
        if m_cap:
            cap = m_cap.group(1)
            resto = resto[m_cap.end():].strip()
        # Cerca provincia (XX) o (XX)
        m_prov = re.search(r"\(([A-Z]{2})\)", resto)
        if m_prov:
            provincia = m_prov.group(1)
            comune = resto[:m_prov.start()].strip()
        else:
            comune = resto

    _el(parent, "CAP",      cap or "00000")
    _el(parent, "Comune",   comune[:60] or "Non specificato")
    if provincia:
        _el(parent, "Provincia", provincia[:2])
    _el(parent, "Nazione", nazione or "IT")
