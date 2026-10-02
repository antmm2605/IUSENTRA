"""Collegamenti PEC verificati nell'audit; mai attribuzione al primo RG simile."""

from collections import defaultdict


def collegamenti_pec(messaggi: list, fascicoli: dict) -> dict[str, str]:
    from web.services.notification_presidia_runtime import build_notification_presidio_repository

    repo = build_notification_presidio_repository()
    headers = {str(getattr(m, "message_id", "") or "") for m in messaggi}
    headers.discard("")
    by_header = defaultdict(set)
    with repo.connection() as conn:
        for start in range(0, len(headers), 100):
            batch = sorted(headers)[start:start + 100]
            rows = conn.execute(
                "SELECT message_id_header, linked_fascicolo_id FROM pec_messages "
                "WHERE tenant_id=? AND message_id_header IN (" + ",".join("?" for _ in batch) + ")",
                (repo.tenant_id, *batch),
            ).fetchall()
            for row in rows:
                if row["linked_fascicolo_id"] in fascicoli:
                    by_header[row["message_id_header"]].add(row["linked_fascicolo_id"])
    result = {}
    for message in messaggi:
        choices = by_header.get(str(getattr(message, "message_id", "") or ""), set())
        if len(choices) == 1:
            result[str(message.id)] = next(iter(choices))
    return result
