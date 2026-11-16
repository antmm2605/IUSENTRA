"""Esiti e discordanze materializzati nel registro SQL dello studio."""
from __future__ import annotations
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _revision(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


class RegistroDiscordanze:
    def __init__(self, registro):
        self.registro = registro
        schema = '20261002_letture_discordanze_postgres.sql' if registro.backend_kind == 'postgres' else '20261002_letture_discordanze.sql'
        with registro.connection() as c:
            c.executescript((Path(__file__).resolve().parent/'sql'/schema).read_text(encoding='utf-8'))

    def esito(self, tenant, fid):
        if not tenant or not fid:
            raise ValueError('Studio e fascicolo obbligatori')
        with self.registro.connection() as c:
            row = c.execute('SELECT payload_json,revisione FROM letture_verifiche_esiti WHERE tenant_id=? AND fascicolo_id=?',(tenant,fid)).fetchone()
        return (json.loads(row['payload_json']),row['revisione']) if row else ({},'')

    def pubblica_esito(self, tenant, fid, payload):
        if not tenant or not fid:
            raise ValueError('Studio e fascicolo obbligatori')
        now = datetime.now(timezone.utc).isoformat()
        with self.registro.connection() as c:
            c.execute('INSERT INTO letture_verifiche_esiti (tenant_id,fascicolo_id,payload_json,revisione,aggiornato_il) VALUES (?,?,?,?,?) ON CONFLICT(tenant_id,fascicolo_id) DO UPDATE SET payload_json=excluded.payload_json,revisione=excluded.revisione,aggiornato_il=excluded.aggiornato_il',(tenant,fid,_json(payload),_revision(payload),now))

    def firma_fonti(self, tenant, fid):
        """La revisione delle fonti già lette, senza aprire file o ricalcolare fatti."""
        with self.registro.connection() as conn:
            rows = conn.execute(
                "SELECT lettore, impronta FROM letture_fascicoli WHERE tenant_id=? AND fascicolo_id=? "
                "AND lettore IN ('motore_documenti','motore_pec')",
                (tenant, fid),
            ).fetchall()
        impronte = {row["lettore"]: row["impronta"] for row in rows}
        return f"{impronte.get('motore_documenti', '') or ''}:{impronte.get('motore_pec', '') or ''}"

    def fascicoli_da_verificare(self, tenant, *, versione, retry_prima_di, limite=4):
        """Prima verifica, fonte cambiata, nuove regole o esito interrotto."""
        if not tenant or limite <= 0:
            return []
        postgres = self.registro.backend_kind == "postgres"
        firma = "(CAST(v.payload_json AS jsonb)->>'firma_fonti')" if postgres else "json_extract(v.payload_json,'$.firma_fonti')"
        regole = "(CAST(v.payload_json AS jsonb)->>'versione_verifiche')" if postgres else "json_extract(v.payload_json,'$.versione_verifiche')"
        fine = "(CAST(v.payload_json AS jsonb)->>'completata_il')" if postgres else "json_extract(v.payload_json,'$.completata_il')"
        errori = "(CAST(v.payload_json AS jsonb)->>'errori')" if postgres else "json_extract(v.payload_json,'$.errori')"
        with self.registro.connection() as conn:
            rows = conn.execute(
                "SELECT f.fascicolo_id FROM letture_fascicoli f "
                "LEFT JOIN letture_fascicoli p ON p.tenant_id=f.tenant_id AND p.fascicolo_id=f.fascicolo_id "
                "AND p.lettore='motore_pec' "
                "LEFT JOIN letture_verifiche_esiti v ON v.tenant_id=f.tenant_id AND v.fascicolo_id=f.fascicolo_id "
                "WHERE f.tenant_id=? AND f.lettore='motore_documenti' AND f.stato='completa' "
                f"AND (v.aggiornato_il IS NULL OR COALESCE({regole}, '')<>? "
                f"OR COALESCE({firma}, '')<>COALESCE(f.impronta,'')||':'||COALESCE(p.impronta,'') "
                f"OR ((COALESCE({fine},'')='' OR COALESCE({errori},'{{}}')<>'{{}}') AND v.aggiornato_il<?)) "
                "AND NOT EXISTS (SELECT 1 FROM letture_eventi e WHERE e.tenant_id=f.tenant_id AND e.fascicolo_id=f.fascicolo_id "
                "AND e.stato IN ('pending','running')) "
                "ORDER BY COALESCE(v.aggiornato_il,''), f.aggiornato_il, f.fascicolo_id LIMIT ?",
                (tenant, versione, retry_prima_di, limite),
            ).fetchall()
        return [str(row["fascicolo_id"]) for row in rows]

    def riconcilia(self, tenant, fid, codice, voci):
        """Solo il verificatore completo può superare una discordanza non più presente."""
        if not tenant or not fid or not codice:
            raise ValueError('Ambito del verificatore obbligatorio')
        now = datetime.now(timezone.utc).isoformat()
        with self.registro.connection() as c:
            prior = {r['chiave']:dict(r) for r in c.execute('SELECT * FROM letture_discordanze WHERE tenant_id=? AND fascicolo_id=? AND codice=?',(tenant,fid,codice)).fetchall()}
            current = {str(v['chiave']):v for v in voci}
            for key in sorted(set(prior)|set(current)):
                payload = current.get(key) or json.loads(prior[key]['payload_json'])
                state = 'aperta' if key in current else 'superata'
                revision = _revision({'stato':state,'payload':payload})
                old = prior.get(key)
                if old and old['revisione'] == revision:
                    continue
                serialized = _json(payload)
                c.execute('INSERT INTO letture_discordanze (tenant_id,fascicolo_id,codice,chiave,stato,payload_json,revisione,aggiornata_il) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,fascicolo_id,codice,chiave) DO UPDATE SET stato=excluded.stato,payload_json=excluded.payload_json,revisione=excluded.revisione,aggiornata_il=excluded.aggiornata_il',(tenant,fid,codice,key,state,serialized,revision,now))
                c.execute('INSERT INTO letture_discordanze_audit (id,tenant_id,fascicolo_id,codice,chiave,stato,revisione,payload_json,registrato_il) VALUES (?,?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,tenant,fid,codice,key,state,revision,serialized,now))

    def aperte(self, tenant, *, page=1, limit=50):
        if not tenant:
            raise ValueError('Studio obbligatorio')
        with self.registro.connection() as c:
            size = max(1,min(100,int(limit)))
            offset = (max(1,int(page))-1)*size
            now = datetime.now(timezone.utc).isoformat()
            coda = c.execute(
                "SELECT CASE WHEN stato='running' AND lease_until>? THEN 'in_corso' ELSE 'in_coda' END AS fase, "
                "COUNT(*) AS n FROM letture_eventi WHERE tenant_id=? AND stato IN ('pending','running') GROUP BY 1",
                (now, tenant),
            ).fetchall()
            conteggi = {riga['fase']: int(riga['n']) for riga in coda}
            summary = c.execute("SELECT COUNT(*) AS n, MAX(d.aggiornata_il) AS ultimo FROM letture_discordanze d WHERE d.tenant_id=? AND d.stato='aperta' AND NOT EXISTS (SELECT 1 FROM letture_eventi e WHERE e.tenant_id=d.tenant_id AND e.fascicolo_id=d.fascicolo_id AND e.stato IN ('pending','running'))",(tenant,)).fetchone()
            rows = c.execute("SELECT d.* FROM letture_discordanze d WHERE d.tenant_id=? AND d.stato='aperta' AND NOT EXISTS (SELECT 1 FROM letture_eventi e WHERE e.tenant_id=d.tenant_id AND e.fascicolo_id=d.fascicolo_id AND e.stato IN ('pending','running')) ORDER BY d.aggiornata_il DESC,d.fascicolo_id,d.chiave LIMIT ? OFFSET ?",(tenant,size,offset)).fetchall()
        total = int(summary['n'])
        return {'voci':[{**json.loads(r['payload_json']), 'fascicoloId': r['fascicolo_id'],
                         'codice': r['codice'], 'chiave': r['chiave'], 'revisione':r['revisione']}
                        for r in rows],
                'lettureInCorso':conteggi.get('in_corso', 0), 'lettureInCoda':conteggi.get('in_coda', 0),
                'totale':total,'pagina':max(1,int(page)),
                'altre':offset+len(rows)<total,'revisione':_revision([total,summary['ultimo']])}
