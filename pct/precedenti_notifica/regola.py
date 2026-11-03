"""Quando i precedenti dello studio bastano a proporre destinatario e domicilio.

Regole di sicurezza (richiesta dell'avvocato del 03/11/2026):

a. la regola normativa del codice (``pct.obblighi_notifica._destinatario``) prevale sempre: se i precedenti
   indicano un altro domicilio la proposta resta quella della norma e la differenza si segnala;
b. proposta automatica solo con almeno ``minimo`` precedenti concordi e consegnati (ricevuta di avvenuta
   consegna) e nessun precedente consegnato discordante negli ultimi ``finestra_giorni``;
c. l'indirizzo PEC non si copia mai dal precedente: si indica il pubblico elenco da cui prenderlo per il
   destinatario attuale (art. 3-bis, comma 1, L. 53/1994; art. 16-ter D.L. 179/2012);
d. verifica nel pubblico elenco, firma e invio restano atti dell'avvocato (art. 3-bis L. 53/1994).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from .categorie import (
    ETICHETTE_DOMICILIO,
    NON_DETERMINATO,
    REGISTRO_PER_DOMICILIO,
    compatibili,
    domicilio_normativo,
)

MINIMO_PRECEDENTI = 3
FINESTRA_DISCORDANTI_GIORNI = 730

AUTOMATICA = "proposta_dai_precedenti"
DA_VERIFICARE = "da_verificare_con_i_precedenti"
CONFLITTO = "prevale_la_norma"
NESSUNO = "nessun_precedente"

AVVERTENZA = ("La verifica dell'indirizzo nel pubblico elenco, la firma della relata e l'invio restano atti "
              "dell'avvocato (art. 3-bis L. 53/1994).")


@dataclass(frozen=True)
class Precedente:
    """Una notifica già eseguita dallo studio verso un destinatario (solo categorie e riferimenti interni)."""

    fascicolo_id: str
    prova_id: str  # id del messaggio PEC della ricevuta nel presidio
    data: str  # ISO
    tipo_atto: str
    categoria_controparte: str
    domicilio: str
    consegnata: bool


def _giorno(valore: str) -> date | None:
    try:
        return date.fromisoformat(str(valore or "")[:10])
    except ValueError:
        return None


def proposta(
    precedenti: list[Precedente] | tuple[Precedente, ...],
    *,
    tipo_atto: str,
    categoria_controparte: str,
    presso_normativo: str,
    fascicolo_id: str = "",
    oggi: date | None = None,
    minimo: int = MINIMO_PRECEDENTI,
    finestra_giorni: int = FINESTRA_DISCORDANTI_GIORNI,
) -> dict:
    """La proposta per un destinatario della tipologia (tipo di atto + categoria di controparte)."""
    oggi = oggi or date.today()
    simili = [p for p in precedenti if p.tipo_atto == tipo_atto and p.categoria_controparte == categoria_controparte
              and p.domicilio != NON_DETERMINATO and p.fascicolo_id != fascicolo_id]
    consegnati = [p for p in simili if p.consegnata]
    normativo = domicilio_normativo(presso_normativo)
    base = {"tipologia": {"tipo_atto": tipo_atto, "categoria_controparte": categoria_controparte},
            "domicilio_norma": normativo, "mancate_consegne": sum(1 for p in simili if not p.consegnata),
            "minimo": minimo, "avvertenza": AVVERTENZA}
    if not consegnati:
        return {**base, "stato": NESSUNO, "numero": 0, "precedenti": [], "fonte": ""}
    conteggio = Counter(p.domicilio for p in consegnati)
    dominante, numero = conteggio.most_common(1)[0]
    limite = oggi - timedelta(days=finestra_giorni)
    discordanti = [p for p in consegnati if p.domicilio != dominante and (_giorno(p.data) or oggi) >= limite]
    mostrati = sorted(consegnati, key=lambda p: p.data, reverse=True)[:10]
    esito = {
        **base,
        "domicilio": dominante,
        "etichetta": ETICHETTE_DOMICILIO.get(dominante, dominante),
        "registro_indirizzo": REGISTRO_PER_DOMICILIO.get(dominante, ""),
        "numero": numero,
        "discordanti": len(discordanti),
        "per_domicilio": dict(conteggio),
        "precedenti": [asdict(p) for p in mostrati],
        "fonte": f"Come nelle {numero} notifiche precedenti dello studio",
    }
    if normativo != NON_DETERMINATO and not compatibili(normativo, dominante):
        return {**esito, "stato": CONFLITTO,
                "motivo": (f"I precedenti indicano «{esito['etichetta']}», la norma «{ETICHETTE_DOMICILIO.get(normativo, normativo)}»: "
                           "prevale la norma, verifica la differenza.")}
    if numero >= minimo and not discordanti:
        return {**esito, "stato": AUTOMATICA,
                "motivo": "Indirizzo da prendere dal pubblico elenco del destinatario attuale, mai dal precedente."}
    motivo = (f"Precedenti concordi {numero} su {minimo} richiesti" if numero < minimo
              else f"{len(discordanti)} precedenti recenti con un domicilio diverso")
    return {**esito, "stato": DA_VERIFICARE, "motivo": motivo + ": proposta da verificare con i precedenti mostrati."}
