"""Metadati del documento informatico per la conservazione (Linee guida AgID, Allegato 5).

Per ogni documento del fascicolo si compilano i metadati minimi del «documento informatico»
dell'Allegato 5, con i nomi dei campi dell'allegato: IdDoc (impronta SHA-256 e identificativo),
ModalitaDiFormazione, TipologiaDocumentale, DatiDiRegistrazione, Soggetti, ChiaveDescrittiva,
Allegati, Riservato, IdentificativoDelFormato, Verifica, Agg (fascicolo), NomeDelDocumento,
VersioneDelDocumento, TempoDiConservazione, Note. I valori vengono solo dai dati del fascicolo:
ciò che il software non conosce resta dichiarato come tale, non inventato.
"""

from __future__ import annotations

import hashlib
from typing import Any

from pct.conservazione.formati import formato_file

# Allegato 5: a) creazione tramite software; b) acquisizione di documento informatico per via
# telematica o su supporto informatico, o copia per immagine; c) memorizzazione di transazioni o
# moduli; d) generazione o raggruppamento automatico di dati.
MODALITA_CREAZIONE = "a"
MODALITA_ACQUISIZIONE = "b"
_FONTI_CREATE = {"TEMPLATE_ATTI_COMPILATORE", "CTU_LIQUIDAZIONE", "EDITOR", "EDITOR_PROFESSIONALE"}
_FONTI_IN_ENTRATA = {"PORTALE_TELEMATICO", "PEC", "IMPORT_ESTERNO", "PORTALE_CLIENTE"}


def impronta(contenuto: bytes) -> str:
    return hashlib.sha256(contenuto).hexdigest()


def _flusso(documento: Any) -> str:
    """E = in entrata, U = in uscita, I = interno (Allegato 5, DatiDiRegistrazione)."""

    fonte = str(getattr(documento, "fonte_documento", "") or "").upper()
    if fonte in _FONTI_IN_ENTRATA or getattr(documento, "mittente_portale", ""):
        return "E"
    if getattr(documento, "id_deposito_pct", ""):
        return "U"
    return "I"


def metadati_documento(documento: Any, fascicolo: Any, contenuto: bytes, *, produttore: str, anni_conservazione: int,
                       riservato: bool = True, tipo_produttore: str = "PG", versione_software: str = "") -> dict[str, Any]:
    nome = str(getattr(documento, "nome_originale", "") or getattr(documento, "nome", "") or "documento")
    fonte = str(getattr(documento, "fonte_documento", "") or "").upper()
    formato = formato_file(str(getattr(documento, "nome", "") or nome))
    tipo = getattr(getattr(documento, "tipo", ""), "value", getattr(documento, "tipo", "")) or "ALTRO"
    firma = bool(getattr(documento, "firmato_digitalmente", False)) or formato["estensione"] in {"p7m", "m7m"}
    data_registrazione = str(getattr(documento, "data_caricamento", "") or "")[:10]
    soggetti = [{"Ruolo": "Produttore", "TipoSoggetto": tipo_produttore if tipo_produttore in {"PF", "PG"} else "PG",
                 "Denominazione": produttore}]
    if getattr(documento, "caricato_da", ""):
        soggetti.append({"Ruolo": "Operatore", "TipoSoggetto": "PF", "Identificativo": str(documento.caricato_da)})
    if getattr(documento, "mittente_portale", ""):
        soggetti.append({"Ruolo": "Mittente", "TipoSoggetto": "PAI", "Denominazione": str(documento.mittente_portale)})
    oggetto = " — ".join(p for p in (str(tipo).replace("_", " ").capitalize(), str(getattr(fascicolo, "titolo", "") or "")) if p)
    versioni = len(getattr(documento, "versioni", []) or []) + 1
    return {
        "IdDoc": {"ImprontaCrittograficaDelDocumento": {"Impronta": impronta(contenuto), "Algoritmo": "SHA-256"},
                  "Identificativo": str(getattr(documento, "id", ""))},
        "ModalitaDiFormazione": MODALITA_CREAZIONE if fonte in _FONTI_CREATE else MODALITA_ACQUISIZIONE,
        "TipologiaDocumentale": str(getattr(documento, "tipo_atto_portale", "") or str(tipo).replace("_", " ").capitalize()),
        "DatiDiRegistrazione": {"TipologiaDiFlusso": _flusso(documento), "TipoRegistro": "Nessuno",
                                "Data": data_registrazione, "Numero": str(getattr(documento, "id", ""))},
        "Soggetti": soggetti,
        "ChiaveDescrittiva": {"Oggetto": oggetto[:500], "ParoleChiave": [t for t in (getattr(documento, "tags", []) or [])][:5]},
        "Allegati": {"NumeroAllegati": 0},
        "Riservato": "Vero" if riservato else "Falso",
        "IdentificativoDelFormato": {"Formato": formato["mime"],
                                     "ProdottoSoftware": {"Nome": "IUSENTRA", "Versione": versione_software, "Produttore": "IUSENTRA"}},
        "Verifica": {"FirmatoDigitalmente": "Vero" if firma else "Falso", "SigillatoElettronicamente": "Falso",
                     "MarcaturaTemporale": "Vero" if formato["estensione"] in {"tsd", "m7m"} else "Falso",
                     "ConformitaCopieImmagineSuSupportoInformatico": "Falso"},
        "Agg": {"TipoAggregazione": "Fascicolo", "IdAggregazione": str(getattr(fascicolo, "numero", "") or getattr(fascicolo, "id", ""))},
        "NomeDelDocumento": nome,
        "VersioneDelDocumento": str(versioni),
        "TempoDiConservazione": int(anni_conservazione),
        "Note": str(getattr(documento, "note", "") or "")[:500],
    }


__all__ = ["MODALITA_ACQUISIZIONE", "MODALITA_CREAZIONE", "impronta", "metadati_documento"]
