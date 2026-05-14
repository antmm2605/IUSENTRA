# Check no fake React full

Generato: 2026-05-13T13:35:26.774Z

Violazioni: 0

Nessuna route piena risulta mascherata da legacy.

## Aggiornamento 2.236.3 - 2026-05-14

Verificate senza dati inventati le superfici `/profilo`, `/agenda/importa`,
`/agenda/nuovo`, `/clienti`, `/soggetti`, `/fascicoli`, `/email/scrivi`,
`/email-ordinaria/scrivi`, `/scadenziario`, `/impostazioni?tab=ai`, PDP, PAT e
SIGIT. I dati di profilo, cliente, fascicolo/procedimento, email e scadenze
arrivano da sessione/API/repository reali; gli stati vuoti restano neutri e non
sostituiscono record mancanti con esempi fittizi.
