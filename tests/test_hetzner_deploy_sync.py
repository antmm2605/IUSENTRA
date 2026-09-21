"""Il deploy conserva hotfix, file non tracciati e commit esclusivi del server."""

from __future__ import annotations

import subprocess
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "deploy" / "hetzner" / "deploy.sh"


def _blocco_sincronizzazione() -> str:
    """Il ramo "repository gia' presente" dello script, senza riscriverlo qui."""

    sorgente = SCRIPT.read_text(encoding="utf-8")
    inizio = sorgente.index("# 3. Sincronizza repository")
    fine = sorgente.index("DEPLOYED_COMMIT=", inizio)
    sezione = sorgente[inizio:fine]
    corpo = sezione[sezione.index("else\n") + len("else\n") :]
    return corpo[: corpo.rindex("fi\n")]


def _git(*argomenti: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *argomenti],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, Path, str, str]:
    """Un remoto con due commit e una copia locale ferma sul branch gemello.

    Riproduce la situazione del server: i due branch gemelli si alternano, e il
    deploy di uno parte mentre la copia e' ancora sull'altro. Il cambio di ramo
    e' proprio il momento in cui git rifiuta di procedere se l'albero e'
    sporco.
    """

    origine = tmp_path / "origine"
    origine.mkdir()
    _git("init", "--initial-branch", "main", "-q", cwd=origine)
    _git("config", "user.email", "deploy@iusentra.test", cwd=origine)
    _git("config", "user.name", "Deploy", cwd=origine)

    (origine / "deploy/hetzner").mkdir(parents=True)
    (origine / "deploy/hetzner/check_runtime_sources.py").write_text("print(\"guard eseguito\")\n")
    (origine / "app.py").write_text("versione uno\n", encoding="utf-8")
    _git("add", ".", cwd=origine)
    _git("commit", "-qm", "primo", cwd=origine)
    primo = _git("rev-parse", "HEAD", cwd=origine)

    (origine / "app.py").write_text("versione due\n", encoding="utf-8")
    _git("add", ".", cwd=origine)
    _git("commit", "-qm", "secondo", cwd=origine)
    secondo = _git("rev-parse", "HEAD", cwd=origine)

    copia = tmp_path / "repo"
    _git("clone", "-q", str(origine), str(copia), cwd=tmp_path)
    _git("config", "user.email", "deploy@iusentra.test", cwd=copia)
    _git("config", "user.name", "Deploy", cwd=copia)
    _git("checkout", "-q", "-B", "gemello", primo, cwd=copia)

    return origine, copia, primo, secondo


def _sincronizza(copia: Path, commit_atteso: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(Path("C:/Program Files/Git/bin/bash.exe")) if os.name == "nt" else "bash", "-euo", "pipefail", "-c", _blocco_sincronizzazione().replace("python3 ", "python ") if os.name == "nt" else _blocco_sincronizzazione()],
        cwd=copia.parent,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HOME": str(copia.parent),
            "REPO_DIR": str(copia),
            "BRANCH": "main",
            "EXPECTED_SHA": commit_atteso,
        },
    )


def test_un_albero_sporco_blocca_il_deploy_senza_perdere_hotfix(repository):
    """Il caso reale dell'11/09/2026: file modificati sul server."""

    _origine, copia, _primo, secondo = repository
    (copia / "app.py").write_text("modifica arrivata sul server\n", encoding="utf-8")

    esito = _sincronizza(copia, secondo)

    assert esito.returncode != 0
    assert _git("rev-parse", "HEAD", cwd=copia) == _primo
    assert (copia / "app.py").read_text(encoding="utf-8") == "modifica arrivata sul server\n"
    assert "modifiche locali da preservare" in esito.stderr


def test_un_file_non_tracciato_viene_preservato(repository):
    """Residuo di una build interrotta con lo stesso nome di un file del commit."""

    _origine, copia, _primo, secondo = repository
    (copia / "nuovo.py").write_text("residuo\n", encoding="utf-8")

    esito = _sincronizza(copia, secondo)

    assert esito.returncode != 0
    assert _git("rev-parse", "HEAD", cwd=copia) == _primo
    assert (copia / "nuovo.py").read_text() == "residuo\n"


def test_un_albero_pulito_arriva_al_commit_verificato(repository):
    _origine, copia, _primo, secondo = repository

    esito = _sincronizza(copia, secondo)

    assert esito.returncode == 0, esito.stderr
    assert _git("rev-parse", "HEAD", cwd=copia) == secondo
    assert _git("rev-parse", "main", cwd=copia) == secondo
    assert "Albero di lavoro non pulito" not in esito.stdout


def test_il_branch_locale_resta_sul_commit_verificato(repository):
    """Il ramo deve puntare al commit, non restare indietro in HEAD staccato.

    Il controllo successivo dello script confronta ``git rev-parse HEAD`` con
    EXPECTED_SHA e si ferma se non coincidono.
    """

    _origine, copia, _primo, secondo = repository

    esito = _sincronizza(copia, secondo)

    assert esito.returncode == 0, esito.stderr
    assert _git("rev-parse", "HEAD", cwd=copia) == secondo
    assert _git("symbolic-ref", "--short", "HEAD", cwd=copia) == "main"


def test_un_commit_solo_sul_server_non_viene_scartato(repository):
    _, copia, _, secondo = repository
    (copia / "hotfix.py").write_text("hotfix\n")
    _git("add", ".", cwd=copia)
    _git("commit", "-qm", "hotfix server", cwd=copia)
    before = _git("rev-parse", "HEAD", cwd=copia)
    result = _sincronizza(copia, secondo)
    assert result.returncode != 0
    assert "tutti i commit del server" in result.stderr
    assert _git("rev-parse", "HEAD", cwd=copia) == before
    assert (copia / "hotfix.py").read_text() == "hotfix\n"


def test_una_release_superata_non_parte(repository):
    _, copia, primo, _ = repository
    result = _sincronizza(copia, primo)
    assert result.returncode != 0
    assert "testa del branch" in result.stderr
    assert _git("rev-parse", "HEAD", cwd=copia) == primo
