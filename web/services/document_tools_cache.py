"""Cache cifrata delle copie appena generate, mai archivio del fascicolo.

Nessuna tabella di dominio: è un artefatto temporaneo rigenerabile, isolato
per tenant e utente e valido un'ora su entrambi i backend SQL del prodotto.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import re
import time
import uuid

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from web.services.document_tools import DocumentToolError
from web.services.registro_letture_runtime import tenant_corrente, utente_corrente_id, percorso_registro

TTL = 3600
MAX_CACHE_BYTES = 512 * 1024 * 1024
MAX_CACHE_FILES = 20


def _context():
    tenant, user = tenant_corrente(), utente_corrente_id()
    if not tenant or tenant in {'default', 'single-studio'} or not user:
        raise DocumentToolError("Studio e utente obbligatori per consultare la copia generata.")
    tenant_hash = hashlib.sha256(tenant.encode()).hexdigest()
    user_hash = hashlib.sha256(user.encode()).hexdigest()
    secret = current_app.secret_key
    if not secret:
        raise DocumentToolError("La protezione delle copie temporanee non è configurata.")
    secret_bytes = secret.encode() if isinstance(secret,str) else bytes(secret)
    key = base64.urlsafe_b64encode(hashlib.sha256(b'iusentra-document-tools-cache:' + secret_bytes).digest())
    return tenant_hash, user_hash, URLSafeTimedSerializer(secret,salt='iusentra-document-tools-results'), Fernet(key)


def _root(tenant_hash):
    configured = current_app.config.get('DOCUMENT_TOOLS_CACHE_ROOT')
    base = Path(configured) if configured else Path(percorso_registro()).resolve().parent/'copie_temporanee_strumenti'
    return base/tenant_hash


def store_result(data: bytes, filename: str, mimetype: str) -> str:
    tenant_hash,user_hash,signer,cipher = _context()
    root = _root(tenant_hash)
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    now = time.time()
    active = []
    # Solo la cache dedicata del tenant, massimo venti artefatti. Nessuna
    # scansione di documenti, mirror SQL/JSON, OCR o indici applicativi.
    for path in root.glob('*.cache'):
        if not re.fullmatch(r'[a-f0-9]{32}\.cache',path.name):
            continue
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        if now-stat.st_mtime > TTL:
            path.unlink(missing_ok=True)
        else:
            active.append(stat.st_size)
    if len(active) >= MAX_CACHE_FILES or sum(active)+len(data)*1.4 > MAX_CACHE_BYTES:
        raise DocumentToolError("La cache delle copie generate è piena. Le copie scadono dopo un’ora; riprova più tardi.")
    identifier = uuid.uuid4().hex
    path = root/(identifier+'.cache')
    encrypted = cipher.encrypt(data)
    with path.open('xb') as output:
        output.write(encrypted)
    path.chmod(0o600)
    return signer.dumps({'id':identifier,'tenant':tenant_hash,'user':user_hash,'filename':filename,'mime':mimetype,'sha256':hashlib.sha256(data).hexdigest()})


def read_result(token: str) -> tuple[bytes,str,str]:
    tenant_hash,user_hash,signer,cipher = _context()
    try:
        payload = signer.loads(token,max_age=TTL)
        identifier = payload['id']
        if payload['tenant'] != tenant_hash or payload['user'] != user_hash or not re.fullmatch(r'[a-f0-9]{32}',identifier):
            raise BadSignature('Contesto diverso')
        data = cipher.decrypt((_root(tenant_hash)/(identifier+'.cache')).read_bytes(),ttl=TTL)
        if hashlib.sha256(data).hexdigest() != payload['sha256']:
            raise InvalidToken()
        return data,str(payload['filename']),str(payload['mime'])
    except SignatureExpired:
        raise DocumentToolError("La copia temporanea è scaduta. Genera di nuovo il documento; gli originali sono conservati.") from None
    except FileNotFoundError:
        raise DocumentToolError("La copia temporanea non è più disponibile. Genera di nuovo il documento; gli originali sono conservati.") from None
    except (BadSignature,InvalidToken,KeyError,TypeError,ValueError):
        raise DocumentToolError("La copia temporanea non è disponibile per questo utente e studio.") from None
