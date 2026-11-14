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
        id="ricorso_con_carta_identita_scansionata",
        titolo="Ricorso con la copia della carta d'identita' cartacea in coda",
        righe=(
            "TRIBUNALE DI ROCCAVERDE - SEZIONE LAVORO",
            "Ricorso ex art. 414 c.p.c. per la sig.ra Anna Rossi,",
            "nata a Roccaverde (RC) il 03/07/1982, residente in Roccaverde.",
            "rappresentata e difesa dall'avv. Paolo Verdi, contro il Ministero",
            "dell'Istruzione e del Merito, in persona del Ministro pro tempore.",
            "La ricorrente, docente a tempo determinato, chiede il riconoscimento",
            "della carta del docente per gli anni scolastici di servizio prestati.",
            "Si producono i contratti di lavoro e la copia del documento personale.",
            "Impronta del dito indice sinistro",
            "IL FUNZIONARIO INCARICATO Mario Bianchi",
            "Scadenza 03-07-2027",
            "REPUBBLICA ITALIANA COMUNE DI ROCCAVERDE",
            "CARTA D'IDENTITA N. AX0000000",
        ),
        attesi=(),
        vietati=("2027-07-03", "1982-07-03"),
    ),
    Caso(
        # Collaudo dell'avvocato del 10/11/2026: il termine per le note è quello scritto dal giudice (art. 127-ter,
        # primo comma, c.p.c.), non l'udienza tenuta né quella sostituita; la seconda diserzione estingue (art. 631).
        id="rinvio_631_note_127_ter",
        titolo="Verbale di esecuzione: rinvio per mancata comparizione con note scritte entro termine perentorio",
        righe=(
            "TRIBUNALE DI ALFA - CANCELLERIA ESECUZIONI MOBILIARI",
            "Proc. n. 111/2025 R.G.E.",
            "All'udienza del 2.11.2026 tenuta dal G.E., viene chiamata la causa.",
            "Poiché nessuno è presente rinvia all'udienza del 21.12.2026 che sostituisce",
            "con il deposito di note scritte ex art. 127 ter c.p.c.",
            "entro il termine perentorio del 16.12.2026.",
            "Ai sensi dell'art. 631 c.p.c. Si comunichi.",
        ),
        attesi=(("data", "termine", "2026-12-16"), ("data", "udienza", "2026-12-21")),
        fascicolo=(("id", "COLLAUDO-631"), ("numero_rg", "111"), ("anno_rg", "2025"), ("tribunale", "Tribunale di Alfa")),
        vietati_fatti=(("data", "termine", "2026-12-21"), ("data", "termine", "2026-11-02")),
    ),
    Caso(
        # Provvedimento collettivo: per la causa 111/2025 vale solo la clausola del suo gruppo (udienza in presenza).
        id="rinvio_collettivo_gruppi_rg",
        titolo="Comunicazione del G.E. con due gruppi di cause e due udienze",
        righe=(
            "TRIBUNALE DI ALFA - CANCELLERIA ESECUZIONI MOBILIARI",
            "Il G.E. comunica che le cause sono rinviate come segue:",
            "I procedimenti recanti n. 10/24; 22/25; 111/25; 300/26",
            "sono rinviati all'udienza del 2.11.2026 che sarà trattata in presenza.",
            "I procedimenti recanti n. 5/21; 83/25; 400/25",
            "sono rinviati all'udienza del 9.11.2026 che sostituisce",
            "con il deposito di note scritte ex art. 127 ter c.p.c.",
            "entro il termine perentorio del 4.11.2026.",
        ),
        attesi=(("data", "udienza", "2026-11-02"),),
        fascicolo=(("id", "COLLAUDO-COLLETTIVO"), ("numero_rg", "111"), ("anno_rg", "2025"), ("tribunale", "Tribunale di Alfa")),
        vietati=("2026-11-04", "2026-11-09"),
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
    Caso(
        id="istanza_esecutorieta_decorrenza_errata",
        titolo="Istanza di esecutorietà del decreto ingiuntivo con decorrenza scritta per errore",
        righe=(
            "GIUDICE DI PACE DI ROCCAVERDE - R.G. n. 321/2024",
            "Istanza per la dichiarazione di esecutorietà ex art. 647 c.p.c.",
            "PREMESSO che il decreto ingiuntivo è stato notificato all'ingiunto",
            "in data 23/12/2024 a mezzo PEC ex art. 3-bis L. 53/94;",
            "considerato che è scaduto il termine di quaranta giorni ex art. 641",
            "decorrente dal 10/02/2024 e che non è stata proposta opposizione,",
            "chiede che il decreto sia dichiarato esecutivo.",
            "Roccaverde, li' 10/02/2025",
        ),
        attesi=(("ruolo", "numero_ruolo", "321/2024"), ("data", "notifica", "2024-12-23")),
        # la data da cui il termine decorre (anteriore alla notifica) non è un termine né un'udienza
        vietati=("2024-02-10",),
    ),
    # Collaudo 10/11/2026: il numero di ruolo della volontaria giurisdizione risultava solo dal deposito integrativo
    # (art. 13 D.M. 44/2011): la Lettura lo prende da qui (pct/procedura_fasi/ruolo_dagli_atti.py).
    Caso(
        id="deposito_integrativo_con_ruolo",
        titolo="Copia del messaggio di deposito telematico integrativo con il numero di ruolo",
        righe=(
            "COPIA NON CRITTOGRAFATA DEPOSITO TELEMATICO",
            "Oggetto: DEPOSITO TELEMATICO: ricevuta pagamento RG: 14848/2025",
            "Mittente: Avv. Mario Rossi <mario.rossi@pec.example.it>",
            "Destinatari: tribunale.firenze@civile.ptel.giustiziacert.it",
            "Tali documenti si riferiscono alla causa RG: 14848/2025 di codesto TRIBUNALE DI FIRENZE",
        ),
        attesi=(("ruolo", "numero_ruolo", "14848/2025"),),
    ),
    # Collaudo 10/11/2026: il decreto che dichiara esecutivo il decreto ingiuntivo (art. 647 c.p.c.) porta in calce la
    # data dell'esecutorietà; la data di emissione del d.i. richiamata nel testo è un provvedimento, non un'udienza.
    Caso(
        id="decreto_esecutorieta_ingiuntivo",
        titolo="Decreto di esecutorietà del decreto ingiuntivo",
        righe=(
            "UFFICIO DEL GIUDICE DI PACE DI PALMI",
            "N.RG 4202 / 2024",
            "Visto il decreto ingiuntivo n. 1109/2024, emesso in data 20-12-2024,",
            "notificato in data 23-12-2024;",
            "atteso che avverso il suddetto decreto non è stata proposta opposizione; visto l'art. 647 c.p.c.;",
            "DICHIARA esecutivo il decreto ingiuntivo n. 1109/2024. Si comunichi PALMI, 10-03-2025",
            "Il Giudice di Pace Dott. Mario Bianchi",
        ),
        attesi=(("ruolo", "numero_ruolo", "4202/2024"), ("data", "notifica", "2024-12-23"), ("data", "data_atto", "2025-03-10")),
        vietati_fatti=(("data", "udienza", "2024-12-20"), ("data", "udienza", "2025-03-10")),
    ),
)


def corpo_del_caso(caso: Caso) -> str:
    return "\n".join(caso.righe)


__all__ = ["CASI", "Caso", "corpo_del_caso"]
