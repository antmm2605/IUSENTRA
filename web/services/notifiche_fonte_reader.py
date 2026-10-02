"""Fonti ufficiali immutabili nel lettore a pagine condiviso."""
from io import BytesIO
from flask import abort, make_response, request, send_file


def visualizza_fonte_notifiche(data: bytes, titolo: str, nome_file: str):
    from web.bootstrap.fascicoli_document_helpers import pdf_mobile_preview_html, pdf_page_count, render_pdf_page_png

    if request.args.get('download') == '1':
        return send_file(BytesIO(data), mimetype='application/pdf', download_name=nome_file,
                         as_attachment=True, max_age=0)
    totale = pdf_page_count(data)
    pagina = request.args.get('page')
    if pagina is not None:
        try:
            numero = int(pagina)
        except (ValueError, TypeError):
            abort(400, description='Numero di pagina non valido.')
        if numero < 1 or numero > totale:
            abort(404, description='Pagina non presente nella fonte.')
        if request.args.get('reader_text') == '1':
            from web.services.pdf_reader_text import page_text_response
            return page_text_response(data, numero)
        response = send_file(BytesIO(render_pdf_page_png(data, numero)), mimetype='image/png', conditional=False)
    else:
        response = make_response(pdf_mobile_preview_html(
            nome_documento=titolo,
            page_urls=[f'{request.path}?page={i}' for i in range(1, totale + 1)],
            scarica_url=request.path + '?download=1', pdf_payload=data,
        ))
    response.headers['Cache-Control'] = 'private, max-age=300'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
