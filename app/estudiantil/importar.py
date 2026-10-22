"""Carga de cohortes desde un CSV del sistema de Seguimiento Académico (PLAN §49).

Una fila por estudiante, sin materias ni notas. La clave es el registro universitario (RU): si ya existe
se actualiza su periodo de licenciatura; si no, se busca a la persona por correo o por nombre y, si no
figura, se registra. Columnas obligatorias: `ru`, `nombres`, `apellidos`, `cohorte` (AAAA-I o AAAA-II)
y `estado`. Opcionales: `email`, `sexo`, `fecha_nacimiento` (solo se guarda la edad al ingreso),
`via` (ordinaria o especial), `otra_ciudad`, `extranjero`, `colegio` (público o privado), `plan`,
`ultimo_ciclo` (obligatoria si está retirado o congelado), `fecha_egreso`, `fecha_titulacion`,
`modalidad` y `motivo` (académico o no académico; obligatorio si está retirado).

Flujo en dos pasos, como la carga de vínculos: `leer` valida y clasifica sin cambiar nada; `aplicar`
guarda las filas sin errores.
"""
import csv
import io
import re
from datetime import date

from app.comun import estudiantes, personas
from app.comun.db import auditar, get_db, sin_tildes, transaccion
from app.comun.importar_usuarios import MAX_BYTES, _booleano, _decodificar, _fecha, _separador
from app.estudiantil import cohortes

MAX_FILAS = 2000
ALIAS = {
    "ru": ("ru", "r.u.", "registro universitario", "registro", "codigo sis", "codigo"),
    "nombres": ("nombres", "nombre"),
    "apellidos": ("apellidos", "apellido"),
    "email": ("email", "correo", "e-mail", "mail", "correo institucional", "correo electronico"),
    "sexo": ("sexo", "genero"),
    "fecha_nacimiento": ("fecha nacimiento", "fecha de nacimiento", "nacimiento"),
    "cohorte": ("cohorte", "cohorte de ingreso", "ingreso", "semestre de ingreso", "ciclo de ingreso"),
    "via": ("via", "via de ingreso", "via ingreso", "modalidad de ingreso"),
    "otra_ciudad": ("otra ciudad", "procede de otra ciudad", "de otra ciudad"),
    "extranjero": ("extranjero", "es extranjero"),
    "colegio": ("colegio", "tipo de colegio", "educacion previa", "procedencia educativa"),
    "plan": ("plan", "plan de estudios"),
    "estado": ("estado", "situacion", "estado academico"),
    "ultimo_ciclo": ("ultimo ciclo", "ultimo ciclo matriculado", "ultima matricula", "ultimo semestre"),
    "fecha_egreso": ("fecha egreso", "fecha de egreso", "egreso"),
    "fecha_titulacion": ("fecha titulacion", "fecha de titulacion", "titulacion"),
    "modalidad": ("modalidad", "modalidad de titulacion"),
    "motivo": ("motivo", "motivo de retiro", "motivo de abandono", "motivo de desercion"),
}
PLANTILLA = ("ru,nombres,apellidos,email,sexo,fecha_nacimiento,cohorte,via,otra_ciudad,extranjero,colegio,plan,estado,"
             "ultimo_ciclo,fecha_egreso,fecha_titulacion,modalidad,motivo\n"
             "1234567,Sofía,Mamani Quispe,sofia@correo.bo,mujer,12/05/2004,2022-I,ordinaria,no,no,publico,Plan 2017,"
             "cursando,,,,,\n"
             "2345678,Luis,Choque Rojas,luis@correo.bo,hombre,03/09/2002,2020-II,especial,sí,no,privado,Plan 2017,"
             "titulado,,15/06/2025,20/11/2025,tesis,\n"
             "3456789,Ana,Condori Flores,,mujer,21/01/2003,2021-I,,,,,,retirado,2022-II,,,,no académico\n")

_ESTADOS = {"cursando": "cursando", "regular": "cursando", "activo": "cursando", "egresado": "egresado",
            "egresada": "egresado", "titulado": "titulado", "titulada": "titulado", "retirado": "retirado",
            "retirada": "retirado", "abandono": "retirado", "desertor": "retirado", "congelado": "congelado",
            "congelada": "congelado"}
_MODALIDADES = {"tesis": "tesis", "tesis de grado": "tesis", "proyecto de grado": "proyecto_grado", "proyecto grado": "proyecto_grado",
                "examen grado": "examen_grado",
                "proyecto": "proyecto_grado", "trabajo dirigido": "trabajo_dirigido", "examen de grado": "examen_grado",
                "examen": "examen_grado", "excelencia": "excelencia", "otra": "otra", "otro": "otra"}
_CICLO = re.compile(r"(\d{4})\s*[-/ ]\s*(ii|i|2|1)")


def _ciclo(texto: str):
    """'2023-I' → (2023, 'I'); None si viene vacío; False si no se entiende."""
    t = sin_tildes(texto or "").strip()
    if not t:
        return None
    m = _CICLO.fullmatch(t)
    return (int(m.group(1)), "I" if m.group(2) in ("i", "1") else "II") if m else False


def _opcion(valor: str, tabla: dict):
    t = sin_tildes(valor or "").strip().replace("_", " ")
    return None if not t else tabla.get(t, False)


def _si_no(valor: str):
    if not (valor or "").strip():
        return None
    r = _booleano(valor, False)
    return False if r is None else r


def _edad(nacimiento: str, anio: int, ciclo: str) -> int:
    n = date.fromisoformat(nacimiento)
    ref = date(anio, 2 if ciclo == "I" else 8, 1)
    return ref.year - n.year - ((ref.month, ref.day) < (n.month, n.day))


def _datos_fila(celda, planes: dict) -> tuple[dict, list[str]]:
    """Interpreta una fila → (datos del periodo de estudios, problemas)."""
    problemas, d = [], {}
    ru = celda("ru").strip()
    if not re.fullmatch(r"[\w.\-]{3,20}", ru):
        problemas.append("falta el registro universitario (RU)" if not ru else "RU no válido")
    d["registro_universitario"] = ru
    if not celda("nombres").strip() or not celda("apellidos").strip():
        problemas.append("faltan nombres o apellidos")
    cohorte = _ciclo(celda("cohorte"))
    if not cohorte:
        problemas.append("cohorte no válida (use AAAA-I o AAAA-II)")
    elif cohortes.ordinal(*cohorte) > cohortes.ordinal(*cohortes.ciclo_actual()) or cohorte[0] < 1990:
        problemas.append("cohorte fuera de rango")
        cohorte = False
    estado = _opcion(celda("estado"), _ESTADOS)
    if not estado:
        problemas.append("estado no válido (cursando, egresado, titulado, retirado o congelado)")
    d["estado"] = estado or None
    hoy = date.today().isoformat()
    f_egreso, f_titulacion, ultimo = _fecha(celda("fecha_egreso")), _fecha(celda("fecha_titulacion")), _ciclo(celda("ultimo_ciclo"))
    if f_egreso is False or f_titulacion is False:
        problemas.append("fecha no válida (use AAAA-MM-DD o DD/MM/AAAA)")
        f_egreso = f_titulacion = None
    if ultimo is False:
        problemas.append("último ciclo no válido (use AAAA-I o AAAA-II)")
        ultimo = None
    if (f_egreso and f_egreso > hoy) or (f_titulacion and f_titulacion > hoy):
        problemas.append("las fechas de egreso y titulación no pueden ser futuras")
    modalidad, motivo = _opcion(celda("modalidad"), _MODALIDADES), _opcion(celda("motivo"), {
        "academico": "academico", "no academico": "no_academico", "noacademico": "no_academico"})
    if modalidad is False:
        problemas.append("modalidad de titulación no válida")
    if motivo is False:
        problemas.append("motivo no válido (académico o no académico)")
    d.update(modalidad_titulacion=modalidad or None, motivo_retiro=motivo or None, fecha_egreso=None,
             fecha_titulacion=None, ultimo_anio=None, ultimo_ciclo=None, titulado=0, hasta=None)
    if cohorte and estado:
        ing = cohortes.ordinal(*cohorte)
        if estado == "titulado":
            if not f_titulacion:
                problemas.append("falta la fecha de titulación")
            else:
                f_egreso = f_egreso or f_titulacion
                if f_egreso > f_titulacion:
                    problemas.append("la titulación es anterior al egreso")
                d.update(fecha_titulacion=f_titulacion, titulado=1)
        if estado in ("egresado", "titulado"):
            if not f_egreso:
                problemas.append("falta la fecha de egreso")
            elif cohortes.ordinal(*cohortes.ciclo_de(f_egreso)) < ing:
                problemas.append("el egreso es anterior al ingreso")
            else:
                u = cohortes.ciclo_de(f_egreso)
                d.update(fecha_egreso=f_egreso, ultimo_anio=u[0], ultimo_ciclo=u[1], hasta=int(f_egreso[:4]))
        if estado in ("retirado", "congelado"):
            if not ultimo:
                problemas.append("falta el último ciclo matriculado")
            elif cohortes.ordinal(*ultimo) < ing:
                problemas.append("el último ciclo es anterior al ingreso")
            else:
                d.update(ultimo_anio=ultimo[0], ultimo_ciclo=ultimo[1], hasta=ultimo[0] if estado == "retirado" else None)
        if estado == "retirado" and not motivo:
            problemas.append("falta el motivo del retiro (académico o no académico)")
        if estado not in ("retirado", "congelado"):
            d["motivo_retiro"] = None
        if estado != "titulado":
            d["modalidad_titulacion"] = None
    if cohorte:
        d.update(cohorte_anio=cohorte[0], cohorte_ciclo=cohorte[1], desde=cohorte[0])
    # Admisión
    sexo = _opcion(celda("sexo"), {"m": "hombre", "masculino": "hombre", "hombre": "hombre", "varon": "hombre",
                                   "f": "mujer", "femenino": "mujer", "mujer": "mujer"})
    via = _opcion(celda("via"), {"ordinaria": "ordinaria", "ordinario": "ordinaria", "regular": "ordinaria",
                                 "especial": "especial", "especiales": "especial"})
    colegio = _opcion(celda("colegio"), {"publico": "publico", "fiscal": "publico", "estatal": "publico",
                                         "privado": "privado", "particular": "privado"})
    ciudad, extranjero = _si_no(celda("otra_ciudad")), _si_no(celda("extranjero"))
    for nombre, valor in (("sexo", sexo), ("vía de ingreso", via), ("colegio", colegio), ("otra ciudad", ciudad),
                          ("extranjero", extranjero)):
        if valor is False and nombre not in ("otra ciudad", "extranjero"):
            problemas.append(f"{nombre} no válido")
    if _booleano(celda("otra_ciudad"), False) is None and celda("otra_ciudad").strip():
        problemas.append("otra ciudad: responda sí o no")
    if _booleano(celda("extranjero"), False) is None and celda("extranjero").strip():
        problemas.append("extranjero: responda sí o no")
    edad = None
    nac = _fecha(celda("fecha_nacimiento"))
    if nac is False:
        problemas.append("fecha de nacimiento no válida")
    elif nac and cohorte:
        edad = _edad(nac, *cohorte)
        if not 14 <= edad <= 80:
            problemas.append("fecha de nacimiento poco creíble para la edad al ingresar")
            edad = None
    d.update(sexo=sexo or None, via_ingreso=via or None, colegio=colegio or None,
             otra_ciudad=None if ciudad is None else int(ciudad),
             extranjero=None if extranjero is None else int(extranjero), edad_ingreso=edad)
    plan = celda("plan").strip()
    d["plan_id"] = None
    if plan:
        if sin_tildes(plan) in planes:
            d["plan_id"] = planes[sin_tildes(plan)]
        else:
            problemas.append(f"el plan «{plan}» no existe en el sistema")
    return d, problemas


def _buscar_persona(ru: str, email: str, nombres: str, apellidos: str) -> tuple[dict | None, dict | None, str | None]:
    """→ (persona externa, periodo de licenciatura a actualizar, aviso)."""
    db = get_db()
    por_ru = db.q("SELECT * FROM estudiante WHERE registro_universitario = ?", [ru])
    if por_ru:
        return db.q("SELECT * FROM persona_externa WHERE id = ?", [por_ru[0]["externo_id"]])[0], por_ru[0], None
    candidatos = []
    if email:
        candidatos += db.q("SELECT * FROM persona_externa WHERE lower(email) = lower(?)", [email])
    if (c := personas.externo_similar(nombres, apellidos)) and c["id"] not in [x["id"] for x in candidatos]:
        candidatos.append(c)
    for p in candidatos:
        lic = [x for x in estudiantes.periodos(p["id"]) if x["nivel"] == "licenciatura" and x["del_programa"]]
        if any(x["registro_universitario"] for x in lic):
            continue                                   # es otra persona con el mismo nombre
        return p, (lic[0] if lic else None), f"Se vincula con la ficha existente de {p['nombres']} {p['apellidos']}."
    return None, None, None


def leer(contenido: bytes) -> tuple[list[dict], list[str]]:
    """→ (filas, errores generales). Cada fila: linea, ru, nombre, email, datos, persona, periodo, accion
    ('nueva' | 'actualiza'), aviso y errores."""
    if len(contenido) > MAX_BYTES:
        return [], ["El archivo supera 1 MB."]
    texto = _decodificar(contenido)
    if not texto.strip():
        return [], ["El archivo está vacío."]
    lector = csv.reader(io.StringIO(texto), delimiter=_separador(texto))
    encabezados = [sin_tildes(h).strip().replace("﻿", "").replace("_", " ") for h in next(lector, [])]
    indice = {c: next((i for i, h in enumerate(encabezados) if h in alias), None) for c, alias in ALIAS.items()}
    faltan = [c for c in ("ru", "nombres", "apellidos", "cohorte", "estado") if indice[c] is None]
    if faltan:
        return [], [f"Faltan columnas: {', '.join(faltan)}. La primera fila debe tener los encabezados "
                    "(ru, nombres, apellidos, cohorte y estado son obligatorios)."]
    planes = {sin_tildes(p["nombre"]): p["id"] for p in get_db().q("SELECT id, nombre FROM plan_estudios")}
    filas, vistos, n = [], {}, 0
    for linea, registro in enumerate(lector, start=2):
        if not any(c.strip() for c in registro):
            continue
        n += 1
        if n > MAX_FILAS:
            return [], [f"Se procesan hasta {MAX_FILAS} filas; divida el archivo."]

        def celda(campo, registro=registro):  # se usa en esta misma vuelta del bucle
            i = indice[campo]
            return registro[i].strip() if i is not None and i < len(registro) else ""

        datos, problemas = _datos_fila(celda, planes)
        ru = datos["registro_universitario"]
        if ru and ru in vistos:
            problemas.append(f"el RU {ru} ya aparece en la fila {vistos[ru]}")
        vistos.setdefault(ru, linea)
        email = celda("email")
        persona, periodo, aviso = (None, None, None)
        if not problemas:
            persona, periodo, aviso = _buscar_persona(ru, email, celda("nombres"), celda("apellidos"))
        filas.append({"linea": linea, "ru": ru, "nombres": celda("nombres"), "apellidos": celda("apellidos"),
                      "email": email, "datos": datos, "persona": persona, "periodo": periodo, "aviso": aviso,
                      "accion": "actualiza" if periodo else "nueva",
                      "errores": [f"Fila {linea}: {p}." for p in problemas]})
    if not filas:
        return [], ["El archivo no tiene filas con datos."]
    return filas, []


def aplicar(filas: list[dict], uid: int) -> tuple[int, int]:
    """Guarda las filas sin errores. → (nuevas, actualizadas)."""
    nuevas = actualizadas = 0
    db = get_db()
    for f in filas:
        if f["errores"]:
            continue
        d = {k: v for k, v in f["datos"].items()}
        with transaccion():
            persona = f["persona"]
            if persona is None:
                persona = personas.crear_externo(f["nombres"], f["apellidos"], None, None, uid)
            if f["email"] and not persona.get("email"):
                db.execute("UPDATE persona_externa SET email = ? WHERE id = ?", [f["email"], persona["id"]])
            periodo = f["periodo"]
            if periodo:
                db.t.estudiante.update(id=periodo["id"], **d)
                actualizadas += 1
            else:
                db.t.estudiante.insert(externo_id=persona["id"], nivel="licenciatura", del_programa=1,
                                       programa=estudiantes.programa_por_omision("licenciatura"), registrado_por=uid, **d)
                nuevas += 1
    if nuevas or actualizadas:
        auditar(uid, "importar_cohortes", "estudiante", None, f"{nuevas} nueva(s), {actualizadas} actualizada(s)")
    return nuevas, actualizadas
