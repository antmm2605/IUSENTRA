"""Fonti ufficiali delle tabelle di liquidazione del danno biologico.

Ogni tabella caricata dal pacchetto porta con se' la propria fonte: riferimento
normativo, URL ufficiale, versione e data di consultazione. E' il requisito del
principio delle fonti certe: nessun valore di liquidazione entra nel calcolo se
non e' riconducibile a un documento pubblicato e citabile in atti.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class FonteTabella:
    """Provenienza verificabile di una tabella di liquidazione."""

    id: str
    nome: str
    riferimento_normativo: str
    url_ufficiale: str
    data_consultazione: str
    pubblicazione: str = ""
    ambito: str = ""

    @classmethod
    def da_dati(cls, dati: Mapping[str, Any]) -> "FonteTabella":
        return cls(
            id=str(dati.get("id", "")),
            nome=str(dati.get("nome", "")),
            riferimento_normativo=str(dati.get("riferimento_normativo", "")),
            url_ufficiale=str(dati.get("url_ufficiale", "")),
            data_consultazione=str(dati.get("data_consultazione", "")),
            pubblicazione=str(dati.get("pubblicazione", "")),
            ambito=str(dati.get("ambito", "")),
        )

    def come_dizionario(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "nome": self.nome,
            "riferimento_normativo": self.riferimento_normativo,
            "pubblicazione": self.pubblicazione,
            "url_ufficiale": self.url_ufficiale,
            "data_consultazione": self.data_consultazione,
            "ambito": self.ambito,
        }

    def come_sorgente(self) -> Dict[str, str]:
        """Voce per l'elenco ``sources`` esposto dai calcolatori."""
        titolo = self.riferimento_normativo or self.nome
        return {"title": titolo, "url": self.url_ufficiale}
