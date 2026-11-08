#!/usr/bin/env python3
"""Riallinea al regime fiscale dello studio le proforma create con un trattamento IVA diverso.

Caso: studio in regime forfetario (RF19) con proforma predisposte con IVA. Nel forfetario la
prestazione non sconta IVA (art. 1, commi 54-89, in particolare comma 58, L. 190/2014: natura N2.2)
né ritenuta (comma 67); il contributo integrativo Cassa forense 4% resta (art. 11 L. 576/1980); il
bollo di € 2 segue la regola di legge (art. 13 Tariffa all. A D.P.R. 642/1972, vedi
``pct.fatturazione_regime``). Nel regime ordinario (RF01) l'IVA si applica (artt. 3 e 16 D.P.R.
633/1972).

Uso (dentro il container dell'app, con i dati del tenant):
    python scripts/riallinea_proforma_regime_20261108.py --studio <slug>            # solo elenco
    python scripts/riallinea_proforma_regime_20261108.py --studio <slug> --scrivi   # corregge

Con ``--scrivi`` si correggono SOLO proforma in bozza, mai fatture, note di credito, documenti
inviati allo SdI, proforma convertite o con incassi: questi si elencano a parte «da decidere», con
le proforma nate da preventivo o conferimento (importo concordato con il cliente). Prima di
scrivere si salva una copia del database dello studio; ogni documento conserva i valori precedenti
in ``dati_personalizzati.storico_regime`` e ogni correzione lascia una riga di audit.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
ATTORE = "riallinea_proforma_regime_20261108"
MOTIVI = {
    "RF19": "regime forfettario RF19 – art. 1 c. 54-89 L. 190/2014",
    "RF02": "regime dei minimi RF02 – art. 27 D.L. 98/2011",
    "RF01": "regime ordinario RF01 – artt. 3 e 16 D.P.R. 633/1972",
}
_LABEL = {"RF01": "Regime ordinario", "RF02": "Regime dei minimi", "RF19": "Regime forfettario"}


def _document(parcella: Any) -> dict[str, Any]:
    data = parcella.dati_personalizzati if isinstance(parcella.dati_personalizzati, dict) else {}
    document = data.get("document")
    return document if isinstance(document, dict) else {}


def _e_proforma(parcella: Any) -> bool:
    return str(_document(parcella).get("documento_operativo") or "").strip().upper() == "PROFORMA"


def calcolo_corretto(parcella: Any, regime: str) -> dict[str, float | bool]:
    """Importi secondo il regime, calcolati per esteso (stesse regole di pct.fatturazione)."""
    from pct.fatturazione_regime import bollo_dovuto, esclusione_bollo, importo_non_soggetto_iva

    senza_iva = regime in {"RF19", "RF02"}
    base = round(float(parcella.base_iva), 2)
    aliquota = float(getattr(parcella, "aliquota_iva", 22.0) or 22.0)
    iva = 0.0 if senza_iva else round(base * aliquota / 100.0, 2)
    anticipazioni = round(float(parcella.totale_anticipazioni), 2)
    non_soggetto = importo_non_soggetto_iva(iva_applicabile=not senza_iva, base_iva=base, anticipazioni=anticipazioni)
    bollo = 2.0 if bollo_dovuto(iva_applicabile=not senza_iva, importo_non_soggetto=non_soggetto,
                                esclusione=esclusione_bollo(_document(parcella))) else 0.0
    addebitato = 0.0 if _document(parcella).get("bollo_a_carico_studio") is True else bollo
    ritenuta = 0.0 if senza_iva else round(float(parcella.ritenuta), 2)
    totale_documento = round(base + iva + addebitato + anticipazioni, 2)
    return {"applica_iva": not senza_iva, "iva": iva, "bollo": bollo, "totale_documento": totale_documento,
            "totale": round(totale_documento - ritenuta, 2), "ritenuta": ritenuta}


def _incassato(manager: Any, parcella: Any) -> bool:
    if parcella.data_pagamento or str(getattr(parcella.stato, "value", parcella.stato)) == "PAGATA":
        return True
    if isinstance((parcella.dati_personalizzati or {}).get("incassi_sql"), dict):
        return True
    try:
        from pct.parcella_incassi_views import balances_for_invoices

        saldo = balances_for_invoices(getattr(manager, "_studio_db", None), {parcella.id: parcella}).get(parcella.id) or {}
        return int(saldo.get("paid_cents") or 0) > 0
    except Exception:
        return False


def classifica(manager: Any, regime: str) -> dict[str, list[dict[str, Any]]]:
    """Proforma da correggere, da decidere e documenti esclusi (fiscali o già coerenti)."""
    esito: dict[str, list[dict[str, Any]]] = {"da_correggere": [], "da_decidere": [], "solo_bollo": []}
    senza_iva = regime in {"RF19", "RF02"}
    for p in manager.tutte():
        if not _e_proforma(p):
            continue  # fatture, note di credito e documenti fiscali: mai toccati
        doc = _document(p)
        iva_attuale = round(float(p.iva), 2)
        incoerente = (senza_iva and iva_attuale > 0) or (not senza_iva and not p.iva_applicabile) \
            or (str(doc.get("regime_fiscale") or "").upper() not in {"", regime})
        corretto = calcolo_corretto(p, regime)
        # Bollo rimasto spento (scelta predefinita dei vecchi moduli) dove la legge lo prevede.
        manca_bollo = p.applica_bollo is False and corretto["bollo"] > 0
        if not incoerente and not manca_bollo:
            continue
        riga = {"id": p.id, "numero": p.numero, "fascicolo": p.id_fascicolo or "", "cliente": p.id_cliente,
                "stato": str(getattr(p.stato, "value", p.stato)), "imponibile": round(float(p.imponibile), 2),
                "cpa": round(float(p.cassa_forense), 2), "iva_attuale": iva_attuale,
                "totale_attuale": round(float(p.totale), 2), "totale_corretto": corretto["totale"],
                "bollo_corretto": corretto["bollo"], "regime_documento": str(doc.get("regime_fiscale") or "")}
        motivi = []
        if riga["stato"] != "BOZZA":
            motivi.append(f"stato {riga['stato']}")
        if p.sdi_identificativo or p.sdi_stato:
            motivi.append("già inviata allo SdI")
        if isinstance((p.dati_personalizzati or {}).get("proforma"), dict) and p.dati_personalizzati["proforma"].get("convertita"):
            motivi.append("già convertita in fattura")
        if _incassato(manager, p):
            motivi.append("incassi registrati")
        if p.id_preventivo or "preventiv" in str(p.origine).lower() or "conferiment" in str(p.origine).lower():
            motivi.append("importo da preventivo/conferimento concordato con il cliente")
        if motivi:
            riga["motivi"] = motivi
            esito["da_decidere"].append(riga)
        elif incoerente:
            esito["da_correggere"].append(riga)
        else:
            esito["solo_bollo"].append(riga)
    return esito


def _backup(manager: Any) -> str:
    db = getattr(manager, "_studio_db", None)
    sorgente = getattr(db, "db_path", "") if db is not None else getattr(manager, "db_path", "")
    if not sorgente:
        raise RuntimeError("Archivio fatturazione non individuato: backup impossibile, nessuna scrittura.")
    stamp = datetime.now(ROME).strftime("%Y%m%d_%H%M%S")
    destinazione = Path(sorgente).with_name(f"{Path(sorgente).stem}.prima_riallinea_regime_{stamp}{Path(sorgente).suffix}")
    if db is not None:
        with sqlite3.connect(str(sorgente)) as src, sqlite3.connect(str(destinazione)) as dst:
            src.backup(dst)
    else:
        destinazione.write_bytes(Path(sorgente).read_bytes())
    return str(destinazione)


def correggi(manager: Any, righe: list[dict[str, Any]], regime: str, *, audit: Any = None) -> list[str]:
    from pct.fatturazione import parcella_revision

    adesso = datetime.now(ROME).replace(microsecond=0).isoformat()
    fatti = []
    for riga in righe:
        p = manager.get(riga["id"])
        if p is None or not _e_proforma(p) or str(getattr(p.stato, "value", p.stato)) != "BOZZA":
            continue
        corretto = calcolo_corretto(p, regime)
        dati = json.loads(json.dumps(p.dati_personalizzati or {}, ensure_ascii=False))
        document = dict(dati.get("document") or {})
        storico = list(dati.get("storico_regime") or [])
        cambia_regime = round(float(p.iva), 2) != corretto["iva"] or str(document.get("regime_fiscale") or "").upper() != regime
        motivo = MOTIVI.get(regime, regime) if cambia_regime else "imposta di bollo – art. 13 Tariffa all. A D.P.R. 642/1972"
        storico.append({"data": adesso, "motivo": motivo, "attore": ATTORE,
                        "prima": {"regime_fiscale": document.get("regime_fiscale", ""), "applica_iva": p.applica_iva,
                                  "applica_ritenuta": p.applica_ritenuta, "applica_bollo": p.applica_bollo,
                                  "iva": round(float(p.iva), 2), "totale_documento": round(float(p.totale_documento), 2),
                                  "totale": round(float(p.totale), 2)}})
        document.update({"regime_fiscale": regime, "regime_fiscale_label": _LABEL.get(regime, regime)})
        if regime in {"RF19", "RF02"}:
            document["natura_iva"] = "N2.2"
        dati["document"] = document
        dati["storico_regime"] = storico
        aggiornata = manager.aggiorna(
            p.id, expected_revision=parcella_revision(p) if getattr(manager, "_studio_db", None) is not None else None,
            applica_iva=bool(corretto["applica_iva"]), applica_ritenuta=False if regime in {"RF19", "RF02"} else p.applica_ritenuta,
            applica_bollo=None, dati_personalizzati=dati)
        if round(float(aggiornata.totale), 2) != corretto["totale"]:
            raise RuntimeError(f"Totale ricalcolato discordante per {p.id}: {aggiornata.totale} invece di {corretto['totale']}.")
        if callable(audit):
            audit("fatturazione.riallinea_regime", p.id,
                  f"regime={regime}; totale {riga['totale_attuale']:.2f} -> {corretto['totale']:.2f}; motivo={motivo}")
        fatti.append(p.id)
    return fatti


def _stampa(esito: dict[str, list[dict[str, Any]]], regime: str) -> None:
    print(f"Regime dello studio: {regime}")
    for chiave, titolo in (("da_correggere", "PROFORMA DA CORREGGERE (regime)"),
                           ("solo_bollo", "PROFORMA COERENTI COL REGIME MA SENZA IL BOLLO DOVUTO (--anche-bollo)"),
                           ("da_decidere", "CASI DA DECIDERE")):
        righe = esito[chiave]
        print(f"\n{titolo}: {len(righe)}")
        for r in righe:
            extra = f" | {', '.join(r['motivi'])}" if r.get("motivi") else ""
            print(f"{r['id'][:8]} {r['numero']:<14} fasc. {r['fascicolo'] or '-':<10} cliente {r['cliente'][:12]:<12} "
                  f"imp. {r['imponibile']:>9.2f} CPA {r['cpa']:>7.2f} IVA {r['iva_attuale']:>8.2f} "
                  f"totale {r['totale_attuale']:>9.2f} -> {r['totale_corretto']:>9.2f} bollo {r['bollo_corretto']:.2f}{extra}")
    tot = sum(r["totale_attuale"] - r["totale_corretto"] for r in esito["da_correggere"])
    print(f"\nDifferenza complessiva sulle proforma da correggere: € {tot:.2f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--studio", required=True, help="slug del tenant dello studio")
    parser.add_argument("--scrivi", action="store_true", help="corregge le proforma (default: solo elenco)")
    parser.add_argument("--anche-bollo", action="store_true",
                        help="con --scrivi corregge anche le proforma coerenti col regime ma senza il bollo dovuto")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pct.config_studio import GestioneConfigStudio
    from pct.scheduler_worker import create_scheduler_app
    from pct.tenant import GestioneTenant
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context

    app = create_scheduler_app()
    owner = next((o for o in GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]).lista() if o.slug == args.studio), None)
    if owner is None:
        print(f"Studio {args.studio} non trovato.")
        return 2
    with app.test_request_context("/__riallinea_regime"):
        _attach_tenant_context(GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"]), owner)
        from web import helpers

        regime = str(GestioneConfigStudio(config_path=helpers._cfg("CONFIG_STUDIO_DB")).config.fatturazione.regime_fiscale or "").upper()
        if regime not in MOTIVI:
            print("Regime fiscale dello studio non leggibile: nessuna operazione.")
            return 2
        manager = helpers.get_fatturazione()
        esito = classifica(manager, regime)
        _stampa(esito, regime)
        if not args.scrivi:
            print("\nSolo elenco: nessuna modifica. Per correggere usare --scrivi.")
            return 0
        print(f"\nCopia di sicurezza: {_backup(manager)}")
        utenti = helpers.get_utenti(carica_audit=False)

        def audit(azione: str, risorsa: str, dettagli: str) -> None:
            utenti.registra_evento(azione, username=ATTORE, risorsa_tipo="parcella", risorsa_id=risorsa, dettagli=dettagli)

        righe = esito["da_correggere"] + (esito["solo_bollo"] if args.anche_bollo else [])
        fatti = correggi(manager, righe, regime, audit=audit)
        print(f"Proforma corrette: {len(fatti)}; casi da decidere lasciati invariati: {len(esito['da_decidere'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
