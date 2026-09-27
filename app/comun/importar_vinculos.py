"""Carga del historial de vínculos desde un CSV de Recursos Humanos.

Formato: una fila por periodo con `email`, `categoria`, `desde` y, opcionalmente, `hasta`
(vacío = vigente), `jornada` (horas semanales), `nota` y `unidad` (IIMAT o CMAT; vacío = IIMAT).
Fechas como AAAA-MM-DD o DD/MM/AAAA. Para cada persona y unidad del archivo, su historial con esa
unidad se **reemplaza** por el del archivo (Recursos Humanos es la fuente oficial); lo que no
aparece no cambia.

Flujo en dos pasos, como la carga de cuentas: `leer` valida y agrupa por persona sin cambiar
nada; `aplicar` reemplaza el historial de las personas sin errores.
"""
import csv
import io

from app.comun import unidades, usuarios, vinculos
from app.comun.db import auditar, sin_tildes
from app.comun.importar_usuarios import MAX_BYTES, _categoria, _decodificar, _fecha, _separador

MAX_FILAS = 2000
ALIAS = {
    "email": ("email", "correo", "e-mail", "mail", "correo electronico", "correo institucional"),
    "categoria": ("categoria",),
    "desde": ("desde", "inicio", "fecha inicio", "fecha de inicio", "fecha ingreso", "fecha de ingreso"),
    "hasta": ("hasta", "termino", "fin", "fecha termino", "fecha de termino", "fecha fin"),
    "jornada": ("jornada", "horas", "horas semanales", "jornada horas"),
    "nota": ("nota", "observacion", "observaciones", "resolucion"),
    "unidad": ("unidad", "dependencia", "unidad academica"),
}
PLANTILLA = ("email,unidad,categoria,desde,hasta,jornada,nota\n"
             "emmy.noether@umsa.bo,IIMAT,contratado,01/03/2018,31/12/2021,40,Contrato 12/2018\n"
             "emmy.noether@umsa.bo,IIMAT,titular,01/01/2022,,40,Resolución 345/2021\n"
             "emmy.noether@umsa.bo,CMAT,titular,01/03/2015,,20,Docente de la Carrera\n")


def leer(contenido: bytes) -> tuple[list[dict], list[str]]:
    """→ (personas, errores generales). Una entrada por persona y unidad: email, unidad (sigla),
    unidad_id, usuario, periodos, actuales (n.º de periodos que se reemplazarán), errores."""
    if len(contenido) > MAX_BYTES:
        return [], ["El archivo supera 1 MB."]
    texto = _decodificar(contenido)
    if not texto.strip():
        return [], ["El archivo está vacío."]
    lector = csv.reader(io.StringIO(texto), delimiter=_separador(texto))
    encabezados = [sin_tildes(h).strip().replace("﻿", "") for h in next(lector, [])]
    indice = {c: next((i for i, h in enumerate(encabezados) if h in alias), None) for c, alias in ALIAS.items()}
    faltan = [c for c in ("email", "categoria", "desde") if indice[c] is None]
    if faltan:
        return [], [f"Faltan columnas: {', '.join(faltan)}. La primera fila debe tener los encabezados "
                    "(email, categoria, desde y, si quiere, hasta, jornada, nota y unidad)."]
    personas, n = {}, 0
    for linea, registro in enumerate(lector, start=2):
        if not any(c.strip() for c in registro):
            continue
        n += 1
        if n > MAX_FILAS:
            return [], [f"Se procesan hasta {MAX_FILAS} filas; divida el archivo."]

        def celda(campo):
            i = indice[campo]
            return registro[i].strip() if i is not None and i < len(registro) else ""

        email = celda("email").lower()
        sigla = celda("unidad").upper() or unidades.INSTITUTO
        p = personas.setdefault((email, sigla), {"email": email, "unidad": sigla, "periodos": [], "errores": []})
        cat, desde, hasta = _categoria(celda("categoria")), _fecha(celda("desde")), _fecha(celda("hasta"))
        jornada = celda("jornada")
        problemas = []
        if not cat:
            problemas.append("categoría no válida")
        if desde is False or hasta is False:
            problemas.append("fecha no válida (use AAAA-MM-DD o DD/MM/AAAA)")
        elif not desde:
            problemas.append("falta la fecha de inicio")
        elif hasta and hasta < desde:
            problemas.append("el término es anterior al inicio")
        if jornada and not (jornada.isdigit() and 1 <= int(jornada) <= 60):
            problemas.append("jornada: horas semanales entre 1 y 60")
        if problemas:
            p["errores"].append(f"Fila {linea}: " + "; ".join(problemas) + ".")
        else:
            p["periodos"].append({"linea": linea, "categoria": cat, "desde": desde, "hasta": hasta,
                                  "jornada": int(jornada) if jornada else None, "nota": celda("nota") or None})
    if not personas:
        return [], ["El archivo no tiene filas con datos."]
    for p in personas.values():
        if p["unidad"] not in unidades.CON_VINCULO:
            p["errores"].insert(0, f"Unidad no válida: {p['unidad']} (use {' o '.join(unidades.CON_VINCULO)}).")
            p["usuario"], p["unidad_id"], p["actuales"] = None, None, 0
            continue
        p["unidad_id"] = unidades.id_de(p["unidad"])
        u = usuarios.por_email(p["email"])
        perfil = usuarios.con_perfil(u["id"]) if u else None
        if not perfil or not perfil["es_investigador"]:
            p["errores"].insert(0, "No hay una cuenta de investigador con ese correo.")
            p["usuario"], p["actuales"] = None, 0
            continue
        p["usuario"] = perfil
        p["actuales"] = len(vinculos.listar(u["id"], p["unidad_id"]))
        p["periodos"].sort(key=lambda x: x["desde"])
        for a, b in zip(p["periodos"], p["periodos"][1:]):
            if not a["hasta"] or a["hasta"] >= b["desde"]:
                p["errores"].append(f"Filas {a['linea']} y {b['linea']}: los periodos se superponen "
                                    "(o uno sin término no es el último).")
    return sorted(personas.values(), key=lambda p: (p["email"], p["unidad"])), []


def aplicar(personas: list[dict], admin_id: int) -> int:
    """Reemplaza el historial de las personas sin errores. → cuántas se actualizaron."""
    n = 0
    for p in personas:
        if p["errores"] or not p["usuario"]:
            continue
        vinculos.reemplazar_historial(p["usuario"]["id"], p["periodos"], admin_id, p["unidad_id"])
        n += 1
    if n:
        auditar(admin_id, "importar_vinculos", "investigador", None, f"{n} persona(s)")
    return n
