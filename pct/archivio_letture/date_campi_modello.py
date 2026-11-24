"""Date nominate della fonte: riusa il calendario e l'identità condivisi.

Le date dell'atto introduttivo servono a stabilire quale testo del codice si applica alla causa: il d.lgs.
149/2022 (art. 35, comma 1, come modificato dalla l. 197/2022) vale per i procedimenti instaurati dopo il
28/02/2023. La causa si instaura con il deposito del ricorso (art. 414-415 c.p.c.; art. 125 c.p.c.) o con la
notificazione dell'atto di citazione (artt. 163 e 39, terzo comma, c.p.c.); l'iscrizione a ruolo segue il
deposito dell'atto introduttivo con la nota d'iscrizione (art. 168 c.p.c.; art. 71 disp. att. c.p.c.). Le
fonti certe sono il provvedimento del giudice che le richiama, la copia del fascicolo informatico attestata
dall'avvocato (art. 196-octies disp. att. c.p.c.) e la relata della notificazione (art. 3-bis l. 53/1994).
"""
from __future__ import annotations

import re

from legal_ocr.formulario.date import trova_date
from pct.pec_case_identity import document_case_identity_evidence, client_tax_code_from_documents
from pct.registro_letture.fatti_repository import Fatto

VERSIONE_DATE_CAMPI_MODELLI = '2026.10.10.date-campi-modello.v3'
# Le regole dell'atto introduttivo (24/11/2026) entrano nel motore con il segno REGOLA_ATTO_INTRODUTTIVO di
# riletture_mirate: nessuna rilettura generale, solo le fonti che contengono quelle date.

CAMPI_DATE = {
    "data_deposito_ricorso": "Data di deposito del ricorso",
    "data_iscrizione_ruolo": "Data di iscrizione a ruolo",
    "data_notifica_citazione": "Data di notifica dell'atto di citazione",
    "data_emissione_decreto": "Data di emissione del decreto",
    "data_pronuncia_sentenza": "Data di pronuncia della sentenza",
}
#: i campi che dicono quando la causa è stata instaurata
CAMPI_INSTAURAZIONE = ("data_deposito_ricorso", "data_iscrizione_ruolo", "data_notifica_citazione")

# Fra il nome dell'atto e il participio può stare la sua qualificazione («ricorso ex art. 414 c.p.c.»,
# «atto di citazione in opposizione»), mai un altro atto: «il ricorso avverso il decreto … depositato il»
# è la data del decreto.
_ALTRO_ATTO = r"decreto|sentenza|ordinanza|provvedimento|memori\w*|comparsa|note|verbale|precetto|terz\w*|chiamat\w*|reclamo|udienz\w*"
_FRAMMENTO = rf"(?:(?!\b(?:{_ALTRO_ATTO})\b)[^;\n]){{0,120}}?"
_ANCORE = {
    "data_deposito_ricorso": rf"\bricorso\b{_FRAMMENTO}\bdepositat[oa]\s+(?:telematicamente\s+)?(?:in\s+cancelleria\s+)?(?:in\s+data|il)\s*$",
    "data_iscrizione_ruolo": r"(?<![\w-])(?:iscritt[ao]\s+a(?:l)?\s+ruolo(?:\s+generale)?|iscrizione\s+a(?:l)?\s+ruolo(?:\s+generale)?(?:\s+della\s+causa)?)"
                             r"(?:\s+(?:avvenuta|effettuata))?\s+(?:in\s+data|il|del)\s*$",
    "data_notifica_citazione": rf"\bcitazione\b{_FRAMMENTO}\bnotificat[oa]\s+(?:\w+mente\s+)?(?:a\s+mezzo\s+(?:pec|posta(?:\s+elettronica\s+certificata)?|ufficiale\s+giudiziario)\s+)?(?:in\s+data|il)\s*$",
    "data_emissione_decreto": r"\bdecreto\s+(?:(?:di\s+)?fissazione\s+(?:dell[’']|della\s+)?udienza[\s,]+)?(?:emesso\s+(?:dal\s+[^;\n]{1,100}\s+)?)?(?:in\s+data|del)\s*$",
    "data_pronuncia_sentenza": r"\bsentenza\s+(?:pronunciata|emessa)\s+(?:in\s+data|il)\s*$",
}
_FINESTRA = 200
# «nuova iscrizione», «reiscrizione», «entro il»: non è la data dell'iscrizione della causa.
_ISCRIZIONE_NON_INTRODUTTIVA = re.compile(r"(?:nuova|successiva|re)\s*$|entro\s*$", re.I)
# Nel giudizio d'appello la narrazione del primo grado ripete le date del primo grado: non sono quelle di
# questo procedimento. Si accettano solo le formule che nominano l'appello.
_GRADO_APPELLO = re.compile(r"(?im)^\s*corte\s+d['’]\s*appello\b|\bappellant[ei]\b|\bappellat[oa]\b")
_APPELLO = re.compile(r"\bappell\w*|\bgravame\b|\bimpugnazion\w*", re.I)


def _fonte_provvedimento(raw):
    """Un provvedimento del procedimento o la copia attestata del fascicolo informatico."""
    attestation = bool(
        re.search(r"(?im)^\s*ATTESTAZIONE\s+DI\s+CONFORMIT[ÀA]\b", raw[:1000])
        and re.search(r"sono\s+conformi\s+alle\s+copie\s+informatiche\s+presenti\s+nel\s+fascicolo\s+informatico", raw, re.I)
    )
    provvedimento = bool(re.search(r"(?im)^\s*(?:SENTENZA|DECRETO|ORDINANZA|VERBALE)\b", raw[:6000]))
    return attestation, provvedimento


def _fatto(field, token, passage, identity, origine, *, prove=(), identity_code="identita_congiunta_provvedimento"):
    return Fatto(
        categoria="metadato_fascicolo", campo=field,
        valore=token.data.isoformat(), valore_letto=token.letto,
        etichetta=CAMPI_DATE[field], contesto=passage,
        posizione=token.inizio, origine=origine, confidenza=1.0 if origine == "nativo" else 0.7,
        verifica="verificata" if origine == "nativo" else "plausibile", prove=[
            {"codice": identity_code, "esito": "ok", "dettaglio": identity},
            {"codice": "data_processuale_nominata", "esito": "ok", "dettaglio": passage},
            *prove,
        ],
    )


# Relata della notificazione in proprio a mezzo PEC (art. 3-bis l. 53/1994): per il destinatario la notifica
# si perfeziona con la ricevuta di avvenuta consegna; la relata deve dire che l'atto notificato è la citazione.
_RELATA_CITAZIONE = re.compile(r"\b(?:ho\s+notificato|notifico|ha\s+notificato)\b[^;]{0,200}?\batto\s+di\s+citazione\b", re.I)
_RDAC_GIORNO = re.compile(r"ricevuta\s+di\s+avvenuta\s+consegna[\s\S]{0,300}?\bil\s+giorno\s+$", re.I)


def _normale(value):
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    words = re.findall(r"[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c)))
    return " ".join(w for w in words if w not in {"ordinario", "ordinaria", "di", "del", "della", "d"})


def _ufficio_nominato(raw, fascicolo):
    ufficio = _normale(getattr(fascicolo, "tribunale", ""))
    return len(ufficio.split()) >= 2 and f" {ufficio} " in f" {_normale(raw)} "


def _notifica_citazione_da_relata(raw, identity, origine, fascicolo):
    from .estrazione_notifiche import _relata_operativa

    relata = _RELATA_CITAZIONE.search(raw)
    if relata is None or not _relata_operativa(raw):
        return []
    # La qualificazione segue il nome dell'atto: «atto di citazione per chiamata del terzo», «… in appello»,
    # «… in riassunzione» (la riassunzione prosegue la causa già instaurata, art. 125 disp. att. c.p.c.).
    formula = relata.group(0) + re.split(r"[,;\n]", raw[relata.end():relata.end() + 80], maxsplit=1)[0]
    if re.search(r"chiamat\w*|terz[oi]\b|integrazione\s+del\s+contraddittorio|riassunzion\w*", formula, re.I):
        return []
    if re.search(rf"\b(?:{_ALTRO_ATTO})\b", formula, re.I) or (bool(_APPELLO.search(formula)) != bool(_GRADO_APPELLO.search(raw[:6000]))):
        return []
    # Prima della notifica la causa non ha ancora un ruolo: bastano il cliente e l'ufficio del fascicolo nominati
    # nell'atto, senza un ruolo discordante.
    if not identity["client_name_match"] or not _ufficio_nominato(raw[:6000], fascicolo) or any("R.G." in c for c in identity["conflicts"]):
        return []
    result = []
    for token in trova_date(raw):
        before = raw[max(0, token.inizio - 320):token.inizio]
        if token.sostituzioni or not _RDAC_GIORNO.search(before) or token.inizio < relata.start():
            continue
        passage = " ".join((formula + " … " + before[-120:] + token.letto).split())
        result.append(_fatto("data_notifica_citazione", token, passage, identity, origine, identity_code="identita_fonte_atti", prove=[
            {"codice": "tipo_fonte", "esito": "ok", "dettaglio": "relata"},
            {"codice": "relata_notifica_citazione", "esito": "ok", "dettaglio": " ".join(formula.split())},
            {"codice": "ricevuta_avvenuta_consegna", "esito": "ok",
             "dettaglio": "Notifica perfezionata per il destinatario alla consegna (art. 3-bis, comma 3, l. 53/1994)."},
        ]))
    return result


# Copia del fascicolo informatico scaricata dal PolisWeb e attestata dall'avvocato (art. 196-octies disp. att.
# c.p.c.): «Ricorso Rossi.PDF - Depositante: VERDI PAOLO; Tipologia: Atto principale; Data deposito: 19-06-2023».
# Il depositante distingue l'atto della parte assistita da quello della controparte.
_COPIA_POLISWEB = re.compile(
    r"(?:-\s*(?P<etichetta>[^()\n;]{2,80}?)\s*\(File:\s*[^)\n]{1,120}\)[^;\n]{0,120}?Contenuto\s+del\s+documento:\s*)?"
    r"(?P<file>[^\n;:]{1,120}?)\s*-\s*Depositante:\s*(?P<depositante>[^;\n]{2,80}?)\s*;\s*"
    r"Tipologia:\s*(?P<tipologia>[^;\n]{2,60}?)\s*;\s*Data\s+deposito:\s*$", re.I)
# Indice dei documenti del deposito telematico (art. 74 disp. att. c.p.c.): la busta che contiene l'atto
# introduttivo con la nota d'iscrizione a ruolo. La data è quella dell'invio: il deposito si perfeziona con la
# ricevuta di avvenuta consegna, di regola lo stesso giorno, e per questo l'indice resta un riscontro.
_INDICE_DEPOSITO = re.compile(r"relativi\s+al\s+deposito\s+telematico\s+inviato\s+in\s+data\s+$", re.I)
_ATTO_CON_NOTA = re.compile(r"^\s*:\s*-\s*(?P<atto>ricorso|atto\s+di\s+citazione|citazione)\b[^\n]{0,60}?nota\s+d.?\s*iscrizione\s+a\s+ruolo", re.I)
_RICORSO = re.compile(r"\bricors[oi]\b", re.I)
_CITAZIONE = re.compile(r"\bcitazione\b", re.I)
# Gli atti principali che non introducono la causa, anche se nominano il ricorso.
_ATTO_NON_INTRODUTTIVO = re.compile(r"memori|comparsa|note|reclamo|appell|istanza|decreto|sentenza|ordinanza|verbale|riassun|integra", re.I)
# «decreto di assegnazione» (art. 168-bis c.p.c.) senza intestazione: il presidente assegna la causa.
_ASSEGNAZIONE = re.compile(r"\b(?:il|la)\s+presidente\b[^;]{0,160}?\b(?:assegna|designa)\b[^;]{0,40}?\bcausa\b", re.I)


def _cliente_nominato(raw, fascicolo):
    from itertools import permutations

    nome = _normale(getattr(fascicolo, "nome_cliente", "")).split()
    testo = f" {_normale(raw)} "
    return 2 <= len(nome) <= 5 and any(f" {' '.join(ordine)} " in testo for ordine in permutations(nome))


_PARTI = re.compile(r"\b(?:promoss[ao]\s+da|tra|ricorrent\w*|attor[ei]|attrice|nei\s+confronti|contro)\b", re.I)


def _parti_compatibili(header, fascicolo):
    """Senza le parti nell'intestazione (decreto di assegnazione) o con il cliente fra le parti, anche con un secondo
    nome («Pasquale Carmelo Rossi» per «Pasquale Rossi»): mai un provvedimento che nomina altre parti."""
    if not _PARTI.search(header):
        return True
    nome = set(_normale(getattr(fascicolo, "nome_cliente", "")).split())
    return len(nome) >= 2 and nome <= set(_normale(header).split())


def _stesso_avvocato(nome, fascicolo):
    letto = set(_normale(nome).split()) - {"avv", "avvocato"}
    for campo in ("avvocato_referente", "avvocato_dominus"):
        studio = set(_normale(getattr(fascicolo, campo, "")).split()) - {"avv", "avvocato"}
        if len(studio) >= 2 and studio == letto:
            return True
    return False


def _identita_fonte_atti(raw, identity, fascicolo):
    """Indice del deposito e copie PolisWeb: il cliente nominato e il ruolo o l'ufficio del fascicolo, senza discordanze."""
    if any("R.G." in c or "Codice fiscale" in c for c in identity["conflicts"]):
        return ""
    if not (identity["client_name_match"] or _cliente_nominato(raw, fascicolo)):
        return ""
    if identity["rg_match"]:
        return "cliente e numero di ruolo del fascicolo"
    return "cliente e ufficio giudiziario del fascicolo" if _ufficio_nominato(raw, fascicolo) else ""


def _date_da_copie_polisweb(raw, identity, origine, fascicolo):
    identita = _identita_fonte_atti(raw, identity, fascicolo)
    if not identita:
        return []
    result = []
    for token in trova_date(raw):
        if token.sostituzioni:
            continue
        match = _COPIA_POLISWEB.search(raw[max(0, token.inizio - 420):token.inizio])
        if match is None or not re.fullmatch(r"atto\s+principale", match.group("tipologia").strip(), re.I):
            continue
        nome = " ".join(filter(None, (match.group("etichetta"), match.group("file"))))
        if _ATTO_NON_INTRODUTTIVO.search(nome) or not (_RICORSO.search(nome) or _CITAZIONE.search(nome)):
            continue
        # Depositare la citazione è iscrivere la causa a ruolo (art. 165 e 168 c.p.c.); il ricorso instaura la causa.
        field = "data_deposito_ricorso" if _RICORSO.search(nome) else "data_iscrizione_ruolo"
        depositante = " ".join(match.group("depositante").split())
        dello_studio = _stesso_avvocato(depositante, fascicolo)
        passage = " ".join((match.group(0) + token.letto).split())
        result.append(_fatto(field, token, passage, identita, origine, prove=[
            {"codice": "tipo_fonte", "esito": "ok", "dettaglio": "copia_polisweb"},
            {"codice": "atto_principale_polisweb", "esito": "ok", "dettaglio": " ".join(nome.split())},
            {"codice": "depositante", "esito": "ok", "dettaglio": depositante},
            {"codice": "depositante_dello_studio", "esito": "ok" if dello_studio else "attenzione",
             "dettaglio": "Atto depositato dall'avvocato dello studio (parte assistita)." if dello_studio
             else "Atto depositato da un difensore diverso dall'avvocato dello studio."},
        ], identity_code="identita_fonte_atti"))
    return result


def _date_da_indice_deposito(raw, identity, origine, fascicolo):
    identita = _identita_fonte_atti(raw, identity, fascicolo)
    if not identita:
        return []
    result = []
    for token in trova_date(raw):
        if token.sostituzioni or not _INDICE_DEPOSITO.search(raw[max(0, token.inizio - 80):token.inizio]):
            continue
        atto = _ATTO_CON_NOTA.match(raw[token.fine:token.fine + 160])
        if atto is None:
            continue
        passage = " ".join((raw[max(0, token.inizio - 60):token.fine] + raw[token.fine:token.fine + atto.end()]).split())
        fields = ["data_iscrizione_ruolo"] + (["data_deposito_ricorso"] if _RICORSO.search(atto.group("atto")) else [])
        for field in fields:
            fact = _fatto(field, token, passage, identita, origine, prove=[
                {"codice": "tipo_fonte", "esito": "ok", "dettaglio": "indice_deposito"},
                {"codice": "nota_iscrizione_ruolo", "esito": "ok", "dettaglio": " ".join(atto.group(0).split())},
                {"codice": "data_invio_non_perfezionamento", "esito": "attenzione",
                 "dettaglio": "Data dell'invio della busta: il deposito si perfeziona con la ricevuta di avvenuta consegna; "
                              "vale come riscontro di un'altra fonte."},
            ], identity_code="identita_fonte_atti")
            # L'indice è redatto dall'avvocato che deposita: da solo non rende certa la data.
            fact.verifica, fact.confidenza = "plausibile", min(fact.confidenza, 0.7)
            result.append(fact)
    return result


def _date_nominate(raw, identity, origine, *, campi, prove, identity_code="identita_congiunta_provvedimento"):
    appello = bool(_GRADO_APPELLO.search(raw[:6000]))
    result = []
    for token in trova_date(raw):
        if token.sostituzioni:
            continue
        before = raw[max(0, token.inizio - _FINESTRA):token.inizio]
        for field in campi:
            match = re.search(_ANCORE[field], before, re.I)
            if match is None:
                continue
            passage = before[match.start():] + token.letto
            if field == "data_iscrizione_ruolo" and _ISCRIZIONE_NON_INTRODUTTIVA.search(before[:match.start()]):
                continue
            if field in CAMPI_INSTAURAZIONE and field != "data_iscrizione_ruolo" and bool(_APPELLO.search(passage)) != appello:
                # Grado diverso da quello del documento: la data è di un altro procedimento.
                continue
            result.append(_fatto(field, token, passage, identity, origine, prove=prove, identity_code=identity_code))
    return result


def estrai_date_modello(testo, *, fascicolo, origine="nativo", codice_fiscale_cliente=""):
    """Non deduce date da upload, termini futuri, citazioni o bozza dell'editor."""
    if fascicolo is None:
        return []
    raw = str(testo or "")
    identity = document_case_identity_evidence(raw, fascicolo)
    tax = client_tax_code_from_documents(
        {"cliente": getattr(fascicolo, "nome_cliente", "")}, [{"text": raw[:6000], "filename": "provvedimento.pdf"}]
    )
    if tax.get("codice_fiscale_cliente_stato") in {"letto_non_valido", "fonti_discordanti"}:
        return []
    declared = tax.get("codice_fiscale_cliente", "")
    if declared and declared != codice_fiscale_cliente.strip().upper():
        return []
    # La fonte deve essere un provvedimento del procedimento, non un modello
    # dell'avvocato che ne ripete una data ancora da verificare.
    attestation, provvedimento = _fonte_provvedimento(raw)
    result = []
    if identity["complete_match"] and (attestation or provvedimento):
        extra = [{"codice": "attestazione_copie_fascicolo_informatico", "esito": "ok", "dettaglio": "Identità congiunta verificata nella stessa attestazione."}] if attestation else []
        result += _date_nominate(raw, identity, origine, campi=tuple(_ANCORE), prove=[
            {"codice": "tipo_fonte", "esito": "ok", "dettaglio": "attestazione" if attestation else "provvedimento"}, *extra])
    elif (identity["rg_match"] and identity["office_match"] and not identity["conflicts"]
          and (provvedimento or _ASSEGNAZIONE.search(raw[:3000])) and _parti_compatibili(raw[:6000], fascicolo)):
        # Il provvedimento del giudice che porta ruolo e ufficio del fascicolo ma non il nome del cliente (decreto
        # di assegnazione, sentenza con il secondo nome): bastano per le sole date dell'atto introduttivo.
        result += _date_nominate(raw, identity, origine, campi=CAMPI_INSTAURAZIONE, identity_code="identita_ruolo_ufficio",
                                 prove=[{"codice": "tipo_fonte", "esito": "ok", "dettaglio": "provvedimento"}])
    result += _date_da_copie_polisweb(raw, identity, origine, fascicolo)
    result += _date_da_indice_deposito(raw, identity, origine, fascicolo)
    if not (attestation or provvedimento):
        result += _notifica_citazione_da_relata(raw, identity, origine, fascicolo)
    unici = {}
    for fact in result:
        unici.setdefault((fact.campo, fact.valore, fact.posizione), fact)
    return list(unici.values())
