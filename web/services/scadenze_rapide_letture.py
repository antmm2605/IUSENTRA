"""Scadenze rapide: lettura per utente, senza alterare adempimento o termini."""
import hashlib
import json
from flask import g, jsonify, request
from web.services import topbar_operational
from web.services.controllo_studio_letture import repository
from web.services.registro_letture_runtime import utente_corrente_id


def aggiungi_letture(rows, summary):
    viste = repository().scadenze_viste(utente_corrente_id())
    for row in rows:
        row['revisione'] = hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
        row['letta'] = viste.get(row['id']) == row['revisione']
    summary['unreadOverdue'] = sum(not r['letta'] and r['status']=='overdue' for r in rows)
    summary['unreadUrgent'] = sum(not r['letta'] and (r['status']=='overdue' or r['priority']=='urgent') for r in rows)


def elenco():
    return topbar_operational.quick_deadlines_payload(g.get('utente_corrente'), full=True)


def register_routes(app, audit):
    def puo():
        user = g.get('utente_corrente')
        return bool(user and user.ha_permesso('scadenziario.leggi'))

    @app.get('/api/v1/ui/scadenze-rapide')
    def scadenze_rapide_elenco():
        if not puo(): return jsonify(ok=False,message='Permesso insufficiente.'),403
        return jsonify(elenco())

    @app.post('/api/v1/ui/scadenze-rapide/lette')
    def scadenze_rapide_lette():
        if not puo(): return jsonify(ok=False,message='Permesso insufficiente.'),403
        payload = request.get_json(silent=True)
        ids = payload.get('ids') if isinstance(payload,dict) else None
        if not isinstance(ids,list) or not 1 <= len(ids) <= 2000 or any(not isinstance(i,str) or not i for i in ids):
            return jsonify(ok=False,message='Seleziona le scadenze da leggere.'),400
        current = {v['id']:v for v in elenco()['deadlines']}
        if any(i not in current for i in ids):
            return jsonify(ok=False,message='La selezione è cambiata: aggiorna l’elenco.'),409
        n = repository().segna_scadenze(utente_corrente_id(),[current[i] for i in dict.fromkeys(ids)])
        from web.services.react_dashboard_cache import invalidate_dashboard_payload_cache
        from web.blueprints.topbar import _topbar_cache_key
        invalidate_dashboard_payload_cache(_topbar_cache_key('deadlines'))
        audit('scadenze.presa_visione','scadenziario','',dettagli=json.dumps(ids))
        oggetto = 'scadenza' if n == 1 else 'scadenze'
        return jsonify(ok=True,message=f'Presa visione salvata per {n} {oggetto}. Gli adempimenti restano aperti.')
