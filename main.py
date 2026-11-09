"""Punto de entrada de TAU, Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática.

Desarrollo:  uv run python main.py      (recarga automática en http://localhost:5001)
"""
import json
import os
import threading
import time
from pathlib import Path

from fasthtml.common import Beforeware, Meta, Response, fast_app, serve
from starlette.middleware.gzip import GZipMiddleware

from app.comun import config

# Zona horaria del instituto para todo el proceso: «hoy» (plazos, vigencias), horas mostradas y
# date('now', 'localtime') en SQLite. Antes de importar el resto de la aplicación.
os.environ.setdefault("TZ", config.ZONA_HORARIA)
time.tzset()
if config.ZONA_HORARIA not in ("UTC", "Etc/UTC") and time.timezone == 0 and not time.daylight:
    print(f"AVISO: no se pudo aplicar la zona horaria {config.ZONA_HORARIA} (¿falta tzdata?); "
          "se usa UTC.", flush=True)

from app.investigacion import institucionales  # noqa: E402
from app.calidad import indicadores as indicadores_calidad  # noqa: E402
from app.calidad import mejora  # noqa: E402
from app.calidad import programados  # noqa: E402
from app.egresados import egresados as seguimiento_egresados  # noqa: E402
from app.comun.auth import beforeware, beforeware_origen, beforeware_solo_lectura
from app.comun.auth import rt as rutas_auth
from app.comun.componentes import avisos_emergentes
from app.comun.componentes.errores import error_interno, no_encontrado, paginas_de_error
from app.comun.cabeceras import CabecerasSeguridad, LimiteCuerpo
from app.comun import correo, registros
from app.comun.registros import RegistroPeticiones
from app.comun.componentes.recursos import encabezados
from app.comun.componentes.recursos import montar as montar_estaticos
from app.comun.db import get_db, init_db
from app.inicio import rt as rutas_inicio
from app.busqueda import rt as rutas_busqueda
from app import navegacion
from app.comun.componentes import layout
from app.servicios import grado as tramites_grado  # noqa: E402
from app.ia import catalogo as _catalogo_ia  # noqa: E402,F401  registra las funciones de IA
from app.academico import rutas as rutas_academico
from app.calidad import rutas as rutas_calidad
from app.comun import rutas as rutas_comun
from app.egresados import rutas as rutas_egresados
from app.estudiantil import rutas as rutas_estudiantil
from app.ia import rutas as rutas_ia
from app.investigacion import rutas as rutas_investigacion
from app.servicios import rutas as rutas_servicios


_candado_mantenimiento = threading.Lock()
_ultimo_mantenimiento = float("-inf")
MANTENIMIENTO_CADA_S = 300  # cada cuánto se mira si toca (cada tarea lleva además su propio plazo horario)


def _correr_mantenimiento():
    try:
        correo.reintentar()  # correos de la cola que fallaron (cada vez: tiene sus propias esperas)
        institucionales.mantenimiento()  # vigencias de proyectos y recordatorios
        programados.mantenimiento()  # informes que se envían solos
        seguimiento_egresados.mantenimiento()  # invitaciones del seguimiento de egresados
        indicadores_calidad.mantenimiento()  # cifras «a hoy» de los indicadores de calidad, una vez al día
        mejora.avisar_vencimientos()  # acciones del plan de mejora por vencer o vencidas (una vez por acción y plazo)
        tramites_grado.recordar()  # informes de tribunales de grado por vencer o vencidos (una vez por ronda y persona)
    except Exception:
        registros.log.exception("Falló el mantenimiento periódico")
    finally:
        _candado_mantenimiento.release()


def _mantenimiento(req):
    """Lanza el mantenimiento periódico en un hilo aparte: no demora la petición que lo dispara y
    el candado impide que dos peticiones simultáneas lo ejecuten a la vez (avisos duplicados)."""
    global _ultimo_mantenimiento
    if config.SOLO_LECTURA or time.monotonic() - _ultimo_mantenimiento < MANTENIMIENTO_CADA_S:
        return
    if not _candado_mantenimiento.acquire(blocking=False):
        return
    _ultimo_mantenimiento = time.monotonic()
    threading.Thread(target=_correr_mantenimiento, name="mantenimiento", daemon=True).start()


def create_app(db_path=config.DB_PATH):
    init_db(db_path)
    # Menú de navegación: lo arma app/navegacion.py (sabe qué ve cada rol en todos los paquetes).
    layout.MENU, layout.MENU_MOVIL = navegacion.menu, navegacion.movil
    if not config.SOLO_LECTURA:
        institucionales.mantenimiento(forzar=True)
    app, _ = fast_app(
        pico=False,
        # Encabezados propios (sin CDN): ver app/comun/componentes/recursos.py.
        default_hdrs=False,
        hdrs=(*encabezados(),
              # Sin herencia de atributos hx-*: cada elemento declara su propio destino y swap.
              # Evita que, p. ej., un botón dentro de un contenedor con hx-swap="outerHTML"
              # herede ese swap sin querer (es además el comportamiento por defecto en htmx 4).
              # allowEval: no evaluar código (hx-on, filtros de eventos): la CSP no admite 'unsafe-eval'.
              Meta(name="htmx-config", content=json.dumps({"disableInheritance": True, "allowEval": False}))),
        exception_handlers={404: no_encontrado, 500: error_interno},
        before=[beforeware_origen, beforeware_solo_lectura, beforeware, Beforeware(_mantenimiento)],
        secret_key=config.SECRET_KEY,
        # Sin PORTAL_SECRET_KEY, la clave se crea junto a la base: en el contenedor es el volumen (sobrevive a los
        # despliegues) y el código queda de solo lectura para el usuario sin privilegios que lo ejecuta.
        key_fname=str(Path(db_path).parent / ".sesskey"),
        session_cookie="portal_sesion",
        max_age=config.SESION_MAX_AGE,
        sess_https_only=config.HTTPS_ONLY,
        static_path=str(config.RAIZ / "static"),
        htmlkw={"lang": "es"},
        title=config.NOMBRE_SISTEMA,
    )
    avisos_emergentes.montar(app)
    app.after.append(paginas_de_error)
    montar_estaticos(app)
    app.add_middleware(CabecerasSeguridad)
    # Compresión (PLAN §62, etapa 6): HTML, CSS y JS viajan comprimidos (la hoja de Tailwind pasa de 49 KB a 9 KB).
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(LimiteCuerpo, maximo=config.MAX_CUERPO)  # 413 antes de leer un envío desmedido
    app.add_middleware(RegistroPeticiones)  # el último agregado es el más externo: registra todo lo demás
    registros.configurar()

    @app.get("/salud")
    def salud():
        """Para el chequeo del hosting: responde si la base contesta (sin sesión ni registro)."""
        try:
            get_db().q("SELECT 1")
        except Exception:
            registros.log.exception("Chequeo de salud: la base no responde")
            return Response("La base de datos no responde", status_code=503)
        return Response("ok", media_type="text/plain")
    # Cada paquete da sus routers en orden (app/<paquete>/rutas/__init__.py, PLAN §62 ARQ-01).
    for router in (rutas_auth, rutas_inicio, rutas_busqueda, *rutas_comun.routers(), *rutas_investigacion.routers(),
                   *rutas_calidad.routers(), *rutas_egresados.routers(), *rutas_academico.routers(),
                   *rutas_estudiantil.routers(), *rutas_servicios.routers(), *rutas_ia.routers()):
        router.to_app(app)
    return app


app = create_app()

if __name__ == "__main__":
    # Solo en este equipo: los navegadores bloquean enlaces a 0.0.0.0.
    serve(host="127.0.0.1")
