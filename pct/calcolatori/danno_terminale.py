"""Danno terminale — tabella dell'Osservatorio di Milano, edizione 2024.

E' l'unica posta liquidabile iure proprio alla vittima di lesioni mortali
quando il decesso non e' immediato ma segue un apprezzabile lasso di tempo
(Cass. Sez. Un. 22 luglio 2015 n. 15350, che ha escluso il danno da morte
immediata).

La tabella distingue due tratti: i primi tre giorni, liquidati in via
equitativa entro un tetto complessivo e non personalizzabili; i giorni dal
quarto in poi, con un importo pro die decrescente e l'aumento per massimo
sconvolgimento fino al 50 per cento.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import parse_date, safe_float, safe_int
from pct.calcolatori.danno_biologico import tabelle, terminale


def _giorni(payload: Mapping[str, Any]) -> tuple:
    data_lesione = parse_date(payload.get("dt_data_lesione"))
    data_decesso = parse_date(payload.get("dt_data_decesso"))
    if data_lesione and data_decesso:
        if data_decesso < data_lesione:
            raise ValueError("La data del decesso non puo' precedere la data delle lesioni.")
        giorni = (data_decesso - data_lesione).days + 1
        return giorni, f"dal {data_lesione.strftime('%d/%m/%Y')} al {data_decesso.strftime('%d/%m/%Y')}"
    giorni = safe_int(payload.get("dt_giorni"))
    if giorni <= 0:
        raise ValueError("Indica i giorni di sopravvivenza, oppure la data delle lesioni e quella del decesso.")
    return giorni, f"{giorni} giorni indicati"


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    giorni, periodo = _giorni(payload)
    massimo_primi_tre = terminale.massimo_primi_tre_giorni()

    equita_richiesta = safe_float(payload.get("dt_importo_primi_tre"), -1.0)
    avvisi: List[str] = []
    if equita_richiesta < 0:
        primi_tre = massimo_primi_tre
        nota_primi_tre = "importo massimo tabellare (in mancanza di una diversa valutazione equitativa)"
    else:
        primi_tre = min(equita_richiesta, massimo_primi_tre)
        if equita_richiesta > massimo_primi_tre:
            avvisi.append(
                f"L'importo indicato per i primi tre giorni supera il tetto di "
                f"{massimo_primi_tre:.2f} €: e' stato ricondotto al massimo tabellare."
            )
        nota_primi_tre = "valutazione equitativa entro il tetto tabellare"
    primi_tre = round(primi_tre, 2)

    dettaglio: List[Dict[str, Any]] = [{
        "voce": f"Primi tre giorni ({min(giorni, 3)} su 3)",
        "importo": primi_tre,
        "criterio": f"{nota_primi_tre}, tetto {massimo_primi_tre:.2f} €, non personalizzabile",
    }]

    oltre = terminale.importo_cumulato(giorni)
    if giorni > terminale.giorno_massimo():
        avvisi.append(
            f"La tabella arriva al {terminale.giorno_massimo()}° giorno: oltre quella soglia il "
            "danno terminale sfuma nel danno biologico temporaneo e va liquidato con la tabella "
            "del danno non patrimoniale da lesione."
        )
    if oltre:
        dettaglio.append({
            "voce": f"Dal quarto al {min(giorni, terminale.giorno_massimo())}° giorno",
            "importo": oltre,
            "criterio": f"importo cumulato di tabella, {terminale.importo_pro_die(giorni):.0f} € pro die all'ultimo giorno",
        })

    massimo = terminale.personalizzazione_massima()
    richiesta = max(0.0, safe_float(payload.get("dt_personalizzazione")))
    if richiesta > massimo:
        avvisi.append(
            f"La personalizzazione richiesta ({richiesta:.0f}%) supera il {massimo}% previsto: "
            "e' stata ridotta al massimo consentito."
        )
        richiesta = float(massimo)
    importo_personalizzazione = round(oltre * richiesta / 100.0, 2)
    if importo_personalizzazione:
        dettaglio.append({
            "voce": f"Personalizzazione {richiesta:.0f}% (massimo sconvolgimento)",
            "importo": importo_personalizzazione,
            "criterio": "opera solo sui giorni successivi ai primi tre",
        })

    totale = round(primi_tre + oltre + importo_personalizzazione, 2)
    fonte = tabelle.fonte(tabelle.MILANO_2024_TERMINALE)
    return {
        "giorni": giorni,
        "periodo": periodo,
        "primi_tre_giorni": primi_tre,
        "primi_tre_giorni_massimo": massimo_primi_tre,
        "giorni_successivi": oltre,
        "personalizzazione_pct": richiesta,
        "personalizzazione_massima_pct": massimo,
        "importo_personalizzazione": importo_personalizzazione,
        "totale": totale,
        "dettaglio": dettaglio,
        "tabelle_applicate": [fonte.come_dizionario()],
        "notes": [
            "Il danno terminale presuppone un apprezzabile lasso di tempo fra le lesioni e la "
            "morte: il danno da morte immediata non e' risarcibile iure hereditatis "
            "(Cass. Sez. Un. 15350/2015).",
            "I primi tre giorni si liquidano in via equitativa entro il tetto tabellare e non "
            "sono personalizzabili; l'aumento per massimo sconvolgimento opera solo sui giorni "
            "successivi.",
            "Gli importi della tabella sono comprensivi della componente biologica temporanea.",
        ],
        "warnings": avvisi,
        "sources": [fonte.come_sorgente()],
    }
