# Verifiche documenti e PagoPA — 21/09/2026

Rilascio preparato: 2.342.1. La consegna complessiva resta aperta.

Modifiche: blocco dei salvataggi integrali da archivi SQL parziali o senza documenti; migrazione iniziale tramite upsert senza cancellazione; riuso dei documenti QuickOrganizer solo dopo verifica dei byte, con namespace ministeriali distinti; editor dei PDF esclusivamente di provenienza CARICAMENTO_STUDIO e privi di firma/riferimenti ministeriali. Originale conservato nelle versioni. Salvataggio PDF senza aggiungere intestazioni. Correzione contrasto del comando Salva. Inclusi i fix PagoPA già predisposti nella sessione.

Verifiche tecniche locali superate: test_fascicoli_partial_write_guard, test_portal_document_identity, test_pagopa_avvisi_runtime, test_pagopa_captcha_proxy; test_fascicoli selezione documento/documenti; test_polisweb selezione qbuilder/parse_documenti; test_local_signer selezione pec; test_utf8_integrity. Suite test_react_document_editor: cinque test passati e uno inizialmente fallito sulla dicitura anteprima nativa; dicitura corretta e singolo test ripetuto con esito positivo. Build React e typecheck passati. Non costituiscono verifica dell’intero prodotto.

Prova reale su Chrome, 127.0.0.1:8080: creato il fascicolo controllato 27B56506, senza dati del cliente; PDF controllato 8E0B4771 predisposto come fixture locale. Modifica del testo, click Salva, riapertura con testo persistito; una versione precedente conservata con hash verificato. L’upload dal selettore Chrome non è stato verificato: l’estensione non consente l’accesso ai file locali. La fixture non sostituisce quella prova.

Ripetuta la prova materiale dopo ricostruzione: salvataggio PDF senza intestazione aggiunta, pulsanti Salva/Lex leggibili e scroll fino al fondo verificati nel browser reale. Rimangono aperti: riconciliazione dei duplicati già presenti, recupero completo dei metadati successivi al backup del cliente, prova di tutti i PDF/layout coinvolti, controllo scheduler locale, CI, commit/push e deploy fino a relativa evidenza. Nessun collaudo con creazione di dati sul server del cliente.

Le prove dell’incidente contenenti dati privati sono conservate fuori dal repository in D:/legale/backups/IUSENTRA/incident-fascicoli-20260921. Non si dichiara ripristino integrale né assenza totale di perdita di metadati.
