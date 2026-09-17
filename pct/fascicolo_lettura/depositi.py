"""I depositi telematici, letti fase per fase.

Un deposito telematico civile attraversa fasi precise (D.M. 44/2011, art. 13;
art. 196-sexies disp. att. c.p.c.; Specifiche tecniche DGSIA 7/8/2024, art.
17): invio, ricevuta di accettazione PEC, ricevuta di avvenuta consegna — il
momento in cui il deposito si ha per avvenuto — esito dei controlli automatici,
accettazione o rifiuto della cancelleria. Solo con l'accettazione l'atto è nel
fascicolo d'ufficio, e l'avvocato deve saperlo. Le fasi degli altri canali
(PDP, PAT, PTT) sono nelle schede di `pct/procedura_fasi/depositi.py`.
"""

from __future__ import annotations

from typing import Any
import re

from pct.procedura_fasi.depositi import canale_deposito, fase_deposito

from ._testo import data_it, dataora_it, pulisci

FASI = {
    "INVIATO": ("inviato", "in attesa della ricevuta di accettazione PEC", False),
    "ACCETTATO_PEC": ("accettato dal gestore PEC", "in attesa della ricevuta di consegna", False),
    "CONSEGNATO": ("consegnato all'ufficio", "in attesa dell'esito dei controlli automatici", False),
    "CONTROLLI_SUPERATI": ("controlli automatici superati", "in attesa dell’accettazione della cancelleria", False),
    "WARN_CONTROLLI": ("controlli automatici superati con avvisi", "in attesa dell'accettazione della cancelleria", False),
    "ERRORE_CONTROLLI": ("controlli automatici con errore", "il deposito non è stato accettato: va corretto e ripetuto", False),
    "ACCETTATO_CANCELLERIA": ("accettato dalla cancelleria", "deposito perfezionato", True),
    "RIFIUTATO_CANCELLERIA": ("rifiutato dalla cancelleria", "il deposito va ripetuto tenendo conto del motivo del rifiuto", False),
}


def titolo_atto(deposito: dict[str, Any]) -> str:
    testo = pulisci(deposito.get("titolo") or deposito.get("nome_atto_principale") or deposito.get("tipo_atto")) or "deposito"
    nome = re.match(r"^(.+?\.(?:pdf|docx?|p7m))(?:\s|$)", testo, re.I)
    return nome.group(1) if nome else testo


def leggi_deposito(deposito: dict[str, Any], canale: str = "") -> dict[str, Any]:
    stato = pulisci(deposito.get("stato")).upper() or "INVIATO"
    # Gli atti importati dal fascicolo d'ufficio (PolisWeb/PST) non sono depositi
    # dello studio in attesa di ricevute: sono atti già nel fascicolo d'ufficio.
    importato = stato.startswith("IMPORTATO")
    if importato:
        fase, attesa, perfezionato = ("acquisito dal fascicolo d'ufficio", "", True)
    else:
        fase, attesa, perfezionato = FASI.get(stato, (stato.lower().replace("_", " "), "", False))
    canale_letto = canale_deposito(deposito.get("fonte_portale") or deposito.get("servizio_portale") or canale) or "PCT_TELEMATICO"
    fase_procedurale = fase_deposito(canale_letto, stato)
    esito_controlli = pulisci(deposito.get("esito_controlli")).upper()
    ricevute = [
        etichetta
        for chiave, etichetta in (
            ("ricevuta_accettazione", "accettazione PEC"),
            ("ricevuta_consegna", "consegna PEC"),
            ("ricevuta_controlli_automatici", "esito controlli automatici"),
            ("ricevuta_cancelleria", "esito cancelleria"),
        )
        if pulisci(deposito.get(chiave))
    ]
    return {
        "id": pulisci(deposito.get("id")),
        "atto": titolo_atto(deposito),
        "tipo_atto": pulisci(deposito.get("tipo_atto")),
        "data": data_it(deposito.get("timestamp")),
        "data_ora": dataora_it(deposito.get("timestamp")),
        "data_accettazione": data_it(deposito.get("data_accettazione")),
        "stato": stato,
        "fase": fase,
        "attesa": attesa,
        "perfezionato": perfezionato,
        "esito_controlli": esito_controlli,
        "ricevute": ricevute,
        "documenti": int(deposito.get("documenti_count") or len(deposito.get("documenti_ids") or []) or 0),
        "identificativo_busta": pulisci(deposito.get("id_deposito_esterno")),
        "portale": pulisci(deposito.get("fonte_portale")),
        "messaggio": pulisci(deposito.get("messaggio"))[:200],
        "destinatario": pulisci(deposito.get("pec_destinatario")),
        "canale": canale_letto,
        "importato": importato,
        # La fase della scheda procedurale: nome, prova attesa e norme che la governano.
        "fase_procedurale": fase_procedurale.get("nome", ""),
        "prova_attesa": fase_procedurale.get("prova", ""),
        "fonti_procedurali": list(fase_procedurale.get("fonti") or []),
    }


def depositi(elenco: list[dict[str, Any]], canale: str = "") -> dict[str, Any]:
    letti = [leggi_deposito(voce, canale) for voce in sorted(elenco, key=lambda row: str(row.get("timestamp") or ""))]
    prove = [voce for voce in letti if "PROVA" in voce["stato"] or "SIMUL" in voce["stato"]]
    letti = [voce for voce in letti if voce not in prove]
    importati = [voce for voce in letti if voce["importato"]]
    perfezionati = [voce for voce in letti if voce["perfezionato"] and not voce["importato"]]
    in_corso = [voce for voce in letti if not voce["perfezionato"] and voce["stato"] not in {"ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA"}]
    falliti = [voce for voce in letti if voce["stato"] in {"ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA"}]
    return {
        "tutti": letti,
        "prove_senza_invio": prove,
        "totale": len(letti),
        "importati": importati,
        "perfezionati": perfezionati,
        "in_corso": in_corso,
        "falliti": falliti,
        "ultimo": letti[-1] if letti else None,
    }


__all__ = ["FASI", "depositi", "leggi_deposito"]
