# Security Policy

## Ambito

IUSENTRA tratta dati professionali e potenzialmente sensibili di studi legali. Le segnalazioni
di sicurezza devono quindi seguire un canale riservato e non essere pubblicate in issue aperte.

## Come segnalare una vulnerabilita'

Invia la segnalazione al canale di supporto riservato concordato con IUSENTRA oppure al referente
tecnico del progetto, includendo almeno:

- descrizione del problema;
- superficie coinvolta;
- impatto atteso;
- passi riproducibili;
- eventuali log o screenshot minimizzati.

## Tempi attesi

- presa in carico iniziale: entro 2 giorni lavorativi;
- classificazione severita' e perimetro: entro 5 giorni lavorativi;
- piano di remediation o mitigazione: appena il triage e' concluso.

## Cosa evitare

- non pubblicare proof-of-concept con dati reali;
- non allegare segreti, password o dataset cliente completi;
- non testare vulnerabilita' su ambienti di terzi senza autorizzazione.

## Hardening minimo atteso

Le release di IUSENTRA mantengono come guardrail minimi:

- logging strutturato con masking dati sensibili;
- healthcheck runtime;
- isolamento dati su `/data`;
- audit delle azioni sensibili;
- fallback espliciti su AI, PEC e portali esterni.
