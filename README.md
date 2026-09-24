# Portal de Investigación

Portal del instituto para que los investigadores gestionen su actividad científica.
Está hecho con FastHTML, HTMX, MonsterUI y SQLite. El diseño completo está en [PLAN.md](PLAN.md).

## Puesta en marcha

```bash
uv sync                                  # instala dependencias
uv run python scripts/seed.py --reset    # crea la BD con cuentas de demostración
uv run python main.py                    # http://localhost:5001 (recarga automática)
uv run pytest                            # tests
```

### Cuentas de demostración

| Correo | Contraseña | Perfil |
|---|---|---|
| admin@instituto.test | `Admin-portal-2026` | Administradora |
| sofia.kovalevskaya@instituto.test | `Temporal-2026` (temporal) | Investigadora y administradora |
| emmy.noether@instituto.test, alan.turing@…, srinivasa.ramanujan@… | `Temporal-2026` (temporal) | Investigador |

Las cuentas con contraseña temporal deben cambiarla en su primer ingreso.

## Estructura

```
main.py                     create_app(): fast_app + MonsterUI + Beforeware + routers
app/config.py               configuración (variables de entorno PORTAL_*)
app/db.py                   fastlite + fastmigrate (init_db, auditar)
app/seguridad.py            Argon2, contraseñas temporales, política de contraseñas
app/usuarios.py             acceso a datos de cuentas y límite de intentos de login
app/auth.py                 Beforeware, login/logout, cambio de contraseña
app/components/layout.py    página, navegación, modal HTMX
app/routes/inicio.py        tablero
app/routes/admin_usuarios.py  administración de cuentas
migrations/NNNN-*.sql       migraciones versionadas (se aplican al arrancar)
scripts/seed.py             datos de demostración
tests/                      pytest con el TestClient de Starlette
```

## Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `PORTAL_DB` | `data/portal.db` | Ruta de la base SQLite |
| `PORTAL_SECRET_KEY` | archivo `.sesskey` | Clave de firma de la cookie de sesión |
| `PORTAL_HTTPS_ONLY` | `0` | `1` en producción para usar cookies solo por HTTPS |
| `PORTAL_INSTITUTO` | Instituto de Investigación Matemática | Nombre que se muestra en la interfaz |

## Migraciones

Para cambiar el esquema, agregue un archivo `migrations/000N-descripcion.sql`. Nunca edite una
migración ya aplicada. `init_db()` aplica las migraciones pendientes al arrancar la app, y
fastmigrate registra en la base la versión aplicada.
