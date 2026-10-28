"""Scelte del modello come priorità, mai nuove fonti né approvazioni.

Il chiamante fornisce catalogo, riscontri temporali e tokenizer fidati.
Non fa richieste al modello e non considera una selezione un giudizio giuridico.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from lex.normativa.applicabilita import Applicabilita
from lex.procedura_atti.provenienza import verifica_provenienza


@dataclass(frozen=True)
class Scelta:
    accettati: tuple[int, ...]
    scartati: tuple[str, ...]


def leggi_scelta(risposta: str, numero_candidati: int, *, massimo=20) -> Scelta:
    if type(numero_candidati) is not int or not 0 <= numero_candidati <= 100:
        raise ValueError("Elenco candidati non valido")
    if type(massimo) is not int or not 0 <= massimo <= 20:
        raise ValueError("Limite selezione non valido")
    if not isinstance(risposta, str) or len(risposta) > 32000:
        raise ValueError("Risposta modello non valida")
    try:
        obj = json.loads(risposta)
    except json.JSONDecodeError as exc:
        raise ValueError("Richiesto JSON completo, nessun recupero di numeri dal testo libero") from exc
    if not isinstance(obj, dict) or set(obj) != {"scelti"} or not isinstance(obj["scelti"], list):
        raise ValueError("Schema selezione non valido")
    good, bad = [], []
    for index, number in enumerate(obj["scelti"]):
        if type(number) is not int or not 1 <= number <= numero_candidati:
            bad.append("Indice non ammesso alla posizione " + str(index + 1))
        elif number in good:
            bad.append("Indice duplicato: " + str(number))
        elif len(good) >= massimo:
            bad.append("Limite delle scelte superato")
        else:
            good.append(number)
    return Scelta(tuple(good), tuple(bad))


def prepara_fonti(candidati: list[dict], scelta: Scelta, riscontri: dict[int, Applicabilita],
                  obbligatorie: set[int], *, tokenizza, budget_token: int,
                  contesto: str = "", massimo=20) -> dict:
    """Budget del prompt completo, testi integri, fonti obbligatorie mai perse in silenzio.

    ID = posizione1..N della lista chiusa. Provenienza controllata con il modulo
    nativo. Modello e risposta non possono fornire riscontri/obbligatorietà.
    """
    if type(budget_token) is not int or budget_token <= 0 or not 1 <= massimo <= 50:
        raise ValueError("Budget non valido")
    if len(candidati) > 100 or not callable(tokenizza):
        raise ValueError("Catalogo o tokenizer non valido")
    valid_ids = set(range(1, len(candidati) + 1))
    if any(type(x) is not int for x in obbligatorie) or not obbligatorie <= valid_ids:
        raise ValueError("Fonte obbligatoria fuori elenco")
    if any(type(x) is not int or x not in valid_ids for x in scelta.accettati):
        raise ValueError("Scelta fuori elenco")
    ordered = list(dict.fromkeys(sorted(obbligatorie) + list(scelta.accettati) + list(range(1, len(candidati)+1))))
    accepted, excluded, errors = [], [], []
    for number in ordered:
        c = candidati[number-1]
        proof = riscontri.get(number)
        problems = verifica_provenienza({"fonti": {number:c.get("testo")},
                                        "fonti_ref":[dict(c.get("riferimento", {}), n=number)]})
        if proof is None or proof.stato != "applicabile":
            problems.append("Applicabilità temporale non dimostrata")
        if problems:
            excluded.append({"n":number,"motivi":problems})
            if number in obbligatorie:
                errors.append("Fonte obbligatoria non utilizzabile: " + str(number))
            continue
        source = {"n":number,"testo":c["testo"],"riferimento":c["riferimento"]}
        trial = contesto + "\nFONTI:\n" + json.dumps(accepted+[source],ensure_ascii=False,sort_keys=True)
        tokens = tokenizza(trial)
        if type(tokens) is not int or tokens < 0:
            raise ValueError("Conteggio tokenizer non valido")
        if len(accepted) >= massimo or tokens > budget_token:
            excluded.append({"n":number,"motivi":["Limite del contesto o delle fonti raggiunto"]})
            if number in obbligatorie:
                errors.append("Fonte obbligatoria oltre il budget: " + str(number))
            continue
        accepted.append(source)
    prompt = contesto + "\nFONTI:\n" + json.dumps(accepted,ensure_ascii=False,sort_keys=True)
    tokens = tokenizza(prompt)
    if type(tokens) is not int or tokens < 0:
        raise ValueError("Conteggio tokenizer non valido")
    if tokens > budget_token:
        errors.append("Il solo contesto supera il budget")
    if not accepted:
        errors.append("Nessuna fonte utilizzabile")
    return {"fonti":accepted,"esclusioni":excluded,"errori":errors,
            "token_prompt":tokens,"pronto_per_modello":not errors,
            "avvisi_selezione":list(scelta.scartati),"certificazione_giuridica":False}
