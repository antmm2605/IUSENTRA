"""Domanda testuale dell’atto: estrazione nel motore, non durante la pagina."""
from __future__ import annotations
import re
from pct.registro_letture.fatti_repository import Fatto

_SEZIONE_SUCCESSIVA = r"(?:In via istruttoria|Procura alle liti|Rela(?:ta|zione) di notifica(?:zione)?)"


def _testo_e_confini(testo: str) -> tuple[str, list[int]]:
    """Conserva le intestazioni prima di normalizzare gli spazi del documento."""
    righe = []
    confini = []
    posizione = 0
    for riga in str(testo or "").splitlines():
        pulita = " ".join(riga.split())
        if not pulita:
            continue
        posizione += bool(righe)
        if re.fullmatch(_SEZIONE_SUCCESSIVA + r"\s*(?:[.:]\s*.*)?", pulita, re.I):
            confini.append(posizione)
        righe.append(pulita)
        posizione += len(pulita)
    pulito = " ".join(righe)
    # Testi nativi già su una riga: il titolo deve seguire una frase e avere i due punti.
    # Un richiamo a «nullità della procura alle liti» non è una nuova sezione.
    confini.extend(m.start() for m in re.finditer(r"(?<=[.!?;])\s+" + _SEZIONE_SUCCESSIVA + r"\s*:", pulito, re.I))
    return pulito, sorted(set(confini))


def estrai_domanda(testo: str, *, origine: str, contesto) -> list[Fatto]:
    pulito, confini = _testo_e_confini(testo)
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
    fine_sezione = min((p for p in confini if p >= da), default=len(pulito))
    if not pulito[da:fine_sezione].strip(" :.-"):
        return []
    match = re.search(r"\b(?:chiede|chiedono|conclude|concludono|voglia|vogliano)\b", pulito[da:min(da + 1400, fine_sezione)], re.I)
    if match:
        start = da + match.start()
    elif formule[-1].group(0).upper() == "CONCLUSIONI":
        # In real pleadings «voglia» often precedes the CONCLUSIONI heading.
        # The heading itself anchors the following numbered requests.
        richiesta = re.search(r"\b(?:accertarsi|accertare|dichiararsi|dichiarare|condannare)\b", pulito[da:min(da + 1400, fine_sezione)], re.I)
        start = da + richiesta.start() if richiesta else da
    else:
        return []
    frase = pulito[start:min(start + 1800, fine_sezione)]
    fine = re.search(r"(?:Ai fini (?:del contributo|fiscali)|Si (?:producono|depositano)|"
                     r"Si offrono in (?:comunicazione|produzione)|Con riserva|Salvis iuribus)", frase, re.I)
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
