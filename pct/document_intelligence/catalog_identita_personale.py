"""Il documento d'identità del cliente: la scansione si riconosce dai suoi campi, non da un titolo.

Una carta d'identità (cartacea o elettronica), un passaporto, una patente,
un permesso di soggiorno non hanno un titolo su una riga: l'OCR di una
scansione restituisce etichette sparse — «REPUBBLICA ITALIANA», «CARTA DI
IDENTITÀ / IDENTITY CARD», «COGNOME / SURNAME», «NOME / NAME», «LUOGO E DATA
DI NASCITA», «CITTADINANZA», «SCADENZA», la riga a lettura ottica con «<<» —
spesso con l'apostrofo letto male («IDENTITA'»). Qui l'identità nasce dalla
concordanza fra il tipo di documento e almeno due campi anagrafici, e si
rafforza quando cognome e nome del cliente del fascicolo compaiono nel testo:
allora il catalogo dice «Carta d'identità di Mario Rossi».

Base normativa: art. 35 D.P.R. 445/2000 (documenti di identità e di
riconoscimento equipollenti); D.M. 23 dicembre 2015 (carta d'identità
elettronica, campi e zona a lettura ottica); art. 1 D.P.R. 445/2000 lett. c)
e d) (documento di identità e di riconoscimento).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any
from pct.fascicoli import TipoDocumento


def residenza_riga_cartacea(testo: str) -> tuple[str, str] | None:
    """Etichetta Via e valore distinto; Num/Piano delimitano il civico.

    Non ripara lettere del nome della strada o cifre del civico.
    La seconda Via deve essere effettivamente letta, non ricostruita.
    """
    matches = re.findall(
        r'\bVIA[. :]+(VIA\s*\d?\s*[A-ZÀ-Ü0-9 .\'’/-]{2,75}?)\s+N(?:UM[A-Z]?|[NM])?[. :]*'
        r'(\d{1,5}[A-Z]?)(?=\s+P(?:IAN|LAN|AN)[A-Z]*\b)', str(testo or '').upper())
    values = {(re.sub(r'^VIA(?=\d)', 'VIA ', re.sub(r'\s+', ' ', via).strip(' .')), civic) for via, civic in matches}
    return next(iter(values)) if len(values) == 1 else None


def concorda_residenza_cartacea(first, second, source: str) -> bool:
    """Solo I/1 nel numero iniziale della strada, corroborato nella fonte.

    Non cambia lettere nel nome proprio della strada né cifre del civico.
    """
    def compact(value):
        return re.sub(r'[ .]+', '', value.upper())
    if not first or not second or first[1] != second[1]:
        return False
    if compact(first[0]) == compact(second[0]):
        return True
    pair = sorted((first[0], second[0]), key=lambda value: 'VIA I' not in value)
    ambiguous, numeric = pair
    if not re.match(r'^VIA I(?=[A-Z])', ambiguous) or not re.match(r'^VIA 1', numeric):
        return False
    corrected = re.sub(r'^VIA I', 'VIA 1', ambiguous)
    if compact(corrected) != compact(numeric):
        return False
    suffix = re.sub(r'^VIA 1\s*', '', numeric)
    tokens = re.findall(r'[A-ZÀ-Ü0-9]+', suffix)
    literal = r'[ .]*'.join(re.escape(token) for token in tokens)
    # La lettura originaria deve mostrare proprio il numero 1 e il medesimo
    # resto della strada, nella stessa riga delimitata dal civico e Piano.
    return bool(re.search(r'\bVI[AISN][ .:]+VI[AISN]\s*1\s*' + literal
        + r'\s+N(?:UM[A-Z]?|[NM])?[. :]*' + re.escape(first[1])
        + r'(?=\s+P(?:IAN|LAN|AN)[A-Z]*\b)', source.upper()))

CARATTERI_ESAMINATI = 4000
FONTE = "normattiva_dpr_445_2000_documentazione_amministrativa"

# (chiave, etichetta, espressione sul testo normalizzato: minuscolo, senza accenti né apostrofi)
TIPI: tuple[tuple[str, str, str], ...] = (
    ("carta_identita", "Carta d'identità", r"\bcarta\s+d\s*i?\s*identita\b|\bcarta\s+identita\b|\bidentity\s+card\b|\bcarta\s+d\s+identit\w*\b|\b[ic]<ita[a-z0-9<]{15,}(?=\s|$)|\bc\.?i\.?e\.?\b(?=.*\b(?:cognome|surname|nome|name)\b)"),
    ("passaporto", "Passaporto", r"\bpassaporto\b|\bpassport\b"),
    ("patente", "Patente di guida", r"\bpatente\s+di\s+guida\b|\bpatente\b|\bdriving\s+licen[cs]e\b"),
    ("permesso_soggiorno", "Permesso di soggiorno", r"\bpermesso\s+di\s+soggiorno\b|\bcarta\s+di\s+soggiorno\b|\bresidence\s+permit\b"),
)
# Campi anagrafici e di rilascio che compaiono su un documento di riconoscimento.
CAMPI: tuple[tuple[str, str], ...] = (
    ("cognome", r"\bcognome\b|\bsurname\b"),
    ("nome", r"\bnome\b|\bname\b"),
    ("nascita", r"\bnat[oa]\s+(?:il|a)\b|\bnascita\b|\bbirth\b"),
    ("cittadinanza", r"\bcittadinanza\b|\bnationality\b"),
    ("residenza", r"\bresidenza\b|\bresidente\b|\baddress\b"),
    ("scadenza", r"\bscadenza\b|\bexpiry\b|\bvalid[ao]\s+fino\b|\bvalidita\b"),
    ("statura", r"\bstatura\b|\bheight\b|\bcapelli\b|\bocchi\b|\bsesso\b|\bsex\b"),
    ("emissione", r"\bcomune\s+di\b|\bsindaco\b|\bministero\s+dell\s*interno\b|\brilasciat[oa]\b|\bemissione\b|\bquestura\b|\bprefettura\b"),
    ("codice_fiscale", r"\b[a-z]{6}\d{2}[a-z]\d{2}[a-z]\d{3}[a-z]\b"),
    ("lettura_ottica", r"[a-z0-9<]{5,}<<[a-z0-9<]{5,}"),
)
_AUTORITA = re.compile(r"\brepubblica\s+italiana\b|\bministero\s+dell\s*interno\b|\bcomune\s+di\b|\bquestura\b|\bprefettura\b|\bmotorizzazione\b")
# Un atto che allega o cita il documento d'identità non è il documento d'identità.
_ATTO = re.compile(r"\bprocura\b|\bdeleg[oa]\b|\bricorso\b|\btribunale\b|\bgiudice\b|\bcitazione\b|\bcomparsa\b|\bmemoria\b|\bsi\s+allega\b|\ballego\b|\bcopia\s+(?:del|della)\b|\bdichiara\b")
_NOME_FILE = re.compile(r"^(?:copia\s+|scansione\s+|scan\s+)?(?:carta\s+d\s*i?\s*identita|documento\s+d\s*i?\s*identita|carta\s+identita|c\.?i\.?e|passaporto|patente(?:\s+di\s+guida)?|permesso\s+di\s+soggiorno|tessera\s+sanitaria)(?:\s+(?:fronte|retro|fronte\s+retro|cliente|[a-z]+(?:\s+[a-z]+)?))?(?:\s+\d{1,2})?$")

# Profili condivisi: il formato guida l'interpretazione delle etichette;
# non certifica il contenuto né l'autenticità della scansione.
PROFILI_ITALIANI = {
    'carta_cartacea': {'label': 'Carta d’identità cartacea',
        'zones': ('comune_emettitore', 'numero_carta', 'anagrafica', 'residenza', 'rilascio', 'scadenza'),
        'source': 'https://www.cartaidentita.interno.gov.it/cose-la-carta/caratteristiche-del-documento/'},
    'cie': {'label': 'Carta d’identità elettronica',
        'zones': ('fronte_anagrafica', 'fronte_emissione_scadenza', 'retro_codice_fiscale_residenza', 'retro_mrz'),
        'source': 'https://www.cartaidentita.interno.gov.it/cose-la-carta/caratteristiche-del-documento/'},
    'tessera_sanitaria': {'label': 'Tessera sanitaria',
        'zones': ('fronte_codice_fiscale', 'fronte_anagrafica', 'fronte_scadenza_ts', 'retro_team'),
        'source': 'https://www1.agenziaentrate.gov.it/web_app_entrate/tessera_sanitaria.html/1000'},
}


def modello_identita_italiana(testo: str) -> str:
    """Il modello dalle sue diciture; non certifica titolare o valori.

    Un retro CIE può mancare del titolo del fronte. Le due coppie di
    etichette bilingui lo distinguono dalla tessera e dalla carta cartacea.
    La forma MRZ individua il formato, mentre la validazione resta al lettore.
    Un contenuto misto non può scegliere il primo modello trovato.
    """
    text = str(testo or '')
    health = bool(re.search(r'\bTESSERA\s+SANITARI\w*\b', text, re.I))
    title = bool(re.search(r"CARTA\s+D[’']?I?\s*IDENTIT[ÀA]?|IDENTITY\s+CARD", text, re.I))
    rear = all(re.search(pattern, text, re.I) for pattern in (
        r'\bCODICE\s+FISCALE\b', r'\bFISCAL\s+CODE\b',
        r'\b(?:INDIRIZZO\s+DI\s+RESIDENZA|RESIDENCE|ADDRESS)\b'))
    optical = bool(re.search(r'\bI<ITA[A-Z0-9<]{20,}', text, re.I))
    if health:
        return '' if title or rear or optical else 'tessera_sanitaria'
    if rear or optical or (title and re.search(r'IDENTITY\s+CARD|SURNAME|\b[A-Z]{2}\d{5}[A-Z]{2}\b', text, re.I)):
        return 'cie'
    # La faccia interna del libretto non ripete il titolo della copertina.
    # I connotati fisici e le etichette anagrafiche identificano il modello,
    # non il titolare: nessun valore o collegamento è certificato da qui.
    paper_inside = all(re.search(pattern, text, re.I) for pattern in (
        r'\bCOGNOME\b', r'\bNOME\b', r'\bNAT[OA]\s+(?:IL|A)\b',
        r'\bRESIDENZA\b', r'\bSTATURA\b', r'\bCAPELLI\b', r'\bOCCHI\b',
    )) and not re.search(r'\b(?:SURNAME|IDENTITY\s+CARD|FISCAL\s+CODE)\b', text, re.I)
    if paper_inside:
        return 'carta_cartacea'
    return 'carta_cartacea' if title else ''


def segmenti_identita_italiana(testo: str) -> list[dict[str, Any]]:
    """Separa carte diverse nella lettura; nessuna posizione assoluta di pagina.

    Il preambolo della prima carta (numero, Comune, scadenza) viene preservato.
    La tessera sanitaria non fornisce rilascio/scadenza/residenza della C.I.
    """
    marker = re.compile(r"CARTA\s+D[’']?I?\s*IDENTIT[ÀA]?|IDENTITY\s+CARD|TESSERA\s+SANITARI\w*", re.I)
    matches = []
    for match in marker.finditer(str(testo or '')):
        if matches and match.start() - matches[-1].end() < 48 and not re.match('TESSERA', match.group(), re.I) and not re.match('TESSERA', matches[-1].group(), re.I):
            continue
        matches.append(match)
    if not matches:
        model = modello_identita_italiana(testo)
        return [{'model': model, 'start': 0, 'end': len(testo), 'text': testo,
                 'profile': PROFILI_ITALIANI[model]}] if model else []
    starts = [0]
    for index, match in enumerate(matches[1:], 1):
        start = match.start()
        if not re.match('TESSERA', match.group(), re.I):
            # Un riquadro recuperato può riportare numero e intestazione
            # prima del titolo CIE: quel preambolo non appartiene alla TS
            # che lo precede nel testo. Non spostare etichette o dati per
            # somiglianza; richiedere il preambolo esplicito e contiguo.
            prefix_start = max(matches[index - 1].end(), start - 240)
            prefix = testo[prefix_start:start]
            header = re.search(
                r'(?m)^[ \t#]*(?:[A-Z]{2}\d{5}[A-Z]{2}[ \t]*\n[ \t\n#]*)?'
                r'REPUBBLICA\s+ITALIANA[ \t]*(?:\n[ \t\n#]*MINISTERO\s+DELL[\'’]INTERNO)?[ \t\n#]*$',
                prefix, re.I,
            )
            if header:
                start = prefix_start + header.start()
        starts.append(start)
    result = []
    for index, match in enumerate(matches):
        end = starts[index + 1] if index + 1 < len(starts) else len(testo)
        chunk = testo[starts[index]:end]
        if re.match(r'TESSERA', match.group(), re.I):
            model = 'tessera_sanitaria'
        else:
            model = modello_identita_italiana(chunk)
            if not model:
                continue
        result.append({'model': model, 'start': starts[index], 'end': end, 'text': chunk,
            'profile': PROFILI_ITALIANI[model]})
    return result


def normalizza(testo: str) -> str:
    """Minuscolo, senza accenti, apostrofi e simboli: «CARTA D'IDENTITÀ» diventa «carta d identita»."""
    piatto = unicodedata.normalize("NFD", str(testo or "").casefold())
    piatto = "".join(c for c in piatto if unicodedata.category(c) != "Mn")
    piatto = re.sub(r"[’'`´]", " ", piatto)
    piatto = re.sub(r"[^a-z0-9<]+", " ", piatto)
    return re.sub(r"\s+", " ", piatto).strip()


def _cliente_nel_testo(testo_normalizzato: str, cliente: str) -> str:
    """Il nome del cliente se cognome e nome (tutte le parole di almeno tre lettere) compaiono nel testo."""
    parole = [p for p in normalizza(cliente).split() if len(p) >= 3 and not p.isdigit()]
    if len(parole) < 2:
        return ""
    if all(re.search(rf"\b{re.escape(parola)}\b", testo_normalizzato) for parola in parole):
        return " ".join(str(cliente or "").split())
    return ""


def documento_identita_personale(testo: str, *, cliente: str = "") -> dict[str, Any] | None:
    """L'identità di una scansione di documento di riconoscimento, o None."""
    grezzo = str(testo or "")
    if not grezzo.strip():
        return None
    piatto = normalizza(grezzo[:CARATTERI_ESAMINATI])
    if _ATTO.search(piatto[:1500]):
        return None
    tipo = next(((chiave, etichetta) for chiave, etichetta, espressione in TIPI if re.search(espressione, piatto)), None)
    if tipo is None:
        return None
    campi = [chiave for chiave, espressione in CAMPI if re.search(espressione, piatto)]
    if len(campi) < 2:
        return None
    chiave, etichetta = tipo
    autorita = bool(_AUTORITA.search(piatto))
    titolare = _cliente_nel_testo(piatto, cliente)
    confidenza = 96 if len(campi) >= 3 or autorita else 90
    if titolare:
        confidenza = 99
    label = f"{etichetta} di {titolare}" if titolare else etichetta
    evidenza = f"scansione di documento di riconoscimento: tipo «{etichetta.lower()}» e campi {', '.join(campi[:5])}"
    if autorita:
        evidenza += "; autorità emittente"
    evidenza += f"; cognome e nome coincidono con il cliente del fascicolo ({titolare})" if titolare else "; titolare non riscontrato con il cliente del fascicolo"
    evidenza += " (art. 35 D.P.R. 445/2000)"
    return dict(
        label=label, role="documento_identita", section="identita", tipo_documento=TipoDocumento.ALLEGATO,
        confidence=confidenza, evidence=evidenza, deposit_role="allegato", deposit_candidate=True,
        excerpt_pattern=r"carta\s+d.{0,3}identit\w*|identity\s+card|passaporto|passport|patente|permesso\s+di\s+soggiorno|cognome|surname",
        fonte=FONTE, tipo_identita=chiave, titolare=titolare,
    )


def documento_identita_dal_nome(nome_file: str) -> str:
    """L'etichetta del documento di riconoscimento se il nome del file lo dice senza ambiguità («Carta d'identità.PDF»)."""
    base = re.sub(r"\.(?:pdf|jpe?g|png|tiff?|p7m|heic)$", "", str(nome_file or "").strip(), flags=re.IGNORECASE)
    base = re.sub(r"\.(?:pdf|jpe?g|png|tiff?)$", "", base, flags=re.IGNORECASE)
    piatto = normalizza(base)
    if not piatto or not _NOME_FILE.match(piatto):
        return ""
    for chiave, etichetta, espressione in TIPI:
        if re.search(espressione.split("(?=")[0], piatto) or (chiave == "carta_identita" and re.search(r"\b(?:documento\s+d\s*i?\s*identita|c\s?i\s?e)\b", piatto)):
            return etichetta
    if "tessera sanitaria" in piatto:
        return "Tessera sanitaria / codice fiscale"
    return "Documento d'identità"


__all__ = ["CAMPI", "FONTE", "TIPI", "documento_identita_dal_nome", "documento_identita_personale", "normalizza"]
