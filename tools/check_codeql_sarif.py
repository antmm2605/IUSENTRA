"""Il gate CodeQL legge i risultati dell'analisi, non il caricamento su GitHub.

CodeQL girava e poi provava a pubblicare gli avvisi nella scheda «Security».
Su una repository privata quella scheda esiste solo con GitHub Code Security
attivo: senza, il passaggio di caricamento risponde «Code scanning is not
enabled for this repository», il job «Analyze (python)» finisce rosso e il
controllo richiesto del deploy resta bloccato per sempre — pur non avendo
CodeQL trovato nulla.

Qui l'analisi resta identica: cambia solo dove finisce il risultato. Il SARIF
viene scritto su file, conservato come artefatto della run e **letto da questo
presidio**, che fa fallire il job quando l'analisi trova qualcosa di grave.
Il valore di sicurezza non si perde: prima nessuno vedeva gli avvisi (la
scheda non c'era), ora un avviso grave ferma la catena.

Cosa ferma la catena:
- un risultato di livello `error`;
- un risultato con `security-severity` pari o superiore alla soglia alta
  (7.0 nella scala CVSS usata da GitHub per il code scanning).

Le eccezioni si dichiarano in `.github/codeql/eccezioni.json`, una per regola,
con il motivo scritto e il presidio alternativo: come per le altre deroghe del
progetto, non esiste esclusione senza motivazione leggibile.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ECCEZIONI = REPO_ROOT / ".github" / "codeql" / "eccezioni.json"

#: Soglia CVSS oltre la quale un avviso e' bloccante, coerente con la
#: classificazione «High» usata da GitHub per il code scanning.
SOGLIA_GRAVITA = 7.0

LIVELLI_BLOCCANTI = {"error"}


def _numero(valore: Any) -> float:
    try:
        return float(str(valore).strip())
    except (TypeError, ValueError):
        return 0.0


def _regole(esecuzione: dict[str, Any]) -> dict[str, dict[str, Any]]:
    strumento = esecuzione.get("tool") or {}
    driver = strumento.get("driver") or {}
    regole: dict[str, dict[str, Any]] = {}
    for gruppo in (driver, *(strumento.get("extensions") or [])):
        for regola in gruppo.get("rules") or []:
            identificativo = str(regola.get("id") or "").strip()
            if identificativo:
                regole[identificativo] = regola
    return regole


def _posizione(risultato: dict[str, Any]) -> str:
    for luogo in risultato.get("locations") or []:
        fisico = (luogo.get("physicalLocation") or {})
        percorso = ((fisico.get("artifactLocation") or {}).get("uri") or "").strip()
        riga = (fisico.get("region") or {}).get("startLine")
        if percorso:
            return f"{percorso}:{riga}" if riga else percorso
    return ""


def _testo(risultato: dict[str, Any]) -> str:
    messaggio = (risultato.get("message") or {}).get("text") or ""
    return " ".join(str(messaggio).split())


def leggi_eccezioni(percorso: Path | None = None) -> dict[str, str]:
    """Le regole escluse dal blocco, con il motivo dichiarato."""
    percorso = percorso or ECCEZIONI
    if not percorso.exists():
        return {}
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as errore:
        raise SystemExit(f"[FAIL] {percorso} non leggibile: {errore}") from None
    escluse: dict[str, str] = {}
    for voce in dati.get("regole_non_bloccanti") or []:
        identificativo = str(voce.get("id") or "").strip()
        motivo = " ".join(str(voce.get("motivo") or "").split())
        if not identificativo:
            continue
        if not motivo:
            raise SystemExit(f"[FAIL] Eccezione CodeQL «{identificativo}» senza motivo dichiarato.")
        escluse[identificativo] = motivo
    return escluse


def risultati_sarif(cartella: Path) -> list[dict[str, Any]]:
    """Ogni risultato dei file SARIF prodotti dall'analisi, normalizzato."""
    trovati: list[dict[str, Any]] = []
    for file_sarif in sorted(cartella.rglob("*.sarif")):
        try:
            documento = json.loads(file_sarif.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as errore:
            raise SystemExit(f"[FAIL] {file_sarif} non leggibile: {errore}") from None
        for esecuzione in documento.get("runs") or []:
            regole = _regole(esecuzione)
            for risultato in esecuzione.get("results") or []:
                identificativo = str(risultato.get("ruleId") or "").strip()
                regola = regole.get(identificativo) or {}
                proprieta = regola.get("properties") or {}
                livello = str(risultato.get("level") or proprieta.get("problem.severity") or "").strip().lower()
                trovati.append(
                    {
                        "id": identificativo,
                        "livello": livello,
                        "gravita": _numero(proprieta.get("security-severity")),
                        "posizione": _posizione(risultato),
                        "messaggio": _testo(risultato),
                        "file": file_sarif.name,
                    }
                )
    return trovati


def bloccanti(trovati: list[dict[str, Any]], escluse: dict[str, str]) -> list[dict[str, Any]]:
    fermi: list[dict[str, Any]] = []
    for voce in trovati:
        if voce["id"] in escluse:
            continue
        if voce["livello"] in LIVELLI_BLOCCANTI or voce["gravita"] >= SOGLIA_GRAVITA:
            fermi.append(voce)
    return fermi


def rapporto(trovati: list[dict[str, Any]], fermi: list[dict[str, Any]], escluse: dict[str, str]) -> str:
    righe = ["# Esito CodeQL", ""]
    righe.append(f"Risultati analizzati: {len(trovati)}")
    righe.append(f"Bloccanti: {len(fermi)}")
    if escluse:
        righe.append("")
        righe.append("## Regole dichiarate non bloccanti")
        for identificativo, motivo in sorted(escluse.items()):
            righe.append(f"- `{identificativo}` — {motivo}")
    if fermi:
        righe.append("")
        righe.append("## Da correggere")
        for voce in fermi:
            posto = voce["posizione"] or "posizione non indicata"
            righe.append(f"- `{voce['id']}` ({voce['livello'] or 'livello non indicato'}) — {posto}: {voce['messaggio']}")
    return "\n".join(righe) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Presidio sui risultati CodeQL (SARIF).")
    parser.add_argument("cartella", nargs="?", default="artifacts/codeql", help="Cartella con i file .sarif")
    parser.add_argument("--report-md", default="", help="Percorso del rapporto leggibile da scrivere")
    parser.add_argument(
        "--consenti-cartella-vuota",
        action="store_true",
        help="Non fallire se l'analisi non ha prodotto alcun file SARIF (uso diagnostico)",
    )
    argomenti = parser.parse_args(argv)

    cartella = Path(argomenti.cartella)
    if not cartella.exists():
        if argomenti.consenti_cartella_vuota:
            print(f"[OK] Nessuna cartella {cartella}: analisi non eseguita, nulla da valutare.")
            return 0
        print(f"[FAIL] Cartella {cartella} assente: l'analisi CodeQL non ha prodotto risultati.")
        return 1

    file_sarif = sorted(cartella.rglob("*.sarif"))
    if not file_sarif and not argomenti.consenti_cartella_vuota:
        print(f"[FAIL] Nessun file SARIF in {cartella}: l'analisi CodeQL non ha prodotto risultati.")
        return 1

    escluse = leggi_eccezioni()
    trovati = risultati_sarif(cartella)
    fermi = bloccanti(trovati, escluse)

    testo = rapporto(trovati, fermi, escluse)
    if argomenti.report_md:
        destinazione = Path(argomenti.report_md)
        destinazione.parent.mkdir(parents=True, exist_ok=True)
        destinazione.write_text(testo, encoding="utf-8")
    print(testo)

    if fermi:
        print(f"[FAIL] CodeQL: {len(fermi)} risultato/i bloccante/i.")
        return 1
    print(f"[OK] CodeQL: nessun risultato bloccante su {len(trovati)} rilevazione/i.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
