#!/usr/bin/env python3
"""Riesame in SOLA LETTURA dei depositi telematici con uno stato non provato da una ricevuta.

Perche' esiste: fino a questa correzione il controllo automatico delle ricevute
(pct/polling_depositi.py), quando nessuna PEC corrispondeva al deposito, usava tutte le PEC della
casella: un «AVVISO DI MANCATA CONSEGNA» di un'altra PEC diventava «Consegnato». Il 12/10/2026
alle 13:08-13:09 trenta depositi sono stati portati a CONSEGNATO cosi', senza ricevuta di
avvenuta consegna. Per l'art. 196-sexies disp. att. c.p.c. il deposito si perfeziona con la RdAC:
uno stato «Consegnato» senza RdAC del deposito non e' provato.

Cosa fa: elenca ogni deposito il cui stato richiede una ricevuta che nel deposito manca (o che
contiene solo numeri IMAP della vecchia funzione), e propone lo stato che le ricevute presenti
provano davvero. NON modifica nulla: nessun salvataggio, nessuna scrittura. La decisione resta
all'avvocato; ogni correzione va fatta poi dal software con audit.

Uso (dentro il container dell'app, con contesto dello studio):
    in_container.sh scripts/riesame_stati_depositi_senza_ricevuta.py [--solo-auto] [--json]
Uso su un file JSON di fascicoli esportato (lista di fascicoli con «id» e «depositi_pct»):
    python scripts/riesame_stati_depositi_senza_ricevuta.py --fascicoli-json export.json [--json]

Non va eseguito in automatico (nessun lavoro pianificato lo richiama).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

# Ricevuta che lo stato presuppone (D.M. 44/2011 artt. 13-14; Specifiche DGSIA 7/8/2024 art. 17).
RICEVUTA_RICHIESTA = {
    "ACCETTATO_PEC": "ricevuta_accettazione",
    "CONSEGNATO": "ricevuta_consegna",
    "CONTROLLI_SUPERATI": "ricevuta_controlli_automatici",
    "WARN_CONTROLLI": "ricevuta_controlli_automatici",
    "ERRORE_CONTROLLI": "ricevuta_controlli_automatici",
    "ACCETTATO_CANCELLERIA": "ricevuta_cancelleria",
    "RIFIUTATO_CANCELLERIA": "ricevuta_cancelleria",
}
_MARCATORE_AUTO = re.compile(r"\[AUTO (\d{2}/\d{2}/\d{4} \d{2}:\d{2})\] Stato aggiornato automaticamente: ([A-Z_]+)")

_MESSAGE_ID = re.compile(r"Message-ID\s*:\s*<?[^\s<>]+@[^\s<>]+", re.I)


def _campo(dep: Any, nome: str) -> str:
    valore = dep.get(nome, "") if isinstance(dep, dict) else getattr(dep, nome, "")
    return str(valore or "")


def ricevuta_valida(testo: str) -> bool:
    """Una ricevuta e' prova se contiene testo: i soli numeri IMAP della vecchia funzione non lo sono."""
    pulito = testo.strip()
    return bool(pulito) and not re.fullmatch(r"[\d\s,]+", pulito)


def e_prova(dep: Any) -> bool:
    """Deposito di prova senza invio, con gli stessi marcatori del software (pct/deposito_simulazione.py)."""
    from types import SimpleNamespace

    from pct.deposito_simulazione import is_simulated_deposit

    campi = ("note", "messaggio", "pec_destinatario", "registrato_da")
    return is_simulated_deposit(SimpleNamespace(**{n: _campo(dep, n) for n in campi}))


def stato_provato(dep: Any) -> tuple[str, str]:
    """(stato che le ricevute presenti provano, motivo)."""
    if e_prova(dep):
        return "PROVA_SENZA_INVIO", "deposito di prova senza invio reale: nessuna ricevuta reale puo' esistere"
    if ricevuta_valida(_campo(dep, "ricevuta_cancelleria")):
        stato = _campo(dep, "stato")
        if stato in {"ACCETTATO_CANCELLERIA", "RIFIUTATO_CANCELLERIA"}:
            return stato, "esito della cancelleria presente"
        return "DA_VERIFICARE", "esito della cancelleria presente ma da leggere"
    if ricevuta_valida(_campo(dep, "ricevuta_controlli_automatici")):
        esito = _campo(dep, "esito_controlli").upper()
        mappa = {"OK": "CONTROLLI_SUPERATI", "WARN": "WARN_CONTROLLI", "ERROR": "ERRORE_CONTROLLI", "FATAL": "ERRORE_CONTROLLI"}
        if esito in mappa:
            return mappa[esito], f"esito dei controlli automatici presente ({esito})"
        return "DA_VERIFICARE", "esito dei controlli presente senza livello"
    if ricevuta_valida(_campo(dep, "ricevuta_consegna")):
        return "CONSEGNATO", "ricevuta di avvenuta consegna presente"
    if ricevuta_valida(_campo(dep, "ricevuta_accettazione")):
        return "ACCETTATO_PEC", "ricevuta di accettazione presente, manca la RdAC"
    if not _MESSAGE_ID.search(_campo(dep, "messaggio")) and "PEC_DEPOSIT_CORRELATION" in _campo(dep, "note"):
        return "DA_VERIFICARE", (
            "registrato da una PEC «deposito da ricondurre», senza invio dello studio: verificare se e' un "
            "deposito dello studio o un evento del giudice/cancelleria"
        )
    return "INVIATO", "nessuna ricevuta nel deposito: in attesa delle ricevute collegate per Message-ID"


def riesame(fascicoli: Iterable[Any]) -> list[dict[str, Any]]:
    righe: list[dict[str, Any]] = []
    for fasc in fascicoli:
        fid = _campo(fasc, "id")
        depositi = fasc.get("depositi_pct", []) if isinstance(fasc, dict) else (getattr(fasc, "depositi_pct", None) or [])
        rg = ""
        numero, anno = _campo(fasc, "numero_rg"), _campo(fasc, "anno_rg")
        if numero and anno and anno != "0":
            rg = f"{numero}/{anno}"
        for dep in depositi or []:
            stato = _campo(dep, "stato").upper()
            campo = RICEVUTA_RICHIESTA.get(stato)
            if not campo or (ricevuta_valida(_campo(dep, campo)) and not e_prova(dep)):
                continue
            proposto, motivo = stato_provato(dep)
            if proposto == stato:
                continue
            auto = _MARCATORE_AUTO.findall(_campo(dep, "note"))
            righe.append({
                "fascicolo": fid,
                "rg": rg,
                "deposito": _campo(dep, "id"),
                "tipo_atto": _campo(dep, "tipo_atto"),
                "inviato_il": _campo(dep, "timestamp"),
                "stato_attuale": stato,
                "ricevuta_mancante": campo,
                "aggiornamento_automatico": auto[-1][0] if auto else "",
                "stato_provato": proposto,
                "motivo": motivo,
            })
    return righe


def _carica_da_json(percorso: str) -> list[Any]:
    dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    if isinstance(dati, dict):
        dati = dati.get("fascicoli") or list(dati.values())
    return list(dati)


def _carica_da_studio() -> list[Any]:
    from contesto_studio import studio  # strumento di sola lettura nel container (in_container.sh)

    with studio() as s:
        gestore = s.fascicoli
        elenco = gestore.tutti() if hasattr(gestore, "tutti") else list(getattr(gestore, "_fascicoli", {}).values())
        return list(elenco)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Riesame in sola lettura degli stati dei depositi senza ricevuta.")
    parser.add_argument("--fascicoli-json", help="file JSON dei fascicoli (altrimenti contesto dello studio)")
    parser.add_argument("--solo-auto", action="store_true", help="solo i depositi aggiornati dal controllo automatico")
    parser.add_argument("--json", action="store_true", help="stampa in JSON")
    args = parser.parse_args(argv)

    fascicoli = _carica_da_json(args.fascicoli_json) if args.fascicoli_json else _carica_da_studio()
    righe = riesame(fascicoli)
    if args.solo_auto:
        righe = [r for r in righe if r["aggiornamento_automatico"]]
    if args.json:
        print(json.dumps(righe, ensure_ascii=False, indent=2))
    else:
        print("RIESAME IN SOLA LETTURA - nessun dato modificato. Decisione dell'avvocato.")
        for r in righe:
            print(
                f"{r['fascicolo']} RG {r['rg'] or '-'} dep. {r['deposito']} ({r['tipo_atto']}, {r['inviato_il'][:10]}): "
                f"{r['stato_attuale']} -> {r['stato_provato']} | manca {r['ricevuta_mancante']} | "
                f"auto {r['aggiornamento_automatico'] or '-'} | {r['motivo']}"
            )
        print(f"Totale depositi da riesaminare: {len(righe)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
