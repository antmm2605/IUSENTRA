from pct.studio_demo import build_studio_demo_snapshot


class _Item:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_build_studio_demo_snapshot_identifica_prossimo_passo():
    snapshot = build_studio_demo_snapshot(
        clienti=[_Item(id="cli-1")],
        fascicoli=[],
        preventivi=[],
        conferimenti=[],
        parcelle=[],
        timesheet_entries=[],
        payment_links=[],
    )

    assert snapshot["ready"] is False
    assert snapshot["ready_steps"] == 1
    assert snapshot["steps_total"] == 7
    assert snapshot["next_action"] == "Usa il preventivo guidato per trasformare la richiesta in percorso operativo."
