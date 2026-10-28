"""Lettura puntuale: testo SQL acquisito, versione e SHA, senza ricerche manuali."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lex.normativa.biblioteca.fabbisogno import norm_articolo
from lex.normativa.consultazione import COLLECTION, dettaglio
from lex.testi_ufficiali import CODICI, _urn_canonico, collegamento_normattiva

HOST_UFFICIALI = {'www.normattiva.it', 'normattiva.it', 'eur-lex.europa.eu', 'publications.europa.eu', 'www.gazzettaufficiale.it', 'www.consigliodistrettuale.it', 'www.consiglionazionaleforense.it'}


class ArticoloCambiato(ValueError):
    pass


def numero_articolo(value):
    from lex.normativa.biblioteca.identita import numero_articolo as convalida_numero
    return convalida_numero(value)


def _urn_da_url(url):
    parts = urlsplit(str(url or ""))
    if parts.scheme != "https" or parts.hostname not in {"www.normattiva.it", "normattiva.it"} or parts.username or parts.password:
        return ""
    query = unquote(parts.query).split("~", 1)[0].split("!", 1)[0]
    return _urn_canonico(query) if query.startswith("urn:nir:") else ""


def _base_urn(urn):
    return re.sub(r"(;[0-9]+):[0-9]+$", r"\1", _urn_canonico(urn))


def _fonte_uguale(url, record):
    urn = _urn_da_url(url)
    if urn:
        if _base_urn(urn) != _base_urn(record["urn"]):return False
        requested=unquote(urlsplit(url).query)
        selected=re.search(r"~art([^!&]+)",requested)
        if selected and numero_articolo(selected[1])!=numero_articolo(record['number']):return False
        # Il documento padre uguale non dimostra un allegato omonimo.
        part=re.search(r";[0-9]+:([0-9]+)$",urn)
        if part:
            effective=_urn_da_url(record.get('source_url',''))
            if not re.search(r";[0-9]+:[0-9]+$",effective):
                effective=_urn_da_url(destinazione_ufficiale(record))
            expected=re.search(r";[0-9]+:([0-9]+)$",effective)
            if expected is None or expected[1]!=part[1]:return False
        version=re.search(r"!vig=([^&]+)",requested)
        if version:
            actual=re.search(r"!vig=([^&]+)",unquote(urlsplit(record.get('source_url','')).query))
            if actual is None or actual[1]!=version[1]:return False
        return True
    a, b = urlsplit(url), urlsplit(record["source_url"])
    return a.scheme == "https" and not a.username and not a.password and (a.hostname, a.path, a.query) == (b.hostname, b.path, b.query)


def risolvi(db, *, ident=0, atto="", articolo="", url="", sha=""):
    if len(str(url)) > 4000 or len(str(atto)) > 100:
        raise ValueError("Riferimento della fonte non valido.")
    numero = numero_articolo(articolo) if articolo else ""
    if not ident and not numero:
        raise ValueError("Articolo non specificato.")
    if atto and not re.fullmatch(r"[A-Za-z0-9_/-]{1,100}", atto):
        raise ValueError("Atto non valido.")
    if not ident and not atto and not url:
        raise ValueError("Fonte dell'articolo non specificata.")
    with closing(sqlite3.connect(Path(db).resolve().as_uri()+"?mode=ro", uri=True)) as conn:
        if ident:
            rows = conn.execute("SELECT id FROM normative_articles WHERE id=?", (ident,)).fetchall()
        else:
            sql = ("SELECT a.id FROM normative_articles a JOIN normative_documents d ON d.id=a.document_id "
                   "WHERE d.collection_name LIKE ? AND replace(replace(replace(replace(lower(a.article_number),'art.',''),'-',''),' ',''),'.','')=? "
                   "AND d.id=(SELECT x.id FROM normative_documents x WHERE x.collection_name=d.collection_name ORDER BY x.redazione_id DESC,x.id DESC LIMIT 1)")
            params = [COLLECTION+'%', numero.replace('.', '')]
            if atto:
                sql += " AND d.collection_name=?"
                params.append(COLLECTION+atto)
            urn = _urn_da_url(url)
            if urn and not atto:
                sql += " AND d.urn IN (?,?)"
                canonical = _base_urn(urn)
                params += [canonical, canonical.replace("urn:nir:presidente.repubblica:decreto:", "urn:nir:stato:decreto.del.presidente.della.repubblica:")]
            rows = conn.execute(sql+" ORDER BY a.id LIMIT 501", params).fetchall()
    if len(rows) > 500:
        raise ValueError("Riferimento non univoco: apri l'articolo dal suo catalogo.")
    trovati = []
    for row in rows:
        item = dettaglio(Path(db), row[0], includi_archivio_generale=bool(ident))
        if not item or (numero and numero_articolo(item['number']) != numero):
            continue
        if atto and item.get('act_key') != atto:
            continue
        if url and not _fonte_uguale(url, item):
            continue
        item['sha256'] = hashlib.sha256(item['text'].encode()).hexdigest()
        if sha and item['sha256'] != sha:
            continue
        trovati.append(item)
    if ident and not trovati:
        from lex.normativa.consultazione import dettagli_precedenti
        for item in dettagli_precedenti(Path(db),ident,sha=sha):
            if numero and numero_articolo(item['number'])!=numero:continue
            if atto and item.get('act_key')!=atto:continue
            if url and not _fonte_uguale(url,item):continue
            trovati.append(item)
    if not trovati:
        if sha and rows:
            raise ArticoloCambiato("Il testo è cambiato rispetto alla selezione: ricarica il modello prima di leggerlo o approvarlo.")
        raise LookupError("Articolo non presente nella biblioteca con questo riferimento: nessun altro testo è stato sostituito.")
    import json
    if len({(r['urn'], r['sha256'], r['updated_at'],json.dumps(r.get('source_provenance') or {},sort_keys=True,ensure_ascii=False)) for r in trovati}) != 1:
        raise ArticoloCambiato("Il riferimento corrisponde a più testi distinti. Seleziona l'articolo preciso da Codici e leggi.")
    item = trovati[0]
    if item.get('only_heading') or not item.get('text', '').strip():
        raise LookupError("La biblioteca contiene solo l'intestazione: il testo integrale non è disponibile.")
    item['article_url'] = '' if item.get('archived_import') else destinazione_ufficiale(item)
    return item


def destinazione_ufficiale(item):
    url = item['source_url']
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.username or parts.password or parts.hostname not in HOST_UFFICIALI:
        return ''
    try:numero = numero_articolo(item['number'])
    except ValueError:return ''
    if '/' in numero or not numero[:1].isdigit():return ''
    if parts.hostname in {'www.normattiva.it', 'normattiva.it'}:
        urn = _urn_da_url(url) or _urn_canonico(item['urn'])
        known = any(_base_urn(urn) == c.urn for c in CODICI)
        allegato = re.match(r"\s*ALLEGATO\s+([0-9]+)\b", item['text'], re.IGNORECASE)
        # Numeri identici in allegati diversi: non inventare quale allegato aprire.
        if allegato and not re.search(r';[0-9]+:[0-9]+$', urn):
            urn += ':'+allegato.group(1)
        elif not known and not re.search(r';[0-9]+:[0-9]+$', urn):
            return ''
        versione = re.search(r'!vig=([^&]*)', unquote(parts.query))
        suffisso = '!vig='+versione.group(1) if versione else '!vig='
        return collegamento_normattiva(urn, numero)+suffisso
    # Un puntatore già acquisito alla disposizione resta valido; non crearne
    # uno fittizio per un PDF, per un sommario o per un portale non riscontrato.
    if parts.fragment and re.search(r'(?:art|page)[_=-]?[0-9]+', parts.fragment, re.IGNORECASE):
        return url
    return ''


def documento_html(item):
    from pct.formatting import format_date_it
    edition_label=format_date_it(item.get('updated_at')) or 'da riscontrare'
    display_number=re.sub(r'^\s*art(?:icolo)?\.?\s*','',str(item['number']),flags=re.IGNORECASE)
    title = 'Art. '+display_number+' — '+item['act_label']
    external = ("<p><a href='"+escape(item['article_url'],quote=True)+"' target='_blank' rel='noopener noreferrer' data-official-outside-reader='1'>Verifica questo articolo nella fonte ufficiale</a></p>") if item['article_url'] else "<p>Il collegamento della fonte identifica il documento completo; qui è già aperto l'articolo selezionato, senza ricerca manuale.</p>"
    archival=''
    heading='Testo acquisito dalla fonte ufficiale'
    if item.get('archived_import'):
        heading='Lettura archiviata precedente alla rettifica'
        archival="<p role='note'><strong>Questa lettura tecnica è stata rettificata e non è utilizzabile come Fonte corrente.</strong> Il testo e l’impronta della precedente selezione restano conservati per confronto.</p>"
        corrected=item.get('rettifica_corrente')
        if corrected:
            archival+="<section aria-label='Parte rettificata della stessa fonte'><h2>Parte rettificata della stessa fonte</h2><pre>"+escape(corrected['text'])+"</pre><p>SHA-256: <code>"+escape(corrected['sha256'])+"</code></p></section>"
    source = urlsplit(item['source_url'])
    source_link = ("<a href='"+escape(item['source_url'],quote=True)+"' target='_blank' rel='noopener noreferrer' data-official-outside-reader='1'>Documento della fonte da cui è stato acquisito il testo</a>") if source.scheme == 'https' and source.hostname in HOST_UFFICIALI and not source.username and not source.password else escape(item['source_url'])
    return ("<!doctype html><html lang='it'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            "<link rel='stylesheet' href='/static/css/normative-article-reader.css'><title>"+escape(title)+"</title></head><body><main>"
            "<header><p>"+escape(heading)+"</p><h1>"+escape(title)+"</h1><p>Edizione della biblioteca: "+escape(edition_label)+"</p></header>"
            "<article aria-label='Testo integrale dell’articolo'><pre>"+escape(item['text'])+"</pre></article>"+archival+external+
            "<details><summary>Provenienza e impronta</summary><p>SHA-256: <code>"+escape(item['sha256'])+"</code></p><p>"
            +source_link+"</p>"
            "<p>Il collegamento completo è una verifica aggiuntiva: per leggere questo articolo non occorre cercarlo nel documento.</p></details></main></body></html>")
