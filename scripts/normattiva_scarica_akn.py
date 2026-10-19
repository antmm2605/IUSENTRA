"""Scarica da Normattiva il testo vigente (Akoma Ntoso) degli atti elencati in akn_targets.tsv.

Uso: python3 scarica_akn_normattiva.py TARGETS.tsv CARTELLA_USCITA [DATA_VIGENZA aaaammgg]
Riprende da dove si era fermato: gli atti già salvati vengono saltati.
Per ogni atto salva <slug>.xml (AKN ufficiale) e <slug>.json (URN, titolo, dataGU, codice redazionale, URL).
"""
import html, json, re, sys, time, urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

targets, out = Path(sys.argv[1]), Path(sys.argv[2])
vigenza = sys.argv[3] if len(sys.argv) > 3 else time.strftime('%Y%m%d')
budget = float(sys.argv[4]) if len(sys.argv) > 4 else 150
out.mkdir(parents=True, exist_ok=True)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
opener.addheaders = [('User-Agent', 'IUSENTRA-biblioteca-normativa/1.0 (studio legale)')]
start = time.time()
for line in targets.read_text(encoding='utf-8').splitlines():
    if time.time() - start > budget:
        break
    urn, label, materia = line.split('\t')
    slug = re.sub(r'[^0-9a-z]+', '_', urn.lower())
    if (out / f'{slug}.json').exists():
        continue
    try:
        page = opener.open('https://www.normattiva.it/uri-res/N2Ls?' + urn, timeout=40).read().decode('utf-8', 'replace')
        m = re.search(r'caricaAKN\?dataGU=(\d{8})&amp;codiceRedaz=([0-9A-Z]+)', page)
        title = html.unescape(re.search(r'<title>([^<]*)', page).group(1)).replace(' - Normattiva', '').strip()
        if not m:
            raise ValueError('collegamento AKN assente')
        gu, redaz = m.groups()
        akn = opener.open(f'https://www.normattiva.it/do/atto/caricaAKN?dataGU={gu}&codiceRedaz={redaz}&dataVigenza={vigenza}', timeout=90).read()
        if b'<akomaNtoso' not in akn[:2000]:
            raise ValueError('risposta non AKN')
        (out / f'{slug}.xml').write_bytes(akn)
        meta = dict(urn_richiesto=urn, etichetta=label, materia=materia, titolo_pagina=title, data_gu=gu,
                    codice_redazionale=redaz, data_vigenza=vigenza, raccolto_il=time.strftime('%Y-%m-%d'),
                    url=f'https://www.normattiva.it/atto/caricaDettaglioAtto?atto.dataPubblicazioneGazzetta={gu[:4]}-{gu[4:6]}-{gu[6:]}&atto.codiceRedazionale={redaz}')
        (out / f'{slug}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
        print('OK', urn, title, len(akn))
    except Exception as exc:
        (out / f'{slug}.errore.txt').write_text(str(exc), encoding='utf-8')
        print('ERRORE', urn, exc)
    time.sleep(1.5)
