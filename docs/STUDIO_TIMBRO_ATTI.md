# Timbro Studio negli Atti

Aggiornato: 2026-05-12.

## Sorgente dati

Il timbro studio vive in `pct/studio_timbro.py` ed e' salvato per tenant in `STUDIO_TIMBRO_DB`, con default derivati da `CONFIG_STUDIO_DB` e dalla configurazione applicativa. Non contiene dati hardcoded di studi reali.

Campi principali: nome studio, sottotitolo, professionista, qualifiche, indirizzo, citta', telefono, fax, codice fiscale, partita IVA, PEC, email, sito, foro, righe extra e layout.

## Rendering

Il renderer espone:

- `to_lines()` per UI e anteprime;
- `to_html()` per Jinja/editor;
- `to_text()` per compilatore e fallback;
- `to_docx_header()` come struttura per export DOCX;
- `to_pdf_flowable()` per ReportLab.

L'iniezione centrale avviene nel renderer template e in `render_compiled_act`, quindi non serve modificare manualmente i 420 template.

## API

- `GET /api/v1/ui/studio/timbro`
- `POST /api/v1/ui/studio/timbro`
- `GET /api/v1/ui/studio/timbro/preview`

Il salvataggio richiede sessione e permesso di configurazione o API key valida, e genera audit `studio.timbro.salva`.

## Regole operative

Il timbro viene inserito in alto a sinistra, allineato a sinistra, prima del titolo dell'autorita' o dell'atto. Il default applica il timbro alla prima pagina e a tutti i modelli, con flag separati per atti interni, stragiudiziali e depositabili.

Sono esposti anche alias compatibili con UI/API: `layout_posizione`, `layout_allineamento`, `margine_top_mm`, `margine_left_mm`, `margine_bottom_after_timbro_mm`, `larghezza_blocco_mm`, `font_family`, `font_size_studio_nome`, `font_size_righe`, `line_spacing`.
