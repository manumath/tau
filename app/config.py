"""Configuración leída del entorno, con valores por defecto aptos para desarrollo."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MIGRACIONES = RAIZ / "migrations"

DB_PATH = Path(os.environ.get("PORTAL_DB", RAIZ / "data" / "portal.db"))
SECRET_KEY = os.environ.get("PORTAL_SECRET_KEY")  # None → FastHTML usa/crea .sesskey
HTTPS_ONLY = os.environ.get("PORTAL_HTTPS_ONLY", "0") == "1"
NOMBRE_INSTITUTO = os.environ.get("PORTAL_INSTITUTO", "Instituto de Investigación Matemática")
# Correo de contacto que se envía a Crossref (su «polite pool» responde mejor si se identifica).
CONTACTO = os.environ.get("PORTAL_CONTACTO")

# Bloqueo de login: N intentos fallidos por email dentro de la ventana.
LOGIN_MAX_FALLOS = 5
LOGIN_VENTANA_MIN = 15
PASS_MIN_LARGO = 10
SESION_MAX_AGE = 8 * 3600
