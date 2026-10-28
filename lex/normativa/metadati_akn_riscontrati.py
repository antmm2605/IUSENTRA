"""Derivati tecnici da riscontri letterali; il payload ufficiale resta immutato."""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
from lxml import etree
from .normattiva_akn_importer import decodifica_xml_akn,parse_akn
NS={'a':'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'}
SUFFIX=('bis','ter','quater','quinquies','sexies','septies','octies','novies','decies','undecies','duodecies')


def _text(node):
    return ' '.join(' '.join(node.xpath('.//text()[not(ancestor::a:meta)]',namespaces=NS)).split())


def _bodies(act):
    nodes=act.xpath('./a:body|./a:mainBody|./a:attachments/a:attachment/a:doc/a:mainBody|./a:attachments/a:attachment/a:doc/a:body',namespaces=NS)
    return hashlib.sha256(json.dumps([(n.getroottree().getpath(n),hashlib.sha256(etree.tostring(n,method='c14n')).hexdigest()) for n in nodes],separators=(',',':')).encode()).hexdigest()


def _one_edit(a,b):
    if abs(len(a)-len(b))>1:return False
    if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))==1
    if len(a)>len(b):a,b=b,a
    return any(b[:i]+b[i+1:]==a for i in range(len(b)))


def _impronta_normalizzatore():
    # Le verifiche di importazione non cambiano il derivato tecnico. L'impronta
    # copre le funzioni e costanti che producono davvero quel derivato.
    import ast
    wanted={"NS","SUFFIX","_text","_bodies","_one_edit","_impronta_normalizzatore","normalizza_metadati"}
    tree=ast.parse(Path(__file__).read_text(encoding="utf-8"))
    nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name in wanted)
        or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in wanted for t in n.targets))]
    return hashlib.sha256(ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False).encode()).hexdigest()


def normalizza_metadati(payload:bytes):
    decoded,transport=decodifica_xml_akn(payload)
    root=etree.fromstring(decoded,etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=True))
    acts=root.xpath('./a:act|./a:doc',namespaces=NS)
    if len(acts)!=1:raise ValueError('Partizione principale non univoca')
    act=acts[0];changes=[]
    aliases=act.xpath('./a:meta/a:identification/a:FRBRWork/a:FRBRalias/@value',namespaces=NS)
    dates=act.xpath('./a:meta/a:identification/a:FRBRWork/a:FRBRdate/@date',namespaces=NS)
    candidates=[]
    if {x for x in aliases if x.startswith('urn:nir:')}=={'urn:nir:stato:costituzione'} and dates==['0000-00-00']:
        candidates=act.xpath('./a:preface//a:docDate[@date="0000-00-00"]',namespaces=NS)
        if candidates:
            if len(re.findall(r"Data a Roma, add[iì](?:'|’)?\s+27\s+dicembre\s+1947",_text(act),re.I))!=1:raise ValueError('Non-data priva del riscontro testuale della firma')
            eli=[x for x in aliases if x.startswith('eli/')]
            pub=act.xpath('./a:meta/a:publication/@date',namespaces=NS)
            if len(eli)!=1 or len(pub)!=1 or not eli[0].startswith('eli/id/'+pub[0].replace('-','/')+'/'):raise ValueError('Non-data priva di riscontro ELI/pubblicazione')
    annotations=[]
    for node in act.xpath('./a:attachments/a:attachment/a:doc',namespaces=NS):
        name=node.get('name') or ''
        if '-art. ' not in name:continue
        prefix,label=name.rsplit('-art. ',1);m=re.fullmatch(r'([MDCLXVI]+)-([a-z]+)',label.rstrip('.'),re.I)
        if not m or m[2].casefold() in SUFFIX:continue
        bodies=node.xpath('./a:mainBody|./a:body',namespaces=NS)
        if len(bodies)!=1:continue
        heading=re.match(r'^(?:Articolo|Art[.])\s+([MDCLXVI]+)(?:\s+|-)('+ '|'.join(sorted(SUFFIX,key=len,reverse=True))+r')\b',_text(bodies[0]),re.I)
        if not heading or heading[1].casefold()!=m[1].casefold() or not _one_edit(m[2].casefold(),heading[2].casefold()):continue
        annotations.append((node,prefix+'-art. '+m[1]+'-'+heading[2].casefold(),heading.group(0)))
    if not candidates and not annotations:return payload,None
    body_hash=_bodies(act);visible_hash=hashlib.sha256(_text(act).encode()).hexdigest()
    for node in candidates:
        changes.append({'localizzatore_xml':node.getroottree().getpath(node),'attributo':'date','prima':node.get('date'),'dopo':None,'riscontro':'firma testuale ed ELI; verifica completa demandata al lettore nativo'})
        del node.attrib['date']
    for node,value,literal in annotations:
        changes.append({'localizzatore_xml':node.getroottree().getpath(node),'attributo':'name','prima':node.get('name'),'dopo':value,'riscontro_letterale':literal})
        node.set('name',value)
    if _bodies(act)!=body_hash or hashlib.sha256(_text(act).encode()).hexdigest()!=visible_hash:raise ValueError('Corpo o testo visibile modificato')
    normalized=etree.tostring(root,encoding='utf-8',xml_declaration=True)
    proof={'schema':1,'regola':'attributi_tecnici_con_riscontro_nel_corpo_ufficiale','modifiche':changes,'sha256_payload_ufficiale':hashlib.sha256(payload).hexdigest(),'sha256_xml_decodificato_originale':hashlib.sha256(decoded).hexdigest(),'sha256_xml_normalizzato':hashlib.sha256(normalized).hexdigest(),'codifica_originale':transport,'corpo_normativo_c14n_immutato_sha256':body_hash,'testo_visibile_immutato_sha256':visible_hash,'normalizzatore_sha256':_impronta_normalizzatore(),'ambito_impronta_normalizzatore':'AST funzioni e costanti del derivato tecnico','originale_non_modificato':True,'derivato_non_esportazione_ufficiale':True}
    return normalized,proof


def leggi_documento(payload:bytes,*,entry:str|None=None,zip_path:Path|None=None):
    normalized,proof=normalizza_metadati(payload)
    if entry is None:
        decoded,_=decodifica_xml_akn(normalized)
        root=etree.fromstring(decoded,etree.XMLParser(resolve_entities=False,no_network=True,huge_tree=True))
        aliases=root.xpath('./a:act/a:meta/a:identification/a:FRBRWork/a:FRBRalias/@value|./a:doc/a:meta/a:identification/a:FRBRWork/a:FRBRalias/@value',namespaces=NS)
        eli=[x for x in aliases if x.startswith('eli/')]
        match=re.fullmatch(r'eli/id/(\d{4})/(\d{2})/(\d{2})/([0-9A-Z]+)/(ORIGINAL|CONSOLIDATED/(\d{4})(\d{2})(\d{2}))',eli[0]) if len(eli)==1 else None
        if match:
            entry='-'.join(match.group(1,2,3))+'_'+match[4]+('_ORIGINALE_V0.xml' if match[5]=='ORIGINAL' else '_VIGENZA_'+'-'.join(match.group(6,7,8))+'_V0.xml')
        else:entry='risposta_puntuale_senza_nome_zip.xml'
    doc=parse_akn(normalized,zip_path=zip_path or Path('risposta_puntuale.xml'),entry=entry,collection_name='Normattiva AKN riscontrato',analizza_pertinenza=False)
    return doc,proof


def verifica_riga_puntuale(directory:Path,row:dict,*,cache:dict|None=None):
    """Rilegge la fonte fisica e ripete identità, partizioni e confronto del testo."""
    from .biblioteca.normattiva_akn import AttoScaricato,converti
    prov=row.get("provenienza_integrazione") or {}
    relative=prov.get("file_xml_originale")
    if not isinstance(relative,str):raise ValueError("Fonte fisica puntuale assente")
    base_key=("base",str(directory))
    base=cache.get(base_key) if cache is not None else None
    if base is None:
        base=Path(directory).resolve()
        if cache is not None:cache[base_key]=base
    path_key=("percorso",str(base),relative)
    path=cache.get(path_key) if cache is not None else None
    if path is None:
        path=(base/relative).resolve(strict=True)
        if cache is not None:cache[path_key]=path
    if not path.is_relative_to(base) or path.suffix!=".xml" or path.is_symlink():
        raise ValueError("Percorso della fonte fisica fuori pacchetto")
    stat=path.stat();signature=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
    if cache is not None:
        all_stats=cache.setdefault(("file_stats",),{})
        if str(path) in all_stats and all_stats[str(path)]!=signature:raise ValueError("Fonte cambiata durante la preparazione")
        all_stats[str(path)]=signature
    # L'URL di consultazione può cambiare per ogni articolo. Converti lo
    # ricopia soltanto nel campo url (non nei contenuti confrontati sotto):
    # non deve provocare la rilettura dell'intero XML per ciascun articolo.
    # URL di acquisizione, SHA, identità, data e firma del file restano in chiave.
    key=("fonte",str(path),row["urn"],prov.get("sha256_akn"),prov.get("sha256_payload_ufficiale"),
         prov.get("vigenza_richiesta"),prov.get("chiave_base_acquisizione") or row["chiave"],
         row["raccolto_il"],prov.get("data_gu"),prov.get("codice_redazionale"),
         prov.get("data_espressione_akn"),prov.get("url_akn_richiesto"))
    stored=cache.get(key) if cache is not None else None
    if stored is not None and stored[0]!=signature:raise ValueError("Fonte puntuale cambiata durante la verifica")
    if stored is None:
        raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest!=prov.get("sha256_payload_ufficiale") or digest!=prov.get("sha256_akn"):
            raise ValueError("Impronta della fonte puntuale discordante")
        request=str(prov.get("vigenza_richiesta") or "").replace("-","")
        source=AttoScaricato(row["urn"],raw,row["titolo_atto"],prov.get("data_gu", ""),
            prov.get("codice_redazionale", ""),request,row.get("url", ""),digest,
            prov.get("data_espressione_akn", ""),prov.get("url_akn_richiesto", ""))
        candidates=converti(source,prov.get("chiave_base_acquisizione") or row["chiave"],row["raccolto_il"])
        after=path.stat()
        if (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)!=signature:
            raise ValueError("Fonte puntuale cambiata durante la lettura")
        stored=(signature,{(r["chiave"],r["articolo"]):r for r in candidates})
        if cache is not None:
            source_keys=[k for k in cache if isinstance(k,tuple) and k[0]=="fonte"]
            if len(source_keys)>=4:cache.pop(source_keys[0])
            cache[key]=stored
    matches=[stored[1][(row["chiave"],row["articolo"])]] if (row["chiave"],row["articolo"]) in stored[1] else []
    if len(matches)!=1:raise ValueError("Articolo o partizione non riscontrati nella fonte puntuale")
    expected=matches[0]
    interval_fields={"successione_primaria_riscontrata","versione_formale_dal","versione_formale_al_escluso","intervallo_formale_riscontrato","acquisita_utc","catena_ufficiale_completa","espressione_dal"}
    if prov.get("intervallo_formale_riscontrato"):
        sequence=prov.get("successione_primaria_riscontrata")
        if not isinstance(sequence,list) or not sequence:raise ValueError("Intervallo senza successione fisica")
        seq_key=("successione",json.dumps(sequence,sort_keys=True),row["urn"])
        checked=cache.get(seq_key) if cache is not None else None
        if checked is None:
            stats=[]
            for frame in sequence:
                file=(base/frame["file_xml_originale"]).resolve(strict=True)
                if not file.is_relative_to(base):raise ValueError("Fotogramma fuori pacchetto")
                st=file.stat();stats.append((str(file),st.st_size,st.st_mtime_ns,st.st_ctime_ns))
            verified=[]
            for frame in sequence:
                payload=(base/frame["file_xml_originale"]).read_bytes()
                if hashlib.sha256(payload).hexdigest()!=frame["sha256_xml"]:raise ValueError("Impronta di un fotogramma discordante")
                document,_=leggi_documento(payload,entry=frame["xml_entry"])
                if document.urn!=row["urn"]:raise ValueError("Atto diverso nella successione")
                start=re.search(r"_VIGENZA_(\d{4}-\d{2}-\d{2})_V[0-9]+[.]xml$",frame["xml_entry"])
                day=start[1] if start else document.redazione_id
                if document.redazione_id>day or day!=frame["dal"]:raise ValueError("Data del fotogramma discordante")
                verified.append((frame["sha256_xml"],day))
            if any(a[1]>b[1] for a,b in zip(verified,verified[1:])):raise ValueError("Successione non ordinata")
            checked=(stats,verified)
            if cache is not None:cache[seq_key]=checked
        positions=[i for i,x in enumerate(checked[1]) if x[0]==prov["sha256_akn"]]
        if len(positions)!=1:raise ValueError("Fotogramma attuale non univoco nella successione")
        pos=positions[0];start=checked[1][pos][1];end=checked[1][pos+1][1] if pos+1<len(checked[1]) else None
        if (prov.get("versione_formale_dal")!=start or prov.get("versione_formale_al_escluso")!=end
                or prov.get("catena_ufficiale_completa") is not False):raise ValueError("Intervallo non coincide con i fotogrammi ufficiali")
        from datetime import datetime
        received=datetime.fromisoformat(prov.get("acquisita_utc", ""))
        if received.tzinfo is None:raise ValueError("Acquisizione senza fuso orario")
        if prov.get("espressione_dal")!=expected["consolidato_al"]:raise ValueError("Espressione letterale discordante")
        expected=dict(expected,consolidato_al=start)
    elif any(k in prov for k in interval_fields):raise ValueError("Intervallo non riscontrato")
    for key in ("urn","atto","testo","rubrica","titolo_atto","data_atto","consolidato_al","senza_testo","struttura_normativa"):
        if row.get(key)!=expected.get(key):raise ValueError("Contenuto puntuale discordante: "+key)
    declared={k:v for k,v in prov.items() if k not in {"file_xml_originale","cache_locale_non_utilizzata"}|interval_fields}
    # Le tuple del lettore diventano array nel pacchetto JSON. Confrontare la
    # rappresentazione persistita conserva invece tutte le differenze di valori.
    if json.dumps(declared,sort_keys=True,separators=(",",":"))!=json.dumps(expected["provenienza_integrazione"],sort_keys=True,separators=(",",":")):
        raise ValueError("Provenienza puntuale discordante dalla rilettura fisica")
    return True


def verifica_cache_puntuali(cache:dict):
    """Conferma tutti i file già riscontrati prima di scrivere SQL, senza riletture per articolo."""
    for key,value in cache.items():
        if not isinstance(key,tuple):continue
        if key[0]=="file_stats":
            for name,signature in value.items():
                st=Path(name).stat()
                if (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)!=signature:
                    raise ValueError("Fonte modificata durante la preparazione del pacchetto")
        elif key[0]=="successione":
            for name,size,mtime,ctime in value[0]:
                st=Path(name).stat()
                if (st.st_size,st.st_mtime_ns,st.st_ctime_ns)!=(size,mtime,ctime):
                    raise ValueError("Successione modificata durante la preparazione del pacchetto")
        elif key[0]=="fonte":
            st=Path(key[1]).stat()
            if (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)!=value[0]:
                raise ValueError("Fonte modificata durante la preparazione del pacchetto")
