"""Guardrail del catalogo: identità e contesto, senza cambiare il calcolo."""

import unittest
from urllib.parse import parse_qs, urlsplit

from pct.tariffario_catalogo import RULE_ROWS
from web.services.react_compensi_forensi_bridge import _safe_record


class CompensiCatalogContextTests(unittest.TestCase):
    def test_rules_keep_distinct_identity_when_profile_is_shared(self):
        rows = [
            _safe_record(row, index, "regole")
            for index, row in enumerate(RULE_ROWS, start=1)
        ]
        self.assertEqual(len(rows), len({row["id"] for row in rows}))
        for original, rendered in zip(RULE_ROWS, rows):
            self.assertEqual(rendered["id"], original["rule_code"])
            self.assertEqual(rendered["title"], original["label"])

    def test_rule_link_preserves_native_matter_grade_and_rule(self):
        original = next(row for row in RULE_ROWS if row["rule_code"] == "amministrativo_tar")
        rendered = _safe_record(original, 1, "regole")
        link = urlsplit(rendered["href"])
        self.assertEqual(link.path, "/tariffario")
        self.assertEqual(parse_qs(link.query), {
            "materia": [original["materia_label"]],
            "grado": [original["grado_input_value"]],
            "regola_tariffaria": [original["rule_code"]],
        })

    def test_profile_does_not_force_a_rule(self):
        rendered = _safe_record({
            "profile_code": "civile_gdp",
            "table_label": "Tabella 1 - Giudice di Pace",
            "materia_label": "Civile di cognizione",
            "grado_input_value": "Giudice di Pace",
        }, 1, "profili")
        self.assertEqual(rendered["id"], "civile_gdp")
        self.assertNotIn("regola_tariffaria", parse_qs(urlsplit(rendered["href"]).query))


if __name__ == "__main__":
    unittest.main()
