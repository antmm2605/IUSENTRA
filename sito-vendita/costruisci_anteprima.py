"""Crea un'unica pagina autonoma (stile e script in linea) per l'anteprima del sito."""
import re, sys
from pathlib import Path

base = Path(__file__).parent
html = (base / "index.html").read_text(encoding="utf-8")
corpo = re.search(r"<!--CONTENUTO-->(.*)<!--/CONTENUTO-->", html, re.S).group(1)
titolo = re.search(r"<title>.*?</title>", html).group(0)
font = re.search(r'<link rel="stylesheet" href="https://fonts[^>]+>', html).group(0)
css = (base / "assets/stile.css").read_text(encoding="utf-8")
js = (base / "assets/app.js").read_text(encoding="utf-8")
out = f"{titolo}\n{font}\n<style>\n{css}\n</style>\n{corpo}\n<script>\n{js}\n</script>\n"
dest = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "anteprima.html"
dest.write_text(out, encoding="utf-8")
print(dest)
