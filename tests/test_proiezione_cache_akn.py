"""La rettifica di una parte non elimina le disposizioni integrali dello stesso atto."""
import hashlib,json,sqlite3,sys,zipfile
from pathlib import Path
import pytest
from tests.test_normativa_akn_trasporto import XML
from lex.normativa.normattiva_importer import ensure_schema
from lex.normativa.versioni_akn import importa_multiversione,impronta_lettore
from tools.proietta_cache_akn import main


def preparazione(tmp_path,monkeypatch,*,tutto_abrogato=False):
    for key in ('PCT_NORMATTIVA_LETTORI_MANIFEST','PCT_NORMATTIVA_LETTORI_MANIFEST_SHA256'):
        monkeypatch.delenv(key,raising=False)
    original=XML.split(b'<attachments>')[0]+b'</act></akomaNtoso>'
    original=original.replace(b'</article></body>',b'</article><article><num>Art. 2.</num><paragraph><content><p>Disciplina seconda effettiva.</p></content></paragraph></article></body>')
    current=original.replace(b'Disciplina seconda effettiva.',b'ARTICOLO ABROGATO')
    if tutto_abrogato:current=current.replace(b'Corpo principale integrale.',b'ARTICOLO ABROGATO')
    archive=tmp_path/'fonte.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('LEGGE_20200101_1/2020-01-01_20G00001_ORIGINALE_V0.xml',original)
        z.writestr('LEGGE_20200101_1/2020-01-01_20G00001_VIGENZA_2020-01-02_V1.xml',current)
    cache=tmp_path/'versioni.sqlite'
    with sqlite3.connect(cache) as c:
        imported=importa_multiversione(c,archivio=archive,sha256_atteso=hashlib.sha256(archive.read_bytes()).hexdigest(),acquisita_utc='2026-10-26T10:00:00+00:00')
        assert imported['errori']==[] and imported['versioni_importate']==2
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
    gate=tmp_path/'gate.json'
    gate.write_text(json.dumps({'importazione_manifest_terminata':True,'integrity_check':'ok','foreign_key_check_ok':True,'lettore_sha256':impronta_lettore(),'sha256_db_finale':hashlib.sha256(cache.read_bytes()).hexdigest()}))
    target=tmp_path/'normattiva.sqlite'
    with sqlite3.connect(target) as c:ensure_schema(c)
    report=tmp_path/'rapporto.json'
    argv=['proietta_cache_akn','--repo',str(Path(__file__).resolve().parents[1]),'--versioni',str(cache),'--candidato',str(target),'--archivi',str(tmp_path),'--rapporto',str(report),'--stato-importazione',str(gate),'--data','2020-01-03']
    monkeypatch.setattr(sys,'argv',argv)
    return target,cache,report,gate


def test_proiezione_reale_mantiene_articolo_integrale_e_segnala_solo_avviso(tmp_path,monkeypatch):
    from lex.normativa.consultazione import dettaglio
    from web.services.normative_article_reader import risolvi
    target,cache,report,_=preparazione(tmp_path,monkeypatch)
    before=hashlib.sha256(cache.read_bytes()).hexdigest()
    main()
    result=json.loads(report.read_text())
    assert result['stato']=='proiezione_terminata' and result['documenti']==1
    assert result['articoli_senza_corpo_nell_edizione']==1
    with sqlite3.connect(target) as c:
        rows=c.execute('SELECT id,article_number,article_text FROM normative_articles ORDER BY id').fetchall()
        assert len(rows)==2
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
    first,second=rows
    a=dettaglio(target,first[0],includi_archivio_generale=True)
    b=dettaglio(target,second[0],includi_archivio_generale=True)
    assert a['only_heading'] is False and 'Corpo principale integrale.' in a['text']
    assert b['only_heading'] is True and 'ARTICOLO ABROGATO' in b['text']
    assert risolvi(target,ident=first[0])['text']==a['text']
    with pytest.raises(LookupError):risolvi(target,ident=second[0])
    assert hashlib.sha256(cache.read_bytes()).hexdigest()==before


def test_edizione_composta_solo_da_avvisi_non_diventa_fonte_integrale(tmp_path,monkeypatch):
    target,cache,report,_=preparazione(tmp_path,monkeypatch,tutto_abrogato=True)
    main()
    result=json.loads(report.read_text())
    assert result['documenti']==0 and result['edizioni_senza_testo_integrale']==1
    with sqlite3.connect(target) as c:assert c.execute('SELECT count(*) FROM normative_documents').fetchone()[0]==0
    with sqlite3.connect(cache) as c:assert c.execute('SELECT count(*) FROM normative_akn_editions').fetchone()[0]==2


def test_sha_cache_discordante_non_scrive_nel_catalogo(tmp_path,monkeypatch):
    target,_,report,gate=preparazione(tmp_path,monkeypatch)
    payload=json.loads(gate.read_text());payload['sha256_db_finale']='0'*64;gate.write_text(json.dumps(payload))
    before=hashlib.sha256(target.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='Cache sorgente diversa'):main()
    assert hashlib.sha256(target.read_bytes()).hexdigest()==before and not report.exists()
