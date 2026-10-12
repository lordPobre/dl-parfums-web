#!/bin/bash
# Compila Tailwind a static/css/app.css y actualiza staticfiles/ (macOS / Linux)
set -e
VER="v3.4.17"
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) BIN="tailwindcss-macos-arm64" ;;
  Darwin-*)     BIN="tailwindcss-macos-x64" ;;
  *-aarch64)    BIN="tailwindcss-linux-arm64" ;;
  *)            BIN="tailwindcss-linux-x64" ;;
esac
if [ ! -f ./tailwindcss ]; then
  curl -sLo tailwindcss "https://github.com/tailwindlabs/tailwindcss/releases/download/$VER/$BIN"
  chmod +x tailwindcss
fi
./tailwindcss -c tailwind.config.js -i static/css/input.css -o static/css/app.css --minify
python3 manage.py collectstatic --noinput
echo "Listo: static/css/app.css y staticfiles/ actualizados. Haz commit de ambos."
