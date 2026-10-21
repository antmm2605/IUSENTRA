"""Converte il testo XHTML ufficiale di un atto UE nel formato JSONL di lex.normativa.consultazione.importa_fonti.

Il file si scarica dall'Ufficio delle pubblicazioni con negoziazione del contenuto (EUR-Lex rifiuta i client automatici):
    curl -sL -H "Accept: application/xhtml+xml" -H "Accept-Language: ita" \
        -o reg.xhtml http://publications.europa.eu/resource/celex/<CELEX>

Uso: python scripts/eurlex_xhtml_a_jsonl.py FILE.xhtml USCITA.jsonl CHIAVE "ATTO" CELEX DATA_ATTO "TITOLO" DATA_GU
"""
import json
import re
import sys
import time

from lxml import html


def articoli(xhtml: bytes) -> list[tuple[str, str, str]]:
    root = html.fromstring(xhtml)
    out = []
    for div in root.xpath('//div[@class="eli-subdivision" and starts-with(@id,"art_")]'):
        if "." in div.get("id"):
            continue
        rubrica = " ".join(div.xpath('.//p[@class="oj-sti-art"]//text()')).strip()
        testo = re.sub(r"\s+", " ", " ".join(t.strip() for t in div.itertext() if t.strip()))
        out.append((div.get("id")[4:], rubrica, re.sub(r"\s+([,.;:)])", r"\1", testo)))
    return out


def main() -> int:
    src, dst, chiave, atto, celex, data_atto, titolo, data_gu = sys.argv[1:9]
    righe = [{"chiave": chiave, "atto": atto, "articolo": n, "rubrica": r, "testo": t, "titolo_atto": titolo,
              "data_atto": data_atto, "urn": f"urn:nir:unione.europea:regolamento:{data_atto};{celex[5:].lstrip('R0') or celex}",
              "vigenza": "VIGENTE", "fonte_testo": f"Ufficio delle pubblicazioni dell'UE (CELEX {celex}, versione italiana)",
              "url": f"https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:{celex}", "consolidato_al": data_gu,
              "raccolto_il": time.strftime("%Y-%m-%d")}
             for n, r, t in articoli(open(src, "rb").read())]
    if not righe:
        print("nessun articolo trovato")
        return 1
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in righe) + "\n")
    print(len(righe), "articoli")
    return 0


if __name__ == "__main__":
    sys.exit(main())
