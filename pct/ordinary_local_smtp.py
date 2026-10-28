"""Comandi SMTP locali nella stessa base SQL della casella ordinaria.

Il comando è consumato una sola volta prima di consegnare il payload al PC.
Un esito mancante non viene ritentato automaticamente.
"""
from __future__ import annotations
import base64
import hashlib
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from werkzeug.utils import secure_filename
from pct.email_client import EmailRicevuta

MAX_BYTES = 100 * 1024 * 1024
DDL = (
    '''CREATE TABLE IF NOT EXISTS ordinary_local_smtp_commands (
       tenant_key TEXT NOT NULL, command_id TEXT NOT NULL, actor_key TEXT NOT NULL,
       state TEXT NOT NULL, sender TEXT NOT NULL, recipients TEXT NOT NULL,
       subject TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
       smtp_message_id TEXT NOT NULL DEFAULT '', confirmed_at TEXT NOT NULL DEFAULT '',
       PRIMARY KEY (tenant_key,command_id))''',
    '''CREATE TABLE IF NOT EXISTS ordinary_local_smtp_attachments (
       tenant_key TEXT NOT NULL, command_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
       filename TEXT NOT NULL, relative_path TEXT NOT NULL, sha256 TEXT NOT NULL,
       size_bytes INTEGER NOT NULL, mime_type TEXT NOT NULL,
       PRIMARY KEY (tenant_key,command_id,ordinal),
       FOREIGN KEY (tenant_key,command_id) REFERENCES ordinary_local_smtp_commands(tenant_key,command_id))''',
)

class LocalSmtpConflict(ValueError):
    pass

class LocalSmtpCommands:
    def __init__(self, mailbox, actor):
        self.mailbox = mailbox
        self.repo = getattr(mailbox, 'repository', None)
        if self.repo is None or self.repo.kind != 'ordinary':
            raise ValueError('Invio locale richiede la casella SQL dello studio.')
        self.actor = str(actor)
        if not self.actor:
            raise ValueError('Utente non disponibile.')
        conn = self.repo._write_conn()
        try:
            for sql in DDL:
                conn.execute(sql)
            self.repo._finish(conn)
        except Exception:
            self.repo._finish(conn, rollback=True)
            raise

    def _key(self, command):
        if not re.fullmatch(r'[a-f0-9]{32}', str(command)):
            raise ValueError('Comando di invio non valido. Riapri la composizione.')
        return (self.repo.tenant, str(command))

    def prepare(self, command, *, sender, recipients, subject, body, uploads):
        key = self._key(command)
        conn = self.repo._write_conn()
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            inserted = conn.execute('INSERT INTO ordinary_local_smtp_commands '
                '(tenant_key,command_id,actor_key,state,sender,recipients,subject,body,created_at) '
                "VALUES (?,?,?,'dispatching',?,?,?,?,?) ON CONFLICT(tenant_key,command_id) DO NOTHING RETURNING command_id",
                (*key,self.actor,sender,recipients,subject,body,stamp)).fetchone()
            if inserted is None:
                raise LocalSmtpConflict('Questo invio è già stato avviato. Verifica l’esito; non verrà rispedito automaticamente.')
            attachments = []
            total = 0
            root = self.mailbox.attachments_dir.resolve()
            for ordinal, upload in enumerate(uploads):
                filename = secure_filename(upload.filename or '') or 'allegato'
                content = upload.stream.read(MAX_BYTES - total + 1)
                total += len(content)
                if total > MAX_BYTES:
                    raise ValueError('Allegati oltre il limite di 100 MiB: nessuna email inviata.')
                rel = Path('local-outbox') / command / f'{ordinal}-{filename}'
                target = (root / rel).resolve()
                target.relative_to(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as out:
                    out.write(content)
                mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                digest = hashlib.sha256(content).hexdigest()
                conn.execute('INSERT INTO ordinary_local_smtp_attachments '
                    '(tenant_key,command_id,ordinal,filename,relative_path,sha256,size_bytes,mime_type) VALUES (?,?,?,?,?,?,?,?)',
                    (*key,ordinal,filename,rel.as_posix(),digest,len(content),mime))
                attachments.append({'filename':filename,'content_base64':base64.b64encode(content).decode('ascii'),'mime_type':mime})
            self.repo._finish(conn)
            return {'from':sender,'to':recipients,'subject':subject,'body':body,'attachments':attachments}
        except Exception:
            self.repo._finish(conn, rollback=True)
            raise

    def confirm(self, command, *, message_id):
        key = self._key(command)
        if not message_id or len(message_id)>998 or '\r' in message_id or '\n' in message_id:
            raise ValueError('Conferma SMTP priva di Message-ID valido.')
        conn = self.repo._write_conn()
        try:
            row = conn.execute('UPDATE ordinary_local_smtp_commands SET state=state '
                "WHERE tenant_key=? AND command_id=? AND actor_key=? AND state IN ('dispatching','sent') "
                'RETURNING state,sender,recipients,subject,body,created_at,smtp_message_id',(*key,self.actor)).fetchone()
            if row is None:
                raise LocalSmtpConflict('Comando non disponibile per questo utente e studio.')
            if row[0] == 'sent':
                if row[6] != message_id:
                    raise LocalSmtpConflict('Conferma diversa da quella già registrata.')
                self.repo._finish(conn)
                return
            stamp = datetime.now(timezone.utc).isoformat()
            attachments=[]
            for a in conn.execute('SELECT filename,relative_path,sha256,size_bytes,mime_type FROM ordinary_local_smtp_attachments '
                                  'WHERE tenant_key=? AND command_id=? ORDER BY ordinal',key).fetchall():
                attachments.append({'nome':a[0],'percorso_rel':a[1],'sha256':a[2],'size':a[3],'mime':a[4]})
            msg = EmailRicevuta(id='INVIATA:LOCAL:'+command,cartella='INVIATI',stato='LETTA',
                mittente=row[1],destinatari=row[2],oggetto=row[3],corpo_testo=row[4],data=stamp,
                message_id=message_id,origine='INVIATA',allegati=attachments,ricevuta_il=stamp)
            self.repo._insert(conn,msg.id,msg.to_dict(),stamp)
            self.repo._audit(conn,msg.id,'local_smtp_confirmed',self.actor,list(msg.to_dict()),stamp)
            conn.execute("UPDATE ordinary_local_smtp_commands SET state='sent',smtp_message_id=?,confirmed_at=? WHERE tenant_key=? AND command_id=?",
                         (message_id,stamp,*key))
            self.repo._finish(conn)
        except Exception:
            self.repo._finish(conn,rollback=True)
            raise
