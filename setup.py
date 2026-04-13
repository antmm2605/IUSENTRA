from setuptools import setup, find_packages

setup(
    name="pct-studio-legale",
    version="2.151.7",
    description="Sistema invio telematico per studi legali (PCT - Processo Civile Telematico)",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "pct": ["data/*.json"],
    },
    python_requires=">=3.9",
    install_requires=[
        "cryptography>=41.0.0",
        "lxml>=4.9.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "click>=8.1.0",
        "flask>=3.0.0",
        "apscheduler>=3.10.0",
        "jinja2>=3.1.0",
        "pdfplumber>=0.10.0",
        "pytesseract>=0.3.10",
        "mammoth>=1.6.0",
        "python-docx>=1.1.0",
        "reportlab>=4.0.0",
        "twilio>=8.0.0",
        "stripe>=7.0.0",
        "zeep>=4.2.1",
    ],
    extras_require={
        "pades": ["pyhanko>=0.20.0", "pyhanko-certvalidator>=0.26.0"],
        "pdf": ["reportlab>=4.0.0", "pdfplumber>=0.10.0"],
        "pkcs11": ["python-pkcs11>=0.7.0", "asn1crypto>=1.5.0"],
    },
    entry_points={
        "console_scripts": [
            "pct=pct.cli:main",
            "pct-web=web.__main__:app.run",
        ],
    },
)
