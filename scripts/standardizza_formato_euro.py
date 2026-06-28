"""Standardizza gli importi visibili IUSENTRA in formato italiano.

Lo script modifica solo sorgenti e template, non bundle compilati, dati runtime,
tracciati FatturaPA/SdI, parser o colonne tecniche valuta.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_PARTS = {
    ".git",
    "data",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
}
EXCLUDED_PREFIXES = {
    Path("pct/data"),
    Path("tests/fixtures"),
    Path("web/static/react/assets"),
    Path("web/static/react/.vite"),
}

TECHNICAL_EUR_FILES = {
    Path("pct/fattura_pa.py"),
    Path("pct/database.py"),
    Path("pct/storage_postgres.py"),
    Path("pct/storage_migration.py"),
    Path("pct/pagamenti.py"),
    Path("web/services/react_impostazioni_payments.py"),
    Path("scripts/standardizza_formato_euro.py"),
}


def rel(path: Path) -> Path:
    return path.relative_to(ROOT)


def is_excluded(path: Path) -> bool:
    relative = rel(path)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return True
    return any(relative == prefix or prefix in relative.parents for prefix in EXCLUDED_PREFIXES)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def replace_file(path: Path, transform) -> bool:
    original = read(path)
    updated = transform(original)
    if updated == original:
        return False
    write(path, updated)
    return True


def ensure_import(text: str, import_line: str, anchor: str | None = None) -> str:
    if import_line in text:
        return text
    if anchor and anchor in text:
        return text.replace(anchor, anchor + "\n" + import_line, 1)
    match = re.search(r"(^from __future__ import annotations\s*\n)", text, flags=re.MULTILINE)
    if match:
        idx = match.end()
        return text[:idx] + "\n" + import_line + "\n" + text[idx:]
    return import_line + "\n" + text


def normalize_py_formatter(text: str) -> str:
    text = ensure_import(text, "from pct.formatting import format_euro_it")
    text = re.sub(
        r"def _fmt_money\(value: Any\) -> str:\n"
        r"(?:    .+\n){1,8}?    return text\.replace\(\"\,\", \"X\"\)\.replace\(\"\\.\", \"\,\"\)\.replace\(\"X\", \"\\.\"\)\n",
        "def _fmt_money(value: Any) -> str:\n    return format_euro_it(value)\n",
        text,
    )
    text = re.sub(
        r"def _money\(value: Any\) -> str:\n"
        r"(?:    .+\n){1,8}?    return f\"EUR \{amount:,.2f\}\"\.replace\(\"\,\", \"X\"\)\.replace\(\"\\.\", \"\,\"\)\.replace\(\"X\", \"\\.\"\)\n",
        "def _money(value: Any) -> str:\n    return format_euro_it(value)\n",
        text,
    )
    text = re.sub(
        r"def _currency\(value: float \| int\) -> str:\n"
        r"    return f\"EUR \{_round_amount\(value\):,.2f\}\"\.replace\(\"\,\", \"X\"\)\.replace\(\"\\.\", \"\,\"\)\.replace\(\"X\", \"\\.\"\)\n",
        "def _currency(value: float | int) -> str:\n    return format_euro_it(_round_amount(value))\n",
        text,
    )
    text = re.sub(
        r"def (_amount|_euro|_money)\(value: Any\) -> str:\n"
        r"(?:    .+\n){1,8}?    return f\"EUR \{text\}\"\n",
        lambda m: f"def {m.group(1)}(value: Any) -> str:\n    return format_euro_it(value)\n",
        text,
    )
    text = re.sub(
        r"def _euro\(value: float\) -> str:\n"
        r"(?:    .+\n){1,5}?    return f\"EUR \{text\}\"\n",
        "def _euro(value: float) -> str:\n    return format_euro_it(value)\n",
        text,
    )
    text = text.replace('return f"EUR {rendered}"', "return format_euro_it(value)")
    text = text.replace('return "EUR " + f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")', "return format_euro_it(value)")
    text = text.replace('return f"EUR {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")', "return format_euro_it(value)")
    text = text.replace('return f"{prefix}EUR {rendered}"', 'return f"{prefix}{format_euro_it(amount)}"')
    text = text.replace('f"EUR {_fmt_money(', 'f"{_fmt_money(')
    text = text.replace("f'EUR {_fmt_money(", "f'{_fmt_money(")
    return text


def normalize_frontend_text(text: str) -> str:
    text = text.replace("'EUR 0,00'", "'€ 0,00'")
    text = text.replace('"EUR 0,00"', '"€ 0,00"')
    text = text.replace("`EUR 0,00`", "`€ 0,00`")
    text = text.replace(".replace('€', 'EUR').trim()", ".trim()")
    text = text.replace(".replace('â‚¬', 'EUR').trim()", ".trim()")
    text = text.replace("Valore causa (EUR)", "Valore causa (€)")
    text = text.replace("Compenso pattuito (EUR)", "Compenso pattuito (€)")
    text = text.replace("Valore preventivato (EUR)", "Valore preventivato (€)")
    text = text.replace("Valore controversia (EUR)", "Valore controversia (€)")
    text = text.replace("Tariffa oraria (EUR/ora)", "Tariffa oraria (€/ora)")
    text = text.replace("Emesso (EUR)", "Emesso (€)")
    text = text.replace(" oltre EUR 520.000", " oltre € 520.000")
    text = text.replace("Oltre EUR 520.000", "Oltre € 520.000")
    text = text.replace("Molto alta / oltre EUR 520.000", "Molto alta / oltre € 520.000")
    return text


def normalize_visible_eur_labels(text: str) -> str:
    """Converte etichette e note visibili, lasciando intatti parser e campi macchina."""
    text = text.replace("EUR-Lex", "__IUSENTRA_EURLEX__")
    text = text.replace("EUR ", "€ ")
    text = text.replace(" EUR", " €")
    text = text.replace("__IUSENTRA_EURLEX__", "EUR-Lex")
    return text


def normalize_jinja_money(text: str) -> str:
    amount_expr = r"([^{}]+?)"
    patterns = [
        (rf"€\s*\{{\{{\s*[\"']%\.2f[\"']\|format\({amount_expr}\)\s*(?:\|replace\([^}}]+\))?\s*\}}\}}", r"{{ \1|euro }}"),
        (rf"EUR\s*\{{\{{\s*[\"']%\.2f[\"']\|format\({amount_expr}\)\s*(?:\|replace\([^}}]+\))?\s*\}}\}}", r"{{ \1|euro }}"),
        (rf"&euro;\s*\{{\{{\s*[\"']%\.2f[\"']\|format\({amount_expr}\)\s*(?:\|replace\([^}}]+\))?\s*\}}\}}", r"{{ \1|euro }}"),
        (rf"\{{\{{\s*[\"']%\.2f[\"']\|format\({amount_expr}\)\s*(?:\|replace\([^}}]+\))?\s*\}}\}}\s*€", r"{{ \1|euro }}"),
        (rf"\{{\{{\s*[\"']%\.2f[\"']\|format\({amount_expr}\)\s*(?:\|replace\([^}}]+\))?\s*\}}\}}\s*EUR", r"{{ \1|euro }}"),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    text = text.replace("(EUR)", "(€)")
    text = text.replace("EUR/ora", "€/ora")
    text = text.replace("EUR 200-500", "€ 200-500")
    text = text.replace("EUR 200/ora", "€ 200/ora")
    text = text.replace("EUR 500/ora", "€ 500/ora")
    text = text.replace("Parametro nel range indicativo EUR 200-500", "Parametro nel range indicativo € 200-500")
    text = text.replace("Oltre EUR 520.000", "Oltre € 520.000")
    text = text.replace("oltre EUR 520.000", "oltre € 520.000")
    text = text.replace("${item.importo.toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} EUR", "€ ${item.importo.toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}")
    text = text.replace("(EUR ${p.totale.toFixed(2)})", "(€ ${Number(p.totale || 0).toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })})")
    return text


def normalize_python_visible_money(text: str) -> str:
    text = ensure_import(text, "from pct.formatting import format_euro_it")
    text = re.sub(r'f"€ \{([^{}]+):,.2f\}"', r"format_euro_it(\1)", text)
    text = re.sub(r'f"â‚¬ \{([^{}]+):,.2f\}"', r"format_euro_it(\1)", text)
    text = re.sub(r'f"EUR \{([^{}]+):,.2f\}"', r"format_euro_it(\1)", text)
    text = re.sub(r'f"Euro \{([^{}]+):,.2f\}"', r"format_euro_it(\1)", text)
    text = re.sub(r"f'€ \{([^{}]+):,.2f\}'", r"format_euro_it(\1)", text)
    text = re.sub(r"f'EUR \{([^{}]+):,.2f\}'", r"format_euro_it(\1)", text)
    text = re.sub(r"€ \{([^{}]+):,.2f\}", r"{format_euro_it(\1)}", text)
    text = re.sub(r"EUR \{([^{}]+):,.2f\}", r"{format_euro_it(\1)}", text)
    text = re.sub(r"\{([^{}]+):,.2f\} EUR", r"{format_euro_it(\1)}", text)
    text = re.sub(r"\{([^{}]+):.2f\} EUR", r"{format_euro_it(\1)}", text)
    text = re.sub(r"EUR \{([^{}]+):.2f\}", r"{format_euro_it(\1)}", text)
    text = re.sub(r"€ \{([^{}]+):.2f\}", r"{format_euro_it(\1)}", text)
    text = text.replace("tariffa EUR {tariffa:.2f}/h", "tariffa {format_euro_it(tariffa)}/h")
    text = text.replace("Importo: *€ {totale:,.2f}*", "Importo: *{format_euro_it(totale)}*")
    return text


def install_jinja_filter(text: str) -> str:
    text = re.sub(
        r"from pct\.formatting import [^\n]*",
        "from pct.formatting import format_euro_it, format_signed_euro_it",
        text,
        count=1,
    )
    text = ensure_import(text, "from pct.formatting import format_euro_it, format_signed_euro_it")
    if '@app.template_filter("euro")' in text and '@app.template_filter("euro_signed")' in text:
        return text
    marker = '    """Register shared Jinja filters and context globals."""\n'
    if marker not in text:
        return text
    addition = (
        marker
        + '\n'
        + '    @app.template_filter("euro")\n'
        + "    def fmt_euro(val: Any) -> str:\n"
        + "        return format_euro_it(val)\n\n"
        + '    @app.template_filter("euro_signed")\n'
        + "    def fmt_euro_signed(val: Any) -> str:\n"
        + "        return format_signed_euro_it(val)\n\n"
    )
    return text.replace(marker, addition, 1)


def audit_visible_eur() -> list[str]:
    findings: list[str] = []
    allowed_substrings = (
        "EUR-Lex",
        '"EUR"',
        "'EUR'",
        "valuta",
        "currency",
        "Divisa",
        "replace(\"EUR\"",
        "replace(/EUR",
        "_MONEY_PREFIX_PATTERN",
        "FatturaPA",
        "fatturapa",
        "SDI",
        "SdI",
        "api",
        "storage",
    )
    for path in ROOT.rglob("*"):
        if not path.is_file() or is_excluded(path):
            continue
        relative = rel(path)
        if relative in TECHNICAL_EUR_FILES:
            continue
        if path.suffix.lower() not in {".py", ".tsx", ".ts", ".html", ".js"}:
            continue
        try:
            text = read(path)
        except UnicodeDecodeError:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            if "EUR" not in line:
                continue
            if any(token in line for token in allowed_substrings):
                continue
            findings.append(f"{relative.as_posix()}:{idx}: {line.strip()[:160]}")
    return findings


def main() -> int:
    changed: list[str] = []

    target_formatters = [
        Path("pct/applicazioni_runtime.py"),
        Path("pct/economic_dashboard.py"),
        Path("web/services/applicazioni_runtime.py"),
        Path("web/services/react_clienti_bridge.py"),
        Path("web/services/react_fascicoli_bridge.py"),
        Path("web/services/react_incassi_pagamenti_bridge.py"),
        Path("web/services/react_preventivo_wizard_bridge.py"),
        Path("web/services/react_preventivi_bridge.py"),
        Path("web/services/react_studio_module_bridge.py"),
        Path("web/services/react_tariffario_compute.py"),
        Path("web/services/react_timesheet_bridge.py"),
        Path("web/blueprints/api_v1_react.py"),
        Path("pct/practice_engine/evaluator.py"),
    ]
    for relative in target_formatters:
        path = ROOT / relative
        if path.exists() and replace_file(path, normalize_py_formatter):
            changed.append(relative.as_posix())

    py_visible_files = [
        Path("web/blueprints/fatturazione.py"),
        Path("web/blueprints/preventivi.py"),
        Path("web/notifiche.py"),
        Path("web/template_atti.py"),
        Path("pct/cli.py"),
        Path("pct/compilatore_atti.py"),
        Path("pct/compensi_a_tempo.py"),
        Path("pct/notifiche_wa.py"),
        Path("pct/operational_resilience.py"),
        Path("pct/strumenti_legali.py"),
        Path("lex/providers/deterministic_provider.py"),
    ]
    for relative in py_visible_files:
        path = ROOT / relative
        if path.exists() and replace_file(path, normalize_python_visible_money):
            changed.append(relative.as_posix())

    visible_label_files = [
        Path("pct/tariffario.py"),
        Path("pct/tariffario_catalogo.py"),
        Path("pct/mediazione_dm150.py"),
        Path("pct/normative_tables.py"),
        Path("web/services/react_tariffario_compute.py"),
        Path("tests/test_economico_context.py"),
        Path("tests/test_mediazione_dm150.py"),
        Path("tests/test_normative_tables.py"),
        Path("tests/test_preventivi_wizard_tariffario_audit.py"),
        Path("tests/test_react_tariffario_console.py"),
        Path("tests/test_tariffario.py"),
        Path("tests/test_tariffario_fascia_alta.py"),
        Path("lex/tests/unit/test_deterministic_provider.py"),
    ]
    for relative in visible_label_files:
        path = ROOT / relative
        if path.exists() and replace_file(path, normalize_visible_eur_labels):
            changed.append(relative.as_posix())

    runtime_filter = ROOT / "web/bootstrap/template_runtime.py"
    if runtime_filter.exists() and replace_file(runtime_filter, install_jinja_filter):
        changed.append(rel(runtime_filter).as_posix())

    for path in list((ROOT / "web").glob("*.html")) + list((ROOT / "web/templates").rglob("*.html")):
        if is_excluded(path):
            continue
        if replace_file(path, normalize_jinja_money):
            changed.append(rel(path).as_posix())

    for path in (ROOT / "frontend/src").rglob("*"):
        if path.suffix.lower() not in {".ts", ".tsx"} or is_excluded(path):
            continue
        if replace_file(path, normalize_frontend_text):
            changed.append(rel(path).as_posix())

    findings = audit_visible_eur()
    print("modified_files=" + str(len(set(changed))))
    for item in sorted(set(changed)):
        print("MOD " + item)
    print("visible_eur_findings=" + str(len(findings)))
    for item in findings[:200]:
        print("EUR? " + item)
    if len(findings) > 200:
        print(f"... altri {len(findings) - 200} risultati")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
