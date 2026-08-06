# Conectar la base de datos (Supabase)

**Esto es opcional para empezar.** La plataforma funciona sin base: los
expedientes se guardan en la carpeta `expedientes/` de tu computadora. Supabase
sirve para que los datos vivan también fuera de tu laptop y para las consultas
que cruzan expedientes (exposición agregada, vigencias por vencer).

Toma unos cinco minutos.

## 1. Crear el proyecto

1. Entra a [supabase.com](https://supabase.com) y crea una cuenta (el plan
   gratuito basta)
2. **New project**. Ponle `nea-onboarding`
3. En **Region** elige la más cercana a México: `East US (North Virginia)`
4. Guarda la contraseña que te genera en tu gestor de contraseñas — no la vas a
   necesitar para esto, pero sin ella no puedes recuperar el proyecto
5. Espera un par de minutos a que termine de crearse

## 2. Crear las tablas

1. En el menú de la izquierda, **SQL Editor**
2. Abre el archivo `supabase/esquema.sql` de este proyecto, copia **todo** su
   contenido y pégalo ahí
3. Dale **Run**

Debe decir *Success*. Si lo vuelves a correr no pasa nada malo.

## 3. Copiar la dirección y la llave

**La dirección** no está en la pantalla de llaves, sino en **Project Settings →
Data API** (o se lee de la barra del navegador: si dice
`/dashboard/project/abcdefgh/...`, tu dirección es `https://abcdefgh.supabase.co`).
Si la copias de la pantalla viene con `/rest/v1/` al final; da igual, el programa
lo recorta solo.

**La llave** está en **Project Settings → API Keys**, sección **Secret keys**:
la que empieza con `sb_secret_`. Dale al ojito para revelarla y luego al icono de
copiar. *No* sirve la **Publishable** ni la **anon**: esas no pueden escribir.
(En proyectos viejos la equivalente es `service_role`, en la pestaña *Legacy*.)

Con eso, el archivo `.env` en la carpeta del proyecto queda así:

```
SUPABASE_URL=https://abcdefgh.supabase.co
SUPABASE_KEY=sb_secret_...
```

Dos trampas de Windows que cuestan tiempo:

- El Bloc de notas le agrega `.txt` al guardar un archivo nuevo. Lo más fácil es
  copiar `.env.ejemplo`, renombrarlo a `.env` y editarlo.
- Escribir en la ventana no es guardar. Si el título dice `*.env` con asterisco,
  falta **Ctrl+S**.

El archivo `.env` está en `.gitignore`: **nunca** se sube a GitHub. Esa llave da
acceso total a la base, trátala como una contraseña — y si alguna vez queda
expuesta (una captura de pantalla, un correo), genera una nueva con **New secret
key** y revoca la anterior.

## 4. Probar

```bash
python db.py probar
```

Debe decir *Conexión correcta*.

## Cosas que conviene saber

**El plan gratuito pausa el proyecto** si pasa una semana sin usarlo. Cuando eso
pase, la plataforma te lo va a decir con todas sus letras; entras al dashboard
de Supabase, le das **Restore** y en dos minutos vuelve. No se pierde nada.

**La seguridad está en deny-by-default.** El esquema prende *Row Level Security*
sin políticas, o sea que la llave pública no puede leer ni escribir nada. Solo
la llave `service_role` de tu `.env` tiene acceso. Como en esas tablas hay CURP,
RFC y domicilios de personas reales, ese es el default correcto.

**Consultas útiles** una vez que haya expedientes:

```bash
python db.py listar        todos los expedientes y su etapa
python db.py exposicion    cuánto garantiza cada obligado solidario en total
python db.py vigencias     documentos que vencen en los próximos 30 días
```
