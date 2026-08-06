@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   Subir el codigo a GitHub
echo ============================================================
echo.
echo Se van a subir solo los programas. Los expedientes de
echo clientes y el archivo .env se quedan en esta computadora.
echo.
echo La primera vez se va a abrir una ventana del navegador para
echo que autorices con tu cuenta de GitHub. Es normal.
echo.
pause
echo.

git push -u origin main

echo.
if %ERRORLEVEL%==0 (
  echo ============================================================
  echo   LISTO. Tu codigo ya esta respaldado en GitHub.
  echo   https://github.com/luigeer/nea-onboarding
  echo ============================================================
) else (
  echo ============================================================
  echo   ALGO FALLO. Copia el mensaje de arriba y mandaselo a
  echo   Claude para resolverlo.
  echo ============================================================
)
echo.
pause
