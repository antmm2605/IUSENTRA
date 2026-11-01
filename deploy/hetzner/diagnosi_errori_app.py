"""Diagnosi in sola lettura degli errori dell'app: solo scheletro delle eccezioni.

Legge i log dei container indicati e per ogni Traceback stampa file, riga, funzione e
classe dell'eccezione, raggruppati con il numero di occorrenze. Il messaggio dell'eccezione
e le righe di log non vengono stampati: possono contenere nomi, testi o dati dello studio.
"""
import collections
import json
import os
import re
import subprocess

COMMAND = ["docker", "compose", "--env-file", "/opt/iusentra/.env.hetzner",
           "-f", "/opt/iusentra/repo/deploy/hetzner/docker-compose.hetzner.yml"]
FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
ECCEZIONE = re.compile(r"^\s*(?:[A-Za-z_][\w.]*\.)?([A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning|Exit|NotReady|Timeout)[A-Za-z0-9_]*)\b")
ROTTA = re.compile(r"(/api/[A-Za-z0-9_/.-]+)")
IDENT = re.compile(r"/[0-9A-Fa-f]{6,}(?=/|$)")


def _percorso(file: str) -> str:
    for radice in ("/app/", "/opt/iusentra/repo/"):
        if radice in file:
            return file.split(radice, 1)[1]
    return "[libreria]/" + file.rsplit("/", 1)[-1]


def main() -> None:
    servizi = os.environ.get("SERVIZI", "app").split()
    filtro = os.environ.get("FILTRO", "").strip()
    since = os.environ.get("DA", "48h")
    firme: collections.Counter = collections.Counter()
    for servizio in servizi:
        testo = subprocess.run(COMMAND + ["logs", "--no-color", "--no-log-prefix", "--since", since, servizio],
                               capture_output=True, text=True, errors="replace", check=False).stdout
        righe = testo.splitlines()
        i = 0
        while i < len(righe):
            if "Traceback (most recent call last)" not in righe[i]:
                i += 1
                continue
            contesto = " ".join(righe[max(0, i - 3):i])
            rotta = ROTTA.search(contesto)
            frames, j = [], i + 1
            while j < len(righe) and (righe[j].startswith(" ") or righe[j].startswith("\t")):
                trovato = FRAME.search(righe[j])
                if trovato:
                    frames.append(f"{_percorso(trovato.group(1))}:{trovato.group(2)} {trovato.group(3)}")
                j += 1
            eccezione = ECCEZIONE.match(righe[j]) if j < len(righe) else None
            nome = eccezione.group(1) if eccezione else "[eccezione non riconosciuta]"
            firma = json.dumps({"servizio": servizio,
                                "rotta": IDENT.sub("/<id>", rotta.group(1)) if rotta else "",
                                "eccezione": nome, "frames": frames[-8:]}, ensure_ascii=False)
            if not filtro or filtro in firma:
                firme[firma] += 1
            i = j + 1
    for firma, quante in firme.most_common(30):
        print(json.dumps({"occorrenze": quante, **json.loads(firma)}, ensure_ascii=False), flush=True)
    print(json.dumps({"firme_distinte": len(firme), "totale": sum(firme.values())}), flush=True)


if __name__ == "__main__":
    main()
