"""L'esito di una sentenza letto dal dispositivo, come fatti dell'archivio delle letture.

Il dispositivo (dopo «P.Q.M.») dice che cosa ha deciso il giudice e come ha regolato le spese (art. 132, n. 5, c.p.c.;
artt. 91, 92 e 93 c.p.c.). Il motore documenti lo registra una volta, in sfondo: chi deve sapere l'esito (Lettura del
fascicolo, Guida pratica) consulta l'archivio e non rilegge la sentenza. I fatti sono della categoria «evento»
(campi «esito_sentenza» e «spese_sentenza»), già ammessa dallo schema dell'archivio in SQLite e PostgreSQL.
L'esito è neutro rispetto alle parti: se è favorevole al cliente lo decide la Lettura con il ruolo del cliente.
"""

from __future__ import annotations

import re

from pct.percorso_pratica.esito import esito_sentenza
from pct.registro_letture.fatti_repository import Fatto

VERSIONE_ESTRAZIONE_ESITO = "2026.11.08.esito-dispositivo.v3-estinzione"
_SENTENZA = re.compile(r"\bS\s?E\s?N\s?T\s?E\s?N\s?Z\s?A\b", re.IGNORECASE)


_ESTINZIONE = re.compile(r"\bdichiara\s+(?:l['’]\s?)?estinzione\b|\bdichiara\s+estinto\s+il\s+(?:processo|giudizio)\b", re.IGNORECASE)
_CANCELLAZIONE = re.compile(r"\bcancellazione\s+della\s+causa\s+dal\s+ruolo\b|\bcancellata\s+dal\s+ruolo\b", re.IGNORECASE)


def estrai_estinzione(testo: str, *, origine: str) -> list[Fatto]:
    """L'ordinanza che dichiara estinto il processo (artt. 181, 307 e 309 c.p.c.), letta dal suo dispositivo.

    Collaudo 08/11/2026 (RG 771/2025 Palmi): l'ordinanza dopo la mancata deposizione delle note «ordina la
    cancellazione della causa dal ruolo e dichiara l'estinzione del processo», ma la Lettura restava in trattazione.
    """
    from pct.percorso_pratica.esito import dispositivo

    disp = dispositivo(str(testo or ""))
    if not disp or not _ESTINZIONE.search(disp):
        return []
    cancellazione = bool(_CANCELLAZIONE.search(disp))
    return [Fatto(
        categoria="evento", campo="estinzione_processo", valore="cancellazione_e_estinzione" if cancellazione else "estinzione",
        valore_letto=disp[:200], etichetta="Processo estinto", contesto=disp[:600],
        posizione=max(0, str(testo).rfind(disp[:40])), origine=origine, verifica="verificata", confidenza=0.9,
        prove=[{"codice": "dispositivo", "esito": "ok", "dettaglio": "estinzione dichiarata nel dispositivo (artt. 307, 309 c.p.c.)"}],
    )]


def estrai_esito(testo: str, *, origine: str) -> list[Fatto]:
    """Esito e spese della sentenza, se il testo è una sentenza con un dispositivo riconoscibile; per un altro
    provvedimento, l'estinzione del processo che dichiara."""
    testo = str(testo or "")
    if not _SENTENZA.search(testo[:4000]):
        return estrai_estinzione(testo, origine=origine)
    esito = esito_sentenza(testo)
    if esito["esito"] == "non_riconosciuto" or not esito["dispositivo"]:
        return []
    posizione = max(0, testo.rfind(esito["dispositivo"][:40]))
    spese = esito["spese"]
    fatti = [Fatto(
        categoria="evento", campo="esito_sentenza", valore=esito["esito"], valore_letto=esito["etichetta"],
        etichetta=esito["etichetta"], contesto=esito["dispositivo"][:600], posizione=posizione, origine=origine,
        verifica="verificata", confidenza=0.9,
        prove=[{"codice": "dispositivo", "esito": "ok", "dettaglio": "esito letto dopo «P.Q.M.» (art. 132, n. 5, c.p.c.)"}],
    )]
    if spese["regolazione"] != "non_indicata":
        valore = spese["regolazione"] + (f";importo={spese['importo']}" if spese["importo"] else "") + (";distrazione" if spese["distrazione"] else "")
        fatti.append(Fatto(
            categoria="evento", campo="spese_sentenza", valore=valore, valore_letto=spese["frase"][:200],
            etichetta="Spese: " + spese["regolazione"].replace("_", " ") + (f" € {spese['importo']}" if spese["importo"] else ""),
            contesto=spese["frase"][:400], posizione=posizione, origine=origine, verifica="verificata", confidenza=0.85,
            prove=[{"codice": "dispositivo", "esito": "ok" if spese["importo"] or spese["regolazione"] != "condanna" else "attenzione",
                    "dettaglio": "importo letto" if spese["importo"] else "importo non leggibile: verificare sul dispositivo"}],
        ))
    return fatti


__all__ = ["VERSIONE_ESTRAZIONE_ESITO", "estrai_esito", "estrai_estinzione"]
