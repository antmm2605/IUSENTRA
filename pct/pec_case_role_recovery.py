"""Recupero governato del ruolo dei fascicoli importati, da prove concordanti.

Non invia PEC e non crea depositi. Il chiamante consegna estrazioni già verificate
e riferimenti originali; nessuna lettura, OCR o scrittura durante una GET.
"""
from __future__ import annotations

from copy import copy
import hashlib
import json
import re
from datetime import datetime

from pct.pec_case_identity import case_identity_evidence, client_tax_code_from_documents, _tokens


def decide_missing_role(case, *, client, receipt, communication, submission, documents):
    """Il ruolo certificato deve legarsi alla pratica, non solo al suo cliente."""
    role = str(receipt.get('numero_ruolo_certificato') or '')
    match = re.fullmatch(r'(\d{1,7})/(\d{4})', role)
    if not match or receipt.get('status') not in {'accepted', 'accepted_manually'}:
        return {'ok': False, 'reason': 'accettazione_cancelleria_con_ruolo_assente'}
    if not submission.get('verified_original_reference') or not submission.get('unique_case_reference'):
        return {'ok': False, 'reason': 'riferimento_deposito_importato_non_dimostrato'}
    if not str(communication.get('cliente_origine') or '').startswith('Comunicazione.xml:'):
        return {'ok': False, 'reason': 'identita_ministeriale_assente'}
    projected = copy(case)
    projected.numero_rg, projected.anno_rg = str(int(match[1])), int(match[2])
    identity = case_identity_evidence(communication, projected, client)
    if identity['conflicts'] or not all(identity[key] for key in ('rg_match', 'office_match', 'client_name_match')):
        return {'ok': False, 'reason': 'identita_congiunta_non_concordante', 'identity': identity}
    office_identity = case_identity_evidence({**communication, 'ufficio': submission.get('receipt_office')}, projected, client)
    if not office_identity['office_match']:
        return {'ok': False, 'reason': 'ufficio_accettazione_discordante'}
    # I documenti devono contenere il cliente, con il suo codice quando dichiarato.
    # Non correggere un cognome per somiglianza né prendere il codice del difensore.
    primary = [doc for doc in documents if doc.get('party_name_confirmed')]
    if not primary:
        return {'ok': False, 'reason': 'cliente_non_confermato_nel_ricorso_originale'}
    party = client_tax_code_from_documents(communication, primary)
    checked = case_identity_evidence(party, projected, client)
    if checked['conflicts'] or (checked['party_tax_code_present'] and not checked['client_tax_code_match']):
        return {'ok': False, 'reason': 'codice_fiscale_originale_non_concordante', 'identity': checked}
    if _tokens(getattr(case, 'nome_cliente', '')) != _tokens(communication.get('cliente')):
        return {'ok': False, 'reason': 'cliente_discordante'}
    current = str(getattr(case, 'numero_rg', '') or '').strip()
    current_year = str(getattr(case, 'anno_rg', '') or '').strip()
    if current:
        if current == projected.numero_rg and current_year == str(projected.anno_rg):
            return {'ok': True, 'status': 'already_present', 'role': role}
        return {'ok': False, 'reason': 'ruolo_esistente_preservato'}
    evidence = {'case_id': str(case.id), 'role': role, 'identity': checked,
                'submission': submission,
                'documents': [{k:doc.get(k) for k in ('id','filename','sha256')} for doc in primary]}
    evidence['sha256'] = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'ok': True, 'status': 'recoverable', 'number': projected.numero_rg, 'year': projected.anno_rg, 'role': role, 'evidence': evidence}


def apply_missing_role(manager, case, decision, *, actor='pec-role-recovery'):
    """Salvataggio mirato nativo; stato manuale e documenti sono preservati."""
    if not decision.get('ok') or decision.get('status') != 'recoverable':
        return decision
    from pct.fascicoli import AvanzamentoPratica
    rows = manager._studio_db.fetchall_readonly('SELECT * FROM fascicoli WHERE id=?', (str(case.id),))
    fresh = manager._row_to_fascicolo(rows[0]) if rows else None
    if fresh is None:
        raise ValueError('Fascicolo non disponibile per il recupero del ruolo.')
    if str(fresh.numero_rg or '').strip():
        return {'ok': False, 'reason': 'ruolo_modificato_dopo_verifica'}
    if (fresh.id_cliente, fresh.nome_cliente, fresh.tribunale) != (case.id_cliente, case.nome_cliente, case.tribunale):
        return {'ok': False, 'reason': 'identita_modificata_dopo_verifica'}
    fresh.numero_rg, fresh.anno_rg = decision['number'], decision['year']
    fresh.modificato_il = datetime.now().isoformat()
    fresh.avanzamento.append(AvanzamentoPratica(
        data=fresh.modificato_il, descrizione=f"R.G. {decision['role']} recuperato dall’accettazione della cancelleria",
        stato_precedente=fresh.stato.value, stato_nuovo=fresh.stato.value, avvocato=actor,
        note='Identità del cliente, ufficio giudiziario e accettazione della cancelleria '
             'concordanti. Fonti originali e impronte conservate nel registro delle verifiche. '
             f"Riferimento prova: {decision['evidence']['sha256']}.",
    ))
    # CAS sulle due rappresentazioni: un salvataggio concorrente impedisce
    # l'aggiornamento, senza riscrivere documenti, pagamenti o decisioni manuali.
    original_json = str(rows[0]['dati_json'] or '{}')
    payload = json.loads(original_json)
    payload.update(numero_rg=fresh.numero_rg, anno_rg=fresh.anno_rg,
                   modificato_il=fresh.modificato_il, avanzamento=fresh.to_dict()['avanzamento'])
    conn = manager._studio_db.conn
    try:
        changed = conn.execute(
            'UPDATE fascicoli SET numero_rg=?,anno_rg=?,modificato_il=?,dati_json=? '
            'WHERE id=? AND COALESCE(numero_rg,\'\')=\'\' AND dati_json=?',
            (fresh.numero_rg, str(fresh.anno_rg), fresh.modificato_il,
             json.dumps(payload, ensure_ascii=False), str(fresh.id), original_json),
        )
        if changed.rowcount != 1:
            conn.rollback()
            return {'ok': False, 'reason': 'fascicolo_modificato_dopo_verifica'}
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    manager._fascicoli[fresh.id] = fresh
    manager._rigenera_mirror_fascicoli_json()
    return {**decision, 'status': 'recovered'}
