"""Punto de entrada del Portal de Investigación.

Desarrollo:  uv run python main.py      (recarga automática en http://localhost:5001)
"""
from fasthtml.common import fast_app, serve
from fasthtml.toaster import setup_toasts
from monsterui.all import Theme

from app import config
from app.auth import beforeware
from app.auth import rt as rutas_auth
from app.db import init_db
from app.routes.admin_usuarios import rt as rutas_admin_usuarios
from app.routes.inicio import rt as rutas_inicio


def create_app(db_path=config.DB_PATH):
    init_db(db_path)
    app, _ = fast_app(
        pico=False,
        hdrs=Theme.blue.headers(),
        before=beforeware,
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
    for router in (rutas_auth, rutas_inicio, rutas_admin_usuarios):
        router.to_app(app)
    return app


app = create_app()

if __name__ == "__main__":
    serve()
