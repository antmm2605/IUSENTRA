"""Il corpus di collaudo: pagine di prova con i dati che i motori devono leggere.

Ogni caso è una pagina scritta come un atto o una comunicazione reale — con
udienze, termini, notifiche, ricevute PEC, numeri di ruolo — e con le trappole
tipiche: date di nascita, documenti d'identità, protocolli, versioni, tabelle
di date senza ancora. Per ogni caso si dichiara che cosa il motore deve
trovare e che cosa non deve mai proporre. Le pagine si renderizzano da questo
testo, così il collaudo prova davvero la lettura ottica e non solo le regole.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Caso:
    id: str
    titolo: str
    righe: tuple[str, ...]
    attesi: tuple[tuple[str, str, str], ...]  # (categoria, campo, valore ISO o codice)
    vietati: tuple[str, ...] = field(default=())  # valori (ISO) che non devono comparire come fatti utili
    fascicolo: tuple[tuple[str, str], ...] = field(default=())
    vietati_fatti: tuple[tuple[str, str, str], ...] = field(default=())


CASI: tuple[Caso, ...] = (
    Caso(
        id="sentenza_fondo_esborsi_distinti",
        titolo="Sentenza con fondo spese ed esborsi distinti",
        righe=("TRIBUNALE DI MILANO", "Sentenza n. 88/2026 pubblicata il 05/09/2026",
               "R.G. n. 1234/2026", "Anna Bianchi contro Ministero dell'Istruzione e del Merito",
               "P.Q.M. Condanna il Ministero alla rifusione delle spese di lite",
               "liquidando euro 1.100,00 per compensi ed euro 21,50 per esborsi.",
               "Fondo spese riconosciuto pari a euro 250,00."),
        attesi=(("importo", "spese_esborsi", "21.50"), ("importo", "fondo_spese", "250.00")),
        fascicolo=(("id", "COLLAUDO-ECONOMICO"), ("nome_cliente", "Anna Bianchi"),
                   ("numero_rg", "1234/2026"), ("anno_rg", "2026"), ("tribunale", "Tribunale di Milano")),
        vietati_fatti=(("importo", "spese_esborsi", "250.00"),),
    ),
    Caso(
        id="sentenza_fondo_non_univoco",
        titolo="Sentenza con due somme non attribuibili a un fondo unico",
        righe=("TRIBUNALE DI MILANO", "Sentenza n. 88/2026 pubblicata il 05/09/2026",
               "R.G. n. 1234/2026", "Anna Bianchi contro Ministero dell'Istruzione e del Merito",
               "P.Q.M. Condanna il Ministero alla rifusione delle spese di lite.",
               "Fondo spese euro 250,00. Fondo spese euro 300,00."),
        attesi=(("evento", "fondo_spese_da_verificare", "verifica_necessaria"),),
        fascicolo=(("id", "COLLAUDO-ECONOMICO"), ("nome_cliente", "Anna Bianchi"),
                   ("numero_rg", "1234/2026"), ("anno_rg", "2026"), ("tribunale", "Tribunale di Milano")),
        vietati_fatti=(("importo", "fondo_spese", "250.00"), ("importo", "fondo_spese", "300.00")),
    ),
    Caso(
        id="data_documento_senza_termini",
        titolo="Data tecnica separata da una frase senza eventi processuali",
        righe=("DOCUMENTO TECNICO DI COLLAUDO", "Non attesta udienze o scadenze.", "Data 12/10/2026"),
        attesi=(), vietati=("2026-10-12",),
    ),
    Caso(
        id="decreto_fissazione_udienza",
        titolo="Decreto di fissazione dell'udienza con termine per le memorie",
        righe=(
            "TRIBUNALE ORDINARIO DI MILANO",
            "Sezione Prima Civile - R.G. n. 1234/2026",
            "Il Giudice, letti gli atti, fissa l'udienza di comparizione",
            "delle parti per il giorno 10/11/2026 alle ore 9.30",
            "e assegna termine perentorio fino al 31/10/2026",
            "per il deposito delle memorie ex art. 171-ter c.p.c.",
            "Il ricorso e' stato notificato il 15/08/2026 a mezzo PEC.",
            "Milano, li' 20/09/2026",
        ),
        attesi=(("ruolo", "numero_ruolo", "1234/2026"), ("data", "udienza", "2026-11-10T09:30"), ("data", "termine", "2026-10-31"), ("data", "notifica", "2026-08-15"), ("data", "data_atto", "2026-09-20")),
    ),
    Caso(
        id="relata_con_dati_anagrafici",
        titolo="Relata di notifica con dati anagrafici e documento d'identita'",
        righe=(
            "RELATA DI NOTIFICA",
            "ai sensi dell'art. 3-bis della legge 21 gennaio 1994 n. 53",
            "Io sottoscritto avv. Mario Rossi notifico il presente atto",
            "al sig. Paolo Bianchi, nato a Roma il 12/03/1980,",
            "carta d'identita' n. CA12345 rilasciata il 03/02/2020,",
            "codice fiscale BNCPLA80C12H501Z, a mezzo PEC.",
            "Ricevuta di accettazione del 05/09/2026 ore 10:15",
            "Ricevuta di avvenuta consegna del 05/09/2026 ore 10:16",
        ),
        attesi=(("prova_notifica", "relata", "relata"), ("prova_notifica", "rac", "rac"), ("prova_notifica", "rdac", "rdac"), ("data", "accettazione", "2026-09-05T10:15"), ("data", "consegna", "2026-09-05T10:16")),
        vietati=("1980-03-12", "2020-02-03", "1994-01-21"),
    ),
    Caso(
        id="comunicazione_con_tabella",
        titolo="Comunicazione di cancelleria con tabella di date e protocolli",
        righe=(
            "COMUNICAZIONE DI CANCELLERIA ex art. 136 c.p.c.",
            "Si comunica il decreto del 05/09/2026 nel procedimento",
            "R.G. 987/2025 - Prot. n. 55/2026 - Versione 1.2.34",
            "Storico depositi: 01/01/2020 02/02/2021 03/03/2022",
            "Periodo di riferimento dal 01/02/2026 al 28/02/2026",
            "Udienza rinviata al giorno 12 marzo 2027 ore 11.00",
        ),
        attesi=(("prova_notifica", "comunicazione_cancelleria", "comunicazione_cancelleria"), ("ruolo", "numero_ruolo", "987/2025"), ("data", "provvedimento", "2026-09-05"), ("data", "udienza", "2027-03-12T11:00")),
        vietati=("2020-01-01", "2021-02-02", "2022-03-03", "2026-02-01", "2026-02-28", "2034-02-01"),
    ),
)


def corpo_del_caso(caso: Caso) -> str:
    return "\n".join(caso.righe)


__all__ = ["CASI", "Caso", "corpo_del_caso"]
