"""Stato operativo da archiviare da una sentenza propria, con fonte e capo economico."""
from __future__ import annotations
import hashlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any
from pct.fascicoli import AvanzamentoPratica, StatoFascicolo
from pct.pec_case_identity import document_case_identity_evidence
from pct.spese_liquidate_lettura import estrai_spese_liquidate

RULE = 'sentenza-propria-da-archiviare-v3-conclusiva'
# Lettore «proposta_definizione»: cambia con la regola, con la lettura del dispositivo e con la
# registrazione automatica dei casi certi (pct/sentenza_automatica.py): lo storico si riesamina sui testi salvati.
# automatica.v2: definizione e credito con certezze separate; pec.v1: anche gli allegati delle PEC collegate;
# ruolo-esteso: numero di ruolo scritto per esteso nell'intestazione («n. 2539, del Ruolo Generale … dell'anno 2025»).
VERSIONE_PROPOSTA = RULE + '+proposta-avvocato.v1+automatica.v2+pec.v1+ruolo-esteso'

def verifica_sentenza_da_archiviare(*, fascicolo: Any, testo: str, fonte: dict[str, Any], cliente: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {'eligible': False, 'rule': RULE, 'fascicolo_id': str(fascicolo.id), 'source': fonte,
              'case_version': str(getattr(fascicolo,'modificato_il','') or ''),
              'expected_case': {key:str(getattr(fascicolo,key,'') or '') for key in ('nome_cliente','numero_rg','anno_rg','tribunale','id_cliente')}}
    if not fonte.get('verified_original') or not re.fullmatch(r'[0-9a-f]{64}', str(fonte.get('sha256') or '')):
        return {**result, 'reason': 'Originale e impronta della fonte non verificati.'}
    # La rilettura di una vecchia fonte non annulla una riapertura registrata.
    reopened = [a for a in fascicolo.avanzamento or []
                if str(a.stato_precedente or '').upper() in {'DEFINITO','ARCHIVIATO'}
                and str(a.stato_nuovo or '').upper() in {'APERTO','IN_CORSO','SOSPESO'}]
    if fascicolo.stato in {StatoFascicolo.APERTO,StatoFascicolo.IN_CORSO,StatoFascicolo.SOSPESO} and reopened:
        return {**result, 'reason': 'Riapertura del procedimento registrata: preservato lo stato e richiesta una prova successiva alla riapertura.'}
    identity = document_case_identity_evidence(testo, fascicolo)
    result['identity'] = identity
    if not identity['complete_match']:
        return {**result, 'reason': 'Identità congiunta del procedimento non confermata.'}
    from pct.pec_case_identity import client_tax_code_from_documents, case_identity_evidence
    profile = {'cliente': fascicolo.nome_cliente, 'ufficio': identity['source_office'],
               'numero_ruolo_certificato': identity['source_rg']}
    profile = client_tax_code_from_documents(profile, [{'filename':'provvedimento.pdf','text':testo,'sha256':fonte['sha256']}])
    tax_identity = case_identity_evidence(profile, fascicolo, cliente)
    result['party_tax_code'] = tax_identity
    if tax_identity['conflicts'] or (tax_identity['party_tax_code_present'] and not tax_identity['client_tax_code_match']):
        return {**result, 'reason': 'Codice fiscale della parte non concordante o non verificabile nell’anagrafica.'}
    # Il testo decide il grado? Regola condivisa con la proposta di definizione:
    # sentenze non definitive, parziali o con prosecuzione non definiscono nulla.
    from pct.sentenza_conclusiva import valuta_sentenza

    valutazione = valuta_sentenza(testo)
    result['grado'] = valutazione['grado']
    if not valutazione['conclusiva']:
        return {**result, 'reason': valutazione['motivo']}
    dispositivo = valutazione['dispositivo']
    # Il capo spese è un dato in più, non una condizione: le spese compensate
    # (art. 92 c.p.c.) definiscono il giudizio come una condanna alle spese.
    amount, quote = estrai_spese_liquidate(dispositivo)
    return {**result, 'eligible': True, 'amount': amount, 'quote': quote or '',
            'compensate': valutazione['compensate'],
            'decision_sha256': hashlib.sha256(dispositivo.encode('utf-8')).hexdigest(),
            'reason': valutazione['motivo']}


def applica_sentenza_da_archiviare(*, fascicoli_repository: Any, fascicolo_id: str,
                                  verifica: dict[str, Any], actor: str = 'motore-sentenze') -> dict[str, Any]:
    if not verifica.get('eligible') or verifica.get('fascicolo_id') != fascicolo_id:
        return {'changed': False, 'reason': verifica.get('reason') or 'Verifica non valida.'}
    fascicolo = fascicoli_repository.get(fascicolo_id)
    if fascicolo is None:
        return {'changed': False, 'reason': 'Fascicolo non disponibile.'}
    source = verifica['source']
    note = ('Sentenza conclusiva della pratica; fonte ' + str(source.get('name') or source.get('document_id') or source.get('message_id'))
            + (' / '+source['component_path'] if source.get('component_path') else '') + '; SHA-256 ' + source['sha256'] + '; capo economico: ' + (verifica.get('quote') or 'spese non liquidate nel dispositivo')
            + '. Predisposizione all’archivio; termini, attività e verifiche residue restano attivi. Non certifica il passaggio in giudicato.')
    from pct.stato_fascicolo import Prova, ammessa, avanzamento
    import json
    db = fascicoli_repository._studio_db
    if db is None: raise ValueError('Fonte SQL non disponibile.')
    pg = getattr(db,'backend_kind','') == 'postgresql'
    connection = db.conn if pg else db._conn_per_scrittura()
    begun = False
    try:
        if not pg:
            connection.execute('PRAGMA busy_timeout=15000')
            connection.execute('BEGIN IMMEDIATE')
        begun = True
        row = connection.execute('SELECT * FROM fascicoli WHERE id = ?' + (' FOR UPDATE' if pg else ''),(fascicolo_id,)).fetchone()
        if row is None: raise ValueError('Fascicolo SQL non disponibile.')
        current = fascicoli_repository._row_to_fascicolo(row)
        if current is None: raise ValueError('Fascicolo SQL non ricostruibile.')
        if current.stato in (StatoFascicolo.DEFINITO,StatoFascicolo.ARCHIVIATO):
            connection.execute('COMMIT');begun=False
            return {'changed':False,'already_present':True,'state':current.stato.value,'acknowledgement':'già presente'}
        expected = verifica.get('expected_case') or {}
        if not expected or any(str(getattr(current,key,'') or '')!=value for key,value in expected.items()) or str(getattr(current,'modificato_il','') or '')!=verifica.get('case_version'):
            connection.execute('COMMIT');begun=False
            return {'changed':False,'retry':True,'reason':'Il fascicolo è cambiato durante la lettura: controllo da ripetere sul dato corrente.'}
        if current.stato == StatoFascicolo.SOSPESO:
            connection.execute('COMMIT');begun=False
            return {'changed':False,'reason':'Sospensione registrata: mantenuta la decisione del fascicolo.'}
        if source.get('document_id'):
            doc = next((d for d in current.documenti if d.id==source['document_id']),None)
            if doc is None or (source.get('archive_sha256') and doc.hash_sha256!=source['archive_sha256']):
                raise ValueError('Documento del fascicolo modificato dopo la verifica della fonte.')
        prova = Prova(StatoFascicolo.DEFINITO,'Sentenza conclusiva verificata: fascicolo da archiviare',note)
        if not ammessa(current.stato,prova):
            connection.execute('COMMIT');begun=False
            return {'changed':False,'reason':'Transizione non ammessa dal ciclo nativo.'}
        now = datetime.now(ZoneInfo('Europe/Rome'))
        item = avanzamento(current.stato,prova,autore=actor)
        item.data = now.isoformat(timespec='seconds')
        current.avanzamento.append(item);current.stato=prova.stato
        current.modificato_il=item.data
        if not current.data_chiusura:current.data_chiusura=now.date().isoformat()
        payload=fascicoli_repository._dati_json_snello(current.to_dict())
        connection.execute('UPDATE fascicoli SET stato=?, data_chiusura=?, modificato_il=?, dati_json=? WHERE id=?',
            (current.stato.value,current.data_chiusura,current.modificato_il,json.dumps(payload,ensure_ascii=False),fascicolo_id))
        connection.execute('COMMIT');begun=False
    except Exception:
        if begun: connection.execute('ROLLBACK')
        raise
    # Le colonne di documenti, attività, depositi, anagrafica e pagamenti non sono
    # sostituite da una copia in memoria: la transizione aggiorna solo il suo dato.
    fascicoli_repository._fascicoli[fascicolo_id]=current
    fascicoli_repository._rigenera_mirror_fascicoli_json()
    return {'changed':True,'state':current.stato.value,'ready':current.archivio_pronto,
            'source':source,'amount':verifica.get('amount'),'rule':RULE}

