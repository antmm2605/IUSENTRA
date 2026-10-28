"""Ripresa dello stesso ZIP ufficiale: Range, confronti e CRC integrale."""
from pathlib import Path
import hashlib,json,re,time,zipfile
from urllib.parse import urlsplit
import requests


def riprendi_download_zip(session,response,partial: Path,*,timeout: int) -> dict:
    url=response.url;parsed=urlsplit(url)
    if parsed.scheme!="https" or parsed.hostname!="api.normattiva.it":
        raise ValueError("Ripresa ammessa solo sulla stessa risorsa Normattiva HTTPS")
    if response.headers.get("accept-ranges","").lower()!="bytes" or response.headers.get("content-encoding","identity").lower()!="identity":
        raise ValueError("Ripresa per byte non dichiarata dalla fonte")
    size=partial.stat().st_size
    if size<1:raise ValueError("Nessun parziale da riscontrare")
    etag=response.headers.get("etag","");strong=bool(etag and not etag.startswith("W/"))
    receipt={"url":url,"bytes_prima":size,"validatore_forte":strong,"etag":etag,"intervalli":[],"errori_rete":0,"stato":"in_corso"}
    path=partial.with_suffix(partial.suffix+".range.json")
    def save():
        tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(receipt,indent=2));tmp.replace(path)
    def fetch(start,end,total=None):
        while True:
            headers={"Range":f"bytes={start}-{end}","Accept-Encoding":"identity"}
            if strong:headers["If-Range"]=etag
            try:
                with session.get(url,headers=headers,timeout=timeout,stream=True,allow_redirects=False) as r:
                    r.raise_for_status()
                    m=re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)",r.headers.get("Content-Range",""))
                    if r.status_code!=206 or not m or (int(m[1]),int(m[2]))!=(start,end):
                        raise ValueError("Intervallo HTTP non rispettato: parziale conservato")
                    if r.headers.get("content-encoding","identity").lower()!="identity":raise ValueError("Codifica byte non coerente")
                    if strong and r.headers.get("etag") not in (None,etag):raise ValueError("ETag cambiato")
                    full=int(m[3]);body=bytearray()
                    if total is not None and full!=total:raise ValueError("Dimensione della fonte variata")
                    for chunk in r.iter_content(chunk_size=256*1024):
                        body.extend(chunk)
                        if len(body)>end-start+1:raise ValueError("Intervallo oltre il limite")
                    if len(body)!=end-start+1:raise ValueError("Intervallo incompleto")
                    receipt["intervalli"].append({"dal":start,"al":end,"totale":full,"sha256":hashlib.sha256(body).hexdigest()});save()
                    return body,full
            except (requests.ConnectionError,requests.Timeout,requests.exceptions.ChunkedEncodingError):
                receipt["errori_rete"]+=1;save()
                if receipt["errori_rete"]>=3:raise
                time.sleep(2)
    try:
        _head,total=fetch(0,0)
        if total<=size:raise ValueError("Totale non coerente con un download interrotto")
        window=min(65536,size)
        official=hashlib.sha256()
        with partial.open("rb") as f:
            if strong:
                while data:=f.read(1024*1024):official.update(data)
                for start in sorted({0,max(0,size//2-window//2),size-window}):
                    data,_=fetch(start,start+window-1,total);f.seek(start)
                    if f.read(window)!=data:raise ValueError("Parziale di altra rappresentazione")
            else:
                # Senza ETag forte i soli campioni non attestano tutti i byte:
                # confrontare il prefisso intero col medesimo flusso ufficiale.
                for start in range(0,size,16*1024*1024):
                    end=min(start+16*1024*1024,size)-1;data,_=fetch(start,end,total);f.seek(start)
                    if f.read(len(data))!=data:raise ValueError("Parziale di altra rappresentazione")
                    official.update(data)
        with partial.open("ab") as f:
            for start in range(size,total,16*1024*1024):
                end=min(start+16*1024*1024,total)-1;data,_=fetch(start,end,total)
                f.write(data);f.flush();official.update(data)
        with partial.open("rb") as f:
            for start in [0,total-window]:
                data,_=fetch(start,start+window-1,total);f.seek(start)
                if f.read(window)!=data:raise ValueError("Fonte variata durante trasferimento")
        with zipfile.ZipFile(partial) as z:
            bad=z.testzip()
            if bad is not None:raise ValueError("CRC integrale discordante: "+bad)
        with partial.open("rb") as f:digest=hashlib.file_digest(f,"sha256").hexdigest()
        if official.hexdigest()!=digest:raise ValueError("SHA del flusso ufficiale discordante dalla copia")
        receipt.update(stato="completato_crc_integrale",bytes_finali=total,sha256=digest,
                       sha256_flusso_ufficiale=official.hexdigest(),prefisso_intero_riscontrato=not strong);save()
        return receipt
    except Exception as exc:
        receipt.update(stato="interrotto_parziale_conservato",errore=type(exc).__name__+": "+str(exc)[:500]);save();raise
