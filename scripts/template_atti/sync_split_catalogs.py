from __future__ import annotations

from apply_cartabia_schema import _read, _sync_splits, MASTER


def main() -> int:
    master = _read(MASTER)
    splits = _sync_splits(master)
    print({key: payload.get("totale_template") for key, payload in splits.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

