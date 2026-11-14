"""Vista in italiano della sequenza notturna per la console Pianificazioni."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pct.scheduler_notturno import finestra
from pct.scheduler_notturno.registro import ESITI_ITALIANI, RegistroNotte
from pct.scheduler_notturno.sequenza import FASI, passi_in_ordine


def _riscontro_passo(passo: dict[str, Any]) -> dict[str, Any]:
    esito = passo["esito"]
    etichetta = ESITI_ITALIANI.get(esito, esito)
    messaggio = passo["messaggio"]
    avvisi = (passo.get("risultato", {}).get("totals") or {}).get("warnings")
    con_avvisi = esito == "completato" and type(avvisi) is int and avvisi > 0
    if con_avvisi:
        etichetta = "Completato con avvisi"
        dettaglio = f"{avvisi} {'avviso registrato' if avvisi == 1 else 'avvisi registrati'}. Consultare il dettaglio del job."
        messaggio = f"{messaggio} {dettaglio}".strip()
    return {**passo, "esito_italiano": etichetta, "messaggio": messaggio, "con_avvisi": con_avvisi}


def stato_sequenza_notturna(db_path: str | Path, momento: datetime | None = None) -> dict[str, Any]:
    registro = RegistroNotte(db_path)
    ora = momento or finestra.adesso()
    sera = finestra.sera_della_notte(ora)
    stato = registro.avanzamento(sera.isoformat()) or registro.ultima_notte_prima(sera.isoformat())
    passi = registro.passi(stato["sera"]) if stato else []
    durate = registro.durate_medie()
    ordine = passi_in_ordine()
    totale = len(ordine)
    fatti = int(stato["indice"]) if stato else 0
    notte_corrente = bool(stato and stato["sera"] == sera.isoformat() and finestra.in_finestra(ora))
    passo_corrente = ordine[fatti][1] if notte_corrente and not stato["conclusa"] and fatti < totale else None
    prossimo = passo_corrente.lavoro if passo_corrente else ""
    riscontri = [_riscontro_passo(p) for p in passi]
    da_verificare = any(p["esito"] in {"fallito", "rinviato", "spento"} or p["con_avvisi"] for p in riscontri)
    if not stato:
        etichetta = "Nessuna notte registrata"
    elif stato["conclusa"]:
        etichetta = "Conclusa con verifiche da fare" if da_verificare else "Conclusa"
    elif notte_corrente:
        etichetta = "In corso"
    else:
        etichetta = "Sequenza incompleta"
    return {
        "stato": etichetta,
        "prossimo": prossimo,
        "motore_prossimo": (passo_corrente.esegue or prossimo) if passo_corrente else "",
        "passo_avviato_alle": (stato or {}).get("passo_avviato_alle", "") if prossimo else "",
        "aggiornata": (stato or {}).get("aggiornata", ""),
        "inizio": finestra.inizio().strftime("%H:%M"),
        "fine": finestra.fine().strftime("%H:%M"),
        "notte": stato["sera"] if stato else "",
        "conclusa": bool(stato and stato["conclusa"]),
        "ripresa_da": (stato or {}).get("ripresa_da", ""),
        "avanzamento": f"{fatti} di {totale} passi",
        "fasi": [
            {
                "numero": fase.numero,
                "nome": fase.nome,
                "motivo": fase.motivo,
                "lavori": [p.lavoro for p in fase.passi],
                "durata_media_minuti": round(sum(durate.get(p.lavoro, 0.0) for p in fase.passi) / 60, 1),
            }
            for fase in FASI
        ],
        "passi": riscontri,
        "falliti": [p["lavoro"] for p in passi if p["esito"] == "fallito"],
        "ai_riserva": registro.esiti_ai(),
    }
