"""Le pratiche di prova del collaudo della catena, una o più per materia, con il risultato atteso scritto da avvocato.

Dati fittizi costruiti sugli esempi delle fonti ufficiali (formule dei provvedimenti e degli atti come li scrivono
gli uffici); nessun dato reale. Le norme citate nelle attese sono quelle vigenti lette nell'archivio Normattiva del
software (aggiornamento del 05/03/2026) il 19/11/2026: artt. 155, 324, 325, 326, 327, 414-416, 434, 474, 480, 543,
633-647, 127-ter, 171-bis, 171-ter c.p.c.; art. 14 D.L. 669/1996; art. 3-bis L. 53/1994; D.Lgs. 104/2010; D.Lgs.
175/2024; art. 552 c.p.p.; art. 35-bis D.Lgs. 25/2008; art. 404 c.c.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from lex.normativa import materie as M
from pct.fascicoli import TipoFascicolo

Documento = tuple[str, list[str]]


@dataclass(frozen=True)
class Passo:
    giorno: str
    documenti: tuple[Documento, ...] = ()
    attese: Callable[[Any], None] | None = None
    descrizione: str = ""


@dataclass(frozen=True)
class PraticaDiProva:
    codice: str
    materia: str
    fascicolo: dict[str, Any]
    passi: tuple[Passo, ...] = field(default_factory=tuple)


def _fascicolo(titolo, tipo, cliente, controparte, ufficio, rg, codice_oggetto="", anno=2026):
    return {"titolo": titolo, "tipo": tipo, "cliente": cliente, "controparte": controparte, "ufficio": ufficio,
            "rg": rg, "anno": anno, "codice_oggetto": codice_oggetto}


def _conclusione(foto, codice):
    voce = foto.conclusione(codice)
    assert voce is not None, f"manca la conclusione {codice}: {[c['codice'] for c in foto.ragionamento.get('conclusioni') or []]}"
    return voce


def _udienza_in_agenda(foto, giorno, ora=""):
    udienze = [a for a in foto.udienze() if a["data"] == giorno]
    assert udienze, f"udienza del {giorno} non in agenda: {foto.agenda}"
    if ora:
        assert any(a["ora"] == ora for a in udienze), udienze


def _nessun_termine_inventato(foto):
    """Senza una conclusione del modello il guardiano non scrive termini (fonte certa o niente)."""
    scritte = [s for s in foto.aperte() if "RAGIONAMENTO:" in s["note"]]
    codici = {c["codice"] for c in foto.ragionamento.get("conclusioni") or []}
    assert all(s["note"].split("RAGIONAMENTO:")[1].split(":")[0] in codici for s in scritte), scritte


# --- Lavoro e previdenza: rito del lavoro contro la P.A. (artt. 414-416, 434 c.p.c.; art. 14 D.L. 669/1996) ------

RICORSO_LAVORO = ("Ricorso ex art 414 cpc Gialli.pdf", [
    "TRIBUNALE ORDINARIO DI VICENZA - SEZIONE LAVORO", "RICORSO EX ART. 414 C.P.C.",
    "La prof.ssa GIALLI ANNA, rappresentata e difesa dall'Avv. Mario Rossi, ricorre contro il",
    "MINISTERO DELL'ISTRUZIONE E DEL MERITO per il pagamento della carta del docente (art. 1, comma 121, L. 107/2015).",
    "Chiede che il Tribunale, in funzione di giudice del lavoro, condanni il Ministero al pagamento di euro 500,00.",
    "Vicenza, 01/10/2026 Avv. Mario Rossi"])
DECRETO_LAVORO = ("4194926s.pdf", [
    "TRIBUNALE ORDINARIO di VICENZA SEZIONE LAVORO R.G. n. 1571/2026", "DECRETO DI FISSAZIONE UDIENZA",
    "Il Giudice del Lavoro, letto il ricorso che precede, visto l'art. 415, commi 2 e 3, c.p.c.",
    "FISSA la comparizione delle parti dinanzi a se' per l'udienza del 09/02/2027 ore 10:00;",
    "ORDINA che il ricorso con il pedissequo decreto sia notificato a cura dell'istante alla controparte nei termini",
    "di legge. Si avverte il convenuto che ha l'onere di costituirsi in cancelleria, a pena di decadenza, almeno",
    "dieci giorni prima dell'udienza come sopra fissata.", "Vicenza, 09/10/2026 Il Giudice del Lavoro dott. Bianchi"])
SENTENZA_LAVORO = ("Sentenza n 120 2027.pdf", [
    "Sentenza n. 120/2027 pubbl. il 09/02/2027 RG n. 1571/2026", "REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO",
    "TRIBUNALE ORDINARIO DI VICENZA Il Giudice del lavoro nella causa RG 1571/2026 promossa da GIALLI ANNA,",
    "rappresentata e difesa dall'Avv. Mario Rossi, contro il MINISTERO DELL'ISTRUZIONE E DEL MERITO.",
    "P.Q.M. accoglie il ricorso; condanna il Ministero dell'Istruzione e del Merito al pagamento di euro 500,00",
    "e delle spese di lite in favore di parte ricorrente, che liquida in euro 1.800,00 per compensi, oltre spese",
    "generali 15%, CPA e IVA, da distrarsi a favore dell'avv. Mario Rossi antistatario. Vicenza, 09/02/2027"])


def _lavoro_decreto(foto):
    # Udienza fissata dal giudice (art. 415, comma 2, c.p.c.): in agenda con l'ora del decreto.
    _udienza_in_agenda(foto, "2027-02-09", "10:00")
    notifica = _conclusione(foto, "notifica_ricorso_decreto_415")
    # Notifica a cura dell'attore entro dieci giorni dalla pronuncia (termine ordinatorio) e comunque almeno trenta
    # giorni prima dell'udienza (art. 415, commi 4 e 5, c.p.c.), per la P.A. presso l'Avvocatura dello Stato.
    assert notifica["stato"] == "da_fare" and notifica["onerato_codice"] == "noi", notifica
    assert notifica["termine"]["scadenza_iso"] in {"2026-10-19", "2027-01-08"}, notifica["termine"]
    assert any("415" in n["norma"] for n in notifica["norme"])
    assert foto.scadenza_il(notifica["termine"]["scadenza_iso"]), foto.scadenze
    # Il termine di costituzione (art. 416 c.p.c.) grava sul Ministero: nessuna scadenza dello studio.
    costituzione = foto.conclusione("costituzione_convenuto")
    if costituzione:
        assert costituzione["onerato_codice"] == "controparte"


def _lavoro_sentenza(foto):
    assert foto.ragionamento["fase"]["codice"] in {"decisa", "giudicato_da_verificare"}, foto.ragionamento["fase"]
    # Cliente vittoriosa: l'appello non è un adempimento dello studio (art. 434 c.p.c.).
    impugnazione = foto.conclusione("termine_impugnazione")
    assert impugnazione is None or impugnazione["stato"] != "da_fare" or impugnazione["onerato_codice"] != "noi", impugnazione
    assert not [u for u in foto.udienze() if u["data"] > foto_oggi(foto)]


def foto_oggi(foto) -> str:
    return foto.guardiano["oggi"]


LAVORO = PraticaDiProva("lavoro_pa", M.LAVORO, _fascicolo(
    "Gialli / Ministero dell'Istruzione", TipoFascicolo.LAVORO, "Anna Gialli", "Ministero dell'Istruzione e del Merito",
    "Tribunale di Vicenza", "1571", "222050"), (
    Passo("2026-10-01", (RICORSO_LAVORO,), lambda f: _nessun_termine_inventato(f), "ricorso depositato"),
    Passo("2026-10-12", (DECRETO_LAVORO,), _lavoro_decreto, "decreto di fissazione dell'udienza"),
    Passo("2027-02-15", (SENTENZA_LAVORO,), _lavoro_sentenza, "sentenza di accoglimento"),
))



def _fase(foto, *codici):
    assert foto.ragionamento.get("fase", {}).get("codice") in codici, foto.ragionamento.get("fase")


def _lavoro_giudicato(foto):
    # Senza notifica vale il termine lungo di sei mesi dalla pubblicazione (art. 327 c.p.c.), senza sospensione
    # feriale nelle controversie di lavoro (art. 3 L. 742/1969): dal 09/02/2027 al 09/08/2027; poi la sentenza passa
    # in giudicato se nessuno impugna (art. 324 c.p.c.): la fase dice di verificarlo, non lo afferma.
    _fase(foto, "giudicato_da_verificare", "decisa")


LAVORO = PraticaDiProva("lavoro_pa", M.LAVORO, LAVORO.fascicolo, LAVORO.passi + (
    Passo("2027-09-15", (), _lavoro_giudicato, "termine lungo per impugnare decorso"),
))

# --- Procedura civile: procedimento monitorio (artt. 633-647 c.p.c.) ------------------------------------------------

def _ricorso_di(ufficio, creditore, debitore, causale, importo, data):
    return ("Ricorso per decreto ingiuntivo.pdf", [
        f"{ufficio.upper()} RICORSO PER DECRETO INGIUNTIVO (artt. 633 e ss. c.p.c.)",
        f"{creditore}, rappresentata e difesa dall'Avv. Mario Rossi, espone di essere creditrice di {debitore}",
        f"della somma di euro {importo} per {causale}, come da documentazione allegata (prova scritta, art. 634 c.p.c.).",
        f"Chiede che il Giudice ingiunga a {debitore} il pagamento della somma, oltre interessi e spese.",
        f"{data} Avv. Mario Rossi"])


def _decreto_ingiuntivo(ufficio, numero, rg, creditore, debitore, importo, data, *, esecutivo=False):
    # Il nome con cui il portale consegna il decreto (PST: «accoglimentoDecretoIngiuntivo.pdf»).
    return ("accoglimentoDecretoIngiuntivo.pdf", [
        f"Decreto ingiuntivo n. {numero} RG n. {rg}", f"{ufficio.upper()} DECRETO INGIUNTIVO",
        f"Il Giudice, letto il ricorso per la concessione del decreto ingiuntivo depositato da {creditore} - Avv. MARIO ROSSI;",
        f"INGIUNGE a {debitore} di pagare entro quaranta giorni dalla notifica del presente decreto la somma di euro {importo}.",
        "Le spese di questa procedura, liquidate in euro 145,50 per spese ed euro 540,00 per compensi."
        + (" Dichiara il decreto provvisoriamente esecutivo ai sensi dell'art. 642 c.p.c." if esecutivo else ""),
        "AVVERTE la parte ingiunta che puo' proporre opposizione nel termine perentorio di quaranta giorni dalla notifica.",
        f"Si comunichi. {data}"])


def _monitorio_decreto(scadenza):
    def attese(foto):
        notifica = _conclusione(foto, "notifica_decreto_ingiuntivo")
        # Il decreto diventa inefficace se non è notificato entro sessanta giorni dalla pronuncia (art. 644 c.p.c.).
        # Lo studio ricorrente: sessanta giorni dalla pronuncia, sempre (novanta solo all'estero), termine certo a suo
        # carico e nello scadenziario (art. 644 c.p.c.).
        assert notifica["stato"] == "da_fare" and notifica["onerato_codice"] == "noi", notifica
        assert notifica["termine"]["scadenza_iso"] == scadenza, notifica["termine"]
        assert foto.scadenza_il(scadenza), foto.scadenze
        assert any("644" in n["norma"] for n in notifica["norme"]), notifica["norme"]
        _fase(foto, "decreto_emesso", "notifica_decreto_da_verificare")
    return attese


MONITORIO = PraticaDiProva("monitorio", M.PROC_CIVILE, _fascicolo(
    "Alfa / Beta S.r.l.", TipoFascicolo.CIVILE, "Associazione Alfa", "Beta S.r.l.", "Giudice di Pace di Palmi", "4202",
    "010001"), (
    Passo("2026-11-02", (_ricorso_di("Ufficio del Giudice di Pace di Palmi", "ASSOCIAZIONE ALFA", "BETA S.R.L.",
                                     "fornitura di servizi non pagata", "2.400,00", "Palmi, 02/11/2026"),),
          _nessun_termine_inventato, "ricorso per decreto ingiuntivo"),
    # Pronuncia del 20/11/2026: sessanta giorni scadono il 19/01/2027 (martedì, nessuna proroga).
    Passo("2026-11-25", (_decreto_ingiuntivo("Ufficio del Giudice di Pace di Palmi", "1109/2026", "4202/2026",
                                             "ASSOCIAZIONE ALFA", "BETA S.R.L.", "2.400,00", "PALMI, 20-11-2026"),),
          _monitorio_decreto("2027-01-19"), "decreto ingiuntivo da notificare"),
))

BANCA = PraticaDiProva("monitorio_bancario", M.BANCA, _fascicolo(
    "Banca Gamma / Delta", TipoFascicolo.CIVILE, "Banca Gamma S.p.A.", "Delta Mario", "Tribunale di Torino", "9911",
    "010001"), (
    Passo("2026-10-05", (_ricorso_di("Tribunale ordinario di Torino", "BANCA GAMMA S.P.A.", "DELTA MARIO",
                                     "saldo debitore di conto corrente (estratto certificato ex art. 50 D.Lgs. 385/1993)",
                                     "18.750,00", "Torino, 05/10/2026"),), _nessun_termine_inventato,
          "ricorso con estratto conto certificato"),
    # Pronuncia del 15/10/2026: sessanta giorni scadono il 14/12/2026 (lunedì).
    Passo("2026-10-20", (_decreto_ingiuntivo("Tribunale ordinario di Torino", "3344/2026", "9911/2026",
                                             "BANCA GAMMA S.P.A.", "DELTA MARIO", "18.750,00", "Torino, 15/10/2026",
                                             esecutivo=True),),
          _monitorio_decreto("2026-12-14"), "decreto ingiuntivo provvisoriamente esecutivo (art. 642 c.p.c.)"),
))

FORENSE = PraticaDiProva("compensi_avvocato", M.FORENSE, _fascicolo(
    "Avv. Rossi / Epsilon", TipoFascicolo.CIVILE, "Mario Rossi", "Epsilon S.r.l.", "Tribunale di Milano", "5150",
    "010024"), (
    Passo("2026-09-01", (_ricorso_di("Tribunale ordinario di Milano", "AVV. MARIO ROSSI", "EPSILON S.R.L.",
                                     "compensi professionali, parcella con parere di congruita' del Consiglio dell'Ordine "
                                     "(artt. 633, n. 2, e 636 c.p.c.)", "6.300,00", "Milano, 01/09/2026"),),
          _nessun_termine_inventato, "ricorso per compensi"),
    # Pronuncia del 10/09/2026: sessanta giorni scadono il 09/11/2026 (lunedì); oggi 15/09/2026.
    Passo("2026-09-15", (_decreto_ingiuntivo("Tribunale ordinario di Milano", "2210/2026", "5150/2026",
                                             "AVV. MARIO ROSSI", "EPSILON S.R.L.", "6.300,00", "Milano, 10/09/2026"),),
          _monitorio_decreto("2026-11-09"), "decreto ingiuntivo per compensi"),
))

# --- Diritto civile e spese di giustizia: cognizione ordinaria con note scritte (artt. 127-ter, 171-ter c.p.c.) ------

CITAZIONE = ("Atto di citazione Bianchi.pdf", [
    "TRIBUNALE ORDINARIO DI TORINO ATTO DI CITAZIONE",
    "La sig.ra BIANCHI ANNA, rappresentata e difesa dall'Avv. Mario Rossi, CITA la DELTA S.R.L. a comparire",
    "all'udienza del 15/02/2027, ore di rito, davanti al Tribunale di Torino, con invito a costituirsi nel termine di",
    "settanta giorni prima dell'udienza (art. 166 c.p.c.), per sentir accertare l'inadempimento del contratto di appalto",
    "e condannare la convenuta al risarcimento del danno di euro 25.000,00. Torino, 20/10/2026 Avv. Mario Rossi"])
ORDINANZA_NOTE = ("Ordinanza 127 ter.pdf", [
    "TRIBUNALE ORDINARIO DI TORINO R.G. n. 777/2026", "Il Giudice, letti gli atti,",
    "dispone che l'udienza del 15/02/2027 sia sostituita dal deposito di note scritte ex art. 127-ter c.p.c.",
    "e assegna alle parti termine perentorio fino al 05/02/2027 per il deposito delle note.",
    "Si comunichi. Torino, 10/12/2026 Il Giudice dott.ssa Neri"])
AVVISO_CONTRIBUTO = ("Avviso pagoPA contributo unificato.pdf", [
    "Avviso di pagamento pagoPA - Contributo unificato (art. 13 D.P.R. 115/2002)",
    "Ente creditore: Ministero della Giustizia. Causale: contributo unificato R.G. 777/2026 Tribunale di Torino",
    "Importo euro 545,00. Data di scadenza: entro il 30/11/2026."])


def _cognizione_note(foto):
    note = _conclusione(foto, "note_127ter")
    # Termine perentorio assegnato dal giudice per le note (art. 127-ter, secondo comma, c.p.c.): lo studio, come
    # ogni parte costituita, deposita entro il 05/02/2027; il giorno di scadenza vale come udienza.
    assert note["termine"]["scadenza_iso"] == "2027-02-05" and note["termine"]["natura"] == "perentorio", note["termine"]
    assert note["stato"] == "da_fare" and note["onerato_codice"] in {"noi", "tutte_le_parti"}, note
    assert foto.scadenza_il("2027-02-05"), foto.scadenze
    # L'udienza del 15/02/2027 è sostituita: in agenda con la modalità della trattazione scritta.
    udienze = [u for u in foto.ragionamento.get("udienze") or [] if u["data"] == "15/02/2027"]
    if udienze:
        assert "note" in udienze[0]["modalita"], udienze
        assert all(a["modalita"] == "note_scritte" for a in foto.udienze() if a["data"] == "2027-02-15"), foto.agenda


def _avviso_contributo_non_e_termine(foto):
    # La scadenza dell'avviso pagoPA non è un termine processuale: nessuna scadenza scritta dal modello.
    assert not foto.scadenza_il("2026-11-30"), foto.scadenze


CIVILE = PraticaDiProva("cognizione_note_scritte", M.CIVILE, _fascicolo(
    "Bianchi / Delta S.r.l.", TipoFascicolo.CIVILE, "Anna Bianchi", "Delta S.r.l.", "Tribunale di Torino", "777"), (
    Passo("2026-10-25", (CITAZIONE,), _nessun_termine_inventato, "citazione iscritta a ruolo"),
    Passo("2026-12-14", (ORDINANZA_NOTE,), _cognizione_note, "udienza sostituita dalle note scritte"),
))

GIUSTIZIA = PraticaDiProva("contributo_unificato", M.GIUSTIZIA, _fascicolo(
    "Bianchi / Omega S.r.l.", TipoFascicolo.CIVILE, "Anna Bianchi", "Omega S.r.l.", "Tribunale di Torino", "778"), (
    Passo("2026-10-26", (CITAZIONE, AVVISO_CONTRIBUTO), _avviso_contributo_non_e_termine,
          "contributo unificato da versare (art. 13 D.P.R. 115/2002)"),
))

# --- Impresa: espropriazione presso terzi, note scritte con termine perentorio (artt. 543, 631, 127-ter c.p.c.) ----

PIGNORAMENTO = ("Atto di pignoramento presso terzi.pdf", [
    "ATTO DI PIGNORAMENTO PRESSO TERZI (art. 543 c.p.c.)",
    "L'ALFA S.R.L., rappresentata e difesa dall'Avv. Mario Rossi, creditrice in forza di decreto ingiuntivo esecutivo,",
    "pignora i crediti della debitrice BETA S.R.L. verso il terzo GAMMA BANCA S.P.A. e cita il debitore a comparire",
    "davanti al Giudice dell'esecuzione del Tribunale di Palmi. Palmi, 01/09/2026 Avv. Mario Rossi"])
VERBALE_631 = ("12631033s.pdf", [
    "Tribunale Civile di Palmi Cancelleria Esecuzioni Mobiliari Proc n. 792/2026",
    "All'udienza del 02.11.2026 tenuta dal G.E. dott. Bianchi, viene chiamata la causa iscritta al n. 792/2026 R.G.E.",
    "tra ALFA S.R.L. contro BETA S.R.L. Il G.E. Poiche' nessuno e' presente rinvia all'udienza del 21.12.2026 che",
    "sostituisce con il deposito di note scritte ex art. 127 ter c.p.c. entro il termine perentorio del 16.12.2026.",
    "Ai sensi dell'art. 631 c.p.c. Si comunichi Il Giudice O.T."])


def _esecuzione_631(foto):
    note = _conclusione(foto, "note_127ter")
    # Mancata comparizione: se nessuno deposita le note entro il termine perentorio, il processo esecutivo si
    # estingue (art. 631, secondo comma, c.p.c.). Il termine è il 16/12/2026, non il giorno dell'udienza.
    assert note["termine"]["scadenza_iso"] == "2026-12-16" and note["termine"]["natura"] == "perentorio", note["termine"]
    assert any("631" in n["norma"] for n in note["norme"]), note["norme"]
    assert foto.scadenza_il("2026-12-16"), foto.scadenze
    assert not [s for s in foto.aperte() if s["data"] == "2026-12-21" and "RAGIONAMENTO:" in s["note"]]


IMPRESA = PraticaDiProva("esecuzione_presso_terzi", M.IMPRESA, _fascicolo(
    "Alfa S.r.l. / Beta S.r.l.", TipoFascicolo.CIVILE, "Alfa S.r.l.", "Beta S.r.l.", "Tribunale di Palmi", "792", "510002"), (
    Passo("2026-09-05", (PIGNORAMENTO,), _nessun_termine_inventato, "pignoramento presso terzi"),
    Passo("2026-11-05", (VERBALE_631,), _esecuzione_631, "rinvio con note scritte ex art. 631 c.p.c."),
))

# --- Materie con udienza fissata da un provvedimento del giudice: la catena non si ferma e non inventa termini ------

def _decreto_udienza(ufficio, rg, intestazione, testo_udienza, data, firma="Il Giudice"):
    return (f"Decreto fissazione udienza {rg.replace('/', '-')}.pdf", [
        f"{ufficio.upper()} R.G. n. {rg}", intestazione, testo_udienza, f"{data} {firma}"])


def _ricorso(nome, intestazione, righe, data):
    return (nome, [intestazione, *righe, f"{data} Avv. Mario Rossi"])


def _udienza_fissata(giorno, ora):
    def attese(foto):
        _nessun_termine_inventato(foto)
        # L'udienza fissata dal giudice (o dal pubblico ministero nel decreto di citazione) con giorno e ora è in
        # agenda: dai fatti letti (consegna ai presìdi) o dal modello della causa (guardiano).
        _udienza_in_agenda(foto, giorno, ora)
    return attese


def _semplice(codice, materia, fascicolo, ricorso, decreto, giorno_ricorso, giorno_decreto, udienza, ora):
    return PraticaDiProva(codice, materia, fascicolo, (
        Passo(giorno_ricorso, (ricorso,), _nessun_termine_inventato, "atto introduttivo"),
        Passo(giorno_decreto, (decreto,), _udienza_fissata(udienza, ora), "udienza fissata"),
    ))


FAMIGLIA = _semplice(
    "separazione_consensuale", M.FAMIGLIA, _fascicolo("Verdi / Verdi", TipoFascicolo.FAMIGLIA, "Laura Verdi", "Paolo Verdi",
                                                      "Tribunale di Bologna", "3030", "111001"),
    _ricorso("Ricorso separazione consensuale.pdf", "TRIBUNALE ORDINARIO DI BOLOGNA RICORSO PER SEPARAZIONE CONSENSUALE (art. 473-bis.51 c.p.c.)",
             ["I coniugi VERDI LAURA e VERDI PAOLO, la prima rappresentata e difesa dall'Avv. Mario Rossi,",
              "chiedono l'omologazione delle condizioni di separazione concordate."], "Bologna, 02/10/2026"),
    _decreto_udienza("Tribunale ordinario di Bologna", "3030/2026", "DECRETO DI FISSAZIONE DELL'UDIENZA",
                     "Il Presidente FISSA l'udienza di comparizione personale dei coniugi per il giorno 12/01/2027 ore 11:30.",
                     "Bologna, 09/10/2026"),
    "2026-10-02", "2026-10-12", "2027-01-12", "11:30")

ALTRO = _semplice(
    "amministrazione_sostegno", M.ALTRO, _fascicolo("Ricorso AdS Rosa", TipoFascicolo.ALTRO, "Carlo Rosa", "", "Tribunale di Padova",
                                                    "1234", "413061"),
    _ricorso("Ricorso amministrazione di sostegno.pdf", "TRIBUNALE ORDINARIO DI PADOVA - GIUDICE TUTELARE RICORSO PER LA NOMINA DI AMMINISTRATORE DI SOSTEGNO (artt. 404 e ss. c.c.)",
             ["Il sig. ROSA CARLO, rappresentato e difeso dall'Avv. Mario Rossi, chiede la nomina di un amministratore",
              "di sostegno in favore della madre ROSA MARIA."], "Padova, 01/10/2026"),
    _decreto_udienza("Tribunale ordinario di Padova", "1234/2026", "DECRETO DEL GIUDICE TUTELARE",
                     "Il Giudice Tutelare FISSA per l'audizione della beneficiaria (art. 407 c.c.) l'udienza del 20/01/2027 ore 9:30.",
                     "Padova, 07/10/2026", "Il Giudice Tutelare"),
    "2026-10-01", "2026-10-12", "2027-01-20", "09:30")

CONSUMO = _semplice(
    "consumatore_gdp", M.CONSUMO, _fascicolo("Neri / Telefonia Zeta", TipoFascicolo.CIVILE, "Luca Neri", "Zeta Telefonia S.p.A.",
                                             "Giudice di Pace di Roma", "45678"),
    _ricorso("Ricorso Giudice di pace consumatore.pdf", "UFFICIO DEL GIUDICE DI PACE DI ROMA RICORSO (art. 316 c.p.c.)",
             ["Il sig. NERI LUCA, consumatore, rappresentato e difeso dall'Avv. Mario Rossi, chiede la restituzione di",
              "euro 640,00 addebitati per servizi non richiesti (art. 66-quinquies D.Lgs. 206/2005)."], "Roma, 05/10/2026"),
    _decreto_udienza("Ufficio del Giudice di Pace di Roma", "45678/2026", "DECRETO DI FISSAZIONE UDIENZA",
                     "Il Giudice di Pace FISSA l'udienza di comparizione delle parti per il giorno 18/02/2027 ore 9:00.",
                     "Roma, 12/10/2026", "Il Giudice di Pace"),
    "2026-10-05", "2026-10-15", "2027-02-18", "09:00")

TRASPORTI = _semplice(
    "opposizione_sanzione_strada", M.TRASPORTI, _fascicolo("Galli / Comune di Milano", TipoFascicolo.CIVILE, "Sara Galli",
                                                          "Comune di Milano", "Giudice di Pace di Milano", "70001"),
    _ricorso("Ricorso opposizione verbale.pdf", "UFFICIO DEL GIUDICE DI PACE DI MILANO RICORSO IN OPPOSIZIONE A VERBALE DI ACCERTAMENTO (art. 7 D.Lgs. 150/2011; art. 204-bis D.Lgs. 285/1992)",
             ["La sig.ra GALLI SARA, rappresentata e difesa dall'Avv. Mario Rossi, propone opposizione al verbale della",
              "Polizia Locale del Comune di Milano notificato il 10/09/2026."], "Milano, 05/10/2026"),
    _decreto_udienza("Ufficio del Giudice di Pace di Milano", "70001/2026", "DECRETO DI FISSAZIONE UDIENZA",
                     "Il Giudice di Pace FISSA l'udienza di discussione per il giorno 25/02/2027 ore 10:30 e ordina alla cancelleria la notifica.",
                     "Milano, 14/10/2026", "Il Giudice di Pace"),
    "2026-10-05", "2026-10-16", "2027-02-25", "10:30")

DIGITALE = _semplice(
    "privacy_garante", M.DIGITALE, _fascicolo("Moro / Garante", TipoFascicolo.CIVILE, "Elisa Moro", "Garante per la protezione dei dati personali",
                                              "Tribunale di Roma", "88001", "400711"),
    _ricorso("Ricorso art 152 codice privacy.pdf", "TRIBUNALE ORDINARIO DI ROMA RICORSO (art. 152 D.Lgs. 196/2003; art. 10 D.Lgs. 150/2011)",
             ["La sig.ra MORO ELISA, rappresentata e difesa dall'Avv. Mario Rossi, propone opposizione al provvedimento del",
              "Garante per la protezione dei dati personali comunicato il 15/09/2026."], "Roma, 08/10/2026"),
    _decreto_udienza("Tribunale ordinario di Roma", "88001/2026", "DECRETO DI FISSAZIONE UDIENZA",
                     "Il Giudice FISSA l'udienza di comparizione delle parti per il giorno 03/03/2027 ore 12:00.",
                     "Roma, 20/10/2026"),
    "2026-10-08", "2026-10-22", "2027-03-03", "12:00")

IMMIGRAZIONE = _semplice(
    "protezione_internazionale", M.IMMIGRAZIONE, _fascicolo("Diallo / Ministero dell'Interno", TipoFascicolo.CIVILE, "Amadou Diallo",
                                                           "Ministero dell'Interno", "Tribunale di Bologna", "12121"),
    _ricorso("Ricorso protezione internazionale.pdf", "TRIBUNALE ORDINARIO DI BOLOGNA - SEZIONE SPECIALIZZATA IMMIGRAZIONE RICORSO (art. 35-bis D.Lgs. 25/2008)",
             ["Il sig. DIALLO AMADOU, rappresentato e difeso dall'Avv. Mario Rossi, impugna il provvedimento della",
              "Commissione territoriale notificato il 01/10/2026."], "Bologna, 20/10/2026"),
    _decreto_udienza("Tribunale ordinario di Bologna", "12121/2026", "DECRETO",
                     "Il Giudice FISSA l'udienza di comparizione delle parti per il giorno 10/03/2027 ore 9:00.",
                     "Bologna, 28/10/2026"),
    "2026-10-20", "2026-10-30", "2027-03-10", "09:00")

UE = _semplice(
    "diritto_ue_consumatori", M.UE, _fascicolo("Conti / Banca Sigma", TipoFascicolo.CIVILE, "Marco Conti", "Banca Sigma S.p.A.",
                                               "Tribunale di Firenze", "6060"),
    _ricorso("Atto di citazione clausole abusive.pdf", "TRIBUNALE ORDINARIO DI FIRENZE ATTO DI CITAZIONE",
             ["Il sig. CONTI MARCO, rappresentato e difeso dall'Avv. Mario Rossi, chiede l'accertamento della vessatorieta'",
              "delle clausole del contratto di credito (Direttiva 93/13/CEE; art. 33 D.Lgs. 206/2005)."], "Firenze, 02/10/2026"),
    _decreto_udienza("Tribunale ordinario di Firenze", "6060/2026", "DECRETO (art. 171-bis c.p.c.)",
                     "Il Giudice, compiute le verifiche preliminari, conferma l'udienza del 22/03/2027 ore 10:00.",
                     "Firenze, 20/10/2026"),
    "2026-10-02", "2026-10-22", "2027-03-22", "10:00")

COSTITUZIONE = _semplice(
    "questione_legittimita", M.COSTITUZIONE, _fascicolo("Fabbri / INPS", TipoFascicolo.LAVORO, "Gino Fabbri", "INPS",
                                                        "Tribunale di Genova", "2525", "222050"),
    _ricorso("Ricorso con questione di legittimita costituzionale.pdf", "TRIBUNALE ORDINARIO DI GENOVA - SEZIONE LAVORO RICORSO EX ART. 414 C.P.C.",
             ["Il sig. FABBRI GINO, rappresentato e difeso dall'Avv. Mario Rossi, chiede il ricalcolo della pensione e",
              "solleva questione di legittimita' costituzionale (art. 23 L. 87/1953; artt. 3 e 38 Cost.)."], "Genova, 01/10/2026"),
    _decreto_udienza("Tribunale ordinario di Genova", "2525/2026", "DECRETO DI FISSAZIONE UDIENZA (art. 415 c.p.c.)",
                     "Il Giudice del Lavoro FISSA l'udienza di discussione del 18/03/2027 ore 9:30.",
                     "Genova, 05/10/2026", "Il Giudice del Lavoro"),
    "2026-10-01", "2026-10-08", "2027-03-18", "09:30")

# Riti che il motore del ragionamento non modella ancora (rito dal codice oggetto PST, che copre i soli registri civili).

PENALE = _semplice(
    "penale_citazione_diretta", M.PENALE, _fascicolo("Proc. pen. c. Ferri", TipoFascicolo.PENALE, "Luigi Ferri", "Procura della Repubblica",
                                                     "Tribunale di Napoli", "4545"),
    _ricorso("Nomina difensore di fiducia.pdf", "PROCURA DELLA REPUBBLICA PRESSO IL TRIBUNALE DI NAPOLI NOMINA DEL DIFENSORE DI FIDUCIA (art. 96 c.p.p.)",
             ["Il sig. FERRI LUIGI, indagato nel procedimento n. 4545/2026 R.G.N.R., nomina difensore di fiducia l'Avv. Mario Rossi."],
             "Napoli, 01/10/2026"),
    _decreto_udienza("Procura della Repubblica presso il Tribunale di Napoli", "4545/2026", "DECRETO DI CITAZIONE DIRETTA A GIUDIZIO (art. 552 c.p.p.)",
                     "Il Pubblico Ministero cita FERRI LUIGI a comparire davanti al Tribunale in composizione monocratica all'udienza del 15/03/2027 ore 9:30.",
                     "Napoli, 20/10/2026", "Il Pubblico Ministero"),
    "2026-10-01", "2026-10-25", "2027-03-15", "09:30")

MILITARE = _semplice(
    "penale_militare", M.MILITARE, _fascicolo("Proc. pen. mil. c. Sala", TipoFascicolo.PENALE, "Andrea Sala", "Procura militare",
                                              "Tribunale militare di Roma", "301"),
    _ricorso("Nomina difensore Tribunale militare.pdf", "PROCURA MILITARE DELLA REPUBBLICA PRESSO IL TRIBUNALE MILITARE DI ROMA NOMINA DEL DIFENSORE",
             ["Il caporale SALA ANDREA nomina difensore di fiducia l'Avv. Mario Rossi (art. 96 c.p.p.; art. 261 c.p.m.p.)."],
             "Roma, 01/10/2026"),
    _decreto_udienza("Tribunale militare di Roma", "301/2026", "DECRETO CHE DISPONE IL GIUDIZIO",
                     "Il Giudice dell'udienza preliminare dispone il giudizio e fissa l'udienza dibattimentale del 20/04/2027 ore 9:00.",
                     "Roma, 30/10/2026"),
    "2026-10-01", "2026-11-02", "2027-04-20", "09:00")

AMMINISTRATIVO = _semplice(
    "tar_appalto", M.AMMINISTRATIVO, _fascicolo("Edil Sud / Comune di Bari", TipoFascicolo.AMMINISTRATIVO, "Edil Sud S.r.l.",
                                                "Comune di Bari", "TAR Puglia", "800"),
    _ricorso("Ricorso TAR aggiudicazione.pdf", "TRIBUNALE AMMINISTRATIVO REGIONALE PER LA PUGLIA RICORSO (artt. 119 e 120 D.Lgs. 104/2010)",
             ["EDIL SUD S.R.L., rappresentata e difesa dall'Avv. Mario Rossi, chiede l'annullamento dell'aggiudicazione",
              "della gara del Comune di Bari comunicata il 01/09/2026."], "Bari, 25/09/2026"),
    _decreto_udienza("Tribunale amministrativo regionale per la Puglia", "800/2026", "AVVISO DI FISSAZIONE DELL'UDIENZA PUBBLICA",
                     "Si comunica che il ricorso e' fissato per l'udienza pubblica del 14/01/2027 ore 9:30.",
                     "Bari, 05/10/2026", "Il Segretario"),
    "2026-09-25", "2026-10-07", "2027-01-14", "09:30")

AMBIENTE = _semplice(
    "tar_demolizione", M.AMBIENTE, _fascicolo("Russo / Comune di Lecce", TipoFascicolo.AMMINISTRATIVO, "Pietro Russo",
                                              "Comune di Lecce", "TAR Puglia - Lecce", "1500"),
    _ricorso("Ricorso TAR ordinanza demolizione.pdf", "TRIBUNALE AMMINISTRATIVO REGIONALE PER LA PUGLIA - SEZIONE DI LECCE RICORSO (art. 29 D.Lgs. 104/2010)",
             ["Il sig. RUSSO PIETRO, rappresentato e difeso dall'Avv. Mario Rossi, chiede l'annullamento dell'ordinanza di",
              "demolizione (art. 31 D.P.R. 380/2001) notificata il 20/08/2026."], "Lecce, 15/10/2026"),
    _decreto_udienza("Tribunale amministrativo regionale per la Puglia - Sezione di Lecce", "1500/2026",
                     "AVVISO DI FISSAZIONE DELLA CAMERA DI CONSIGLIO",
                     "Si comunica che l'istanza cautelare e' fissata per la camera di consiglio del 04/02/2027 ore 10:00.",
                     "Lecce, 28/10/2026", "Il Segretario"),
    "2026-10-15", "2026-10-30", "2027-02-04", "10:00")

TRIBUTARIO = _semplice(
    "tributario_avviso_accertamento", M.TRIBUTARIO, _fascicolo("Longo / Agenzia delle Entrate", TipoFascicolo.TRIBUTARIO,
                                                              "Giorgio Longo", "Agenzia delle Entrate", "Corte di giustizia tributaria di primo grado di Torino", "2027"),
    _ricorso("Ricorso CGT avviso di accertamento.pdf", "CORTE DI GIUSTIZIA TRIBUTARIA DI PRIMO GRADO DI TORINO RICORSO (D.Lgs. 175/2024)",
             ["Il sig. LONGO GIORGIO, rappresentato e difeso dall'Avv. Mario Rossi, impugna l'avviso di accertamento",
              "IRPEF 2021 notificato il 15/07/2026 dall'Agenzia delle Entrate."], "Torino, 01/10/2026"),
    _decreto_udienza("Corte di giustizia tributaria di primo grado di Torino", "2027/2026", "AVVISO DI TRATTAZIONE",
                     "Si comunica che il ricorso e' fissato per la trattazione in udienza pubblica del 16/03/2027 ore 9:00.",
                     "Torino, 30/10/2026", "Il Segretario"),
    "2026-10-01", "2026-11-03", "2027-03-16", "09:00")

PRATICHE: tuple[PraticaDiProva, ...] = (
    LAVORO, MONITORIO, BANCA, FORENSE, CIVILE, GIUSTIZIA, IMPRESA, FAMIGLIA, ALTRO, CONSUMO, TRASPORTI, DIGITALE,
    IMMIGRAZIONE, UE, COSTITUZIONE, PENALE, MILITARE, AMMINISTRATIVO, AMBIENTE, TRIBUTARIO,
)
