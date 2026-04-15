"""Download and setup routes for Local Signer telematico assets."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from flask import Flask, Response, redirect, send_file


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
    local_signer_windows_exe_name: Callable[[], str],
    local_signer_windows_offline_ps1_path: Callable[[], Path],
    local_signer_windows_offline_ps1_name: Callable[[], str],
    render_local_signer_windows_ps1: Callable[[str], str],
    local_signer_windows_ps1_name: Callable[[], str],
    local_signer_macos_installer_path: Callable[[], Path],
    local_signer_macos_name: Callable[[], str],
    render_local_signer_macos_command: Callable[[str], str],
    local_signer_linux_installer_path: Callable[[], Path],
    local_signer_linux_name: Callable[[], str],
    render_local_signer_linux_sh: Callable[[str], str],
    get_base_url: Callable[[], str],
) -> None:
    """Register Local Signer package download and installer routes."""

    @app.route("/polisWeb/local-signer/download")
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
            return str(exc), 500

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
            return str(exc), 500

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
            return str(exc), 500

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
            return str(exc), 500

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
            return str(exc), 500

    @app.route("/polisWeb/local-signer/download/python-embedded")
    def polis_local_signer_download_python_embedded():
        return redirect(
            "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip",
            code=302,
        )

    @app.route("/polisWeb/local-signer/setup/windows-exe")
    def polis_local_signer_setup_windows_exe():
        try:
            cmd_path = local_signer_windows_cmd_path()
            if cmd_path.exists():
                return send_file(
                    cmd_path,
                    as_attachment=True,
                    download_name=local_signer_windows_cmd_name(),
                    mimetype="application/octet-stream",
                )
            exe_path = local_signer_windows_exe_path()
            if not exe_path.exists():
                return (
                    "Installer Windows non ancora generato. Usare temporaneamente l'installer PowerShell.",
                    404,
                )
            return send_file(
                exe_path,
                as_attachment=True,
                download_name=local_signer_windows_exe_name(),
                mimetype="application/octet-stream",
            )
        except Exception as exc:
            return str(exc), 500

    @app.route("/polisWeb/local-signer/setup/windows")
    def polis_local_signer_setup_windows():
        base_url = get_base_url()
        cmd_path = local_signer_windows_cmd_path()
        if cmd_path.exists():
            return send_file(
                cmd_path,
                as_attachment=True,
                download_name=local_signer_windows_cmd_name(),
                mimetype="application/octet-stream",
            )
        exe_path = local_signer_windows_exe_path()
        if exe_path.exists():
            return send_file(
                exe_path,
                as_attachment=True,
                download_name=local_signer_windows_exe_name(),
                mimetype="application/octet-stream",
            )
        offline_ps1 = local_signer_windows_offline_ps1_path()
        if offline_ps1.exists():
            return send_file(
                offline_ps1,
                as_attachment=True,
                download_name=local_signer_windows_offline_ps1_name(),
                mimetype="text/plain; charset=utf-8",
            )
        return Response(
            render_local_signer_windows_ps1(base_url),
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{local_signer_windows_ps1_name()}"'},
        )

    @app.route("/polisWeb/local-signer/installa-windows")
    def polis_local_signer_installa():
        try:
            return Response(
                render_local_signer_windows_ps1(get_base_url()),
                mimetype="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{local_signer_windows_ps1_name()}"',
                },
            )
        except Exception as exc:
            app.logger.exception("Errore generazione script installer: %s", exc)
            return str(exc), 500

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
            return str(exc), 500

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
            return str(exc), 500
