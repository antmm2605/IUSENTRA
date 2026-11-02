"""Applicare le regole dello studio ai passaggi del software.

Per ogni passaggio si consultano prima le regole dello studio che valgono per
la sua regola e per il suo contesto; per ogni «casella» (lo stato del
passaggio, o un campo) vince la regola più specifica. La regola si applica
solo se non urta un vincolo inderogabile (``vincoli.verifica_regola``):
altrimenti il passaggio resta quello del software e mostra il rifiuto con la
norma. Il valore del software resta sempre visibile accanto alla correzione.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .modello import STATO_ESCLUSO, Passaggio, livello_controllo
from .regole_studio import RegolaStudio
from .vincoli import verifica_regola


@dataclass(frozen=True)
class Applicazione:
    """Che cosa è successo a una regola su un passaggio: per il registro di audit."""

    regola_studio_id: str
    chiave_passaggio: str
    fascicolo_id: str
    esito: str  # "applicata" | "rifiutata"
    motivo: str = ""


def _scelte(passaggio: Passaggio, regole: Iterable[RegolaStudio]) -> list[RegolaStudio]:
    candidate = [regola for regola in regole if regola.vale_per(passaggio.regola_id, passaggio.contesto)]
    migliori: dict[str, RegolaStudio] = {}
    for regola in candidate:
        attuale = migliori.get(regola.casella())
        if attuale is None or regola.ordine_preferenza() > attuale.ordine_preferenza():
            migliori[regola.casella()] = regola
    return sorted(migliori.values(), key=lambda regola: regola.casella())


def _riferimento(regola: RegolaStudio) -> dict[str, object]:
    return {"id": regola.id, "etichetta": regola.etichetta(), "descrizione": regola.descrizione(),
            "ambito": regola.ambito, "autore": regola.autore_nome or regola.autore_id, "motivo": regola.motivo}


def applica_a_passaggio(passaggio: Passaggio, regole: Iterable[RegolaStudio]) -> tuple[Passaggio, list[Applicazione]]:
    risultato = passaggio.con(stato_software=passaggio.stato_software or passaggio.stato)
    applicazioni: list[Applicazione] = []
    applicate: list[dict[str, object]] = list(risultato.regole_applicate)
    rifiutate: list[dict[str, object]] = list(risultato.regole_rifiutate)
    for regola in _scelte(passaggio, regole):
        rifiuto = verifica_regola(risultato, regola)
        if rifiuto is not None:
            rifiutate.append({**_riferimento(regola), "rifiuto": rifiuto.come_dizionario()})
            applicazioni.append(Applicazione(regola.id, passaggio.chiave, passaggio.contesto.fascicolo_id, "rifiutata", rifiuto.motivo))
            continue
        if regola.azione == "modifica_valore":
            campo = risultato.campi[regola.campo]
            campi = dict(risultato.campi)
            campi[regola.campo] = campo.__class__(
                etichetta=campo.etichetta, valore=regola.valore, vincolato=campo.vincolato, motivo_vincolo=campo.motivo_vincolo,
                valore_software=campo.valore_software or campo.valore, regola_studio_id=regola.id,
            )
            # Il titolo dice il valore in vigore: quello dello studio, non più quello del software.
            titolo = risultato.titolo.replace(campo.valore, regola.valore) if campo.valore and campo.valore in risultato.titolo else risultato.titolo
            risultato = risultato.con(campi=campi, titolo=titolo)
        elif regola.azione == "non_proporre":
            risultato = risultato.con(stato=STATO_ESCLUSO)
        elif regola.azione == "chiedi_sempre":
            if livello_controllo("da_chiedere") > livello_controllo(risultato.stato):
                risultato = risultato.con(stato="da_chiedere")
        elif regola.azione == "non_chiedere_conferma":
            if risultato.stato in {"da_confermare", "da_chiedere"}:
                risultato = risultato.con(stato="proposto")
        applicate.append(_riferimento(regola))
        applicazioni.append(Applicazione(regola.id, passaggio.chiave, passaggio.contesto.fascicolo_id, "applicata"))
    return risultato.con(regole_applicate=tuple(applicate), regole_rifiutate=tuple(rifiutate)), applicazioni


def applica_regole(passaggi: Iterable[Passaggio], regole: Iterable[RegolaStudio]) -> tuple[list[Passaggio], list[Applicazione]]:
    regole = list(regole)
    corretti: list[Passaggio] = []
    applicazioni: list[Applicazione] = []
    for passaggio in passaggi:
        nuovo, eventi = applica_a_passaggio(passaggio, regole)
        corretti.append(nuovo)
        applicazioni.extend(eventi)
    return corretti, applicazioni


__all__ = ["Applicazione", "applica_a_passaggio", "applica_regole"]
