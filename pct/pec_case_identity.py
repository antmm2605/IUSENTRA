"""Cross-check procedural identity without treating a recipient tax code as a party."""
from __future__ import annotations
import re
import unicodedata
from typing import Any


def _tokens(value: Any) -> tuple[str, ...]:
    text = unicodedata.normalize('NFKD', str(value or '').casefold())
    return tuple(sorted(re.findall(r'[a-z0-9]+', ''.join(c for c in text if not unicodedata.combining(c)))))


def _office(value: Any) -> tuple[str, ...]:
    return tuple(token for token in _tokens(value) if token not in {'di', 'del', 'della', 'd', 'ordinario', 'ordinaria'})


def _case_role(fascicolo: Any) -> tuple[str, str] | None:
    number = str(getattr(fascicolo, 'numero_rg', '') or '').strip()
    year = str(getattr(fascicolo, 'anno_rg', '') or '').strip()
    full = re.fullmatch(r'([0-9]+)\s*/\s*([0-9]{4})', number)
    if full:
        if year and year != full.group(2):
            return None
        return str(int(full.group(1))), full.group(2)
    if number.isdigit() and re.fullmatch(r'[0-9]{4}', year):
        return str(int(number)), year
    return None


def case_identity_evidence(profile: dict[str, Any], fascicolo: Any, client: dict[str, Any] | None = None) -> dict[str, Any]:
    source_office = _office(profile.get('ufficio'))
    case_office = _office(getattr(fascicolo, 'tribunale', ''))
    # Generic classifications are not an identified judicial office.
    source_known = len(source_office) >= 2 and 'giudiziario' not in source_office
    office_match = bool(source_known and case_office and source_office == case_office)
    source_name = _tokens(profile.get('cliente'))
    case_name = _tokens(getattr(fascicolo, 'nome_cliente', ''))
    names = [_tokens(value) for value in (profile.get('parti_processuali') or []) if isinstance(value, str)]
    name_match = bool(case_name and case_name in [source_name, *names])
    client = client or {}
    source_cf = re.sub(r'\s+', '', str(profile.get('codice_fiscale_cliente') or '')).upper() if source_name == case_name else ''
    client_cf = re.sub(r'\s+', '', str(client.get('codice_fiscale') or '')).upper()
    cf_match = bool(source_cf and client_cf and source_cf == client_cf)
    # Only an explicit XML client/party label supports an identity contradiction;
    # a guessed name in a subject line must not exclude the client's case.
    name_certified = str(profile.get('cliente_origine') or '').startswith('Comunicazione.xml:')
    source_rg = re.search(r'(?<![0-9])([0-9]+)\s*/\s*([0-9]{4})(?![0-9])', str(profile.get('numero_ruolo_certificato') or profile.get('numero_rg') or ''))
    case_rg = _case_role(fascicolo)
    source_rg_key = (str(int(source_rg.group(1))), source_rg.group(2)) if source_rg else None
    rg_match = bool(source_rg_key and case_rg and source_rg_key == case_rg)
    conflicts = []
    if source_name == case_name and profile.get('codice_fiscale_cliente_stato') in {'letto_non_valido', 'fonti_discordanti'}:
        conflicts.append('Codice fiscale della parte non valido o fonti discordanti')
    if source_rg_key and case_rg and source_rg_key != case_rg:
        conflicts.append('R.G. e anno del procedimento discordanti')
    if source_known and case_office and not office_match:
        conflicts.append('Ufficio giudiziario discordante')
    if name_certified and source_name and case_name and not name_match:
        conflicts.append('Nome e cognome del cliente discordanti')
    if source_cf and client_cf and not cf_match:
        conflicts.append('Codice fiscale del cliente discordante')
    return {'rg_match': rg_match, 'client_tax_code_match': cf_match, 'client_tax_code_available': bool(client_cf), 'office_match': office_match, 'client_name_match': name_match,
            'client_name_source': profile.get('cliente_origine') or '',
            'party_tax_code_present': bool(source_cf),
            'recipient_tax_code_is_party_identity': False, 'conflicts': conflicts}


def client_tax_code_from_documents(profile: dict[str, Any], documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Read a declared party code with its source; never infer it from a name."""
    from pct.archivio_letture.estrazione_parti import estrai_parti
    from pct.clienti import GestioneClienti
    from pct.codice_fiscale import _checksum
    from itertools import permutations

    target = _tokens(profile.get('cliente'))
    if len(target) < 2 or len(target) > 5:
        return dict(profile)
    evidence: list[dict[str, Any]] = []
    labelled = re.compile(r'\b(?:c\.?\s*f\.?|codice\s+fiscale)\s*[:=]?\s*([A-Z0-9]{16})\b', re.I)
    stop = re.compile(r'\b(?:rappresentat\w*|difes\w*|difensor\w*|avv\.?|avvocat\w*|contro(?:parte)?|destinatario)\b', re.I)

    def remember(code: str, document: dict[str, Any], excerpt: str) -> None:
        code = re.sub(r'\s+', '', code).upper()
        valid = bool(GestioneClienti.valida_cf(code) and _checksum(code[:15]) == code[15])
        evidence.append({'codice_fiscale': code, 'valido': valid, 'filename': document['filename'],
                         'sha256': document.get('sha256') or '', 'citazione': excerpt[:500]})

    # Reuse the party reader. A narrow labelled-block reader covers flattened
    # native PDF text whose line structure is absent, without including counsel.
    alternatives = '|'.join(r"[\s'’.-]+".join(re.escape(token) for token in order)
                            for order in permutations(target))
    anchor = re.compile(r'(?<!\w)(?:' + alternatives + r')(?!\w)', re.I)
    for document in documents[:20]:
        filename = str(document.get('filename') or '')
        if not filename.lower().endswith(('.pdf', '.pdf.zip', '.doc', '.docx', '.txt', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.p7m')):
            continue
        text = str(document.get('text') or '')[:24000]
        for party in estrai_parti(text, cliente=str(profile.get('cliente') or '')):
            if _tokens(party.nome) == target and party.codice_fiscale and party.ruolo not in {'difensore_assistito', 'difensore_controparte', 'ctu', 'testimone'}:
                remember(party.codice_fiscale, document, party.citazione)
        for match in anchor.finditer(text[:7000]):
            tail = text[match.end():match.end() + 500]
            if not re.match(r'[\s,;:()]*\b(?:nat[oa]|c\.?\s*f\.?|codice\s+fiscale)\b', tail, re.I):
                continue
            boundary = stop.search(tail)
            own_data = tail[:boundary.start()] if boundary else tail
            declared = labelled.search(own_data)
            if declared:
                remember(declared.group(1), document, text[match.start():match.end() + declared.end()])
    result = dict(profile)
    codes = {entry['codice_fiscale'] for entry in evidence}
    result['codice_fiscale_cliente_nome'] = str(profile.get('cliente') or '')
    result['codice_fiscale_cliente_evidenze'] = evidence[:10]
    result['codice_fiscale_cliente_stato'] = 'non_presente_nella_fonte'
    if len(codes) == 1:
        result['codice_fiscale_cliente'] = next(iter(codes))
        result['codice_fiscale_cliente_stato'] = 'letto_valido' if all(entry['valido'] for entry in evidence) else 'letto_non_valido'
    elif len(codes) > 1:
        result.pop('codice_fiscale_cliente', None)
        result['codice_fiscale_cliente_stato'] = 'fonti_discordanti'
    return result


def document_case_identity_evidence(text: str, fascicolo: Any) -> dict[str, Any]:
    """Match the issuing header, never a cited case in the reasoning."""
    from itertools import permutations
    from legal_ocr.ner_legal import extract_numero_ruolo, extract_uffici
    from pct.archivio_letture.collaudo import ufficio_esplicito_del_ruolo
    from pct.registro_letture.fatti_repository import Fatto

    header = re.split(r"\b(?:motivazione|motivi\s+della\s+decisione|ragioni\s+della\s+decisione)\b", str(text or '')[:6000], maxsplit=1, flags=re.I)[0]
    # I confini di riga delimitano l'ufficio: appiattirli fa inglobare
    # al resolver il titolo o il numero della sentenza nella sede.
    header = header.strip()
    roles = extract_numero_ruolo(header)
    source_role = roles[0] if roles else {}
    office = ufficio_esplicito_del_ruolo(Fatto(categoria='ruolo', campo='rg', valore='', contesto=header))
    if not office:
        offices = extract_uffici(header)
        office = offices[0] if offices else ''
    expected = _tokens(getattr(fascicolo, 'nome_cliente', ''))
    name_present = False
    if 2 <= len(expected) <= 5:
        normalized = ' '.join(re.findall(r'[a-z0-9]+', ''.join(c for c in unicodedata.normalize('NFKD', header.casefold()) if not unicodedata.combining(c))))
        name_present = any(' ' + ' '.join(order) + ' ' in ' ' + normalized + ' ' for order in permutations(expected))
    profile = {'ufficio': office, 'cliente': getattr(fascicolo, 'nome_cliente', '') if name_present else '',
               'cliente_origine': 'intestazione del provvedimento',
               'numero_ruolo_certificato': str(source_role.get('numero') or '') + '/' + str(source_role.get('anno') or '')}
    evidence = case_identity_evidence(profile, fascicolo)
    evidence['source_office'] = office
    evidence['source_rg'] = profile['numero_ruolo_certificato']
    evidence['complete_match'] = all(evidence[key] for key in ('rg_match', 'client_name_match', 'office_match')) and not evidence['conflicts']
    return evidence

