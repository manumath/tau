"""Configuración leída del entorno, con valores por defecto aptos para desarrollo."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Hasta el 17-nov-2026 las variables de entorno se llamaban PORTAL_*; ahora son TAU_* (PLAN §74). Una instalación que aún
# las tenga no puede quedar mal configurada en silencio (p. ej., sin clave de sesión ni servidor de correo).
_VIEJAS = sorted(k for k in os.environ if k.startswith("PORTAL_"))
if _VIEJAS:
    print(f"AVISO: estas variables ya no se leen; cámbieles el prefijo PORTAL_ por TAU_: {', '.join(_VIEJAS)}", flush=True)
MIGRACIONES = RAIZ / "migrations"
# La instancia de esta instalación (PLAN §74): la carpeta con los datos y la marca de la unidad. Vive fuera del código;
# sin la variable, se usa la de ejemplo del repositorio. `scripts/instalar.py` la carga en una base nueva.
INSTANCIA = Path(os.environ.get("TAU_INSTANCIA") or RAIZ / "instancias" / "ejemplo")

DB_PATH = Path(os.environ.get("TAU_DB", RAIZ / "data" / "tau.db"))
SECRET_KEY = os.environ.get("TAU_SECRET_KEY")  # None → FastHTML usa/crea .sesskey junto a la base
HTTPS_ONLY = os.environ.get("TAU_HTTPS_ONLY", "0") == "1"
# Nombres de las unidades (membretes, páginas públicas, correos): salen de la tabla `unidad`, que la Administración del
# sistema edita en Administración → Unidades (PLAN §73). La variable de entorno, si está, manda sobre la tabla; el valor
# de la derecha solo se usa antes de que exista la base. Se resuelven al pedirlos (`__getattr__`, al final).
_UNIDADES = {"NOMBRE_INSTITUTO": ("TAU_INSTITUTO", "instituto", "Instituto"),
             "UNIVERSIDAD": ("TAU_UNIVERSIDAD", "universidad", "Universidad"),
             "FACULTAD": ("TAU_FACULTAD", "facultad", "Facultad"),
             "NOMBRE_CARRERA": ("TAU_CARRERA", "carrera", "Carrera")}
# Dirección, teléfonos y sitio de la Carrera para el pie del membrete de los informes (PLAN.md §55), como en la
# hoja membretada oficial. Vacío: el pie no la muestra.
DIRECCION = os.environ.get("TAU_DIRECCION", "")

# Contexto local: zona horaria de las fechas (plazos, «hoy», horas mostradas) y moneda de los montos.
ZONA_HORARIA = os.environ.get("TAU_ZONA_HORARIA", "America/La_Paz")
MONEDA = os.environ.get("TAU_MONEDA", "BOB")
# País del instituto: una revista de este país es «nacional» en los informes.
PAIS = os.environ.get("TAU_PAIS", "Bolivia")
# Durante el piloto, los artículos en revistas aún no verificadas cuentan con lo declarado. Para los
# informes de calidad, con «1» solo cuentan los de revistas verificadas (los demás quedan «por confirmar»).
EXIGIR_REVISTA_VERIFICADA = os.environ.get("TAU_EXIGIR_REVISTA_VERIFICADA", "0") == "1"
SIMBOLOS_MONEDA = {"BOB": "Bs", "USD": "US$", "EUR": "€"}

# Nombres que cuentan como filiación del instituto en una publicación (se comparan sin tildes ni
# mayúsculas; las siglas, como palabra completa). Vale cualquier instancia que contiene al
# instituto y la doble filiación: por omisión, la sigla y el nombre de cada unidad de la tabla. Con
# TAU_FILIACIONES (separados por «;») se fija otra lista. Se resuelve al pedirla (`config.FILIACIONES`).
# OpenAlex (carga automática de la producción y citas). La clave es opcional: OpenAlex contabiliza
# el uso por consulta y la clave permite superar el cupo gratuito si hiciera falta.
OPENALEX_URL = os.environ.get("TAU_OPENALEX_URL", "https://api.openalex.org")
OPENALEX_CLAVE = os.environ.get("TAU_OPENALEX_CLAVE")
# IA con criterio humano (PLAN §59): dos proveedores con API de chat compatible con OpenAI. Sin URL, el proveedor no
# existe; sin TAU_IA_EXT_ZDR=true (retención cero de datos), el externo queda deshabilitado. Nunca en la base.
IA_LOCAL_URL = os.environ.get("TAU_IA_LOCAL_URL")          # p. ej., http://127.0.0.1:11434/v1 (Ollama)
IA_LOCAL_MODELO = os.environ.get("TAU_IA_LOCAL_MODELO")
IA_EXT_URL = os.environ.get("TAU_IA_EXT_URL")              # p. ej., https://openrouter.ai/api/v1
IA_EXT_MODELO = os.environ.get("TAU_IA_EXT_MODELO")
IA_EXT_CLAVE = os.environ.get("TAU_IA_EXT_CLAVE")
IA_EXT_ZDR = os.environ.get("TAU_IA_EXT_ZDR", "").strip().lower() in ("1", "true", "si", "sí")
IA_TIEMPO_S = float(os.environ.get("TAU_IA_TIEMPO_S", "300"))  # límite por llamada (un modelo local es lento)
# Lista de estudiantes por paralelo (PLAN §68): la genera el sistema de notas (Kardex). Con TAU_LISTAS_URL, TAU la consulta a esa
# API en el momento, con la clave TAU_LISTAS_CLAVE, y no guarda nada. Sin ella se usa la copia temporal que carga la Dirección.
LISTAS_URL = (os.environ.get("TAU_LISTAS_URL") or "").rstrip("/")
LISTAS_CLAVE = os.environ.get("TAU_LISTAS_CLAVE")
LISTAS_TIEMPO_S = float(os.environ.get("TAU_LISTAS_TIEMPO_S", "10"))
# Correo de contacto que se envía a Crossref (su «polite pool» responde mejor si se identifica).
CONTACTO = os.environ.get("TAU_CONTACTO")

# Nombre del sistema: el corto va en el encabezado, los correos y las exportaciones; la
# descripción, en el ingreso y donde haya espacio.
NOMBRE_SISTEMA = os.environ.get("TAU_SISTEMA", "TAU")
# DESCRIPCION_SISTEMA y NOMBRE_COMPLETO llevan el nombre de la Carrera: se resuelven al pedirlos (`__getattr__`).

# Dirección pública del sistema (para los enlaces de los correos).
URL_BASE = os.environ.get("TAU_URL", "http://localhost:5001").rstrip("/")
# Otras direcciones desde las que se accede al sistema (separadas por coma), p. ej. una dirección
# interna además del dominio público. Las peticiones que modifican datos deben venir de alguna de
# ellas o del propio host (protección CSRF).
ORIGENES_EXTRA = [x.strip() for x in os.environ.get("TAU_ORIGENES_EXTRA", "").split(",") if x.strip()]

# Correo: "archivo" (desarrollo: guarda .eml en <datos>/correos), "smtp" (producción),
# "memoria" (tests) o "desactivado".
CORREO_MODO = os.environ.get("TAU_CORREO_MODO", "archivo")
CORREO_REMITENTE = os.environ.get("TAU_CORREO_REMITENTE", f"{NOMBRE_SISTEMA} <no-responder@instituto.test>")
SMTP_HOST = os.environ.get("TAU_SMTP_HOST", "localhost")
SMTP_PUERTO = int(os.environ.get("TAU_SMTP_PUERTO", "587"))
SMTP_USUARIO = os.environ.get("TAU_SMTP_USUARIO")
SMTP_CLAVE = os.environ.get("TAU_SMTP_CLAVE")
SMTP_STARTTLS = os.environ.get("TAU_SMTP_STARTTLS", "1") == "1"

# Modo solo lectura (mudanzas y mantenimiento): se puede consultar, pero ningún cambio se guarda.
SOLO_LECTURA = os.environ.get("TAU_SOLO_LECTURA", "0") == "1"
# Módulos con que arranca una base **nueva** (PLAN §73): minimo, instituto, carrera, carrera_instituto o completo
# (app/comun/modulos.PERFILES). Después manda Administración → Módulos; en una base en uso no tiene efecto.
PERFIL = os.environ.get("TAU_PERFIL", "minimo")
# Piloto con usuarios reales (PLAN §72, etapa 9): cada pantalla lleva «Comentar esta pantalla».
PILOTO = os.environ.get("TAU_PILOTO", "0") == "1"
# Informes que se envían solos a las direcciones (app.informes.programados). Las pruebas los apagan.
INFORMES_PROGRAMADOS = os.environ.get("TAU_INFORMES_PROGRAMADOS", "1") == "1"
# Registros (app/comun/registros.py): «archivo» (consola y data/registros/tau.log) o «consola».
REGISTROS = os.environ.get("TAU_REGISTROS", "archivo")
# Correo al que se avisa de un error del servidor (a lo más uno cada 15 minutos); vacío = no se avisa.
AVISO_ERRORES = os.environ.get("TAU_AVISO_ERRORES", "").strip() or None

# Bloqueo de login: N intentos fallidos por email dentro de la ventana.
LOGIN_MAX_FALLOS = 5
LOGIN_VENTANA_MIN = 15
# Fallos desde una misma IP, con cualquier correo, dentro de la misma ventana (PLAN §62). Más alto que el límite por
# correo: una sala de computación o una red con NAT comparte la IP.
LOGIN_MAX_FALLOS_IP = 20
PASS_MIN_LARGO = 10
SESION_MAX_AGE = 8 * 3600

# Tamaño máximo de una petición (PLAN §62): el adjunto mayor es de 20 MB; el resto es margen para los demás campos.
MAX_CUERPO = int(os.environ.get("TAU_MAX_CUERPO_MB", "25")) * 1024 * 1024


def __getattr__(nombre: str):
    """Los valores que dependen de las unidades de esta instalación: se leen de la base cada vez (con su caché), para
    que un cambio en Administración → Unidades se vea sin reiniciar."""
    if nombre in _UNIDADES:
        variable, tipo, inicial = _UNIDADES[nombre]
        if os.environ.get(variable):
            return os.environ[variable]
        try:
            from app.comun import unidades   # diferida: `db` importa este módulo
            return unidades.nombre_de(tipo)
        except Exception:                    # la base aún no existe (al importar, en un script)
            return inicial
    if nombre == "DESCRIPCION_SISTEMA":
        return os.environ.get("TAU_SISTEMA_DESCRIPCION") or (
            f"Sistema Integrado de Gestión Académica y Científica de la {__getattr__('NOMBRE_CARRERA')}")
    if nombre == "NOMBRE_COMPLETO":
        return f"{NOMBRE_SISTEMA} | {__getattr__('DESCRIPCION_SISTEMA')}"
    if nombre == "FILIACIONES":
        if os.environ.get("TAU_FILIACIONES"):
            return [f.strip() for f in os.environ["TAU_FILIACIONES"].split(";") if f.strip()]
        try:
            from app.comun import unidades
            return unidades.filiaciones()
        except Exception:
            return [x for _, _, inicial in _UNIDADES.values() for x in (inicial,)]
    raise AttributeError(f"module 'app.comun.config' has no attribute '{nombre}'")

