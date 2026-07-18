"""Download and setup routes for Local Signer telematico assets."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from flask import Flask, Response, redirect, send_file


_LOCAL_SIGNER_MOD_FILES = {
    "__init__.py",
    "ai_cache.py",
    "ai_handlers.py",
    "pec_bridge.py",
    "security.py",
    "server_bootstrap.py",
    "support_agent.py",
}


def register_telematico_local_signer_routes(
    app: Flask,
    *,
    local_signer_python_name: Callable[[], str],
    local_ai_bridge_source_path: Callable[[], Path],
    local_ai_bridge_python_name: Callable[[], str],
    local_ai_lex_context_source_path: Callable[[], Path],
    local_ai_lex_context_python_name: Callable[[], str],
    local_signer_visible_signature_source_path: Callable[[], Path],
    local_signer_visible_signature_python_name: Callable[[], str],
    local_signer_uffici_path: Callable[[], Path],
    local_signer_windows_cmd_path: Callable[[], Path],
    local_signer_windows_cmd_name: Callable[[], str],
    local_signer_windows_exe_path: Callable[[], Path],
    local_signer_windows_exe_alias_path: Callable[[], Path],
    local_signer_windows_exe_name: Callable[[], str],
    local_signer_windows_offline_ps1_path: Callable[[], Path],
    local_signer_windows_offline_ps1_name: Callable[[], str],
    render_local_signer_windows_ps1: Callable[[str], str],
    local_signer_windows_ps1_name: Callable[[], str],
    local_signer_uffici_pst_pubblici_path: Callable[[], Path],
    local_signer_macos_installer_path: Callable[[], Path],
    local_signer_macos_name: Callable[[], str],
    render_local_signer_macos_command: Callable[[str], str],
    local_signer_linux_installer_path: Callable[[], Path],
    local_signer_linux_name: Callable[[], str],
    render_local_signer_linux_sh: Callable[[str], str],
    get_base_url: Callable[[], str],
) -> None:
    """Register Local Signer package download and installer routes."""

    def _send_windows_exe():
        exe_path = local_signer_windows_exe_path()
        download_name = local_signer_windows_exe_name()
        if not exe_path.exists():
            # L'EXE della versione corrente non e' stato ancora rigenerato da
            # Windows (l'EXE IExpress si genera solo su Windows). Serviamo
            # l'ultimo EXE Windows disponibile (alias non versionato): installa
            # comunque Python portatile + venv + sorgenti, e al primo /update il
            # Local Signer aggiorna i sorgenti .py alla versione corrente. Cosi'
            # i nuovi clienti possono sempre scaricare un installer funzionante.
            alias_path = local_signer_windows_exe_alias_path()
            if alias_path.exists():
                exe_path = alias_path
                download_name = alias_path.name
            else:
                return (
                    "Installer Windows .exe non ancora generato. Rigenerare i pacchetti Local Signer.",
                    404,
                )
        return send_file(
            exe_path,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/octet-stream",
        )

    def _send_windows_ps1():
        ps1_path = local_signer_windows_offline_ps1_path()
        if not ps1_path.exists():
            ps1_path = local_signer_windows_exe_path().parent / local_signer_windows_ps1_name()
        if ps1_path.exists():
            return send_file(
                ps1_path,
                as_attachment=True,
                download_name=local_signer_windows_ps1_name(),
                mimetype="text/plain; charset=utf-8",
            )
        return Response(
            render_local_signer_windows_ps1(get_base_url()),
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{local_signer_windows_ps1_name()}"'},
        )

    def _download_error(label: str, exc: Exception):
        app.logger.exception("Errore download Local Signer %s: %s", label, exc)
        return "Download Local Signer non disponibile. Verifica i pacchetti e riprova.", 500

    @app.route("/polisWeb/local-signer/download")
    @app.route("/polisWeb/local-signer/download/local-signer.py")
    def polis_local_signer_download():
        try:
            signer_path = Path(__file__).resolve().parents[2] / "tools" / "local_signer.py"
            if not signer_path.exists():
                return "File non trovato", 404
            return send_file(
                signer_path,
                as_attachment=True,
                download_name=local_signer_python_name(),
                mimetype="text/x-python",
            )
        except Exception as exc:
            return _download_error("python", exc)

    @app.route("/polisWeb/local-signer/download/local-ai-bridge")
    def polis_local_ai_bridge_download():
        try:
            bridge_path = local_ai_bridge_source_path()
            if not bridge_path.exists():
                return "File non trovato", 404
            return send_file(
                bridge_path,
                as_attachment=True,
                download_name=local_ai_bridge_python_name(),
                mimetype="text/x-python",
            )
        except Exception as exc:
            return _download_error("local-ai-bridge", exc)

    @app.route("/polisWeb/local-signer/download/windows-http")
    def polis_local_signer_windows_http_download():
        try:
            helper_path = Path(__file__).resolve().parents[2] / "tools" / "local_signer_windows_http.ps1"
            if not helper_path.exists():
                return "File non trovato", 404
            return send_file(
                helper_path,
                as_attachment=True,
                download_name="local_signer_windows_http.ps1",
                mimetype="text/plain; charset=utf-8",
            )
        except Exception as exc:
            return _download_error("windows-http", exc)

    @app.route("/polisWeb/local-signer/download/lex-document-context")
    def polis_local_ai_lex_context_download():
        try:
            context_path = local_ai_lex_context_source_path()
            if not context_path.exists():
                return "File non trovato", 404
            return send_file(
                context_path,
                as_attachment=True,
                download_name=local_ai_lex_context_python_name(),
                mimetype="text/x-python",
            )
        except Exception as exc:
            return _download_error("lex-document-context", exc)

    @app.route("/polisWeb/local-signer/download/visible-signature")
    def polis_local_signer_visible_signature_download():
        try:
            helper_path = local_signer_visible_signature_source_path()
            if not helper_path.exists():
                return "File non trovato", 404
            return send_file(
                helper_path,
                as_attachment=True,
                download_name=local_signer_visible_signature_python_name(),
                mimetype="text/x-python",
            )
        except Exception as exc:
            return _download_error("visible-signature", exc)

    @app.route("/polisWeb/local-signer/download/requirements")
    def polis_local_signer_requirements_download():
        try:
            requirements_path = Path(__file__).resolve().parents[2] / "tools" / "requirements_local_signer.txt"
            if not requirements_path.exists():
                return "File requisiti non trovato", 404
            return send_file(
                requirements_path,
                as_attachment=True,
                download_name="requirements_local_signer.txt",
                mimetype="text/plain; charset=utf-8",
            )
        except Exception as exc:
            return _download_error("requirements", exc)

    @app.route("/polisWeb/local-signer/download/local-signer-mod/<path:filename>")
    def polis_local_signer_mod_download(filename: str):
        try:
            requested = Path(filename).name
            if requested != filename or requested not in _LOCAL_SIGNER_MOD_FILES:
                return "File non consentito", 404
            module_path = Path(__file__).resolve().parents[2] / "local_signer_mod" / requested
            if not module_path.exists():
                return "Modulo Local Signer non trovato", 404
            return send_file(
                module_path,
                as_attachment=True,
                download_name=requested,
                mimetype="text/x-python",
            )
        except Exception as exc:
            return _download_error("modulo", exc)

    @app.route("/polisWeb/local-signer/download/uffici")
    def polis_local_signer_download_uffici():
        try:
            uffici_path = local_signer_uffici_path()
            if not uffici_path.exists():
                return "Registro uffici non trovato", 404
            return send_file(
                uffici_path,
                as_attachment=True,
                download_name="uffici_ministero.json",
                mimetype="application/json",
            )
        except Exception as exc:
            app.logger.exception("Errore download registro uffici Local Signer: %s", exc)
            return _download_error("uffici", exc)

    @app.route("/polisWeb/local-signer/download/uffici-pst-pubblici")
    def polis_local_signer_download_uffici_pst_pubblici():
        try:
            uffici_path = local_signer_uffici_pst_pubblici_path()
            if not uffici_path.exists():
                return "Catalogo pubblico uffici PST non trovato", 404
            return send_file(
                uffici_path,
                as_attachment=True,
                download_name="uffici_pst_pubblici.json",
                mimetype="application/json",
            )
        except Exception as exc:
            app.logger.exception("Errore download catalogo pubblico uffici PST: %s", exc)
            return _download_error("uffici-pst-pubblici", exc)

    @app.route("/polisWeb/local-signer/download/python-embedded")
    def polis_local_signer_download_python_embedded():
        return redirect(
            "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip",
            code=302,
        )

    @app.route("/polisWeb/local-signer/setup/windows-exe")
    def polis_local_signer_setup_windows_exe():
        try:
            return _send_windows_exe()
        except Exception as exc:
            return _download_error("windows-exe", exc)

    @app.route("/polisWeb/local-signer/setup/windows-ps1")
    def polis_local_signer_setup_windows_ps1():
        try:
            return _send_windows_exe()
        except Exception as exc:
            app.logger.exception("Errore invio installer Windows EXE: %s", exc)
            return _download_error("windows-ps1", exc)

    @app.route("/polisWeb/local-signer/setup/windows")
    def polis_local_signer_setup_windows():
        try:
            return _send_windows_exe()
        except Exception as exc:
            app.logger.exception("Errore invio installer Windows EXE: %s", exc)
            return _download_error("windows", exc)

    @app.route("/polisWeb/local-signer/installa-windows")
    def polis_local_signer_installa():
        try:
            return _send_windows_exe()
        except Exception as exc:
            app.logger.exception("Errore invio installer Windows EXE: %s", exc)
            return _download_error("installa-windows", exc)

    @app.route("/polisWeb/local-signer/setup/macos")
    def polis_local_signer_setup_macos():
        try:
            installer_path = local_signer_macos_installer_path()
            if installer_path.exists():
                return send_file(
                    installer_path,
                    as_attachment=True,
                    download_name=local_signer_macos_name(),
                    mimetype="text/plain; charset=utf-8",
                )
            return Response(
                render_local_signer_macos_command(get_base_url()),
                mimetype="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{local_signer_macos_name()}"'},
            )
        except Exception as exc:
            app.logger.exception("Errore generazione installer macOS: %s", exc)
            return _download_error("macos", exc)

    @app.route("/polisWeb/local-signer/setup/linux")
    def polis_local_signer_setup_linux():
        try:
            installer_path = local_signer_linux_installer_path()
            if installer_path.exists():
                return send_file(
                    installer_path,
                    as_attachment=True,
                    download_name=local_signer_linux_name(),
                    mimetype="text/plain; charset=utf-8",
                )
            return Response(
                render_local_signer_linux_sh(get_base_url()),
                mimetype="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{local_signer_linux_name()}"'},
            )
        except Exception as exc:
            app.logger.exception("Errore generazione installer Linux: %s", exc)
            return _download_error("linux", exc)
