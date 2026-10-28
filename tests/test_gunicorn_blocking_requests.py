"""Il server deve restare vivo durante un lettore nativo non cooperativo."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import importlib.util
import tempfile
import unittest
from urllib.request import urlopen
from urllib.error import URLError


def _exercise_native_reader(tmp_path, polling_requests=1):
    app = tmp_path / "controlled_native_reader.py"
    app.write_text("""import ctypes

def application(environ, start_response):
    if environ['PATH_INFO'] == '/read':
        ctypes.CDLL(None).sleep(4)
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b'ok']
""")
    bootstrap = Path(os.environ.get("IUSENTRA_TEST_WSGI") or (Path(__file__).resolve().parents[1] / "wsgi.py"))
    (tmp_path / "wsgi_under_test.py").write_text(bootstrap.read_text())
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "__init__.py").touch()
    (tmp_path / "web" / "app.py").write_text("from controlled_native_reader import application\ndef create_app(): return application\n")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env.pop("GUNICORN_WORKER_CLASS", None)
    env.pop("GUNICORN_MAX_REQUESTS", None)
    env.pop("GUNICORN_MAX_REQUESTS_JITTER", None)
    env.update(GUNICORN_BIND=f"127.0.0.1:{port}", WEB_CONCURRENCY="1",
               GUNICORN_THREADS="2", GUNICORN_TIMEOUT="1", GUNICORN_GRACEFUL_TIMEOUT="1")
    config = Path(os.environ.get("IUSENTRA_TEST_GUNICORN_CONFIG") or (Path(__file__).resolve().parents[1] / "gunicorn.conf.py"))
    with (tmp_path / "server.log").open("w+") as log:
        process = subprocess.Popen([sys.executable, "-m", "gunicorn", "--config", str(config),
                                    "wsgi_under_test:app"], cwd=tmp_path,
                                   env=env, stdout=log, stderr=log, start_new_session=True)
        try:
            url = f"http://127.0.0.1:{port}"
            ready = False
            for _ in range(80):
                try:
                    ready = urlopen(url, timeout=.2).status == 200
                    if ready:
                        break
                except (URLError, OSError):
                    pass
                time.sleep(.1)
            assert ready
            with ThreadPoolExecutor(max_workers=1) as executor:
                slow = executor.submit(urlopen, url + "/read", timeout=10)
                time.sleep(.5)
                for _ in range(polling_requests):
                    assert urlopen(url, timeout=1.5).status == 200
                assert slow.result(timeout=10).status == 200
            log.flush()
            log.seek(0)
            assert "WORKER TIMEOUT" not in log.read()
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)


@unittest.skipUnless(os.name == "posix" and importlib.util.find_spec("gunicorn"), "Runtime Gunicorn POSIX richiesto")
class GunicornNativeReaderTest(unittest.TestCase):
    def test_worker_non_muore_ne_blocca_ui_durante_lettura_nativa(self):
        with tempfile.TemporaryDirectory(prefix="iusentra-native-reader-test-") as root:
            _exercise_native_reader(Path(root))

    def test_polling_non_ricicla_worker_con_importazione_in_corso(self):
        with tempfile.TemporaryDirectory(prefix="iusentra-import-polling-test-") as root:
            _exercise_native_reader(Path(root), polling_requests=1200)


if __name__ == "__main__":
    unittest.main()
