from __future__ import annotations

import re


LEGAL_TOPICS: dict[str, list[str]] = {
    "civile": ["codice civile", "obbligazioni", "contratto", "risarcimento", "responsabilita civile"],
    "processo civile": ["processo civile", "procedura civile", "codice di procedura civile", "udienza", "citazione"],
    "PCT": ["pct", "processo civile telematico", "datiatto", "busta telematica", "polisweb"],
    "famiglia": ["separazione", "divorzio", "minori", "affidamento", "responsabilita genitoriale", "famiglia"],
    "lavoro": ["licenziamento", "rapporto di lavoro", "datore di lavoro", "lavoratore", "tfr", "retribuzione"],
    "tributario": ["tributario", "imposta", "iva", "agenzia delle entrate", "sigit", "ptt"],
    "amministrativo": ["tar", "consiglio di stato", "procedimento amministrativo", "siga", "pat"],
    "penale": ["processo penale", "codice penale", "codice di procedura penale", "pdp", "indagini preliminari"],
    "esecuzioni": ["esecuzione forzata", "pignoramento", "precetto", "giudice dell'esecuzione"],
    "locazioni": ["locazione", "sfratto", "canone", "conduttore", "locatore"],
    "condominio": ["condominio", "amministratore di condominio", "assemblea condominiale", "millesimi"],
    "societario": ["societa", "srl", "spa", "assemblea", "amministratori", "bilancio"],
    "crisi impresa": ["crisi d'impresa", "liquidazione giudiziale", "concordato", "sovraindebitamento"],
    "privacy": ["privacy", "gdpr", "dati personali", "garante per la protezione", "data breach"],
    "forense/deontologia": ["avvocato", "deontologia", "codice deontologico", "ordine forense", "cnf"],
    "compensi/parametri forensi": ["parametri forensi", "compenso", "onorario", "dm 55", "art. 22-bis"],
    "deposito telematico": ["deposito telematico", "ricevuta accettazione", "controlli automatici", "punto di accesso"],
    "firma digitale": ["firma digitale", "cades", "pades", "certificato digitale", "marca temporale"],
    "PEC/notifiche": ["pec", "posta elettronica certificata", "notifica telematica", "domicilio digitale"],
    "fatturazione": ["fattura", "fatturazione elettronica", "corrispettivo", "iva", "split payment"],
    "antiriciclaggio": ["antiriciclaggio", "adeguata verifica", "titolare effettivo", "segnalazione sospetta"],
    "appalti": ["appalto", "contratti pubblici", "codice dei contratti", "anac", "gara"],
    "previdenza": ["inps", "inail", "previdenza", "invalidita civile", "contributi"],
    "bancario": ["banca", "credito", "mutuo", "interessi", "usura", "anatocismo"],
    "consumatori": ["consumatore", "codice del consumo", "garanzia legale", "pratiche commerciali scorrette"],
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def detect_topics(text: str) -> tuple[list[str], float]:
    low = clean_text(text).lower()
    topics: list[str] = []
    score = 0.0
    for topic, keywords in LEGAL_TOPICS.items():
        hits = sum(1 for keyword in keywords if keyword.lower() in low)
        if hits:
            topics.append(topic)
            score += min(20, hits * 5)
    return topics, min(score, 100.0)
