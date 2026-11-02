"""Contributi Cassa Forense: soggettivo, integrativo e maternità per l'anno di competenza.

Base normativa (testi scaricati da cassaforense.it e consultati il 31/10/2026):
- Regolamento unico della previdenza forense (delibera del Comitato dei Delegati
  del 23/05/2024, approvato con ministeriale del 27/09/2024, G.U. Serie Generale
  n. 238 del 10/10/2024, comunicato 24A05286), in vigore dal 01/01/2025:
  https://www.cassaforense.it/media/pedlynkt/regolamento-unico-previdenza-forense.pdf
  * art. 30, cc. 1-2: contributo soggettivo 16% per il 2025, 17% per il 2026,
    18% dal 2027 fino al tetto reddituale; 3% sul reddito eccedente il tetto;
  * art. 30, c. 3 e art. 37, c. 3: pensionati di vecchiaia iscritti all'Albo,
    12% fino al tetto e 3% oltre, senza contributo minimo soggettivo;
  * art. 31, c. 7: contributo integrativo 4% sul volume d'affari IVA (c. 2:
    sul lordo fatturato per chi è in regime fiscale agevolato);
  * art. 32: contributo di maternità determinato annualmente dal CdA;
  * art. 37, cc. 1-2: contributi minimi (2.750 e 350 euro per il 2025), ridotti
    alla metà per i primi 6 anni se la prima iscrizione precede il 35° anno;
  * art. 41, cc. 1-2: importi in autoliquidazione arrotondati all'euro più vicino;
    pagamento non dovuto se l'eccedenza non supera i dieci euro.
- Note illustrative Mod. 5/2026 (redditi 2025), punto C: il minimo soggettivo copre
  il reddito fino a 17.188 euro; oltre è dovuto il 16% sul reddito eccedente
  17.188 euro fino al tetto, anche per chi versa il minimo ridotto:
  https://www.cassaforense.it/media/btuftmyc/note-illustrative-mod5-2026.pdf
- Tabella ufficiale dei contributi minimi (minimi, soglie di copertura, tetti e
  contributo di maternità per anno; maternità 2026 «da definire»):
  https://www.cassaforense.it/media/pkxmzmvw/tabella-contributi-minimi.pdf

Perimetro dichiarato: gli anni di competenza regolati dal Regolamento unico in
vigore dal 2025 e pubblicati nella tabella ufficiale. Gli anni fino al 2024
(regolamento previgente) e quelli i cui minimi e tetto non sono ancora pubblicati
sono rifiutati con il motivo. Non calcola esoneri temporanei (art. 40), contributo
modulare volontario (art. 33), sanzioni e interessi.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, fmt_eur, safe_float, safe_int

PRIMO_ANNO_REGOLAMENTO_UNICO = 2025
SOGLIA_ECCEDENZA_NON_DOVUTA = 10.0  # art. 41, c. 2, Regolamento unico

POSIZIONI = {
    "ordinaria": "Iscritto alla Cassa (contributi minimi interi)",
    "agevolata": "Primi 6 anni di iscrizione, iscritto prima dei 35 anni (minimi ridotti alla metà)",
    "pensionato": "Pensionato di vecchiaia ancora iscritto all'Albo",
}


def _euro(valore: float) -> float:
    """Arrotondamento all'euro più vicino (art. 41, c. 1, Regolamento unico)."""
    return float(Decimal(str(valore)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _cent(valore: float) -> float:
    return float(Decimal(str(valore)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _righe_anno(norme: Any, anno: int) -> Dict[str, Dict[str, Any]]:
    """Righe della tabella per l'anno esatto: nessun ripiego su un altro anno."""
    righe = [r for r in norme.rows("contributi_cassa_forense") if safe_int(r.get("year")) == anno]
    return {str(r.get("tipo") or ""): dict(r) for r in righe}


def _anni_disponibili(norme: Any) -> List[int]:
    return sorted({safe_int(r.get("year")) for r in norme.rows("contributi_cassa_forense")})


def _eccedenza(importo: float, notes: List[str], voce: str) -> float:
    """Autoliquidazione: euro più vicino e soglia dei dieci euro (art. 41, cc. 1-2)."""
    arrotondato = _euro(importo)
    if 0 < arrotondato <= SOGLIA_ECCEDENZA_NON_DOVUTA:
        notes.append(
            f"{voce}: eccedenza di {arrotondato:.0f} euro non dovuta perché non supera i dieci euro "
            "(art. 41, c. 2, Regolamento unico)."
        )
        return 0.0
    return arrotondato


def calcola(payload: Mapping[str, Any], norme: Any, *, anno_corrente: int) -> Dict[str, Any]:
    anno = safe_int(payload.get("cf_anno")) or anno_corrente
    reddito = max(0.0, safe_float(payload.get("cf_reddito")))
    volume = max(0.0, safe_float(payload.get("cf_compensi")))
    posizione = clean_text(payload.get("cf_posizione")) or "ordinaria"
    if posizione not in POSIZIONI:
        raise ValueError("Posizione contributiva non riconosciuta: scegliere fra ordinaria, agevolata e pensionato.")

    if anno < PRIMO_ANNO_REGOLAMENTO_UNICO:
        raise ValueError(
            f"Il {anno} è regolato dal Regolamento unico previgente (fino al 31/12/2024): "
            "il calcolatore copre gli anni dal 2025, regolati dal Regolamento unico approvato "
            "con ministeriale del 27/09/2024."
        )
    righe = _righe_anno(norme, anno)
    sogg, integ = righe.get("soggettivo"), righe.get("integrativo")
    if not sogg or not integ:
        disponibili = ", ".join(str(a) for a in _anni_disponibili(norme)) or "nessuno"
        raise ValueError(
            f"Minimi, soglia di copertura e tetto reddituale Cassa Forense per il {anno} non risultano "
            f"pubblicati nella tabella ufficiale (anni disponibili: {disponibili}). "
            "Il calcolo non viene eseguito per non usare valori non ufficiali."
        )

    notes: List[str] = []
    warnings: List[str] = []

    # ── Contributo soggettivo (artt. 30 e 37 Regolamento unico) ──────────────
    aliquota = float(sogg["aliquota"])
    tetto = float(sogg["tetto_eur"])
    aliquota_oltre = float(sogg["aliquota_oltre_tetto"])
    oltre_tetto = max(0.0, reddito - tetto) * aliquota_oltre / 100.0
    if posizione == "pensionato":
        aliquota_usata = float(sogg["aliquota_pensionati"])
        minimo_sogg = 0.0
        fino_tetto = min(reddito, tetto) * aliquota_usata / 100.0
        notes.append(
            f"Pensionato di vecchiaia: {aliquota_usata:.0f}% fino al tetto di {fmt_eur(tetto)} euro e "
            f"{aliquota_oltre:.0f}% oltre, senza contributo minimo soggettivo (art. 30, c. 3, e art. 37, c. 3)."
        )
    else:
        aliquota_usata = aliquota
        minimo_sogg = float(sogg["minimo_ridotto_eur"] if posizione == "agevolata" else sogg["minimo_eur"])
        copertura = float(sogg["copertura_eur"])
        fino_tetto = max(0.0, min(reddito, tetto) - copertura) * aliquota / 100.0
        notes.append(
            f"Contributo soggettivo: minimo di {fmt_eur(minimo_sogg)} euro (copre il reddito fino a "
            f"{fmt_eur(copertura)} euro) più il {aliquota:g}% sul reddito eccedente fino al tetto di "
            f"{fmt_eur(tetto)} euro e il {aliquota_oltre:g}% oltre il tetto (art. 30 e art. 37 Regolamento unico)."
        )
    ecc_sogg = _eccedenza(fino_tetto + oltre_tetto, notes, "Contributo soggettivo")
    totale_sogg = _cent(minimo_sogg + ecc_sogg)

    # ── Contributo integrativo (artt. 31 e 37) ────────────────────────────────
    aliquota_int = float(integ["aliquota"])
    minimo_int = float(integ["minimo_ridotto_eur"] if posizione == "agevolata" else integ["minimo_eur"])
    dovuto_int = volume * aliquota_int / 100.0
    ecc_int = _eccedenza(max(0.0, dovuto_int - minimo_int), notes, "Contributo integrativo")
    totale_int = _cent(minimo_int + ecc_int)
    if dovuto_int < minimo_int:
        notes.append(
            f"Contributo integrativo: {aliquota_int:g}% del volume d'affari ({fmt_eur(_cent(dovuto_int))} euro) "
            f"inferiore al minimo di {fmt_eur(minimo_int)} euro: è dovuto il minimo (art. 37)."
        )
    notes.append(
        f"Il contributo integrativo del {aliquota_int:g}% si applica in fattura ed è ripetibile nei confronti "
        "del cliente (art. 31, c. 4); chi è in regime fiscale agevolato lo calcola sul lordo fatturato (art. 31, c. 2)."
    )

    # ── Contributo di maternità (art. 32) ─────────────────────────────────────
    mat = righe.get("maternita_assistenza") or {}
    mat_da_definire = not mat or mat.get("status") == "da_definire"
    importo_mat = 0.0 if mat_da_definire else float(mat.get("minimo_eur") or 0.0)
    if mat_da_definire:
        warnings.append(
            f"Contributo di maternità {anno}: da definire nella tabella ufficiale Cassa Forense; "
            "non è incluso nel totale, che resta provvisorio."
        )

    if posizione == "agevolata":
        notes.append(
            "Minimi soggettivo e integrativo ridotti alla metà per i primi 6 anni di iscrizione alla Cassa "
            "con prima iscrizione anteriore al 35° anno di età; le aliquote in autoliquidazione restano invariate "
            "(art. 37, c. 2)."
        )
    notes.append(
        "Scadenze: minimi e maternità in quattro rate (28 febbraio, 30 aprile, 30 giugno, 30 settembre); "
        "Mod. 5 entro il 30 settembre dell'anno successivo; eccedenze in autoliquidazione in due rate "
        "del 50% al 30 settembre e al 31 dicembre (art. 38 e art. 41, c. 7)."
    )

    contributi = [
        {
            "tipo": "soggettivo",
            "label": f"Contributo soggettivo {anno}",
            "base": "reddito_netto_professionale",
            "aliquota": aliquota_usata,
            "minimo_eur": minimo_sogg,
            "base_usata": _cent(reddito),
            "eccedenza": ecc_sogg,
            "calcolato": totale_sogg,
            "note": str(sogg.get("note") or ""),
        },
        {
            "tipo": "integrativo",
            "label": f"Contributo integrativo {anno}",
            "base": "volume_affari_iva",
            "aliquota": aliquota_int,
            "minimo_eur": minimo_int,
            "base_usata": _cent(volume),
            "eccedenza": ecc_int,
            "calcolato": totale_int,
            "note": str(integ.get("note") or ""),
        },
        {
            "tipo": "maternita_assistenza",
            "label": f"Contributo di maternità {anno}",
            "base": "importo_fisso",
            "aliquota": 0.0,
            "minimo_eur": importo_mat,
            "base_usata": 0.0,
            "eccedenza": 0.0,
            "calcolato": importo_mat,
            "note": str(mat.get("note") or ""),
            "status": "da_definire" if mat_da_definire else "definito",
        },
    ]
    return {
        "anno": anno,
        "posizione": posizione,
        "posizione_label": POSIZIONI[posizione],
        "reddito": _cent(reddito),
        "compensi": _cent(volume),
        "soggettivo_minimo": minimo_sogg,
        "soggettivo_eccedenza": ecc_sogg,
        "soggettivo_totale": totale_sogg,
        "integrativo_minimo": minimo_int,
        "integrativo_eccedenza": ecc_int,
        "integrativo_totale": totale_int,
        "maternita": importo_mat,
        "contributi": contributi,
        "totale": _cent(totale_sogg + totale_int + importo_mat),
        "totale_provvisorio": mat_da_definire,
        "notes": notes,
        "warnings": warnings,
    }


__all__ = ["POSIZIONI", "calcola"]
