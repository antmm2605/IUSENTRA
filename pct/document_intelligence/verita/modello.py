"""Il modello di un'etichetta certa: documento, voce del catalogo, livello e fonte."""

from __future__ import annotations

from dataclasses import asdict, dataclass

LIVELLO_DEPOSITO = "A"  # dichiarata nel deposito telematico (Portale dei Servizi Telematici)
LIVELLO_AVVOCATO = "B"  # decisa dall'avvocato su quel documento


@dataclass(frozen=True)
class EtichettaCerta:
    fascicolo_id: str
    document_id: str
    etichetta: str
    sezione: str
    livello: str
    fonte: str
    dettaglio: str = ""
    sha256: str = ""
    negativa: bool = False  # l'avvocato ha respinto questa voce per il documento

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
