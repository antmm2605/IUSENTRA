"""Testi anteriori delle norme delle fattispecie per materia che una riforma con regime transitorio ha cambiato.

Per ogni voce di ``ANTERIORI`` si scarica da Normattiva (Akoma Ntoso, multivigenza) il testo vigente il giorno prima
della riforma e lo si registra in ``lex/harness/dati/testi_anteriori_materie.json`` con URL, data di vigenza, impronta e
la norma transitoria letta nel testo vigente (stesso formato di ``lex/conoscenza/dati/testi_anteriori.json``). Il testo
anteriore non è un consiglio: è il diritto applicabile ai procedimenti indicati dalla norma transitoria.

Uso: python scripts/lex_harness_testi_anteriori_materie.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

USCITA = RADICE / "lex" / "harness" / "dati" / "testi_anteriori_materie.json"

# atto anteriore -> (urn, vigenza AAAAMMGG, articoli, citazione, chiave della norma transitoria vigente, regole)
ANTERIORI = {
    "dlgs25_ante2026": ("urn:nir:stato:decreto.legislativo:2008-01-28;25", "20260611", ("35bis", "35ter"),
                        "d.lgs. 25/2008", "dl100_2026:17", ("imm_protezione_internazionale",)),
}


def main() -> int:
    from lex.harness.norme import testo_norma
    from lex.normativa.biblioteca.fabbisogno import norm_articolo
    from lex.normativa.biblioteca.normattiva_akn import converti, nuovo_opener, scarica

    opener = nuovo_opener()
    registrate, esiti = {}, []
    for atto, (urn, vigenza, articoli, sigla, transitoria, regole) in ANTERIORI.items():
        documento = scarica(urn, vigenza, opener=opener, timeout=180)
        righe = converti(documento, atto, dt.date.today().isoformat())
        per_numero = {norm_articolo(str(r.get("articolo") or "")).replace(".", "").lower(): r for r in righe}
        nota = testo_norma(transitoria)
        i = nota.testo.find("4. Ai procedimenti") if nota else -1
        decorrenza = [nota.testo[i:nota.testo.find(".", nota.testo.find("monocratica", i)) + 1]] if i >= 0 else []
        vig = f"{vigenza[6:]}/{vigenza[4:6]}/{vigenza[:4]}"
        for numero in articoli:
            r = per_numero.get(numero)
            testo = " ".join(str((r or {}).get("testo") or "").split())
            art = numero.replace("bis", "-bis").replace("ter", "-ter")
            base = {"citazione": f"art. {art} {sigla}", "vigente_al": vig, "urn": urn, "decorrenza_letta": decorrenza,
                    "norma_transitoria": transitoria, "regole": list(regole), "sha256_akn": documento.sha256_xml}
            if not testo:
                registrate[f"{atto}:{numero}"] = {**base, "stato": f"assente al {vig}"}
                continue
            registrate[f"{atto}:{numero}"] = {
                **base, "stato": "testo anteriore", "testo": testo,
                "versione": hashlib.sha256(testo.encode()).hexdigest()[:16],
                "url": f"https://www.normattiva.it/uri-res/N2Ls?{urn}~art{numero}!vig={vigenza[:4]}-{vigenza[4:6]}-{vigenza[6:]}"}
        esiti.append({"urn": urn, "atto": atto, "esito": "scaricato", "articoli_atto": len(righe)})
    dati = {"metodo": __doc__.split("\n\n")[1].replace("\n", " "), "acquisito_il": dt.date.today().isoformat(),
            "esiti": esiti, "norme": registrate}
    USCITA.write_text(json.dumps(dati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v["stato"] for k, v in registrate.items()}, ensure_ascii=False), esiti)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
