from __future__ import annotations

import re
from pathlib import Path

from packaging_manifest import (
    dev_requirements,
    extras_requirements,
    read_version,
    render_flat_requirements,
    runtime_requirements,
)
from pct import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]

RUNTIME_HEADER = """# requirements.txt - file flat generato da requirements/base.txt
# Non modificare a mano: usare requirements/*.txt e tools/sync_packaging_files.py
"""

DEV_HEADER = """# requirements-dev.txt - file flat generato da requirements/dev.txt
# Non modificare a mano: usare requirements/*.txt e tools/sync_packaging_files.py
"""


def test_versione_allineata_tra_package_docker_e_railway():
    docker_text = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    railway_text = (REPO_ROOT / "railway.toml").read_text(encoding="utf-8")

    docker_version = re.search(r'org\.opencontainers\.image\.version="([^"]+)"', docker_text)
    railway_version = re.search(r"#\s+version:\s+([0-9]+\.[0-9]+\.[0-9]+)", railway_text)

    assert read_version() == __version__
    assert docker_version is not None and docker_version.group(1) == __version__
    assert railway_version is not None and railway_version.group(1) == __version__


def test_setup_py_usa_manifest_governato_per_versione_e_requirements():
    setup_text = (REPO_ROOT / "setup.py").read_text(encoding="utf-8")

    assert "sys.path.insert(0, str(Path(__file__).resolve().parent))" in setup_text
    assert "from packaging_manifest import extras_requirements, read_version, runtime_requirements" in setup_text
    assert "version=read_version()" in setup_text
    assert "install_requires=runtime_requirements()" in setup_text
    assert "extras_require=extras_requirements()" in setup_text


def test_manifest_runtime_ed_extra_coprono_i_backend_e_gli_extra_ufficiali():
    runtime = set(runtime_requirements())
    extras = extras_requirements()

    assert {"psycopg2-binary==2.9.11", "PyMySQL>=1.1.0", "sqlalchemy>=2.0.0"}.issubset(runtime)
    assert "flask-sock>=0.7.0" in runtime
    assert "PyYAML>=6.0.2" in runtime
    assert extras["pdf"] == [
        "mammoth>=1.6.0",
        "pdfplumber>=0.10.0",
        "pypdf>=6.0.0",
        "pytesseract>=0.3.10",
        "python-docx>=1.1.0",
        "reportlab>=4.0.0",
    ]
    assert extras["pades"] == [
        "pyhanko>=0.20.0",
        "pyhanko-certvalidator>=0.26.0",
    ]
    assert extras["pkcs11"] == [
        "python-pkcs11>=0.7.0",
        "asn1crypto>=1.5.0",
    ]


def test_flat_requirements_sono_generati_dal_manifest():
    runtime_expected = render_flat_requirements(RUNTIME_HEADER, runtime_requirements())
    dev_expected = render_flat_requirements(DEV_HEADER, dev_requirements())

    assert (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8") == runtime_expected
    assert (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8") == dev_expected


def test_docker_runtime_ha_healthcheck_railway_compatibile_e_entrypoint_hardened():
    docker_text = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    railway_text = (REPO_ROOT / "railway.toml").read_text(encoding="utf-8")

    assert "HEALTHCHECK" in docker_text
    assert 'VOLUME ["/data"]' not in docker_text
    assert "RUN mkdir -p /data" in docker_text
    assert "/api/pronto" in docker_text
    assert "${PORT:-8080}" in docker_text
    assert "os.getenv('PORT', '8080')" in docker_text
    assert 'adduser --system --ingroup iusentra' in docker_text
    assert "COPY pyproject.toml ." in docker_text
    assert "COPY packaging_manifest.py ." in docker_text
    assert "COPY requirements ./requirements" in docker_text
    assert 'COPY docker/entrypoint.py /usr/local/bin/iusentra-entrypoint.py' in docker_text
    assert 'ENTRYPOINT ["python", "/usr/local/bin/iusentra-entrypoint.py"]' in docker_text
    assert "/api/pronto" in compose_text
    assert "pct.scheduler_worker" in compose_text
    assert "pct.ocr_worker" in compose_text
    assert "healthcheck:" in compose_text
    assert 'healthcheckPath = "/api/pronto"' in railway_text
    assert "healthcheckTimeout = 180" in railway_text


def test_root_governance_docs_e_pyproject_sono_presenti():
    assert (REPO_ROOT / "pyproject.toml").exists()
    assert (REPO_ROOT / "LICENSE").exists()
    assert (REPO_ROOT / "SECURITY.md").exists()
    assert (REPO_ROOT / "CONTRIBUTING.md").exists()


def test_ci_include_packaging_check_coverage_ed_e2e_smoke():
    ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    nightly_text = (REPO_ROOT / ".github" / "workflows" / "e2e-nightly.yml").read_text(encoding="utf-8")

    assert "python tools/sync_packaging_files.py --check" in ci_text
    assert "pytest --cov" in ci_text
    assert "tests/e2e/test_studio_reale_flow.py" in ci_text
    assert "tests/e2e/test_ai_pipeline_full.py" in nightly_text
    assert "tests/e2e/test_tenant_migration_full.py" in nightly_text
    assert "tests/e2e/test_operational_crash_day.py" in nightly_text
