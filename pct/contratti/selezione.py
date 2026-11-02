"""Selezione di variante, controlli e scheda in base ai fatti raccolti.

Base normativa: artt. 1325, 1350 e 2657 c.c. per forma e trascrizione; i
controlli specifici citano la propria norma nel catalogo. Il motore non
decide al posto dell'avvocato: ogni domanda senza risposta e ogni esito
``valutazione_avvocato`` restano visibili come punti aperti.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pct.contratti.catalogo import clausole_della_famiglia, controlli_comuni, domande_comuni, famiglia, libreria_clausole, regole_comuni

_FORME_PUBBLICO_UFFICIALE = {"scrittura_autenticata", "atto_pubblico"}


def _titoli_clausole(chiavi) -> list[str]:
    """Titoli italiani delle clausole per la scheda (la chiave tecnica resta solo se manca il titolo)."""
    libreria = libreria_clausole().get("clausole", {})
    return [str((libreria.get(chiave) or {}).get("titolo") or chiave) for chiave in chiavi]


def _soddisfa(quando: dict, fatti: dict) -> bool | None:
    """True/False se decidibile; None se manca un fatto necessario."""
    for chiave, atteso in quando.items():
        if chiave not in fatti or fatti[chiave] in (None, ""):
            return None
        valore = fatti[chiave]
        if isinstance(atteso, dict):
            try:
                numero = float(valore)
            except (TypeError, ValueError):
                return None
            if "maggiore_di" in atteso and not numero > float(atteso["maggiore_di"]):
                return False
            if "minore_di" in atteso and not numero < float(atteso["minore_di"]):
                return False
        elif isinstance(atteso, list):
            if valore not in atteso:
                return False
        elif valore != atteso:
            return False
    return True


def _forma(contratto, variante) -> dict:
    forma = variante.forma if variante else contratto.forma
    return {
        "forma": forma,
        "richiede_pubblico_ufficiale": forma in _FORME_PUBBLICO_UFFICIALE,
        "nota": (
            "Lo studio redige e negozia il testo; la stipulazione richiede notaio o pubblico ufficiale."
            if forma in _FORME_PUBBLICO_UFFICIALE else ""
        ),
    }


def valuta(contratto_id: str, fatti: dict | None = None, oggi: date | None = None) -> dict:
    """Restituisce variante selezionata, esiti dei controlli e scheda di controllo."""
    fatti = dict(fatti or {})
    contratto = famiglia(contratto_id)
    oggi = oggi or datetime.now(ZoneInfo("Europe/Rome")).date()

    varianti = [v for v in contratto.varianti if _soddisfa(v.quando, fatti) is True]
    variante = varianti[0] if len(varianti) == 1 else None

    esiti, sospesi = [], []
    for controllo in (*contratto.controlli, *controlli_comuni()):
        stato = _soddisfa(controllo.quando, fatti)
        voce = {"id": controllo.id, "esito": controllo.esito,
                "messaggio": controllo.messaggio, "norma": controllo.norma}
        if stato is True:
            esiti.append(voce)
        elif stato is None:
            sospesi.append(voce)

    domande_aperte = [d.id for d in (*contratto.domande, *domande_comuni()) if d.id not in fatti]
    punti_avvocato = [e for e in esiti if e["esito"] == "valutazione_avvocato"]
    if contratto.varianti and variante is None:
        punti_avvocato.append({"id": "variante", "esito": "valutazione_avvocato", "norma": "",
                               "messaggio": "Variante non determinabile dai fatti raccolti: scelta dell'avvocato."})
    if contratto.qualificazione in ("atipico", "misto"):
        punti_avvocato.append({"id": "qualificazione", "esito": "valutazione_avvocato", "norma": "art. 1322 c.c.",
                               "messaggio": "Contratto atipico o misto: verificare meritevolezza e qualificazione concreta."})

    regole = regole_comuni()
    novita = [n for n in regole["novita_2026"] if contratto.area in n["aree"]]
    forma = _forma(contratto, variante)
    riferimenti = list(contratto.riferimenti) + (list(variante.riferimenti) if variante else [])

    return {
        "contratto": {"id": contratto.id, "nome": contratto.nome, "area": contratto.area},
        "variante": ({"id": variante.id, "nome": variante.nome} if variante else None),
        "varianti_compatibili": [v.id for v in varianti],
        "bloccanti": [e for e in esiti if e["esito"] == "blocco"],
        "punti_avvocato": punti_avvocato,
        "adempimenti": [e for e in esiti if e["esito"] == "adempimento"],
        "avvisi": [e for e in esiti if e["esito"] == "avviso"],
        "controlli_sospesi": sospesi,
        "domande_aperte": domande_aperte,
        "forma": forma,
        "novita": novita,
        "scheda": {
            "funzione": fatti.get("funzione", ""),
            "qualificazione": contratto.qualificazione,
            "parti": fatti.get("parti", ""),
            "normativa": riferimenti,
            "forma": forma["forma"],
            "contenuti_obbligatori": [e["messaggio"] for e in esiti if e["esito"] == "blocco"],
            "clausole_negoziabili": _titoli_clausole(clausole_della_famiglia(contratto)),
            "documentazione": fatti.get("documentazione", ""),
            "adempimenti": [e["messaggio"] for e in esiti if e["esito"] == "adempimento"],
            "esecuzione": fatti.get("esecuzione", ""),
            "controllo_professionale": [p["messaggio"] for p in punti_avvocato],
            "versione": {"verifica_normativa": oggi.isoformat(), "stato": "da_verificare_su_fonte_ufficiale"},
        },
        "pronto_per_redazione": not domande_aperte and not sospesi
            and not any(e["esito"] == "blocco" for e in esiti),
    }
