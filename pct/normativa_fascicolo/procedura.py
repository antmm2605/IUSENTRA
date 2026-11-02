"""Gruppo (a): le norme del rito, del canale di deposito e delle notifiche del fascicolo.

Legge le schede versionate di `pct.procedura_fasi` (rito per tipo e
procedimento, canale di deposito, canale di notifica): ogni adempimento vi cita
le voci del registro delle fonti, quindi ogni norma porta con sé la fase in cui
serve. Nessuna scheda, nessuna norma: il gruppo resta vuoto e lo dice.
"""

from __future__ import annotations

from typing import Any

from pct.procedura_fasi import rito_per_fascicolo, schede_per_fascicolo

from .voci import aggiungi, voce_registro

# Le notifiche in proprio (L. 53/1994) non sono il canale del difensore penale.
_RITI_SENZA_NOTIFICA_IN_PROPRIO = {"penale"}
_RITI_STRAGIUDIZIALI = {"mediazione"}


def _fonti_delle_fasi(scheda: dict[str, Any]) -> list[tuple[str, str]]:
    """Coppie (fonte, fase) nell'ordine della scheda."""
    coppie: list[tuple[str, str]] = []
    for fase in scheda.get("fasi", []):
        nome = str(fase.get("nome") or "")
        for identificativo in fase.get("fonti", []):
            coppie.append((identificativo, nome))
        for adempimento in fase.get("adempimenti", []):
            for identificativo in adempimento.get("fonti", []):
                coppie.append((identificativo, nome))
    for voce in scheda.get("tempistiche", []):
        for identificativo in voce.get("fonti", []):
            coppie.append((identificativo, ""))
    return coppie


def _da_scheda(voci: dict[str, dict[str, Any]], scheda: dict[str, Any], premessa: str) -> None:
    nome = str(scheda.get("nome") or "").strip()
    if not nome:
        return
    for identificativo, fase in _fonti_delle_fasi(scheda):
        perche = f"{premessa} {nome}" + (f", fase «{fase}»" if fase else "")
        aggiungi(voci, voce_registro(identificativo), perche)
    # Le fonti che la scheda aggiunge in coda (udienza cartolare, DGSIA vigenti).
    for riga in scheda.get("fonti", []):
        identificativo = str(riga.get("id") or "")
        if f"registro:{identificativo}" not in voci:
            aggiungi(voci, voce_registro(identificativo), f"{premessa} {nome}")


def norme_procedura(fascicolo: dict[str, Any]) -> dict[str, Any]:
    tipo = str(fascicolo.get("tipo") or "")
    procedimento = str(fascicolo.get("tipo_procedimento") or "")
    canale = str(fascicolo.get("canale_operativo") or "")
    rito = rito_per_fascicolo(tipo, procedimento)
    voci: dict[str, dict[str, Any]] = {}
    contesto: dict[str, str] = {"rito": "", "deposito": "", "ufficio": str(fascicolo.get("tribunale") or "").strip()}
    if rito or canale:
        schede = schede_per_fascicolo(tipo=tipo, tipo_procedimento=procedimento, canale_operativo=canale)
        contesto["rito"] = str((schede.get("rito") or {}).get("nome") or "")
        contesto["deposito"] = str((schede.get("deposito") or {}).get("nome") or "")
        _da_scheda(voci, schede.get("rito") or {}, "perché: rito del fascicolo —")
        # La mediazione si svolge davanti all'organismo: deposito e notifiche giudiziali solo se dichiarati.
        giudiziale = rito not in _RITI_STRAGIUDIZIALI or bool(canale)
        if giudiziale:
            _da_scheda(voci, schede.get("deposito") or {}, "perché: canale di deposito —")
        else:
            contesto["deposito"] = ""
        if giudiziale and rito not in _RITI_SENZA_NOTIFICA_IN_PROPRIO:
            for scheda in schede.get("notifiche") or []:
                _da_scheda(voci, scheda, "perché: canale di notifica —")
    vuoto = "" if voci else (
        "Il tipo di pratica non ha ancora una scheda di fasi e termini nel software: "
        "indica nel profilo del fascicolo il tipo di procedimento per vedere le norme del rito."
    )
    return {"voci": list(voci.values()), "contesto": contesto, "vuoto": vuoto}


__all__ = ["norme_procedura"]
