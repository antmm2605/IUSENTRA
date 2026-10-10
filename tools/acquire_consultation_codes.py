"""Download only public Normattiva XML; no access to server or studio data."""
import argparse
import http.cookiejar
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ACTS = [
    ('militari_303_1941', 'stato:relazione.e.regio.decreto:1941-02-20;303'),
    ('militari_attuazione_1023_1941', 'stato:regio.decreto:1941-09-09;1023'),
    ('navigazione_regolamento_328_1952', 'stato:decreto.del.presidente.della.repubblica:1952-02-15;328'),
    ('postale_156_1973', 'stato:decreto.del.presidente.della.repubblica:1973-03-29;156'),
    ('cpp_regolamento_334_1989', 'ministero.grazia.e.giustizia:decreto:1989-09-30;334'),
    ('proprieta_regolamento_33_2010', 'ministero.sviluppo.economico:decreto:2010-01-13;33'),
    ('contratti_163_2006', 'stato:decreto.legislativo:2006-04-12;163'),
    ('contratti_regolamento_207_2010', 'stato:decreto.del.presidente.della.repubblica:2010-10-05;207'),
    ('ordinamento_militare_66_2010', 'stato:decreto.legislativo:2010-03-15;66'),
    ('turismo_79_2011', 'stato:decreto.legislativo:2011-05-23;79'),
    ('giustizia_contabile_174_2016', 'stato:decreto.legislativo:2016-08-26;174'),
    ('protezione_civile_1_2018', 'stato:decreto.legislativo:2018-01-02;1'),
    ('incentivi_184_2025', 'stato:decreto.legislativo:2025-11-27;184'),
]


OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def download(url):
    if urllib.parse.urlsplit(url).hostname != 'www.normattiva.it':
        raise ValueError('Host outside the public source allowlist')
    request = urllib.request.Request(url, headers={'User-Agent': 'IUSENTRA public legal library acquisition'})
    with OPENER.open(request, timeout=45) as response:
        if urllib.parse.urlsplit(response.url).hostname != 'www.normattiva.it':
            raise ValueError('Unexpected redirect outside Normattiva')
        content = response.read(64 * 1024 * 1024 + 1)
        if len(content) > 64 * 1024 * 1024:
            raise ValueError('Source exceeds size limit')
        return content, response.url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for key, identity in ACTS:
        row = {'key': key, 'urn': 'urn:nir:' + identity}
        try:
            page, source = download('https://www.normattiva.it/uri-res/N2Ls?' + row['urn'])
            links = re.findall(r'''(?:href|action)\s*=\s*["']([^"']*caricaAKN[^"']*)''', page.decode('utf-8'))
            if not links:
                raise ValueError('Official XML link missing from resolved act')
            xml, xml_url = download(urllib.parse.urljoin(source, html.unescape(links[0])))
            tree = ET.fromstring(xml)
            if tree.tag.rsplit('}', 1)[-1] != 'akomaNtoso':
                raise ValueError('Not an official AKN document')
            ns = {'a': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'}
            work = tree.find('.//a:FRBRWork/a:FRBRuri', ns)
            expected_date, expected_number = identity.rsplit(':', 1)[-1].split(';')
            if work is None or f'/{expected_date}/{expected_number}' not in work.get('value', ''):
                raise ValueError('Downloaded act identity does not match requested act')
            (args.output / (key + '.xml')).write_bytes(xml)
            row.update(status='downloaded', source_url=source, xml_url=xml_url,
                       sha256=hashlib.sha256(xml).hexdigest(), bytes=len(xml),
                       expression_dates=[n.attrib for n in tree.findall('.//a:FRBRExpression/a:FRBRdate', ns)])
        except (OSError, ValueError, ET.ParseError) as error:
            row.update(status='failed', error=str(error))
        manifest.append(row)
        (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(key, row['status'], flush=True)
        time.sleep(1)
    if any(r['status'] != 'downloaded' for r in manifest):
        raise SystemExit('Some public sources could not be downloaded; see manifest')


if __name__ == '__main__':
    main()
