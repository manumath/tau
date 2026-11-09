"""Servicio de IA con criterio humano (PLAN §59, etapa 0a). Única puerta hacia los modelos.

`generar(clave, datos, auth)` comprueba, en este orden y en el servidor:
  1. que no se invoque desde un módulo vedado (principio 2), ni para una función de un módulo vedado;
  2. que la función esté activa (todas nacen apagadas, principio 6) y que la persona pueda pedirla;
  3. el nivel de cada dato (`clasificacion`): un dato sensible o por encima del máximo de la función se rechaza;
  4. seudonimiza los nombres de personas si la función lo pide (la correspondencia queda solo en memoria);
  5. elige el proveedor según el nivel (anexo A): el externo solo con retención cero (`PORTAL_IA_EXT_ZDR`), y con datos
     personales solo seudonimizados; si falla, el local cuando el nivel lo permite;
  6. registra el uso y lo audita.
La salida nace como `borrador_ia` y no surte efecto hasta que una persona la aprueba (`decidir`, principio 1).
"""
import hashlib
import inspect
import re
import threading
from difflib import SequenceMatcher
from pathlib import Path

import httpx2

from app.comun import config, notificaciones, usuarios
from app.comun.db import AHORA, auditar, get_db, transaccion
from app.ia import clasificacion
from app.ia.funciones import VEDADOS, Funcion, obtener as funcion

NO_DISPONIBLE = "La función de IA no está disponible; puede continuar manualmente."
DIR_INSTRUCCIONES = Path(__file__).parent / "instrucciones"
RAIZ = Path(__file__).resolve().parents[2]
# Archivos de los módulos vedados: si la llamada viene de uno de ellos, se bloquea aunque la función sea válida.
ARCHIVOS_VEDADOS = (
    "app/servicios/auxiliaturas.py", "app/servicios/rutas/auxiliaturas.py",
    "app/servicios/grado.py", "app/servicios/rutas/grado.py",
    "app/academico/oferta.py", "app/academico/rutas/oferta.py",
    "app/academico/carga.py", "app/academico/rutas/carga.py",
    "app/estudiantil/tutoria.py", "app/estudiantil/rutas/tutoria.py",
)
ESTADOS_FINALES = ("aprobada", "editada", "rechazada")


class IAError(Exception):
    """Error que se muestra tal cual a la persona."""


class IABloqueada(IAError):
    pass


class IADatosNoPermitidos(IAError):
    pass


class IANoDisponible(IAError):
    pass


# --- Política y activación ------------------------------------------------------------------------------------------

def politica_vigente() -> dict | None:
    filas = get_db().q("SELECT * FROM ia_politica WHERE vigente = 1")
    return filas[0] if filas else None


def politicas() -> list[dict]:
    return get_db().q("SELECT * FROM ia_politica ORDER BY version DESC")


def crear_politica(texto: str, uid: int) -> tuple[int | None, str | None]:
    texto = (texto or "").strip()
    if not texto:
        return None, "Escriba el texto de la política."
    version = get_db().q("SELECT COALESCE(MAX(version), 0) + 1 AS n FROM ia_politica")[0]["n"]
    pid = get_db().t.ia_politica.insert(version=version, texto=texto, creado_por=uid)["id"]
    auditar(uid, "ia_crear_politica", "ia_politica", pid, f"versión {version}")
    return pid, None


def aprobar_politica(pid: int, uid: int) -> str | None:
    p = get_db().q("SELECT * FROM ia_politica WHERE id = ?", [pid])
    if not p:
        return "La política no existe."
    if p[0]["fecha_aprobacion"]:
        return "Esa versión ya fue aprobada."
    with transaccion():
        get_db().execute("UPDATE ia_politica SET vigente = 0")
        get_db().execute(f"UPDATE ia_politica SET vigente = 1, aprobada_por = ?, fecha_aprobacion = {AHORA} WHERE id = ?",
                         [uid, pid])
    auditar(uid, "ia_aprobar_politica", "ia_politica", pid, f"versión {p[0]['version']}")
    return None


def estado_funcion(clave: str) -> dict:
    filas = get_db().q("SELECT * FROM ia_funcion WHERE clave = ?", [clave])
    return filas[0] if filas else {"clave": clave, "activa": 0, "responsable_id": None}


def activa(clave: str) -> bool:
    return bool(estado_funcion(clave)["activa"])


def activar(clave: str, responsable_id: int | None, uid: int) -> str | None:
    """Activa una función con su responsable. Exige una política de uso aprobada."""
    f = funcion(clave)
    if not f:
        return "La función no existe."
    if not politica_vigente():
        return "Antes de activar una función, la Dirección debe aprobar la política de uso de la IA."
    r = usuarios.por_id(responsable_id) if responsable_id else None
    if not r or not r["activo"]:
        return "Designe a la persona responsable de la función."
    get_db().execute(f"""INSERT INTO ia_funcion (clave, activa, responsable_id, actualizado_por, actualizado_en)
                         VALUES (?, 1, ?, ?, {AHORA})
                         ON CONFLICT (clave) DO UPDATE SET activa = 1, responsable_id = excluded.responsable_id,
                         actualizado_por = excluded.actualizado_por, actualizado_en = excluded.actualizado_en""",
                     [clave, responsable_id, uid])
    auditar(uid, "ia_activar", "ia_funcion", None, f"{clave}; responsable {responsable_id}")
    return None


def desactivar(clave: str, uid: int):
    get_db().execute(f"UPDATE ia_funcion SET activa = 0, actualizado_por = ?, actualizado_en = {AHORA} WHERE clave = ?",
                     [uid, clave])
    auditar(uid, "ia_desactivar", "ia_funcion", None, clave)


# --- Instrucciones versionadas ----------------------------------------------------------------------------------------

def instrucciones(clave: str) -> tuple[int, str]:
    """La versión más alta de app/ia/instrucciones/<clave>/v<n>.md."""
    versiones = sorted((int(m.group(1)), p) for p in (DIR_INSTRUCCIONES / clave).glob("v*.md")
                       if (m := re.fullmatch(r"v(\d+)\.md", p.name)))
    if not versiones:
        raise IANoDisponible(NO_DISPONIBLE)
    version, ruta = versiones[-1]
    return version, ruta.read_text(encoding="utf-8").strip()


# --- Datos: nivel y seudonimización -----------------------------------------------------------------------------------

def nivel_de(datos: list[tuple[str, str]]) -> int:
    return max((clasificacion.nivel(origen) for origen, _ in datos), default=clasificacion.PUBLICO)


def seudonimizar(datos: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """Reemplaza cada nombre de persona (y cada palabra de su nombre) por [PERSONA_n] en todos los datos.
    → (datos seudonimizados, {marcador: nombre}); la correspondencia no se guarda en ninguna parte."""
    nombres = []
    for origen, valor in datos:
        if origen in clasificacion.NOMBRES and valor and valor.strip() not in nombres:
            nombres.append(valor.strip())
    mapa = {f"[PERSONA_{i}]": n for i, n in enumerate(nombres, start=1)}
    reemplazos = []  # (patrón, marcador): primero los nombres completos, luego sus palabras
    for marcador, n in mapa.items():
        reemplazos.append((re.escape(n), marcador))
    for marcador, n in mapa.items():
        reemplazos += [(rf"\b{re.escape(w)}\b", marcador) for w in n.split() if len(w) > 2]

    def limpiar(texto: str) -> str:
        for patron, marcador in reemplazos:
            texto = re.sub(patron, marcador, texto)
        return texto
    return [(o, limpiar(v or "")) for o, v in datos], mapa


def restaurar(texto: str, mapa: dict[str, str]) -> str:
    for marcador, nombre in mapa.items():
        texto = texto.replace(marcador, nombre)
    return texto


# --- Proveedores ------------------------------------------------------------------------------------------------------

def proveedores(f: Funcion, nivel: int, seudonimizado: bool) -> list[dict]:
    """Proveedores permitidos, en orden de preferencia (anexo A)."""
    res = []
    externo_permitido = nivel <= clasificacion.INTERNO or (nivel == clasificacion.PERSONAL and seudonimizado)
    if (f.externa and externo_permitido and config.IA_EXT_ZDR and config.IA_EXT_URL and config.IA_EXT_MODELO):
        res.append({"tipo": "externo", "url": config.IA_EXT_URL, "modelo": config.IA_EXT_MODELO,
                    "clave": config.IA_EXT_CLAVE})
    if nivel <= clasificacion.PERSONAL and config.IA_LOCAL_URL and config.IA_LOCAL_MODELO:
        res.append({"tipo": "local", "url": config.IA_LOCAL_URL, "modelo": config.IA_LOCAL_MODELO, "clave": None})
    return res


def cuerpo(prov: dict, f: Funcion, sistema: str, usuario_txt: str) -> dict:
    c = {"model": prov["modelo"], "temperature": 0.3, "max_tokens": f.max_tokens,
         "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario_txt}]}
    if prov["tipo"] == "externo":
        c["provider"] = {"zdr": True}  # retención cero en cada solicitud, además de la configuración de la cuenta
    return c


def _enviar(url: str, cabeceras: dict, datos: dict, tiempo: float) -> str:
    """Llamada HTTP a la API de chat (compatible con OpenAI). Las pruebas la reemplazan: nunca salen a la red."""
    r = httpx2.post(url.rstrip("/") + "/chat/completions", json=datos, headers=cabeceras, timeout=tiempo)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _texto_usuario(datos: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"[{origen}]\n{valor}" for origen, valor in datos)


# --- Invocación -------------------------------------------------------------------------------------------------------

def _desde_modulo_vedado() -> str | None:
    for marco in inspect.stack(context=0)[2:]:
        try:
            rel = Path(marco.filename).resolve().relative_to(RAIZ).as_posix()
        except ValueError:
            continue
        if rel in ARCHIVOS_VEDADOS:
            return rel
    return None


def generar(clave: str, datos: list[tuple[str, str]], auth: dict, entidad_tipo: str | None = None,
            entidad_id: int | None = None, en_fondo: bool = False, solo_local: bool = False,
            posproceso=None) -> int:
    """Pide un borrador a la IA. → id del uso (estado `generando`, luego `borrador_ia` o `error`).
    `entidad_tipo` identifica el documento («memoria:memoria-2026»); `solo_local` impide el proveedor externo aunque el
    nivel lo permita (p. ej., respuestas anónimas); `posproceso(texto) → texto` se aplica a la respuesta antes de
    guardarla (cifras desde la base, citas textuales). Lanza IAError (con un mensaje para la persona) si no se puede."""
    f = funcion(clave)
    if f is None:
        raise ValueError(f"Función de IA desconocida: {clave}")
    origen = _desde_modulo_vedado()
    if f.modulo in VEDADOS or origen:
        auditar(auth["id"], "ia_bloqueada", "ia_funcion", None, f"{clave} desde {origen or f.modulo}")
        raise IABloqueada("La IA no puede usarse en este módulo: es una decisión que toman personas.")
    if not activa(clave):
        raise IANoDisponible("Esta función de IA no está activa.")
    if not f.puede_pedir(auth, entidad_tipo):
        raise IABloqueada("No tiene permiso para usar esta función de IA.")
    nivel = nivel_de(datos)
    if nivel == clasificacion.SENSIBLE or nivel > f.nivel_max:
        auditar(auth["id"], "ia_datos_rechazados", "ia_funcion", None, f"{clave}: nivel {nivel}")
        raise IADatosNoPermitidos("Estos datos no pueden enviarse a la IA.")
    mapa = {}
    if f.seudonimizar:
        datos, mapa = seudonimizar(datos)
    provs = [p for p in proveedores(f, nivel, f.seudonimizar) if not (solo_local and p["tipo"] == "externo")]
    if not provs:
        raise IANoDisponible(NO_DISPONIBLE)
    version, sistema = instrucciones(clave)
    usuario_txt = _texto_usuario(datos)
    uso_id = get_db().t.ia_uso.insert(
        funcion_clave=clave, usuario_id=auth["id"], version_prompt=version, nivel_datos=nivel,
        hash_entrada=hashlib.sha256(usuario_txt.encode()).hexdigest(), seudonimizado=int(f.seudonimizar),
        entidad_tipo=entidad_tipo, entidad_id=entidad_id)["id"]
    auditar(auth["id"], "ia_invocar", "ia_uso", uso_id, f"{clave} v{version}; nivel {nivel}")
    trabajo = (uso_id, f, provs, sistema, usuario_txt, mapa, auth["id"] if en_fondo else None, posproceso)
    if en_fondo:
        threading.Thread(target=_ejecutar, args=trabajo, name=f"ia-{uso_id}", daemon=True).start()
    else:
        _ejecutar(*trabajo)
    return uso_id


def _ejecutar(uso_id, f, provs, sistema, usuario_txt, mapa, avisar_a, posproceso=None):
    ultimo = None
    for prov in provs:
        cabeceras = {"Authorization": f"Bearer {prov['clave']}"} if prov["clave"] else {}
        try:
            texto = _enviar(prov["url"], cabeceras, cuerpo(prov, f, sistema, usuario_txt), config.IA_TIEMPO_S)
        except Exception as e:  # cualquier falla del proveedor: se intenta el siguiente
            ultimo = f"{prov['tipo']}: {type(e).__name__}"
            continue
        texto = restaurar(texto.strip(), mapa)
        if posproceso:
            texto = posproceso(texto)
        with transaccion():
            get_db().execute(f"""UPDATE ia_uso SET estado = 'borrador_ia', proveedor = ?, modelo = ?, terminado_en = {AHORA}
                                 WHERE id = ?""", [prov["tipo"], prov["modelo"], uso_id])
            get_db().t.ia_salida.insert(uso_id=uso_id, texto_generado=texto)
        auditar(None, "ia_borrador", "ia_uso", uso_id, f"{f.clave}; {prov['tipo']} {prov['modelo']}")
        if avisar_a:
            notificaciones.avisar(usuarios.por_id(avisar_a), f"Borrador de IA listo: {f.nombre}",
                                  "El borrador está listo para que lo revise. No surte efecto hasta que lo apruebe.")
        return
    get_db().execute(f"UPDATE ia_uso SET estado = 'error', error = ?, terminado_en = {AHORA} WHERE id = ?",
                     [ultimo, uso_id])
    auditar(None, "ia_error", "ia_uso", uso_id, f"{f.clave}; {ultimo}")
    if avisar_a:
        notificaciones.avisar(usuarios.por_id(avisar_a), f"IA no disponible: {f.nombre}", NO_DISPONIBLE)


# --- Revisión humana --------------------------------------------------------------------------------------------------

def obtener(uso_id: int) -> dict | None:
    filas = get_db().q("""SELECT u.*, s.texto_generado, s.texto_final FROM ia_uso u
                          LEFT JOIN ia_salida s ON s.uso_id = u.id WHERE u.id = ?""", [uso_id])
    return filas[0] if filas else None


def distancia(generado: str, final: str) -> float:
    """0 = sin cambios, 1 = todo distinto."""
    return round(1 - SequenceMatcher(None, generado, final).ratio(), 4)


def decidir(uso_id: int, auth: dict, decision: str, texto_final: str = "", motivo: str = "",
            valoracion: str | int | None = None) -> list[str]:
    """La decisión humana sobre un borrador: «aprobar» (con o sin cambios) o «rechazar». → errores."""
    uso = obtener(uso_id)
    if not uso:
        return ["El borrador no existe."]
    f = funcion(uso["funcion_clave"])
    if uso["estado"] != "borrador_ia":
        return ["Este borrador ya fue revisado o no está listo."]
    if not f or not f.puede_aprobar(auth, uso):
        return ["No le corresponde revisar este borrador."]
    val = None
    if valoracion not in (None, ""):
        if not str(valoracion).isdigit() or not 1 <= int(valoracion) <= 5:
            return ["La valoración va de 1 a 5."]
        val = int(valoracion)
    if decision == "aprobar":
        final = (texto_final or "").strip()
        if not final:
            return ["El texto aprobado no puede quedar vacío."]
        estado = "aprobada" if final == uso["texto_generado"].strip() else "editada"
        dist = distancia(uso["texto_generado"].strip(), final)
    elif decision == "rechazar":
        estado, final, dist = "rechazada", None, None
    else:
        return ["Decisión desconocida."]
    with transaccion():
        get_db().execute(f"""UPDATE ia_uso SET estado = ?, revisor_id = ?, fecha_decision = {AHORA}, motivo = ?,
                             distancia_edicion = ?, valoracion = ? WHERE id = ?""",
                         [estado, auth["id"], (motivo or "").strip()[:1000] or None, dist, val, uso_id])
        get_db().execute("UPDATE ia_salida SET texto_final = ? WHERE uso_id = ?", [final, uso_id])
    auditar(auth["id"], "ia_decision", "ia_uso", uso_id, f"{uso['funcion_clave']}: {estado}")
    if final is not None and f.al_aprobar:
        f.al_aprobar(obtener(uso_id), final)
    return []


def texto_aprobado(uso_id: int) -> str | None:
    """El texto que puede surtir efecto: solo el aprobado por una persona."""
    uso = obtener(uso_id)
    return uso["texto_final"] if uso and uso["estado"] in ("aprobada", "editada") else None


def marca(uso: dict) -> str:
    """Etiqueta visible del texto (principio 4)."""
    if uso["estado"] in ("aprobada", "editada"):
        f = funcion(uso["funcion_clave"])
        fecha = uso["fecha_decision"][:10]
        return (f"Elaborado con apoyo de IA; revisado por {f.revisor if f else 'una persona'}, "
                f"{fecha[8:10]}/{fecha[5:7]}/{fecha[:4]}")
    return "Borrador generado con IA"


# --- Consultas por documento ------------------------------------------------------------------------------------------

def ultimo(clave: str, entidad_tipo: str) -> dict | None:
    """El uso más reciente de la función sobre ese documento (cualquiera sea su estado)."""
    filas = get_db().q("""SELECT id FROM ia_uso WHERE funcion_clave = ? AND entidad_tipo = ? ORDER BY id DESC LIMIT 1""",
                       [clave, entidad_tipo])
    return obtener(filas[0]["id"]) if filas else None


def aprobado(clave: str, entidad_tipo: str) -> dict | None:
    """El último texto aprobado por una persona para ese documento: lo único que se muestra o surte efecto."""
    filas = get_db().q("""SELECT id FROM ia_uso WHERE funcion_clave = ? AND entidad_tipo = ?
                          AND estado IN ('aprobada', 'editada') ORDER BY id DESC LIMIT 1""", [clave, entidad_tipo])
    return obtener(filas[0]["id"]) if filas else None


def pendiente(clave: str, entidad_tipo: str) -> dict | None:
    """Un borrador en curso o por revisar, si lo hay (el último uso; uno con error no cuenta)."""
    u = ultimo(clave, entidad_tipo)
    return u if u and u["estado"] in ("generando", "borrador_ia") else None
