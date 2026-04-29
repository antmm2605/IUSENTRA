from pathlib import Path
import sys

from setuptools import find_packages, setup

sys.path.insert(0, str(Path(__file__).resolve().parent))

from packaging_manifest import extras_requirements, read_version, runtime_requirements


setup(
    name="pct-studio-legale",
    # Versione applicativa 2.195.18, letta dalla source of truth pct.__init__
    version=read_version(),
    description="IUSENTRA: gestionale web modulare per studi legali con PCT, Lex locale e servizi telematici",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "pct": ["data/*.json", "sql/*.sql", "template_atti_catalogo_data/*.json"],
        "lex": ["research/source_policy/*.yaml"],
    },
    python_requires=">=3.12",
    install_requires=runtime_requirements(),
    extras_require=extras_requirements(),
    entry_points={
        "console_scripts": [
            "pct=pct.cli:main",
            "iusentra=pct.cli:main",
            "pct-web=web.__main__:app.run",
        ],
    },
)
