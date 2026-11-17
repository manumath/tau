---
name: nueva-ruta-o-permiso
description: Agregar una pantalla, ruta HTMX o acción con permisos en TAU (FastHTML + HTMX + MonsterUI), o cambiar quién puede hacer algo. Úsala al crear rutas, formularios, modales, acciones de roles o reglas /admin.
---

# Nueva ruta, pantalla o permiso

## Dónde va

- Paquetes: `app/comun` (personas, cuentas, vínculos, roles; **no importa de los demás**),
  `app/investigacion`, `app/academico`, `app/calidad`, `app/estudiantil`, `app/egresados`, `app/servicios` y `app/ia`. Lógica en el módulo
  (`app/<paquete>/<tema>.py`), pantallas en `app/<paquete>/rutas/<tema>.py` con `rt = APIRouter()`.
- **Módulo (PLAN §73):** un archivo de rutas nuevo se agrega a `rutas=` del módulo que corresponde en
  `app/<paquete>/modulo.py`; sin eso la aplicación no arranca («Rutas que ningún módulo declara»). Una acción nueva
  de `ACCIONES` va en `acciones=` de ese mismo módulo (o de la plataforma, en `app/comun/modulo.py`).
- Registre el router en `main.py`. Las rutas con segmento literal que choca con `{id}`
  (`/productos/bibtex` frente a `/productos/{pid}`) van **antes**.

## Permisos (servidor, siempre)

1. Acción nueva en `ACCIONES` de `app/comun/permisos.py` → conjunto de roles. Se consulta con
   `permisos.puede(auth, "accion", unidad)`; los roles valen en su unidad (los de la universidad, en todas). La unidad se pide por su tipo
   (`unidades.carrera()`, `unidades.instituto()`), nunca por una sigla: otra carrera tiene las suyas (PLAN §73).
2. Quién decide qué (decisiones del instituto, PLAN.md §23–25):
   - **Administración del sistema:** cuentas, roles (a pedido de las direcciones), auditoría.
   - **Dirección de Carrera:** categoría y vínculo de cada persona (cambios, término, carga
     horaria contratada) — única dependencia; planes, oferta, docencia.
   - **Dirección del Instituto:** ciclo de vida de los proyectos institucionales (convocatoria,
     propuestas, responsables), catálogos, memoria y anexo. No define vínculos.
   - **Comisión de calidad:** ve todo, no modifica.
3. Rutas `/admin/...`: agregue su patrón a `REGLAS_ADMIN` en `app/comun/auth.py` (lo que no está se
   deniega; `tests/test_permisos_rutas.py::test_toda_ruta_admin_tiene_regla` lo exige) **y** vuelva
   a verificar dentro de la ruta con `puede(…)`. Ocultar un botón no basta.
4. Pruebe cada rol: matriz `RUTAS` en `tests/test_permisos_rutas.py` y un test del 403. Para la
   Dirección de Carrera en tests, la fixture `carrera` (cuenta admin + ese rol).
5. Toda ruta fuera de `/admin` y de las públicas debe comprobar algo (`puede`, `auth["id"]`, la ficha del estudiante,
   403/404): `tests/test_rutas_declaradas.py` lo revisa en la ruta y en las funciones que llama. Si es de verdad para todo
   el personal (sugerencias, formularios vacíos), agréguela a `TODO_EL_PERSONAL` con su motivo.

## HTMX y componentes

- **Nada de JavaScript en el HTML** (la CSP es `script-src 'self'`): ni `onclick=`, `onchange=`,
  `hx_on…` ni `Script("…")` en línea; el navegador los bloquearía sin aviso visible. Use los
  atributos que atiende `static/js/acciones.js` (`data_accion="cerrar-modal"`, `"vaciar"`,
  `"copiar"`, `"imprimir"`…, `data_navegar`, `data_enter`, `data_sin_envio`,
  `data_tras_pedido_limpiar`); si falta un comportamiento, agréguelo ahí. Botón que cierra el
  modal: `**CERRAR` de `layout.py`. `tests/test_csp.py` lo vigila.
- Sin herencia de atributos: cada elemento declara `hx_target` y `hx_swap`.
- Modales: `modal(...)` de `app/comun/componentes/layout.py` con `hx_target=f"#{ID_MODAL}"`;
  cerrar con `**CERRAR`. Filas o fragmentos fuera de banda: `Template(x(hx_swap_oob="true"))`.
- **Menú:** una pantalla que deba aparecer en el menú lateral se agrega en el `aportes.py` de su paquete, en la función
  `menu` de su módulo (PLAN §73): devuelve `(grupo, orden, item(...))`, con el grupo (Investigación, Docencia,
  Estudiantes, Servicios, Calidad o Administración) y un orden entre sus vecinos. Las del estudiante, en `menu_estudiante`
  (grupos «Mi carrera» o «Servicios»; en el teléfono según `navegacion.PRIORIDAD_MOVIL_ESTUDIANTE`). Siempre con **la
  misma condición de permiso** que su ruta. Las de Docencia van en `PESTANAS` de `app/academico/componentes.py`. No
  toque `app/navegacion.py`, `app/busqueda.py` ni `app/inicio.py`: solo juntan aportes y no importan de ningún paquete. Una pantalla
  nueva va también en `tests/navegador/test_accesibilidad_pantallas.py`; si pide datos personales, lleva
  `layout.aviso_privacidad(clave)` y su módulo va en `privacidad.FORMULARIOS`. El enlace activo lo
  marca `acciones.js` por la dirección: no hace falta `seccion=`. Un **grupo nuevo** necesita además su regla de plegado en
  `estilos/entrada.css` (`html[data-grupos~=clave]`, la clave es el título sin tildes, en minúsculas y con guiones en vez de espacios).
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
