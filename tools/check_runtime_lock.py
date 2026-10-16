"""Verify the governed Docker runtime without loading the application or its data."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
APPLICATION = 'pct-studio-legale'


def canonical_name(value: str) -> str:
    return re.sub(r'[-_.]+', '-', value).lower()


def load_lock(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.!+\-]+)', line)
        if match is None:
            raise ValueError('Il profilo runtime richiede soltanto versioni esatte.')
        name, version = canonical_name(match[1]), match[2]
        if name == APPLICATION or name in pins:
            raise ValueError('Package applicativo o duplicato nel profilo runtime.')
        pins[name] = version
    if not pins:
        raise ValueError('Profilo runtime vuoto.')
    return pins


def compare_runtime(pins: dict[str, str], installed: dict[str, str], version: str) -> dict:
    expected = {**pins, APPLICATION: version}
    actual = {canonical_name(name): value for name, value in installed.items()}
    missing = sorted(expected.keys() - actual.keys())
    unexpected = sorted(actual.keys() - expected.keys())
    changed = [{'name': name, 'expected': expected[name], 'installed': actual[name]}
               for name in sorted(expected.keys() & actual.keys()) if expected[name] != actual[name]]
    return {'ok': not (missing or unexpected or changed), 'expected_count': len(expected),
            'installed_count': len(actual), 'missing': missing, 'unexpected': unexpected, 'changed': changed}


def installed_snapshot() -> dict[str, str]:
    result: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = canonical_name(distribution.metadata['Name'])
        if name in result and result[name] != distribution.version:
            raise ValueError('Versioni concorrenti del medesimo package nel runtime.')
        result[name] = distribution.version
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', action='store_true', required=True)
    parser.add_argument('--lock', type=Path, default=ROOT / 'requirements/lock/runtime-linux-py312.txt')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    from packaging_manifest import read_version
    try:
        result = compare_runtime(load_lock(args.lock), installed_snapshot(), read_version())
        result['profile_ok'] = (sys.version_info[:2] == (3, 12) and sys.platform == 'linux'
                                and platform.machine() in {'x86_64', 'AMD64'})
        result['ok'] = result['ok'] and result['profile_ok']
    except (OSError, ValueError, TypeError) as exc:
        result = {'ok': False, 'error': str(exc)}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
