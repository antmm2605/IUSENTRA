"""Regole temporali sigillate dalla distribuzione, mai dal piano del modello.

La presenza della legge in biblioteca non ne approva l'applicazione al caso.
Il registro e le approvazioni restano dati distinti con impronta attesa esterna.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date,timedelta
from pathlib import Path
import hashlib,json,os,re
from .applicabilita import Applicabilita,data_iso,data_evento_confermato,impronta,valuta_applicabilita

@dataclass(frozen=True)
class RegistroApplicabilita:
    regole: tuple[dict,...] = ()
    approvate: frozenset[str] = frozenset()
    sha256: str | None = None

def carica_registro() -> RegistroApplicabilita:
    path=os.environ.get('PCT_NORMATTIVA_APPLICABILITA_MANIFEST')
    expected=os.environ.get('PCT_NORMATTIVA_APPLICABILITA_MANIFEST_SHA256')
    if not path and not expected:return RegistroApplicabilita()
    if not path or not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):
        raise ValueError('Registro di applicabilita privo di percorso o SHA atteso')
    p=Path(path).resolve(strict=True)
    if p.stat().st_size>8*1024**2:raise ValueError('Registro di applicabilita oltre limite')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Registro di applicabilita alterato')
    obj=json.loads(raw)
    if not isinstance(obj,dict) or obj.get('schema')!=1 or not isinstance(obj.get('regole'),list) or not isinstance(obj.get('approvazioni'),list):
        raise ValueError('Registro di applicabilita non strutturato')
    rules=obj['regole'];hashes=set()
    for rule in rules:
        if not isinstance(rule,dict) or not isinstance(rule.get('atto_id'),str) or not rule['atto_id'].startswith(('urn:nir:','https://www.gazzettaufficiale.it/eli/id/')):
            raise ValueError('Identita della regola non dichiarata')
        if rule['atto_id'].startswith('urn:nir:'):
            named=re.fullmatch(r'urn:nir:[^:]+:[^:]+:(\d{4}-\d{2}-\d{2})(?:;[^;?#!]+)?',rule['atto_id'])
            if not named:raise ValueError('La regola richiede la identita completa con data, non solo numero e anno')
            data_iso(named[1])
        if rule.get('ambito') not in {'sostanziale','processuale'} or not isinstance(rule.get('evento'),str) or not rule['evento']:
            raise ValueError('Evento o ambito della regola non dichiarati')
        from lex.testi_ufficiali import _urn_canonico
        if _urn_canonico(rule['atto_id'])!=rule['atto_id']:raise ValueError('Identita della regola da normalizzare prima della approvazione')
        articles=rule.get('articoli')
        if articles is not None and (not isinstance(articles,list) or not articles or len(articles)>1000 or any(not isinstance(x,str) or not x.strip() or len(x)>40 for x in articles)):raise ValueError('Articoli della regola non dichiarati correttamente')
        if 'partizione_xml' in rule and (not isinstance(rule['partizione_xml'],str) or not rule['partizione_xml']):raise ValueError('Partizione della regola non dichiarata')
        extra=rule.get('fonti_congiunte',[])
        if not isinstance(extra,list) or len(extra)>16:raise ValueError('Fonti congiunte della regola non valide')
        proof=rule.get('fonte')
        from .consultazione import url_ufficiale_valido
        if not isinstance(proof,dict) or not url_ufficiale_valido(proof.get('url','')):raise ValueError('Fonte ufficiale della regola mancante')
        if any(not isinstance(f,dict) or not url_ufficiale_valido(f.get('url','')) for f in extra):raise ValueError('Fonte congiunta non ufficiale o incompleta')
        digest=impronta(rule)
        if digest in hashes:raise ValueError('Regola duplicata nel registro')
        hashes.add(digest)
    approved=set()
    for approval in obj['approvazioni']:
        if not isinstance(approval,dict) or approval.get('regola_sha256') not in hashes or not str(approval.get('approvata_da') or '').strip() or not str(approval.get('riferimento_approvazione') or '').strip():
            raise ValueError('Approvazione della regola incompleta o non riferibile')
        data_iso(approval.get('approvata_il'))
        if approval['regola_sha256'] in approved:raise ValueError('Approvazione duplicata')
        approved.add(approval['regola_sha256'])
    return RegistroApplicabilita(tuple(rules),frozenset(approved),expected)

def valuta_fonte_registrata(atto_id: str, provenienza: dict, eventi: dict, registro: RegistroApplicabilita, *, articolo: str | None = None,riscontra_fonte=None) -> dict:
    from lex.testi_ufficiali import _urn_canonico
    identity=_urn_canonico(atto_id)
    rules=[r for r in registro.regole if _urn_canonico(r['atto_id'])==identity]
    from .biblioteca.fabbisogno import norm_articolo
    relevant=bool(rules)
    scope_missing=False
    selected=[]
    for r in rules:
        if r.get('articoli') is not None:
            if articolo is None:scope_missing=True;continue
            if norm_articolo(articolo) not in {norm_articolo(x) for x in r['articoli']}:continue
        if r.get('partizione_xml'):
            part=(provenienza.get('edizione_archiviata') or {}).get('partizione_xml')
            if not part:scope_missing=True;continue
            if part!=r['partizione_xml']:continue
        selected.append(r)
    rules=selected;relevant=bool(rules) or scope_missing
    if scope_missing:
        result=Applicabilita('da_verificare',('Articolo o partizione necessari per la regola temporale',))
    elif not rules:

        result=Applicabilita('da_verificare',('Applicabilita da riscontrare sul procedimento',))
    elif len({(r['ambito'],r['evento']) for r in rules})!=1:
        result=Applicabilita('da_verificare',('Ambiti o eventi diversi: necessario riscontro della regola pertinente',))
    else:
        scope,event=rules[0]['ambito'],rules[0]['evento']
        when=data_evento_confermato(eventi,event)
        from .provenienza_edizione import riscontro_alla_data
        edition=provenienza.get('edizione_archiviata') or {}
        covered=when is not None and riscontro_alla_data(edition,when) is True
        # Punto effettivamente riscontrato nella versione, non una nuova
        # durata di vigenza dedotta dal giorno di download.
        coverage={'confermata':covered,'dal':when.isoformat() if when else '',
                  'al_escluso':(when+timedelta(days=1)).isoformat() if when and when<date.max else ''}
        approved=[r for r in rules if impronta(r) in registro.approvate]
        sources_ok=(not approved or when is None or (riscontra_fonte is not None and all(riscontra_fonte(f,when) for r in approved for f in [r['fonte'],*r.get('fonti_congiunte',[])])))
        if not sources_ok:
            result=Applicabilita('da_verificare',('Versione o provenienza della disposizione transitoria non riscontrata alla data del procedimento',))
        else:
            result=valuta_applicabilita({'atto_id':identity,'ambito':scope,'evento_riferimento':event,'copertura_versione':coverage},eventi,rules,registro.approvate)
    return {'stato':result.stato,'motivi':list(result.motivi),'regole':list(result.regole),
            'registro_sha256':registro.sha256,'regole_pertinenti':relevant,'atto_id':identity}


def riscontro_fonte_cache(proof:dict, quando, percorso:Path) -> bool:
    """Fonte della regola riletta nella cache qualificata, non nella risposta AI.

    Un cambio anche della sola provenienza rende inutilizzabile l'approvazione
    precedente. Il percorso proviene dalla configurazione, mai dal manifest.
    """
    import sqlite3
    from contextlib import closing
    from lex.normativa.versioni_akn import leggi_versione
    from lex.normativa.biblioteca.fabbisogno import norm_articolo
    from lex.testi_ufficiali import _urn_canonico,collegamento_normattiva
    if proof.get('archivio')!='cache_akn' or not percorso.is_file():return False
    urn=proof.get('urn');article=proof.get('articolo');snapshot=proof.get('edizione_archiviata')
    if not isinstance(urn,str) or not isinstance(article,str) or not isinstance(snapshot,dict):return False
    if proof.get('versione')!=(snapshot.get('espressione_dal') or snapshot.get('versione_dal')):return False
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        acquired=datetime.fromisoformat(snapshot.get('acquisita_utc',''))
        if acquired.tzinfo is None or proof.get('acquisita_il')!=acquired.astimezone(ZoneInfo('Europe/Rome')).date().isoformat():return False
    except (TypeError,ValueError):return False
    if proof.get('url')!=collegamento_normattiva(urn,article):return False
    with closing(sqlite3.connect(percorso.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
        conn.execute('PRAGMA query_only=ON')
        rows=leggi_versione(conn,urn=urn,data_riferimento=quando.isoformat(),partizione=proof.get('partizione_xml'))
    selected=[r for r in rows if norm_articolo(r['numero'])==norm_articolo(article)]
    if len(selected)!=1:return False
    row=selected[0]
    if _urn_canonico(row['urn'])!=_urn_canonico(urn) or row['testo']!=proof.get('testo') or hashlib.sha256(row['testo'].encode()).hexdigest()!=proof.get('sha256'):return False
    fields=('urn','numero','partizione','localizzatore_xml','versione_dal','versione_al_escluso','espressione_dal','xml_sha256','xml_decodificato_sha256','zip_sha256','acquisita_utc','lettore_sha256','lettore_riscontro_sha256','rilettura_catena_sha256','politica_lettori_sha256','rapporto_compatibilita_sha256')
    actual={k:row.get(k) for k in fields}
    return actual==snapshot
