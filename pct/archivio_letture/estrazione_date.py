"""Le date come fatti: token stretto (formulario) + ancora (contesto) + orario."""

from __future__ import annotations

from legal_ocr.formulario.date import trova_date
from pct.registro_letture.fatti_repository import Fatto

from .ancoraggio import ancora_per, brano, ora_vicina

ETICHETTE = {
    "udienza": "Udienza", "termine": "Termine", "costituzione": "Costituzione", "deposito": "Deposito", "notifica": "Notifica",
    "accettazione": "Ricevuta di accettazione", "consegna": "Ricevuta di avvenuta consegna", "comunicazione": "Comunicazione",
    "provvedimento": "Provvedimento", "data_atto": "Data dell'atto",
}
CONFIDENZA_PER_SOSTITUZIONE = 0.18


def estrai_date(testo: str, *, origine: str) -> list[Fatto]:
    """Ogni data vera e ancorata del testo diventa un fatto di categoria «data»."""
    testo = str(testo or "")
    fatti: list[Fatto] = []
    limite = 0
    trovate = trova_date(testo)
    for indice, trovata in enumerate(trovate):
        successiva = trovate[indice + 1].inizio if indice + 1 < len(trovate) else None
        ancora = ancora_per(testo, trovata.inizio, trovata.fine, limite=limite, limite_dopo=successiva)
        limite = trovata.fine
        if ancora is None:
            continue
        ora = ora_vicina(testo, trovata.fine) if ancora.campo in {"udienza", "accettazione", "consegna", "comunicazione"} else ""
        valore = trovata.data.isoformat() + (f"T{ora}" if ora else "")
        etichetta = f"{ETICHETTE.get(ancora.campo, ancora.campo)} del {trovata.data.strftime('%d/%m/%Y')}" + (f" ore {ora}" if ora else "")
        fatti.append(Fatto(
            categoria="data", campo=ancora.campo, valore=valore, valore_letto=trovata.letto, etichetta=etichetta,
            contesto=brano(testo, trovata.inizio, trovata.fine), posizione=trovata.inizio, origine=origine,
            confidenza=max(0.2, 1.0 - CONFIDENZA_PER_SOSTITUZIONE * trovata.sostituzioni),
            prove=[
                {"codice": "calendario", "esito": "ok", "dettaglio": f"{trovata.scritto} è una data del calendario"},
                {"codice": "forma", "esito": "ok" if trovata.sostituzioni <= 1 else "attenzione", "dettaglio": (f"{trovata.sostituzioni} segni corretti dal formulario" if trovata.sostituzioni else "nessuna correzione")},
                {"codice": "ancoraggio", "esito": "ok", "dettaglio": f"«{ancora.testo}» a {ancora.distanza} caratteri"},
            ],
        ))
    return fatti


__all__ = ["ETICHETTE", "estrai_date"]
