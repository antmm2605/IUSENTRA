"""Le «regole dello studio»: le correzioni dell'avvocato, memorizzate e riapplicate ai casi simili.

Una regola dello studio è una sostituzione deterministica di una scelta del
software, non un addestramento: nessun modello impara dalle correzioni (come
per le decisioni del catalogo, che restano solo insieme di misura). La regola
dice che cosa cambia (``azione``, ``campo``, ``valore``), per quale regola del
software (``regola_id``) e dove vale (``ambito``):

- ``fascicolo``: solo questa pratica;
- ``giudice``: questo giudice di questo ufficio;
- ``ufficio``: questo ufficio giudiziario;
- ``tipo``: tutti i casi in cui la regola del software scatta (eventualmente
  solo per la materia indicata).

Vince la regola più specifica; a pari specificità, la più recente; fra azioni
sullo stato del passaggio, a pari specificità prevale quella che lascia più
controllo all'avvocato.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .modello import Contesto

AMBITI = {
    "fascicolo": "solo questo fascicolo",
    "giudice": "questo giudice",
    "ufficio": "questo ufficio",
    "tipo": "tutti i casi di questo tipo",
}
SPECIFICITA = {"fascicolo": 4, "giudice": 3, "ufficio": 2, "tipo": 1}
AZIONI = {
    "modifica_valore": "usa un altro valore",
    "non_proporre": "non proporre più",
    "chiedi_sempre": "chiedi sempre all'avvocato",
    "non_chiedere_conferma": "proponi senza chiedere conferma",
}
# Le azioni sullo stato del passaggio si contendono la stessa «casella».
AZIONI_STATO = ("non_proporre", "chiedi_sempre", "non_chiedere_conferma")
# A pari specificità: più controllo dell'avvocato vince.
_PRIORITA_STATO = {"chiedi_sempre": 3, "non_proporre": 2, "non_chiedere_conferma": 1}


_TITOLI = {"dott", "dottssa", "ssa", "dr", "dssa", "giudice", "g", "i", "gi", "cons", "consigliere", "pres", "presidente"}


def normalizza(testo: Any) -> str:
    """Ufficio e giudice confrontati senza maiuscole, accenti, titoli e punteggiatura."""
    grezzo = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode("ascii").lower()
    parole = re.sub(r"[^a-z0-9]+", " ", grezzo).split()
    return " ".join(parola for parola in parole if parola not in _TITOLI)


@dataclass
class RegolaStudio:
    regola_id: str
    azione: str
    ambito: str
    autore_id: str
    autore_nome: str = ""
    campo: str = ""
    valore: str = ""
    fascicolo_id: str = ""
    ufficio: str = ""
    giudice: str = ""
    materia: str = ""
    motivo: str = ""
    produttore: str = ""
    attiva: bool = True
    id: str = ""
    creata_il: str = ""
    aggiornata_il: str = ""
    passaggio_originale: dict[str, Any] = field(default_factory=dict)

    def valida_forma(self) -> None:
        if self.azione not in AZIONI:
            raise ValueError("Azione della regola non riconosciuta.")
        if self.ambito not in AMBITI:
            raise ValueError("Ambito della regola non riconosciuto.")
        if not self.regola_id:
            raise ValueError("La regola dello studio deve indicare quale regola del software corregge.")
        if self.azione == "modifica_valore" and (not self.campo or not str(self.valore).strip()):
            raise ValueError("Indica il campo da correggere e il valore giusto.")
        if self.ambito == "fascicolo" and not self.fascicolo_id:
            raise ValueError("Manca il fascicolo a cui limitare la regola.")
        if self.ambito in {"ufficio", "giudice"} and not normalizza(self.ufficio):
            raise ValueError("L'ufficio giudiziario di questo fascicolo non è noto: scegli un altro ambito.")
        if self.ambito == "giudice" and not normalizza(self.giudice):
            raise ValueError("Il giudice di questo fascicolo non è noto: scegli un altro ambito.")

    def vale_per(self, regola_id: str, contesto: Contesto) -> bool:
        if not self.attiva or self.regola_id != regola_id:
            return False
        if self.ambito == "fascicolo":
            return self.fascicolo_id == contesto.fascicolo_id
        if self.ambito == "giudice":
            return normalizza(self.ufficio) == normalizza(contesto.ufficio) and normalizza(self.giudice) == normalizza(contesto.giudice) != ""
        if self.ambito == "ufficio":
            return normalizza(self.ufficio) == normalizza(contesto.ufficio) != ""
        if self.materia:
            return normalizza(self.materia) == normalizza(contesto.materia)
        return True

    def casella(self) -> str:
        return "__stato__" if self.azione in AZIONI_STATO else f"campo:{self.campo}"

    def ordine_preferenza(self) -> tuple[int, int, str]:
        return (SPECIFICITA.get(self.ambito, 0), _PRIORITA_STATO.get(self.azione, 0), self.aggiornata_il or self.creata_il)

    def etichetta(self) -> str:
        """«regola dello studio del gg/mm/aaaa», come la vede l'avvocato accanto alla regola del software."""
        giorno = str(self.creata_il or "")[:10]
        if re.match(r"\d{4}-\d{2}-\d{2}$", giorno):
            anno, mese, di = giorno.split("-")
            return f"regola dello studio del {di}/{mese}/{anno}"
        return "regola dello studio"

    def descrizione(self) -> str:
        cosa = AZIONI.get(self.azione, self.azione)
        if self.azione == "modifica_valore":
            cosa = f"{self.campo} = {self.valore}"
        dove = AMBITI.get(self.ambito, self.ambito)
        if self.ambito in {"ufficio", "giudice"}:
            dove += f" ({self.ufficio}{' · ' + self.giudice if self.ambito == 'giudice' else ''})"
        if self.ambito == "tipo" and self.materia:
            dove += f" (materia {self.materia})"
        return f"{cosa} — {dove}"

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "id": self.id, "regolaId": self.regola_id, "produttore": self.produttore, "azione": self.azione,
            "azioneEtichetta": AZIONI.get(self.azione, self.azione), "campo": self.campo, "valore": self.valore,
            "ambito": self.ambito, "ambitoEtichetta": AMBITI.get(self.ambito, self.ambito),
            "fascicoloId": self.fascicolo_id, "ufficio": self.ufficio, "giudice": self.giudice, "materia": self.materia,
            "motivo": self.motivo, "autoreId": self.autore_id, "autoreNome": self.autore_nome, "attiva": self.attiva,
            "creataIl": self.creata_il, "aggiornataIl": self.aggiornata_il, "etichetta": self.etichetta(),
            "descrizione": self.descrizione(),
            "passaggioOriginale": {k: self.passaggio_originale.get(k) for k in ("titolo", "produttore", "regola", "campi", "statoSoftware")},
        }


__all__ = ["AMBITI", "AZIONI", "AZIONI_STATO", "RegolaStudio", "SPECIFICITA", "normalizza"]
