"""Aggancio dei pannelli pronti all'app web: viste dei pannelli avvolte e invalidazione dopo le scritture."""

from __future__ import annotations

from flask import Flask

from web.services.pannelli_pronti_runtime import avvolgi_viste, invalida_dopo_scrittura


def registra_pannelli_pronti(app: Flask) -> None:
    avvolti = avvolgi_viste(app)
    app.after_request(invalida_dopo_scrittura)
    app.extensions["pannelli_pronti"] = {"endpoint": avvolti}
