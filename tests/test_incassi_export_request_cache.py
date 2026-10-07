import csv
import io
import unittest
from unittest.mock import Mock, patch

from flask import Flask
from pct.fatturazione import Parcella, VoceParcella
from web.services.react_incassi_pagamenti_bridge import export_incassi_selection_csv


class IncassiExportTests(unittest.TestCase):
    def test_complete_selection_formula_and_italian_values(self):
        rows = [dict(id=f"parcella:{index}", kind="Parcella", label=str(index),
                     customer='=CLIENTE("prova")', stateLabel="Bozza",
                     amountDisplay="€ 1.234,56", dateLabel="05/10/2026") for index in range(250)]
        data = export_incassi_selection_csv(rows, [row["id"] for row in rows])
        self.assertTrue(data.startswith("\ufeff"))
        decoded = list(csv.reader(io.StringIO(data.lstrip("\ufeff")), delimiter=";"))
        self.assertEqual(len(decoded), 251)
        self.assertEqual(decoded[-1][1], "249")
        self.assertEqual(decoded[1][2], '\'=CLIENTE("prova")')
        self.assertEqual(decoded[1][4:], ["€ 1.234,56", "05/10/2026"])

    def test_foreign_or_stale_selection_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non sono più disponibili"):
            export_incassi_selection_csv([dict(id="parcella:own")], ["parcella:foreign"])
        for invalid in ([], "own", [None]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                export_incassi_selection_csv([], invalid)


class CassaRequestCacheTests(unittest.TestCase):
    def invoice(self, year=2026, **options):
        return Parcella(id="controlled", numero="TEST", id_cliente="controlled", id_fascicolo=None,
                        data_emissione=f"{year}-01-01", data_scadenza=None,
                        voci=[VoceParcella("Prestazione controllata", prezzo_unitario=1000)], **options)

    def test_native_amounts_and_year_resolved_with_one_manager_per_request(self):
        app = Flask(__name__)
        manager = Mock()
        manager.cassa_forense_aliquota_integrativa.return_value = 4
        with patch("pct.normative_tables.GestioneTabelleNormative", return_value=manager) as factory:
            with app.test_request_context("/incassi-pagamenti"):
                self.assertEqual(self.invoice().totale, 1268.8)
                self.assertEqual(self.invoice(applica_ritenuta=True).totale, 1068.8)
                self.assertEqual(self.invoice(applica_cassa=False).totale, 1220)
                self.assertEqual(self.invoice(2025, applica_iva=False).totale, 1040)
                self.assertEqual(factory.call_count, 1)
                self.assertIn(unittest.mock.call(2025), manager.cassa_forense_aliquota_integrativa.call_args_list)
            with app.test_request_context("/fatturazione"):
                self.assertEqual(self.invoice().totale, 1268.8)
                self.assertEqual(factory.call_count, 2)

    def test_cli_has_no_request_cache(self):
        manager = Mock()
        manager.cassa_forense_aliquota_integrativa.return_value = 6
        with patch("pct.normative_tables.GestioneTabelleNormative", return_value=manager) as factory:
            self.assertEqual(self.invoice()._aliquota_cassa(), .06)
            self.assertEqual(self.invoice()._aliquota_cassa(), .06)
            self.assertEqual(factory.call_count, 2)
