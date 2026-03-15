from setuptools import setup, find_packages

setup(
    name="pct-studio-legale",
    version="1.0.0",
    description="Sistema invio telematico per studi legali (PCT - Processo Civile Telematico)",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "cryptography>=41.0.0",
        "lxml>=4.9.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "click>=8.1.0",
        "flask>=3.0.0",
    ],
    extras_require={
        "pades": ["pyhanko>=0.20.0", "pyhanko-certvalidator>=0.26.0"],
        "pdf": ["reportlab>=4.0.0"],
    },
    entry_points={
        "console_scripts": [
            "pct=pct.cli:main",
            "pct-web=web.__main__:app.run",
        ],
    },
)
