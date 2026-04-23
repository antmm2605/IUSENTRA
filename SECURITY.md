# Security Policy

## Ambito

IUSENTRA tratta dati professionali e potenzialmente sensibili di studi legali. Le segnalazioni di sicurezza devono seguire un canale riservato e non essere pubblicate in issue aperte.

## Come segnalare una vulnerabilita'

Invia la segnalazione al canale di supporto riservato concordato con IUSENTRA oppure al referente tecnico del progetto, includendo almeno:

- descrizione del problema;
- superficie coinvolta;
- impatto atteso;
- passi riproducibili;
- eventuali log o screenshot minimizzati;
- versione applicativa e contesto di esecuzione.

## Classificazione severita'

### Critica
- accesso non autorizzato a dati cliente;
- esecuzione di codice arbitrario;
- bypass autenticazione;
- esposizione di chiavi, token o segreti;
- rottura isolamento tenant.

### Alta
- escalation privilegi;
- accesso improprio a documenti o fascicoli;
- bypass di controlli autorizzativi;
- alterazione audit log;
- lettura impropria di dati sensibili.

### Media
- leak informativi limitati;
- CSRF/XSS con impatto contenuto;
- degradazione disponibilita' senza perdita dati;
- hardening incompleto su superfici esposte.

### Bassa
- header mancanti;
- configurazioni deboli non sfruttabili direttamente;
- errori documentali o di processo senza impatto immediato sui dati.

## Tempi attesi

- presa in carico iniziale: entro 2 giorni lavorativi;
- classificazione severita' e perimetro: entro 5 giorni lavorativi;
- mitigazione iniziale per vulnerabilita' critiche o alte: con priorita' immediata dopo il triage;
- piano di remediation definitivo: appena il triage e' concluso.

## Coordinamento e disclosure

- non pubblicare proof-of-concept con dati reali;
- non allegare segreti, password o dataset cliente completi;
- non testare vulnerabilita' su ambienti di terzi senza autorizzazione;
- la disclosure pubblica avviene solo dopo disponibilita' di mitigazione o fix.

## Hardening minimo atteso

Le release di IUSENTRA mantengono come guardrail minimi:

- logging strutturato con masking dati sensibili;
- healthcheck runtime;
- isolamento dati su `/data`;
- audit delle azioni sensibili;
- fallback espliciti su AI, PEC e portali esterni;
- segreti solo via variabili ambiente o secret store;
- bootstrap credenziali con cambio password obbligatorio;
- backup verificabili e prove periodiche di ripristino.

## Verifiche operative raccomandate prima di una release

- esecuzione CI completa senza errori bloccanti;
- controllo assenza segreti nei file tracked;
- verifica bootstrap password e cambio obbligatorio al primo accesso;
- test rapido di backup e restore dei dati persistenti;
- verifica masking log e rotazione dei file sensibili;
- verifica coerenza configurazione Docker, Railway e packaging.

## Fuori ambito

Salvo diverso accordo, non rientrano nel canale di vulnerability disclosure:

- richieste di supporto funzionale;
- problemi causati da middleware o installazioni locali alterate dal deployer;
- ambienti non supportati o configurati in modo difforme dalla documentazione.
