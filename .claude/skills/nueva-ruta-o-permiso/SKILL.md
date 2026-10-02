---
name: nueva-ruta-o-permiso
description: Agregar una pantalla, ruta HTMX o acción con permisos en TAU (FastHTML + HTMX + MonsterUI), o cambiar quién puede hacer algo. Úsala al crear rutas, formularios, modales, acciones de roles o reglas /admin.
---

# Nueva ruta, pantalla o permiso

## Dónde va

- Paquetes: `app/comun` (personas, cuentas, vínculos, roles; **no importa de los demás**),
  `app/investigacion`, `app/academico`, `app/acreditacion`. Lógica en el módulo
  (`app/<paquete>/<tema>.py`), pantallas en `app/<paquete>/rutas/<tema>.py` con `rt = APIRouter()`.
- Registre el router en `main.py`. Las rutas con segmento literal que choca con `{id}`
  (`/productos/bibtex` frente a `/productos/{pid}`) van **antes**.

## Permisos (servidor, siempre)

1. Acción nueva en `ACCIONES` de `app/comun/permisos.py` → conjunto de roles. Se consulta con
   `permisos.puede(auth, "accion", unidad)`; los roles valen en su unidad (los de UMSA, en todas).
2. Quién decide qué (decisiones del instituto, PLAN.md §23–25):
   - **Administración del sistema:** cuentas, roles (a pedido de las direcciones), auditoría.
   - **Dirección de Carrera:** categoría y vínculo de cada persona (cambios, término, carga
     horaria contratada) — única dependencia; planes, oferta, docencia.
   - **Dirección del Instituto:** ciclo de vida de los proyectos institucionales (convocatoria,
     propuestas, responsables), catálogos, memoria y anexo. No define vínculos.
   - **Comité de acreditación:** ve todo, no modifica.
3. Rutas `/admin/...`: agregue su patrón a `REGLAS_ADMIN` en `app/comun/auth.py` (lo que no está se
   deniega; `tests/test_permisos_rutas.py::test_toda_ruta_admin_tiene_regla` lo exige) **y** vuelva
   a verificar dentro de la ruta con `puede(…)`. Ocultar un botón no basta.
4. Pruebe cada rol: matriz `RUTAS` en `tests/test_permisos_rutas.py` y un test del 403. Para la
   Dirección de Carrera en tests, la fixture `carrera` (cuenta admin + ese rol).

## HTMX y componentes

- Sin herencia de atributos: cada elemento declara `hx_target` y `hx_swap`.
- Modales: `modal(...)` de `app/comun/componentes/layout.py` con `hx_target=f"#{ID_MODAL}"`;
  cerrar con `JS_CERRAR`. Filas o fragmentos fuera de banda: `Template(x(hx_swap_oob="true"))`.
- Tras crear algo con página propia: `return Redirect(url)` (HTMX recibe `HX-Redirect`).
  Avisos: `add_toast(sess, "…", "success")`.
- Campos dinámicos del formulario (p. ej. varias actividades): `async def post(auth, req, …)` y
  `await req.form()`.
- Errores de validación: vuelva a mostrar el formulario con `mensaje_error(*errores)` y lo escrito.
- Operaciones que tardan (consultas a OpenAlex o Crossref, envíos con correo): `boton_espera` de
  `layout.py` (se deshabilita y muestra que trabaja). No use `LoaderButton` de MonsterUI: rompe las
  clases en tupla. Si la petición la hace el formulario, póngale
  `hx_disabled_elt="find button[type='submit']"`.
- Trámites con etapas: `etapas(pasos)` de `app/comun/componentes/etapas.py` (los pasos los calcula
  la lógica del módulo, como `institucionales.pasos`). Avances (x de n): `Progress` de MonsterUI.
- Componentes de MonsterUI basados en daisyUI (`Steps`, `Alert`, `Loading`, `Toast`) no tienen
  estilos en TAU (daisyUI no se carga): no los use.
- Toda modificación se audita: `auditar(auth["id"], "accion", "entidad", id, "detalle legible")`.

## Textos

- Interfaz en español, trato de **usted**, sin jerga técnica; el nombre del sistema viene de
  `config.NOMBRE_SISTEMA` (TAU), nunca escrito a mano; «el sistema», no «el portal».
- Clases de Tailwind nuevas → `scripts/estilos.sh` (skill `cerrar-etapa`).

## Pruebas

Test de la lógica (módulo) y de la pantalla con `client` (`tests/conftest.py`: `login`, `HX`,
`admin`, `carrera`). Luego revise la pantalla con la skill `captura-visual`.
