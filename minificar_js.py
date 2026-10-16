"""Minifica static/js/src/*.js en static/js/*.js (los archivos que cargan las plantillas).

Edita siempre static/js/src/ y luego corre:  python minificar_js.py
(compilar_css.sh / .bat ya lo llaman antes de collectstatic). Una prueba del CI falla si se olvida.
"""
import sys
from pathlib import Path

try:
    from rjsmin import jsmin
except ImportError:
    sys.exit("Falta rjsmin: pip install -r requirements.txt")

RAIZ = Path(__file__).resolve().parent
SRC = RAIZ / "static" / "js" / "src"
DEST = RAIZ / "static" / "js"


def minificar(texto):
    return jsmin(texto, keep_bang_comments=False).strip() + "\n"


if __name__ == "__main__":
    fuentes = sorted(SRC.glob("*.js"))
    if not fuentes:
        sys.exit(f"No hay archivos en {SRC.relative_to(RAIZ)}")
    for f in fuentes:
        original = f.read_text(encoding="utf-8")
        salida = minificar(original)
        with open(DEST / f.name, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(salida)
        print(f"ok  static/js/{f.name}: {len(original.encode()) / 1024:.1f} KB -> {len(salida.encode()) / 1024:.1f} KB")
