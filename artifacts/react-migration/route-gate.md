# Route gate report

Route nel manifest: 57
Route con unlockFromGate=true: 38
Route governate consentite: /statistiche, /audit, /registro-attivita, /utenti, /utenti/nuovo, /profili, /backup, /sito-studio, /sito-studio/contatti, /studio, /amministrazione, /impostazioni, /impostazioni-studio, /impostazioni/calendario, /impostazioni/pagamenti, /notifiche, /notifiche-whatsapp, /sincronizzazione-calendari, /fatturazione, /fatturazione/nuova, /incassi-pagamenti, /preventivi, /preventivi/nuovo, /preventivi/wizard, /preventivi/conferimento/nuovo, /compensi-forensi, /tariffario, /template-atti, /template-atti/catalogo, /redazione-atti, /giurisprudenza, /legal-intelligence, /legal-intelligence/news, /legal-intelligence/mediazione, /ricerca-legale, /deposito/checklist, /strumenti-legali, /strumenti-operativi
Tranche 4A: route studio/backup censite come bridge se conservano scritture legacy.
Tranche 5A: studio e amministrazione restano bridge quando sono hub di navigazione.
Tranche 6A: fatturazione e incassi restano bridge se le scritture principali sono legacy.
Tranche 7A: preventivi non wizard restano bridge finche i POST principali sono legacy.
Tranche 8A: compensi/tariffario declassati quando mantengono fallback o bridge legacy.
Tranche 9A: template atti/redazione exact restano bridge finche le azioni principali sono legacy.
Tranche 10A: giurisprudenza/legal intelligence declassate se non hanno workflow React operativo pieno.
Parte 12A: react_full deprecato; unlockFromGate=true richiede status react_bridge/react_operational_partial/react_operational_full.
Violazioni: 0
