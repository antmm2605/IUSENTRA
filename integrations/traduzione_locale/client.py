"""Client del traduttore open source su socket Unix; nessun servizio cloud."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import socket
from collections import Counter
from pathlib import Path

MODEL = {
    "modello": "tencent/Hy-MT2-7B-GGUF", "revisione": "ab8472660ac61fac25f1af43fac2599d52a8a775",
    "sha256_modello": "9f96256500f3fc1ab4d64336b58f52a949a95ad7516b0c229476eef782f9f77b",
    "motore": "llama.cpp b12020 · Q4_K_M", "licenza": "Apache-2.0", "destinazione": "it",
}
MODEL["motore"] += " · protocollo " + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
ALIAS = "iusentra-traduzione-hymt2-7b-9f962565"
LANGUAGES = frozenset(["zh", "en", "fr", "pt", "es", "ja", "tr", "ru", "ar", "ko", "th", "de", "vi", "ms", "id", "tl", "hi", "zh-hant", "pl", "cs", "nl", "km", "my", "fa", "gu", "ur", "te", "mr", "he", "bn", "ta", "uk", "bo", "kk", "mn", "ug", "yue"])


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def segmenti(text, *, maximum=650):
    if not text.strip():
        raise ValueError("Testo da tradurre assente.")
    result=[]
    start=0
    while start<len(text):
        end=min(len(text),start+maximum)
        if end<len(text):
            candidates=[m.end() for m in re.finditer(r"[.!?;:]\s+|\n+",text[start:end]) if m.end()>=maximum//3]
            if candidates:
                end=start+candidates[-1]
            else:
                whitespace=[m.end() for m in re.finditer(r"\s+",text[start:end])]
                if whitespace:
                    end=start+whitespace[-1]
        result.append({"inizio":start,"fine":end,"sha256":digest(text[start:end])})
        start=end
    return result


REFERENCES = re.compile(r"(?<![\w])(?:ECLI:[A-Z0-9:._-]+|[CTF][\-\u2011\u2013]\d+/\d+(?:[\s\u00a0]P)?|\d{2,4}/\d{1,4}/(?:UE|EU|CE|EC|CEE|EEC)|TUE|TFUE|TEU|TFEU|CEDH|CEDU)(?![\w])")


def protect_references(text):
    prefix='ZXQREF'
    while prefix in text:
        prefix='X'+prefix
    replacements={}
    def replace(match):
        token=prefix+str(len(replacements)+1).zfill(4)+'ZXQ'
        replacements[token]=match.group(0)
        return token
    return REFERENCES.sub(replace,text),replacements


def restore_references(text,replacements):
    for token,original in replacements.items():
        if text.count(token)!=1:
            raise ValueError("Riferimenti originali non preservati dal traduttore.")
    for token,original in replacements.items():
        text=text.replace(token,original)
    return text


class UnixConnection(http.client.HTTPConnection):
    def __init__(self,path):
        super().__init__("localhost",timeout=120)
        self.path=path
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def call(config,method,path,payload=None):
    location=str(config.get("IUSENTRA_TRANSLATION_SOCKET") or os.environ.get("IUSENTRA_TRANSLATION_SOCKET") or "/data/runtime/traduzione/motore.sock")
    if not Path(location).is_absolute():
        raise ValueError("Servizio locale non configurato.")
    connection=UnixConnection(location)
    try:
        body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
        connection.request(method,path,body,{"Content-Type":"application/json"})
        response=connection.getresponse()
        raw=response.read(8*1024*1024+1)
        if response.status!=200 or len(raw)>8*1024*1024:
            raise ValueError("Servizio locale di traduzione non disponibile.")
        try:
            result=json.loads(raw)
        except (ValueError,TypeError) as exc:
            raise ValueError("Risposta del traduttore non leggibile.") from exc
        if not isinstance(result,dict):
            raise ValueError("Risposta del traduttore non valida.")  # noqa: TRY004 - errore del protocollo remoto, non tipo di un argomento Python
        return result
    finally:
        connection.close()


def rpc(config,action,payload):
    if payload.get('lingua') not in LANGUAGES:
        raise ValueError("Lingua non disponibile nel traduttore locale.")
    models=call(config,'GET','/v1/models')
    if [row.get('id') for row in models.get('data',[])] != [ALIAS]:
        raise ValueError("Identità del traduttore locale non riscontrata.")
    text=payload['testo']
    if action=='prepara':
        return {**MODEL,"sha256_originale":digest(text),"segmenti":segmenti(text)}
    if action!='traduci' or payload.get('sha256_modello')!=MODEL['sha256_modello']:
        raise ValueError("Modello di traduzione diverso da quello richiesto.")
    if len(text)>650:
        raise ValueError("Passaggio oltre il limite: nessun troncamento automatico.")
    protected,replacements=protect_references(text)
    prompt="Translate the following text into Italian. Note that you should only output the translated result without any additional explanation. Preserve reference tokens containing ZXQREF exactly, without changing or omitting any token:\n"+protected
    response=call(config,'POST','/v1/chat/completions',{
        "model":ALIAS,"messages":[{"role":"user","content":prompt}],"temperature":0,
        "seed":42,"max_tokens":2048,"stream":False})
    choices=response.get('choices') or []
    if len(choices)!=1 or choices[0].get('finish_reason')!='stop':
        raise ValueError("Traduzione non completa: limite o interruzione del motore.")
    translated=choices[0].get('message',{}).get('content')
    if not isinstance(translated,str) or not translated.strip() or '<think>' in translated:
        raise ValueError("Risposta di traduzione non utilizzabile.")
    translated=restore_references(translated.strip(),replacements)
    if Counter(REFERENCES.findall(text)) != Counter(REFERENCES.findall(translated)):
        raise ValueError("Identificativi della fonte alterati nella traduzione.")
    warnings=[]
    if Counter(re.findall(r"\d+",text)) != Counter(re.findall(r"\d+",translated)):
        warnings.append("Numeri o riferimenti da confrontare con l'originale.")
    if len(translated)<len(text)*0.35 or len(translated)>len(text)*4:
        warnings.append("Lunghezza della traduzione da confrontare con l'originale.")
    return {**MODEL,"sha256_originale":digest(text),"testo":translated,
            "sha256_traduzione":digest(translated),"avvisi":warnings}
