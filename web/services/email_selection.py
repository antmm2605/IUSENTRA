"""Selezione multipagina con gli stessi filtri della casella React."""
from web.services.react_email_bridge import build_react_email_payload


def select_mailbox_ids(db_path, query, *, ordinary=False, tenant_id='default'):
    return build_react_email_payload(
        db_path=db_path, include_telematic=not ordinary, tenant_id=tenant_id,
        folder=query.get('cartella', 'INBOX'), query=query.get('q', '').strip(),
        stato=query.get('stato', '').strip().upper(),
        solo_pst=not ordinary and query.get('pst') == '1',
        con_allegati=query.get('con_allegati') == '1',
        solo_collegate=not ordinary and query.get('collegate') == '1',
        solo_da_presidiare=not ordinary and query.get('da_presidiare') == '1',
        stato_pct=query.get('stato_pct', '').strip().upper() if not ordinary else '',
        origine=query.get('origine', '').strip().upper(),
        data_da=query.get('data_da', '').strip(), data_a=query.get('data_a', '').strip(),
        selection_only=True,
    )
