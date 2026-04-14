from __future__ import annotations

from pathlib import Path

from pct.template_atti import GestioneTemplateAtti


def main() -> None:
    gestore = GestioneTemplateAtti()
    output_path = Path(gestore.export_template_repository())
    payload = gestore.repository_payload()
    print(f"Esportati {payload.get('count', 0)} template in {output_path}")


if __name__ == "__main__":
    main()
