# Route gate report

Route nel manifest: 102
Route con unlockFromGate=true: 76
Route governate consentite: /, /admin/database, /agenda, /agenda/nuovo, /amministrazione, /audit, /backup, /cartelle-condivise, /clienti, /clienti/nuovo, /compensi-forensi, /deposito/checklist, /documenti, /email, /email-ordinaria, /notifiche-legali, /fascicoli, /fascicoli/archivio, /fascicoli/nuovo, /fatturazione, /fatturazione/nuova, /giurisprudenza, /global-search, /impostazioni, /impostazioni-studio, /impostazioni/calendario, /impostazioni/pagamenti, /incassi-pagamenti, /legal-intelligence, /legal-intelligence/mediazione, /legal-intelligence/news, /messaggi, /messaggi/nuovo, /notifiche, /notifiche-whatsapp, /preventivi, /preventivi/conferimento/:id, /preventivi/conferimento/nuovo, /preventivi/nuovo, /preventivi/wizard, /privacy/registro, /privacy/registro/nuovo, /profili, /redazione-atti, /regia-operativa, /registro-attivita, /registro-gdpr, /ricerca-legale, /ricerca-studio, /scadenziario, /scadenziario/nuova, /scadenziario/:id, /scadenziario/:id/modifica, /sincronizzazione-calendari, /sito-studio, /sito-studio/builder, /sito-studio/contatti, /sito-studio/redazione-ai, /soggetti, /soggetti/nuovo, /statistiche, /strumenti-legali, /strumenti-operativi, /studio, /tariffario, /template-atti, /template-atti/catalogo, /timesheet, /utenti, /utenti/nuovo, /wizard-pro, /workspace-intelligente, /portali/pdp/acquisizione, /portali/pat/acquisizione, /portali/ptt/acquisizione, /portali/sigit/acquisizione
Tranche 4A: route studio/backup censite come bridge se conservano scritture legacy.
Tranche 5A: studio e amministrazione restano bridge quando sono hub di navigazione.
Tranche 6A: fatturazione e incassi restano bridge se le scritture principali sono legacy.
Tranche 7A: preventivi non wizard restano bridge finche i POST principali sono legacy.
Tranche 8A: compensi/tariffario declassati quando mantengono fallback o bridge legacy.
Tranche 9A: template atti/redazione exact restano bridge finche le azioni principali sono legacy.
Tranche 10A: giurisprudenza/legal intelligence declassate se non hanno workflow React operativo pieno.
Parte 12A: react_full deprecato; unlockFromGate=true richiede status react_bridge/react_operational_partial/react_operational_full.
Violazioni: 0
