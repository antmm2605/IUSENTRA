#!/usr/bin/env python3
"""Il giro completo su una cartella di atti, misurato sempre allo stesso modo.

    python scripts/banco_importazione_fedele.py <cartella con i PDF>

Serve a rispondere a una domanda sola: **una correzione fatta su un documento
peggiora gli altri?** Tarare il riconoscimento su un atto e vederlo tornare
bene non dice niente — gli atti di uno studio hanno margini che vanno da un
centimetro a sette, interlinee da 13 a 29 punti, e certi PDF non dichiarano
nemmeno il nome dei caratteri. Una modifica si accetta solo se questo banco
non peggiora su nessun documento.

Per ognuno fa il giro che fa l'avvocato — PDF, editor, di nuovo PDF — e
misura: pagine prima e dopo, parole prima e dopo, e quante parole finiscono
entro un millimetro da dove erano.

Non tocca niente e non scrive niente nella cartella: lavora su copie
temporanee.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# lo script si lancia dalla cartella del progetto o da dentro scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#: Sotto questa quota di parole rimaste al loro posto il documento e' cambiato
#: abbastanza da doverlo rivedere prima di depositarlo.
QUOTA_BUONA = 90.0


def _parole(percorso: Path) -> int:
    import pdfplumber

    with pdfplumber.open(str(percorso)) as pdf:
        return len(" ".join((p.extract_text() or "") for p in pdf.pages).split())


def _pagine(percorso: Path) -> int:
    import pdfplumber

    with pdfplumber.open(str(percorso)) as pdf:
        return len(pdf.pages)


def giro(sorgente: Path, cartella: Path) -> dict:
    """Un documento attraverso l'editor e di nuovo in PDF."""
    from pct.documento_fedele import converti_file
    from pct.editor import html_to_pdf
    from pct.verifica_fedelta import confronta

    documento = converti_file(str(sorgente))
    html = "".join(p.html for p in documento.pagine)
    arrivo = cartella / f"{sorgente.stem}-ritorno.pdf"
    arrivo.write_bytes(html_to_pdf(html, sorgente.stem))

    esito = confronta(sorgente, arrivo)
    return {
        "nome": sorgente.name,
        "pagine_prima": _pagine(sorgente),
        "pagine_dopo": _pagine(arrivo),
        "parole_prima": _parole(sorgente),
        "parole_dopo": _parole(arrivo),
        "entro_tolleranza": esito.entro_tolleranza,
        "verdetto": esito.verdetto,
    }


def principale(argomenti=None) -> int:
    lettore = argparse.ArgumentParser(description=__doc__)
    lettore.add_argument("cartella", type=Path, help="dove stanno i PDF da provare")
    lettore.add_argument("--limite", type=int, default=0, help="quanti documenti al massimo")
    scelte = lettore.parse_args(argomenti)

    if not scelte.cartella.is_dir():
        print(f"non e' una cartella: {scelte.cartella}", file=sys.stderr)
        return 2

    documenti, visti = [], set()
    for percorso in sorted(scelte.cartella.rglob("*.pdf")):
        if percorso.name in visti or percorso.name.endswith(".p7m"):
            continue
        visti.add(percorso.name)
        documenti.append(percorso)
    if scelte.limite:
        documenti = documenti[: scelte.limite]
    if not documenti:
        print("nessun PDF trovato", file=sys.stderr)
        return 1

    esiti = []
    with tempfile.TemporaryDirectory() as temporanea:
        for percorso in documenti:
            try:
                esiti.append(giro(percorso, Path(temporanea)))
            except Exception as errore:
                esiti.append({
                    "nome": percorso.name, "pagine_prima": 0, "pagine_dopo": 0,
                    "parole_prima": 0, "parole_dopo": 0, "entro_tolleranza": 0.0,
                    "verdetto": f"errore: {type(errore).__name__}",
                })

    print(f"{'documento':46s} {'pagine':>12} {'parole':>15} {'a posto':>9}  verdetto")
    print("-" * 102)
    for e in esiti:
        segno = "=" if e["pagine_prima"] == e["pagine_dopo"] else "!"
        print(f"{e['nome'][:44]:46s} {e['pagine_prima']:>5}{segno}{e['pagine_dopo']:<6} "
              f"{e['parole_prima']:>6}/{e['parole_dopo']:<8} {e['entro_tolleranza']:>8.1f}%  {e['verdetto']}")
    print("-" * 102)

    buoni = [e for e in esiti
             if e["pagine_prima"] == e["pagine_dopo"] and e["entro_tolleranza"] >= QUOTA_BUONA]
    print(f"documenti che tornano com'erano: {len(buoni)} su {len(esiti)}")
    return 0 if len(buoni) == len(esiti) else 1


if __name__ == "__main__":
    raise SystemExit(principale())
