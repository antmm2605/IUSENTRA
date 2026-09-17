"""Domanda testuale dell’atto: estrazione nel motore, non durante la pagina."""
from __future__ import annotations
import re
from pct.registro_letture.fatti_repository import Fatto

def estrai_domanda(testo: str, *, origine: str, contesto) -> list[Fatto]:
    pulito = " ".join(str(testo or "").split())
    testa = pulito[:1500]
    if re.search(r"^(?:Tipo contenuto:|Oggetto:|From:|Mittente:)", testa, re.I):
        return []
    if not re.search(r"\b(?:RICORSO|ATTO DI CITAZIONE|COMPARSA|MEMORIA)\b", testa, re.I):
        return []
    # Una citazione della domanda altrui nel racconto dei fatti non è il petitum.
    formule = list(re.finditer(r"\b(?:CONCLUSIONI|P\.?\s*Q\.?\s*M\.?|Tutto (?:ciò|quanto) premesso|Per (?:questi|tali) motivi)\b", pulito, re.I))
    if not formule:
        return []
    da = formule[-1].end()
    match = re.search(r"\b(?:chiede|chiedono|conclude|concludono|voglia|vogliano)\b", pulito[da:da + 1400], re.I)
    if match:
        start = da + match.start()
    elif formule[-1].group(0).upper() == "CONCLUSIONI":
        # In real pleadings «voglia» often precedes the CONCLUSIONI heading.
        # The heading itself anchors the following numbered requests.
        richiesta = re.search(r"\b(?:accertarsi|accertare|dichiararsi|dichiarare|condannare)\b", pulito[da:da + 1400], re.I)
        start = da + richiesta.start() if richiesta else da
    else:
        return []
    frase = pulito[start:start + 1800]
    fine = re.search(r"(?:Ai fini (?:del contributo|fiscali)|Si (?:producono|depositano)|Con riserva|Salvis iuribus)", frase, re.I)
    if fine:
        frase = frase[:fine.start()]
    frase = frase.strip()
    if len(frase) > 420:
        frase = frase[:420].rsplit(" ", 1)[0] + "…"
    secondario = " ".join(str(contesto.testo_secondario or "").split())
    concorde = len(frase) > 30 and frase.rstrip("…") in secondario
    verifica = "verificata" if origine == "nativo" or concorde else "plausibile"
    return [Fatto(categoria="evento", campo="domanda_atto", valore=frase, valore_letto=frase,
        etichetta="Domanda riportata nelle conclusioni", posizione=start,
        contesto=frase, origine=origine, confidenza=.98 if verifica == "verificata" else .75,
        verifica=verifica, prove=[{"codice":"conclusioni_atto", "esito":"ok",
        "dettaglio":"Citazione testuale dopo la formula conclusiva dell’atto."}])]
