"""Scadenze di deposito adempiute: il deposito telematico consegnato nel termine (V28).

Il deposito telematico si ha per avvenuto quando viene generata la ricevuta di avvenuta consegna
(art. 16-bis, c. 7, D.L. 179/2012; oggi art. 196-sexies disp. att. c.p.c.). Se nel fascicolo c'è un
deposito consegnato entro la scadenza:

- se il deposito dichiara un tipo di atto compatibile con la scadenza (note, memoria, comparsa) ed è
  l'unico compatibile, la scadenza si chiude con la nota della ricevuta (fonte certa);
- se il tipo di atto non è dichiarato («DEPOSITO PCT»), la scadenza non si chiude: riceve l'avviso
  del deposito trovato e decide l'avvocato.

Restano escluse le scadenze che non sono depositi (udienze, notifiche, pagamenti) e i depositi
rifiutati dalla cancelleria o con errore nei controlli.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Iterable

MARCATORE_CHIUSURA = "ADEMPIUTA_CON_DEPOSITO"
MARCATORE_AVVISO = "DEPOSITO_DA_ABBINARE"
_CONSEGNATI = {"CONSEGNATO", "WARN_CONTROLLI", "CONTROLLI_SUPERATI", "ACCETTATO_CANCELLERIA"}
_TIPI_SCADENZA = {"DEPOSITO_MEMORIA", "DEPOSITO_ATTO"}
_FAMIGLIE = {
    "note": re.compile(r"\bnot[ae]\b|127[\s-]*ter|trattazione scritta", re.IGNORECASE),
    "memoria": re.compile(r"\bmemori[ae]\b|171[\s-]*ter|183", re.IGNORECASE),
    "comparsa": re.compile(r"\bcompars[ae]\b|costituzione", re.IGNORECASE),
}


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def _giorno(testo: str) -> date | None:
    testo = testo.strip()
    for formato, lunghezza in (("%Y-%m-%d", 10), ("%d/%m/%Y", 10)):
        try:
            return datetime.strptime(testo[:lunghezza], formato).date()
        except ValueError:
            continue
    return None


def famiglia(testo: str) -> str:
    trovate = [nome for nome, regola in _FAMIGLIE.items() if regola.search(testo or "")]
    return trovate[0] if len(trovate) == 1 else ""


def depositi_consegnati_entro(depositi: Iterable[Any], scadenza_il: date, dal: date | None) -> list[dict[str, Any]]:
    risultato = []
    for deposito in depositi:
        if _valore(deposito, "stato").upper() not in _CONSEGNATI:
            continue
        giorno = _giorno(_valore(deposito, "timestamp"))
        if giorno is None or giorno > scadenza_il or (dal and giorno < dal):
            continue
        risultato.append({"giorno": giorno, "tipo": _valore(deposito, "tipo_atto"), "id": _valore(deposito, "id")})
    return risultato


def abbina_depositi(scadenziario: Any, *, fascicolo_id: str, depositi: list[Any]) -> dict[str, int]:
    esito = {"chiuse": 0, "avvisate": 0}
    for voce in list(scadenziario.tutte(solo_aperte=True, id_fascicolo=fascicolo_id)):
        note = _valore(voce, "note")
        if _valore(voce, "tipo").upper() not in _TIPI_SCADENZA or MARCATORE_CHIUSURA in note or MARCATORE_AVVISO in note:
            continue
        scadenza_il = _giorno(_valore(voce, "data_scadenza"))
        if scadenza_il is None:
            continue
        # Dalla decorrenza del termine; se manca, i 180 giorni precedenti la scadenza.
        dal = _giorno(_valore(voce, "data_decorrenza")) or (scadenza_il - timedelta(days=180))
        trovati = depositi_consegnati_entro(depositi, scadenza_il, dal)
        if not trovati:
            continue
        cercata = famiglia(f"{_valore(voce, 'titolo')} {_valore(voce, 'descrizione')}")
        compatibili = [d for d in trovati if cercata and famiglia(d["tipo"]) == cercata]
        if len(compatibili) == 1:
            d = compatibili[0]
            scadenziario.completa(
                _valore(voce, "id"),
                note=(f"{MARCATORE_CHIUSURA}:{d['id']}\nDeposito «{d['tipo']}» consegnato il {d['giorno']:%d/%m/%Y}, "
                      "entro il termine (ricevuta di avvenuta consegna, art. 16-bis, c. 7, D.L. 179/2012)."),
            )
            esito["chiuse"] += 1
            continue
        elenco = ", ".join(f"{d['giorno']:%d/%m/%Y}" for d in trovati[:3])
        scadenziario.aggiorna(
            _valore(voce, "id"),
            note=f"{note}\n{MARCATORE_AVVISO}".strip(),
            descrizione=(f"Deposito consegnato in questo fascicolo il {elenco}, entro il termine: se è l'adempimento, "
                         f"chiudi la scadenza.\n{_valore(voce, 'descrizione')}").strip(),
        )
        esito["avvisate"] += 1
    return esito


__all__ = ["MARCATORE_AVVISO", "MARCATORE_CHIUSURA", "abbina_depositi", "depositi_consegnati_entro", "famiglia"]
