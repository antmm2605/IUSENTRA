"""Gli istituti processuali riconosciuti nei provvedimenti: non solo la data, ma che cosa è.

Una data letta in un decreto non basta: «termine del 10/09/2026» non dice
all'avvocato che cosa deve fare. «Deposito di note scritte ex art. 127-ter
c.p.c.» sì — e da quella qualificazione discendono gli altri termini che il
decreto impone senza scriverne la data: la notifica di ricorso e decreto
trenta giorni prima, la costituzione del resistente dieci giorni prima.

Questa qualificazione appartiene ai motori di lettura, non ai presìdi: i
presìdi la consultano nell'archivio insieme alla data, e la mostrano. Un
presidio che la ricavasse da sé rileggerebbe il testo a ogni richiesta, e due
presìdi potrebbero ricavarla in due modi diversi.

Base normativa
--------------
* **art. 127-ter c.p.c.** (introdotto dal D.Lgs. 149/2022, riforma Cartabia):
  l'udienza può essere sostituita dal deposito di note scritte; il giorno di
  scadenza del termine vale come data dell'udienza.
* **art. 127-bis c.p.c.**: udienza con collegamento audiovisivo a distanza; la
  parte può chiedere che si tenga in presenza.
* I termini derivati (trenta giorni per la notifica, dieci per la costituzione)
  non sono di legge in astratto: sono quelli che **il singolo decreto**
  impone, e si registrano solo quando il decreto li dichiara.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

#: la norma citata accanto a ogni termine che ne discende
NORMA_127_TER = "art. 127-ter c.p.c. (D.Lgs. 149/2022)"
NORMA_127_BIS = "art. 127-bis c.p.c. (D.Lgs. 149/2022)"


@dataclass(frozen=True, slots=True)
class Istituto:
    """Che cosa è una data, e che cosa comporta per l'avvocato."""

    codice: str
    campo: str
    titolo: str
    descrizione: str
    norma: str

    def etichetta(self, giorno: date) -> str:
        return f"{self.titolo} — {giorno.strftime('%d/%m/%Y')}"


NOTE_127_TER = Istituto(
    "note_127_ter", "termine",
    "Deposito note scritte ex art. 127-ter c.p.c.",
    "Il decreto sostituisce l'udienza con il deposito di note scritte. Il giorno di "
    "scadenza vale come data dell'udienza: istanze, conclusioni e allegati vanno pronti prima.",
    NORMA_127_TER,
)
NOTIFICA_RICORSO_DECRETO = Istituto(
    "notifica_ricorso_decreto", "termine",
    "Notifica di ricorso e decreto, trenta giorni prima",
    "Il decreto pone a carico del ricorrente la notifica di ricorso e decreto almeno "
    "trenta giorni prima della data fissata.",
    NORMA_127_TER,
)
COSTITUZIONE_RESISTENTE = Istituto(
    "costituzione_resistente", "costituzione",
    "Costituzione del resistente, dieci giorni prima",
    "Il decreto assegna al resistente un termine sino a dieci giorni prima della scadenza "
    "per costituirsi.",
    NORMA_127_TER,
)
UDIENZA_127_BIS = Istituto(
    "udienza_127_bis", "udienza",
    "Udienza con collegamento audiovisivo ex art. 127-bis c.p.c.",
    "Il decreto dispone la comparizione da remoto: verificare la stanza virtuale e il "
    "deposito delle note operative prima dell'udienza.",
    NORMA_127_BIS,
)
COSTITUZIONE_CONVENUTO = Istituto(
    "costituzione_convenuto", "costituzione",
    "Costituzione del convenuto, dieci giorni prima",
    "Il decreto richiama il termine di costituzione almeno dieci giorni prima dell'udienza.",
    NORMA_127_BIS,
)

ISTITUTI: tuple[Istituto, ...] = (
    NOTE_127_TER, NOTIFICA_RICORSO_DECRETO, COSTITUZIONE_RESISTENTE,
    UDIENZA_127_BIS, COSTITUZIONE_CONVENUTO,
)
ISTITUTI_PER_CODICE: dict[str, Istituto] = {voce.codice: voce for voce in ISTITUTI}

#: giorni di anticipo che il decreto può imporre, e l'istituto che ne nasce
_DERIVATI_127_TER = (
    (30, NOTIFICA_RICORSO_DECRETO, re.compile(r"30\s+giorn[io]\s+prima", re.I)),
    (10, COSTITUZIONE_RESISTENTE,
     re.compile(r"10\s+giorn[io]\s+prima.*?(?:scadenza|udienza|termine)"
                r"|(?:scadenza|udienza|termine).*?10\s+giorn[io]\s+prima", re.I | re.S)),
)

_RE_127_TER = re.compile(r"127\s*[-\s]?\s*ter", re.I)
_RE_127_BIS = re.compile(r"127\s*[-\s]?\s*bis", re.I)


def cita_127_ter(testo: str) -> bool:
    return bool(_RE_127_TER.search(str(testo or "")))


def cita_127_bis(testo: str) -> bool:
    return bool(_RE_127_BIS.search(str(testo or "")))


def derivati_da_note(testo: str, scadenza: date) -> list[tuple[Istituto, date]]:
    """I termini che il decreto fa discendere dalla scadenza delle note scritte.

    Si registrano **solo** quelli che il decreto dichiara: un decreto che non
    parla della notifica non fa nascere un termine di notifica, e inventarlo
    metterebbe in scadenziario una data che nessun giudice ha imposto.
    """
    testo = str(testo or "")
    return [
        (istituto, scadenza - timedelta(days=giorni))
        for giorni, istituto, espressione in _DERIVATI_127_TER
        if espressione.search(testo)
    ]


def derivati_da_udienza_remota(testo: str, udienza: date) -> list[tuple[Istituto, date]]:
    """Il termine di costituzione che il decreto di udienza da remoto richiama."""
    espressione = re.compile(
        r"(?:almeno\s+)?10\s+giorn[io]\s+prima.*?(?:costituzion|costituirs)"
        r"|(?:costituzion|costituirs).*?(?:almeno\s+)?10\s+giorn[io]\s+prima",
        re.I | re.S,
    )
    if not espressione.search(str(testo or "")):
        return []
    return [(COSTITUZIONE_CONVENUTO, udienza - timedelta(days=10))]


def istituto_di(codice: str) -> Istituto | None:
    return ISTITUTI_PER_CODICE.get(str(codice or "").strip())


__all__ = [
    "COSTITUZIONE_CONVENUTO", "COSTITUZIONE_RESISTENTE", "ISTITUTI", "ISTITUTI_PER_CODICE",
    "NORMA_127_BIS", "NORMA_127_TER", "NOTE_127_TER", "NOTIFICA_RICORSO_DECRETO",
    "UDIENZA_127_BIS", "Istituto", "cita_127_bis", "cita_127_ter",
    "derivati_da_note", "derivati_da_udienza_remota", "istituto_di",
]
