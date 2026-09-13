"""Calcolatori giuridici modulari.

Ogni modulo copre una materia con base normativa dichiarata nel docstring:

- ``interessi_acconti``: imputazione degli acconti ex art. 1194 c.c.
- ``maggior_danno``: maggior danno da svalutazione ex art. 1224, comma 2, c.c.
- ``danno_biologico``: liquidazione del danno biologico sulle tabelle vigenti
  (art. 139 D.Lgs. 209/2005, tabella unica nazionale del D.P.R. 12/2025,
  tabelle milanesi edizione 2024).
- ``danno_parentale``: perdita del rapporto parentale (Tabelle Milano 2024).
- ``danno_premorienza``: lesione del bene salute definita da premorienza
  (Tabelle Milano 2024).
- ``consenso_informato``: danno al diritto di autodeterminazione in ambito
  sanitario (Tabelle Milano 2024; Cass. 28985/2019).
- ``diffamazione``: danno da diffamazione a mezzo stampa e riparazione
  pecuniaria ex art. 12 L. 47/1948 (Tabelle Milano 2024).
- ``capitalizzazione_rendita``: attualizzazione della rendita perduta
  (Tabelle Milano 2024; Cass. 9002/2022).
- ``lite_temeraria``: somma equitativa per abuso del processo (art. 96,
  comma 3, c.p.c.; criteri Osservatorio di Milano 2024).
- ``danno_terminale``: sofferenza fra lesioni e decesso (Tabelle Milano 2024;
  Cass. Sez. Un. 15350/2015).
- ``usufrutto``: usufrutto vitalizio e nuda proprietà (D.P.R. 131/1986).
- ``quote_riserva``: quote di riserva dei legittimari (artt. 536-556 c.c.).
- ``assegno_mantenimento``: stima orientativa dell'assegno (art. 337-ter c.c.,
  art. 5 L. 898/1970).
- ``pena_riti_alternativi``: attenuanti, continuazione e riti alternativi
  (artt. 62-bis, 65, 81, 132, 163 c.p.; artt. 442 e 444 c.p.p.).
- ``crediti_lavoro``: rivalutazione e interessi sui crediti di lavoro
  (art. 429, comma 3, c.p.c.; art. 22, comma 36, L. 724/1994).
- ``patrocinio_spese_stato``: limiti di reddito per l'ammissione al patrocinio
  (artt. 76, 77 e 92 D.P.R. 115/2002).
- ``competenza_valore``: competenza per valore del giudice di pace
  (art. 7 c.p.c.; art. 3, comma 1, D.Lgs. 149/2022).
- ``termini_scadenza``: scadenza dei termini processuali con sospensione feriale
  (art. 155 c.p.c.; L. 742/1969), sul motore di ``pct.termini_processuali``.
- ``impugnazioni``: termine breve e termine lungo a confronto (artt. 325 e 327
  c.p.c.), sullo stesso motore dei termini.
- ``ravvedimento_operoso``: sanzione ridotta e interessi (art. 13 D.Lgs.
  472/1997; art. 13 D.Lgs. 471/1997; D.Lgs. 87/2024).
- ``compenso_a_tempo_calc``: compenso a tempo dell'avvocato (art. 22-bis D.M.
  55/2014), sul motore di ``pct.compensi_a_tempo``.

L'orchestrazione applicativa resta in ``pct.strumenti_legali``.
"""
from pct.calcolatori import (  # noqa: F401
    assegno_mantenimento,
    capitalizzazione_rendita,
    consenso_informato,
    competenza_valore,
    compenso_a_tempo_calc,
    crediti_lavoro,
    danno_biologico,
    danno_parentale,
    diffamazione,
    danno_premorienza,
    danno_terminale,
    impugnazioni,
    interessi_acconti,
    lite_temeraria,
    maggior_danno,
    patrocinio_spese_stato,
    pena_riti_alternativi,
    quote_riserva,
    ravvedimento_operoso,
    termini_scadenza,
    usufrutto,
)

__all__ = [
    "assegno_mantenimento",
    "capitalizzazione_rendita",
    "consenso_informato",
    "competenza_valore",
    "compenso_a_tempo_calc",
    "crediti_lavoro",
    "danno_biologico",
    "danno_parentale",
    "diffamazione",
    "danno_premorienza",
    "danno_terminale",
    "impugnazioni",
    "interessi_acconti",
    "lite_temeraria",
    "maggior_danno",
    "patrocinio_spese_stato",
    "pena_riti_alternativi",
    "quote_riserva",
    "ravvedimento_operoso",
    "termini_scadenza",
    "usufrutto",
]
