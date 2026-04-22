from __future__ import annotations

import os
import pathlib
import sys
from collections import deque

DATA_ROOT = pathlib.Path("/data")
RUN_USER = "iusentra"


def _resolve_identity() -> tuple[int, int]:
    import grp
    import pwd

    user = pwd.getpwnam(RUN_USER)
    group = grp.getgrnam(RUN_USER)
    return user.pw_uid, group.gr_gid


def _prepare_data_root(path: pathlib.Path, uid: int, gid: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    chown_fn = getattr(os, "chown", None)
    if chown_fn is None:
        return
    try:
        chown_fn(path, uid, gid)
    except OSError:
        # Su alcuni volumi gestiti dal provider cloud il mount resta scrivibile
        # anche senza chown esplicito: non blocchiamo l'avvio.
        pass


def _drop_privileges(uid: int, gid: int) -> None:
    os.setgid(gid)
    os.setuid(uid)


def _candidate_write_roots() -> list[pathlib.Path]:
    roots: list[pathlib.Path] = [
        DATA_ROOT,
        DATA_ROOT / "search",
        DATA_ROOT / "system" / "installation",
        DATA_ROOT / "system" / "installation" / "keys",
    ]
    queue: deque[tuple[pathlib.Path, int]] = deque([(DATA_ROOT, 0)])
    seen = {root for root in roots}
    while queue and len(roots) < 20:
        current, depth = queue.popleft()
        if depth >= 4 or not current.exists():
            continue
        try:
            children = sorted((child for child in current.iterdir() if child.is_dir()), key=lambda item: item.name)
        except OSError:
            continue
        for child in children:
            if child in seen:
                continue
            roots.append(child)
            seen.add(child)
            queue.append((child, depth + 1))
            if len(roots) >= 20:
                break
    return roots


def _probe_write_as_user(path: pathlib.Path, uid: int, gid: int) -> bool:
    probe_name = f".iusentra-perm-check-{os.getpid()}"
    probe_path = path / probe_name
    original_euid = os.geteuid()
    original_egid = os.getegid()
    try:
        path.mkdir(parents=True, exist_ok=True)
        os.setegid(gid)
        os.seteuid(uid)
        with probe_path.open("wb") as handle:
            handle.write(b"ok")
        probe_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False
    finally:
        os.seteuid(original_euid)
        os.setegid(original_egid)
        try:
            probe_path.unlink(missing_ok=True)
        except OSError:
            pass


def _should_drop_privileges(uid: int, gid: int) -> bool:
    for candidate in _candidate_write_roots():
        if not _probe_write_as_user(candidate, uid, gid):
            print(
                f"[IUSENTRA] Volume host non compatibile con scrittura come {RUN_USER} su {candidate}; "
                "continuo come root in modo esplicito per non rompere il runtime locale.",
                file=sys.stderr,
                flush=True,
            )
            return False
    return True


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("Comando runtime mancante.")

    uid, gid = _resolve_identity()

    _prepare_data_root(DATA_ROOT, uid, gid)

    if os.geteuid() == 0:
        if _should_drop_privileges(uid, gid):
            _drop_privileges(uid, gid)

    os.execvp(argv[1], argv[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
