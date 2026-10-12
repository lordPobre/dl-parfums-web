# Compila Tailwind a static/css/app.css y actualiza staticfiles/ (Windows / PowerShell)
# Uso:  .\compilar_css.ps1          (una vez)
#       .\compilar_css.ps1 -watch   (recompila mientras editas plantillas)
param([switch]$watch)
$ErrorActionPreference = "Stop"
$ver = "v3.4.17"
if (-not (Test-Path ".\tailwindcss.exe")) {
    Write-Host "Descargando Tailwind $ver..."
    Invoke-WebRequest "https://github.com/tailwindlabs/tailwindcss/releases/download/$ver/tailwindcss-windows-x64.exe" -OutFile "tailwindcss.exe"
}
if ($watch) {
    .\tailwindcss.exe -c tailwind.config.js -i static/css/input.css -o static/css/app.css --watch
} else {
    .\tailwindcss.exe -c tailwind.config.js -i static/css/input.css -o static/css/app.css --minify
    python manage.py collectstatic --noinput
    Write-Host "Listo: static/css/app.css y staticfiles/ actualizados. Haz commit de ambos."
}
