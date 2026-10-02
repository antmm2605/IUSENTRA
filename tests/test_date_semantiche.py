import importlib
import unittest
from pathlib import Path

root=Path(__file__).resolve().parents[1]/'pct/archivio_letture'

def module(name):
    return importlib.import_module('pct.archivio_letture.' + name)

anchors=module('ancoraggio')
relevance=module('pertinenza_documentale')

class DateSemantiche(unittest.TestCase):
    def test_redazione_non_udienza(self):
        for text,value in (
            ('annotazione “udienza mediante collegamenti audiovisivi”. Velletri, 6 gennaio 2026. Il giudice dott. Claudio Silvestrini','2026-01-06'),
            ('annotazione "trattazione scritta". Velletri, 27 aprile 2025. Il giudice dott. Claudio Silvestrini','2025-04-27'),
            ('RINVIA al 7 ottobre 2026. Santa Maria Capua Vetere, 1 aprile 2026. La giudice','2026-04-01'),
        ):
            with self.subTest(text=text):
                self.assertIn('redazione',anchors.esclusione_data_salvata(text,value))

    def test_vero_dispositivo_resta(self):
        text='RINVIA all’udienza del 7/10/2026, ore 10.45. Il giudice dispone la comunicazione.'
        self.assertEqual(anchors.esclusione_data_salvata(text,'2026-10-07'),'')
        start=text.index('7/10/2026')
        self.assertEqual(anchors.ancora_per(text,start,start+10).campo,'udienza')

    def test_identita_ocr_senza_titolo(self):
        text='NomeGIOVANNA Cittadinanza ITALIANA TAURIANOVA STUDENTESSA Scade il 30/05/2025 AT9974233 CONNOTATI E CONTRASSEGNI SALIENTI Cognome ALESSI'
        self.assertEqual(relevance.natura_documentale(text)[0],'documento_identita')

    def test_atto_non_diventa_documento_personale(self):
        text='TRIBUNALE DI VELLETRI RICORSO. Cognome Rossi Nome Mario Cittadinanza ITALIANA. Si allega copia documento AT9974233, scade il 30/05/2025, connotati.'
        self.assertNotEqual(relevance.natura_documentale(text)[0],'documento_identita')

    def test_segnali_incompleti_non_bastano(self):
        self.assertEqual(relevance.natura_documentale('Cognome Rossi Nome Mario Scade il 30/05/2025')[0],'')

if __name__=='__main__':
    unittest.main()
