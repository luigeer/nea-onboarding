# Credenciales para drive_cliente.py

El cliente necesita autenticarse contra la API de Drive. Hay dos vías; para
empezar basta la primera.

## 1. Uso interactivo (OAuth, cuenta de Luis)

Pasos únicos, en [console.cloud.google.com](https://console.cloud.google.com)
con la cuenta `luis@getnea.com`:

1. Crear un proyecto (por ejemplo `nea-onboarding`)
2. **APIs & Services → Library** → habilitar **Google Drive API**
3. **APIs & Services → OAuth consent screen** → tipo **Internal** (solo cuentas
   del Workspace de Grit), nombre `Nea Onboarding`
4. **APIs & Services → Credentials → Create credentials → OAuth client ID** →
   tipo **Desktop app**
5. Descargar el JSON y guardarlo como `.credenciales/cliente_oauth.json` en la
   raíz del repo

La primera ejecución abre el navegador para autorizar; el token queda cacheado
en `.credenciales/token.json` y se renueva solo. La carpeta `.credenciales/`
está en `.gitignore` — **nunca se versiona**.

Prueba:

```bash
python drive_cliente.py estructura
```

## 2. Tarea programada (cuenta de servicio, después)

La consulta diaria de firmas no puede abrir un navegador. Cuando toque:

1. En el mismo proyecto: **Credentials → Create credentials → Service account**
2. Crear una llave JSON y guardarla fuera del repo
3. Compartir la carpeta `Nea — Expedientes de Clientes` con el correo de la
   cuenta de servicio (o darle acceso a la unidad compartida cuando exista)
4. Apuntar la variable de entorno `NEA_DRIVE_SA` a la ruta del JSON

## Notas

- El identificador de la carpeta raíz está en `drive_cliente.py`
  (`CARPETA_RAIZ`) y se puede sobreescribir con la variable `NEA_DRIVE_RAIZ`.
- Todas las llamadas pasan `supportsAllDrives=True`: cuando los expedientes se
  muevan a la unidad compartida (pendiente, ESPECIFICACION.md §3.1) no hay que
  cambiar nada, porque los identificadores se conservan al mover.
- El scope es `auth/drive` completo porque los documentos que suelta ventas
  son propiedad de otras cuentas y el scope `drive.file` no los vería.
