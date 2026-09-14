"""Perfezionamento della notificazione e decorrenza del termine.

Sapere *quando* una notifica si è perfezionata è il presupposto di ogni
scadenza: il termine non decorre dalla spedizione ma dal perfezionamento, che
cade in momenti diversi per il notificante e per il destinatario e che cambia
con il canale usato. È l'errore che costa la decadenza, e non si risolve
contando giorni sul calendario.

Base normativa (testi verificati su Normattiva):

- **Art. 147 c.p.c.** (testo in vigore dal 1° gennaio 2023). Le notificazioni
  non possono farsi prima delle 7 e dopo le 21; quelle a mezzo PEC o servizio
  elettronico di recapito certificato qualificato possono essere eseguite senza
  limiti orari e «si intendono perfezionate, per il notificante, nel momento in
  cui è generata la ricevuta di accettazione e, per il destinatario, nel momento
  in cui è generata la ricevuta di avvenuta consegna. Se quest'ultima è generata
  tra le ore 21 e le ore 7 del mattino del giorno successivo, la notificazione
  si intende perfezionata per il destinatario alle ore 7».
- **Corte costituzionale 75/2019**, sul regime storico dell'art. 16-septies
  D.L. 179/2012: la notifica telematica eseguita dopo le 21 si perfeziona per il
  notificante alla generazione della ricevuta di accettazione. La regola è oggi
  scritta nell'art. 147, comma 3, c.p.c.
- **Art. 149 c.p.c.**: la notifica a mezzo posta «si perfeziona, per il soggetto
  notificante, al momento della consegna del plico all'ufficiale giudiziario e,
  per il destinatario, dal momento in cui lo stesso ha la legale conoscenza
  dell'atto».
- **Art. 8, commi 4 e 5, L. 890/1982**: in caso di mancato recapito la
  notificazione «si ha comunque per eseguita trascorsi dieci giorni dalla data
  di spedizione» della raccomandata che dà notizia del deposito, e si ha per
  eseguita dalla data del ritiro del piego se anteriore.
- **Art. 140 c.p.c.** letto con **Corte costituzionale 3/2010**, che ne ha
  dichiarato l'illegittimità «nella parte in cui prevede che la notifica si
  perfeziona, per il destinatario, con la spedizione della raccomandata
  informativa, anziché con il ricevimento della stessa o, comunque, decorsi
  dieci giorni dalla relativa spedizione».
- **Art. 143 c.p.c.**: per il destinatario di residenza, dimora e domicilio
  sconosciuti «la notificazione si ha per eseguita nel ventesimo giorno
  successivo a quello in cui sono compiute le formalità prescritte».
- **Art. 155 c.p.c.** e **art. 1 L. 742/1969** per il computo del termine che
  decorre dal perfezionamento e per la sospensione feriale.

Il modulo non decide se la notifica è valida: dice quando si è perfezionata
secondo il canale dichiarato, e da lì calcola il termine. La validità della
relata, del destinatario e dell'indirizzo resta una verifica dell'avvocato.
"""
from __future__ import annotations

from datetime import date, time, timedelta
from typing import Any, Dict, List, Mapping, Optional

from pct.calcolatori._base import clean_text, fmt_date_it, parse_date, safe_int
from pct.termini_processuali import ItalianDeadlineCalculator

# Ore fra le quali la ricevuta di avvenuta consegna differisce il
# perfezionamento per il destinatario (art. 147, comma 3, c.p.c.).
ORA_CHIUSURA = time(21, 0)
ORA_APERTURA = time(7, 0)

# Giorni di compiuta giacenza: art. 8, comma 4, L. 890/1982 per la notifica a
# mezzo posta e Corte cost. 3/2010 per l'art. 140 c.p.c. La decorrenza è la
# stessa in entrambi i casi — la spedizione della raccomandata informativa — ma
# le due fonti restano distinte e vengono citate separatamente.
GIORNI_GIACENZA = 10

# Art. 143, terzo comma, c.p.c.: la notificazione si ha per eseguita nel
# ventesimo giorno successivo alle formalità.
GIORNI_IRREPERIBILE = 20

FONTI: tuple[Dict[str, str], ...] = (
    {
        "title": "Art. 147 c.p.c. — Tempo delle notificazioni (testo vigente dal 1° gennaio 2023)",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art147",
    },
    {
        "title": "Art. 149 c.p.c. — Notificazione a mezzo del servizio postale",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art149",
    },
    {
        "title": "Art. 140 c.p.c. — Irreperibilità o rifiuto di ricevere la copia",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art140",
    },
    {
        "title": "Art. 143 c.p.c. — Residenza, dimora e domicilio sconosciuti",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443~art143",
    },
    {
        "title": "Art. 8 L. 20 novembre 1982, n. 890 — Deposito e compiuta giacenza",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1982-11-20;890~art8",
    },
    {
        "title": "L. 7 ottobre 1969, n. 742 — Sospensione feriale dei termini",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1969-10-07;742",
    },
)

CANALI: Dict[str, Dict[str, str]] = {
    "pec": {
        "label": "PEC o servizio elettronico di recapito certificato (L. 53/1994, art. 3-bis)",
        "norma": "Art. 147, commi 2 e 3, c.p.c.",
    },
    "posta": {
        "label": "Servizio postale tramite ufficiale giudiziario (L. 890/1982)",
        "norma": "Art. 149 c.p.c.; art. 8 L. 890/1982",
    },
    "art140": {
        "label": "Irreperibilità relativa — deposito in casa comunale (art. 140 c.p.c.)",
        "norma": "Art. 140 c.p.c.; Corte cost. 3/2010",
    },
    "art143": {
        "label": "Residenza, dimora e domicilio sconosciuti (art. 143 c.p.c.)",
        "norma": "Art. 143, terzo comma, c.p.c.",
    },
    "mani": {
        "label": "Consegna a mani dall'ufficiale giudiziario (artt. 138-139 c.p.c.)",
        "norma": "Artt. 138 e 139 c.p.c.",
    },
}

ESITI_POSTA = {
    "consegnato": "Piego consegnato al destinatario o a persona abilitata",
    "giacenza": "Piego non consegnato: deposito e compiuta giacenza",
}


def _ora(valore: Any, campo: str) -> Optional[time]:
    """Orario in formato ``hh:mm``; vuoto è ammesso e vale «non dichiarato»."""
    testo = clean_text(valore).replace(".", ":")
    if not testo:
        return None
    pezzi = testo.split(":")
    try:
        ore = int(pezzi[0])
        minuti = int(pezzi[1]) if len(pezzi) > 1 else 0
    except (TypeError, ValueError):
        raise ValueError(f"{campo}: usa il formato 24 ore, ad esempio 21:40.") from None
    if not 0 <= ore <= 23 or not 0 <= minuti <= 59:
        raise ValueError(f"{campo}: orario non valido ({testo}).")
    return time(ore, minuti)


def _fmt_ora(valore: Optional[time]) -> str:
    return valore.strftime("%H:%M") if valore else ""


def _fmt_momento(giorno: Optional[date], orario: Optional[time]) -> str:
    if giorno is None:
        return ""
    testo = fmt_date_it(giorno)
    return f"{testo} alle {_fmt_ora(orario)}" if orario else testo


def _nella_fascia_notturna(orario: time) -> bool:
    """Vero se la ricevuta cade nella fascia protetta 21:00 → 07:00."""
    return orario >= ORA_CHIUSURA or orario < ORA_APERTURA


def _perfezionamento_pec(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data_rac = parse_date(payload.get("not_data_invio"))
    if data_rac is None:
        raise ValueError("Indica la data della ricevuta di accettazione (RAC).")
    ora_rac = _ora(payload.get("not_ora_invio"), "Ora della ricevuta di accettazione")
    data_rdac = parse_date(payload.get("not_data_consegna"))
    if data_rdac is None:
        raise ValueError(
            "Indica la data della ricevuta di avvenuta consegna (RdAC): è il momento in cui la "
            "notifica si perfeziona per il destinatario."
        )
    if data_rdac < data_rac:
        raise ValueError("La ricevuta di avvenuta consegna non può precedere quella di accettazione.")
    ora_rdac = _ora(payload.get("not_ora_consegna"), "Ora della ricevuta di avvenuta consegna")

    giorno_destinatario = data_rdac
    ora_destinatario = ora_rdac
    differito = False
    if ora_rdac is not None and _nella_fascia_notturna(ora_rdac):
        differito = True
        ora_destinatario = ORA_APERTURA
        if ora_rdac >= ORA_CHIUSURA:
            giorno_destinatario = data_rdac + timedelta(days=1)

    passaggi = [
        {
            "passaggio": "Ricevuta di accettazione (RAC) — perfezionamento per il notificante",
            "data": _fmt_momento(data_rac, ora_rac),
        },
        {
            "passaggio": "Ricevuta di avvenuta consegna (RdAC)",
            "data": _fmt_momento(data_rdac, ora_rdac),
        },
    ]
    if differito:
        passaggi.append(
            {
                "passaggio": "Differimento alle ore 7 (art. 147, comma 3, c.p.c.)",
                "data": _fmt_momento(giorno_destinatario, ora_destinatario),
            }
        )

    note = [
        "Per il notificante la notifica si perfeziona alla generazione della ricevuta di "
        "accettazione; per il destinatario alla generazione della ricevuta di avvenuta consegna "
        "(art. 147, comma 3, c.p.c.).",
        "L'invio telematico non soggiace ai limiti orari delle 7 e delle 21 previsti per gli altri "
        "canali (art. 147, comma 2, c.p.c.).",
    ]
    if differito:
        note.append(
            "La ricevuta di avvenuta consegna cade nella fascia fra le 21 e le 7: per il "
            f"destinatario la notifica si perfeziona alle 7 del {fmt_date_it(giorno_destinatario)}."
        )
    elif ora_rdac is None:
        note.append(
            "Ora della ricevuta di avvenuta consegna non indicata: il differimento alle 7 previsto "
            "per la fascia 21-7 non è stato verificato. Ricavala dalla ricevuta per avere la "
            "decorrenza esatta."
        )

    return {
        "giorno_notificante": data_rac,
        "ora_notificante": ora_rac,
        "giorno_destinatario": giorno_destinatario,
        "ora_destinatario": ora_destinatario,
        "passaggi": passaggi,
        "notes": note,
        "differito": differito,
    }


def _compiuta_giacenza(
    data_cad: Optional[date],
    data_ritiro: Optional[date],
    *,
    etichetta_avviso: str,
) -> tuple[date, List[Dict[str, str]], List[str]]:
    """Data di perfezionamento per compiuta giacenza e passaggi che la spiegano."""
    if data_cad is None:
        raise ValueError(
            f"Indica la data di spedizione {etichetta_avviso}: da lì decorrono i dieci giorni di "
            "compiuta giacenza."
        )
    scadenza_giacenza = data_cad + timedelta(days=GIORNI_GIACENZA)
    passaggi = [
        {"passaggio": f"Spedizione {etichetta_avviso}", "data": fmt_date_it(data_cad)},
        {
            "passaggio": f"Compiuta giacenza: {GIORNI_GIACENZA} giorni dalla spedizione",
            "data": fmt_date_it(scadenza_giacenza),
        },
    ]
    note: List[str] = []
    if data_ritiro is not None and data_ritiro < scadenza_giacenza:
        passaggi.append({"passaggio": "Ritiro del piego, anteriore alla compiuta giacenza", "data": fmt_date_it(data_ritiro)})
        note.append(
            "Il piego è stato ritirato prima dei dieci giorni: la notificazione si ha per eseguita "
            "dalla data del ritiro."
        )
        return data_ritiro, passaggi, note
    if data_ritiro is not None:
        note.append(
            "Il ritiro è successivo alla compiuta giacenza: prevale il decorso dei dieci giorni "
            "dalla spedizione."
        )
    return scadenza_giacenza, passaggi, note


def _perfezionamento_posta(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data_consegna_ug = parse_date(payload.get("not_data_invio"))
    if data_consegna_ug is None:
        raise ValueError(
            "Indica la data di consegna del plico all'ufficiale giudiziario: è il perfezionamento "
            "per il notificante (art. 149 c.p.c.)."
        )
    esito = clean_text(payload.get("not_esito_posta")).lower() or "consegnato"
    if esito not in ESITI_POSTA:
        raise ValueError("Esito della notifica postale non riconosciuto.")

    passaggi = [
        {
            "passaggio": "Consegna del plico all'ufficiale giudiziario — perfezionamento per il notificante",
            "data": fmt_date_it(data_consegna_ug),
        }
    ]
    note = [
        "Per il notificante la notifica si perfeziona alla consegna del plico all'ufficiale "
        "giudiziario; per il destinatario dalla legale conoscenza dell'atto (art. 149 c.p.c.).",
    ]

    if esito == "consegnato":
        data_ricezione = parse_date(payload.get("not_data_consegna"))
        if data_ricezione is None:
            raise ValueError("Indica la data di consegna del piego risultante dall'avviso di ricevimento.")
        if data_ricezione < data_consegna_ug:
            raise ValueError("La consegna al destinatario non può precedere la consegna all'ufficiale giudiziario.")
        passaggi.append({"passaggio": "Consegna del piego al destinatario", "data": fmt_date_it(data_ricezione)})
        giorno_destinatario = data_ricezione
    else:
        giorno_destinatario, passaggi_giacenza, note_giacenza = _compiuta_giacenza(
            parse_date(payload.get("not_data_avviso")),
            parse_date(payload.get("not_data_ritiro")),
            etichetta_avviso="della raccomandata di avviso del deposito (CAD)",
        )
        passaggi.extend(passaggi_giacenza)
        note.extend(note_giacenza)
        note.append(
            "Compiuta giacenza ex art. 8, commi 4 e 5, L. 890/1982: i dieci giorni decorrono dalla "
            "spedizione della raccomandata di avviso, non dal deposito del piego."
        )

    return {
        "giorno_notificante": data_consegna_ug,
        "ora_notificante": None,
        "giorno_destinatario": giorno_destinatario,
        "ora_destinatario": None,
        "passaggi": passaggi,
        "notes": note,
        "differito": False,
    }


def _perfezionamento_art140(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data_formalita = parse_date(payload.get("not_data_invio"))
    if data_formalita is None:
        raise ValueError("Indica la data del deposito in casa comunale e dell'affissione dell'avviso.")
    giorno_destinatario, passaggi_giacenza, note_giacenza = _compiuta_giacenza(
        parse_date(payload.get("not_data_avviso")),
        parse_date(payload.get("not_data_ritiro")),
        etichetta_avviso="della raccomandata informativa",
    )
    passaggi = [
        {
            "passaggio": "Deposito in casa comunale e affissione dell'avviso — adempimenti dell'art. 140 c.p.c.",
            "data": fmt_date_it(data_formalita),
        },
        *passaggi_giacenza,
    ]
    note = [
        "Per il destinatario la notifica si perfeziona con il ricevimento della raccomandata "
        "informativa o, comunque, decorsi dieci giorni dalla sua spedizione (Corte cost. 3/2010).",
        *note_giacenza,
    ]
    return {
        "giorno_notificante": data_formalita,
        "ora_notificante": None,
        "giorno_destinatario": giorno_destinatario,
        "ora_destinatario": None,
        "passaggi": passaggi,
        "notes": note,
        "differito": False,
    }


def _perfezionamento_art143(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data_formalita = parse_date(payload.get("not_data_invio"))
    if data_formalita is None:
        raise ValueError("Indica la data in cui sono state compiute le formalità dell'art. 143 c.p.c.")
    giorno_destinatario = data_formalita + timedelta(days=GIORNI_IRREPERIBILE)
    return {
        "giorno_notificante": data_formalita,
        "ora_notificante": None,
        "giorno_destinatario": giorno_destinatario,
        "ora_destinatario": None,
        "passaggi": [
            {"passaggio": "Compimento delle formalità (deposito in casa comunale)", "data": fmt_date_it(data_formalita)},
            {
                "passaggio": f"Notificazione eseguita nel {GIORNI_IRREPERIBILE}° giorno successivo",
                "data": fmt_date_it(giorno_destinatario),
            },
        ],
        "notes": [
            "Art. 143, terzo comma, c.p.c.: la notificazione si ha per eseguita nel ventesimo "
            "giorno successivo a quello in cui sono compiute le formalità prescritte.",
            "L'art. 143 presuppone ricerche effettive e documentate sulla residenza, dimora e "
            "domicilio del destinatario: senza di esse la notifica è nulla.",
        ],
        "differito": False,
    }


def _perfezionamento_mani(payload: Mapping[str, Any]) -> Dict[str, Any]:
    data_consegna = parse_date(payload.get("not_data_consegna")) or parse_date(payload.get("not_data_invio"))
    if data_consegna is None:
        raise ValueError("Indica la data di consegna della copia risultante dalla relata.")
    ora_consegna = _ora(payload.get("not_ora_consegna"), "Ora della consegna")
    note = [
        "Consegna a mani: la notifica si perfeziona nello stesso momento per il notificante e per "
        "il destinatario, alla data della relata.",
    ]
    if ora_consegna is not None and (ora_consegna < ORA_APERTURA or ora_consegna >= ORA_CHIUSURA):
        note.append(
            "L'orario dichiarato è fuori dalla fascia 7-21 dell'art. 147, primo comma, c.p.c.: "
            "verifica la relata, perché la notificazione non può essere eseguita in quell'orario."
        )
    return {
        "giorno_notificante": data_consegna,
        "ora_notificante": ora_consegna,
        "giorno_destinatario": data_consegna,
        "ora_destinatario": ora_consegna,
        "passaggi": [{"passaggio": "Consegna della copia al destinatario", "data": _fmt_momento(data_consegna, ora_consegna)}],
        "notes": note,
        "differito": False,
    }


_CALCOLO_CANALE = {
    "pec": _perfezionamento_pec,
    "posta": _perfezionamento_posta,
    "art140": _perfezionamento_art140,
    "art143": _perfezionamento_art143,
    "mani": _perfezionamento_mani,
}


def _termine(partenza: date, durata: int, unita: str, sospensione: bool) -> Dict[str, Any]:
    esito = ItalianDeadlineCalculator().calculate(
        partenza,
        durata,
        "forward",
        template_code="NOTIFICA_DECORRENZA",
        template_name="Termine dal perfezionamento della notifica",
        period_type="months" if unita == "mesi" else "days",
        suspend_august=sospensione,
        reference_law="Art. 155 c.p.c.; L. 742/1969",
    )
    return {
        "scadenza": fmt_date_it(esito.get("deadline")),
        "scadenza_senza_proroghe": fmt_date_it(esito.get("rawDeadline")),
        "passaggi": [
            {"passaggio": voce.get("label", ""), "data": fmt_date_it(voce.get("date"))}
            for voce in esito.get("steps") or []
        ],
    }


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    canale = clean_text(payload.get("not_canale")).lower() or "pec"
    if canale not in CANALI:
        raise ValueError("Canale di notificazione non riconosciuto.")

    esito = _CALCOLO_CANALE[canale](payload)
    giorno_destinatario: date = esito["giorno_destinatario"]

    durata = safe_int(payload.get("not_termine_durata"), 0)
    unita = clean_text(payload.get("not_termine_unita")).lower() or "giorni"
    if unita not in {"giorni", "mesi"}:
        raise ValueError("Unità del termine non riconosciuta: usa giorni o mesi.")
    sospensione = clean_text(payload.get("not_sospensione_feriale")).lower() != "esclusa"

    note = list(esito["notes"])
    passaggi = list(esito["passaggi"])
    termine: Dict[str, Any] = {}
    if durata > 0:
        termine = _termine(giorno_destinatario, durata, unita, sospensione)
        passaggi.extend(termine["passaggi"])
        note.append(
            f"Termine di {durata} {unita} calcolato dal perfezionamento per il destinatario, con "
            "il computo dell'art. 155 c.p.c. (il giorno iniziale non si conta, la scadenza in "
            "giorno festivo o di sabato è prorogata)."
        )
        note.append(
            "Sospensione feriale dal 1° al 31 agosto applicata (L. 742/1969)."
            if sospensione
            else "Sospensione feriale esclusa su indicazione dell'utente (art. 3 L. 742/1969)."
        )

    avvisi = [
        "Il modulo individua il momento del perfezionamento secondo il canale dichiarato: non "
        "verifica la validità della relata, dell'indirizzo del destinatario né dell'elenco "
        "pubblico da cui è tratto.",
        "Il perfezionamento per il notificante e quello per il destinatario sono distinti: il "
        "termine per impugnare o per costituirsi decorre da quello che riguarda la parte onerata.",
    ]
    if canale == "pec":
        avvisi.append(
            "Le date vanno lette sulle ricevute in formato originale (RAC e RdAC), non sul client "
            "di posta: fanno fede l'orario e il riferimento temporale certificati dal gestore."
        )

    righe = [
        {
            "soggetto": "Notificante",
            "momento": _fmt_momento(esito["giorno_notificante"], esito["ora_notificante"]),
            "riferimento": CANALI[canale]["norma"],
        },
        {
            "soggetto": "Destinatario",
            "momento": _fmt_momento(giorno_destinatario, esito["ora_destinatario"]),
            "riferimento": CANALI[canale]["norma"],
        },
    ]

    return {
        "canale": canale,
        "canale_label": CANALI[canale]["label"],
        "riferimento_normativo": CANALI[canale]["norma"],
        "perfezionamento_notificante": _fmt_momento(esito["giorno_notificante"], esito["ora_notificante"]),
        "perfezionamento_destinatario": _fmt_momento(giorno_destinatario, esito["ora_destinatario"]),
        "dies_a_quo": fmt_date_it(giorno_destinatario),
        "differimento_ore_7": bool(esito["differito"]),
        "termine_durata": durata,
        "termine_unita": unita if durata > 0 else "",
        "sospensione_feriale": sospensione,
        "scadenza": termine.get("scadenza", ""),
        "scadenza_senza_proroghe": termine.get("scadenza_senza_proroghe", ""),
        "perfezionamenti": righe,
        "passaggi": passaggi,
        "notes": note,
        "warnings": avvisi,
        "sources": list(FONTI),
    }
