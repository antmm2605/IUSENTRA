"""Read-only presentation of a detached CMS attachment, without verification."""
from hashlib import sha256
from html import escape

from web.bootstrap.fascicoli_document_helpers import _safe_preview_download_url


def detached_signature_preview(data: bytes, download_url: str):
    rows: list[tuple[str, str]] = []
    error = ''
    try:
        if len(data) > 8 * 1024 * 1024:
            raise ValueError('Il componente di firma supera il limite di lettura dei metadati (8 MB).')
        from asn1crypto import cms, pem
        from pct.document_intelligence.container_metadata import extract_cms_metadata
        from pct.formatting import format_datetime_it
        payload = pem.unarmor(data)[2] if pem.detect(data) else data
        description = extract_cms_metadata(payload)
        if not description.ok:
            raise ValueError(description.error_message)
        info = cms.ContentInfo.load(payload, strict=True)
        if info['content_type'].native != 'signed_data':
            raise ValueError('Il file non contiene una firma CMS separata.')
        signed = info['content']
        rows.extend([('Formato', 'Firma CMS / S/MIME separata'),
                     ('Firmatari dichiarati', str(len(signed['signer_infos'])))])
        for number, cert in enumerate(signed['certificates'], 1):
            if cert.name != 'certificate':
                continue
            value = cert.chosen
            prefix = f'Certificato {number}'
            rows.extend([(f'{prefix} · intestatario', value.subject.human_friendly),
                         (f'{prefix} · emittente', value.issuer.human_friendly),
                         (f'{prefix} · valido dal', format_datetime_it(value['tbs_certificate']['validity']['not_before'].native)),
                         (f'{prefix} · valido fino al', format_datetime_it(value['tbs_certificate']['validity']['not_after'].native))])
    except (ValueError, TypeError, KeyError) as cause:
        error = str(cause) or 'La struttura della firma non è leggibile.'
    rows.extend([('Dimensione originale', f"{len(data):,}".replace(',', '.') + ' byte'),
                 ('Impronta SHA-256 dell’allegato', sha256(data).hexdigest())])
    fields = ''.join(f'<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>' for label, value in rows)
    status = (f'<p role="alert">{escape(error)} Il file originale resta scaricabile.</p>' if error else
              '<p>Questo allegato contiene la firma separata della PEC e non una pagina da leggere. '
              'I dati seguenti sono letti dal file originale.</p>')
    html = ('<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>*{box-sizing:border-box}body{margin:0;padding:16px;background:#f6f8fc;color:#15223b;'
            'font:14px/1.5 Inter,system-ui,sans-serif}main{max-width:980px;margin:auto;padding:20px;'
            'border:1px solid #dce3ec;border-radius:12px;background:white}header{display:flex;'
            'align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}h1{font-size:20px;margin:0}'
            'a{display:inline-flex;padding:8px 12px;min-height:38px;border:1px solid #cbd5e1;'
            'border-radius:8px;color:#15223b;text-decoration:none;font-weight:600}'
            'a:hover,a:focus-visible{background:#eff6ff;outline:2px solid #2563eb;outline-offset:2px}'
            'dl{display:grid;gap:10px}dl div{padding:10px 12px;background:#f6f8fc;border-radius:8px}'
            'dt{font-size:12px;color:#526177}dd{margin:4px 0 0;overflow-wrap:anywhere}'
            '.notice{padding:12px;border-left:3px solid #a76c12;background:#fffbeb}</style></head><body><main>'
            '<header><h1>Firma separata della PEC</h1>'
            f'<a href="{_safe_preview_download_url(download_url)}" download>Scarica originale</a></header>'
            f'{status}<p class="notice">Validità della firma non verificata: la sola lettura dei metadati '
            'non verifica integrità del messaggio, identità del firmatario o attendibilità del certificato.</p>'
            f'<dl>{fields}</dl></main></body></html>')
    return html, 200, {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'private, no-store'}
