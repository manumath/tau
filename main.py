"""Punto de entrada del Portal de Investigación.

Desarrollo:  uv run python main.py      (recarga automática en http://localhost:5001)
"""
import json
import os
import time

from fasthtml.common import Beforeware, Meta, fast_app, serve
from fasthtml.toaster import setup_toasts

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
from app.comun.componentes.errores import JS_AVISOS, no_encontrado, paginas_de_error
from app.comun.cabeceras import CabecerasSeguridad
from app.comun.componentes.recursos import encabezados
from app.comun.componentes.recursos import montar as montar_estaticos
from app.comun.db import init_db
from app.investigacion.rutas.actividades import rt as rutas_actividades
from app.investigacion.rutas.adjuntos import rt as rutas_adjuntos
from app.investigacion.rutas.bibtex import rt as rutas_bibtex
from app.comun.rutas.admin_auditoria import rt as rutas_admin_auditoria
from app.investigacion.rutas.admin_revistas import rt as rutas_admin_revistas
from app.investigacion.rutas.admin_lineas import rt as rutas_admin_lineas
from app.acreditacion.rutas.anexo import rt as rutas_acreditacion
from app.comun.rutas.estudiantes import rt as rutas_estudiantes
from app.comun.rutas.admin_usuarios import rt as rutas_admin_usuarios
from app.acreditacion.rutas.informes import rt as rutas_informes
from app.comun.rutas.inicio import rt as rutas_inicio
from app.investigacion.rutas.investigadores import rt as rutas_investigadores
from app.investigacion.rutas.perfil import rt as rutas_perfil
from app.comun.rutas.personas import rt as rutas_personas
from app.investigacion.rutas.productos import rt as rutas_productos
from app.investigacion.rutas.propuestas import rt as rutas_propuestas
from app.investigacion.rutas.proyectos import rt as rutas_proyectos
from app.investigacion.rutas.publico import rt as rutas_publico


def _mantenimiento(req):
    """Vigencia de proyectos institucionales y recordatorios (a lo más una vez por hora)."""
    if not config.SOLO_LECTURA:
        institucionales.mantenimiento()


def create_app(db_path=config.DB_PATH):
    init_db(db_path)
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
              Meta(name="htmx-config", content=json.dumps({"disableInheritance": True})),
              JS_AVISOS),
        exception_handlers={404: no_encontrado},
        before=[beforeware_origen, beforeware_solo_lectura, beforeware, Beforeware(_mantenimiento)],
        secret_key=config.SECRET_KEY,
        key_fname=str(config.RAIZ / ".sesskey"),
        session_cookie="portal_sesion",
        max_age=config.SESION_MAX_AGE,
        sess_https_only=config.HTTPS_ONLY,
        static_path=str(config.RAIZ / "static"),
        htmlkw={"lang": "es"},
        title="Portal de Investigación",
    )
    setup_toasts(app)
    app.after.append(paginas_de_error)
    montar_estaticos(app)
    app.add_middleware(CabecerasSeguridad)
    # rutas_bibtex va antes que rutas_productos: /productos/bibtex coincidiría con /productos/{pid}.
    for router in (rutas_auth, rutas_inicio, rutas_admin_usuarios, rutas_perfil, rutas_bibtex,
                   rutas_investigadores, rutas_actividades, rutas_productos, rutas_personas,
                   rutas_adjuntos, rutas_estudiantes, rutas_propuestas, rutas_proyectos, rutas_acreditacion, rutas_informes, rutas_publico,
                   rutas_admin_auditoria, rutas_admin_revistas, rutas_admin_lineas):
        router.to_app(app)
    return app


app = create_app()

if __name__ == "__main__":
    # Solo en este equipo: los navegadores bloquean enlaces a 0.0.0.0.
    serve(host="127.0.0.1")
