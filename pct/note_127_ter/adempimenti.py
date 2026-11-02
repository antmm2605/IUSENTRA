"""Che cosa preparare per le note scritte, secondo il decreto (art. 127-ter c.p.c.).

Ogni voce nasce da ciò che il decreto scrive o dalla norma che governa le note:

* contenuto: le sole istanze e conclusioni previste per l'udienza sostituita (art. 127-ter,
  comma 1, c.p.c.);
* le cinque indicazioni che il decreto chiede di riportare nelle note;
* la prova della notifica, se la resistente non è costituita e il nostro cliente è il
  ricorrente: per la notifica telematica la busta con il file «.eml» della ricevuta di avvenuta
  consegna completa (art. 19-bis Provv. DGSIA 16/04/2014, citato dal decreto, oggi art. 26
  Specifiche tecniche DGSIA 7/8/2024 adottate ai sensi dell'art. 34 D.M. 44/2011); per la notifica
  cartacea la copia digitale con attestazione di conformità (artt. 16-decies e 16-undecies D.L.
  179/2012, citati dal decreto, oggi art. 196-undecies disp. att. c.p.c.);
* il provvedimento atteso fuori udienza nei giorni indicati dal decreto dopo la scadenza;
* l'opposizione entro cinque giorni dalla comunicazione (art. 127-ter, comma 2, c.p.c.): la
  propone già il presidio PEC (``CIV_OPPOSIZIONE_127_TER``), qui è solo richiamata.

Il contenuto delle note (istanze e conclusioni) resta dell'avvocato: nessuna voce lo scrive.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .decreto import DecretoNoteScritte


@dataclass(frozen=True)
class Adempimento:
    codice: str
    testo: str
    dettaglio: str
    fonti: tuple[str, ...] = ()  # identificativi di pct/procedura_fasi/fonti.py

    def riga(self) -> str:
        return f"{self.testo}: {self.dettaglio}" if self.dettaglio else self.testo


def _indicazioni(giorno: date, *, rg: str, giudice: str, ufficio: str, difensori: str) -> str:
    return (
        "1) dicitura «Note per la trattazione scritta»; "
        f"2) data di udienza {giorno:%d/%m/%Y}; "
        f"3) numero di ruolo e anno {('R.G. ' + rg) if rg else '(da indicare)'}; "
        f"4) giudice {giudice or '(da indicare)'} e ufficio {ufficio or '(da indicare)'}; "
        f"5) difensori costituiti e parti assistite {difensori or '(da indicare)'}"
    )


def _prova_notifica(decreto: DecretoNoteScritte | None, documento_prova: str, certa: bool) -> Adempimento:
    modi = []
    if decreto is None or decreto.prova_telematica:
        modi.append("notifica telematica: busta con il file «.eml» della ricevuta di avvenuta consegna completa")
    if decreto is None or decreto.prova_cartacea:
        modi.append("notifica cartacea: copia digitale del ricorso notificato con attestazione di conformità")
    dove = f"; nel fascicolo: «{documento_prova}»" if documento_prova else "; nel fascicolo non risulta ancora un documento di prova"
    prefisso = "" if certa else "Se la parte resistente non si è costituita: "
    return Adempimento(
        "prova_notifica",
        f"{prefisso}allegare alle note o depositare nello stesso termine la prova della notifica",
        "; ".join(modi) + dove,
        ("dgsia_art26", "dispatt_196undecies"),
    )


def adempimenti_note(
    decreto: DecretoNoteScritte | None,
    giorno: date,
    *,
    rg: str = "",
    giudice: str = "",
    ufficio: str = "",
    difensori: str = "",
    cliente_ricorrente: bool | None = None,
    resistente_costituita: bool | None = None,
    documento_prova: str = "",
    opposizione_proposta: bool = False,
    ora_limite: str = "",
) -> list[Adempimento]:
    """Le voci della checklist per le note in scadenza il ``giorno`` (data dell'udienza sostituita).

    ``decreto`` None: il decreto è già stato letto e resta la scadenza proposta; ``ora_limite`` è
    l'orario che quella scadenza riporta dal decreto.
    """
    ora = (decreto.ora_limite if decreto else ora_limite) or ""
    voci = [
        Adempimento(
            "contenuto",
            "Note con le sole istanze e conclusioni previste per l'udienza sostituita",
            f"il giorno di scadenza ({giorno:%d/%m/%Y}) vale come data di udienza"
            + (f"; deposito entro le ore {ora}, come invita il decreto" if ora else "")
            + "; le conclusioni le scrive l'avvocato",
            ("cpc_127ter",),
        ),
        Adempimento(
            "indicazioni",
            "Riportare nelle note le indicazioni richieste dal decreto",
            _indicazioni(giorno, rg=rg, giudice=giudice, ufficio=ufficio, difensori=difensori),
            ("cpc_127ter",),
        ),
    ]
    invito = decreto is None or decreto.invito_prova_notifica
    if invito and cliente_ricorrente is not False and resistente_costituita is not True:
        certa = cliente_ricorrente is True and resistente_costituita is False
        voci.append(_prova_notifica(decreto, documento_prova, certa))
    giorni = (decreto.giorni_decisione if decreto else 0) or 30
    voci.append(Adempimento(
        "decisione",
        "Provvedimento del giudice atteso fuori udienza",
        f"entro {giorni} giorni dalla scadenza (indicativamente entro il {giorno + timedelta(days=giorni):%d/%m/%Y}); "
        "se nessuna parte deposita, il giudice fissa un nuovo termine o un'udienza",
        ("cpc_127ter", "cpc_309"),
    ))
    if opposizione_proposta:
        voci.append(Adempimento(
            "opposizione",
            "Eventuale opposizione alla trattazione scritta",
            "entro cinque giorni dalla comunicazione (art. 127-ter, comma 2, c.p.c.): già proposta dal presidio PEC",
            ("cpc_127ter",),
        ))
    return voci


__all__ = ["Adempimento", "adempimenti_note"]
