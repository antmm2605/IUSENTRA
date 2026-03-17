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
import uuid
from datetime import date
from typing import Optional, TYPE_CHECKING

from lxml import etree

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
    e = etree.SubElement(parent, tag)
    if text:
        e.text = str(text)
    return e


def _progressivo(parcella_numero: str) -> str:
    """Deriva il ProgressivoInvio dal numero parcella (es. '2025/001' → '2025001')."""
    return parcella_numero.replace("/", "").replace("-", "")


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
    # Radice
    root = etree.Element("p:FatturaElettronica", nsmap={"p": _NS})
    root.set("versione", "FPR12")

    # ---------------------------------------------------------------- HEADER
    header = _el(root, "FatturaElettronicaHeader")

    # DatiTrasmissione
    dt = _el(header, "DatiTrasmissione")
    id_tx = _el(dt, "IdTrasmittente")
    _el(id_tx, "IdPaese", "IT")
    _el(id_tx, "IdCodice", (studio_piva or studio_cf)[:16])
    _el(dt, "ProgressivoInvio", _progressivo(parcella.numero))
    _el(dt, "FormatoTrasmissione", "FPR12")
    _el(dt, "CodiceDestinatario", codice_destinatario.upper().ljust(7, "0")[:7])
    if pec_destinatario or (cliente and getattr(cliente, "recapiti", None)
                            and getattr(cliente.recapiti, "pec", "")):
        pec = pec_destinatario or cliente.recapiti.pec
        if pec:
            _el(dt, "PECDestinatario", pec)

    # CedentePrestatore (studio)
    cp = _el(header, "CedentePrestatore")
    da_cp = _el(cp, "DatiAnagrafici")
    if studio_piva:
        ifiva = _el(da_cp, "IdFiscaleIVA")
        _el(ifiva, "IdPaese", "IT")
        _el(ifiva, "IdCodice", studio_piva[:11])
    if studio_cf:
        _el(da_cp, "CodiceFiscale", studio_cf[:16])
    ana_cp = _el(da_cp, "Anagrafica")
    _el(ana_cp, "Denominazione", studio_nome[:80])
    _el(da_cp, "RegimeFiscale", regime_fiscale)

    # Sede cedente (parsing semplice indirizzo)
    sede_cp = _el(cp, "Sede")
    _split_indirizzo(sede_cp, studio_indirizzo)

    # CessionarioCommittente (cliente)
    cc = _el(header, "CessionarioCommittente")
    da_cc = _el(cc, "DatiAnagrafici")
    piva_cl = getattr(cliente, "partita_iva", "") if cliente else ""
    cf_cl   = getattr(cliente, "codice_fiscale", "") if cliente else ""
    if piva_cl:
        ifiva_cl = _el(da_cc, "IdFiscaleIVA")
        _el(ifiva_cl, "IdPaese", "IT")
        _el(ifiva_cl, "IdCodice", piva_cl[:11])
    if cf_cl:
        _el(da_cc, "CodiceFiscale", cf_cl[:16])
    ana_cc = _el(da_cc, "Anagrafica")
    if cliente:
        if getattr(cliente, "tipo", None) and cliente.tipo.value == "PERSONA_FISICA":
            _el(ana_cc, "Nome",    getattr(cliente, "nome", "")[:60])
            _el(ana_cc, "Cognome", getattr(cliente, "cognome", "")[:60])
        else:
            _el(ana_cc, "Denominazione", (getattr(cliente, "ragione_sociale", "")
                                          or getattr(cliente, "nome_completo", ""))[:80])
    else:
        _el(ana_cc, "Denominazione", "Cliente")

    sede_cc = _el(cc, "Sede")
    ind_cl = ""
    if cliente and getattr(cliente, "indirizzo", None):
        ind_cl = str(cliente.indirizzo)
    _split_indirizzo(sede_cc, ind_cl)

    # ---------------------------------------------------------------- BODY
    body = _el(root, "FatturaElettronicaBody")

    # DatiGenerali
    dg = _el(body, "DatiGenerali")
    dgd = _el(dg, "DatiGeneraliDocumento")
    _el(dgd, "TipoDocumento", "TD01")        # Fattura
    _el(dgd, "Divisa", "EUR")
    _el(dgd, "Data", parcella.data_emissione[:10])
    _el(dgd, "Numero", parcella.numero)

    # Cassa Forense (contributo previdenziale)
    if parcella.applica_cassa and parcella.cassa_forense > 0:
        dcp = _el(dgd, "DatiCassaPrevidenziale")
        _el(dcp, "TipoCassa", "CAF")         # Cassa Avvocati e Forense
        _el(dcp, "AlCassa", "4.00")
        _el(dcp, "ImportoContributoCassa", f"{parcella.cassa_forense:.2f}")
        _el(dcp, "ImponibileCassa", f"{parcella.imponibile:.2f}")
        _el(dcp, "AliquotaIVA",
            f"{22.00:.2f}" if parcella.applica_iva else "0.00")
        _el(dcp, "Ritenuta", "SI" if parcella.applica_ritenuta else "NO")

    # Ritenuta d'acconto
    if parcella.applica_ritenuta and parcella.ritenuta > 0:
        dr = _el(dgd, "DatiRitenuta")
        _el(dr, "TipoRitenuta", "RT01")      # persona fisica
        _el(dr, "ImportoRitenuta", f"{parcella.ritenuta:.2f}")
        _el(dr, "AliquotaRitenuta", "20.00")
        _el(dr, "CausalePagamento", "P")     # prestazione professionale

    # Bollo
    if parcella.applica_bollo and parcella.bollo > 0:
        db = _el(dgd, "DatiBollo")
        _el(db, "BolloVirtuale", "SI")
        _el(db, "ImportoBollo", f"{parcella.bollo:.2f}")

    _el(dgd, "ImportoTotaleDocumento", f"{parcella.totale:.2f}")
    if parcella.note:
        _el(dgd, "Causale", parcella.note[:200])

    # DatiBeniServizi
    dbs = _el(body, "DatiBeniServizi")
    aliquota = "22.00" if parcella.applica_iva else "0.00"
    natura   = "" if parcella.applica_iva else "N2.2"   # non soggetto IVA

    for i, voce in enumerate(parcella.voci, start=1):
        dl = _el(dbs, "DettaglioLinee")
        _el(dl, "NumeroLinea", str(i))
        _el(dl, "Descrizione", voce.descrizione[:1000])
        _el(dl, "Quantita", f"{voce.quantita:.2f}")
        _el(dl, "PrezzoUnitario", f"{voce.prezzo_unitario:.8f}")
        _el(dl, "PrezzoTotale", f"{voce.importo:.2f}")
        _el(dl, "AliquotaIVA", aliquota)
        if natura:
            _el(dl, "Natura", natura)

    # Contributo cassa forense come riga aggiuntiva
    if parcella.applica_cassa and parcella.cassa_forense > 0:
        dl_cassa = _el(dbs, "DettaglioLinee")
        _el(dl_cassa, "NumeroLinea", str(len(parcella.voci) + 1))
        _el(dl_cassa, "Descrizione", "Contributo Cassa Forense 4% (art. 11 L. 576/1980)")
        _el(dl_cassa, "Quantita", "1.00")
        _el(dl_cassa, "PrezzoUnitario", f"{parcella.cassa_forense:.8f}")
        _el(dl_cassa, "PrezzoTotale", f"{parcella.cassa_forense:.2f}")
        _el(dl_cassa, "AliquotaIVA", aliquota)
        if natura:
            _el(dl_cassa, "Natura", natura)

    # DatiRiepilogo
    dr_rie = _el(dbs, "DatiRiepilogo")
    _el(dr_rie, "AliquotaIVA", aliquota)
    if natura:
        _el(dr_rie, "Natura", natura)
        _el(dr_rie, "RiferimentoNormativo",
            "Operazione non soggetta ad IVA ex art. 1, co. 54-89, L. 190/2014")
    _el(dr_rie, "ImponibileImporto", f"{parcella.base_iva:.2f}")
    _el(dr_rie, "Imposta", f"{parcella.iva:.2f}")
    _el(dr_rie, "EsigibilitaIVA", "I")      # immediata

    # DatiPagamento
    dp = _el(body, "DatiPagamento")
    _el(dp, "CondizioniPagamento", "TP02")  # pagamento completo
    ddp = _el(dp, "DettaglioPagamento")
    codice_mp = _METODO_MAP.get(parcella.metodo_pagamento or "", MP_BONIFICO)
    _el(ddp, "ModalitaPagamento", codice_mp)
    if parcella.data_scadenza:
        _el(ddp, "DataScadenzaPagamento", parcella.data_scadenza[:10])
    _el(ddp, "ImportoPagamento", f"{parcella.totale:.2f}")

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

def _split_indirizzo(parent: etree._Element, indirizzo: str) -> None:
    """
    Parsa un indirizzo libero e popola i campi Sede FatturaPA.
    Formato atteso: "Via Roma 1, 20100 Milano (MI)"
    """
    if not indirizzo:
        _el(parent, "Indirizzo", "Via (non specificata)")
        _el(parent, "CAP", "00000")
        _el(parent, "Comune", "Non specificato")
        _el(parent, "Nazione", "IT")
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
    _el(parent, "Nazione", "IT")
