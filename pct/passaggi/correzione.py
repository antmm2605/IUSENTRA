"""Dalla correzione dell'avvocato su un passaggio alla regola dello studio.

L'avvocato sceglie che cosa cambiare e l'ambito; ufficio, giudice e fascicolo
li prende il server dal passaggio stesso (mai dal client). Prima di salvare si
controllano i vincoli inderogabili: una correzione che li urta non diventa
regola e il motivo, con la norma, torna all'avvocato.
"""

from __future__ import annotations

from .modello import Passaggio
from .regole_studio import RegolaStudio
from .vincoli import Rifiuto, verifica_regola


class CorrezioneRifiutata(ValueError):
    def __init__(self, rifiuto: Rifiuto, regola: RegolaStudio) -> None:
        super().__init__(rifiuto.motivo)
        self.rifiuto = rifiuto
        self.regola = regola


def regola_da_correzione(
    passaggio: Passaggio, *, azione: str, ambito: str, autore_id: str, autore_nome: str = "",
    campo: str = "", valore: str = "", motivo: str = "", materia: str = "",
) -> RegolaStudio:
    contesto = passaggio.contesto
    regola = RegolaStudio(
        regola_id=passaggio.regola_id, produttore=passaggio.produttore, azione=str(azione or "").strip(),
        ambito=str(ambito or "").strip(), autore_id=autore_id, autore_nome=autore_nome,
        campo=str(campo or "").strip(), valore=str(valore or "").strip(), motivo=str(motivo or "").strip(),
        fascicolo_id=contesto.fascicolo_id if ambito == "fascicolo" else "",
        ufficio=contesto.ufficio if ambito in {"ufficio", "giudice"} else "",
        giudice=contesto.giudice if ambito == "giudice" else "",
        materia=(str(materia or "").strip() or contesto.materia) if ambito == "tipo" and materia else "",
        passaggio_originale=passaggio.come_dizionario(),
    )
    regola.valida_forma()
    rifiuto = verifica_regola(passaggio, regola)
    if rifiuto is not None:
        raise CorrezioneRifiutata(rifiuto, regola)
    return regola


__all__ = ["CorrezioneRifiutata", "regola_da_correzione"]
