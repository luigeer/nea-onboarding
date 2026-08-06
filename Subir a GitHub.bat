@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem El entorno desde el que se genero este archivo tenia desactivadas las
rem preguntas interactivas de git, y eso se hereda. Aqui se restablecen para
rem que el dialogo de autorizacion de GitHub pueda aparecer.
set "GCM_INTERACTIVE="
set "GIT_ASKPASS="
set "GIT_TERMINAL_PROMPT=1"
set "GIT_EDITOR="

echo ============================================================
echo   Subir el codigo a GitHub
echo ============================================================
echo.
echo Se van a subir solo los programas. Los expedientes de
echo clientes y el archivo .env se quedan en esta computadora.
echo.
echo La primera vez se abre una ventana para que autorices con tu
echo cuenta de GitHub. Es normal. Si no la ves, revisa la barra de
echo tareas o presiona Alt+Tab.
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
