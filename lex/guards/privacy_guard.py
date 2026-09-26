"""Filtri minimi privacy per i payload Lex.

Il modello di Lex gira sullo stesso host di IUSENTRA (Ollama locale, vedi
CLAUDE.md «AI locale»): i dati del fascicolo non escono dal server, quindi qui
non si maschera nulla e il controllo lascia passare. L'unico canale verso
l'esterno è la ricerca pubblica governata, che ha la propria guardia in
`integrations/` (nessun dato personale nelle query). Se in futuro Lex usasse un
modello remoto, questa guardia dovrà mascherare nomi, codici fiscali e
riferimenti di causa prima dell'invio (art. 25 e 28 GDPR).
"""

from __future__ import annotations

from typing import Any


class PrivacyGuard:
    def sanitize_sections(self, sections: dict[str, Any] | None) -> dict[str, Any]:
        return dict(sections or {})

    def check(self, **kwargs):
        from lex.contracts import GuardVerdict

        return GuardVerdict(allowed=True)
