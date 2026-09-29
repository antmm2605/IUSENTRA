"""Registro delle fatture emesse e IVA a debito per periodo.

- Art. 23 D.P.R. 633/1972: le fatture emesse si annotano nell'ordine della numerazione con data, numero,
  cliente, imponibile, aliquota e imposta.
- Art. 1 c. 3 D.Lgs. 127/2015: dal 2019 (dal 2024 anche per i forfettari) la fattura è elettronica e
  si considera emessa con la trasmissione allo SdI: qui entrano solo le parcelle trasmesse; le altre
  sono avvisi di parcella (proforma) e restano fuori, con il loro conteggio.
- Art. 1 c. 3 D.P.R. 100/1998 e art. 7 D.P.R. 542/1999: liquidazione mensile o trimestrale; nel
  trimestrale l'imposta dovuta si maggiora dell'1% (qui indicato, non versato).
- Regime forfettario (L. 190/2014): niente IVA in fattura e niente registri IVA.
- Scissione dei pagamenti (art. 17-ter D.P.R. 633/1972) per le fatture a pubbliche amministrazioni:
  l'IVA la versa l'ente; se indicata nella parcella è esclusa dall'IVA a debito.
"""

from __future__ import annotations

import csv
import io
from typing import Any

STATI_ESCLUSI = {"BOZZA", "ANNULLATA"}


def _trasmessa(parcella: Any) -> bool:
    return bool(str(getattr(parcella, "sdi_identificativo", "") or "").strip()
                or str(getattr(parcella, "sdi_data_invio", "") or "").strip())


def _split_payment(parcella: Any) -> bool:
    dati = getattr(parcella, "dati_personalizzati", {}) or {}
    documento = dati.get("document", {}) if isinstance(dati, dict) else {}
    esigibilita = str((documento or {}).get("esigibilita_iva") or "").strip().upper() if isinstance(documento, dict) else ""
    return esigibilita == "S"


def registro_fatture_emesse(fatturazione: Any, anno: int, *, periodicita: str = "trimestrale") -> dict[str, Any]:
    righe: list[dict[str, Any]] = []
    proforma = 0
    periodi: dict[str, float] = {}
    for p in fatturazione.tutte():
        stato = str(getattr(getattr(p, "stato", ""), "value", getattr(p, "stato", "")) or "")
        if stato in STATI_ESCLUSI or not str(p.data_emissione or "").startswith(str(anno)):
            continue
        if not _trasmessa(p):
            proforma += 1
            continue
        split = _split_payment(p)
        mese = int(p.data_emissione[5:7])
        periodo = f"{(mese - 1) // 3 + 1}° trimestre" if periodicita == "trimestrale" else f"{mese:02d}/{anno}"
        iva = round(float(p.iva), 2)
        if not split:
            periodi[periodo] = round(periodi.get(periodo, 0.0) + iva, 2)
        righe.append({
            "numero": p.numero, "data": p.data_emissione, "cliente": getattr(p, "id_cliente", ""),
            "imponibile": round(float(p.imponibile), 2), "cassa_forense": round(float(p.cassa_forense), 2),
            "aliquota_iva": float(p.aliquota_iva) if p.iva_applicabile else 0.0, "iva": iva,
            "esigibilita": "scissione dei pagamenti" if split else "immediata",
            "totale_documento": round(float(p.totale_documento), 2), "periodo": periodo,
        })
    righe.sort(key=lambda r: (r["data"], r["numero"]))
    liquidazioni = []
    for periodo, iva in sorted(periodi.items()):
        riga = {"periodo": periodo, "iva_a_debito": iva}
        if periodicita == "trimestrale" and not periodo.startswith("4"):
            riga["interessi_1_per_cento"] = round(iva * 0.01, 2)
        liquidazioni.append(riga)
    return {
        "anno": int(anno), "fatture": righe, "liquidazioni": liquidazioni, "proforma_escluse": proforma,
        "totale_imponibile": round(sum(r["imponibile"] for r in righe), 2),
        "totale_iva": round(sum(r["iva"] for r in righe if r["esigibilita"] == "immediata"), 2),
        "note": [
            "Entrano le fatture trasmesse allo SdI; le parcelle non trasmesse sono avvisi di parcella (proforma).",
            "L'IVA sugli acquisti (fatture passive) non è registrata in IUSENTRA: la liquidazione mostra solo l'IVA a "
            "debito; la detrazione la calcola il commercialista.",
            "Nel trimestrale l'imposta dei primi tre trimestri si maggiora dell'1% (art. 7 D.P.R. 542/1999); il "
            "quarto trimestre si liquida in dichiarazione.",
        ],
    }


def csv_registro(registro: dict[str, Any]) -> str:
    buffer = io.StringIO()
    scrittore = csv.writer(buffer, delimiter=";")
    scrittore.writerow(["Numero", "Data", "Cliente", "Imponibile", "Cassa forense", "Aliquota IVA", "IVA",
                        "Esigibilità", "Totale documento", "Periodo"])
    for r in registro["fatture"]:
        scrittore.writerow([r["numero"], r["data"], r["cliente"], f"{r['imponibile']:.2f}".replace(".", ","),
                            f"{r['cassa_forense']:.2f}".replace(".", ","), f"{r['aliquota_iva']:g}",
                            f"{r['iva']:.2f}".replace(".", ","), r["esigibilita"],
                            f"{r['totale_documento']:.2f}".replace(".", ","), r["periodo"]])
    return "﻿" + buffer.getvalue()


__all__ = ["csv_registro", "registro_fatture_emesse"]
