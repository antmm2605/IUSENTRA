"""Traduzione esplicita e incrementale del corpus già acquisito nello studio."""
from __future__ import annotations

import hashlib
import http.client
import re

from integrations.traduzione_locale.client import LANGUAGES, rpc
from pct.traduzioni_giurisprudenza import TraduzioniCorpus


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def original(owner,sid,language=""):
    record=owner.get_sentenza(int(sid))
    if not record or not str(record.get("testo_integrale") or "").strip():
        raise KeyError("Testo originale non presente nello studio.")
    languages={str(x.get("lingua") or "").lower() for x in record.get("documenti",[]) if x.get("valido",True)}
    if language and (language not in LANGUAGES or language not in languages):
        raise ValueError("Lingua non riscontrata nei documenti conservati.")
    return record,str(record["testo_integrale"])


def status(owner,sid,identity):
    if not re.fullmatch(r"[0-9a-f]{32}",identity):
        raise KeyError("Traduzione non trovata.")
    job=TraduzioniCorpus(owner.db_path).get(int(sid),identity)
    _record,text=original(owner,sid)
    if digest(text)!=job['source_sha256']:
        raise ValueError("La fonte è cambiata: questa traduzione appartiene alla versione precedente.")
    return {"ok":True,"id":job['id'],"stato":job['stato'],"completati":job['completati'],"totale":job['totale'],"avvisi":job['avvisi'],"errore":job['errore'],"modello":job['modello'],"revisione":job['revisione'],"lettore":f"/giurisprudenza/corpus/{sid}/traduzioni/{job['id']}" if job['stato']=='completa' else ""}


def start(owner,config,sid,language,*,retry=False):
    _record,text=original(owner,sid,language)
    sha=digest(text)
    repository=TraduzioniCorpus(owner.db_path)
    previous=repository.existing(int(sid),sha,language)
    if previous and (previous['stato']!='errore' or not retry):
        return status(owner,sid,previous['id'])
    prepared=None if previous else rpc(config,"prepara",{"testo":text,"lingua":language})
    if prepared:
        parts=prepared.get('segmenti') or []
        if prepared.get('sha256_originale')!=sha or not parts or parts[0]['inizio']!=0 or parts[-1]['fine']!=len(text):
            raise ValueError("Inventario della traduzione non riscontrato.")
        last=0
        for part in parts:
            if part['inizio']!=last or part['fine']<=last or digest(text[last:part['fine']])!=part['sha256']:
                raise ValueError("Segmenti non corrispondenti all'originale.")
            last=part['fine']
    identity=repository.begin(int(sid),sha,language,prepared,retry=retry)
    return status(owner,sid,identity)


def step(owner,config,sid,identity):
    repository=TraduzioniCorpus(owner.db_path)
    job=repository.get(int(sid),identity)
    _record,text=original(owner,sid,job['source_language'])
    if digest(text)!=job['source_sha256']:
        repository.fail(int(sid),identity,'fonte_modificata')
        raise ValueError("La fonte originale è cambiata durante la traduzione.")
    part=repository.claim(int(sid),identity)
    if part:
        try:
            source=text[part['inizio']:part['fine']]
            if digest(source)!=part['source_sha256']:
                raise ValueError("Segmento originale non verificato.")
            translated=rpc(config,"traduci",{"testo":source,"lingua":job['source_language'],"sha256_modello":job['sha256_modello']})
            if not str(translated.get('testo') or '').strip() or digest(translated['testo'])!=translated.get('sha256_traduzione'):
                raise ValueError("Integrità della traduzione non riscontrata.")
            _record,current=original(owner,sid)
            if digest(current)!=job['source_sha256']:
                raise ValueError("Fonte modificata durante la traduzione.")
            repository.complete(int(sid),identity,part,translated)
        except (ValueError,OSError,RuntimeError,http.client.HTTPException):
            repository.fail(int(sid),identity,'traduzione_interrotta')
            raise ValueError("Traduzione interrotta. I segmenti già completati sono conservati; puoi riprendere esplicitamente.") from None
    return status(owner,sid,identity)


def document(owner,sid,identity):
    status(owner,sid,identity)
    job=TraduzioniCorpus(owner.db_path).get(int(sid),identity,segments=True)
    if job['stato']!='completa' or job['completati']!=job['totale']:
        raise ValueError("Traduzione non completa.")
    record,text=original(owner,sid)
    parts=[]
    for row in job['segmenti']:
        source=text[row['inizio']:row['fine']]
        if digest(source)!=row['source_sha256'] or digest(row['testo_tradotto'])!=row['output_sha256']:
            raise ValueError("Integrità della traduzione non riscontrata.")
        parts.append({"originale":source,"traduzione":row['testo_tradotto'],"avviso":row['avviso']})
    return {"titolo":record.get('titolo') or 'Provvedimento conservato',"parti":parts,
            "modello":job['modello'],"revisione":job['revisione'],"motore":job['motore'],
            "source_sha256":job['source_sha256'],"source_language":job['source_language'],
            "avvisi":job['avvisi'],"originale_url":f"/giurisprudenza/corpus/{sid}/testo?embed=source"}
