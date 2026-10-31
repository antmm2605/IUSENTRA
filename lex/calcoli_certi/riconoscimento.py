"""Quale calcolatore serve alla domanda: solo se la scelta è univoca.

Le parole chiave sono quelle del nome dello strumento più i sinonimi d'uso forense
dichiarati qui. Serve anche una richiesta di calcolo («calcola», «quanto», «a quanto
ammonta»…): una domanda su cosa dice la norma resta alla ricerca normativa.
"""
from __future__ import annotations

import re

# Sinonimi d'uso: solo dove il nome dello strumento non basta a riconoscerlo.
SINONIMI: dict[str, tuple[str, ...]] = {
    "interessi": ("interessi legali", "interessi moratori", "interessi di mora", "saggio legale", "art. 1284", "231/2002"),
    "contributo_unificato": ("contributo unificato",),
    "rivalutazione_istat": ("rivalutazione istat", "rivalutazione monetaria", "indice foi"),
    "canone_locazione": ("aggiornamento del canone", "adeguamento del canone", "aggiornamento istat del canone"),
    "usura": ("soglia di usura", "tasso soglia", "usura"),
    "prescrizione": ("prescrizione civile", "si prescrive", "prescritto"),
    "prescrizione_penale": ("prescrizione del reato", "prescrizione penale"),
    "danno_biologico": ("danno biologico", "punti di invalidita", "micropermanenti"),
    "maggior_danno": ("credito di valore", "crediti di valore", "interessi compensativi"),
    "lite_temeraria": ("lite temeraria", "responsabilita aggravata", "art. 96 c.p.c."),
    "assegno_mantenimento": ("assegno di mantenimento", "mantenimento del figlio", "mantenimento dei figli", "mantenimento del coniuge", "assegno divorzile"),
    "tfr": ("tfr", "trattamento di fine rapporto"),
    "onorari_forensi": ("compenso dell'avvocato", "parametri forensi", "dm 55/2014", "d.m. 55/2014"),
    "indennita_mediazione": ("indennita di mediazione", "spese di mediazione"),
    "successione_legittima": ("successione legittima", "quote ereditarie"),
    "imposta_registro": ("imposta di registro",),
    "pignoramento": ("pignoramento dello stipendio", "pignoramento della pensione", "quota pignorabile"),
}

_RICHIESTA_DI_CALCOLO = re.compile(
    r"\b(calcol\w*|quant[oaie]|a quanto ammont\w*|importo|ammontare|determina\w*|liquid\w*|quale (?:e|sia) (?:il|la) (?:somma|cifra|totale))\b"
)


def _norm(testo: str) -> str:
    import unicodedata

    base = unicodedata.normalize("NFKD", str(testo or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c))


def chiede_un_calcolo(testo_normalizzato: str) -> bool:
    return bool(_RICHIESTA_DI_CALCOLO.search(testo_normalizzato))


def scegli_strumento(domanda: str, titoli: dict[str, str]) -> str:
    """Identificativo dello strumento, o stringa vuota se nessuno o più d'uno corrispondono."""
    testo = _norm(domanda)
    if not chiede_un_calcolo(testo):
        return ""
    punteggi: dict[str, int] = {}
    for tool, titolo in titoli.items():
        chiavi = [_norm(titolo)] + [_norm(s) for s in SINONIMI.get(tool, ())]
        punti = max((len(chiave) for chiave in chiavi if chiave and chiave in testo), default=0)
        if punti:
            punteggi[tool] = punti
    if not punteggi:
        return ""
    migliori = sorted(punteggi.items(), key=lambda voce: voce[1], reverse=True)
    if len(migliori) > 1 and migliori[0][1] == migliori[1][1]:
        return ""  # ambiguo: decide il percorso ordinario
    return migliori[0][0]


__all__ = ["SINONIMI", "chiede_un_calcolo", "scegli_strumento"]
