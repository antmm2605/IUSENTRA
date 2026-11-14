"""Le fonti del ragionamento: tutto ciò che il fascicolo sa, in dizionari semplici.

Il ragionamento non sa nulla di Flask né dei repository: riceve queste fonti (raccolte in sfondo
da `raccolta.py`, o scritte a mano nei test) e ne trae il modello della causa. Così la stessa
logica vale per la pagina, per Lex, per i pannelli precalcolati e per i casi di collaudo.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class FontiCausa:
    # id, numero_rg, anno_rg, tribunale, codice_oggetto_pst, oggetto, tipo, tipo_procedimento,
    # cliente, controparte, valore_causa, avvocato_referente
    fascicolo: dict[str, Any] = field(default_factory=dict)
    # nome, avvocati (nomi), pec (indirizzi)
    studio: dict[str, Any] = field(default_factory=dict)
    # id, nome, data_documento, natura, etichetta, testo, sha256 (natura ed etichetta dal catalogo)
    documenti: list[dict[str, Any]] = field(default_factory=list)
    # i fatti dell'archivio delle letture (Fatto.to_dict): categoria, campo, valore, contesto, verifica, oggetto_id...
    fatti: list[dict[str, Any]] = field(default_factory=list)
    # id, oggetto, data, mittente, destinatari, allegati (nomi), inviata (bool)
    pec: list[dict[str, Any]] = field(default_factory=list)
    # id, tipo_atto, stato, data, numero_rg
    depositi: list[dict[str, Any]] = field(default_factory=list)
    # id, numero, tipo (proforma/fattura), stato, totale, data, descrizione, data_pagamento, metodo, prova_incasso
    parcelle: list[dict[str, Any]] = field(default_factory=list)
    # voci del presidio economico: voce, stato, importo, origine, documento, data
    pagamenti: list[dict[str, Any]] = field(default_factory=list)
    # le scadenze e gli appuntamenti già registrati (titolo, data, stato): solo per il confronto con il modello
    scadenze: list[dict[str, Any]] = field(default_factory=list)
    oggi: date | None = None
    # Atto esatto -> consegna e identificativo della prova verificata nel registro.
    consegne_verificate: dict[str, dict[str, str]] = field(default_factory=dict)

    def impronta(self) -> str:
        """L'impronta delle fonti: se non cambia, il modello salvato resta valido."""
        dati = asdict(self)
        dati.pop("oggi", None)
        for documento in dati["documenti"]:
            testo = documento.pop("testo", "") or ""
            documento["testo_sha"] = hashlib.sha256(testo.encode("utf-8")).hexdigest()
        grezzo = json.dumps(dati, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(grezzo.encode("utf-8")).hexdigest()


__all__ = ["FontiCausa"]
