"""I vincoli inderogabili: ciò che nessuna regola dello studio può cambiare.

Una regola dello studio sostituisce una scelta del software; non può
sostituire la legge. Ogni vincolo dichiara la norma che lo fonda e il motivo
in italiano, che il passaggio mostra quando una regola viene rifiutata.

- ``termine_perentorio``: un termine perentorio non si elimina e la sua data
  non si sposta (art. 153 c.p.c.: i termini perentori non possono essere
  abbreviati o prorogati). Se la data letta è sbagliata, è un dato letto da
  correggere in «Letture e verifiche», non una regola.
- ``deposito_non_autonomo``: il deposito telematico è un atto del difensore
  (art. 196-quater disp. att. c.p.c.; art. 111-bis c.p.p.), firmato e inviato
  da lui; il software prepara e controlla, non deposita da solo.
- ``conferma_avvocato``: il passaggio esiste perché il software non può
  decidere da solo (es. più udienze candidate): nessuna regola lo rende
  automatico.
- un campo ``vincolato`` (fissato dalla norma o dal provvedimento) non si
  cambia con una regola dello studio.
"""

from __future__ import annotations

from dataclasses import dataclass

from .modello import Passaggio
from .regole_studio import RegolaStudio

VINCOLI = {
    "termine_perentorio": {
        "etichetta": "termine perentorio",
        "norme": ("cpc_153",),
    },
    "deposito_non_autonomo": {
        "etichetta": "deposito riservato al difensore",
        "norme": ("dispatt_196quater", "cpp_111bis"),
    },
    "conferma_avvocato": {
        "etichetta": "decisione riservata all'avvocato",
        "norme": (),
    },
}
CAMPI_DI_DEPOSITO = {"deposito", "modalita_deposito", "invio", "deposita"}
CAMPI_DATA_TERMINE = {"data", "data_termine", "scadenza"}


@dataclass(frozen=True)
class Rifiuto:
    vincolo: str
    motivo: str
    norme: tuple[str, ...]

    def come_dizionario(self) -> dict[str, object]:
        from pct.procedura_fasi.fonti import fonti

        return {"vincolo": self.vincolo, "motivo": self.motivo, "norme": fonti(self.norme)}


def _rifiuto(vincolo: str, motivo: str) -> Rifiuto:
    return Rifiuto(vincolo, motivo, tuple(VINCOLI.get(vincolo, {}).get("norme", ())))


def verifica_regola(passaggio: Passaggio, regola: RegolaStudio) -> Rifiuto | None:
    """None se la regola si può applicare al passaggio, altrimenti il rifiuto motivato."""
    vincoli = set(passaggio.vincoli)
    if regola.azione == "non_proporre" and "termine_perentorio" in vincoli:
        return _rifiuto("termine_perentorio", "Un termine perentorio non si può togliere con una regola dello studio: "
                        "i termini perentori non possono essere abbreviati o prorogati (art. 153 c.p.c.).")
    if regola.azione == "modifica_valore":
        campo = passaggio.campi.get(regola.campo)
        if "termine_perentorio" in vincoli and regola.campo in CAMPI_DATA_TERMINE:
            return _rifiuto("termine_perentorio", "La data di un termine perentorio non si sposta con una regola dello studio "
                            "(art. 153 c.p.c.). Se la data letta è sbagliata, correggila come dato letto in «Letture e verifiche».")
        if "deposito_non_autonomo" in vincoli and regola.campo in CAMPI_DI_DEPOSITO:
            return _rifiuto("deposito_non_autonomo", "Il deposito resta un atto del difensore: il software prepara e controlla, "
                            "ma non deposita da solo (art. 196-quater disp. att. c.p.c.; art. 111-bis c.p.p.).")
        if campo is not None and campo.vincolato:
            return Rifiuto("campo_vincolato", f"«{campo.etichetta}» è fissato dalla norma o dal provvedimento: "
                           f"{campo.motivo_vincolo or 'non si cambia con una regola dello studio'}.", tuple(passaggio.norme))
        if campo is None:
            return Rifiuto("campo_inesistente", f"Il passaggio non ha il campo «{regola.campo}».", ())
    if regola.azione == "non_chiedere_conferma":
        if "deposito_non_autonomo" in vincoli:
            return _rifiuto("deposito_non_autonomo", "Il deposito non può diventare automatico: è un atto del difensore, "
                            "firmato e inviato da lui (art. 196-quater disp. att. c.p.c.; art. 111-bis c.p.p.).")
        if "conferma_avvocato" in vincoli:
            return _rifiuto("conferma_avvocato", "Qui il software non ha elementi per decidere da solo: la scelta resta all'avvocato.")
    return None


__all__ = ["CAMPI_DATA_TERMINE", "CAMPI_DI_DEPOSITO", "Rifiuto", "VINCOLI", "verifica_regola"]
