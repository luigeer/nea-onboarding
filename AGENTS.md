# AGENTS.md

## Skills de superpowers en este repo

El plugin `superpowers` inyecta al inicio de cada sesión una instrucción que exige
invocar un skill antes de responder cualquier cosa, incluso una pregunta simple.
Esta sección acota esa regla a propósito: aquí se decide qué es obligatorio, qué
se usa cuando aplica y qué no aplica.

### Obligatorio, sin excepciones

- **`superpowers:verification-before-completion`** — antes de afirmar que algo
  funciona, está listo, quedó arreglado o que las pruebas pasan, y antes de
  cualquier commit. Nunca se afirma sin haber corrido el comando y mostrado su
  salida.
- **`superpowers:test-driven-development`** — todo cambio de comportamiento
  empieza por la prueba que lo describe, no por el código.

La compuerta del proyecto es:

```
python tests/todas.py
```

El veredicto es **el código de salida**, nunca el texto de la salida. `tests/todas.py`
existe justamente por ese error: dos archivos imprimían éxito a media página y
salían con código 0 aunque lo que venía después estuviera rojo.

Quien opera este repo no lee código. Por eso "ya quedó" no es una conclusión que
se pueda ofrecer: se muestra la salida del comando y se deja que hable ella.

### Cuando aplique

- **`superpowers:brainstorming`** — antes de construir algo nuevo o cambiar
  comportamiento existente. Primero se aclara el requisito de negocio, después se
  toca el código.
- **`superpowers:systematic-debugging`** — cuando algo falla. Se busca la causa
  antes de proponer un parche; adivinar sobre un expediente real es lo peor que
  se puede hacer.
- **`superpowers:writing-plans`** y **`superpowers:executing-plans`** — trabajo de
  varios pasos que no cabe en una sesión.
- **`superpowers:writing-skills`** — al crear o editar los skills del negocio.

### No aplican aquí

Este repo se trabaja de forma individual, con commits directos a `main`, sin pull
requests ni ramas de feature. Estos skills asumen un equipo y sobran:

`requesting-code-review`, `receiving-code-review`, `using-git-worktrees`,
`finishing-a-development-branch`, `dispatching-parallel-agents`,
`subagent-driven-development`.

### Preguntas rápidas

Explicar cómo funciona algo, leer un archivo, revisar el estado del repo o
responder una duda **no** dispara proceso formal: se responde directo. Escribir o
modificar código sí cuenta como tarea, y ahí los dos obligatorios de arriba no se
negocian.
