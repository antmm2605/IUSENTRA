"""Converte gli AKN vigenti di Normattiva nel formato JSONL di lex.normativa.consultazione.importa_fonti."""
import json, re, sys
from pathlib import Path
from lxml import etree

NS = {'a': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'}
SIGLA = {'legge': 'l.', 'decreto.legislativo': 'd.lgs.', 'decreto.del.presidente.della.repubblica': 'd.P.R.',
         'decreto.legge': 'd.l.', 'decreto': 'd.m.', 'legge.costituzionale': 'l. cost.'}
CHIAVE = {'legge': 'legge', 'decreto.legislativo': 'dlgs', 'decreto.del.presidente.della.repubblica': 'dpr',
          'decreto.legge': 'dl', 'decreto': 'dm', 'legge.costituzionale': 'lcost'}


def testo(el):
    t = ' '.join(x.strip() for x in el.itertext() if x.strip())
    return re.sub(r'\s+([,.;:)])', r'\1', re.sub(r'\s+', ' ', t)).strip()


def numero(num):
    v = re.sub(r'^art(icolo)?\.?\s*', '', num.strip().lower()).strip(' .')
    return re.sub(r'[\s\-]', '', v)


def converti(xml: Path, meta: dict) -> list[dict]:
    root = etree.parse(str(xml))
    urn = next(v for v in root.xpath('//a:FRBRWork/a:FRBRalias/@value', namespaces=NS) if v.startswith('urn:nir:'))
    tipo = urn.split(':')[-2]
    num, data = urn.split(';')[-1], urn.split(':')[-1].split(';')[0]
    anno = data[:4]
    titolo = testo(root.xpath('//a:preface//a:docTitle', namespaces=NS)[0]) if root.xpath('//a:preface//a:docTitle', namespaces=NS) else meta['titolo_pagina']
    chiave = f"{CHIAVE[tipo]}_{num}_{anno}"
    atto = f"{SIGLA[tipo]} {num}/{anno}"
    rows, visti = [], set()
    # Solo gli articoli del corpo dell'atto: allegati e componenti hanno numerazioni proprie.
    for art in root.xpath('//a:body//a:article[not(ancestor::a:attachment) and not(ancestor::a:component) and not(ancestor::a:mod)]', namespaces=NS):
        n = art.find('a:num', NS)
        if n is None:
            continue
        nr = numero(testo(n))
        if not nr or nr in visti:
            continue
        visti.add(nr)
        h = art.find('a:heading', NS)
        rubrica = testo(h).strip('() ') if h is not None else ''
        corpo = testo(art)
        if not corpo:
            continue
        rows.append(dict(chiave=chiave, atto=atto, articolo=nr, rubrica=rubrica, testo=corpo, titolo_atto=titolo,
                         data_atto=data, urn=urn, vigenza='VIGENTE', fonte_testo='Normattiva (Akoma Ntoso vigente)',
                         url=meta['url'], consolidato_al=f"{meta['data_vigenza'][:4]}-{meta['data_vigenza'][4:6]}-{meta['data_vigenza'][6:]}",
                         raccolto_il=meta['raccolto_il']))
    return rows


if __name__ == '__main__':
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    (dst / 'atti').mkdir(parents=True, exist_ok=True)
    report = []
    for meta_file in sorted(src.glob('*.json')):
        meta = json.loads(meta_file.read_text(encoding='utf-8'))
        rows = converti(meta_file.with_suffix('.xml'), meta)
        report.append((meta['urn_richiesto'], len(rows), meta['etichetta']))
        if rows:
            (dst / 'atti' / f"{rows[0]['chiave']}.jsonl").write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n', encoding='utf-8')
    for r in report:
        print(*r, sep='\t')
