"""Configuración leída del entorno, con valores por defecto aptos para desarrollo."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MIGRACIONES = RAIZ / "migrations"

DB_PATH = Path(os.environ.get("PORTAL_DB", RAIZ / "data" / "portal.db"))
SECRET_KEY = os.environ.get("PORTAL_SECRET_KEY")  # None → FastHTML usa/crea .sesskey junto a la base
HTTPS_ONLY = os.environ.get("PORTAL_HTTPS_ONLY", "0") == "1"
NOMBRE_INSTITUTO = os.environ.get("PORTAL_INSTITUTO", "Instituto de Investigación Matemática")
UNIVERSIDAD = os.environ.get("PORTAL_UNIVERSIDAD", "Universidad Mayor de San Andrés")
FACULTAD = os.environ.get("PORTAL_FACULTAD", "Facultad de Ciencias Puras y Naturales")
NOMBRE_CARRERA = os.environ.get("PORTAL_CARRERA", "Carrera de Matemática")
# Dirección, teléfonos y sitio de la Carrera para el pie del membrete de los informes (PLAN.md §55), como en la
# hoja membretada oficial. Vacío: el pie no la muestra.
DIRECCION = os.environ.get("PORTAL_DIRECCION", "")

# Contexto local: zona horaria de las fechas (plazos, «hoy», horas mostradas) y moneda de los montos.
ZONA_HORARIA = os.environ.get("PORTAL_ZONA_HORARIA", "America/La_Paz")
MONEDA = os.environ.get("PORTAL_MONEDA", "BOB")
# País del instituto: una revista de este país es «nacional» en los informes.
PAIS = os.environ.get("PORTAL_PAIS", "Bolivia")
# Durante el piloto, los artículos en revistas aún no verificadas cuentan con lo declarado. Para los
# informes de calidad, con «1» solo cuentan los de revistas verificadas (los demás quedan «por confirmar»).
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
# IA con criterio humano (PLAN §59): dos proveedores con API de chat compatible con OpenAI. Sin URL, el proveedor no
# existe; sin PORTAL_IA_EXT_ZDR=true (retención cero de datos), el externo queda deshabilitado. Nunca en la base.
IA_LOCAL_URL = os.environ.get("PORTAL_IA_LOCAL_URL")          # p. ej., http://127.0.0.1:11434/v1 (Ollama)
IA_LOCAL_MODELO = os.environ.get("PORTAL_IA_LOCAL_MODELO")
IA_EXT_URL = os.environ.get("PORTAL_IA_EXT_URL")              # p. ej., https://openrouter.ai/api/v1
IA_EXT_MODELO = os.environ.get("PORTAL_IA_EXT_MODELO")
IA_EXT_CLAVE = os.environ.get("PORTAL_IA_EXT_CLAVE")
IA_EXT_ZDR = os.environ.get("PORTAL_IA_EXT_ZDR", "").strip().lower() in ("1", "true", "si", "sí")
IA_TIEMPO_S = float(os.environ.get("PORTAL_IA_TIEMPO_S", "300"))  # límite por llamada (un modelo local es lento)
# Lista de estudiantes por paralelo (PLAN §68): la genera el sistema de notas (Kardex). Con PORTAL_LISTAS_URL, TAU la consulta a esa
# API en el momento, con la clave PORTAL_LISTAS_CLAVE, y no guarda nada. Sin ella se usa la copia temporal que carga la Dirección.
LISTAS_URL = (os.environ.get("PORTAL_LISTAS_URL") or "").rstrip("/")
LISTAS_CLAVE = os.environ.get("PORTAL_LISTAS_CLAVE")
LISTAS_TIEMPO_S = float(os.environ.get("PORTAL_LISTAS_TIEMPO_S", "10"))
# Correo de contacto que se envía a Crossref (su «polite pool» responde mejor si se identifica).
CONTACTO = os.environ.get("PORTAL_CONTACTO")

# Nombre del sistema: el corto va en el encabezado, los correos y las exportaciones; la
# descripción, en el ingreso y donde haya espacio.
NOMBRE_SISTEMA = os.environ.get("PORTAL_SISTEMA", "TAU")
DESCRIPCION_SISTEMA = os.environ.get(
    "PORTAL_SISTEMA_DESCRIPCION", "Sistema Integrado de Gestión Académica y Científica de la Carrera de Matemática")
NOMBRE_COMPLETO = f"{NOMBRE_SISTEMA} | {DESCRIPCION_SISTEMA}"

# Dirección pública del sistema (para los enlaces de los correos).
URL_BASE = os.environ.get("PORTAL_URL", "http://localhost:5001").rstrip("/")
# Otras direcciones desde las que se accede al sistema (separadas por coma), p. ej. una dirección
# interna además del dominio público. Las peticiones que modifican datos deben venir de alguna de
# ellas o del propio host (protección CSRF).
ORIGENES_EXTRA = [x.strip() for x in os.environ.get("PORTAL_ORIGENES_EXTRA", "").split(",") if x.strip()]

# Correo: "archivo" (desarrollo: guarda .eml en <datos>/correos), "smtp" (producción),
# "memoria" (tests) o "desactivado".
CORREO_MODO = os.environ.get("PORTAL_CORREO_MODO", "archivo")
CORREO_REMITENTE = os.environ.get("PORTAL_CORREO_REMITENTE", f"{NOMBRE_SISTEMA} <no-responder@instituto.test>")
SMTP_HOST = os.environ.get("PORTAL_SMTP_HOST", "localhost")
SMTP_PUERTO = int(os.environ.get("PORTAL_SMTP_PUERTO", "587"))
SMTP_USUARIO = os.environ.get("PORTAL_SMTP_USUARIO")
SMTP_CLAVE = os.environ.get("PORTAL_SMTP_CLAVE")
SMTP_STARTTLS = os.environ.get("PORTAL_SMTP_STARTTLS", "1") == "1"

# Modo solo lectura (mudanzas y mantenimiento): se puede consultar, pero ningún cambio se guarda.
SOLO_LECTURA = os.environ.get("PORTAL_SOLO_LECTURA", "0") == "1"
# Piloto con usuarios reales (PLAN §72, etapa 9): cada pantalla lleva «Comentar esta pantalla».
PILOTO = os.environ.get("PORTAL_PILOTO", "0") == "1"
# Informes que se envían solos a las direcciones (app.calidad.programados). Las pruebas los apagan.
INFORMES_PROGRAMADOS = os.environ.get("PORTAL_INFORMES_PROGRAMADOS", "1") == "1"
# Registros (app/comun/registros.py): «archivo» (consola y data/registros/portal.log) o «consola».
REGISTROS = os.environ.get("PORTAL_REGISTROS", "archivo")
# Correo al que se avisa de un error del servidor (a lo más uno cada 15 minutos); vacío = no se avisa.
AVISO_ERRORES = os.environ.get("PORTAL_AVISO_ERRORES", "").strip() or None

# Bloqueo de login: N intentos fallidos por email dentro de la ventana.
LOGIN_MAX_FALLOS = 5
LOGIN_VENTANA_MIN = 15
# Fallos desde una misma IP, con cualquier correo, dentro de la misma ventana (PLAN §62). Más alto que el límite por
# correo: una sala de computación o una red con NAT comparte la IP.
LOGIN_MAX_FALLOS_IP = 20
PASS_MIN_LARGO = 10
SESION_MAX_AGE = 8 * 3600

# Tamaño máximo de una petición (PLAN §62): el adjunto mayor es de 20 MB; el resto es margen para los demás campos.
MAX_CUERPO = int(os.environ.get("PORTAL_MAX_CUERPO_MB", "25")) * 1024 * 1024
