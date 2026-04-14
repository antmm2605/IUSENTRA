from __future__ import annotations

from pct.template_atti import GestioneTemplateAtti


def main() -> None:
    gestore = GestioneTemplateAtti()
    stats = gestore.import_template_repository(gestore.repository_json_path)
    print(
        "Importati "
        f"{stats.get('template_repository', 0)} template in {gestore.repository_db_path}"
    )


if __name__ == "__main__":
    main()
