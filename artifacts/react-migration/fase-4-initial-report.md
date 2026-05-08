# Fase 4 - Audit iniziale documenti, telematico, comunicazioni, Lex

## 1. Route full React verificate

26 route risultano `react_operational_full` nel manifest dopo la promozione dei bridge documentali e Legal Intelligence. Le route promosse leggono API JSON reali e dichiarano `writes=none`.

## 2. Route bridge ancora presenti

0 nel manifest. L'audit anti-mascheramento segnala 1 bridge reale residuo: `/statistiche`, mantenuta partial.

## 3. Route legacy operative

25 route restano `legacy_operational`, concentrate su impostazioni, wildcard economiche/documentali, portali telematici e deposito/checklist.

## 4. Template Jinja UI primaria

130 template restano UI primaria nell'inventario. Nessun template e' stato declassato senza verifica di route e flusso.

## 5. CTA `_legacy=1`

81 occorrenze complessive nel repository di migrazione. Le CTA primarie sono rimosse dalle route promosse.

## 6. Route da migrare nell'area richiesta

Migrate: Template atti, Redazione atti, Giurisprudenza, Legal Intelligence, News, Mediazione, Ricerca legale. Non migrate: portali telematici specifici e checklist deposito per rischio compliance.

## 7. Endpoint API disponibili

Usati endpoint `/api/v1/ui/template-atti`, `/api/v1/ui/template-atti/catalogo`, `/api/v1/ui/redazione-atti`, `/api/v1/ui/giurisprudenza`, `/api/v1/ui/legal-intelligence`, `/api/v1/ui/legal-intelligence/news`, `/api/v1/ui/legal-intelligence/mediazione`, `/api/v1/ui/ricerca-legale`.

## 8. Endpoint mancanti necessari

Per promuovere ulteriormente servono endpoint JSON specifici per editor template, generazione atti, dettaglio giurisprudenza, sincronizzazione/approvazione fonti, portali e deposito.

## 9. Componenti UI disponibili e mancanti

Completata la base richiesta per documenti/telematico/comunicazioni/Lex: `IusWizardStepper`, `IusCompliancePanel`, `IusDocumentStatusBadge`, `IusChannelCard`, `IusMessageList`, `LexPanel`, stati loading/error/empty/success.

## 10. Rischi tecnici

Non promuovere portali o workflow di generazione documenti senza autorizzazioni, XSD/versioni verificate, audit, gestione file e API JSON dedicate.
