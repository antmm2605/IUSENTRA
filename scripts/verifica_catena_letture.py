#!/usr/bin/env python3
"""Autocontrollo della catena delle letture, sui fascicoli veri dello studio.

Da eseguire **sul server**, dove ci sono i dati reali:

    docker compose exec app python scripts/verifica_catena_letture.py
    docker compose exec app python scripts/verifica_catena_letture.py --fascicolo FF6E8CC0
    docker compose exec app python scripts/verifica_catena_letture.py --json

Non è un test con dati inventati: apre il registro e l'archivio dello studio e
riporta che cosa contengono davvero, dove la catena si è fermata e dove si è
rotta. Risponde a cinque domande, nell'ordine in cui contano:

1. **Il registro si apre?** Se no, tutto il resto è fermo e il motivo va letto qui.
2. **Il ciclo dei due motori dove sta?** Per ogni fascicolo: fermo (tutto letto
   e confermato), da leggere, in errore — con il motivo.
3. **Che cosa hanno scritto i motori?** Fatti per categoria e per verdetto.
4. **L'archivio ha consegnato ai presìdi?** Per ogni presidio: quanto gli spetta,
   quanto ha preso in carico, quanto resta.
5. **C'è spreco?** Categorie lette da nessun presidio, oggetti fermi in attesa.

Esce con codice 0 se la catena è integra, 1 se qualcosa la rompe.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _stato_fascicolo(fascicolo: Any, registro: Any, tenant: str) -> dict[str, Any]:
    from web.services.archivio_letture_runtime import stato_ciclo_fascicolo, _impronta_viva

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    stato = stato_ciclo_fascicolo(fascicolo_id, registro, tenant, impronta=_impronta_viva(fascicolo))
    fatti = registro.fatti(tenant, fascicolo_id, verifiche=None)
    return {
        "id": fascicolo_id,
        "titolo": _testo(getattr(fascicolo, "titolo", ""))[:60],
        "ciclo": stato.stato,
        "motivo": stato.motivo,
        "fatti": len(fatti),
        "_fatti": fatti,
    }


def verifica(fascicolo_id: str = "") -> dict[str, Any]:
    """Lo stato reale della catena per lo studio corrente."""
    from pct.archivio_letture.distribuzione import PRESIDI, categorie_senza_presidio, distribuzione_attesa
    from web.helpers import get_fascicoli
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    esito: dict[str, Any] = {"ok": True, "problemi": [], "registro": {}, "fascicoli": [], "fatti": {}, "presidi": {}, "sprechi": {}}
    try:
        registro = registro_corrente()
        tenant = tenant_corrente()
        esito["registro"] = {"aperto": True, "percorso": str(getattr(registro, "db_path", "")), "backend": getattr(registro, "backend_kind", ""), "tenant": tenant}
    except Exception as exc:
        esito["ok"] = False
        esito["registro"] = {"aperto": False, "motivo": f"{type(exc).__name__}: {exc}"}
        esito["problemi"].append(f"Il registro delle letture non si apre: {type(exc).__name__}: {exc}. Tutta la catena è ferma.")
        return esito

    fascicoli = [f for f in get_fascicoli().tutti(archiviati=True) if not fascicolo_id or _testo(getattr(f, "id", "")) == fascicolo_id]
    if fascicolo_id and not fascicoli:
        esito["ok"] = False
        esito["problemi"].append(f"Fascicolo {fascicolo_id} non trovato.")
        return esito

    per_categoria: dict[str, dict[str, int]] = {}
    tutti_fatti: list[Any] = []
    conteggi_ciclo = {"fermo": 0, "da_leggere": 0, "in_errore": 0}
    for fascicolo in fascicoli:
        try:
            riga = _stato_fascicolo(fascicolo, registro, tenant)
        except Exception as exc:
            esito["ok"] = False
            esito["problemi"].append(f"Fascicolo {_testo(getattr(fascicolo, 'id', ''))}: stato del ciclo non leggibile ({type(exc).__name__}: {exc}).")
            continue
        conteggi_ciclo[riga["ciclo"]] = conteggi_ciclo.get(riga["ciclo"], 0) + 1
        for fatto in riga.pop("_fatti"):
            tutti_fatti.append(fatto)
            voce = per_categoria.setdefault(str(fatto.categoria), {})
            voce[str(fatto.verifica)] = voce.get(str(fatto.verifica), 0) + 1
        esito["fascicoli"].append(riga)
    esito["ciclo"] = conteggi_ciclo
    esito["fatti"] = per_categoria

    if conteggi_ciclo.get("in_errore"):
        esito["ok"] = False
        for riga in esito["fascicoli"]:
            if riga["ciclo"] == "in_errore":
                esito["problemi"].append(f"Fascicolo {riga['id']} in errore nel ciclo: {riga['motivo']}")

    attesa = distribuzione_attesa(tutti_fatti)
    for presidio in PRESIDI:
        spettanti = attesa.get(presidio.nome) or []
        da_prendere = 0
        for fascicolo in fascicoli:
            fid = _testo(getattr(fascicolo, "id", ""))
            suoi = [f for f in spettanti if _testo(getattr(f, "fascicolo_id", "")) == fid]
            if suoi:
                da_prendere += len(registro.da_consegnare(tenant, fid, presidio.nome, suoi))
        esito["presidi"][presidio.nome] = {
            "etichetta": presidio.etichetta,
            "spettanti": len(spettanti),
            "da_prendere": da_prendere,
            "presi": len(spettanti) - da_prendere,
        }

    senza = categorie_senza_presidio(tutti_fatti)
    if senza:
        esito["sprechi"]["categorie_senza_presidio"] = senza
        esito["problemi"].append(
            "Categorie lette dai motori che nessun presidio dichiara di usare: "
            + ", ".join(f"{categoria} ({quanti})" for categoria, quanti in sorted(senza.items()))
        )
    return esito


def stampa(esito: dict[str, Any]) -> None:
    registro = esito.get("registro") or {}
    print("=" * 78)
    print("CATENA DELLE LETTURE — stato reale dello studio")
    print("=" * 78)
    if not registro.get("aperto"):
        print(f"\n  REGISTRO NON DISPONIBILE: {registro.get('motivo')}")
        print("  Tutta la catena è ferma: nessun motore legge, nessun presidio riceve.\n")
        return
    print(f"\nRegistro: {registro.get('percorso')} ({registro.get('backend')}) · studio «{registro.get('tenant')}»")

    ciclo = esito.get("ciclo") or {}
    print(f"\nCICLO DEI DUE MOTORI — {sum(ciclo.values())} fascicoli")
    print(f"  fermi (tutto letto e confermato) : {ciclo.get('fermo', 0)}")
    print(f"  da leggere                       : {ciclo.get('da_leggere', 0)}")
    print(f"  in errore                        : {ciclo.get('in_errore', 0)}")
    non_fermi = [riga for riga in esito.get("fascicoli") or [] if riga["ciclo"] != "fermo"]
    for riga in non_fermi[:10]:
        print(f"    · {riga['id']} {riga['titolo'][:38]:40} {riga['ciclo']}: {riga['motivo'][:60]}")
    if len(non_fermi) > 10:
        print(f"    · e altri {len(non_fermi) - 10}")

    print("\nCHE COSA HANNO SCRITTO I MOTORI")
    fatti = esito.get("fatti") or {}
    if not fatti:
        print("  nessun fatto in archivio: i motori non hanno ancora letto nulla")
    for categoria, verdetti in sorted(fatti.items()):
        dettaglio = " · ".join(f"{verdetto} {quanti}" for verdetto, quanti in sorted(verdetti.items()))
        print(f"  {categoria:16} {sum(verdetti.values()):5}   {dettaglio}")

    print("\nCONSEGNE AI PRESÌDI")
    for nome, voce in (esito.get("presidi") or {}).items():
        stato = "tutto consegnato" if voce["da_prendere"] == 0 else f"{voce['da_prendere']} da consegnare"
        print(f"  {voce['etichetta']:24} spettanti {voce['spettanti']:5} · presi {voce['presi']:5} · {stato}")

    problemi = esito.get("problemi") or []
    in_sospeso = sum(int(voce.get("da_prendere") or 0) for voce in (esito.get("presidi") or {}).values())
    da_leggere = int((esito.get("ciclo") or {}).get("da_leggere") or 0)
    print("\n" + "-" * 78)
    if problemi:
        print("LA CATENA HA PROBLEMI:")
        for problema in problemi:
            print(f"  · {problema}")
    elif da_leggere or in_sospeso:
        print("CATENA IN CORSO, senza rotture:")
        if da_leggere:
            print(f"  · {da_leggere} fascicoli attendono il prossimo giro dei motori")
        if in_sospeso:
            print(f"  · {in_sospeso} fatti sono nell'archivio e attendono di essere presi dai presìdi")
    else:
        print("CATENA COMPLETA E FERMA: i motori hanno letto, l'archivio ha registrato,")
        print("i presìdi hanno preso tutto. Riparte solo su un documento nuovo o una PEC nuova.")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Autocontrollo della catena delle letture sui dati reali.")
    parser.add_argument("--fascicolo", default="", help="limita l'esame a un solo fascicolo")
    parser.add_argument("--json", action="store_true", help="esito in JSON invece che leggibile")
    argomenti = parser.parse_args()

    from web.app import create_app

    app = create_app()
    with app.test_request_context("/__verifica-catena-letture"):
        esito = verifica(argomenti.fascicolo.strip())
    esito.pop("fascicoli", None) if argomenti.json and len(esito.get("fascicoli") or []) > 50 else None
    if argomenti.json:
        print(json.dumps(esito, ensure_ascii=False, indent=2, default=str))
    else:
        stampa(esito)
    return 0 if esito.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
