"""Punto de entrada del Portal de Investigación.

Desarrollo:  uv run python main.py      (recarga automática en http://localhost:5001)
"""
import json
import os
import time

from fasthtml.common import Beforeware, Meta, fast_app, serve
from fasthtml.toaster import setup_toasts
from monsterui.all import Theme

from app import config

# Zona horaria del instituto para todo el proceso: «hoy» (plazos, vigencias), horas mostradas y
# date('now', 'localtime') en SQLite. Antes de importar el resto de la aplicación.
os.environ.setdefault("TZ", config.ZONA_HORARIA)
time.tzset()
if config.ZONA_HORARIA not in ("UTC", "Etc/UTC") and time.timezone == 0 and not time.daylight:
    print(f"AVISO: no se pudo aplicar la zona horaria {config.ZONA_HORARIA} (¿falta tzdata?); "
          "se usa UTC.", flush=True)

from app import institucionales  # noqa: E402
from app.auth import beforeware, beforeware_solo_lectura
from app.auth import rt as rutas_auth
from app.components.errores import JS_AVISOS, no_encontrado, paginas_de_error
from app.components.perfil import katex_headers
from app.db import init_db
from app.routes.actividades import rt as rutas_actividades
from app.routes.adjuntos import rt as rutas_adjuntos
from app.routes.bibtex import rt as rutas_bibtex
from app.routes.admin_auditoria import rt as rutas_admin_auditoria
from app.routes.admin_revistas import rt as rutas_admin_revistas
from app.routes.acreditacion import rt as rutas_acreditacion
from app.routes.admin_usuarios import rt as rutas_admin_usuarios
from app.routes.informes import rt as rutas_informes
from app.routes.inicio import rt as rutas_inicio
from app.routes.investigadores import rt as rutas_investigadores
from app.routes.perfil import rt as rutas_perfil
from app.routes.personas import rt as rutas_personas
from app.routes.productos import rt as rutas_productos
from app.routes.propuestas import rt as rutas_propuestas
from app.routes.proyectos import rt as rutas_proyectos
from app.routes.publico import rt as rutas_publico


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
        hdrs=(*Theme.blue.headers(), *katex_headers(),
              # Sin herencia de atributos hx-*: cada elemento declara su propio destino y swap.
              # Evita que, p. ej., un botón dentro de un contenedor con hx-swap="outerHTML"
              # herede ese swap sin querer (es además el comportamiento por defecto en htmx 4).
              Meta(name="htmx-config", content=json.dumps({"disableInheritance": True})),
              JS_AVISOS),
        exception_handlers={404: no_encontrado},
        before=[beforeware_solo_lectura, beforeware, Beforeware(_mantenimiento)],
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
    # rutas_bibtex va antes que rutas_productos: /productos/bibtex coincidiría con /productos/{pid}.
    for router in (rutas_auth, rutas_inicio, rutas_admin_usuarios, rutas_perfil, rutas_bibtex,
                   rutas_investigadores, rutas_actividades, rutas_productos, rutas_personas,
                   rutas_adjuntos, rutas_propuestas, rutas_proyectos, rutas_acreditacion, rutas_informes, rutas_publico,
                   rutas_admin_auditoria, rutas_admin_revistas):
        router.to_app(app)
    return app


app = create_app()

if __name__ == "__main__":
    # Solo en este equipo: los navegadores bloquean enlaces a 0.0.0.0.
    serve(host="127.0.0.1")
