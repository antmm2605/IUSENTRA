"""Lettura documento in memoria per la nuova anagrafica cliente."""

from __future__ import annotations

import re
import hashlib
from datetime import date
from pathlib import Path
from typing import Any

from werkzeug.datastructures import FileStorage
from core.security.upload_validator import validate_upload
from legal_ocr.motore.mrz import cifra_controllo as _mrz_check_digit, td1_verificata


def read_client_existing_document(manager: Any, repository: Any, tenant: str, client_id: str, *, service: Any = None, user_context: Any = None, client: Any = None) -> dict[str, Any]:
    """Trova la fonte nei soli fascicoli SQL del cliente, senza copiarla."""
    from pct.document_intelligence.catalog_identita_personale import documento_identita_dal_nome
    candidates = {}
    for case in manager.cerca(id_cliente=client_id, archiviati=True):
        if str(case.id_cliente) != client_id:
            continue
        assignments = {}
        for item in repository.list_catalog_assignments(tenant, case.id):
            assignments.setdefault(str(item.document_id), item)
        for doc in case.documenti:
            assignment = assignments.get(str(doc.id))
            meta = getattr(assignment, 'metadata', {}) or {}
            verified = bool(assignment and assignment.document_nature == 'documento_identita'
                and meta.get('identity_client_id') == client_id and meta.get('identity_holder'))
            if not verified and not documento_identita_dal_nome(str(getattr(doc, 'nome_originale', '') or doc.nome)):
                continue
            current = str(getattr(doc, 'hash_contenuto_sha256', '') or '')
            if verified and current and current != assignment.document_sha256:
                verified = False
            key = (current or assignment.document_sha256) if verified else f'{case.id}:{doc.id}'
            candidates.setdefault(key, (str(case.id), str(doc.id), verified))
    verified = [value for value in candidates.values() if value[2]]
    selected = verified or list(candidates.values())
    if len(selected) != 1:
        message = ('Sono presenti più documenti d’identità: apri il documento da leggere dal fascicolo.'
            if selected else 'Nessun documento d’identità disponibile nei fascicoli collegati al cliente.')
        raise ClientDocumentReaderError(message, status_code=422)
    case_id, document_id, _ = selected[0]
    return read_client_case_document(manager, repository, tenant, case_id, client_id,
        document_id, service=service, user_context=user_context, client=client)


def read_client_case_document(manager: Any, repository: Any, tenant: str, case_id: str, client_id: str, document_id: str = "", *, service: Any = None, user_context: Any = None, acquire_missing: bool = True, client: Any = None) -> dict[str, Any]:
    """Riusa solo una lettura SQL corrente di un documento d'identità del cliente."""
    from web.services.fascicolo_documento_ocr import leggi_documento
    from web.services.document_tools import DocumentToolError
    case = manager.get(case_id)
    if case is None or str(getattr(case, 'id_cliente', '') or '') != client_id:
        raise ClientDocumentReaderError('Il fascicolo non appartiene al cliente aperto.', status_code=403)
    records = repository.list_documents(tenant, case_id)
    candidates = []
    for doc in case.documenti:
        if document_id and str(doc.id) != document_id:
            continue
        original_name = str(getattr(doc, 'nome_originale', '') or getattr(doc, 'nome', '') or '')
        if not original_name.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.p7m')):
            continue
        names = {str(getattr(doc, field, '') or '').casefold() for field in ('nome', 'nome_originale')}
        for record in records:
            if record.status != 'ready' or record.original_filename.casefold() not in names:
                continue
            extracted = repository.get_extracted_text(tenant, case_id, record.id, record.current_version_id)
            content = str(getattr(extracted, 'text', '') or '')
            identity_sources = _archived_identity_sources(extracted)
            parser_sources = identity_sources or [{'mode': 'unqualified', 'text': content}]
            from pct.document_intelligence.catalog_identita_personale import documento_identita_personale
            if not documento_identita_personale(content):
                continue
            # Il nome serve soltanto a trovare il candidato: è l'impronta del
            # contenuto attuale decifrato a dimostrare la corrispondenza.
            try:
                name, raw = leggi_documento(manager, case_id, str(doc.id))
            except DocumentToolError as exc:
                raise ClientDocumentReaderError('Il documento d’identità corrente non è leggibile: ' + str(exc), status_code=422) from exc
            sha = hashlib.sha256(raw).hexdigest()
            if sha != record.sha256:
                continue
            # Recupero una sola volta le letture CIE storiche con etichette
            # disordinate; la nuova versione conserva impronta e audit nativi.
            parsed = parse_client_document_text(content, filename=name, identity_sources=parser_sources)
            identity_profile = documento_identita_personale(content)
            invalid_layout = bool(identity_profile and identity_profile.get('tipo_identita') == 'carta_identita') and any(
                key not in parsed['patch'] for key in (
                    'nome', 'cognome', 'codice_fiscale', 'data_nascita', 'luogo_nascita',
                    'doc_numero', 'doc_rilasciato_da', 'doc_data_rilascio', 'doc_data_scadenza', 'via', 'comune'))
            if client is not None:
                from copy import deepcopy
                checked = deepcopy(parsed)
                try:
                    _verify_client_identity(content, checked, client)
                    invalid_layout = invalid_layout or any(key in parsed['patch'] and key not in checked['patch']
                        for key in ('nome', 'cognome'))
                except ClientDocumentReaderError:
                    invalid_layout = True
            from legal_ocr.motore.identita import RECUPERO_IDENTITA_VERSIONE
            from pct.document_intelligence.service import IDENTITY_PROVENANCE_MARKER
            checked_recovery = any(f'Recupero identità {RECUPERO_IDENTITA_VERSIONE}:' in str(w) for w in (getattr(extracted, 'warnings', []) or []))
            checked_provenance = IDENTITY_PROVENANCE_MARKER in (getattr(extracted, 'warnings', []) or [])
            if ((invalid_layout and not checked_recovery) or (not identity_sources and not checked_provenance)) and service is not None and acquire_missing:
                service.reacquire_existing_version(tenant, case_id, record.id, raw, user_context, identity_recovery=True)
                return read_client_case_document(manager, repository, tenant, case_id, client_id,
                    str(doc.id), service=service, user_context=user_context, acquire_missing=False, client=client)
            candidates.append((doc, name, sha, content, parser_sources))
            break
    if not candidates and acquire_missing and service is not None:
        # Il nome individua una fonte da esaminare, non prova i dati della parte.
        # Recupero puntuale nella pipeline nativa SQL; mai l'intero fascicolo.
        selected = [doc for doc in case.documenti
            if (not document_id or str(doc.id) == document_id)
            and str(getattr(doc, 'nome_originale', '') or getattr(doc, 'nome', '') or '').lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.p7m'))
            and (document_id or re.search(r'identit[àa]|identity|passaport', ' '.join(str(getattr(doc, key, '') or '') for key in ('nome', 'nome_originale')), re.I))]
        if len(selected) == 1:
            from pct.document_intelligence.sources import source_from_uploaded_document
            name, raw = leggi_documento(manager, case_id, str(selected[0].id))
            source = source_from_uploaded_document(tenant_id=tenant, fascicolo_id=case_id,
                document_id=str(selected[0].id), filename=name, content=raw,
                metadata={'reason': 'client_identity_read', 'documento_id': str(selected[0].id)})
            outcome = service.process_lex_indexing_sources(tenant, case_id, [source], user_context, retry_errors=True)
            if outcome.errors:
                raise ClientDocumentReaderError('Lettura del documento d’identità non completata: ' + '; '.join(outcome.errors), status_code=422)
            return read_client_case_document(manager, repository, tenant, case_id, client_id,
                str(selected[0].id), acquire_missing=False, client=client)
        if len(selected) > 1:
            raise ClientDocumentReaderError('Sono presenti più documenti d’identità: seleziona il documento da leggere.', status_code=422)
    if len(candidates) != 1:
        message = 'Sono presenti più documenti d’identità: seleziona il documento da leggere.' if candidates else 'Non è disponibile una lettura verificata del documento d’identità corrente nel fascicolo.'
        raise ClientDocumentReaderError(message, status_code=422)
    doc, name, sha, content, identity_sources = candidates[0]
    result = parse_client_document_text(content, filename=name, identity_sources=identity_sources)
    if client is not None:
        _verify_client_identity(content, result, client)
    _corroborate_client_fields(manager, repository, tenant, case, records, result)
    result['source_document'] = {'id': str(doc.id), 'fascicolo_id': case_id, 'sha256': sha,
        'href': f'/fascicoli/{case_id}/documenti/{doc.id}/visualizza', 'label': name}
    return result


def _archived_identity_sources(extracted: Any) -> list[dict[str, Any]]:
    """Riusa le prove delle pagine archiviate, mai qualifiche inventate."""
    sources = []
    for page in getattr(extracted, 'pages', []) or []:
        values = page.get('identity_sources', []) if isinstance(page, dict) else getattr(page, 'identity_sources', [])
        sources.extend(value for value in values if isinstance(value, dict)
                       and value.get('mode') in {'native', 'ocr', 'recovery'} and value.get('text'))
    return sources


def _verify_client_identity(content: str, result: dict[str, Any], client: Any) -> None:
    """Il collegamento al fascicolo non basta a provare il titolare della carta."""
    from pct.document_intelligence.catalog_identita_personale import documento_identita_personale, normalizza
    identity = documento_identita_personale(content, cliente=client.nome_completo)
    if not identity or not identity.get('titolare'):
        raise ClientDocumentReaderError('Il titolare del documento non coincide con il cliente. La scheda non è stata modificata.', status_code=422)
    if len(_codici_fiscali_validi(content)) > 1:
        raise ClientDocumentReaderError('Il documento contiene codici fiscali di più titolari. Seleziona la fonte del cliente; la scheda non è stata modificata.', status_code=422)
    patch = result['patch']
    expected = _find_cf(str(client.codice_fiscale or '').upper())
    actual = str(patch.get('codice_fiscale') or '')
    if expected and actual and expected != actual:
        raise ClientDocumentReaderError('Il codice fiscale del documento è discordante con il cliente. La scheda non è stata modificata.', status_code=422)
    parsed = normalizza(str(patch.get('nome') or '') + ' ' + str(patch.get('cognome') or ''))
    target = normalizza(str(client.nome or '') + ' ' + str(client.cognome or ''))
    if sorted(parsed.split()) != sorted(target.split()):
        if not expected or expected != actual:
            raise ClientDocumentReaderError('Nome e cognome non sono stati estratti con affidabilità sufficiente. La scheda non è stata modificata.', status_code=422)
        # Le parole e il CF riscontrano il titolare, ma etichette OCR confuse
        # non devono sovrascrivere nome/cognome corretti dell'anagrafica.
        for key in ('nome', 'cognome'):
            patch.pop(key, None)
        result['fields'] = [item for item in result['fields'] if item.get('name') not in ('nome', 'cognome')]
        result['warnings'].append('Nome e cognome conservati: etichette del documento non estratte con affidabilità sufficiente.')


def _corroborate_client_fields(manager: Any, repository: Any, tenant: str, case: Any, records: list[Any], result: dict[str, Any]) -> None:
    """Riscontri personali nel solo fascicolo, già estratti e con byte correnti.

    Non attribuisce atti o effetti processuali e non deduce valori per similarità.
    Due impronte distinte devono dichiarare lo stesso dato per la stessa parte.
    """
    from web.services.fascicolo_documento_ocr import leggi_documento
    patch = result['patch']
    cf = str(patch.get('codice_fiscale') or '')
    names = [str(patch.get(key) or '').casefold() for key in ('nome', 'cognome')]
    if not cf or not all(names):
        return
    votes: dict[str, dict[str, list[dict[str, str]]]] = {}
    checked_hashes = set()
    for record in records:
        if record.status != 'ready' or record.sha256 in checked_hashes:
            continue
        extracted = repository.get_extracted_text(tenant, case.id, record.id, record.current_version_id)
        header = re.sub(r'\s+', ' ', str(getattr(extracted, 'text', '') or '')[:2400])
        if cf not in header.upper() or not all(re.search(r'\b' + re.escape(name) + r'\b', header, re.I) for name in names):
            continue
        personal = header[header.upper().index(cf):][:550]
        values = {field: _clean_value(field, value) for field, value, _ in _birth_from_text(personal)}
        address = re.search(r'(?:residente/domiciliato\s+fiscalmente\s+a|residente\s+(?:a|in))\s+([A-ZÀ-Ü\' -]+?)\s*\(([A-Z]{2})\)\s+((?:STRADA|VIA|VIALE|PIAZZA)\s+.+?)\s+civico\s+(\d{1,5}[A-Z]?)\b', personal, re.I)
        if address:
            values.update(comune=address.group(1).title(), provincia=address.group(2).upper(), via=address.group(3).title(), civico=address.group(4))
        else:
            address = re.search(r'nat[oa]\s+il\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4})\s+a\s+([A-ZÀ-Ü\' -]+?)\s*\(([A-Z]{2})\)\s+ed\s+ivi\s+residente\s+in\s+((?:STRADA|VIA|VIALE|PIAZZA)\s+.+?)\s*,\s*(\d{1,5}[A-Z]?)\s*,', personal, re.I)
            if address:
                values.update(data_nascita=_parse_date(address.group(1),'birth'), luogo_nascita=address.group(2).title(), provincia_nascita=address.group(3).upper(), comune=address.group(2).title(), provincia=address.group(3).upper(), via=address.group(4).title(), civico=address.group(5))
        if not values or (patch.get('data_nascita') and values.get('data_nascita') and patch['data_nascita'] != values['data_nascita']):
            continue
        matching = [doc for doc in case.documenti if record.original_filename.casefold() in {str(getattr(doc,key,'') or '').casefold() for key in ('nome','nome_originale')}]
        if len(matching) != 1:
            continue
        try:
            name, raw = leggi_documento(manager, case.id, str(matching[0].id))
        except Exception:
            continue
        if hashlib.sha256(raw).hexdigest() != record.sha256:
            continue
        checked_hashes.add(record.sha256)
        source = {'id':str(matching[0].id),'sha256':record.sha256,'label':name,
            'href':f'/fascicoli/{case.id}/documenti/{matching[0].id}/visualizza'}
        for field,value in values.items():
            if value:
                votes.setdefault(field,{}).setdefault(value,[]).append(source)
    for field, alternatives in votes.items():
        if len(alternatives) != 1:
            result['warnings'].append('Riscontri discordanti per ' + FIELD_LABELS.get(field,field) + ': mantenuto il dato corrente.')
            continue
        value, sources = next(iter(alternatives.items()))
        if len(sources) < 2 or (patch.get(field) and patch[field].casefold() != value.casefold()):
            continue
        patch[field] = value
        result['fields'] = [row for row in result['fields'] if row['name'] != field] + [
            {'name':field,'label':FIELD_LABELS.get(field,field),'value':value,'confidence':0.9,
             'source':'Riscontri concordanti nel fascicolo','status':'affidabile','sources':sources}]
    result['missing'] = [FIELD_LABELS[key] for key in EXPECTED_FIELDS if key not in patch]

ALLOWED_CLIENT_DOCUMENT_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")
ALLOWED_CLIENT_DOCUMENT_MIME_TYPES = ("application/pdf", "image/png", "image/jpeg")
MAX_CLIENT_DOCUMENT_MB = 12

FIELD_LABELS: dict[str, str] = {
    "codice_fiscale": "codice fiscale",
    "cognome": "cognome",
    "nome": "nome",
    "sesso": "sesso",
    "data_nascita": "data di nascita",
    "luogo_nascita": "luogo di nascita",
    "provincia_nascita": "provincia di nascita",
    "nazionalita": "nazionalità",
    "doc_tipo": "tipo documento",
    "doc_numero": "numero documento",
    "doc_rilasciato_da": "rilasciato da",
    "doc_data_rilascio": "data rilascio",
    "doc_data_scadenza": "data scadenza",
    "via": "via",
    "civico": "civico",
    "cap": "CAP",
    "comune": "comune",
    "provincia": "provincia",
    "nazione": "nazione",
    "telefono": "telefono",
    "cellulare": "cellulare",
    "email": "email",
    "pec": "PEC",
}

EXPECTED_FIELDS = (
    "nome",
    "cognome",
    "codice_fiscale",
    "data_nascita",
    "luogo_nascita",
    "provincia_nascita",
    "doc_numero",
    "doc_rilasciato_da",
    "doc_data_rilascio",
    "doc_data_scadenza",
    "via",
    "civico",
    "comune",
)


class ClientDocumentReaderError(ValueError):
    """Errore recuperabile nella lettura del documento cliente."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.public_message = message
        self.status_code = status_code


def read_client_document_upload(upload: FileStorage | None, *, client: Any = None) -> dict[str, Any]:
    if upload is None or not getattr(upload, "filename", ""):
        raise ClientDocumentReaderError("Seleziona un PDF o un'immagine del documento.")
    filename = str(upload.filename or "documento")
    content = upload.read()
    validation = validate_upload(
        filename,
        content,
        allowed_extensions=ALLOWED_CLIENT_DOCUMENT_EXTENSIONS,
        allowed_mime_types=ALLOWED_CLIENT_DOCUMENT_MIME_TYPES,
        max_size_mb=MAX_CLIENT_DOCUMENT_MB,
    )
    if not validation.ok:
        raise ClientDocumentReaderError(validation.error or "Documento non leggibile.")
    return read_client_document_bytes(
        content,
        validation.safe_filename or Path(filename).name,
        mime_type=validation.mime_type,
        client=client,
    )


def read_client_document_bytes(content: bytes, filename: str, *, mime_type: str = "", client: Any = None) -> dict[str, Any]:
    extracted = _extract_text(content, filename)
    text, warning = extracted[:2]
    result = parse_client_document_text(
        text,
        filename=filename,
        mime_type=mime_type,
        warnings=[warning] if warning else [],
        identity_sources=extracted[2] if len(extracted) > 2 else None,
    )
    if "CF decodificato localmente dal codice a barre" in warning:
        for field in result['fields']:
            if field['name'] == 'codice_fiscale':
                field['source'] = 'codice a barre del retro CIE, confrontato con la MRZ'
    if client is not None:
        _verify_client_identity(text, result, client)
    return result


def parse_client_document_text(
    text: str,
    *,
    filename: str = "documento",
    mime_type: str = "",
    warnings: list[str] | None = None,
    identity_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    clean_text = _normalize_text(text)
    fields: dict[str, dict[str, Any]] = {}
    mrz = _parse_mrz_from_text(clean_text)
    for field, value in (mrz.get("patch") or {}).items():
        _remember_field(fields, field, value, 0.97, "zona MRZ")
    visible_fields = _extract_visible_fields(clean_text)
    visible_fields, qualified_values, qualification_warnings = _qualified_identity_candidates(
        visible_fields, identity_sources or [], mrz.get('patch') or {},
    )
    for field, value, confidence in visible_fields:
        _remember_field(fields, field, value, confidence, "testo documento")

    qualified_text = '\n\n'.join(str(source.get('text') or '') for source in (identity_sources or [])
                                 if source.get('mode') in {'native', 'recovery'})
    conflicting_fields, multiple_named_holders = _identity_reading_conflicts(qualified_text or clean_text, visible_fields)
    if qualified_text:
        # Un recupero dimostra i propri campi, non l'appartenenza di un
        # altro fronte. Le coppie complete discordanti restano ambigue;
        # una sola etichetta OCR isolata non dimostra un secondo titolare.
        _, ambiguous_source_holders = _identity_reading_conflicts(clean_text, [])
        multiple_named_holders = multiple_named_holders or ambiguous_source_holders
    for field in conflicting_fields:
        fields.pop(field, None)
    multiple_fiscal_holders = len(_codici_fiscali_validi(clean_text)) > 1
    multiple_holders = multiple_fiscal_holders or multiple_named_holders
    tokens = clean_text.upper().split()
    verified_cards = {(first[5:14], names) for first, second, names in zip(tokens, tokens[1:], tokens[2:])
                      if len(first) == 30 and len(second) == 30 and 24 <= len(names) <= 30
                      and td1_verificata(first, second, names)}
    visible_numbers = {_clean_value(field, value) for field, value, confidence in visible_fields
                       if field == 'doc_numero' and confidence >= .78 and _clean_value(field, value)}
    multiple_cards = len(verified_cards) > 1 or len(visible_numbers) > 1
    if multiple_holders or multiple_cards:
        # Anche la nuova anagrafica, priva di un cliente atteso, deve evitare
        # di comporre una persona dai campi di carte appartenenti a più titolari.
        fields.clear()

    date_warnings = _check_identity_dates(fields, visible_fields)
    pending_names = set()
    if identity_sources is not None and bool(fields.get('nome')) != bool(fields.get('cognome')):
        # Un'etichetta OCR non è una prova del valore: il parser generico
        # resta compatibile, ma una lettura immagine isolata non compila.
        for key in ('nome', 'cognome'):
            if key in fields and fields[key]['source'] != 'zona MRZ' and not qualified_values.get(key):
                pending_names.add(key)
                fields[key]['source'] = 'lettura OCR senza riscontro del titolare'
    for key, row in fields.items():
        if row['source'] != 'zona MRZ' and str(row['value']).casefold() in qualified_values.get(key, set()):
            row['source'] = 'lettura riscontrata nella fonte del documento'

    patch = {
        key: str(row["value"])
        for key, row in fields.items()
        if key not in pending_names and str(row.get("value") or "").strip() and float(row.get("confidence") or 0) >= 0.78
    }
    from pct.territorio_italia import verifica_comune_italiano
    geographic_checks = {}
    for field, province_field in (('luogo_nascita', 'provincia_nascita'), ('comune', 'provincia')):
        value = patch.get(field, '')
        province = patch.get(province_field, '')
        if not value:
            continue
        if province == 'EE' or (field == 'comune' and patch.get('nazione', 'Italia').casefold() not in {'italia', 'italy', 'it'}):
            geographic_checks[field] = {'stato': 'localita_estera'}
            continue
        check = verifica_comune_italiano(value, province)
        if field == 'luogo_nascita' and check['stato'] == 'non_riscontrato':
            from pct.codice_fiscale import trova_belfiore
            historical = trova_belfiore(value, province)
            if historical and (not province or historical['provincia_nascita'] == province):
                check = {'stato': 'concordante', 'catalogo': 'belfiore_storico', 'luogo': historical}
        geographic_checks[field] = check
        if check['stato'] != 'concordante':
            fields[field]['confidence'] = 0.70
            patch.pop(field, None)
    missing = [FIELD_LABELS[key] for key in EXPECTED_FIELDS if key not in patch]
    field_rows = [
        {
            "name": key,
            "label": FIELD_LABELS.get(key, key),
            "value": row["value"],
            "confidence": row["confidence"],
            "source": row["source"],
            "status": "affidabile" if key not in pending_names and float(row.get("confidence") or 0) >= 0.78 else "da verificare",
        }
        for key, row in sorted(fields.items(), key=lambda item: FIELD_LABELS.get(item[0], item[0]))
    ]
    all_warnings = list(warnings or [])
    all_warnings.extend(qualification_warnings)
    all_warnings.extend(date_warnings)
    for key in sorted(pending_names):
        all_warnings.append(f"{FIELD_LABELS[key].capitalize()} letto dall’OCR senza un riscontro del titolare: valore da verificare, non applicato.")
    for field in sorted(conflicting_fields):
        all_warnings.append(
            f"Valori discordanti per {FIELD_LABELS.get(field, field)} nella lettura: "
            "nessun valore è stato scelto o applicato per questo campo."
        )
    document_profiles = _document_profiles(clean_text)
    for field, check in geographic_checks.items():
        if check['stato'] not in {'concordante', 'localita_estera'}:
            all_warnings.append(f"{FIELD_LABELS[field].capitalize()}: Comune italiano non riscontrato univocamente con la provincia nel catalogo; valore conservato tra i dati da verificare e non applicato.")
    from pct.codice_fiscale import confronta_con_dati
    fiscal_check = confronta_con_dati(patch.get('codice_fiscale', ''), **{
        key: patch.get(key, '') for key in
        ('cognome', 'nome', 'sesso', 'data_nascita', 'luogo_nascita', 'provincia_nascita')})
    fiscal_messages = {
        'concordante': 'Codice fiscale letto concordante con il calcolo dai dati anagrafici del documento.',
        'omocodia_compatibile': 'Codice fiscale letto compatibile con un’omocodia: conservato il codice del documento.',
        'discordante': 'Codice fiscale letto discordante dal calcolo: controlla i dati anagrafici e la fonte; nessuna sostituzione automatica.',
        'non_valido': 'Il codice fiscale letto non supera i controlli formali; nessuna sostituzione con il codice calcolato.',
        'non_letto': 'Calcolo del codice fiscale disponibile dai dati letti, ma il codice del documento non è ancora leggibile: confronto non concluso.',
    }
    if fiscal_check['stato'] in fiscal_messages:
        all_warnings.append(fiscal_messages[fiscal_check['stato']])
    if mrz.get('detected'):
        for field in ('nazionalita', 'sesso'):
            if field not in (mrz.get('patch') or {}):
                all_warnings.append(FIELD_LABELS[field].capitalize() + ' non leggibile nella zona MRZ: questo campo non è stato applicato da quella lettura.')
    if not mrz.get('detected') and re.search(r'\b[PIAC]<[A-Z0-9<]{12,}', clean_text, re.I):
        all_warnings.append('Zona MRZ non validata: dati incompleti o cifre di controllo discordanti. I valori MRZ non sono stati applicati.')
    if not clean_text:
        all_warnings.append("Il testo non è stato estratto dal documento. Verifica qualità della scansione o lingua OCR installata.")
    if multiple_fiscal_holders:
        message = "Il documento contiene codici fiscali di più titolari. Seleziona la fonte della persona da leggere; nessun campo è stato applicato."
        all_warnings.append(message)
    elif multiple_cards:
        message = ("Il documento contiene più carte con zone MRZ verificate distinte. Seleziona una sola carta; nessun campo è stato applicato."
                   if len(verified_cards) > 1 else
                   "Il documento contiene numeri di carte distinti. Seleziona una sola carta; nessun campo è stato applicato.")
        all_warnings.append(message)
    elif multiple_named_holders:
        message = "Il documento contiene nomi e cognomi di titolari distinti senza un riscontro comune. Seleziona la fonte della persona da leggere; nessun campo è stato applicato."
        all_warnings.append(message)
    elif not patch:
        message = "Non ho trovato dati anagrafici affidabili nel documento."
    elif missing:
        message = "Dati documento letti. Alcuni campi non risultano presenti o abbastanza chiari."
    else:
        message = "Dati documento letti e pronti per la compilazione."
    return {
        "ok": bool(patch),
        "message": message,
        "source": "lettore_documento_cliente",
        "filename": Path(filename).name,
        "mime_type": mime_type,
        "patch": patch,
        "fields": field_rows,
        "missing": missing,
        "warnings": all_warnings,
        "mrz": {"detected": bool(mrz.get("detected")), "type": mrz.get("type") or ""},
        "document_profiles": document_profiles,
        "fiscal_check": fiscal_check,
        "geographic_checks": geographic_checks,
    }


def _document_profiles(text: str) -> list[dict[str, Any]]:
    from pct.document_intelligence.catalog_identita_personale import segmenti_identita_italiana
    return [{key: value for key, value in segment.items() if key != 'text'} for segment in segmenti_identita_italiana(text)]


def _qualified_identity_candidates(candidates, sources, mrz):
    """Distingue riscontri della fonte e varianti OCR grezze, senza votazioni.

    La confidenza della pagina non è la confidenza di un campo. Una fonte
    nativa o un recupero già riscontrato può corroborare lo stesso valore;
    due riscontri discordanti restano entrambi sottoposti al blocco.
    """
    if not sources:
        return candidates, {}, []
    qualified: dict[str, set[str]] = {}
    birth_checks: set[tuple[int, int, int]] = set()
    additions = []
    personal = {key: {_clean_value(key, value) for field, value, _ in candidates
                      if field == key and _clean_value(key, value)} for key in ('nome', 'cognome')}
    for key, value in mrz.items():
        clean = _clean_value(key, value)
        if clean:
            qualified.setdefault(key, set()).add(clean.casefold())
    for source in sources:
        if source.get('mode') not in {'native', 'recovery'}:
            continue
        content = _normalize_text(source.get('text', ''))
        values = _extract_visible_fields(content)
        # La TS può corroborare una data già letta, non inventarla dal CF.
        # Occorrono codice valido, nomi esatti della stessa persona e la
        # data materialmente presente nella fonte qualificata.
        if all(len(personal[key]) == 1 for key in personal):
            from pct.codice_fiscale import decodifica, _codice_nome
            name, surname = (next(iter(personal[key])) for key in ('nome', 'cognome'))
            flat = re.sub(r'\s+', ' ', content)
            code = _find_cf(content)
            demographics = decodifica(code) if code else None
            if (demographics and re.search(r'\b(?:NASCITA|BIRTH)\b', flat, re.I)
                    and all(re.search(r'\b' + re.escape(value) + r'\b', flat, re.I) for value in (name, surname))
                    and code[:6] == _codice_nome(surname) + _codice_nome(name, nome=True)):
                birthday = demographics['data_nascita']
                decoded_date = date.fromisoformat(birthday)
                birth_checks.add((decoded_date.year % 100, decoded_date.month, decoded_date.day))
                printed = {_clean_value('data_nascita', value) for value in
                           re.findall(r'(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{4}(?!\d)', content)}
                if birthday in printed:
                    values.append(('data_nascita', birthday, .9))
        for field, value, confidence in values:
            clean = _clean_value(field, value)
            if clean and confidence >= .78:
                qualified.setdefault(field, set()).add(clean.casefold())
                additions.append((field, value, confidence))
    discarded = set()
    incompatible_birth = False
    selected = []
    for field, value, confidence in candidates + additions:
        clean = _clean_value(field, value)
        proof = qualified.get(field)
        contradicted_birth = False
        if field == 'data_nascita' and clean and len(birth_checks) == 1:
            read_date = date.fromisoformat(clean)
            contradicted_birth = (read_date.year % 100, read_date.month, read_date.day) not in birth_checks
            incompatible_birth = incompatible_birth or contradicted_birth
        if clean and ((proof and clean.casefold() not in proof) or contradicted_birth):
            discarded.add(field)
        else:
            selected.append((field, value, confidence))
    warnings = [f"{FIELD_LABELS.get(field, field).capitalize()}: variante OCR grezza non concordante con i riscontri della fonte; non applicata."
                for field in sorted(discarded)]
    if incompatible_birth:
        warnings.append('Una variante OCR della data di nascita è incompatibile con il codice fiscale valido della stessa persona nella fonte ed è stata esclusa. Nessuna data è stata ricostruita dal codice.')
    return selected, qualified, warnings


def _check_identity_dates(fields, candidates, *, today=None):
    """Solo vincoli cronologici, nessuna durata legale o correzione dell'anno."""
    today = today or date.today()
    warnings = []
    keys = {'data_nascita', 'doc_data_rilascio', 'doc_data_scadenza'}
    invalid = {key for key, value, _ in candidates
               if key in keys and value and not _clean_value(key, value)}
    for key in sorted(invalid):
        warnings.append(f"{FIELD_LABELS[key].capitalize()}: una lettura non corrisponde a una data di calendario valida ed è stata esclusa.")
    for key in ('data_nascita', 'doc_data_rilascio'):
        if key in fields and date.fromisoformat(fields[key]['value']) > today:
            fields.pop(key)
            warnings.append(f"{FIELD_LABELS[key].capitalize()} futura rispetto a oggi: lettura non applicata, controllare la fonte.")
    issued, expires = (fields.get(key) for key in ('doc_data_rilascio', 'doc_data_scadenza'))
    if issued and expires and issued['value'] > expires['value']:
        fields.pop('doc_data_rilascio')
        fields.pop('doc_data_scadenza')
        warnings.append('Data rilascio successiva alla data scadenza: entrambe le letture restano da verificare e non sono state applicate.')
    return warnings


def _identity_reading_conflicts(text: str, visible_fields: list[tuple[str, str, float]]) -> tuple[set[str], bool]:
    """Non compone persone o date scegliendo la prima lettura discordante.

    Le copie concordanti sono una sola evidenza. La TS conserva il proprio
    dominio: la sua scadenza non viene confrontata con quella della carta.
    """
    from pct.document_intelligence.catalog_identita_personale import segmenti_identita_italiana
    values: dict[str, set[str]] = {}
    for field, value, confidence in visible_fields:
        clean = _clean_value(field, value)
        if clean and confidence >= .78:
            values.setdefault(field, set()).add(clean.casefold())
    segments = segmenti_identita_italiana(text) or [{'text': text, 'model': ''}]
    people: dict[tuple[str, str], set[str]] = {}
    for segment in segments:
        source = segment['text']
        if segment['model'] == 'carta_cartacea':
            for match in re.finditer(r'\bSCADE\s+IL\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4})', source, re.I):
                expiry = _clean_value('doc_data_scadenza', match.group(1))
                if expiry:
                    values.setdefault('doc_data_scadenza', set()).add(expiry)
        # La ripetizione di Cognome delimita anche fronti senza titolo o
        # numero. I valori devono portare entrambe le etichette personali.
        starts = [match.start() for match in re.finditer(r'\bCOGNOME\b', source, re.I)]
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else len(source)
            chunk = source[start:end]
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            name = _clean_value('nome', _line_value(lines, ('NOME', 'GIVEN NAME', 'GIVEN NAMES')))
            surname = _clean_value('cognome', _line_value(lines, ('COGNOME', 'SURNAME')))
            if not name or not surname:
                continue
            values.setdefault('nome', set()).add(name.casefold())
            values.setdefault('cognome', set()).add(surname.casefold())
            people.setdefault((surname.casefold(), name.casefold()), set()).update(_codici_fiscali_validi(chunk))
    conflicting = {field for field, alternatives in values.items() if len(alternatives) > 1}
    shared_codes = set.intersection(*people.values()) if people else set()
    return conflicting, len(people) > 1 and not shared_codes


def _extract_text(content: bytes, filename: str) -> tuple[str, str, list[dict[str, Any]]]:
    try:
        from pct.document_intelligence.extraction import extract_text_from_document

        result = extract_text_from_document(
            content, filename, Path(filename).suffix.lower().lstrip("."), identity_scan=True,
        )
        page_summary = "Letta 1 pagina" if len(result.pages) == 1 else f"Lette {len(result.pages)} pagine"
        warning = (f"{page_summary} del documento. La lettura delle pagine non implica il riconoscimento di tutti i campi."
                   if result.ok and result.pages else (result.error_message or "Lettura del documento non completata.") if not result.ok else "")
        if result.ok:
            warning += _preparation_summary(result.warnings)
        if result.ok and any(re.fullmatch(
                r'(?:Pagina \d+: )?Codice a barre del retro CIE [A-Z0-9]{9}: CF decodificato localmente, checksum e dati MRZ concordanti; originale invariato\.',
                str(item)) for item in result.warnings):
            warning += ' CF decodificato localmente dal codice a barre del retro CIE e confrontato con la MRZ; originale invariato.'
        return str(result.text or ""), warning, list(getattr(result, 'identity_sources', []) or [])
    except Exception:  # pragma: no cover
        return "", "Lettura automatica non completata. Verifica il formato del file o la qualità della scansione.", []


def _preparation_summary(warnings: list[str]) -> str:
    """Solo operazioni effettivamente annotate, senza esporre testo o coordinate.

    Un tentativo non è una lettura verificata e una rettifica scartata non
    può diventare una promessa di correzione dell'immagine mostrata.
    """
    items = [str(item) for item in warnings]
    if not any('Preparazione terminata; avvio OCR' in item for item in items):
        return ''
    steps = []
    for evidence, label in (
        ('Geometria:', 'geometria'), ('Analisi orientamento:', 'orientamento'),
        ('illuminazione normalizzata:', 'illuminazione'),
        ('contrasto normalizzato:', 'contrasto'), ('nitidezza:', 'nitidezza'),
        ('Ingrandimento misurato', 'ingrandimento'),
        ('pixel selezionati per luminanza locale', 'separazione dello sfondo'),
    ):
        if any(evidence in item for item in items):
            steps.append(label)
    if not steps:
        return ''
    return (' Controlli e tentativi sulle immagini: ' + ', '.join(steps)
            + '. I tentativi non confermati non compilano i campi.')


def _normalize_text(value: str) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _remember_field(fields: dict[str, dict[str, Any]], field: str, value: Any, confidence: float, source: str) -> None:
    clean = _clean_value(field, str(value or ""))
    if not clean:
        return
    previous = fields.get(field)
    if previous and float(previous.get("confidence") or 0) >= confidence:
        return
    fields[field] = {"value": clean, "confidence": round(float(confidence), 2), "source": source}


def _clean_value(field: str, value: str) -> str:
    clean = re.sub(r"\s+", " ", str(value or "").replace("<", " ")).strip(" :-")
    if not clean:
        return ""
    if field in {'nome', 'cognome', 'nazionalita', 'doc_rilasciato_da'}:
        if re.search(r'\b(?:COGNOME|SURNAME|NOME|NAME|SEX|HEIGHT|NATIONALITY|CITTADINANZA|RESIDENRA|PADRE|MADRE|TUTOR|FISCAL|CODICE|SCADENZA|EXPIRY)\b', clean, re.I):
            return ""
        if field in {'nome', 'cognome'} and (len(clean) < 2 or re.search(r'\d', clean)):
            return ""
        if field == 'nazionalita' and re.search(r'\d', clean):
            return ""
    if field in {"codice_fiscale", "provincia_nascita", "provincia"}:
        limit = 16 if field == "codice_fiscale" else 2
        return re.sub(r"[^A-Z0-9]", "", clean.upper())[:limit]
    if field in {"nome", "cognome", "luogo_nascita", "comune"}:
        return _title_case(clean)
    if field == "sesso":
        return _normalize_sex(clean)
    if field == "nazionalita":
        return _normalize_nationality(clean)
    if field == "doc_tipo":
        return _normalize_document_type(clean)
    if field in {"data_nascita", "doc_data_rilascio", "doc_data_scadenza"}:
        purpose = "birth" if field == "data_nascita" else "expiry" if field == "doc_data_scadenza" else "generic"
        return _parse_date(clean, purpose)
    if field in {"email", "pec"}:
        match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", clean, flags=re.I)
        return match.group(0).lower() if match else ""
    return clean.strip()


def _title_case(value: str) -> str:
    return " ".join(part.capitalize() for part in str(value or "").lower().split())


def _normalize_key(value: str) -> str:
    replacements = str.maketrans("àèéìòù", "aeeiou")
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower().translate(replacements))


def _normalize_sex(value: str) -> str:
    raw = _normalize_key(value)
    if raw in {"m", "male", "maschio", "maschile"}:
        return "M"
    if raw in {"f", "female", "femmina", "femminile"}:
        return "F"
    return ""


def _normalize_nationality(value: str) -> str:
    raw = _normalize_key(value)
    if raw in {"ita", "italia", "italiana", "italiano", "italian"}:
        return "Italiana"
    return _title_case(value)


def _normalize_document_type(value: str) -> str:
    raw = _normalize_key(value)
    if "pass" in raw:
        return "PASSAPORTO"
    if "patente" in raw:
        return "PATENTE"
    if "soggiorno" in raw:
        return "PERMESSO_SOGGIORNO"
    if "ident" in raw or raw.startswith("i"):
        return "CARTA_IDENTITA"
    return value.upper()


def _parse_date(value: str, purpose: str = "generic") -> str:
    raw = str(value or "").strip()
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", raw)
    if iso:
        return _valid_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    italian = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})\b", raw)
    if italian:
        year = int(italian.group(3))
        if year < 100:
            year = _two_digit_year(year, purpose)
        return _valid_date(year, int(italian.group(2)), int(italian.group(1)))
    if re.fullmatch(r"\d{6}", raw):
        return _valid_date(_two_digit_year(int(raw[:2]), purpose), int(raw[2:4]), int(raw[4:6]))
    compact = re.search(r"\b(\d{4})(\d{2})(\d{2})\b", raw)
    if compact:
        return _valid_date(int(compact.group(1)), int(compact.group(2)), int(compact.group(3)))
    return ""


def _two_digit_year(year: int, purpose: str) -> int:
    current = date.today().year
    century = current // 100 * 100
    full = century + year
    if purpose == "birth":
        return full - 100 if full > current else full
    if purpose == "expiry":
        return full + 100 if full < current - 30 else full
    return full - 100 if full > current + 30 else full


def _valid_date(year: int, month: int, day: int) -> str:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _parse_mrz_from_text(text: str) -> dict[str, Any]:
    # Alcuni OCR archiviano le tre righe TD1 come una sola riga, separate
    # da spazi. Conserviamo i confini, evitando il concatenamento dei campi.
    for line in str(text or '').splitlines():
        parts = line.upper().split()
        if (len(parts) == 3 and re.fullmatch(r'[IAC]<ITA[A-Z0-9<]{23,25}', parts[0])
                and re.fullmatch(r'\d{7}[MF<][A-Z0-9<]{20,22}', parts[1])
                and re.fullmatch(r'[A-Z0<]{24,30}', parts[2]) and '<<' in parts[2]):
            name_zone = _corroborated_mrz_name_zone(parts[2], text)
            if not name_zone:
                continue
            patch = _parse_td1(parts[0], parts[1], name_zone)
            if patch:
                return {'detected': True, 'type': 'CARTA_IDENTITA', 'patch': patch}
    lines = [_clean_mrz_line(line) for line in str(text or "").splitlines()]
    lines = [line for line in lines if line and "<" in line and len(line) >= 24]
    for index in range(len(lines) - 1):
        first, second = lines[index], lines[index + 1]
        if first.startswith("P") and len(first) >= 40 and len(second) >= 40:
            patch = _parse_td3(first[:44], second[:44])
            if patch:
                return {"detected": True, "type": "PASSAPORTO", "patch": patch}
        if first[:1] in {"I", "A", "C"} and len(first) >= 34 and len(second) >= 34:
            patch = _parse_td2(first[:36], second[:36])
            if patch:
                return {"detected": True, "type": "DOCUMENTO", "patch": patch}
    for index in range(len(lines) - 2):
        first, second, third = lines[index], lines[index + 1], lines[index + 2]
        if first[:1] in {"I", "A", "C"} and len(first) >= 28 and len(second) >= 28 and len(third) >= 24:
            names = _corroborated_mrz_name_zone(third[:30], text)
            patch = _parse_td1(first[:30], second[:30], names) if names else {}
            if patch:
                return {"detected": True, "type": "CARTA_IDENTITA", "patch": patch}
    return {"detected": False, "type": "", "patch": {}}


def _clean_mrz_line(line: str) -> str:
    return re.sub(r"[^A-Z0-9<]", "", str(line or "").upper())


def _corroborated_mrz_name_zone(segment: str, text: str) -> str:
    """Ripara zero/O solo nel nome e solo con parola autonoma sul fronte.

    Numeri, date e codici del documento non vengono normalizzati così.
    Il nome atteso in anagrafica non è una prova per correggere l'OCR.
    """
    if '0' not in segment:
        return segment
    visible = '\n'.join(line for line in str(text or '').upper().splitlines() if '<' not in line)
    for word in segment.split('<'):
        if '0' in word and not re.search(r'\b' + re.escape(word.replace('0', 'O')) + r'\b', visible):
            return ''
    return segment.replace('0', 'O')


def _parse_td3(line1: str, line2: str) -> dict[str, str]:
    if not _valid_td2_td3_checks(line2, composite_position=43):
        return {}
    patch = _parse_mrz_names(line1[5:])
    patch.update({
        "doc_tipo": "PASSAPORTO",
        "doc_numero": line2[:9].replace("<", ""),
        "data_nascita": line2[13:19],
        "doc_data_scadenza": line2[21:27],
    })
    _add_mrz_demographics(patch, line2, country_position=10, sex_position=20)
    return patch


def _parse_td2(line1: str, line2: str) -> dict[str, str]:
    if not _valid_td2_td3_checks(line2, composite_position=35):
        return {}
    patch = _parse_mrz_names(line1[5:])
    patch.update({
        "doc_tipo": "CARTA_IDENTITA",
        "doc_numero": line2[:9].replace("<", ""),
        "data_nascita": line2[13:19],
        "doc_data_scadenza": line2[21:27],
    })
    _add_mrz_demographics(patch, line2, country_position=10, sex_position=20)
    cf = _find_cf(f"{line1} {line2}")
    if cf:
        patch["codice_fiscale"] = cf
    return patch


def _parse_td1(line1: str, line2: str, line3: str) -> dict[str, str]:
    if not td1_verificata(line1, line2, line3):
        return {}
    patch = _parse_mrz_names(line3)
    patch.update({
        "doc_tipo": "CARTA_IDENTITA",
        "doc_numero": line1[5:14].replace("<", ""),
        "data_nascita": line2[:6],
        "doc_data_scadenza": line2[8:14],
    })
    # Sex and nationality are not protected by the numeric check digits.
    # An unreadable value in either must not invalidate verified numbers,
    # nor be silently repaired into a plausible personal value.
    _add_mrz_demographics(patch, line2, country_position=15, sex_position=7)
    cf = _find_cf(f"{line1} {line2}")
    if cf:
        patch["codice_fiscale"] = cf
    return patch


def _add_mrz_demographics(patch: dict[str, str], line: str, *, country_position: int, sex_position: int) -> None:
    sex = line[sex_position:sex_position + 1]
    country = line[country_position:country_position + 3]
    if sex in {'M', 'F'}:
        patch['sesso'] = sex
    if re.fullmatch(r'[A-Z]{3}', country):
        patch['nazionalita'] = country


def _valid_td2_td3_checks(line: str, *, composite_position: int) -> bool:
    if len(line) < 28:
        return False
    if not re.fullmatch(r'[A-Z0-9<]{9}[0-9][A-Z0-9<]{3}[0-9]{7}[A-Z0-9<][0-9]{7}', line[:28]):
        return False
    if not (_mrz_check_digit(line[:9], line[9])
            and _mrz_check_digit(line[13:19], line[19])
            and _mrz_check_digit(line[21:27], line[27])):
        return False
    if len(line) > composite_position:
        composite = line[:10] + line[13:20] + line[21:composite_position]
        return _mrz_check_digit(composite, line[composite_position])
    return False


def _parse_mrz_names(segment: str) -> dict[str, str]:
    surname, _, names = str(segment or "").partition("<<")
    return {"cognome": surname.replace("<", " "), "nome": names.replace("<", " ")}


def _extract_visible_fields(text: str) -> list[tuple[str, str, float]]:
    """Classifica i segmenti prima di applicare le regole del loro modello.

    La tessera sanitaria può corroborare l'anagrafica, ma non presta
    scadenza, numero, rilascio o residenza alla carta d'identità.
    """
    from pct.document_intelligence.catalog_identita_personale import segmenti_identita_italiana
    segments = segmenti_identita_italiana(text)
    if not segments:
        return _extract_visible_fields_model(text)
    values = []
    for segment in segments:
        values.extend(_extract_visible_fields_model(segment['text'], model=segment['model']))
    # Una lettera degradata nell'etichetta non autorizza a inventare il
    # valore: usa soltanto la data stampata e un CF valido della stessa
    # lettura, già sottoposta ai controlli per titolari multipli.
    from pct.codice_fiscale import decodifica
    code = _find_cf(text.upper())
    demographics = decodifica(code) if code else None
    if demographics:
        for segment in segments:
            if segment['model'] != 'carta_cartacea':
                continue
            source = segment['text']
            birthday = re.search(r'\bRAT[OA]\s+IL[. :]*(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b', source, re.I)
            if birthday and _clean_value('data_nascita', birthday.group(1)) == demographics['data_nascita']:
                values.append(('data_nascita', birthday.group(1), .9))
            place = re.search(r"\b([A-ZÀ-Ü' -]{2,60})\({1,2}([A-Z]{2})\)\s+CITTADINANZA\b", source, re.I)
            if (place and place.group(1).strip().casefold() == demographics['luogo_nascita'].casefold()
                    and place.group(2).upper() == demographics['provincia_nascita']):
                values.extend([('luogo_nascita', place.group(1).strip(), .9),
                               ('provincia_nascita', place.group(2), .9)])
            municipality = re.search(r"\bRESIDENRA[. :]*([A-ZÀ-Ü' -]{2,60})\({1,2}([A-Z]{2})\)", source, re.I)
            if municipality:
                values.extend([('comune', municipality.group(1).strip(), .86),
                               ('provincia', municipality.group(2), .86)])
    return values


def _extract_visible_fields_model(text: str, *, model: str = '') -> list[tuple[str, str, float]]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    flattened = "\n".join(lines)
    upper = flattened.upper()
    found: list[tuple[str, str, float]] = []

    cf = _find_cf(upper)
    if cf:
        found.append(("codice_fiscale", cf, 0.96))
    # Una scansione può raccogliere carta e tessera sanitaria nella stessa
    # pagina: le date della seconda non sono quelle del documento d'identità.
    from pct.document_intelligence.catalog_identita_personale import segmenti_identita_italiana
    segments = segmenti_identita_italiana(flattened)
    if model == 'tessera_sanitaria':
        personal = [('codice_fiscale', cf, .96)] if cf else []
        for field, labels, confidence in (
                ('cognome', ('COGNOME', 'SURNAME'), .88),
                ('nome', ('NOME', 'NAME'), .88)):
            value = _line_value(lines, labels)
            if value:
                personal.append((field, value, confidence))
        personal.extend(_birth_from_text(flattened))
        return personal
    identity_text = '\n'.join(segment['text'] for segment in segments if segment['model'] != 'tessera_sanitaria') if segments else flattened
    date_text = identity_text
    identity_lines = [line.strip() for line in identity_text.splitlines() if line.strip()]
    if re.search(r"CARTA\s+D[’']?IDENT|IDENTITY\s+CARD", upper):
        found.append(("doc_tipo", "CARTA_IDENTITA", 0.9))
    elif re.search(r"\bPASSAPORT", upper):
        found.append(("doc_tipo", "PASSAPORTO", 0.9))
    elif re.search(r"\bPATENTE\b", upper):
        found.append(("doc_tipo", "PATENTE", 0.86))

    for field, labels, confidence in (
        ("cognome", ("COGNOME", "SURNAME"), 0.88),
        ("nome", ("NOME", "GIVEN NAME", "GIVEN NAMES"), 0.88),
        ("sesso", ("SESSO", "SEX"), 0.86),
        ("nazionalita", ("NAZIONALITA", "NAZIONALITÀ", "CITTADINANZA", "NATIONALITY"), 0.84),
        ("doc_numero", ("NUMERO DOCUMENTO", "DOCUMENTO N", "N DOCUMENTO", "DOCUMENT NUMBER"), 0.82),
        ("doc_rilasciato_da", ("RILASCIATO DA", "AUTORITA", "AUTORITÀ", "ISSUED BY"), 0.8),
    ):
        value = _line_value(identity_lines, labels)
        if value:
            found.append((field, value, confidence))

    found.extend(_birth_from_text(identity_text))
    if model == 'carta_cartacea' or (not model and re.search(r"CARTA\s+D[’']?IDENT", identity_text, re.I) and not re.search(r'IDENTITY\s+CARD', identity_text, re.I)):
        paper_number = re.search(r"N\s*[°º.]\s*([A-Z]{2}\s*\d{7})\b", identity_text, re.I)
        if paper_number:
            found.append(('doc_numero', re.sub(r'\s+', '', paper_number.group(1)), 0.92))
        expires = re.search(r"\bSCADE\s+IL\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4})", identity_text, re.I)
        if expires:
            found.append(('doc_data_scadenza', expires.group(1), 0.94))
        birth = re.search(r"(\d{1,2}[./-]\d{1,2}[./-]\d{4})\s+NAT[OA]\s+IL", identity_text, re.I)
        if not birth:
            birth = re.search(r"NAT[OA]\s+IL[. :]*(\d{1,2}[./-]\d{1,2}[./-]\d{4})", identity_text, re.I)
        if birth:
            found.append(('data_nascita', birth.group(1), 0.92))
        # Nel vecchio modello a colonne il valore precede spesso «Nome».
        reversed_name = re.search(r"(?:^|\n)([A-ZÀ-Ü' -]{2,60})\s+NOME[. :]+", identity_text, re.I)
        if reversed_name:
            found.append(('nome', reversed_name.group(1), 0.92))
        issuer = re.search(r"\bCOM[UV]NE\s+DI\s+([A-ZÀ-Ü' -]+?)(?=\s+CARTA\b)", identity_text, re.I)
        if not issuer:
            # Il timbro dei diritti può separare l'intestazione comunale dal
            # titolo. Il valore resta quello della sola riga, non la residenza.
            issuer = re.search(r"\bCOM[UV]NE[ \t]+DI[ \t]+([A-ZÀ-Ü'’ -]{2,80})(?=\r?\n|$)", identity_text, re.I)
        if issuer:
            city = re.sub(r'\s+', ' ', issuer.group(1)).strip()
            found.append(('doc_rilasciato_da', 'Comune di ' + city.title(), 0.9))
            # Le due colonne della carta cartacea possono essere unite
            # dall'OCR: l'intestazione dei connotati non fa parte del Comune
            # stampato accanto alla data. Ripristina solo quel confine.
            stamp_text = re.sub(r'(\bCONTRASSEGNI\s+SALIENT[TI])(?=[A-ZÀ-Ü]{2,}[-–]\d)',
                                r'\1\n', identity_text, flags=re.I)
            issued = {match.group(1) for match in re.finditer(r'\b' + re.escape(city)
                + r'\s*(?:[-–,]\s*|\s+)(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b', stamp_text, re.I)}
            if len(issued) == 1:
                found.append(('doc_data_rilascio', next(iter(issued)), 0.9))
        residence = re.search(r"\b(?:CITTADINANZA|CILTADINANZA)[. :]*\s+(?:ITALIANA\s+)?([A-ZÀ-Ü' -]{2,50}?)\s+RESIDENZA[. :]*\s+((?:STRADA|VIA|VIALE|PIAZZA)\s+[^\n]{2,90}?)\s+(\d{1,5}[A-Z]?)\s+VIA\b", identity_text, re.I)
        if residence:
            city = residence.group(1).strip()
            if city:
                found.append(('comune', city, 0.86))
            found.append(('civico', residence.group(3), 0.86))
            # La denominazione della via su copie sbiadite deve essere
            # corroborata: mostrarla, senza assegnarle affidabilità fittizia.
            found.append(('via', residence.group(2), 0.6))
        municipality = re.search(r"\bRESIDENZA[. :]*([A-ZÀ-Ü' -]{2,60})\({1,2}([A-Z]{2})\)", identity_text, re.I)
        if municipality:
            found.extend([('comune', municipality.group(1).strip(), .86),
                          ('provincia', municipality.group(2), .86)])
    # CIE: le etichette italiane/inglesi e i valori sono spesso disposti
    # su righe e colonne diverse. Non leggere una intestazione come valore.
    if model == 'cie' or (not model and re.search(r"IDENTITY\s+CARD", upper)):
        # Il lettore può collocare il numero in un'intestazione prima del
        # titolo della carta. Si accetta un solo numero effettivamente letto
        # nei segmenti CIE, senza sostituire lettere o cifre.
        cie_segments = [segment['text'].upper() for segment in segments if segment['model'] == 'cie']
        cie_numbers = {value for chunk in cie_segments
                       for value in re.findall(r'\b[A-Z]{2}\d{5}[A-Z]{2}\b', chunk)}
        if len(cie_numbers) == 1:
            found.append(('doc_numero', next(iter(cie_numbers)), 0.94))
        for field, pattern in (
            ('cognome', r'\bCOGNOME\s*/\s*SURNAME\s+([A-ZÀ-Ü\'’ -]{2,80}?)\s+NOME\s*/\s*NAME\b'),
            ('nome', r'\bNOME\s*/\s*NAME\s+([A-ZÀ-Ü\'’ -]{2,80}?)(?=\s+LUOGO\b|\s+DATA\b|\n|$)'),
        ):
            values = {re.sub(r'\s+', ' ', match.group(1)).strip() for match in re.finditer(pattern, identity_text, re.I)
                      if not re.search(r'\b(?:FIRMA|TITOLARE|COGNOME|NOME|SURNAME|NAME)\b', match.group(1), re.I)}
            if len(values) == 1:
                found.append((field, next(iter(values)), 0.94))
        for field, pattern in (('sesso', r'\bSEX\s+([MF])\b'),
                               ('nazionalita', r'\bNATIONALITY\s+([A-Z]{3})\b')):
            values = {match.group(1).upper() for match in re.finditer(pattern, identity_text, re.I)}
            if len(values) == 1:
                found.append((field, next(iter(values)), 0.94))
        # Nel fronte CIE il Comune emittente ha una dicitura bilingue,
        # diversa dal Comune di residenza riportato sul retro.
        cie_issuer = re.search(
            r"\bCOMUNE\s+DI[ \t]*/?[ \t]*(?:MUNICIPALITY|MUNICIPAUTY)[ \t]*(?:\n[ \t]*)?([A-ZÀ-Ü'’ -]{2,80}?)(?=\s+COGNOME\b|\n|$)",
            identity_text, re.I,
        )
        if cie_issuer:
            city = re.sub(r'\s+', ' ', cie_issuer.group(1)).strip()
            if not re.search(r'\b(?:COGNOME|SURNAME|NOME|NAME|RESIDENZA|ADDRESS)\b', city, re.I):
                found.append(('doc_rilasciato_da', 'Comune di ' + city.title(), 0.94))
        elif len(cie_numbers) == 1:
            # La traduzione inglese può essere degradata, ma etichetta
            # italiana, separatore e nome del Comune devono essere letti.
            from pct.codice_fiscale import trova_belfiore
            issuers = {re.sub(r'\s+', ' ', match.group(1)).strip() for match in re.finditer(
                r"\bCOMUNE\s+D[IE][ \t]*/[ \t]*[A-Z]{8,15}[ \t]*(?:\n[ \t]*)?([A-ZÀ-Ü'’ -]{2,80}?)(?=\s+COGNOME\b|\n|$)",
                identity_text, re.I)}
            if len(issuers) == 1:
                city = next(iter(issuers))
                if trova_belfiore(city):
                    found.append(('doc_rilasciato_da', 'Comune di ' + city.title(), .9))
        birth = re.search(r"PLACE\s+AND\s+DATE\s+OF\s+BIRTH\s+([A-ZÀ-Ü' -]+?)\s*\(([A-Z]{2})\)\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})", flattened, re.I)
        if birth:
            found.extend([( "luogo_nascita", birth.group(1), 0.94), ("provincia_nascita", birth.group(2), 0.94), ("data_nascita", birth.group(3), 0.94)])
        else:
            # Traduzione OCR degradata: i valori restano quelli stampati.
            # La data deve concordare con la MRZ verificata della medesima
            # carta e il Comune/provincia devono esistere nel catalogo.
            labelled_birth = re.search(
                # L'OCR può unire PLACE AND DATE, senza cambiare i valori
                # stampati sulla riga successiva. Restano obbligatori tutti
                # i riscontri di carta, MRZ, data e catalogo sottostanti.
                r"\bLUOGO[^\n]{0,70}(?:\bDATE|PLACE[A-Z]{0,4}DATE)[A-Z ]{0,20}\n\s*([A-ZÀ-Ü' -]{2,60})\s*\(([A-Z]{2})\)\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})",
                flattened, re.I,
            )
            verified = _parse_mrz_from_text(flattened).get('patch') or {}
            if labelled_birth and cie_numbers == {verified.get('doc_numero')}:
                from pct.codice_fiscale import trova_belfiore
                city, province, birthday = labelled_birth.groups()
                place = trova_belfiore(city, province)
                if (place and place['provincia_nascita'] == province.upper()
                        and _clean_value('data_nascita', birthday) == _clean_value('data_nascita', verified.get('data_nascita', ''))):
                    found.extend([('luogo_nascita', city, .9), ('provincia_nascita', province, .9)])
        paired_pattern = r"EMISSIONE[^\n]*SCADENZA[^\n]*\n\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4})"
        for paired in re.finditer(paired_pattern, identity_text, re.I):
            found.extend([("doc_data_rilascio", paired.group(1), 0.95), ("doc_data_scadenza", paired.group(2), 0.95)])
        # L'etichetta Expiry della coppia non introduce la prima data:
        # quella è l'emissione. Non produrre una falsa seconda scadenza.
        date_text = re.sub(paired_pattern, '', identity_text, flags=re.I)
        # Zona emissione separata: etichetta su una propria riga, poi il
        # valore. Non prendere la data di scadenza da una riga mescolata.
        issued_zone = re.search(r'^[ \t]*EMISSIONE[ \t]*(?:[/ ]*(?:ISSUING|ASSUING))?[ \t]*\n\s*(\d{2}[./]\d{2}[./]\d{4})\b',
                                identity_text, re.I | re.M)
        if issued_zone:
            found.append(('doc_data_rilascio', issued_zone.group(1), .94))
        demographics = re.search(r"(?:SEX|NATIONALITY|HEIGHT)\s*\n\s*([MF])\s+\d{2,3}\s+(ITA)\b", upper)
        if demographics:
            found.extend([("sesso", demographics.group(1), 0.94), ("nazionalita", demographics.group(2), 0.94)])
        residence = re.search(r'\b(?:RESIDENCE|ADDRESS)\s+((?:VIALE|VIA|STRADA|PIAZZA|CORSO)\s+[^\n]{2,100}?),?\s+N[.°]?\s*(\d{1,5}[A-Z]?)\s+([A-ZÀ-Ü\'’ -]{2,60}?)\s*\(([A-Z]{2})\)', identity_text, re.I)
        if residence:
            found.extend([('via', residence.group(1).rstrip(' ,'), 0.94),
                ('civico', residence.group(2), 0.94), ('comune', residence.group(3), 0.94),
                ('provincia', residence.group(4), 0.94)])
    for field, labels, purpose, confidence in (
        ("data_nascita", ("DATA DI NASCITA", "NATO IL", "NATA IL", "DATE OF BIRTH"), "birth", 0.9),
        ("doc_data_rilascio", ("DATA RILASCIO", "RILASCIATO IL", "ISSUED ON"), "generic", 0.82),
        ("doc_data_scadenza", ("DATA SCADENZA", "SCADENZA", "VALIDA FINO AL", "VALIDO FINO AL", "EXPIRY", "EXPIRES"), "expiry", 0.9),
    ):
        value = _date_after_labels(date_text, labels, purpose)
        if value:
            found.append((field, value, confidence))

    found.extend(_address_from_text(lines))
    if model == 'carta_cartacea':
        from pct.document_intelligence.catalog_identita_personale import residenza_riga_cartacea
        address = residenza_riga_cartacea(identity_text)
        if address:
            found.extend([('via', address[0], .9), ('civico', address[1], .9)])
    email = _find_email(flattened)
    if email:
        found.append(("email", email, 0.82))
    pec = _find_labelled_email(flattened, ("PEC", "POSTA CERTIFICATA"))
    if pec:
        found.append(("pec", pec, 0.84))
    phone = _line_value(lines, ("TELEFONO", "TEL", "PHONE"))
    if phone:
        found.append(("telefono", phone, 0.8))
    mobile = _line_value(lines, ("CELLULARE", "MOBILE"))
    if mobile:
        found.append(("cellulare", mobile, 0.8))
    return found


def _line_value(lines: list[str], labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    for index, line in enumerate(lines):
        if re.fullmatch(rf"\s*(?:{label_pattern})\s*/\s*(?:SURNAME|NAME|GIVEN NAMES?|NATIONALITY|SEX)\s*", line, flags=re.I):
            if index + 1 < len(lines):
                return _trim_value(lines[index + 1])
            continue
        match = re.search(rf"\b(?:{label_pattern})\b\s*(?:[:\-\.]|N[.°])?\s*(.+)$", line, flags=re.I)
        if match:
            raw = re.sub(r"^\s*/\s*(?:SURNAME|NAME|GIVEN NAMES?|NATIONALITY|SEX)\b\s*", "", match.group(1), flags=re.I)
            if re.search(r"\b(?:HEIGHT|NATIONALITY|SEX)\b", raw, re.I):
                continue
            value = _trim_value(raw)
            if value and _normalize_key(value) not in {_normalize_key(label) for label in labels}:
                return value
        if re.fullmatch(rf"\s*(?:{label_pattern})\s*", line, flags=re.I) and index + 1 < len(lines):
            return _trim_value(lines[index + 1])
    return ""


def _trim_value(value: str) -> str:
    clean = re.split(
        r"\b(?:NOME|COGNOME|SESSO|SEX|DATA|NATO|NATA|RATO(?=\s+IL)|NAT(?=\s*\d)|LUOGO|SCADENZA|RILASCIO|RESIDENZA|INDIRIZZO|NAZIONALIT[ÀA])\b|\bRESIDENRA(?=[A-ZÀ-Ü(])",
        str(value or "").strip(" .:-"),
        maxsplit=1,
        flags=re.I,
    )[0]
    return clean.strip(" .:-")


def _birth_from_text(text: str) -> list[tuple[str, str, float]]:
    found: list[tuple[str, str, float]] = []
    match = re.search(
        r"\bNAT[OA]\s+A\s+([A-ZÀ-Ü' -]{2,60}?)(?:\s*\(([A-Z]{2})\)|\s+([A-Z]{2}))?\s+(?:IL\s+)?(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        text,
        flags=re.I,
    )
    if match:
        found.append(("luogo_nascita", match.group(1), 0.88))
        province = match.group(2) or match.group(3)
        if province:
            found.append(("provincia_nascita", province, 0.9))
        found.append(("data_nascita", match.group(4), 0.9))
    place = re.search(r"\bLUOGO\s+DI\s+NASCITA\s*[:\-]?\s*([A-ZÀ-Ü' -]{2,60}?)(?:\s*\(([A-Z]{2})\)|\s+([A-Z]{2})\b)", text, flags=re.I)
    if place:
        found.append(("luogo_nascita", place.group(1), 0.86))
        province = place.group(2) or place.group(3)
        if province:
            found.append(("provincia_nascita", province, 0.88))
    return found


def _date_after_labels(text: str, labels: tuple[str, ...], purpose: str) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*[:\-]?\s*(\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})", text, flags=re.I)
    # La normalizzazione avviene in _remember_field: conservare qui anche
    # il token invalido permette di spiegare perché non viene applicato.
    return match.group(1) if match else ""


def _address_from_text(lines: list[str]) -> list[tuple[str, str, float]]:
    for line in lines:
        if not re.search(r"\b(?:RESIDENZA|INDIRIZZO|ADDRESS)\b", line, flags=re.I):
            continue
        value = re.sub(r"^.*?\b(?:RESIDENZA|INDIRIZZO|ADDRESS)\b\s*[:\-]?", "", line, flags=re.I).strip()
        match = re.search(r"(.+?)\s+(\d+[A-Z]?)\s*,?\s*(\d{5})\s+(.+?)\s+\(?([A-Z]{2})\)?$", value, flags=re.I)
        if not match:
            continue
        return [
            ("via", match.group(1), 0.8),
            ("civico", match.group(2), 0.8),
            ("cap", match.group(3), 0.82),
            ("comune", match.group(4), 0.78),
            ("provincia", match.group(5), 0.82),
            ("nazione", "Italia", 0.8),
        ]
    return []


def _find_cf(text: str) -> str:
    codes = _codici_fiscali_validi(text)
    return next(iter(codes)) if len(codes) == 1 else ''


def _codici_fiscali_validi(text: str) -> set[str]:
    from pct.clienti import GestioneClienti
    from pct.codice_fiscale import _checksum
    normalized = re.sub(r'\bCODICE(?=[A-Z]{6}[0-9LMNPQRSTUV]{2})', 'CODICE ', str(text or '').upper())
    candidates = re.findall(r"\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b", normalized)
    return {code for code in candidates if GestioneClienti.valida_cf(code) and _checksum(code[:15]) == code[15]}


def _find_email(text: str) -> str:
    match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", str(text or ""), flags=re.I)
    return match.group(0).lower() if match else ""


def _find_labelled_email(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"\b(?:{label_pattern})\b\s*[:\-]?\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{{2,}})", text, flags=re.I)
    return match.group(1).lower() if match else ""
