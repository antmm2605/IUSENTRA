"""Le fasi dei riti con gli adempimenti e i termini che la legge vi collega.

Una scheda per rito: le fasi nell'ordine del processo, per ogni fase gli
adempimenti con il termine letterale della norma e, dove esiste, il codice del
template versionato di `pct/termini_processuali.py` che lo calcola. La scheda
non calcola date: cita la regola e rimanda al motore dei termini.
"""

from __future__ import annotations

import re
from typing import Any


def _adempimento(azione: str, termine: str, *fonti: str, template: str = "", parte: str = "") -> dict[str, Any]:
    voce: dict[str, Any] = {"azione": azione, "termine": termine, "fonti": list(fonti)}
    if template:
        voce["template"] = template
    if parte:
        voce["parte"] = parte
    return voce


def _fase(codice: str, nome: str, *adempimenti: dict[str, Any]) -> dict[str, Any]:
    return {"codice": codice, "nome": nome, "fonti": [], "adempimenti": list(adempimenti)}


SCHEDE_RITO: dict[str, dict[str, Any]] = {
    "ordinario": {
        "codice": "ordinario",
        "nome": "Rito ordinario di cognizione (dopo la riforma Cartabia)",
        "base": "c.p.c., artt. 163-bis, 165, 166, 171-bis, 171-ter, 183, 189, 325 e 327",
        "fasi": [
            _fase("introduttiva", "Fase introduttiva",
                  _adempimento("Notificare l'atto di citazione con udienza fissata nel rispetto del termine a comparire", "termini liberi non minori di centoventi giorni fra notificazione e udienza (centocinquanta all'estero)", "cpc_163bis", "l53_art3bis", parte="attore"),
                  _adempimento("Costituirsi iscrivendo la causa a ruolo", "entro dieci giorni dalla notificazione della citazione", "cpc_165", template="CIV_COSTITUZIONE_ATTORE_165", parte="attore"),
                  _adempimento("Costituirsi con comparsa di risposta", "almeno settanta giorni prima dell'udienza di comparizione", "cpc_166", template="CIV_COSTITUZIONE_CONVENUTO_166", parte="convenuto")),
            _fase("verifiche", "Verifiche preliminari",
                  _adempimento("Attendere il decreto del giudice sulla regolarità del contraddittorio", "entro quindici giorni dalla scadenza del termine di costituzione del convenuto", "cpc_171bis")),
            _fase("memorie", "Memorie integrative",
                  _adempimento("Depositare la prima memoria integrativa (domande ed eccezioni conseguenti, precisazione delle conclusioni)", "almeno quaranta giorni prima dell'udienza dell'art. 183", "cpc_171ter", template="CIV_MEMORIA_171_TER_1"),
                  _adempimento("Depositare la seconda memoria integrativa", "nel termine successivo fissato dall'art. 171-ter", "cpc_171ter", template="CIV_MEMORIA_171_TER_2"),
                  _adempimento("Depositare la terza memoria integrativa", "nel termine successivo fissato dall'art. 171-ter", "cpc_171ter", template="CIV_MEMORIA_171_TER_3")),
            _fase("trattazione", "Prima udienza e trattazione",
                  _adempimento("Comparire personalmente all'udienza di prima comparizione e trattazione", "alla data fissata; la mancata comparizione senza giustificato motivo è valutabile ai sensi dell'art. 116", "cpc_183")),
            _fase("istruttoria", "Istruttoria",
                  _adempimento("Assumere le prove ammesse e seguire l'eventuale consulenza tecnica", "nei termini fissati dal giudice istruttore", "cpc_183")),
            _fase("decisoria", "Rimessione al collegio e decisione",
                  _adempimento("Depositare le note di precisazione delle conclusioni", "termine non superiore a sessanta giorni prima dell'udienza di rimessione", "cpc_189", template="CIV_NOTE_CONCLUSIONI_189"),
                  _adempimento("Depositare la comparsa conclusionale", "nel termine perentorio assegnato dal giudice", "cpc_189", template="CIV_CONCLUSIONALI_189"),
                  _adempimento("Depositare la memoria di replica", "nel termine perentorio assegnato dal giudice", "cpc_189", template="CIV_REPLICHE_189")),
            _fase("impugnazione", "Dopo la sentenza",
                  _adempimento("Valutare l'appello", "trenta giorni dalla notificazione della sentenza (termine breve)", "cpc_325", template="CIV_APPELLO_BREVE"),
                  _adempimento("Termine lungo per l'impugnazione", "sei mesi dalla pubblicazione della sentenza, indipendentemente dalla notificazione", "cpc_327", template="CIV_APPELLO_LUNGO"),
                  _adempimento("Ricorso per cassazione", "sessanta giorni dalla notificazione della sentenza", "cpc_325", template="CIV_CASSAZIONE_BREVE")),
        ],
    },
    "semplificato": {
        "codice": "semplificato",
        "nome": "Procedimento semplificato di cognizione",
        "base": "c.p.c., art. 281-undecies",
        "fasi": [
            _fase("introduttiva", "Ricorso e decreto",
                  _adempimento("Depositare il ricorso", "il giudice, entro cinque giorni dalla designazione, fissa con decreto l'udienza e il termine di costituzione del convenuto", "cpc_281undecies", parte="ricorrente"),
                  _adempimento("Notificare ricorso e decreto al convenuto", "prima dell'udienza, nel rispetto del termine assegnato", "cpc_281undecies", "l53_art3bis", parte="ricorrente"),
                  _adempimento("Costituirsi", "non oltre dieci giorni prima dell'udienza", "cpc_281undecies", parte="convenuto")),
            _fase("impugnazione", "Dopo la decisione",
                  _adempimento("Valutare l'appello", "trenta giorni dalla notificazione; sei mesi dalla pubblicazione", "cpc_325", "cpc_327", template="CIV_APPELLO_BREVE")),
        ],
    },
    "lavoro": {
        "codice": "lavoro",
        "nome": "Rito del lavoro",
        "base": "c.p.c., artt. 414, 415, 416, 420, 429, 433, 434 e 435",
        "fasi": [
            _fase("introduttiva", "Ricorso, decreto e notifica",
                  _adempimento("Depositare il ricorso con i documenti", "il giudice fissa l'udienza con decreto entro cinque giorni; fra deposito e udienza non più di sessanta giorni", "cpc_414", "cpc_415", parte="ricorrente"),
                  # Amministrazioni statali: art. 415, settimo comma, c.p.c. rinvia alle leggi speciali (art. 11 R.D. 1611/1933).
                  _adempimento("Notificare ricorso e decreto al convenuto", "prima dell'udienza, nei termini dell'art. 415", "cpc_415", "l53_art3bis", "rd1611_art11", parte="ricorrente"),
                  _adempimento("Costituirsi con memoria difensiva (domande riconvenzionali ed eccezioni a pena di decadenza)", "almeno dieci giorni prima dell'udienza", "cpc_416", "cpc_417bis", parte="convenuto")),
            _fase("discussione", "Udienza di discussione",
                  _adempimento("Comparire personalmente all'udienza di discussione (interrogatorio libero, tentativo di conciliazione, proposta del giudice)", "alla data fissata con il decreto; la mancata comparizione personale senza giustificato motivo è valutabile ai fini del giudizio", "cpc_415", "cpc_420")),
            _fase("decisoria", "Decisione",
                  _adempimento("Pronuncia della sentenza con lettura del dispositivo e delle ragioni della decisione", "nell'udienza, esaurita la discussione; nei casi di particolare complessità deposito nel termine non superiore a sessanta giorni fissato nel dispositivo, con comunicazione alle parti", "cpc_429", "cpc_430")),
            _fase("appello", "Appello",
                  _adempimento("Depositare il ricorso in appello e notificarlo con il decreto", "il presidente fissa l'udienza entro sessanta giorni; l'appellante notifica ricorso e decreto nei dieci giorni successivi al deposito del decreto", "cpc_433", "cpc_435", parte="appellante"),
                  # Nel rito del lavoro l'appello si propone con il deposito del ricorso (art. 434, secondo comma, c.p.c.).
                  _adempimento("Termini per impugnare", "deposito del ricorso in appello entro trenta giorni dalla notificazione della sentenza (quaranta se notificata all'estero); senza notificazione, sei mesi dalla pubblicazione", "cpc_434", "cpc_327", template="CIV_APPELLO_BREVE")),
        ],
    },
    "decreto_ingiuntivo": {
        "codice": "decreto_ingiuntivo",
        "nome": "Procedimento per decreto ingiuntivo",
        "base": "c.p.c., artt. 633, 641, 644, 645, 647 e 654",
        "fasi": [
            _fase("emissione", "Ricorso e decreto",
                  _adempimento("Depositare il ricorso monitorio", "il decreto è emesso entro trenta giorni dal deposito", "cpc_641", parte="ricorrente")),
            _fase("notifica", "Notifica del decreto",
                  _adempimento("Notificare il decreto all'ingiunto", "entro sessanta giorni dalla pronuncia (novanta all'estero), altrimenti il decreto è inefficace", "cpc_644", template="CIV_DI_NOTIFICA_644", parte="ricorrente")),
            _fase("opposizione", "Opposizione",
                  _adempimento("Proporre opposizione", "entro quaranta giorni dalla notificazione del decreto", "cpc_641", template="CIV_OPPOSIZIONE_DI", parte="ingiunto")),
            _fase("esecutorietà", "Esecutorietà",
                  _adempimento("Chiedere la dichiarazione di esecutorietà", "decorso il termine di opposizione senza opposizione o senza costituzione dell'opponente, su istanza anche verbale", "cpc_647", parte="ricorrente")),
            _fase("precetto", "Precetto ed esecuzione",
                  _adempimento("Notificare il precetto menzionando il decreto di esecutorietà", "non occorre una nuova notificazione del decreto esecutivo; il precetto intima di adempiere entro un termine non minore di dieci giorni", "cpc_654", "cpc_480", template="ESE_PRECETTO_ADEMPIMENTO_10GG", parte="ricorrente")),
        ],
    },
    "esecuzione": {
        "codice": "esecuzione",
        "nome": "Esecuzione forzata",
        "base": "c.p.c., artt. 480, 481, 497, 518, 543, 557, 615 e 617",
        "fasi": [
            _fase("precetto", "Precetto",
                  _adempimento("Notificare il precetto con l'intimazione ad adempiere", "termine non minore di dieci giorni", "cpc_480", template="ESE_PRECETTO_ADEMPIMENTO_10GG", parte="creditore"),
                  _adempimento("Iniziare l'esecuzione", "entro novanta giorni dalla notificazione del precetto, altrimenti il precetto perde efficacia", "cpc_481", template="ESE_PRECETTO_EFFICACIA_90GG", parte="creditore"),
                  _adempimento("Opposizione agli atti esecutivi", "venti giorni dalla notificazione del titolo esecutivo o del precetto", "cpc_617", template="ESE_OPPOSIZIONE_ATTI_617", parte="debitore"),
                  _adempimento("Opposizione all'esecuzione", "prima dell'inizio dell'esecuzione, con citazione davanti al giudice competente", "cpc_615", parte="debitore")),
            _fase("pignoramento", "Pignoramento e iscrizione a ruolo",
                  _adempimento("Iscrivere a ruolo il pignoramento mobiliare", "nel termine di legge dalla consegna del verbale", "cpc_518", template="ESE_ISCRIZIONE_RUOLO_MOBILIARE", parte="creditore"),
                  _adempimento("Iscrivere a ruolo il pignoramento presso terzi", "nel termine di legge dalla notificazione dell'atto", "cpc_543", template="ESE_ISCRIZIONE_RUOLO_PRESSO_TERZI", parte="creditore"),
                  _adempimento("Iscrivere a ruolo il pignoramento immobiliare", "entro quindici giorni dalla consegna dell'atto di pignoramento", "cpc_557", template="ESE_ISCRIZIONE_RUOLO_IMMOBILIARE", parte="creditore"),
                  _adempimento("Chiedere l'assegnazione o la vendita", "entro quarantacinque giorni dal pignoramento, altrimenti perde efficacia", "cpc_497", parte="creditore")),
            _fase("presso_terzi", "Espropriazione presso terzi: dichiarazione del terzo e assegnazione",
                  _adempimento("Verificare la dichiarazione del terzo", "il terzo la invia al creditore con raccomandata o PEC e specifica le somme o le cose dovute", "cpc_547", parte="creditore"),
                  _adempimento("Se la dichiarazione manca: chiedere all'udienza un'udienza successiva e notificare l'ordinanza al terzo", "l'ordinanza si notifica al terzo almeno dieci giorni prima della nuova udienza; se il terzo non compare il credito si considera non contestato", "cpc_548", parte="creditore"),
                  _adempimento("Comparire alle udienze del giudice dell'esecuzione", "se nessuna parte compare il giudice fissa un'udienza successiva; alla seconda diserzione dichiara l'estinzione", "cpc_631", parte="creditore")),
        ],
    },
    "volontaria": {
        "codice": "volontaria",
        "nome": "Volontaria giurisdizione: procedimento in camera di consiglio",
        "base": "c.p.c., artt. 737, 739 e 742",
        "fasi": [
            _fase("ricorso", "Ricorso e decreto",
                  _adempimento("Depositare il ricorso al giudice competente", "il provvedimento ha forma di decreto motivato, salvo che la legge disponga altrimenti", "cpc_737", parte="ricorrente")),
            _fase("reclamo", "Reclamo",
                  _adempimento("Valutare il reclamo contro il decreto", "dieci giorni dalla comunicazione del decreto (una sola parte) o dalla notificazione (più parti), a pena di decadenza", "cpc_739")),
            _fase("revoca", "Modifica o revoca",
                  _adempimento("Chiedere la modifica o la revoca del decreto se mutano le circostanze", "in ogni tempo, salvi i diritti dei terzi in buona fede", "cpc_742")),
        ],
    },
    "cautelare": {
        "codice": "cautelare",
        "nome": "Procedimento cautelare",
        "base": "c.p.c., art. 669-terdecies",
        "fasi": [
            _fase("reclamo", "Reclamo",
                  _adempimento("Proporre reclamo contro l'ordinanza cautelare", "quindici giorni dalla pronuncia in udienza ovvero dalla comunicazione o notificazione se anteriore", "cpc_669terdecies", template="CIV_RECLAMO_CAUTELARE_669_TERDECIES")),
        ],
    },
    "mediazione": {
        "codice": "mediazione",
        "nome": "Mediazione civile e commerciale",
        "base": "D.Lgs. 28/2010, artt. 5, 6 e 8",
        "fasi": [
            _fase("avvio", "Domanda e primo incontro",
                  _adempimento("Verificare se la mediazione è condizione di procedibilità", "nelle materie dell'art. 5 (condominio, diritti reali, divisione, successioni, locazione, contratti bancari e assicurativi, responsabilità sanitaria e altre)", "dlgs28_art5"),
                  _adempimento("Depositare la domanda e partecipare al primo incontro", "il primo incontro si tiene non prima di venti e non oltre quaranta giorni dal deposito della domanda", "dlgs28_art8")),
            _fase("svolgimento", "Svolgimento",
                  _adempimento("Concludere il procedimento", "durata di sei mesi, prorogabile per periodi non superiori a tre mesi", "dlgs28_art6")),
        ],
    },
    "amministrativo": {
        "codice": "amministrativo",
        "nome": "Processo amministrativo",
        "base": "c.p.a., artt. 29, 45, 46 e 92",
        "fasi": [
            _fase("introduttiva", "Ricorso",
                  _adempimento("Notificare il ricorso per annullamento", "sessanta giorni (decadenza)", "cpa_29", parte="ricorrente"),
                  _adempimento("Depositare il ricorso notificato", "trenta giorni dal perfezionamento dell'ultima notificazione", "cpa_45", parte="ricorrente"),
                  _adempimento("Costituirsi", "sessanta giorni dal perfezionamento della notificazione", "cpa_46", parte="parte intimata")),
            _fase("impugnazione", "Impugnazione",
                  _adempimento("Notificare l'impugnazione", "sessanta giorni dalla notificazione della sentenza", "cpa_92")),
        ],
    },
    "tributario": {
        "codice": "tributario",
        "nome": "Processo tributario (Testo unico D.Lgs. 175/2024)",
        "base": "D.Lgs. 175/2024, artt. 61, 64, 67, 68 e 69",
        "fasi": [
            _fase("introduttiva", "Ricorso e costituzione",
                  _adempimento("Proporre il ricorso notificandolo all'ente", "sessanta giorni dalla notificazione dell'atto impugnato, a pena di inammissibilità", "tu175_art67", "tu175_art64", parte="ricorrente"),
                  _adempimento("Costituirsi depositando telematicamente il ricorso", "trenta giorni dalla proposizione, a pena di inammissibilità", "tu175_art68", parte="ricorrente"),
                  _adempimento("Costituzione dell'ente", "sessanta giorni dalla notifica del ricorso", "tu175_art69", parte="resistente")),
        ],
    },
    "penale": {
        "codice": "penale",
        "nome": "Procedimento penale: adempimenti del difensore",
        "base": "c.p.p., artt. 111-bis, 415-bis, 429, 552 e 585",
        "fasi": [
            _fase("indagini", "Conclusione delle indagini",
                  _adempimento("Presentare memorie, documenti e richiesta di interrogatorio dopo l'avviso di conclusione delle indagini", "entro venti giorni dalla notifica dell'avviso", "cpp_415bis", parte="indagato")),
            _fase("giudizio", "Rinvio a giudizio e citazione",
                  _adempimento("Preparare l'udienza fissata dal decreto che dispone il giudizio", "fra il decreto e la data del giudizio deve intercorrere un termine non inferiore a venti giorni", "cpp_429"),
                  _adempimento("Verificare il decreto di citazione a giudizio", "contenuti e avvisi obbligatori dell'art. 552", "cpp_552")),
            _fase("depositi", "Depositi",
                  _adempimento("Depositare atti, richieste e memorie con modalità telematiche", "in ogni stato e grado del procedimento", "cpp_111bis")),
            _fase("impugnazione", "Impugnazione",
                  _adempimento("Proporre impugnazione", "quindici, trenta o quarantacinque giorni secondo l'art. 544 c.p.p.; più quindici giorni per il difensore dell'imputato giudicato in assenza", "cpp_585")),
        ],
    },
}

_RITO_PER_TIPO = {
    "CIVILE": "ordinario", "LAVORO": "lavoro", "FAMIGLIA": "ordinario", "SUCCESSIONI": "ordinario",
    "PENALE": "penale", "AMMINISTRATIVO": "amministrativo", "TRIBUTARIO": "tributario", "STRAGIUDIZIALE": "mediazione",
}
# Indizi come inizio di parola: «tar» dentro «volontaria», «testamentaria» o «notarile» non è il TAR, e
# «amministrazione di sostegno» non è il processo amministrativo (serve «amministrativ»).
_RITO_PER_PROCEDIMENTO = (
    ("semplificat", "semplificato"), ("281", "semplificato"), ("lavoro", "lavoro"), ("ingiunt", "decreto_ingiuntivo"),
    ("monitor", "decreto_ingiuntivo"), ("esecu", "esecuzione"), ("pignor", "esecuzione"), ("precett", "esecuzione"),
    ("espropriaz", "esecuzione"), ("volontaria", "volontaria"), ("giudice tutelare", "volontaria"),
    # Amministrazione di sostegno: ricorso al giudice tutelare, procedimento camerale (artt. 720-bis e 737 ss. c.p.c.).
    ("amministrazione di sostegno", "volontaria"),
    ("camera di consiglio", "volontaria"),
    ("cautel", "cautelare"), ("mediaz", "mediazione"), ("amministrativ", "amministrativo"), ("tar", "amministrativo"),
    ("t.a.r", "amministrativo"), ("tribut", "tributario"), ("penal", "penale"), ("ordinar", "ordinario"),
)
_PAROLE_INTERE = {"tar", "t.a.r"}

# Il codice oggetto ministeriale (catalogo PST, pct/data/cataloghi/codici_oggetto_pst.json): le prime tre cifre sono il
# gruppo («codicePadre») e dicono il rito. 010/050/210: ingiunzione (artt. 633 ss. c.p.c.); 011-019, 051-059, 211, 310:
# cautelari (artt. 669-bis ss.); 2xx: lavoro e previdenza (artt. 409 ss.); 4xx: volontaria giurisdizione (artt. 737 ss.);
# 5xx: esecuzioni mobiliari e presso terzi (artt. 513 ss., 543 ss.); 6xx: esecuzioni immobiliari (artt. 555 ss.).
_RITO_PER_GRUPPO_PST = {
    **{gruppo: "decreto_ingiuntivo" for gruppo in ("010", "050", "210")},
    **{gruppo: "cautelare" for gruppo in ("011", "012", "014", "015", "017", "019", "051", "052", "053", "055", "059", "211", "310")},
}
_RITO_PER_CLASSE_PST = {"2": "lavoro", "4": "volontaria", "5": "esecuzione", "6": "esecuzione"}
_RITO_PER_AREA_PST = {
    "lavoro e previdenza": "lavoro", "volontaria giurisdizione": "volontaria", "esecuzioni mobiliari / obblighi": "esecuzione",
    "esecuzioni immobiliari": "esecuzione",
}
# Gli atti del fascicolo, quando profilo e codice oggetto tacciono: l'atto di pignoramento e il precetto aprono
# l'esecuzione (artt. 480, 492, 543 c.p.c.), il ricorso monitorio il procedimento d'ingiunzione (art. 638 c.p.c.).
_RITO_PER_ATTO = (
    (r"\batto\s+di\s+pignoramento|\bprecetto\b|istanza\s+ex\s+art\.?\s*492", "esecuzione"),
    (r"opposizione\s+a\s+decreto\s+ingiuntivo", "ordinario"),
    (r"ricorso\s+per\s+decreto\s+ingiuntivo", "decreto_ingiuntivo"),
    (r"ricorso\s+in\s+materia\s+di\s+lavoro|\b414\b", "lavoro"),
)


def _indizio_presente(indizio: str, testo: str) -> bool:
    fine = r"(?![a-zà-ù])" if indizio in _PAROLE_INTERE else ""
    return re.search(rf"(?<![a-zà-ù0-9]){re.escape(indizio)}{fine}", testo) is not None


def _da_indizi(testo: str, *, senza_generico: bool = False) -> str:
    testo = " ".join(str(testo or "").split()).lower()
    for indizio, codice in _RITO_PER_PROCEDIMENTO:
        if senza_generico and codice == "ordinario":
            continue
        if _indizio_presente(indizio, testo):
            return codice
    return ""


def rito_da_codice_oggetto(codice_oggetto: str, area: str = "") -> str:
    """Il rito dal codice oggetto ministeriale PST (sei cifre) o, in mancanza, dalla sua area del catalogo."""
    codice = re.sub(r"\D", "", str(codice_oggetto or ""))[:6]
    if len(codice) == 6:
        if codice[:3] in _RITO_PER_GRUPPO_PST:
            return _RITO_PER_GRUPPO_PST[codice[:3]]
        if codice[0] in _RITO_PER_CLASSE_PST:
            return _RITO_PER_CLASSE_PST[codice[0]]
    return _RITO_PER_AREA_PST.get(" ".join(str(area or "").split()).lower(), "")


def rito_per_fascicolo(tipo: str, tipo_procedimento: str = "", *, codice_oggetto: str = "", oggetto: str = "", area: str = "",
                       etichette_atti: tuple[str, ...] | list[str] = ()) -> str:
    """Il codice del rito, dalla fonte più certa alla più generica.

    1. il tipo di procedimento dichiarato nel profilo, se specifico (non il generico «ordinario»);
    2. il codice oggetto ministeriale PST (``rito_da_codice_oggetto``) o l'area del catalogo;
    3. l'oggetto del fascicolo per esteso («Espropriazione mobiliare presso terzi», «Decreto ingiuntivo»);
    4. gli atti del fascicolo (atto di pignoramento, precetto, ricorso monitorio);
    5. il tipo di fascicolo (civile → cognizione ordinaria, lavoro → rito del lavoro…), e il «ordinario» dichiarato.

    Collaudo 10/11/2026: un'espropriazione presso terzi (codice 510002), un decreto ingiuntivo del giudice di pace
    (010001) e un'autorizzazione del giudice tutelare (413014) risultavano «cognizione ordinaria Cartabia» perché si
    guardava solo il tipo «civile».
    """
    dichiarato = _da_indizi(tipo_procedimento, senza_generico=True)
    if dichiarato:
        return dichiarato
    dal_codice = rito_da_codice_oggetto(codice_oggetto, area)
    if dal_codice:
        return dal_codice
    dall_oggetto = _da_indizi(oggetto, senza_generico=True)
    if dall_oggetto:
        return dall_oggetto
    for espressione, codice in _RITO_PER_ATTO:
        if any(re.search(espressione, str(etichetta or ""), re.I) for etichetta in etichette_atti):
            return codice
    return _da_indizi(tipo_procedimento) or _RITO_PER_TIPO.get(" ".join(str(tipo or "").split()).upper(), "")


def rito_da_intestazione(intestazione: dict[str, Any], etichette_atti: tuple[str, ...] | list[str] = ()) -> str:
    """Il rito dall'intestazione della Lettura (tipo, rito dichiarato, codice oggetto PST, oggetto, area) e dagli atti."""
    voce = intestazione or {}
    return rito_per_fascicolo(voce.get("tipo", ""), voce.get("rito", ""), codice_oggetto=voce.get("codice_oggetto_pst", ""),
                              oggetto=voce.get("oggetto", ""), area=voce.get("area", ""), etichette_atti=etichette_atti)


def scheda_rito(codice: str) -> dict[str, Any]:
    scheda = SCHEDE_RITO.get(" ".join(str(codice or "").split()).lower())
    return dict(scheda) if scheda else {}


__all__ = ["SCHEDE_RITO", "rito_da_codice_oggetto", "rito_da_intestazione", "rito_per_fascicolo", "scheda_rito"]
