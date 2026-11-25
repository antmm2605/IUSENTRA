"""Parametri della chiamata letti dalla domanda: solo ciò che la domanda dice, mai valori inventati.

Funzioni pure, ciascuna con il suo test (``lex/tests/test_strumenti_estrazione.py``):
date in gg/mm/aaaa, importi, percentuali, articolo e atto citati, comma, estremi di una pronuncia (organo, numero,
anno), ente della prassi, serie e tipo di atto della Gazzetta, organo e sede della giustizia amministrativa, numero di
ruolo del fascicolo, argomento di una domanda («quale norma disciplina X» → X) e campi di un calcolatore.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
        "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}


def normalizza(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "").lower())
    return " ".join("".join(c for c in base if not unicodedata.combining(c)).replace("’", "'").split())


# ------------------------------------------------------------------------------------------------ date e numeri
_DATA = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")
_DATA_LETTERE = re.compile(r"\b(\d{1,2})(?:°|º)?\s+(" + "|".join(MESI) + r")\s+(\d{4})\b")


def date_it(testo: str) -> list[str]:
    """Le date della domanda in gg/mm/aaaa, nell'ordine in cui compaiono; solo date di calendario esistenti."""
    from datetime import date

    trovate: list[tuple[int, str]] = []
    for m in _DATA.finditer(testo):
        g, mm, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        trovate.append((m.start(), (g, mm, a)))
    for m in _DATA_LETTERE.finditer(normalizza(testo)):
        trovate.append((m.start(), (int(m.group(1)), MESI[m.group(2)], int(m.group(3)))))
    uscita = []
    for _, (g, mm, a) in sorted(trovate):
        try:
            date(a, mm, g)
        except ValueError:
            continue
        valore = f"{g:02d}/{mm:02d}/{a}"
        if valore not in uscita:
            uscita.append(valore)
    return uscita


_IMPORTO = re.compile(r"(?:€\s*)?\b(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*(?:euro|€)|€\s*(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)")


def importi(testo: str) -> list[float]:
    """Gli importi in euro («12.000 euro», «€ 1.500,50»), nell'ordine."""
    uscita = []
    for m in _IMPORTO.finditer(testo):
        cifra = (m.group(1) or m.group(2)).replace(".", "").replace(",", ".")
        uscita.append(float(cifra))
    return uscita


def percentuali(testo: str) -> list[float]:
    return [float(m.group(1).replace(",", ".")) for m in re.finditer(r"\b(\d+(?:,\d+)?)\s*(?:%|per ?cento\b)", testo)]


# ------------------------------------------------------------------------------------------------ norme
_ART = re.compile(r"\bart(?:icolo|t?\.)?\s*(\d{1,4}(?:\.\d{1,3})?(?:[- ]?(?:bis|ter|quater|quinquies|sexies|septies|octies|"
                  r"novies|decies|undecies|duodecies|terdecies))?(?:\.\d{1,3})?)\b")
_ATTO_NUM = re.compile(r"\b(d\.?\s?lgs\.?|d\.?\s?l\.|d\.?p\.?r\.?|l\.|legge|d\.?m\.?)\s*(?:n\.\s*)?(\d+)\s*(?:/|del )\s*(\d{4})\b")
_SIGLE_ATTO = {"legge": "l.", "l.": "l.", "d.l.": "d.l.", "dl.": "d.l."}


def _codici() -> list[dict[str, Any]]:
    from .mappa import mappa

    return sorted(mappa()["codici_normattiva"], key=lambda c: -max(len(x) for x in c["sinonimi"]))


# Codici e testi unici che la biblioteca conserva come atti numerati: la sigla d'uso si traduce nell'atto.
CODICI_COME_ATTI = (
    (r"c\.\s?p\.\s?a\.|codice del processo amministrativo", "d.lgs. 104/2010"),
    (r"codice del consumo|cod\. cons\.", "d.lgs. 206/2005"),
    (r"codice della strada|c\.\s?d\.\s?s\.|\bcds\b", "d.lgs. 285/1992"),
    (r"codice della crisi(?: d'impresa)?|c\.\s?c\.\s?i\.\s?i\.|\bccii\b", "d.lgs. 14/2019"),
    (r"codice (?:della )?privacy", "d.lgs. 196/2003"),
    (r"t\.\s?u\.\s?b\.|testo unico bancario", "d.lgs. 385/1993"),
    (r"t\.\s?u\.\s?f\.|testo unico della finanza", "d.lgs. 58/1998"),
    (r"codice dei contratti pubblici", "d.lgs. 36/2023"),
    (r"statuto dei lavoratori", "l. 300/1970"),
    (r"testo unico (?:delle )?spese di giustizia|t\.\s?u\.\s?s\.\s?g\.", "d.p.r. 115/2002"),
    (r"codice dell'amministrazione digitale|\bcad\b", "d.lgs. 82/2005"),
)


def atto_citato(coda: str) -> str:
    """L'atto all'inizio del testo che segue un articolo: sigla del codice («c.c.») o «tipo numero/anno»."""
    for schema, atto in CODICI_COME_ATTI:
        m = re.search(schema, coda)
        if m and m.start() < 25:
            return atto
    for codice in _codici():
        for sin in sorted(codice["sinonimi"], key=len, reverse=True):
            if re.search(r"(?<![\w.])" + re.escape(sin.lower()) + r"(?![\w])", coda):
                return codice["sinonimi"][0].lower()
    a = _ATTO_NUM.search(coda)
    if a:
        tipo = a.group(1).replace(" ", "")
        tipo = _SIGLE_ATTO.get(tipo, tipo if tipo.endswith(".") else tipo + ".")
        return f"{tipo} {a.group(2)}/{a.group(3)}"
    return ""


def articolo_citato(testo: str) -> tuple[str, str] | None:
    """(articolo, atto) per «art. 163-bis c.p.c.», «articolo 5 del d.lgs. 28/2010», «art. 3 bis l. 53/1994»."""
    t = normalizza(testo)
    for m in _ART.finditer(t):
        atto = atto_citato(t[m.end():m.end() + 60])
        if atto:
            numero = m.group(1).replace(" ", "-")
            numero = re.sub(r"(\d)(bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)", r"\1-\2", numero)
            return numero, atto
    return None


def comma(testo: str) -> str:
    t = normalizza(testo)
    m = re.search(r"\bcomma (\d+(?:-?(?:bis|ter|quater))?)\b", t) or re.search(r"\b(\d+)(?:°|º)? comma\b", t)
    if m:
        return m.group(1)
    ordinali = {"primo": "1", "secondo": "2", "terzo": "3", "quarto": "4", "quinto": "5", "sesto": "6"}
    m = re.search(r"\b(primo|secondo|terzo|quarto|quinto|sesto) comma\b", t)
    return ordinali[m.group(1)] if m else ""


# ------------------------------------------------------------------------------------------------ pronunce
_ORGANO = (
    ("consulta", r"corte\s+cost(?:ituzionale)?\.?|c\.\s?cost\.|\bconsulta\b"),
    ("consiglio_di_stato", r"cons(?:iglio)?\.?\s*(?:di\s+)?st(?:ato)?\.?|c\.\s?d\.\s?s\.|\bcds\b"),
    ("cgars", r"c\.?\s?g\.?\s?a\.?\s?r\.?\s?s\.?|\bcga\b"),
    ("tar", r"\bt\.?\s?a\.?\s?r\.?(?=[\s,]|$)"),
    ("cassazione", r"\bcass(?:azione)?\b\.?|suprema corte"),
)
_NUMERO_ANNO = re.compile(r"\b(?:n\.?\s*)?(\d{1,6})\s*(?:/\s*((?:19|20)\d{2})\b|del(?:l')?\s*(?:\d{1,2}[./-]\d{1,2}[./-])?((?:19|20)\d{2})\b)")


def organo(testo: str) -> str:
    """L'organo giudicante nominato per primo: cassazione, consulta, consiglio_di_stato, tar, cgars."""
    t = normalizza(testo)
    primo = None
    for nome, schema in _ORGANO:
        m = re.search(schema, t)
        if m and (primo is None or m.start() < primo[0]):
            primo = (m.start(), nome)
    return primo[1] if primo else ""


def estremi_pronuncia(testo: str) -> dict[str, Any] | None:
    """{organo, numero, anno} quando la domanda cita una pronuncia con numero e anno (non un numero di ruolo)."""
    t = normalizza(testo)
    org = organo(t)
    if not org and not re.search(r"\b(?:sentenza|ordinanza|pronuncia|decisione)\b", t):
        return None
    for m in _NUMERO_ANNO.finditer(t):
        prima = t[max(0, m.start() - 12):m.start()]
        if re.search(r"r\.?\s?g\.?\s*(?:n\.?)?\s*$|ruolo\s*(?:n\.?)?\s*$|circolare\s*(?:n\.?)?\s*$|art\w*\.?\s*$|\d[./-]$|"
                     r"(?:\bl|legge|lgs|d\.\s?l|d\.?p\.?r|d\.?m|reg|direttiva)\.?\s*(?:n\.\s*)?$", prima):
            continue  # numero di ruolo, circolare, articolo o pezzo di una data (10/09/2025)
        return {"organo": org, "numero": int(m.group(1)), "anno": int(m.group(2) or m.group(3))}
    return None


_SEDI_TAR = ("lazio", "lombardia", "campania", "puglia", "sicilia", "toscana", "veneto", "piemonte", "emilia-romagna",
             "liguria", "calabria", "sardegna", "marche", "abruzzo", "umbria", "basilicata", "molise", "friuli venezia giulia",
             "trentino", "valle d'aosta", "milano", "brescia", "napoli", "salerno", "bari", "lecce", "palermo", "catania",
             "firenze", "venezia", "torino", "bologna", "parma", "genova", "reggio calabria", "catanzaro", "cagliari",
             "ancona", "l'aquila", "pescara", "perugia", "potenza", "campobasso", "trieste", "trento", "bolzano", "aosta",
             "latina", "roma")


def sede_tar(testo: str) -> str:
    t = normalizza(testo)
    m = re.search(r"\bt\.?\s?a\.?\s?r\.?\s+(?:del(?:la|l'|lo)?\s+|di\s+)?([a-z' -]{3,30})", t)
    if not m:
        return ""
    coda = m.group(1)
    for sede in sorted(_SEDI_TAR, key=len, reverse=True):
        if coda.startswith(sede):
            return sede.title().replace("Emilia-romagna", "Emilia-Romagna").replace("D'aosta", "d'Aosta")
    return ""


# ------------------------------------------------------------------------------------------------ fonti pubbliche
def ente_prassi(testo: str) -> str:
    t = normalizza(testo)
    if re.search(r"\binps\b", t):
        return "inps"
    if re.search(r"agenzia (?:delle )?entrate(?! riscossione)|\bade\b|\bentrate\b(?! riscossione)|\bfisco\b", t):
        return "agenzia_entrate"
    return ""


_SERIE = (("S1", r"prima serie|1a serie|1ª serie|serie speciale .{0,20}corte costituzionale"),
          ("S2", r"seconda serie|2a serie|unione europea"), ("S3", r"terza serie|3a serie|serie speciale regioni|serie .{0,10}regioni"),
          ("S4", r"quarta serie|4a serie|concorsi"), ("S5", r"quinta serie|5a serie|contratti pubblici"), ("SG", r"serie generale"))
_TIPI_GU = (("decreto legislativo", r"decret\w* legislativ\w*"), ("decreto-legge", r"decret\w*[- ]legge"),
            ("decreto ministeriale", r"decret\w* ministerial\w*"), ("legge", r"\bleggi\b|\blegge\b"))


def periodo_del_mese(testo: str) -> tuple[str, str]:
    """«di ottobre 2026», «nel mese di marzo 2025» → (01/10/2026, 31/10/2026); vuoto se non c'è un mese con l'anno."""
    import calendar

    m = re.search(r"\b(" + "|".join(MESI) + r")\s+((?:19|20)\d{2})\b", normalizza(testo))
    if not m:
        return "", ""
    mese, anno = MESI[m.group(1)], int(m.group(2))
    return f"01/{mese:02d}/{anno}", f"{calendar.monthrange(anno, mese)[1]:02d}/{mese:02d}/{anno}"


def serie_gazzetta(testo: str) -> str:
    t = normalizza(testo)
    for codice, schema in _SERIE:
        if re.search(schema, t):
            return codice
    return ""


def tipo_atto_gazzetta(testo: str) -> str:
    t = normalizza(testo)
    for tipo, schema in _TIPI_GU:
        if re.search(schema, t):
            return tipo
    return ""


# ------------------------------------------------------------------------------------------------ fascicolo
def numero_di_ruolo(testo: str) -> str:
    """Il numero di ruolo citato («R.G. n. 1234/2025», «RG 1234 del 2025», «ruolo generale 1234/2025», «RGNR 55/2024»,
    «n. 1234/2025 R.G.») come «RG 1234/2025»; vuoto se la domanda non cita un numero di ruolo."""
    t = normalizza(testo)
    sigla = r"(?:r\.?\s?g\.?(?:\s?n\.?\s?r\.?)?|rgnr|ruolo(?: generale)?|proc(?:edimento|\.)?|r\.?\s?g\.?\s?a\.?\s?c\.?)"
    numero = r"(\d{1,7})\s*(?:/|-|del(?:l')?\s+(?:anno\s+)?)\s*((?:19|20)\d{2})\b"
    m = re.search(r"\b" + sigla + r"\s*(?:n\.?\s*|nr\.?\s*|numero\s*)?" + numero, t) or re.search(
        r"\bn\.?\s*" + numero + r"\s*(?:di\s+)?" + sigla, t) or re.search(
        r"\b(?:causa|procedimento|giudizio|fascicolo|pratica|vertenza|contenzioso)\s+(?:iscritt\w+ al\s+|n\.?\s*|nr\.?\s*|numero\s*)?"
        r"(\d{1,7})\s*/\s*((?:19|20)\d{2})\b", t)
    return f"RG {m.group(1)}/{m.group(2)}" if m else ""


# Il rito della domanda, prima di scegliere un calcolatore di termini: un termine si calcola con le regole del suo rito.
_RITI = (
    ("penale", r"\bpenal\w*|imputat\w*|\breato\b|condann\w* penal|querel\w*|procura della repubblica|\bgip\b|\bgup\b|"
               r"bancarotta|\btruffa\b|\bfurto\b|\brapina\b|omicidio|estorsion\w*|peculato|corruzion\w*|spaccio|riciclaggio|"
               r"stalking|atti persecutori|maltrattament\w*|motivazione (?:riservata|contestuale)|544 c\.?p\.?p|"
               r"decreto penale|riesame|415-?bis|indagat\w*|c\.p\.p\.|codice di procedura penale|patteggi\w*|rito abbreviato"),
    ("sanzioni", r"\bmulta\b|\bmulte\b|verbale (?:di|del|della) (?:contestazione|polizia|vigili|codice della strada)|"
                 r"codice della strada|autovelox|eccesso di velocita|sanzion\w* amministrativ\w*|ordinanza[- ]ingiunzione|"
                 r"verbale .{0,20}(?:vigili|polizia (?:locale|municipale|stradale))|contravvenzione stradale|\bprefetto\b"),
    ("condominio", r"condomin\w*|delibera (?:dell'|condominiale|assembleare)|assemblea (?:di )?condomin\w*|1137"),
    ("tributario", r"tributari\w*|cartell\w* (?:esattorial\w*|di pagamento)|avviso di accertamento|corte di giustizia tributaria|"
                   r"commissione tributaria|agenzia (?:delle )?entrate|\bfisco\b|\bimposta\b.{0,40}(?:accertament|ricorso)"),
    ("amministrativo", r"\btar\b|t\.a\.r\.|consiglio di stato|giudice amministrativo|provvedimento amministrativo|"
                       r"bando|gara d'appalto|\bgara\b|appalt\w*|permesso di costruire|silenzio[- ]rifiuto|pubblica amministrazione"),
    ("lavoro", r"giudice del lavoro|rito del lavoro|controversi\w* di lavoro|causa di lavoro|\blicenziament\w*|"
               r"datore di lavoro|lavorator\w*|\b409 c\.?p\.?c|previdenzial\w*|\binps\b"),
)


def rito(testo: str) -> str:
    """penale, sanzioni, condominio, tributario, amministrativo, lavoro; vuoto = civile ordinario o non detto."""
    t = normalizza(testo)
    for nome, schema in _RITI:
        if re.search(schema, t):
            return nome
    return ""


# ------------------------------------------------------------------------------------------------ argomento
# Verbi e locuzioni dopo cui comincia il tema («quale norma disciplina X», «abbiamo trattato X»).
_CORNICE_VERBALE = re.compile(r"\b(?:disciplin\w+|regolat\w+(?: la materia di)?|guardare per|trattat\w+|seguit\w+|"
                              r"si e espress\w+ su|chiarit\w+ .{0,40}? su|norma su|norme su|disciplina di|la materia di)\s+")
# Preposizioni che introducono il tema: vale la prima.
_INTRODUCE_TEMA = re.compile(r"\b(?:in materia di|in tema di|a proposito di|riguardo (?:alla|agli|alle|al|ai|a)|"
                             r"sulla|sullo|sulle|sugli|sul|sui|su)\s+|\bsull'")
_ARTICOLI = re.compile(r"^(?:(?:il|lo|la|i|gli|le|un|una|uno)\s+|l'|un')")


def argomento(testo: str) -> str:
    """Il tema della domanda senza la cornice interrogativa.

    «Quale norma disciplina la caparra confirmatoria?» → «caparra confirmatoria»;
    «Novità normative in materia di mediazione obbligatoria?» → «mediazione obbligatoria»;
    «In quali pratiche abbiamo già trattato onere della prova?» → «onere della prova».
    """
    t = normalizza(testo).rstrip(" ?.!")
    t = re.split(r"[?!]|\.\s+(?=[a-z])", t)[0].strip()
    t = re.sub(r"\s*\([^)]*\)\s*$", "", t)
    resto = t
    cornici = list(_CORNICE_VERBALE.finditer(t))
    if cornici:
        resto = t[cornici[-1].end():]
    else:
        tema = _INTRODUCE_TEMA.search(t)
        if tema:
            resto = t[tema.end():]
    resto = _ARTICOLI.sub("", resto.strip())
    resto = re.sub(r"\s+(?:per favore|grazie|secondo te|grazie mille)$", "", resto)
    return togli_cornice(resto).strip(" ,;:'\"«»")


_CORNICE_INIZIALE = re.compile(
    r"^(?:(?:mi |ci )?(?:puoi |potresti |sai |vorrei |voglio |devo |dovrei |posso )?"
    r"(?:dirmi|dire|dici|diresti|indicar\w*|spiegar\w*|trovar\w*|cercar\w*|sapere|capire|conoscere|vedere|avere|dammi|dimmi|spiegami|trovami|"
    r"cercami|mostrami|serve|servono|occorre|aiutami (?:a|con))\s+)+|"
    r"^(?:(?:mi )?(?:fai|fammi|dammi|prepara(?:mi)?) (?:la |una )?scheda (?:pratica|operativa|della procedura) (?:di|del|della|dello|per|sul|sulla)|"
    r"(?:la |una )?scheda (?:pratica|operativa) (?:di|del|della|dello|per)|quali sono i passi (?:per|da seguire per)|i passi per|"
    r"come si (?:fa|procede|avvia|apre|propone|presenta|introduce|chiede|ottiene|deposita|attiva)|come (?:faccio|devo fare|si deve fare|procedo)|"
    r"che cosa serve per|cosa serve per|cosa (?:devo|bisogna) fare per|quali sono i passi per|qual e la procedura per|"
    r"procedura per|iter per|iter di|passi per|guida (?:pratica )?(?:a|per|su)?)\s+")
_ARTICOLI_INIZIALI = re.compile(r"^(?:(?:il|lo|la|i|gli|le|un|una|uno|del|della|dello|dei|delle|degli|di|per|a|al|alla)\s+|l'|un'|dell')+")


def togli_cornice(testo: str) -> str:
    """Il nome dell'istituto senza la richiesta intorno: «come si fa un'opposizione a decreto ingiuntivo» →
    «opposizione a decreto ingiuntivo»."""
    t = normalizza(testo).strip(" ?.!")
    for _ in range(3):
        nuovo = _ARTICOLI_INIZIALI.sub("", _CORNICE_INIZIALE.sub("", t)).strip()
        if nuovo == t:
            break
        t = nuovo
    return t


# ------------------------------------------------------------------------------------------------ calcolatori
_PAROLE_DATA_INIZIO = ("inizio", "decorrenza", "dal", "assunzione", "pubblicazione", "evento", "invio", "sinistro", "fatto",
                       "base", "contratto", "domanda", "avvio", "lesione", "esecuzione")
_PAROLE_DATA_FINE = ("fine", "cessazione", "al", "liquidazione", "decesso", "consegna", "ritiro", "notificazione")
_PAROLE_DENARO = ("importo", "capitale", "valore", "retribuzione", "reddito", "canone", "asse", "compenso", "onorario",
                  "rendita", "patrimonio", "netto", "lordo", "credito", "spese", "prezzo", "somma", "imponibile")


def _etichetta(campo: dict[str, Any]) -> str:
    return normalizza(campo.get("etichetta", ""))


def campi_calcolatore(testo: str, campi: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """I campi del calcolatore che la domanda valorizza: «etichetta valore», scelte nominate, date e importi.

    1. etichetta del campo seguita dal valore (numero, data o etichetta di una scelta);
    2. scelte: l'etichetta (o il valore) di un'opzione nominata nella domanda, la più lunga;
    3. date non ancora usate: ai campi data di inizio e poi di fine, nell'ordine della domanda;
    4. importi in euro non usati: al primo campo di denaro; percentuali al campo percentuale; «N anni» all'età/anni.
    """
    t = normalizza(testo)
    uscita: dict[str, Any] = {}
    usati: set[str] = set()
    # 1. etichetta seguita dal valore (la prima occorrenza dell'etichetta che è davvero seguita da un valore)
    for nome, campo in campi.items():
        et = _etichetta(campo)
        if len(et) < 3:
            continue
        for occorrenza in re.finditer(r"(?<![\w])" + re.escape(et) + r"(?![\w])", t):
            coda = t[occorrenza.end():occorrenza.end() + 60].lstrip(" :=")
            if campo["tipo"] == "date":
                d = date_it(coda[:12])
                if d:
                    uscita[nome] = d[0]
                    usati.add(d[0])
                    break
            elif campo["tipo"] == "number":
                m = re.match(r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)\s*(euro|€)?", coda)
                if m:
                    cifra = (m.group(1).replace(".", "").replace(",", ".") if m.group(2) or "." in m.group(1)
                             else m.group(1).replace(",", "."))
                    valore = float(cifra)
                    uscita[nome] = valore if (m.group(2) or not valore.is_integer()) else int(valore)
                    usati.add(m.group(1))
                    break
            elif campo["tipo"] == "select":
                scelta = _scelta(coda[:50], campo, all_inizio=True)
                if scelta is not None:
                    uscita[nome] = scelta
                    break
    # 2. scelte nominate
    for nome, campo in campi.items():
        if nome in uscita or campo["tipo"] != "select":
            continue
        scelta = _scelta(t, campo)
        if scelta is not None:
            uscita[nome] = scelta
    # 3. date libere
    libere = [d for d in date_it(testo) if d not in usati]
    date_campi = [n for n, c in campi.items() if c["tipo"] == "date" and n not in uscita]
    inizio = [n for n in date_campi if any(p in n.lower() or p in _etichetta(campi[n]) for p in _PAROLE_DATA_INIZIO)]
    fine = [n for n in date_campi if n not in inizio and any(p in n.lower() or p in _etichetta(campi[n]) for p in _PAROLE_DATA_FINE)]
    gia_inizio = any(n in uscita and c["tipo"] == "date" and any(p in n.lower() or p in _etichetta(c) for p in _PAROLE_DATA_INIZIO)
                     for n, c in campi.items())
    if gia_inizio:
        inizio = []
    for nome, valore in zip([*inizio[:1], *fine[:1]], libere, strict=False):
        uscita[nome] = valore
    # 4. importi, percentuali, anni
    numeri = [n for n, c in campi.items() if c["tipo"] == "number" and n not in uscita]
    soldi = [v for v in importi(testo)]
    denaro = [n for n in numeri if any(p in n.lower() or p in _etichetta(campi[n]) for p in _PAROLE_DENARO)]
    for nome, valore in zip(denaro[:1], soldi, strict=False):
        uscita[nome] = valore
    perc = percentuali(testo)
    campi_perc = [n for n in numeri if n not in uscita and re.search(r"%|perc|tasso|punti|invalidit", n.lower() + " " + _etichetta(campi[n]))]
    for nome, valore in zip(campi_perc[:1], perc, strict=False):
        uscita[nome] = int(valore) if valore.is_integer() else valore
    mese_anno = re.search(r"\b(\d{1,2})\s*/\s*((?:19|20)\d{2})\b(?!\s*/)", t)
    mesi = [n for n in numeri if n not in uscita and "mese" in n.lower() + _etichetta(campi[n])]
    anni_campo = [n for n in numeri if n not in uscita and re.search(r"\banno\b|_anno", n.lower() + " " + _etichetta(campi[n]))]
    if mese_anno and not _DATA.search(t[max(0, mese_anno.start() - 3):mese_anno.end()]) and mesi and anni_campo:
        uscita[mesi[0]] = int(mese_anno.group(1))
        uscita[anni_campo[0]] = int(mese_anno.group(2))
    if not soldi and denaro and denaro[0] not in uscita:
        valore = re.search(r"\b(?:valore(?: della causa)?|causa|lite|controversia) (?:di |da )?(\d+(?:\.\d{3})*(?:,\d+)?)\b", t)
        if valore:
            cifra = float(valore.group(1).replace(".", "").replace(",", "."))
            uscita[denaro[0]] = int(cifra) if cifra.is_integer() and "," not in valore.group(1) else cifra
    anni = re.search(r"\b(\d{1,3})\s+anni\b", t)
    campi_anni = [n for n in numeri if n not in uscita and re.search(r"\beta\b|anni|anzianit", _etichetta(campi[n]) + " " + n.lower())]
    if anni and campi_anni:
        uscita[campi_anni[0]] = int(anni.group(1))
    figli = re.search(r"\b(\d{1,2})\s+figli\b", t)
    campi_figli = [n for n in numeri if n not in uscita and "figli" in (n.lower() + _etichetta(campi[n]))]
    if figli and campi_figli:
        uscita[campi_figli[0]] = int(figli.group(1))
    if "comune" in campi and "comune" not in uscita:
        m = re.search(r"\b(?:comune di|per il comune di|per)\s+([A-Z][a-zà-ÿ']+(?:\s+[A-Z][a-zà-ÿ']+)?)", testo)
        if m:
            uscita["comune"] = m.group(1)
    return uscita


def _scelta(testo: str, campo: dict[str, Any], *, all_inizio: bool = False) -> str | None:
    etichette = campo.get("etichette") or {v: v for v in campo.get("valori", [])}
    migliore = None
    for valore, etichetta in etichette.items():
        if valore in ("", "0", "1"):  # sì/no: solo con l'etichetta del campo (passo 1)
            if not all_inizio:
                continue
        for forma in {normalizza(etichetta), normalizza(etichetta).split(" — ")[0].split(" (")[0], normalizza(valore).replace("_", " ")}:
            if len(forma) < (1 if all_inizio else 2):
                continue
            ok = re.match(re.escape(forma) + r"(?![\w])", testo) if all_inizio else re.search(r"(?<![\w])" + re.escape(forma) + r"(?![\w])", testo)
            if ok and (migliore is None or len(forma) > migliore[0]):
                migliore = (len(forma), valore)
    return migliore[1] if migliore else None


# ------------------------------------------------------------------------------------------------ filtri facoltativi
def pratica_indicata(testo: str) -> str:
    """La pratica nominata nella domanda: numero di ruolo («RG 1234/2025») o nome («pratica Castagnoli», «causa Castagnoli contro
    Pianigiani», «fascicolo Alfa srl»). Vuoto se la domanda non ne nomina una: allora vale il fascicolo aperto, se c'è.
    Se più pratiche corrispondono al nome, lo strumento chiede quale."""
    ruolo = numero_di_ruolo(testo)
    if ruolo:
        return ruolo
    m = re.search(r"\b(?:[Pp]ratica|[Cc]ausa|[Ff]ascicolo|[Pp]rocedimento|[Vv]ertenza|[Cc]ontenzioso|[Dd]ossier)\s+(?:del(?:la|lo|l')?\s+|di\s+)?"
                  r"((?:sig\.?\s+|sig\.ra\s+|dott\.?\s+)?[A-Z][\w'’]+(?:\s+(?:[A-Z][\w'’]+|srl|spa|sas|snc|s\.r\.l\.|s\.p\.a\.))*"
                  r"(?:\s+(?:contro|c\.|vs\.?|/)\s+[A-Z][\w'’]+(?:\s+[A-Z][\w'’]+)*)?)", testo)
    return m.group(1).strip(" ?,.;") if m else ""


def sezione_cassazione(testo: str) -> str:
    t = normalizza(testo)
    if re.search(r"sezioni unite|\bs\.\s?u\.|\bss\.\s?uu\.", t):
        return "S.U."
    m = re.search(r"\bsez(?:ione|\.)?\s*(lav(?:oro|\.)?|trib(?:utaria|\.)?|[ivx]{1,4}|\d)\b", t)
    if not m:
        return ""
    v = m.group(1)
    return "lavoro" if v.startswith("lav") else "tributaria" if v.startswith("trib") else v.upper()


def anno_citato(testo: str) -> int | None:
    """L'anno nominato da solo («nel 2023», «del 2022», «dal 2020»), non quello di una data o di un numero/anno."""
    t = normalizza(testo)
    for m in re.finditer(r"\b(?:nel|del|dal|anno|degli anni|dell'anno|negli ultimi anni,? dal|emess\w* nel|pubblicat\w* nel)?\s*((?:19|20)\d{2})\b", t):
        prima = t[max(0, m.start() - 12):m.start()]
        dopo = t[m.end():m.end() + 2]
        if not re.search(r"\d\s*[/.-]?\s*$|n\.\s*\d+\s*$|n\.?\s*\d+\s*(?:del\s*)?$|art\w*\.?\s*$|\d+\s*del\s*$", prima) and not dopo.startswith("/"):
            return int(m.group(1))
    return None


_MATERIE = (("lavoro", r"\blavor\w*|licenziament\w*|dipendent\w*"), ("famiglia", r"famiglia|separazion\w*|divorzi\w*|affidament\w*|minori"),
            ("penale", r"\bpenal\w*|querela|reato|imputat\w*"), ("amministrativo", r"amministrativ\w*|\btar\b|appalt\w*"),
            ("tributario", r"tributari\w*|fiscal\w*|cartell\w*"), ("locazioni", r"locazion\w*|sfratt\w*|affitt\w*"),
            ("condominio", r"condomin\w*"), ("esecuzioni", r"esecuzion\w*|pignorament\w*|precetto"),
            ("successioni", r"successi\w*|eredit\w*|testament\w*"), ("consumatori", r"consumator\w*"),
            ("societario", r"societari\w*|societa\b"), ("civile", r"\bcivil\w*"))


def materia(testo: str, *, anche_senza_preposizione: bool = False) -> str:
    """La materia nominata («in materia di lavoro», «diritto di famiglia»); con ``anche_senza_preposizione`` basta la
    parola tipica della materia (per filtrare i modelli d'atto: «modello di ricorso per licenziamento» → lavoro)."""
    t = normalizza(testo)
    for nome, schema in _MATERIE:
        prima = r"" if anche_senza_preposizione else r"(?:di|in|per|materia|diritto)\s+(?:del\s+|della\s+|di\s+)?"
        if re.search(prima + r"(?:" + schema + ")", t):
            return nome
    return ""


def stato_scadenze(testo: str) -> str:
    t = normalizza(testo)
    if re.search(r"scadut\w*|passat\w*|non rispettat|mancat\w*", t):
        return "scadute"
    if re.search(r"\btutte\b(?! (?:le|i) (?:pratiche|fascicoli|cause))", t):  # «tutte le pratiche» non è lo stato
        return "tutte"
    if re.search(r"\baperte\b|\baperti\b|da fare|pendent\w*|ancora da|in corso|prossim\w*|imminent\w*|in scadenza|da rispettare|"
                 r"non (?:ancora )?(?:chiuse|evase|fatte)", t):
        return "aperte"
    return ""


__all__ = ["rito", "anno_citato", "materia", "pratica_indicata", "sezione_cassazione", "stato_scadenze", "argomento", "articolo_citato", "atto_citato", "campi_calcolatore", "comma", "date_it", "ente_prassi",
           "estremi_pronuncia", "importi", "normalizza", "numero_di_ruolo", "organo", "percentuali", "sede_tar",
           "serie_gazzetta", "tipo_atto_gazzetta"]
