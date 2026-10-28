import hashlib,io,re,zipfile
from types import SimpleNamespace
import pytest
import requests
from lex.normativa.trasferimento import riprendi_download_zip


class Risposta:
    def __init__(self,body,status=206,headers=None):
        self.body=body;self.status_code=status;self.headers=headers or {}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def raise_for_status(self):
        if self.status_code>=400:
            raise requests.HTTPError(response=self)
    def iter_content(self,chunk_size):yield self.body


class Sessione:
    def __init__(self,payload,status=206):self.payload=payload;self.status=status;self.calls=0
    def get(self,url,*,headers,timeout,stream,allow_redirects):
        self.calls+=1
        assert allow_redirects is False
        start,end=map(int,re.fullmatch(r"bytes=(\d+)-(\d+)",headers["Range"]).groups())
        return Risposta(self.payload[start:end+1],self.status,{"Content-Range":f"bytes {start}-{end}/{len(self.payload)}"})


def archivio():
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",zipfile.ZIP_STORED) as z:z.writestr("atto.xml",b"<atto>testo ufficiale</atto>"*100)
    return b.getvalue()


def originale():
    return SimpleNamespace(url="https://api.normattiva.it/t/normattiva.api/file-download/v1/download/risorsa",headers={"accept-ranges":"bytes"})


def test_ripresa_preserva_byte_e_verifica_crc(tmp_path):
    data=archivio();p=tmp_path/"fonte.zip.part";p.write_bytes(data[:len(data)//2])
    result=riprendi_download_zip(Sessione(data),originale(),p,timeout=1)
    assert p.read_bytes()==data
    assert result["stato"]=="completato_crc_integrale"
    assert result["sha256"]==hashlib.sha256(data).hexdigest()
    assert result["validatore_forte"] is False


@pytest.mark.parametrize("status",[200,302,403,429])
def test_range_ignorato_o_negato_non_sovrascrive_parziale(tmp_path,status):
    data=archivio();p=tmp_path/"fonte.zip.part";before=data[:len(data)//2];p.write_bytes(before);session=Sessione(data,status)
    with pytest.raises((ValueError,requests.HTTPError)):riprendi_download_zip(session,originale(),p,timeout=1)
    assert p.read_bytes()==before
    assert session.calls==1


def test_parziale_altra_rappresentazione_non_promosso(tmp_path):
    data=archivio();p=tmp_path/"fonte.zip.part";before=b"altro"+data[5:len(data)//2];p.write_bytes(before)
    with pytest.raises(ValueError,match="altra rappresentazione"):
        riprendi_download_zip(Sessione(data),originale(),p,timeout=1)
    assert p.read_bytes()==before


def test_crc_non_valido_blocca_promozione(tmp_path):
    data=bytearray(archivio());data[60]^=1;data=bytes(data);p=tmp_path/"fonte.zip.part";p.write_bytes(data[:len(data)//2])
    with pytest.raises(ValueError,match="CRC integrale"):riprendi_download_zip(Sessione(data),originale(),p,timeout=1)
    assert p.exists()
    assert not (tmp_path/"fonte.zip").exists()


def test_get_pubblica_tentativi_connessione_finiti(monkeypatch):
    from lex.normativa.normattiva_client import NormattivaClient
    monkeypatch.setattr("lex.normativa.normattiva_client.time.sleep",lambda _:None)
    calls=[]
    def timeout(*args,**kwargs):
        calls.append(1)
        raise requests.Timeout("rete")
    client=NormattivaClient(session=SimpleNamespace(headers={},get=timeout))
    with pytest.raises(requests.Timeout):
        client._get_public_download("https://api.normattiva.it/risorsa")
    assert len(calls)==2


@pytest.mark.parametrize("status",[403,429])
def test_get_negata_non_viene_ritentata(monkeypatch,status):
    from lex.normativa.normattiva_client import NormattivaClient
    calls=[]
    def denied(*args,**kwargs):
        calls.append(1)
        return Risposta(b"",status)
    client=NormattivaClient(session=SimpleNamespace(headers={},get=denied))
    response=client._get_public_download("https://api.normattiva.it/risorsa")
    with pytest.raises(requests.HTTPError):response.raise_for_status()
    assert len(calls)==1