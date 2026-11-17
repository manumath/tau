"""Punto de entrada de TAU, Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática.

Desarrollo:  uv run python main.py      (recarga automática en http://localhost:5001)
"""
import json
import os
import threading
import time
from pathlib import Path

from fasthtml.common import Meta, Response, fast_app, serve
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
from app.comun.auth import beforeware, beforeware_origen, beforeware_solo_lectura
from app.comun.auth import rt as rutas_auth
from app.comun.componentes import avisos_emergentes
from app.comun.componentes.errores import error_interno, no_encontrado, paginas_de_error
from app.comun.cabeceras import CabecerasSeguridad, LimiteCuerpo
from app.comun import correo, modulos, registros
from app.comun.registros import RegistroPeticiones
from app.comun.componentes.recursos import encabezados
from app.comun.componentes.recursos import montar as montar_estaticos
from app.comun.db import get_db, init_db
from app.inicio import rt as rutas_inicio
from app.busqueda import rt as rutas_busqueda
from app import manifiestos, navegacion
from app.comun.componentes import layout
from app.ia import catalogo as _catalogo_ia  # noqa: E402,F401  registra las funciones de IA
from app.academico import rutas as rutas_academico
from app.calidad import rutas as rutas_calidad
from app.comun import rutas as rutas_comun
from app.egresados import rutas as rutas_egresados
from app.estudiantil import rutas as rutas_estudiantil
from app.ia import rutas as rutas_ia
from app.informes import rutas as rutas_informes
from app.investigacion import rutas as rutas_investigacion
from app.servicios import rutas as rutas_servicios


_candado_mantenimiento = threading.Lock()
_ultimo_mantenimiento = float("-inf")
MANTENIMIENTO_CADA_S = 300  # cada cuánto se mira si toca (cada tarea lleva además su propio plazo horario)


def _correr_mantenimiento():
    try:
        correo.reintentar()  # correos de la cola que fallaron (cada vez: tiene sus propias esperas)
        # Las tareas periódicas las aporta cada módulo (`mantenimiento` en su aportes.py): uno apagado no avisa ni
        # envía nada (PLAN §73).
        for tareas in modulos.aportes("mantenimiento"):
            for tarea in tareas:
                tarea()
    except Exception:
        registros.log.exception("Falló el mantenimiento periódico")
    finally:
        _candado_mantenimiento.release()


def _mantenimiento(req=None):
    """Lanza el mantenimiento periódico en un hilo aparte, si ya toca: el candado impide que dos lo ejecuten a la vez
    (avisos duplicados)."""
    global _ultimo_mantenimiento
    if config.SOLO_LECTURA or time.monotonic() - _ultimo_mantenimiento < MANTENIMIENTO_CADA_S:
        return
    if not _candado_mantenimiento.acquire(blocking=False):
        return
    _ultimo_mantenimiento = time.monotonic()
    threading.Thread(target=_correr_mantenimiento, name="mantenimiento", daemon=True).start()


# El reloj de las tareas periódicas (PLAN §73, mejora 6): un hilo propio que arranca con el servidor y mira cada
# MANTENIMIENTO_CADA_S si toca. Antes las disparaba una petición web: sin visitas (un fin de semana, de noche) no salían
# los recordatorios ni se reintentaban los correos. Las pruebas crean la aplicación sin arrancar el servidor: no hay reloj.
PRIMERA_ESPERA_S = 20          # deja que el servidor termine de arrancar
_parar_reloj = threading.Event()


def _reloj(primera: float = PRIMERA_ESPERA_S, cada: float = MANTENIMIENTO_CADA_S):
    espera = primera
    while not _parar_reloj.wait(espera):
        _mantenimiento()
        espera = cada


def _arrancar_reloj():
    _parar_reloj.clear()
    threading.Thread(target=_reloj, name="reloj-mantenimiento", daemon=True).start()


def _detener_reloj():
    _parar_reloj.set()


def create_app(db_path=config.DB_PATH):
    init_db(db_path)
    manifiestos.registrar()   # catálogo de módulos (PLAN §73): lo que cada paquete declara en su modulo.py
    modulos.sembrar(config.PERFIL)   # solo escribe en una base nueva o si hay un módulo nuevo
    # Menú de navegación: lo arma app/navegacion.py (sabe qué ve cada rol en todos los paquetes).
    layout.MENU, layout.MENU_MOVIL = navegacion.menu, navegacion.movil
    if not config.SOLO_LECTURA and modulos.activo("investigacion"):
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
        # La compuerta de módulos va primera: una ruta de un módulo apagado no existe para nadie (PLAN §73).
        before=[modulos.compuerta, beforeware_origen, beforeware_solo_lectura, beforeware],
        on_startup=[_arrancar_reloj], on_shutdown=[_detener_reloj],   # las tareas periódicas tienen su propio reloj
        secret_key=config.SECRET_KEY,
        # Sin TAU_SECRET_KEY, la clave se crea junto a la base: en el contenedor es el volumen (sobrevive a los
        # despliegues) y el código queda de solo lectura para el usuario sin privilegios que lo ejecuta.
        key_fname=str(Path(db_path).parent / ".sesskey"),
        session_cookie="tau_sesion",
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
                   *rutas_informes.routers(), *rutas_calidad.routers(), *rutas_egresados.routers(), *rutas_academico.routers(),
                   *rutas_estudiantil.routers(), *rutas_servicios.routers(), *rutas_ia.routers()):
        router.to_app(app)
    modulos.marcar_rutas(app)   # cada ruta queda con su módulo; una sin dueño impide arrancar
    return app


app = create_app()

if __name__ == "__main__":
    # Solo en este equipo: los navegadores bloquean enlaces a 0.0.0.0.
    serve(host="127.0.0.1")
