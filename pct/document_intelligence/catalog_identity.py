"""Identità documentali strutturali, prima dei richiami presenti nel corpo.

Un indice non è l'atto elencato; un XML di dati non è il PDF del provvedimento.
Le regole richiedono intestazione e segnali concordanti nel contenuto.
"""
from __future__ import annotations

import re
from typing import Any

from pct.fascicoli import TipoDocumento
from .catalog_fields import catalog_xml, invoice_bodies, invoice_data, xml_value


def structural_identity(text: str) -> dict[str, Any] | None:
    raw = str(text or '').strip()
    head = re.sub(r'\s+', ' ', raw[:2000]).casefold()

    def result(label: str, role: str, section: str, tipo: TipoDocumento, pattern: str,
               evidence: str, confidence: int = 98, deposit: str = 'allegato') -> dict[str, Any]:
        return dict(label=label, role=role, section=section, tipo_documento=tipo,
                    confidence=confidence, evidence=evidence, deposit_role=deposit,
                    deposit_candidate=deposit != 'fuori_busta', excerpt_pattern=pattern)

    if raw.startswith('<'):
        root = catalog_xml(raw)
        if root is None:
            return None
        tag = str(root.tag)
        if tag.startswith('{http://schemi.processotelematico.giustizia.it/'):
            local = tag.rsplit('}', 1)[-1]
            return result(f'Dati strutturati PST — {local}', 'dati_atto', 'allegati', TipoDocumento.ALLEGATO,
                          r'<(?:[A-Za-z0-9_]+:)?' + re.escape(local) + r'\b',
                          'XML: elemento radice e namespace ministeriale PST; non è il PDF dell’atto', 99, 'fuori_busta')
        bodies = invoice_bodies(root)
        if bodies and all(invoice_data(body) for body in bodies):
            types = {xml_value(data, 'TipoDocumento') for body in bodies for data in invoice_data(body)}
            label = 'Nota di credito in XML FatturaPA' if types == {'TD04'} else 'Documento fiscale in XML FatturaPA'
            if len(bodies) > 1:
                label = 'Lotto di documenti fiscali in XML FatturaPA'
            return result(label, 'fattura_xml', 'pagamenti', TipoDocumento.PARCELLA,
                          r'<(?:[A-Za-z0-9_]+:)?FatturaElettronica\b',
                          'radice FatturaPA, intestazione e corpi fiscali; non prova emissione SdI o pagamento', 98)
        return None

    if re.match(r'^attestazione\s+di\s+conformit[aà]\b', head) and re.search(r'\battesta\b', head) and re.search(r'\bconform[ie]\b', head):
        return result('Attestazione di conformità', 'attestazione', 'allegati', TipoDocumento.ALLEGATO,
                      r'\battestazione\s+di\s+conformit[aà]\b',
                      'titolo e dichiarazione di conformità; gli atti elencati sono oggetto dell’attestazione', 98, 'attestazione')

    if re.match(r'^istanza\s+di\s+mediazione\b', head) and 'organismo di mediazione' in head and len(re.findall(r'_{5,}', raw)) >= 3:
        return result('Modulo di istanza di mediazione', 'modulo_mediazione', 'allegati', TipoDocumento.ALLEGATO,
                      r'\bistanza\s+di\s+mediazione\b',
                      'modello dell’organismo con campi prestampati da compilare; non prova un deposito', 97, 'fuori_busta')

    # Alcuni moduli ufficiali non hanno titolo: l'identità nasce dalla
    # dichiarazione di conferimento iniziale, non da una procura citata.
    if re.match(r'^(?:il|la|i|le)\s+sottoscritt[oaie]\b', head) and re.search(r'\bconferisc[oe]\s+procura\s+speciale\s+sostanziale\b', head[:900]) and 'organismo di mediazione' in head:
        blank = len(re.findall(r'_{5,}', raw)) >= 3
        return result('Modulo di procura speciale per la mediazione' if blank else 'Procura speciale per la mediazione',
                      'modulo_procura_mediazione' if blank else 'procura_mediazione', 'procure', TipoDocumento.PROCURA,
                      r'\bconferisc[oe]\s+procura\s+speciale\s+sostanziale\b',
                      'dichiarazione iniziale di conferimento dei poteri per la mediazione' + ('; campi da compilare, non prova una procura conferita' if blank else '; firme e poteri da verificare'),
                      97, 'fuori_busta' if blank else 'procura')

    sentence_title = r'\bs\s*e\s*n\s*t\s*e\s*n\s*z\s*a\b'
    if 'in nome del popolo italiano' in head[:500] and re.search(sentence_title, head[:1200]) and re.search(r'\b(?:tribunale|corte|giudice di pace)\b', head[:500]):
        return result('Sentenza', 'provvedimento', 'provvedimenti', TipoDocumento.SENTENZA,
                      sentence_title, 'intestazione giudiziaria, formula solenne e titolo di sentenza concordanti', 99, 'fuori_busta')

    if re.match(r'^indice\s+(?:dei\s+)?documenti\b', head) and re.search(r'\b(?:deposito telematico|art\.? 74)\b', head):
        return result('Indice dei documenti depositati', 'indice_documenti', 'allegati', TipoDocumento.ALLEGATO,
                      r'\bindice\s+(?:dei\s+)?documenti\b', 'intestazione: indice e riferimenti al deposito documentale', 99, 'fuori_busta')

    if re.search(r'\bnota\s+(?:di\s+)?iscrizione\s+a\s+ruolo\b', head.replace('’', ' ').replace("'", ' ')) and re.search(r'\b(?:tribunale|giudice di pace|corte)\b', head):
        return result('Nota di iscrizione a ruolo', 'nota_iscrizione_ruolo', 'atti', TipoDocumento.DEPOSITO_PCT,
                      r'\bnota\s+(?:d[’\x27i ]+)?iscrizione\s+a\s+ruolo\b', 'intestazione della nota e ufficio giudiziario; non è la ricevuta CU', 98, 'fuori_busta')

    if re.search(r'(?im)^\s*atto\s+di\s+citazione\s*$', raw[:2000]) and re.search(r'\b(?:tribunale|giudice di pace|corte)\b', head) and re.search(r'\brappresentat\w*\s+e\s+difes\w*\b', head):
        return result('Atto di citazione', 'atto_principale', 'atti', TipoDocumento.CITAZIONE,
                      r'\batto\s+di\s+citazione\b', 'titolo autonomo dell’atto, ufficio giudiziario e rappresentanza delle parti', 98, 'atto_principale')

    if re.search(r'\bintimazione(?:\s*testi)?\b', head[:500]) and re.search(r'(?im)^\s*intima\s*$|\bintima\s+(?:alla|al|a)\b', raw):
        label = 'Intimazione a comparire con documentazione di notifica' if re.search(r'\bavviso\s+di\s+ricevimento\b', raw, re.I) else 'Intimazione a comparire'
        return result(label, 'atto_processuale', 'notifiche', TipoDocumento.NOTIFICA,
                      r'\bintimazione\b', 'titolo e formula autonoma di intimazione presenti nel documento', 97, 'prova_notifica')

    if re.search(r'\brelata\s+di\s+notifica\b', head[:500]) and re.search(r'\bho\s+notificato\b', head):
        return result('Relata di notifica', 'relata', 'notifiche', TipoDocumento.NOTIFICA,
                      r'\brelata\s+di\s+notifica\b', 'intestazione della relata e attestazione dell’attività di notificazione', 98, 'prova_notifica')

    if 'studio legale' in head[:350] and re.search(r'\bgent\W', head[:550]) and 'oggetto:' in head:
        label = 'Lettera stragiudiziale — sollecito' if 'sollecito' in head[:700] else 'Lettera stragiudiziale'
        return result(label, 'corrispondenza_stragiudiziale', 'comunicazioni', TipoDocumento.COMUNICAZIONE,
                      r'\bstudio\s+legale\b|\boggetto\s*:', 'carta intestata, formula di saluto al destinatario e oggetto della lettera', 96)

    if re.search(r'\b(?:fattura\s+pro[ -]?forma|avviso\s+di\s+parcella|notula)\b', head[:400]) and re.search(r'\b(?:totale|compenso|onorari)\b', head):
        return result('Proforma / avviso di parcella', 'proforma', 'pagamenti', TipoDocumento.PARCELLA,
                      r'\b(?:fattura\s+pro[ -]?forma|avviso\s+di\s+parcella|notula)\b',
                      'intestazione di documento proforma e importi; non prova emissione della fattura o pagamento', 97)

    if re.search(r'\bfattura\b', head[:400]) and 'totale fattura' in head and re.search(r'\b(?:p\.?\s*iva|partita iva|cliente)\b', head):
        return result('Fattura', 'fattura', 'pagamenti', TipoDocumento.PARCELLA,
                      r'\bfattura\b', 'intestazione della fattura, cliente e totale del documento', 97)

    if re.search(r'\bvisura\s+(?:per\s+soggetto|catastale|per\s+immobile)\b', head[:600]) and re.search(r'\b(?:servizi catastali|catasto dei fabbricati|catasto terreni)\b', head):
        return result('Visura catastale', 'visura_catastale', 'allegati', TipoDocumento.ALLEGATO,
                      r'\bvisura\s+(?:per\s+soggetto|catastale|per\s+immobile)\b', 'intestazione della visura e dati del catasto', 97)

    if re.search(r'\bposte\s*italiane\b', head) and all(formula in head for formula in ('avvenuta consegna', 'mancata consegna', 'avvenuto ritiro')):
        return result('Documentazione di recapito postale', 'prova_notifica', 'notifiche', TipoDocumento.NOTIFICA,
                      r'\b(?:avvenuta|mancata)\s+consegna\b', 'modulo postale con opzioni di consegna e ritiro; esito non dedotto dalle caselle prestampate', 98, 'prova_notifica')

    if re.search(r'\bavviso\s+di\s+ricevimento\b', head) and re.search(r'\b(?:raccomandat\w*|notificazione|poste)\b', head):
        return result('Avviso di ricevimento postale', 'prova_notifica', 'notifiche', TipoDocumento.NOTIFICA,
                      r'\bavviso\s+di\s+ricevimento\b', 'modulo di ricevimento con riferimenti alla spedizione postale', 98, 'prova_notifica')

    if re.match(r'^accordo\s+(?:di\s+)?(?:conciliazione|mediazione)\b', head) and 'organismo di mediazione' in head and re.search(r'\ble parti\s+(?:convengono|concordano|si accordano)\b', head):
        return result('Accordo di mediazione', 'accordo_mediazione', 'allegati', TipoDocumento.CONTRATTO,
                      r'\baccordo\s+(?:di\s+)?(?:conciliazione|mediazione)\b',
                      'intestazione di accordo, organismo e dichiarazione concorde delle parti; firme ed efficacia non verificate', 97)

    if re.search(r'\bverbale\b.{0,90}\bmediazione\b', head) and 'organismo di mediazione' in head:
        outcome = re.search(r'\b(mancata adesione|mancata partecipazione|esito negativo)\b', head)
        label = f'Verbale di mediazione — {outcome.group(1)}' if outcome else 'Verbale di mediazione'
        return result(label,
                      'verbale_mediazione', 'allegati', TipoDocumento.VERBALE,
                      r'\bverbale\b.{0,90}\bmediazione\b', 'intestazione del verbale e organismo di mediazione', 98)

    # Un provvedimento senza titolo resta tale: non si inventa «ordinanza» o
    # «decreto» dalla sola presenza di disposizioni o dal nome del file.
    court_head = re.sub(r'\s+', ' ', raw[:500]).casefold()
    court = bool(re.search(r'\btribunale\b', court_head) and re.search(r'(?im)^\s*(?:il giudice|il presidente)\b', raw[:500]))
    disposition = bool(re.search(r'\b(?:DISPONE|ASSEGNA|DELEGA|P\.?\s*Q\.?\s*M\.?)\b', raw) or re.search(r'(?im)^\s*(?:dispone|assegna|delega|p\.?\s*q\.?\s*m\.?)\s*$', raw))
    if court and disposition:
        if re.search(r'(?im)^\s*decreto\s*$', raw[:600]):
            label, tipo, formula = 'Decreto dell’ufficio giudiziario', TipoDocumento.DECRETO, r'\bdecreto\b'
        elif re.search(r'(?im)^\s*ordinanza\s*$', raw[:600]):
            label, tipo, formula = 'Ordinanza dell’ufficio giudiziario', TipoDocumento.ORDINANZA, r'\bordinanza\b'
        else:
            label, tipo, formula = 'Provvedimento dell’ufficio giudiziario', TipoDocumento.ATTO_GIUDIZIARIO, r'\b(?:dispone|assegna|delega|p\.?\s*q\.?\s*m\.?)\b'
        # La specifica formula del decreto di fissazione è gestita dal resolver.
        if not re.search(r'\bdecreto\s+di\s+fissazione\b', raw, re.I):
            return result(label, 'provvedimento', 'provvedimenti', tipo, formula,
                          'intestazione dell’ufficio, giudice e dispositivo autonomo concordanti', 97, 'fuori_busta')
    return None
