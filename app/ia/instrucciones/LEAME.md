# Instrucciones de las funciones de IA

Una carpeta por función (su `clave`), con un archivo por versión: `v1.md`, `v2.md`… El servicio usa la versión más
alta y la guarda en cada uso (`ia_uso.version_prompt`), para que la medición del piloto compare versiones.

- No edite una versión ya usada: cree la siguiente.
- El texto es el mensaje de sistema. Los datos llegan aparte, cada uno con su origen (`[producto.titulo]`).
- Pida que el modelo no invente cifras ni nombres y que escriba en español.
