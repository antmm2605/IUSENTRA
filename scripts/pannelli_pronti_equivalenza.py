"""Verifica di equivalenza dei pannelli pronti su tutti i fascicoli di uno studio.

Fase «salva»: per ogni fascicolo e pannello fa la richiesta GET come l'avvocato (il pannello si calcola e si salva
con l'impronta delle fonti). Fase «confronta», in un processo nuovo e con i pannelli pronti disattivati: ricalcola
da zero ogni pannello e lo confronta con il payload salvato, controllando che l'impronta salvata sia ancora quella
attuale. Fase «ricalcola», in un processo nuovo: rifà da zero il calcolo del pannello come il calcolatore in sfondo
(stesso percorso del salvataggio, cache interne escluse) e confronta il payload salvato prima con quello appena
ricalcolato, a parità di impronta; serve a verificare i pannelli preparati dalla copertura, compresi quelli che
salvano parti in più per la ricomposizione (per esempio il Quadro). Usare solo su una copia dei dati: il ricalcolo
riscrive l'archivio dei pannelli. Ammessi solo i campi di orario di generazione elencati in ``CAMPI_ORARIO``.

Uso (nel contenitore, su una copia dei dati):
  python -m scripts.pannelli_pronti_equivalenza --tenant <slug> --utente <id> --fase salva --report r.jsonl
  python -m scripts.pannelli_pronti_equivalenza --tenant <slug> --utente <id> --fase confronta --report r.jsonl
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Campi che dicono quando e in quanto tempo il payload è stato generato: cambiano a ogni calcolo e non sono dati
# del fascicolo (``tempiMs`` è la durata delle fasi lente del dettaglio, a fini diagnostici).
CAMPI_ORARIO = frozenset({"generatedAt", "generated_at", "generato_il", "generatoIl", "calcolato_il", "calcolatoIl",
                          "tempiMs"})


# Orari dei controlli della regia: il motore registra quando ha eseguito ogni verifica (ora del calcolo).
CAMPI_ORARIO_DEI_CONTROLLI = frozenset({"lastCheck", "created_at"})


def normalizza(valore, dentro_controlli=False):
    if isinstance(valore, dict):
        return {k: ("<orario>" if k in CAMPI_ORARIO or (dentro_controlli and k in CAMPI_ORARIO_DEI_CONTROLLI)
                    else normalizza(v, dentro_controlli or k == "validation")) for k, v in valore.items()}
    if isinstance(valore, list):
        return [normalizza(v, dentro_controlli) for v in valore]
    return valore


def differenze(a, b, percorso="$", limite=8):
    trovate = []
    if type(a) is not type(b):
        return [f"{percorso}: {type(a).__name__} ≠ {type(b).__name__}"]
    if isinstance(a, dict):
        for chiave in sorted(set(a) | set(b)):
            if chiave not in a or chiave not in b:
                trovate.append(f"{percorso}.{chiave}: presente solo da una parte")
            else:
                trovate.extend(differenze(a[chiave], b[chiave], f"{percorso}.{chiave}", limite))
            if len(trovate) >= limite:
                break
    elif isinstance(a, list):
        if len(a) != len(b):
            trovate.append(f"{percorso}: {len(a)} ≠ {len(b)} elementi")
        for indice, (x, y) in enumerate(zip(a, b)):
            trovate.extend(differenze(x, y, f"{percorso}[{indice}]", limite))
            if len(trovate) >= limite:
                break
    elif isinstance(a, str) and isinstance(b, str) and a != b:
        # Testi lunghi: si mostra il punto in cui divergono.
        punto = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        inizio = max(0, punto - 40)
        trovate.append(f"{percorso} (dal carattere {punto}): {a[inizio:punto + 80]!r} ≠ {b[inizio:punto + 80]!r}")
    elif a != b:
        trovate.append(f"{percorso}: {str(a)[:80]!r} ≠ {str(b)[:80]!r}")
    return trovate[:limite]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--utente", required=True)
    parser.add_argument("--fase", choices=("salva", "confronta", "ricalcola"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--fascicoli", default="")
    parser.add_argument("--pannelli", default="")
    parser.add_argument("--da", type=int, default=0)
    parser.add_argument("--a", type=int, default=10**6)
    args = parser.parse_args()
    os.environ["IUSENTRA_STARTUP_GOVERNANCE_CHILD"] = "1"
    from web.app import create_app
    from web.services.pannelli_pronti_catalogo import PANNELLI

    app = create_app()
    if args.fase == "confronta":
        app.config["PANNELLI_PRONTI_DISATTIVI"] = True
    client = app.test_client()
    with client.session_transaction() as sessione:
        sessione.update({"user_id": args.utente, "auth_scope": "tenant", "auth_tenant_slug": args.tenant,
                         "tenant_slug": args.tenant})
    pannelli = [p for p in PANNELLI if p.percorso and (not args.pannelli or p.nome in args.pannelli.split(","))]
    with app.test_request_context("/__equivalenza"):
        from flask import g
        from pct.tenant import GestioneTenant
        from web.services.fascicoli_presidi_runtime import _attach_tenant_context

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        _attach_tenant_context(manager, manager.get(args.tenant))
        data_paths = dict(g.data_paths)
        import sqlite3

        conn = sqlite3.connect(f"file:{data_paths['STUDIO_DB']}?mode=ro", uri=True)
        fascicoli = [r[0] for r in conn.execute(
            "SELECT id FROM fascicoli WHERE UPPER(COALESCE(stato,''))<>'ARCHIVIATO' ORDER BY id").fetchall()]
        conn.close()
    if args.fascicoli:
        fascicoli = [f for f in fascicoli if f in set(args.fascicoli.split(","))]
    fascicoli = fascicoli[args.da:args.a]
    from pct.pannelli_pronti import impronta as impronta_fonti
    from web.services.pannelli_pronti_catalogo import VERSIONE_PANNELLI
    from web.services.pannelli_pronti_runtime import archivio_per_percorsi, fonti_per_percorsi

    archivio, fonti = archivio_per_percorsi(data_paths), fonti_per_percorsi(data_paths)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("a", encoding="utf-8") as report:
        for indice, fascicolo_id in enumerate(fascicoli):
            for pannello in pannelli:
                url = pannello.percorso.format(fid=fascicolo_id)
                if args.fase == "ricalcola":
                    report.write(json.dumps(_ricalcola(client, archivio, fascicolo_id, pannello, url),
                                            ensure_ascii=False) + "\n")
                    report.flush()
                    continue
                inizio = time.monotonic()
                risposta = client.get(url, headers={"Accept": "application/json"})
                durata = int((time.monotonic() - inizio) * 1000)
                riga = {"fase": args.fase, "fascicolo": fascicolo_id, "pannello": pannello.nome, "ms": durata,
                        "stato": risposta.status_code, "esito": risposta.headers.get("X-Iusentra-Pannello", "")}
                if args.fase == "confronta":
                    voce = _voce_salvata(archivio, fascicolo_id, pannello)
                    if voce is None:
                        riga["confronto"] = "non salvato"
                    else:
                        attuale = impronta_fonti.impronta(fonti, fascicolo_id,
                                                          generazione=archivio.generazione(fascicolo_id),
                                                          versione=VERSIONE_PANNELLI)
                        salvato = json.loads(bytes(voce.corpo).decode("utf-8"))
                        nuovo = json.loads(risposta.get_data().decode("utf-8"))
                        if pannello.ricomponi:  # le novità personali si ricompongono a ogni apertura
                            salvato.get("letture", {}).pop("novita", None)
                            nuovo.get("letture", {}).pop("novita", None)
                        diff = differenze(normalizza(salvato), normalizza(nuovo))
                        riga.update(confronto="uguale" if not diff else "diverso", differenze=diff,
                                    impronta_valida=voce.impronta == attuale)
                report.write(json.dumps(riga, ensure_ascii=False) + "\n")
                report.flush()
            print(f"{indice + 1}/{len(fascicoli)} {fascicolo_id}", file=sys.stderr, flush=True)


def _ricalcola(client, archivio, fascicolo_id, pannello, url):
    """Payload salvato prima contro payload ricalcolato da zero con lo stesso percorso del calcolo in sfondo."""
    from web.services.pannelli_pronti_runtime import AMBIENTE_RICALCOLO

    riga = {"fase": "ricalcola", "fascicolo": fascicolo_id, "pannello": pannello.nome}
    prima = _voce_salvata(archivio, fascicolo_id, pannello)
    if prima is None:
        return {**riga, "confronto": "non salvato"}
    inizio = time.monotonic()
    risposta = client.get(url, headers={"Accept": "application/json"},
                          environ_overrides={AMBIENTE_RICALCOLO: True, "REMOTE_ADDR": "127.0.0.1"})
    riga.update(ms=int((time.monotonic() - inizio) * 1000), stato=risposta.status_code,
                esito=risposta.headers.get("X-Iusentra-Pannello", ""))
    dopo = archivio.voce(prima.chiave)
    if risposta.headers.get("X-Iusentra-Pannello") != "calcolato" or dopo is None or dopo.calcolato_il == prima.calcolato_il:
        return {**riga, "confronto": "ricalcolo non salvato"}
    salvato = json.loads(bytes(prima.corpo).decode("utf-8"))
    nuovo = json.loads(bytes(dopo.corpo).decode("utf-8"))
    if pannello.ricomponi:  # le novità personali si ricompongono a ogni apertura
        for dati in (salvato, nuovo):
            (dati.get("letture") or {}).pop("novita", None) if isinstance(dati, dict) else None
    diff = differenze(normalizza(salvato), normalizza(nuovo))
    return {**riga, "confronto": "uguale" if not diff else "diverso", "differenze": diff,
            "impronta_valida": prima.impronta == dopo.impronta}


def _voce_salvata(archivio, fascicolo_id, pannello):
    """La voce salvata per il percorso canonico del pannello (qualunque profilo dell'utente della verifica)."""
    import sqlite3

    conn = sqlite3.connect(archivio.percorso)
    try:
        # Solo la richiesta canonica (senza parametri): è quella che la fase di confronto ricalcola.
        riga = conn.execute("SELECT chiave FROM pannelli WHERE fascicolo_id=? AND pannello=? AND impronta<>'' "
                            "AND corpo IS NOT NULL AND percorso=? ORDER BY calcolato_il DESC LIMIT 1",
                            (fascicolo_id, pannello.nome, pannello.percorso.format(fid=fascicolo_id))).fetchone()
    finally:
        conn.close()
    return archivio.voce(riga[0]) if riga else None


if __name__ == "__main__":
    main()
