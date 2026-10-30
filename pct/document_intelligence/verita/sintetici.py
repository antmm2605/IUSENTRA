"""Documenti inventati per tutte le voci del catalogo, a integrazione dei documenti reali dello studio.

Richiesta dell'avvocato del 30/10/2026: ampliare l'addestramento a tutte le tipologie di atti e documenti, anche
quelle che oggi lo studio non ha, con dati inventati. Due sorgenti:

- le regole di titolo del catalogo (titolo, riscontri nel corpo, norma di riferimento), da cui si generano titoli
  e frasi che le regole stesse riconoscono;
- modelli scritti qui per le voci che il catalogo riconosce dal contenuto (sentenze, decreti, verbali, procure,
  contratti, documenti d'identità, PEC…).

Parti, uffici, numeri e luoghi sono di fantasia. Ogni documento entra nel dataset solo se il classificatore
completo del catalogo (`catalog_resolver._classify_indexed_content`, lo stesso dei testi reali) gli assegna
proprio la voce prevista: l'etichetta di un esempio inventato è quella che le regole governate darebbero, mai una
scelta libera. Gli esempi inventati servono solo all'addestramento, mai alla verifica.
"""

from __future__ import annotations

import random
import re
import re._parser as sre_parse  # parser dei pattern della libreria standard
from collections.abc import Callable, Iterator
from dataclasses import dataclass

_SEME = 20261030
CONFIDENZA_MINIMA = 90

# Nomi, luoghi e uffici di fantasia: nessun dato reale.
_COGNOMI = ("Esposito Demo", "Ferri Prova", "Galli Esempio", "Landi Fittizio", "Marini Campione", "Neri Modello",
            "Orsini Simulato", "Pace Inventato", "Riva Esempio", "Sala Prova", "Testa Fittizia", "Valli Campione",
            "Bassi Esempio", "Conti Prova", "Donati Fittizio", "Fabbri Campione")
_NOMI = ("Alfa", "Bruno", "Carla", "Dario", "Elena", "Franco", "Giulia", "Ilario", "Luisa", "Marco", "Nadia", "Paolo",
         "Rita", "Sergio", "Teresa", "Ugo")
_SOCIETA = ("Esempio S.r.l.", "Prova Servizi S.p.A.", "Campione Costruzioni S.r.l.", "Fittizia Logistica S.n.c.")
_CITTA = ("Città Esempio", "Borgo Prova", "Valle Fittizia", "Porto Campione", "Monte Modello", "Lago Inventato")
_UFFICI = {
    "civile": ("TRIBUNALE ORDINARIO DI {c}", "CORTE D'APPELLO DI {c}", "UFFICIO DEL GIUDICE DI PACE DI {c}",
               "TRIBUNALE DI {c}\nSEZIONE CIVILE"),
    "lavoro": ("TRIBUNALE DI {c}\nSEZIONE LAVORO", "TRIBUNALE ORDINARIO DI {c}\nSezione Lavoro e Previdenza",
               "CORTE D'APPELLO DI {c}\nSEZIONE LAVORO"),
    "penale": ("TRIBUNALE DI {c}\nSEZIONE PENALE", "PROCURA DELLA REPUBBLICA PRESSO IL TRIBUNALE DI {c}",
               "TRIBUNALE DI {c}\nUfficio del Giudice per le indagini preliminari"),
    "amministrativo": ("TRIBUNALE AMMINISTRATIVO REGIONALE DI {c}", "CONSIGLIO DI STATO\nSEZIONE QUARTA"),
    "tributario": ("CORTE DI GIUSTIZIA TRIBUTARIA DI PRIMO GRADO DI {c}",),
    "studio": ("STUDIO LEGALE ESEMPIO\nVia dell'Esempio n. 1 - {c}", "Avv. Studio Prova\n{c}"),
}
_FRASI = (
    "Il presente atto è redatto nell'interesse di {p}, come in epigrafe rappresentato e difeso.",
    "Si richiamano integralmente i documenti già prodotti nel fascicolo telematico.",
    "Si allegano i documenti indicati nell'indice dei documenti.",
    "Visti gli atti del procedimento iscritto al n. {n}/{a} R.G.",
    "Il sottoscritto difensore attesta la conformità della copia informatica all'originale.",
    "Si chiede l'accoglimento delle conclusioni come sopra rassegnate, con vittoria di spese e compensi.",
    "In fatto: le parti hanno intrattenuto rapporti dal {d}, documentati in atti.",
    "In diritto: la domanda è fondata per le ragioni che seguono.",
    "Si producono in copia i documenti numerati da 1 a {k}.",
    "Ai fini del contributo unificato si dichiara che il valore della causa è indeterminabile.",
    "Con riserva di ulteriormente dedurre e produrre nei termini di legge.",
    "Si comunica per quanto di competenza.",
)
_CODA = ("{c}, {d}", "Con osservanza.", "Firmato digitalmente da {p}", "Pagina 1 di {k}", "Avv. {p}")
_OCR = str.maketrans({"o": "0", "l": "1", "e": "c", "a": "u", "i": "l"})


@dataclass(frozen=True, slots=True)
class DocumentoInventato:
    voce: str
    origine: str  # id della regola di titolo o del modello di contenuto
    testo: str


@dataclass(slots=True)
class _Dati:
    parte: str
    controparte: str
    citta: str
    numero: int
    anno: int
    data: str
    pagine: int


def _dati(g: random.Random) -> _Dati:
    anno = g.choice((2022, 2023, 2024, 2025, 2026))
    return _Dati(
        parte=f"{g.choice(_COGNOMI)} {g.choice(_NOMI)}",
        controparte=g.choice(_SOCIETA) if g.random() < 0.5 else f"{g.choice(_COGNOMI)} {g.choice(_NOMI)}",
        citta=g.choice(_CITTA), numero=g.randint(100, 9999), anno=anno,
        data=f"{g.randint(1, 28):02d}/{g.randint(1, 12):02d}/{anno}", pagine=g.randint(2, 12),
    )


# --- regole di titolo ------------------------------------------------------------------------------------------

def _esempio_da_pattern(pattern: str, g: random.Random) -> str:
    """Una stringa che soddisfa il pattern."""
    return _visita(sre_parse.parse(pattern, re.IGNORECASE), g)


def _visita(nodi, g: random.Random) -> str:
    parti: list[str] = []
    for opcode, valore in nodi:
        nome = str(opcode)
        if nome == "LITERAL":
            parti.append(chr(valore))
        elif nome == "NOT_LITERAL":
            parti.append("a" if chr(valore) != "a" else "b")
        elif nome == "ANY":
            parti.append("a")
        elif nome == "IN":
            parti.append(_in(valore))
        elif nome == "BRANCH":
            parti.append(_visita(g.choice(valore[1]), g))
        elif nome == "SUBPATTERN":
            parti.append(_visita(valore[-1], g))
        elif nome in {"MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"}:
            minimo, massimo, corpo = valore
            volte = minimo if minimo > 0 else g.choice((0, 1)) if massimo else 0
            parti.extend(_visita(corpo, g) for _ in range(volte))
        elif nome == "ATOMIC_GROUP":
            parti.append(_visita(valore, g))
        # AT (\b, ^, $), ASSERT, ASSERT_NOT, GROUPREF: nessun carattere.
    return "".join(parti)


def _in(insieme) -> str:
    negato = any(str(op) == "NEGATE" for op, _ in insieme)
    for opcode, valore in insieme:
        nome = str(opcode)
        if negato:
            return "a" if nome != "LITERAL" or chr(valore) != "a" else "b"
        if nome == "LITERAL":
            return chr(valore)
        if nome == "RANGE":
            return chr(valore[0])
        if nome == "CATEGORY":
            categoria = str(valore)
            return "0" if "DIGIT" in categoria else " " if "SPACE" in categoria else "a"
    return "a"


def _materia(regola) -> str:
    testo = f"{regola.fonte} {regola.evidence} {regola.id}".casefold()
    if any(s in testo for s in ("c.p.p", "cpp", "penal", "querel", "indagat", "imputat", "reato")):
        return "penale"
    if any(s in testo for s in ("c.p.a", "cpa", "amministrativ", "tar", "consiglio di stato")):
        return "amministrativo"
    if any(s in testo for s in ("tribut", "546/1992", "fisc")):
        return "tributario"
    if any(s in testo for s in ("lavoro", "414", "416", "previdenz")):
        return "lavoro"
    if regola.section in {"comunicazioni", "allegati"}:
        return "studio"
    return "civile"


def _testo_da_regola(regola, g: random.Random) -> str:
    d = _dati(g)
    intestazione = g.choice(_UFFICI[_materia(regola)]).format(c=d.citta.upper())
    titolo = regola.label if g.random() < 0.5 else _esempio_da_pattern(regola.titolo, g)
    titolo = titolo.upper() if g.random() < 0.6 else titolo
    riscontro = _esempio_da_pattern(regola.conferma, g)
    righe = [intestazione, "", titolo, ""]
    if g.random() < 0.7:
        righe.append(f"nel procedimento n. {d.numero}/{d.anno} R.G. tra {d.parte} e {d.controparte}")
    righe.append(f"{regola.evidence[:1].upper()}{regola.evidence[1:]}: {riscontro}.")
    righe.extend(_corpo(d, g))
    return _rifinisci("\n".join(righe), d, g)


# --- modelli per le voci riconosciute dal contenuto ---------------------------------------------------------

def _sentenza(d: _Dati, g: random.Random) -> str:
    sezione = g.choice(("", "SEZIONE LAVORO\n", "SEZIONE SECONDA CIVILE\n"))
    return (f"TRIBUNALE ORDINARIO DI {d.citta.upper()}\n{sezione}REPUBBLICA ITALIANA\nIN NOME DEL POPOLO ITALIANO\n"
            f"Il Tribunale, in composizione monocratica, ha pronunciato la seguente\nSENTENZA\n"
            f"nella causa civile iscritta al n. {d.numero}/{d.anno} R.G. promossa da {d.parte} contro {d.controparte}\n"
            f"MOTIVI DELLA DECISIONE\n{g.choice(_FRASI).format(p=d.parte, n=d.numero, a=d.anno, d=d.data, k=d.pagine)}\n"
            f"P.Q.M.\nil Tribunale, definitivamente pronunciando, {g.choice(('accoglie la domanda', 'rigetta il ricorso', 'condanna parte convenuta al pagamento delle spese di lite'))}.\n"
            f"{d.citta}, {d.data}\nIl Giudice")


def _procura(d: _Dati, g: random.Random) -> str:
    return (f"{g.choice(('PROCURA ALLE LITI', 'Procura alle liti', 'PROCURA SPECIALE ALLE LITI'))}\n"
            f"Io sottoscritto {d.parte} nomino e costituisco mio procuratore e difensore l'Avv. Studio Prova, "
            f"conferendo ogni facoltà di legge, ivi compresa quella di transigere e conciliare, nel giudizio contro {d.controparte}.\n"
            f"Eleggo domicilio presso lo studio del difensore. Autorizzo il trattamento dei dati personali.\n"
            f"{d.citta}, {d.data}\nFirma {d.parte}\nÈ autentica la firma\nAvv. Studio Prova")


def _verbale(d: _Dati, g: random.Random) -> str:
    return (f"TRIBUNALE DI {d.citta.upper()}\nVERBALE DI UDIENZA\nCausa n. {d.numero}/{d.anno} R.G.\n"
            f"Oggi {d.data}, innanzi al Giudice, sono comparsi l'Avv. Studio Prova per {d.parte} "
            f"e l'Avv. Esempio per {d.controparte}.\nI procuratori si riportano ai propri atti.\n"
            f"Il Giudice rinvia la causa all'udienza del {g.randint(1, 28):02d}/{g.randint(1, 12):02d}/{d.anno + 1} per la discussione.\n"
            f"Il Giudice\nIl Cancelliere")


def _decreto_fissazione(d: _Dati, g: random.Random) -> str:
    return (f"TRIBUNALE DI {d.citta.upper()}\nSEZIONE LAVORO\nDECRETO DI FISSAZIONE UDIENZA\n"
            f"Il Giudice del lavoro, letto il ricorso depositato da {d.parte} contro {d.controparte} (n. {d.numero}/{d.anno} R.G.),\n"
            f"visto l'art. 415 c.p.c.,\nFISSA\nper la discussione l'udienza del {g.randint(1, 28):02d}/{g.randint(1, 12):02d}/{d.anno + 1}, ore 9:30,\n"
            f"assegnando al ricorrente termine per la notifica del ricorso e del presente decreto.\n{d.citta}, {d.data}\nIl Giudice")


def _contratto_lavoro(d: _Dati, g: random.Random) -> str:
    return (f"CONTRATTO INDIVIDUALE DI LAVORO A TEMPO {g.choice(('INDETERMINATO', 'DETERMINATO'))}\n"
            f"Tra {d.controparte}, datore di lavoro, e {d.parte}, lavoratore,\nsi conviene e si stipula quanto segue:\n"
            f"1. Il lavoratore è assunto con la qualifica di impiegato, livello {g.randint(1, 7)} del CCNL applicato.\n"
            f"2. La retribuzione mensile lorda è di euro {g.randint(1200, 3500)},00.\n3. Il periodo di prova è di {g.choice((30, 60, 90))} giorni.\n"
            f"{d.citta}, {d.data}\nIl datore di lavoro\nIl lavoratore")


def _carta_identita(d: _Dati, g: random.Random) -> str:
    return (f"REPUBBLICA ITALIANA\nCARTA DI IDENTITÀ / IDENTITY CARD\nCOGNOME / SURNAME\n{d.parte.split()[0].upper()}\n"
            f"NOME / NAME\n{d.parte.split()[-1].upper()}\nLUOGO E DATA DI NASCITA\n{d.citta.upper()} {d.data}\n"
            f"CITTADINANZA ITALIANA\nSCADENZA / EXPIRY {g.randint(1, 28):02d}.{g.randint(1, 12):02d}.{d.anno + 10}\n"
            f"COMUNE DI {d.citta.upper()}")


def _richiesta_pagamento(d: _Dati, g: random.Random) -> str:
    return (f"STUDIO LEGALE ESEMPIO\nAvv. Studio Prova\nVia dell'Esempio n. 1 - {d.citta}\n{d.citta}, {d.data}\n"
            f"Spett.le {d.controparte}\nA mezzo PEC\nOggetto: Richiesta pagamento - {d.parte}\n"
            f"In nome e per conto del mio assistito {d.parte}, Vi invito a corrispondere entro quindici giorni dal ricevimento "
            f"della presente la somma di euro {g.randint(500, 20000)},00 a titolo di corrispettivo non pagato.\n"
            f"In mancanza, sarò costretto ad agire in giudizio senza ulteriore avviso.\nDistinti saluti\nAvv. Studio Prova")


def _messaggio_pec(d: _Dati, g: random.Random) -> str:
    return (f"Oggetto: {g.choice(('Invio documentazione', 'Trasmissione atti', 'Riscontro'))} - {d.parte}\n"
            f"Mittente: studio.prova@pec.esempio.it\nDestinatari: {d.controparte.split()[0].lower()}@pec.esempio.it\n"
            f"Data: {d.data} 10:{g.randint(10, 59)}\nTipo: messaggio di posta certificata\n"
            f"Corpo email:\nSi trasmette in allegato la documentazione relativa alla pratica {d.parte}.\n"
            f"Cordiali saluti\nAvv. Studio Prova")


def _note_trattazione(d: _Dati, g: random.Random) -> str:
    return (f"TRIBUNALE DI {d.citta.upper()}\nNOTE DI TRATTAZIONE SCRITTA\n(art. 127-ter c.p.c.)\n"
            f"nella causa n. {d.numero}/{d.anno} R.G. per {d.parte} contro {d.controparte}\n"
            f"In vista dell'udienza sostituita dal deposito di note scritte, il sottoscritto difensore "
            f"si riporta a tutte le difese e conclusioni già rassegnate e chiede che la causa sia trattenuta in decisione.\n"
            f"{d.citta}, {d.data}\nAvv. Studio Prova")


def _gg(d: _Dati, g: random.Random, scarto: int = 0) -> str:
    return f"{g.randint(1, 28):02d}/{g.randint(1, 12):02d}/{d.anno + scarto}"


def _nota_iscrizione(d: _Dati, g: random.Random) -> str:
    ufficio = g.choice(("TRIBUNALE ORDINARIO DI", "TRIBUNALE DI", "GIUDICE DI PACE DI"))
    return (f"{g.choice(('NOTA DI ISCRIZIONE A RUOLO', 'Nota di iscrizione a ruolo', 'NOTA D’ISCRIZIONE A RUOLO'))}\n"
            f"{ufficio} {d.citta.upper()}\n(nota di accompagnamento ex art. 71 disp. att. c.p.c.)\n"
            f"Attore/Ricorrente: {d.parte}\nConvenuto/Resistente: {d.controparte}\n"
            f"Procuratore: Avv. Studio Prova\nOggetto della domanda: {g.choice(('inadempimento contrattuale', 'risarcimento danni', 'pagamento somme'))}\n"
            f"Codice oggetto: {g.randint(100000, 199999)}\nValore della causa: euro {g.randint(1000, 90000)},00\n"
            f"Contributo unificato versato: euro {g.choice((98, 237, 518, 759))},00\nData: {d.data}")


def _indice_documenti(d: _Dati, g: random.Random) -> str:
    voci = ("Contratto", "Fatture", "Diffida", "Estratto conto", "Corrispondenza", "Ricevute di pagamento")
    elenco = "\n".join(f"{n}. {v}" for n, v in enumerate(g.sample(voci, k=g.randint(3, 6)), start=1))
    return (f"{g.choice(('INDICE DEI DOCUMENTI', 'Indice dei documenti', 'INDICE DOCUMENTI'))}\n"
            f"{g.choice(('depositati con il deposito telematico', 'prodotti ai sensi dell’art. 74 disp. att. c.p.c.'))}\n"
            f"nella causa n. {d.numero}/{d.anno} R.G. - {d.parte} contro {d.controparte}\n{elenco}")


def _ricevuta_cu(d: _Dati, g: random.Random) -> str:
    importo = g.choice((43, 98, 118, 237, 518, 759, 1214))
    return (f"{g.choice(('RICEVUTA DI PAGAMENTO', 'Ricevuta telematica pagoPA', 'RICEVUTA TELEMATICA'))}\n"
            f"Ente creditore: Ministero della Giustizia\nCausale: contributo unificato - "
            f"{g.choice(('Tribunale', 'Corte d’Appello', 'Giudice di Pace'))} di {d.citta}\n"
            f"Importo pagato: euro {importo},00\nData pagamento: {d.data}\n"
            f"Codice IUV: {g.randint(10**16, 10**17 - 1)}\nPagatore: {d.parte}\nEsito: pagamento eseguito")


def _esenzione_cu(d: _Dati, g: random.Random) -> str:
    return (f"DICHIARAZIONE DI ESENZIONE DAL CONTRIBUTO UNIFICATO\n"
            f"Il sottoscritto Avv. Studio Prova, difensore di {d.parte}, dichiara che il procedimento n. {d.numero}/{d.anno} "
            f"è esente dal contributo unificato ai sensi dell'art. 10 D.P.R. 115/2002, "
            f"{g.choice(('trattandosi di controversia di previdenza', 'essendo la parte titolare di reddito inferiore alla soglia', 'trattandosi di procedimento esente'))}.\n"
            f"{d.citta}, {d.data}\nAvv. Studio Prova")


def _invito_cu(d: _Dati, g: random.Random) -> str:
    return (f"TRIBUNALE DI {d.citta.upper()}\nCANCELLERIA\nINVITO AL PAGAMENTO DEL CONTRIBUTO UNIFICATO\n"
            f"ai sensi dell'art. 248 D.P.R. 115/2002\nProcedimento n. {d.numero}/{d.anno} R.G. - parte {d.parte}\n"
            f"Si invita la parte a regolarizzare il pagamento del contributo unificato dovuto, pari a euro "
            f"{g.choice((98, 237, 518))},00, entro trenta giorni dalla notifica del presente invito.\nIl Funzionario")


def _patrocinio(d: _Dati, g: random.Random) -> str:
    return (f"CONSIGLIO DELL'ORDINE DEGLI AVVOCATI DI {d.citta.upper()}\n"
            f"DELIBERA DI AMMISSIONE AL PATROCINIO A SPESE DELLO STATO\n"
            f"Vista l'istanza presentata da {d.parte} in data {d.data}, ai sensi degli artt. 74 e seguenti D.P.R. 115/2002,\n"
            f"il Consiglio AMMETTE in via anticipata e provvisoria l'istante al gratuito patrocinio per la causa contro {d.controparte}.\n"
            f"Il Consigliere segretario")


def _proforma(d: _Dati, g: random.Random) -> str:
    compenso = g.randint(800, 9000)
    return (f"STUDIO LEGALE ESEMPIO\n{g.choice(('AVVISO DI PARCELLA', 'FATTURA PRO FORMA', 'Notula'))} n. {d.numero}/{d.anno}\n"
            f"Cliente: {d.parte}\nPratica: {d.parte} / {d.controparte}\nCompenso professionale: euro {compenso},00\n"
            f"Spese generali 15%: euro {compenso * 15 // 100},00\nCassa avvocati 4%\nIVA 22%\n"
            f"Totale da corrispondere: euro {compenso * 14 // 10},00\nIl presente documento non costituisce fattura.")


def _fattura(d: _Dati, g: random.Random) -> str:
    imponibile = g.randint(500, 9000)
    return (f"FATTURA n. {d.numero}/{d.anno} del {d.data}\nSTUDIO LEGALE ESEMPIO - P. IVA 0{g.randint(10**9, 10**10 - 1)}\n"
            f"Cliente: {d.parte}\nDescrizione: prestazioni professionali {g.choice(('stragiudiziali', 'giudiziali', 'di consulenza'))}\n"
            f"Imponibile: euro {imponibile},00\nCassa avvocati 4%\nIVA 22%\n"
            f"Totale fattura: euro {imponibile * 13 // 10},00\nModalità di pagamento: bonifico")


def _visura(d: _Dati, g: random.Random) -> str:
    return (f"{g.choice(('Visura per soggetto', 'Visura per immobile', 'Visura catastale'))}\n"
            f"Agenzia delle Entrate - Direzione Provinciale di {d.citta} - Ufficio Provinciale Territorio\n"
            f"Servizi Catastali\nData: {d.data}\nCatasto dei Fabbricati\nComune di {d.citta}\n"
            f"Foglio {g.randint(1, 80)} Particella {g.randint(1, 900)} Sub {g.randint(1, 30)}\n"
            f"Categoria A/{g.randint(2, 7)} Classe {g.randint(1, 6)} Rendita euro {g.randint(200, 1500)},{g.randint(10, 99)}\n"
            f"Intestato: {d.parte}")


def _recapito_postale(d: _Dati, g: random.Random) -> str:
    return (f"Poste Italiane\nDOCUMENTAZIONE DI RECAPITO\nRaccomandata n. {g.randint(10**11, 10**12 - 1)}\n"
            f"Destinatario: {d.controparte}\n[ ] avvenuta consegna\n[ ] mancata consegna\n[ ] avvenuto ritiro\n"
            f"Data: {d.data}\nFirma dell'addetto")


def _avviso_ricevimento(d: _Dati, g: random.Random) -> str:
    return (f"Poste Italiane\nAVVISO DI RICEVIMENTO\n{g.choice(('Raccomandata A.R.', 'Atti giudiziari - notificazione a mezzo posta'))}\n"
            f"n. {g.randint(10**11, 10**12 - 1)}\nDestinatario: {d.controparte}, {d.citta}\nMittente: Avv. Studio Prova\n"
            f"Consegnato il {d.data}\nFirma del ricevente")


def _relazione_ctu(d: _Dati, g: random.Random) -> str:
    return (f"TRIBUNALE DI {d.citta.upper()}\nCausa n. {d.numero}/{d.anno} R.G. - {d.parte} contro {d.controparte}\n"
            f"{g.choice(('RELAZIONE PERITALE', 'Relazione peritale del CTU', 'PERIZIA DEL CTU'))}\n"
            f"Il sottoscritto consulente tecnico d'ufficio, nominato con ordinanza del {_gg(d, g)}, rassegna le proprie risposte ai quesiti.\n"
            f"1. Descrizione dei luoghi e delle operazioni svolte.\n2. Risposta ai quesiti.\n3. Conclusioni.\nIl CTU")


def _decreto_ctu(d: _Dati, g: random.Random) -> str:
    return (f"TRIBUNALE DI {d.citta.upper()}\nDECRETO DI LIQUIDAZIONE\nCausa n. {d.numero}/{d.anno} R.G.\n"
            f"Il Giudice, vista l'istanza del CTU, esaminata la consulenza tecnica depositata,\n"
            f"LIQUIDA al consulente tecnico d'ufficio la somma di euro {g.randint(800, 6000)},00 oltre accessori,\n"
            f"ponendola provvisoriamente a carico di {d.parte}.\n{d.citta}, {d.data}\nIl Giudice")


def _nomina_ctp(d: _Dati, g: random.Random) -> str:
    return (f"TRIBUNALE DI {d.citta.upper()}\nCausa n. {d.numero}/{d.anno} R.G.\n"
            f"{g.choice(('NOMINA DEL CTP', 'Nomina CTP', 'DESIGNAZIONE DEL CTP'))}\n"
            f"Il sottoscritto difensore di {d.parte} nomina quale consulente tecnico di parte l'Ing. Esempio, "
            f"che parteciperà alle operazioni peritali.\n{d.citta}, {d.data}\nAvv. Studio Prova")


def _avvio_peritali(d: _Dati, g: random.Random) -> str:
    return (f"Ing. Esempio - Consulente Tecnico d'Ufficio\nTribunale di {d.citta} - causa n. {d.numero}/{d.anno} R.G.\n"
            f"Oggetto: comunicazione di {g.choice(('inizio', 'avvio'))} delle attività peritali\n"
            f"Si comunica alle parti che le operazioni peritali avranno inizio il giorno {_gg(d, g, 1)} alle ore 10:00 "
            f"presso {g.choice(('lo studio del CTU', 'i luoghi di causa'))}.\nIl CTU")


def _accordo_mediazione(d: _Dati, g: random.Random) -> str:
    return (f"{g.choice(('ACCORDO DI CONCILIAZIONE', 'Accordo di mediazione', 'ACCORDO DI CONCILIAZIONE'))}\n"
            f"Organismo di mediazione Esempio iscritto al n. {g.randint(1, 1200)} del registro\n"
            f"Procedimento n. {d.numero}/{d.anno} tra {d.parte} e {d.controparte}\n"
            f"Le parti convengono quanto segue: {d.controparte} corrisponde a {d.parte} la somma di euro "
            f"{g.randint(1000, 30000)},00 a saldo e stralcio di ogni pretesa.\n{d.citta}, {d.data}\nIl mediatore")


def _modulo_mediazione(d: _Dati, g: random.Random) -> str:
    return ("ISTANZA DI MEDIAZIONE\nOrganismo di mediazione Esempio\nParte istante: ______________\n"
            "Codice fiscale: ______________\nParte invitata: ______________\nOggetto della controversia: ______________\n"
            f"Valore della lite: ______________\n(D.Lgs. 28/2010) Modulo aggiornato al {d.anno}")


def _procura_mediazione(d: _Dati, g: random.Random) -> str:
    vuoto = g.random() < 0.5
    chi = "______________" if vuoto else d.parte
    return (f"Il sottoscritto {chi}, nato a {'______________' if vuoto else d.citta},\n"
            f"conferisce procura speciale sostanziale a {'______________' if vuoto else 'Avv. Studio Prova'} "
            f"per partecipare in suo nome al procedimento dinanzi all'Organismo di mediazione Esempio, "
            f"con facoltà di conciliare e transigere.\n{d.citta}, {d.data}\nFirma {'______________' if vuoto else chi}")


MODELLI_CONTENUTO: dict[str, Callable[[_Dati, random.Random], str]] = {
    "Sentenza": _sentenza,
    "Procura alle liti": _procura,
    "Verbale di udienza": _verbale,
    "Decreto di fissazione udienza": _decreto_fissazione,
    "Contratto di lavoro": _contratto_lavoro,
    "Carta d'identità": _carta_identita,
    "Richiesta stragiudiziale di pagamento": _richiesta_pagamento,
    "Messaggio PEC": _messaggio_pec,
    "Note di trattazione scritta": _note_trattazione,
    "Nota di iscrizione a ruolo": _nota_iscrizione,
    "Indice dei documenti depositati": _indice_documenti,
    "Contributo unificato / pagamento": _ricevuta_cu,
    "Contributo unificato / esenzione": _esenzione_cu,
    "Contributo unificato / invito pagamento": _invito_cu,
    "Patrocinio a spese dello Stato": _patrocinio,
    "Proforma / avviso di parcella": _proforma,
    "Fattura": _fattura,
    "Visura catastale": _visura,
    "Documentazione di recapito postale": _recapito_postale,
    "Avviso di ricevimento postale": _avviso_ricevimento,
    "Relazione peritale CTU": _relazione_ctu,
    "Decreto di liquidazione CTU": _decreto_ctu,
    "Nomina di CTP": _nomina_ctp,
    "Comunicazione avvio operazioni peritali": _avvio_peritali,
    "Accordo di mediazione": _accordo_mediazione,
    "Modulo di istanza di mediazione": _modulo_mediazione,
    # Con i campi vuoti il catalogo la riconosce come modulo, compilata come procura: si tengono solo quelli
    # che il catalogo classifica come la voce attesa.
    "Procura speciale per la mediazione": _procura_mediazione,
    "Modulo di procura speciale per la mediazione": _procura_mediazione,
}


# --- varietà comune -----------------------------------------------------------------------------------------

def _corpo(d: _Dati, g: random.Random) -> list[str]:
    frasi = g.sample(_FRASI, k=g.randint(2, 7))
    return [f.format(p=d.parte, n=d.numero, a=d.anno, d=d.data, k=d.pagine) for f in frasi]


def _rifinisci(testo: str, d: _Dati, g: random.Random) -> str:
    """Coda dell'atto, intestazione di pagina e qualche errore tipico del riconoscimento ottico nel corpo."""
    righe = testo.split("\n")
    righe.append(g.choice(_CODA).format(c=d.citta, d=d.data, p=d.parte, k=d.pagine))
    if g.random() < 0.3:
        righe.insert(0, f"Pagina 1 di {d.pagine}")
    if g.random() < 0.25:
        # Solo nel corpo: l'intestazione resta leggibile come nei documenti veri ben scansionati.
        indice = g.randrange(len(righe) // 2, len(righe))
        righe[indice] = "".join(c.translate(_OCR) if g.random() < 0.08 else c for c in righe[indice])
    if g.random() < 0.3:
        righe = [r.lower() if i > 4 else r for i, r in enumerate(righe)]
    return "\n".join(righe)


def documenti_inventati(per_voce: int = 60, *, voci: set[str] | None = None, tentativi: int = 5,
                        classifica: Callable[[str], tuple[str, int]] | None = None,
                        seme: int = _SEME) -> Iterator[DocumentoInventato]:
    """Fino a `per_voce` documenti per ogni regola di titolo e per ogni modello di contenuto.

    Ogni documento è prima classificato dal catalogo completo: entra solo con la voce prevista e una confidenza
    di almeno `CONFIDENZA_MINIMA`.
    """
    from pct.document_intelligence.catalog_titoli import REGOLE_TITOLO

    if classifica is None:
        from pct.document_intelligence.catalog_resolver import _classify_indexed_content

        def classifica(testo: str) -> tuple[str, int]:
            esito = _classify_indexed_content(testo)
            return str(esito.label or ""), int(esito.confidence or 0)

    g = random.Random(seme)
    sorgenti: list[tuple[str, str, Callable[[], str]]] = []
    for regola in REGOLE_TITOLO:
        sorgenti.append((regola.label, regola.id, lambda r=regola: _testo_da_regola(r, g)))
    for voce, modello in MODELLI_CONTENUTO.items():
        sorgenti.append((voce, f"modello:{voce}", lambda m=modello: _rifinisci(m(_dati(g), g), _dati(g), g)))
    for voce, origine, genera in sorgenti:
        if voci is not None and voce not in voci:
            continue
        accettati = 0
        for _ in range(per_voce * tentativi):
            if accettati >= per_voce:
                break
            testo = genera()
            etichetta, confidenza = classifica(testo)
            if etichetta == voce and confidenza >= CONFIDENZA_MINIMA:
                accettati += 1
                yield DocumentoInventato(voce=voce, origine=origine, testo=testo)


SEME_BANCO = _SEME + 1  # banco di prova: documenti diversi da quelli di addestramento

__all__ = ["CONFIDENZA_MINIMA", "MODELLI_CONTENUTO", "SEME_BANCO", "DocumentoInventato", "documenti_inventati"]
