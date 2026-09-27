"""Configuración leída del entorno, con valores por defecto aptos para desarrollo."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MIGRACIONES = RAIZ / "migrations"

DB_PATH = Path(os.environ.get("PORTAL_DB", RAIZ / "data" / "portal.db"))
SECRET_KEY = os.environ.get("PORTAL_SECRET_KEY")  # None → FastHTML usa/crea .sesskey
HTTPS_ONLY = os.environ.get("PORTAL_HTTPS_ONLY", "0") == "1"
NOMBRE_INSTITUTO = os.environ.get("PORTAL_INSTITUTO", "Instituto de Investigación Matemática")
UNIVERSIDAD = os.environ.get("PORTAL_UNIVERSIDAD", "Universidad Mayor de San Andrés")

# Contexto local: zona horaria de las fechas (plazos, «hoy», horas mostradas) y moneda de los montos.
ZONA_HORARIA = os.environ.get("PORTAL_ZONA_HORARIA", "America/La_Paz")
MONEDA = os.environ.get("PORTAL_MONEDA", "BOB")
# País del instituto: una revista de este país es «nacional» en los informes.
PAIS = os.environ.get("PORTAL_PAIS", "Bolivia")
# Durante el piloto, los artículos en revistas aún no verificadas cuentan con lo declarado. Para la
# acreditación, con «1» solo cuentan los de revistas verificadas (los demás quedan «por confirmar»).
EXIGIR_REVISTA_VERIFICADA = os.environ.get("PORTAL_EXIGIR_REVISTA_VERIFICADA", "0") == "1"
SIMBOLOS_MONEDA = {"BOB": "Bs", "USD": "US$", "EUR": "€"}

# Nombres que cuentan como filiación del instituto en una publicación (se comparan sin tildes ni
# mayúsculas; las siglas, como palabra completa). Vale cualquier instancia que contiene al
# instituto y la doble filiación. Separados por «;» en PORTAL_FILIACIONES.
FILIACIONES = [f.strip() for f in os.environ.get(
    "PORTAL_FILIACIONES",
    "IIMAT; Instituto de Investigación Matemática; CMAT; Carrera de Matemática; FCPN; "
    "Facultad de Ciencias Puras y Naturales; UMSA; Universidad Mayor de San Andrés").split(";") if f.strip()]
# OpenAlex (carga automática de la producción y citas). La clave es opcional: OpenAlex contabiliza
# el uso por consulta y la clave permite superar el cupo gratuito si hiciera falta.
OPENALEX_URL = os.environ.get("PORTAL_OPENALEX_URL", "https://api.openalex.org")
OPENALEX_CLAVE = os.environ.get("PORTAL_OPENALEX_CLAVE")
# Correo de contacto que se envía a Crossref (su «polite pool» responde mejor si se identifica).
CONTACTO = os.environ.get("PORTAL_CONTACTO")

# Dirección pública del portal (para los enlaces de los correos).
URL_BASE = os.environ.get("PORTAL_URL", "http://localhost:5001").rstrip("/")
# Otras direcciones desde las que se accede al portal (separadas por coma), p. ej. una dirección
# interna además del dominio público. Las peticiones que modifican datos deben venir de alguna de
# ellas o del propio host (protección CSRF).
ORIGENES_EXTRA = [x.strip() for x in os.environ.get("PORTAL_ORIGENES_EXTRA", "").split(",") if x.strip()]

# Correo: "archivo" (desarrollo: guarda .eml en <datos>/correos), "smtp" (producción),
# "memoria" (tests) o "desactivado".
CORREO_MODO = os.environ.get("PORTAL_CORREO_MODO", "archivo")
CORREO_REMITENTE = os.environ.get("PORTAL_CORREO_REMITENTE", "Portal de Investigación <no-responder@instituto.test>")
SMTP_HOST = os.environ.get("PORTAL_SMTP_HOST", "localhost")
SMTP_PUERTO = int(os.environ.get("PORTAL_SMTP_PUERTO", "587"))
SMTP_USUARIO = os.environ.get("PORTAL_SMTP_USUARIO")
SMTP_CLAVE = os.environ.get("PORTAL_SMTP_CLAVE")
SMTP_STARTTLS = os.environ.get("PORTAL_SMTP_STARTTLS", "1") == "1"

# Modo solo lectura (mudanzas y mantenimiento): se puede consultar, pero ningún cambio se guarda.
SOLO_LECTURA = os.environ.get("PORTAL_SOLO_LECTURA", "0") == "1"

# Bloqueo de login: N intentos fallidos por email dentro de la ventana.
LOGIN_MAX_FALLOS = 5
LOGIN_VENTANA_MIN = 15
PASS_MIN_LARGO = 10
SESION_MAX_AGE = 8 * 3600
