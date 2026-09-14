"""I depositi telematici, letti fase per fase.

Un deposito PCT attraversa fasi precise (D.M. 44/2011, artt. 13-16; Specifiche
tecniche DGSIA): invio, ricevuta di accettazione PEC, ricevuta di consegna,
esito dei controlli automatici, accettazione o rifiuto della cancelleria. Il
deposito è perfezionato solo con l'accettazione della cancelleria: prima di
quel momento l'atto non è nel fascicolo d'ufficio, e l'avvocato deve saperlo.
"""

from __future__ import annotations

from typing import Any

from ._testo import data_it, dataora_it, pulisci

FASI = {
    "INVIATO": ("inviato", "in attesa della ricevuta di accettazione PEC", False),
    "ACCETTATO_PEC": ("accettato dal gestore PEC", "in attesa della ricevuta di consegna", False),
    "CONSEGNATO": ("consegnato all'ufficio", "in attesa dell'esito dei controlli automatici", False),
    "WARN_CONTROLLI": ("controlli automatici superati con avvisi", "in attesa dell'accettazione della cancelleria", False),
    "ERRORE_CONTROLLI": ("controlli automatici con errore", "il deposito non è stato accettato: va corretto e ripetuto", False),
    "ACCETTATO_CANCELLERIA": ("accettato dalla cancelleria", "deposito perfezionato", True),
    "RIFIUTATO_CANCELLERIA": ("rifiutato dalla cancelleria", "il deposito va ripetuto tenendo conto del motivo del rifiuto", False),
}


def leggi_deposito(deposito: dict[str, Any]) -> dict[str, Any]:
    stato = pulisci(deposito.get("stato")).upper() or "INVIATO"
    fase, attesa, perfezionato = FASI.get(stato, (stato.lower().replace("_", " "), "", False))
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
        "atto": pulisci(deposito.get("titolo") or deposito.get("nome_atto_principale") or deposito.get("tipo_atto")) or "deposito",
        "tipo_atto": pulisci(deposito.get("tipo_atto")),
        "data": data_it(deposito.get("timestamp")),
        "data_ora": dataora_it(deposito.get("timestamp")),
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
    }


def depositi(elenco: list[dict[str, Any]]) -> dict[str, Any]:
    letti = [leggi_deposito(voce) for voce in elenco]
    letti.sort(key=lambda voce: pulisci(voce["data_ora"]) or "", reverse=False)
    perfezionati = [voce for voce in letti if voce["perfezionato"]]
    in_corso = [voce for voce in letti if not voce["perfezionato"] and voce["stato"] not in {"ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA"}]
    falliti = [voce for voce in letti if voce["stato"] in {"ERRORE_CONTROLLI", "RIFIUTATO_CANCELLERIA"}]
    return {
        "tutti": letti,
        "totale": len(letti),
        "perfezionati": perfezionati,
        "in_corso": in_corso,
        "falliti": falliti,
        "ultimo": letti[-1] if letti else None,
    }


__all__ = ["FASI", "depositi", "leggi_deposito"]
