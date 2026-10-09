from web.services.client_document_reader import _preparation_summary


def test_summary_only_describes_recorded_preparation_without_source_data():
    warnings = ['Pagina 1: Geometria: quattro bordi non riscontrati; nessuna rettifica globale.',
                'Pagina 1: Analisi orientamento: 0°; originale invariato.',
                'Pagina 1: Ingrandimento misurato ×2 prima dell’OCR.',
                'Pagina 1: Preparazione terminata; avvio OCR locale sui pixel preparati.',
                'Riquadro (13, 20, 300, 40), contenuto privato da non mostrare']
    result = _preparation_summary(warnings)
    assert 'geometria, orientamento, ingrandimento' in result
    assert 'non compilano i campi' in result
    assert 'contrasto' not in result and 'privato' not in result and '13' not in result
    assert 'rettificat' not in result


def test_no_preparation_does_not_claim_it_ran():
    assert _preparation_summary(['Pagina 1: lettura nativa']) == ''
    assert _preparation_summary(['contrasto normalizzato: errore prima dell’OCR']) == ''
