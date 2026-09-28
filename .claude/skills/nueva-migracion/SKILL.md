---
name: nueva-migracion
description: Agregar o probar una migración de esquema o de datos en TAU (migrations/NNNN-*.sql o .py con fastmigrate). Úsala siempre que cambie una tabla, una columna, un CHECK o haya que mover datos existentes.
---

# Nueva migración

TAU usa SQLite con fastmigrate: al arrancar se aplican las migraciones pendientes, **también en el
servidor de desarrollo del usuario sobre `data/portal.db`** (y en producción). Una migración
aplicada no se edita nunca: los cambios van en una nueva.

## Pasos

1. **Número:** el siguiente a `ls migrations | tail -1`. Nombre descriptivo en español:
   `migrations/0034-algo-claro.sql`. Para cargar datos con lógica, `.py` (ver `0004-msc2020.py`,
   `0028-planes-2017.py`).
2. **Encabezado:** comentario que explique la decisión (qué y por qué, con la sección de PLAN.md).
3. **SQL de SQLite:**
   - `ALTER TABLE … ADD COLUMN` admite `CHECK` y `DEFAULT` constantes; `DROP COLUMN` solo si
     nada la indexa o referencia.
   - Para cambiar un CHECK o una FK hay que recrear la tabla (crear `x_nueva`, copiar, borrar,
     renombrar) con `PRAGMA foreign_keys` en cuenta.
   - Datos existentes: migre lo que había (UPDATE/INSERT … SELECT) y documente qué se pierde.
   - Los valores se buscan por sigla o nombre (`(SELECT id FROM unidad WHERE sigla = 'CMAT')`),
     nunca por id fijo.
4. **Código:** en Python, las fechas y «hoy» usan el dialecto de `app/comun/db.py` (`HOY`,
   `AHORA`, `vigente_hasta()`, `marca_tiempo()`, `transaccion()`); nada propio de SQLite fuera de ahí.
5. **Probar sobre copias, nunca sobre `data/portal.db`:**
   ```bash
   S=<scratchpad>; sqlite3 data/portal.db ".backup '$S/copia.db'"
   uv run python -c "from app.comun.db import init_db; init_db('$S/copia.db')"
   sqlite3 "$S/copia.db" "SELECT …"   # verifique el resultado
   ```
   Pruebe también una base con datos de la versión anterior si la migración mueve datos
   (p. ej., una base sembrada antes del cambio) y una base nueva: `PORTAL_DB=$S/n.db uv run python scripts/seed.py`.
6. **Seed:** si el cambio afecta los datos de ejemplo, actualice `scripts/seed.py` (idempotente:
   solo agrega lo que falta).
7. **Pruebas:** un test que ejecute la migración sobre datos armados a mano cuando mueve datos
   (ejemplo: `tests/test_unidades.py::test_migracion_une_los_periodos`, que corre el SQL con
   `get_db().conn.execute(sql)`).
8. **Documentación:** en `docs/mantenimiento.md`, «hoy la última es la NNNN»; en PLAN.md, la
   migración en la sección de la etapa.
9. Avise al usuario que su servidor de desarrollo la aplicará a `data/portal.db` al recargar, y
   qué datos cambian.
