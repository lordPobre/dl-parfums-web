@echo off
REM Compila Tailwind a static\css\app.css y actualiza staticfiles\ (Windows, sin PowerShell)
REM Uso:  compilar_css.bat          (una vez)
REM       compilar_css.bat watch    (recompila mientras editas plantillas)
setlocal
set VER=v3.4.17
if not exist tailwindcss.exe (
    echo Descargando Tailwind %VER%...
    curl -sLo tailwindcss.exe https://github.com/tailwindlabs/tailwindcss/releases/download/%VER%/tailwindcss-windows-x64.exe
    if errorlevel 1 ( echo No se pudo descargar Tailwind. & exit /b 1 )
)
if /I "%1"=="watch" (
    tailwindcss.exe -c tailwind.config.js -i static/css/input.css -o static/css/app.css --watch
    exit /b
)
tailwindcss.exe -c tailwind.config.js -i static/css/input.css -o static/css/app.css --minify || exit /b 1
python minificar_js.py
python manage.py collectstatic --noinput || exit /b 1
echo Listo: static\css\app.css y staticfiles\ actualizados. Haz commit de ambos.
