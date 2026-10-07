"""Presa visione e lettura: persistenti, isolate per studio, SQLite/PostgreSQL."""
from datetime import datetime, timezone
from pathlib import Path

class LettureControllo:
    def __init__(self, registro, tenant):
        if not tenant or tenant in {'default', 'single-studio'}:
            raise ValueError('Studio obbligatorio.')
        self.registro, self.tenant = registro, tenant
        suffix = '_postgres' if registro.backend_kind == 'postgres' else ''
        with registro.connection() as c:
            c.executescript((Path(__file__).resolve().parent.parent/'sql'/f'20261005_controllo_letture{suffix}.sql').read_text('utf-8'))

    def viste(self, utente):
        if not utente: raise ValueError('Utente obbligatorio.')
        with self.registro.connection() as c:
            rows = c.execute('SELECT fascicolo_id,codice,chiave,revisione FROM controllo_discordanze_viste WHERE tenant_id=? AND utente_id=?',(self.tenant,utente)).fetchall()
        return {(r['fascicolo_id'],r['codice'],r['chiave']):r['revisione'] for r in rows}

    def conferma(self, utente, voci):
        if not utente or not isinstance(voci,list) or not 1 <= len(voci) <= 1000:
            raise ValueError('Selezione delle verifiche non valida.')
        now = datetime.now(timezone.utc).isoformat()
        with self.registro.connection() as c:
            for v in voci:
                if not isinstance(v,dict): raise ValueError('Verifica non valida.')
                key = tuple(str(v.get(k) or '') for k in ('fascicoloId','codice','chiave','revisione'))
                if not all(key): raise ValueError('Identità della verifica incompleta.')
                row = c.execute("SELECT revisione FROM letture_discordanze WHERE tenant_id=? AND fascicolo_id=? AND codice=? AND chiave=? AND stato='aperta'",(self.tenant,*key[:3])).fetchone()
                if not row or row['revisione'] != key[3]:
                    raise ValueError('La verifica è cambiata: aggiorna e rileggi prima di confermare.')
                c.execute('INSERT INTO controllo_discordanze_viste (tenant_id,utente_id,fascicolo_id,codice,chiave,revisione,letta_il) VALUES (?,?,?,?,?,?,?) ON CONFLICT(tenant_id,utente_id,fascicolo_id,codice,chiave) DO UPDATE SET revisione=excluded.revisione,letta_il=excluded.letta_il',(self.tenant,utente,*key,now))
        return len(voci)

    def pec_lette(self):
        with self.registro.connection() as c:
            return {r['email_id'] for r in c.execute("SELECT email_id FROM controllo_pec_letture WHERE tenant_id=? AND stato='LETTA'",(self.tenant,)).fetchall()}

    def segna_pec(self, utente, ids):
        if not utente or not isinstance(ids,list) or not 1 <= len(ids) <= 2000 or any(not isinstance(i,str) or not i or len(i)>200 for i in ids):
            raise ValueError('Selezione delle comunicazioni non valida.')
        ids = list(dict.fromkeys(ids))
        now = datetime.now(timezone.utc).isoformat()
        with self.registro.connection() as c:
            for eid in ids:
                c.execute("INSERT INTO controllo_pec_letture (tenant_id,email_id,utente_id,letta_il,stato) VALUES (?,?,?,?,?) ON CONFLICT(tenant_id,email_id) DO UPDATE SET utente_id=excluded.utente_id,letta_il=excluded.letta_il,stato=excluded.stato",(self.tenant,eid,utente,now,"LETTA"))
        return ids, now

    def stati_pec(self):
        with self.registro.connection() as c:
            return {r['email_id']: (r['stato'],r['letta_il']) for r in c.execute('SELECT email_id,stato,letta_il FROM controllo_pec_letture WHERE tenant_id=?',(self.tenant,)).fetchall()}

    def pec_non_letta(self, utente, eid):
        if not utente or not eid: raise ValueError('Utente e comunicazione obbligatori.')
        with self.registro.connection() as c:
            c.execute("INSERT INTO controllo_pec_letture (tenant_id,email_id,utente_id,letta_il,stato) VALUES (?,?,?,?,?) ON CONFLICT(tenant_id,email_id) DO UPDATE SET utente_id=excluded.utente_id,letta_il=excluded.letta_il,stato=excluded.stato",(self.tenant,eid,utente,"","NON_LETTA"))

    def non_viste(self, utente):
        if not utente: raise ValueError('Utente obbligatorio.')
        with self.registro.connection() as c:
            return c.execute("SELECT COUNT(*) AS n FROM letture_discordanze d WHERE d.tenant_id=? AND d.stato='aperta' AND NOT EXISTS (SELECT 1 FROM letture_eventi e WHERE e.tenant_id=d.tenant_id AND e.fascicolo_id=d.fascicolo_id AND e.stato IN ('pending','running')) AND NOT EXISTS (SELECT 1 FROM controllo_discordanze_viste v WHERE v.tenant_id=d.tenant_id AND v.utente_id=? AND v.fascicolo_id=d.fascicolo_id AND v.codice=d.codice AND v.chiave=d.chiave AND v.revisione=d.revisione)",(self.tenant,utente)).fetchone()['n']

    def scadenze_viste(self, utente):
        if not utente: raise ValueError('Utente obbligatorio.')
        with self.registro.connection() as c:
            return {r['scadenza_id']:r['revisione'] for r in c.execute('SELECT scadenza_id,revisione FROM controllo_scadenze_viste WHERE tenant_id=? AND utente_id=?',(self.tenant,utente)).fetchall()}

    def segna_scadenze(self, utente, voci):
        if not utente or not isinstance(voci,list) or not 1 <= len(voci) <= 2000 or any(not isinstance(v,dict) or not isinstance(v.get('id'),str) or not v['id'] or len(v['id'])>200 or not isinstance(v.get('revisione'),str) or not v['revisione'] for v in voci):
            raise ValueError('Selezione delle scadenze non valida.')
        now = datetime.now(timezone.utc).isoformat()
        with self.registro.connection() as c:
            for v in voci:
                c.execute('INSERT INTO controllo_scadenze_viste (tenant_id,utente_id,scadenza_id,revisione,letta_il) VALUES (?,?,?,?,?) ON CONFLICT(tenant_id,utente_id,scadenza_id) DO UPDATE SET revisione=excluded.revisione,letta_il=excluded.letta_il',(self.tenant,utente,v['id'],v['revisione'],now))
        return len({v['id'] for v in voci})
