"""Derivato tecnico per un suffisso omesso nei soli metadati NIR.

Non corregge gli XML originali e non equivale a una nuova esportazione ufficiale.
Richiede il medesimo suffisso nell'intestazione XML e nel catalogo ufficiale,
oltre a data, tipo, numero base e identita ELI/GU concordanti. Il corpo normativo
canonico deve restare byte per byte identico. La citazione pubblica resta ELI/GU,
non l'URN ricostruito internamente per il lettore. Nessun chiamante HTTP/AI.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
import hashlib,json,re
from lxml import etree
from lex.normativa.normattiva_akn_importer import decodifica_xml_akn
NS={'a':'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'}
SUFFISSI=frozenset(('bis','ter','quater','quinquies','sexies','septies','octies','novies','decies','undecies','duodecies','terdecies','quaterdecies','quindecies','sexdecies','septdecies','duodevicies','undevicies','vicies'))
@dataclass(frozen=True)
class DerivatoIdentita:
    xml:bytes
    prova:dict

def _numero(value):
    if not isinstance(value,str):raise ValueError('Numero non testuale')
    return re.sub(r'\s+','',re.sub(r'^n[.]?\s*','',value.strip(),flags=re.I)).strip('.').casefold()

def _numero_alfanumerico(value):
    """Numero dell'atto, mai numero di articolo o posizione nel codice."""
    value=_numero(value)
    decimal=re.fullmatch(r'(\d+)-?([a-z]+)',value)
    if decimal and decimal[2] in SUFFISSI:return str(int(decimal[1]))+decimal[2],str(int(decimal[1]))
    series=re.fullmatch(r'(\d+)/([a-z]{1,3})',value)
    if series:return str(int(series[1]))+'/'+series[2],str(int(series[1]))
    suffixes='|'.join(sorted(SUFFISSI,key=len,reverse=True))
    roman=re.fullmatch(r'([ivxlcdm]+)-?('+suffixes+r')',value)
    if roman:
        number=roman[1].upper()
        if not re.fullmatch(r'M{0,4}(?:CM|CD|D?C{0,4})(?:XC|XL|L?X{0,4})(?:IX|IV|V?I{0,4})',number):return None
        values=[{'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}[x] for x in number]
        total=sum(-v if n+1<len(values) and v<values[n+1] else v for n,v in enumerate(values))
        return str(total)+roman[2],str(total)
    return None


def riscontra_suffisso(xml:bytes,*,xml_sha256:str,catalogo:dict,pagina_catalogo_sha256:str)->DerivatoIdentita:
    if hashlib.sha256(xml).hexdigest()!=xml_sha256 or not re.fullmatch('[0-9a-f]{64}',pagina_catalogo_sha256):raise ValueError('Impronte primarie assenti o discordanti')
    decoded,transport=decodifica_xml_akn(xml)
    root=etree.fromstring(decoded,etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=True))
    acts=root.xpath('./a:act|./a:doc',namespaces=NS)
    if etree.QName(root).localname!='akomaNtoso' or len(acts)!=1:raise ValueError('Documento AKN non univoco')
    act=acts[0];nodes=act.xpath('./a:meta/a:identification/a:FRBRWork/a:FRBRalias',namespaces=NS)
    aliases=[x for x in nodes if str(x.get('value','')).startswith('urn:nir:')]
    if len(aliases)!=1:raise ValueError('Alias NIR non univoco')
    original=aliases[0].get('value');m=re.fullmatch(r'urn:nir:([^:]+):([^:]+):(\d{4}-\d{2}-\d{2});(\d+)',original)
    if not m:raise ValueError('La regola vale solo per un suffisso omesso da numero base numerico')
    work=act.xpath('./a:meta/a:identification/a:FRBRWork/a:FRBRdate/@date',namespaces=NS)
    if work!=[m[3]]:raise ValueError('Data NIR e Work discordanti')
    date.fromisoformat(m[3])
    headers=act.xpath('./a:preface//a:docNumber',namespaces=NS)
    header_texts=[' '.join(n.itertext()).strip() for n in headers]
    numbers={_numero_alfanumerico(n) for n in header_texts}
    expected=_numero_alfanumerico(str(catalogo.get('numeroAttoAlfanumerico') or ''))
    if expected is None or expected[1]!=str(int(m[4])) or numbers!={expected} or len(header_texts)!=1:raise ValueError('Suffisso non riscontrato identico in catalogo e intestazione')
    if str(catalogo.get('dataEmanazione',''))[:10]!=m[3] or str(catalogo.get('numeroAtto',''))!=m[4]:raise ValueError('Data o numero base del catalogo discordanti')
    typ=str(catalogo.get('denominazioneAtto') or '').upper()
    from lex.normativa.identita_documento import TIPI
    types={' '.join(k.replace('-',' ').split()):v for k,v in TIPI.items()}
    types.update({'DECRETO MINISTERIALE':'decreto.ministeriale','DECRETO':'decreto'})
    expected_type=types.get(' '.join(typ.replace('-',' ').split()))
    if expected_type!=m[2]:
        from lex.testi_ufficiali import _varianti_urn
        alternative=f'urn:nir:{m[1]}:{expected_type}:{m[3]};{m[4]}'
        if expected_type is None or alternative not in _varianti_urn(original):raise ValueError('Tipo di atto discordante')
    pub=str(catalogo.get('dataGU') or '');code=str(catalogo.get('codiceRedazionale') or '')
    date.fromisoformat(pub)
    if not re.fullmatch('[0-9A-Z]{4,16}',code) or act.xpath('./a:meta/a:publication/@date',namespaces=NS)!=[pub]:raise ValueError('Pubblicazione GU discordante')
    elis=[x.get('value') for x in nodes if str(x.get('value','')).startswith('eli/')]
    stem='eli/id/'+pub.replace('-','/')+'/'+code+'/'
    if len(elis)!=1 or not elis[0].startswith(stem) or not re.fullmatch(re.escape(stem)+r'(ORIGINAL|CONSOLIDATED/\d{8})',elis[0]):raise ValueError('Identita ELI e GU non concordanti')
    doc_dates=set(act.xpath('./a:preface//a:docDate/@date',namespaces=NS))
    if doc_dates and doc_dates!={m[3]}:raise ValueError('Data nell intestazione discordante')
    def corpo():
        return b''.join(etree.tostring(child,method='c14n') for child in act if isinstance(child.tag,str) and etree.QName(child).localname!='meta')
    before=corpo();descriptor=re.sub(r'\s+','',re.sub(r'^n[.]?\s*','',header_texts[0],flags=re.I)).strip('.')
    resolved=original.rsplit(';',1)[0]+';'+descriptor
    aliases[0].set('value',resolved)
    if corpo()!=before:raise ValueError('Il corpo normativo e cambiato')
    derived=etree.tostring(root,encoding='utf-8',xml_declaration=True)
    evidence={'schema':1,'regola':'suffisso_omesso_solo_metadati_NIR','urn_dichiarato_originale':original,'urn_derivato_interno_non_alias_ufficiale':resolved,'numero_riscontrato':str(catalogo['numeroAttoAlfanumerico']),'identita_citazione':'https://www.gazzettaufficiale.it/eli/id/'+pub.replace('-','/')+'/'+code+'/sg','xml_originale_sha256':xml_sha256,'xml_decodificato_originale_sha256':hashlib.sha256(decoded).hexdigest(),'xml_derivato_sha256':hashlib.sha256(derived).hexdigest(),'corpo_c14n_immutato_sha256':hashlib.sha256(before).hexdigest(),'pagina_catalogo_sha256':pagina_catalogo_sha256,'riga_catalogo_sha256':hashlib.sha256(json.dumps(catalogo,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),'codifica_originale':transport,'originale_non_modificato':True,'non_esportazione_ufficiale_derivata':True,'applicabilita_non_certificata':True}
    return DerivatoIdentita(derived,evidence)


def verifica_riga_pacchetto(directory, riga:dict, *, cache:dict|None=None)->dict:
    """Rilegge le prove del pacchetto offline prima di accettare un ID GU.

    Non basta un dizionario che dichiari di avere un riscontro: XML e pagina
    catalogo devono essere nel pacchetto, con SHA e corpo riproducibili.
    """
    from pathlib import Path
    from lex.normativa.normattiva_akn_importer import parse_akn
    from lex.normativa.biblioteca.fabbisogno import norm_articolo
    cache={} if cache is None else cache
    base_key=('base_identita',str(directory))
    base=cache.get(base_key)
    if base is None:
        base=Path(directory).resolve(strict=True);cache[base_key]=base
    provenance=riga.get('provenienza_integrazione')
    if not isinstance(provenance,dict):raise ValueError('Prove di identita mancanti')
    proof=provenance.get('normalizzazione_identita')
    if not isinstance(proof,dict):raise ValueError('Riscontro di identita mancante')
    def load(name,limit):
        if not isinstance(name,str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Percorso prova non ammesso')
        key=('file_identita',str(base),name)
        stored=cache.get(key)
        if stored is None:
            p=(base/name).resolve(strict=True);stat=p.stat()
            if not p.is_relative_to(base) or stat.st_size>limit:raise ValueError('Prova fuori pacchetto o oltre limite')
            raw=p.read_bytes();signature=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
            after=p.stat()
            if (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)!=signature:raise ValueError('Prova cambiata durante lettura')
            stored=(p,raw,signature)
            files=[k for k in cache if isinstance(k,tuple) and k[0]=='file_identita']
            if len(files)>=8:cache.pop(files[0])
            cache[key]=stored
            stats=cache.setdefault(('stat_identita',),{})
            if str(p) in stats and stats[str(p)]!=signature:raise ValueError('Prova cambiata fra due letture dello stesso import')
            stats[str(p)]=signature
        p,raw,signature=stored;stat=p.stat()
        if stat.st_size>limit or (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)!=signature:raise ValueError('Prova modificata durante preparazione')
        return p,raw
    original_path,raw=load(proof.get('file_xml_originale'),512*1024**2)
    _,page=load(proof.get('file_pagina_catalogo'),8*1024**2)
    if hashlib.sha256(page).hexdigest()!=proof.get('pagina_catalogo_sha256'):raise ValueError('Pagina catalogo alterata')
    pub=re.fullmatch(r'https://www[.]gazzettaufficiale[.]it/eli/id/(\d{4})/(\d{2})/(\d{2})/([0-9A-Z]+)/sg',str(riga.get('urn','')))
    if not pub or riga.get('url')!=riga['urn']:raise ValueError('Identita di pubblicazione GU non univoca')
    gu='-'.join(pub.group(1,2,3));rows=[r for r in json.loads(page).get('listaAtti',[]) if (r.get('dataGU'),r.get('codiceRedazionale'))==(gu,pub[4])]
    if len(rows)!=1:raise ValueError('Atto non univoco nella pagina catalogo')
    def interprete(payload,source_path,entry,expected):
        digest=hashlib.sha256(payload).hexdigest()
        if digest!=expected:raise ValueError('Impronte primarie assenti o discordanti')
        key=('documento_identita',digest,proof['pagina_catalogo_sha256'],entry,riga['urn'])
        stored=cache.get(key)
        if stored is None:
            derived=riscontra_suffisso(payload,xml_sha256=expected,catalogo=rows[0],pagina_catalogo_sha256=proof['pagina_catalogo_sha256'])
            document=parse_akn(derived.xml,zip_path=source_path,entry=entry,collection_name='Riscontro identita GU',analizza_pertinenza=False)
            stored=(derived,document)
            documents=[k for k in cache if isinstance(k,tuple) and k[0]=='documento_identita']
            if len(documents)>=16:cache.pop(documents[0])
            cache[key]=stored
        return stored
    entry=proof.get('xml_entry','')
    derived,doc=interprete(raw,original_path,entry,proof.get('xml_originale_sha256',''))
    if any(proof.get(k)!=v for k,v in derived.prova.items()) or derived.prova['identita_citazione']!=riga['urn']:raise ValueError('Dichiarazione del riscontro alterata')
    if riga.get('data_atto')!=doc.data_atto or riga.get('titolo_atto')!=doc.titolo:raise ValueError('Intestazione del pacchetto diversa dalle fonti')
    part=provenance.get('partizione_xml');locator=provenance.get('localizzatore_xml')
    matches=[a for a in doc.articles if norm_articolo(a.article_number)==norm_articolo(riga.get('articolo','')) and a.partizione==part and a.localizzatore_xml==locator]
    if len(matches)!=1 or matches[0].article_text!=riga.get('testo') or (matches[0].article_title or '')!=(riga.get('rubrica') or '') or matches[0].struttura_normativa!=riga.get('struttura_normativa',[]):raise ValueError('Testo o partizione non coincidono con la fonte primaria')
    label=rows[0]['denominazioneAtto']+' '+rows[0]['numeroAttoAlfanumerico']
    if 'partizione_etichetta' in riga:
        if riga['partizione_etichetta']!=matches[0].partizione:raise ValueError('Etichetta della partizione diversa dall XML')
        loc=riga.get('localizzatore_etichetta') or ''
        if loc and loc!=matches[0].localizzatore_xml:raise ValueError('Etichetta del localizzatore diversa dall XML')
        label+=' ['+matches[0].partizione+(' '+loc if loc else '')+']'
    if riga.get('atto')!=label:raise ValueError('Etichetta dell atto diversa dalle fonti')
    if provenance.get('sha256_payload_ufficiale')!=derived.prova['xml_originale_sha256']:raise ValueError('SHA della fonte originale discordante')
    start=re.search(r'_VIGENZA_(\d{4}-\d{2}-\d{2})_V',entry)
    start=start[1] if start else doc.redazione_id
    if provenance.get('versione_formale_dal')!=start or riga.get('consolidato_al')!=start or provenance.get('vigenza_richiesta')!=start:raise ValueError('Edizione dichiarata diversa dal fotogramma primario')
    end=provenance.get('versione_formale_al_escluso')
    if end:
        next_proof=proof.get('fotogramma_successivo')
        if not isinstance(next_proof,dict):raise ValueError('Fine intervallo priva di fonte successiva')
        next_path,next_raw=load(next_proof.get('file_xml_originale'),512*1024**2)
        nxt,next_doc=interprete(next_raw,next_path,next_proof.get('xml_entry',''),next_proof.get('xml_originale_sha256',''))
        frame=re.search(r'_VIGENZA_(\d{4}-\d{2}-\d{2})_V',next_proof.get('xml_entry',''))
        if next_doc.urn!=derived.prova['urn_derivato_interno_non_alias_ufficiale'] or nxt.prova['urn_derivato_interno_non_alias_ufficiale']!=derived.prova['urn_derivato_interno_non_alias_ufficiale'] or not frame or frame[1]!=end or date.fromisoformat(end)<=date.fromisoformat(start):raise ValueError('Fine intervallo discordante dalla fonte primaria')
    return {'tipo_atto':doc.tipo_atto,'numero':derived.prova['numero_riscontrato'],'data_pubblicazione':gu,'identita_citazione':riga['urn'],'xml_originale_sha256':derived.prova['xml_originale_sha256'],'sha256_testo':hashlib.sha256(matches[0].article_text.encode()).hexdigest(),'versione_formale_dal':start,'versione_formale_al_escluso':end,'numero_riscontrato':derived.prova['numero_riscontrato']}


def verifica_cache_riscontri_identita(cache:dict):
    from pathlib import Path
    for name,signature in cache.get(('stat_identita',),{}).items():
        stat=Path(name).stat()
        if (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)!=signature:
            raise ValueError('Prova di identità modificata durante preparazione')
