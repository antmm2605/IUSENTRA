"""Guardrail tecnico: dettaglio puntuale, priorità corrente e nessuna scrittura."""
from datetime import date, timedelta
from types import SimpleNamespace
import unittest

from pct.scadenziario import Scadenza, PrioritaTermine, StatoTermine
from web.services.react_scadenziario_bridge import build_react_scadenziario_payload


class CompactDeadlinePriorityTests(unittest.TestCase):
    def test_compact_recalculates_native_priority_without_loading_or_saving_archive(self):
        for days, expected in [(0, "CRITICA"), (2, "CRITICA"), (5, "ALTA"), (20, "MEDIA"), (45, "BASSA")]:
            with self.subTest(days=days):
                item = Scadenza(id="controlled-priority", titolo="Guardrail tecnico", priorita=PrioritaTermine.ALTA,
                    data_scadenza=(date.today() + timedelta(days=days)).isoformat())
                calls = []
                def get_selected(identifier):
                    calls.append(identifier)
                    return item
                def forbidden(*args, **kwargs):
                    raise AssertionError("Il dettaglio non deve caricare o scrivere l'archivio")
                deadlines = SimpleNamespace(get=get_selected, tutte=forbidden, aggiorna=forbidden, _salva=forbidden)
                matters = SimpleNamespace(get=lambda identifier: None)
                payload = build_react_scadenziario_payload(gestione_scadenziario=deadlines, gestione_fascicoli=matters,
                    query_args={"focus_id": item.id, "compatto": "1", "calcolatore": "0"})
                self.assertEqual(calls, [item.id])
                self.assertEqual([row["id"] for row in payload["items"]], [item.id])
                self.assertEqual(payload["items"][0]["priority"], expected)
                self.assertEqual(item.stato, StatoTermine.APERTO)
                self.assertEqual(item.completata_il, "")
                self.assertEqual(payload["nextItems"], [])
                self.assertEqual(payload["overduePreview"], [])


if __name__ == "__main__":
    unittest.main()
