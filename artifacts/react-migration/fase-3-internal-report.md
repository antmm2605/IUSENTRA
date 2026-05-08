# Fase 3 - Report tecnico interno

## 1. Route gia full React vere

Prima della tranche: 18 manifestate `react_operational_full`; dopo verifica anti-mascheramento le route operative amministrazione, economico e studio gia migrate restano governate.

## 2. Route dichiarate full da ricontrollare

`/statistiche` e `/preventivi/wizard` restano da trattare con cautela: il manifest le mantiene partial, l'audit anti-mascheramento classifica `/preventivi/wizard` come full reale e `/statistiche` come bridge residuo.

## 3. Bridge convertibili subito

Convertite in questa sessione: `/template-atti`, `/template-atti/catalogo`, `/redazione-atti`, `/giurisprudenza`, `/legal-intelligence`, `/legal-intelligence/news`, `/legal-intelligence/mediazione`, `/ricerca-legale`.

## 4. Legacy ad alto impatto

Restano legacy: impostazioni sensibili, dettagli/export economici, editor documentali, checklist deposito e portali telematici. Motivo: POST storici, file/PDF/DOCX/XML, segreti, certificati, sessioni e compliance portali.

## 5. Template Jinja ancora UI primaria

Inventario invariato: 258 template censiti, 130 UI primaria, 36 fallback tecnico. Non sono stati declassati template non verificati per evitare classificazioni artificiali.

## 6. CTA `_legacy=1`

Conteggio anti-mascheramento corrente: 81 occorrenze complessive. Nelle 8 route promosse: 0 CTA legacy primarie.

## 7. Componenti disponibili

Gia presenti: shell, sidebar, topbar, section header, metric/action card, status badge, form section, collapsible panel, data table shell, LexFloatingButton.

## 8. Componenti mancanti completati

Aggiunti: loading, error, success, retry, skeleton card/table, wizard stepper, compliance panel, document status badge, channel card, message list, LexPanel, icon registry.

## 9. Esito

Target bridge raggiunto: 8 -> 0 nel manifest. Target legacy/Jinja non raggiunto per scelta di sicurezza: i percorsi residui sono ad alto rischio e richiedono API o workflow dedicati prima della promozione.
