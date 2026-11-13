"""Malla de un plan en elaboración: asignaturas por semestre, electivas, ciclos y la lista de verificación (PLAN §65,
etapa 3). Solo se edita un plan en elaboración; `verificar` dice qué falta para ponerlo en vigencia."""
import csv
import io
import re

from app.academico import importar_planes, menciones, planes
from app.comun.db import auditar, get_db, transaccion

SIGLA = re.compile(r"^[A-Z]{2,4}-\d{3}$")
DEPARTAMENTO_PROPIO = importar_planes.DEPARTAMENTO_PROPIO
# Tipos que se eligen al agregar una fila, con el texto que ve quien elabora el plan.
TIPOS_FILA = {"obligatoria": "Obligatoria", "trabajo_final": "Trabajo final",
              "casilla_electiva_a": "Casilla de electiva A (se llena con una electiva)",
              "casilla_electiva_b": "Casilla de electiva B (se llena con una electiva)",
              "casilla_electiva": "Casilla de electiva (se llena con una electiva)",
              "electiva_a": "Electiva A (lista de electivas)", "electiva_b": "Electiva B (lista de electivas)",
              "electiva": "Electiva (lista de electivas)"}
COLUMNAS_CSV = ["sigla", "nombre", "tipo", "semestre", "ciclo", "horas_teoricas", "horas_practicas",
                "horas_laboratorio", "creditos", "requisitos"]
MAX_SEMESTRES = 20


def es_casilla(tipo): return tipo.startswith("casilla")
def es_lista(tipo): return tipo in planes.GRUPOS_ELECTIVAS


def _num(texto, etiqueta, errores, maximo=99):
    texto = (texto or "").strip()
    if not texto:
        return None
    if not texto.isdigit() or int(texto) > maximo:
        errores.append(f"{etiqueta}: debe ser un número entre 0 y {maximo}.")
        return None
    return int(texto)


# --- Ciclos ---------------------------------------------------------------------------------------------------------

def ciclos(pid: int) -> list[dict]:
    return get_db().q("SELECT * FROM plan_ciclo WHERE plan_id = ? ORDER BY semestre_desde", [pid])


def _sincronizar_ciclos(pid: int) -> None:
    """El ciclo de cada fila sale del semestre; las electivas (sin semestre) no tienen ciclo."""
    db = get_db()
    db.execute("UPDATE plan_asignatura SET ciclo = NULL WHERE plan_id = ?", [pid])
    for c in ciclos(pid):
        db.execute("UPDATE plan_asignatura SET ciclo = ? WHERE plan_id = ? AND semestre BETWEEN ? AND ?",
                   [c["nombre"], pid, c["semestre_desde"], c["semestre_hasta"]])


def guardar_ciclos(pid: int, filas: list[dict], uid: int) -> list[str]:
    """Reemplaza los ciclos del plan. `filas`: [{nombre, desde, hasta}]; las filas sin nombre se ignoran."""
    p = planes.obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return ["Solo se editan los ciclos de un plan en elaboración."]
    errores, listos = [], []
    for f in filas:
        nombre = (f.get("nombre") or "").strip()
        if not nombre:
            continue
        desde, hasta = _num(f.get("desde"), f"Ciclo «{nombre}», desde", errores, MAX_SEMESTRES), \
            _num(f.get("hasta"), f"Ciclo «{nombre}», hasta", errores, MAX_SEMESTRES)
        if desde is None or hasta is None or hasta < desde:
            errores.append(f"Ciclo «{nombre}»: indique el semestre en que empieza y el en que termina.")
            continue
        listos.append((nombre, desde, hasta))
    nombres = [n.lower() for n, _, _ in listos]
    if len(set(nombres)) != len(nombres):
        errores.append("Dos ciclos tienen el mismo nombre.")
    ordenados = sorted(listos, key=lambda x: x[1])
    if any(b[1] <= a[2] for a, b in zip(ordenados, ordenados[1:])):
        errores.append("Los ciclos no pueden compartir semestres.")
    if errores:
        return errores
    with transaccion():
        get_db().execute("DELETE FROM plan_ciclo WHERE plan_id = ?", [pid])
        for nombre, desde, hasta in listos:
            get_db().t.plan_ciclo.insert(plan_id=pid, nombre=nombre, semestre_desde=desde, semestre_hasta=hasta)
        _sincronizar_ciclos(pid)
        auditar(uid, "editar_ciclos_plan", "plan_estudios", pid, ", ".join(f"{n} ({d}-{h})" for n, d, h in listos))
    return []


# --- Filas de la malla ----------------------------------------------------------------------------------------------

def fila(fid: int) -> dict | None:
    filas = get_db().q("""SELECT pa.*, a.sigla, a.nombre, a.linea_formativa FROM plan_asignatura pa
                          LEFT JOIN asignatura a ON a.id = pa.asignatura_id WHERE pa.id = ?""", [fid])
    if not filas:
        return None
    f = filas[0]
    f["requisitos"] = [r["sigla"] for r in get_db().q(
        "SELECT sigla FROM requisito WHERE plan_asignatura_id = ? AND sigla IS NOT NULL ORDER BY id", [fid])]
    f["egresado"] = bool(get_db().q("SELECT 1 FROM requisito WHERE plan_asignatura_id = ? AND condicion = 'egresado'",
                                    [fid]))
    return f


def siglas_del_plan(pid: int, excepto: int | None = None) -> list[dict]:
    return get_db().q("""SELECT pa.id, a.sigla, a.nombre, pa.semestre FROM plan_asignatura pa
                         JOIN asignatura a ON a.id = pa.asignatura_id WHERE pa.plan_id = ? AND pa.id <> ?
                         ORDER BY COALESCE(pa.semestre, 99), pa.orden""", [pid, excepto or 0])


def guardar_fila(pid: int, fid: int | None, f: dict, requisitos: list[str], uid: int) -> list[str]:
    """Agrega (fid vacío) o modifica una asignatura, casilla o electiva del plan. → errores."""
    db = get_db()
    p = planes.obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return ["Solo se edita la malla de un plan en elaboración."]
    actual = fila(fid) if fid else None
    if fid and (not actual or actual["plan_id"] != pid):
        return ["La asignatura no está en este plan."]
    errores = []
    tipo = f.get("tipo")
    if tipo not in TIPOS_FILA:
        return ["Elija el tipo."]
    duracion = p["duracion_semestres"] or MAX_SEMESTRES
    semestre = None
    if not es_lista(tipo):
        semestre = _num(f.get("semestre"), "Semestre", errores, MAX_SEMESTRES)
        if semestre is None or semestre < 1:
            errores.append("Indique el semestre (1 en adelante).")
        elif p["duracion_semestres"] and semestre > duracion:
            errores.append(f"El plan dura {duracion} semestres: cambie la duración en los datos generales para "
                           f"agregar el semestre {semestre}.")
    sigla = (f.get("sigla") or "").strip().upper()
    nombre = (f.get("nombre") or "").strip()
    asignatura = None
    if es_casilla(tipo):
        sigla = ""
    elif not SIGLA.match(sigla):
        errores.append("La sigla debe ser como «MAT-111»: letras del departamento, guion y tres cifras.")
    else:
        cat = db.q("SELECT * FROM asignatura WHERE sigla = ?", [sigla])
        if cat:
            asignatura = cat[0]["id"]
            if nombre and nombre != cat[0]["nombre"]:
                errores.append(f"La sigla {sigla} ya existe en el catálogo como «{cat[0]['nombre']}»: deje el nombre en "
                               "blanco para usarlo.")
        elif not nombre or len(nombre) > 150:
            errores.append(f"{sigla} es una sigla nueva: escriba su nombre (hasta 150 caracteres).")
        if db.q("SELECT 1 FROM plan_asignatura pa JOIN asignatura a ON a.id = pa.asignatura_id "
                "WHERE pa.plan_id = ? AND a.sigla = ? AND pa.id <> ?", [pid, sigla, fid or 0]):
            errores.append(f"{sigla} ya está en este plan.")
    medidas = {}
    if p["sistema"] == "creditos":
        medidas["creditos"] = _num(f.get("creditos"), "Créditos", errores)
    else:
        for c, t in (("horas_teoricas", "Horas teóricas"), ("horas_practicas", "Horas prácticas"),
                     ("horas_laboratorio", "Horas de laboratorio")):
            medidas[c] = _num(f.get(c), t, errores)
    en_plan = {s["sigla"] for s in siglas_del_plan(pid, fid)}
    reqs = [r for r in dict.fromkeys(requisitos) if r]
    if any(r not in en_plan or r == sigla for r in reqs):
        errores.append("Un requisito no está en el plan o es la misma asignatura.")
    if errores:
        return errores
    with transaccion():
        if sigla and asignatura is None:
            depto = sigla.split("-")[0]
            asignatura = db.t.asignatura.insert(sigla=sigla, nombre=nombre, departamento=depto,
                                                de_la_carrera=int(depto == DEPARTAMENTO_PROPIO),
                                                linea_formativa=(f.get("linea_formativa") or "").strip() or None)["id"]
        valores = {"asignatura_id": asignatura, "tipo": tipo, "semestre": semestre, "creditos": None,
                   "horas_teoricas": None, "horas_practicas": None, "horas_laboratorio": None} | medidas
        if fid:
            db.t.plan_asignatura.update(id=fid, **valores)
        else:
            orden = db.q("SELECT COALESCE(MAX(orden), -1) + 1 AS o FROM plan_asignatura WHERE plan_id = ?", [pid])[0]["o"]
            fid = db.t.plan_asignatura.insert(plan_id=pid, orden=orden, **valores)["id"]
        db.execute("DELETE FROM requisito WHERE plan_asignatura_id = ?", [fid])
        for r in reqs:
            db.t.requisito.insert(plan_asignatura_id=fid, sigla=r)
        if f.get("egresado"):
            db.t.requisito.insert(plan_asignatura_id=fid, condicion="egresado")
        _sincronizar_ciclos(pid)
        auditar(uid, "editar_malla_plan", "plan_estudios", pid,
                f"{'Modificó' if actual else 'Agregó'} {sigla or planes.TIPOS[tipo]}"
                + (f" (semestre {semestre})" if semestre else ""))
    return []


def quitar_fila(pid: int, fid: int, uid: int) -> int | None:
    """Quita la fila del plan. → cuántas otras filas la tenían como requisito (quedan marcadas), o None si no se puede."""
    p = planes.obtener(pid)
    actual = fila(fid)
    if not p or p["estado"] != "elaboracion" or not actual or actual["plan_id"] != pid:
        return None
    with transaccion():
        db = get_db()
        huerfanas = 0
        if actual["sigla"]:
            huerfanas = db.q("""SELECT COUNT(DISTINCT pa.id) n FROM requisito r JOIN plan_asignatura pa
                                ON pa.id = r.plan_asignatura_id WHERE pa.plan_id = ? AND r.sigla = ?""",
                             [pid, actual["sigla"]])[0]["n"]
        db.execute("DELETE FROM plan_asignatura WHERE id = ?", [fid])
        auditar(uid, "editar_malla_plan", "plan_estudios", pid, f"Quitó {actual['sigla'] or planes.TIPOS[actual['tipo']]}")
    return huerfanas


# --- CSV de un plan -------------------------------------------------------------------------------------------------

def leer_csv(texto: str, sistema: str) -> tuple[list[dict], list[str]]:
    """Filas del CSV de un plan (mismo formato que datos/planes/*.csv) o los errores que impiden cargarlo."""
    lector = csv.DictReader(io.StringIO(texto.lstrip("﻿")))
    faltan = [c for c in COLUMNAS_CSV if c not in (lector.fieldnames or [])]
    if faltan:
        return [], [f"Faltan columnas: {', '.join(faltan)}. Descargue la plantilla."]
    filas, errores = [], []
    vistas = set()
    for n, f in enumerate(lector, start=2):
        f = {k: (v or "").strip() for k, v in f.items() if k}
        if not any(f.values()):
            continue
        e = len(errores)
        if f["tipo"] not in TIPOS_FILA:
            errores.append(f"Fila {n}: el tipo «{f['tipo']}» no es válido.")
        elif es_casilla(f["tipo"]) != (not f["sigla"]):
            errores.append(f"Fila {n}: una casilla de electiva no lleva sigla y las demás sí.")
        if f["sigla"] and not SIGLA.match(f["sigla"]):
            errores.append(f"Fila {n}: la sigla «{f['sigla']}» no tiene el formato MAT-111.")
        elif f["sigla"] and not f["nombre"] and not get_db().q("SELECT 1 FROM asignatura WHERE sigla = ?", [f["sigla"]]):
            errores.append(f"Fila {n}: {f['sigla']} es nueva y necesita nombre.")
        if f["sigla"] in vistas:
            errores.append(f"Fila {n}: {f['sigla']} está repetida.")
        vistas.add(f["sigla"])
        for c in ("semestre", "horas_teoricas", "horas_practicas", "horas_laboratorio", "creditos"):
            if f[c] and not f[c].isdigit():
                errores.append(f"Fila {n}: {c} debe ser un número.")
        if f["tipo"] in TIPOS_FILA and not es_lista(f["tipo"]) and not f["semestre"]:
            errores.append(f"Fila {n}: falta el semestre.")
        if sistema == "creditos" and any(f[c] for c in ("horas_teoricas", "horas_practicas", "horas_laboratorio")):
            errores.append(f"Fila {n}: el plan se mide en créditos y la fila trae horas.")
        if sistema == "horas" and f["creditos"]:
            errores.append(f"Fila {n}: el plan se mide en horas y la fila trae créditos.")
        if len(errores) == e:
            filas.append(f)
    return filas, errores[:30]


def importar_csv(pid: int, texto: str, uid: int) -> tuple[int, list[str]]:
    """Reemplaza la malla del plan en elaboración por la del CSV. → (filas cargadas, errores)."""
    p = planes.obtener(pid)
    if not p or p["estado"] != "elaboracion":
        return 0, ["Solo se carga la malla de un plan en elaboración."]
    filas, errores = leer_csv(texto, p["sistema"])
    if not errores and not filas:
        errores = ["El archivo no tiene filas."]
    if errores:
        return 0, errores
    with transaccion():
        db = get_db()
        db.execute("DELETE FROM plan_asignatura WHERE plan_id = ?", [pid])
        db.execute("DELETE FROM observacion_plan WHERE plan_id = ? AND tipo IN ('nombre', 'duplicada')", [pid])
        importar_planes.cargar_filas(db.conn, pid, filas)
        db.execute("UPDATE plan_estudios SET duracion_semestres = ? WHERE id = ?",
                   [max([int(f["semestre"]) for f in filas if f["semestre"]] + [p["duracion_semestres"] or 0]), pid])
        _sincronizar_ciclos(pid)
        auditar(uid, "importar_malla_plan", "plan_estudios", pid, f"{len(filas)} filas de un CSV")
    return len(filas), []


def plantilla_csv() -> str:
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(COLUMNAS_CSV)
    w.writerow(["MAT-111", "Álgebra I", "obligatoria", "1", "", "4", "2", "", "", ""])
    w.writerow(["MAT-131", "Álgebra II", "obligatoria", "2", "", "4", "2", "", "", "MAT-111"])
    w.writerow(["", "", "casilla_electiva_a", "5", "", "4", "2", "", "", ""])
    w.writerow(["MAT-392", "Una electiva", "electiva_a", "", "", "4", "2", "", "", "MAT-131"])
    return salida.getvalue()


# --- Lista de verificación ------------------------------------------------------------------------------------------

def _hay_ciclo(grafo: dict[str, list[str]]) -> list[str] | None:
    estado, camino = {}, []

    def visita(n):
        estado[n] = 1
        camino.append(n)
        for m in grafo.get(n, []):
            if estado.get(m) == 1:
                return camino[camino.index(m):] + [m]
            if m in grafo and not estado.get(m):
                r = visita(m)
                if r:
                    return r
        estado[n] = 2
        camino.pop()
        return None
    for n in grafo:
        if not estado.get(n):
            r = visita(n)
            if r:
                return r
    return None


def verificar(pid: int) -> list[dict]:
    """Lo que falta para poner el plan en vigencia: [{clave, texto, nivel, detalle}] con nivel 'ok', 'falta' (impide
    ponerlo en vigencia) o 'aviso' (conviene revisar, no lo impide)."""
    p = planes.obtener(pid)
    filas = planes.asignaturas(pid)
    res = []

    def punto(clave, texto, nivel, detalle=""):
        res.append({"clave": clave, "texto": texto, "nivel": nivel, "detalle": detalle})

    falta = []
    if not p["resolucion"]:
        falta.append("la resolución")
    if not p["duracion_semestres"]:
        falta.append("la duración en semestres")
    if p["sistema"] == "horas" and not p["semanas_semestre"]:
        falta.append("las semanas del semestre")
    if p["sistema"] == "creditos" and not p["horas_por_credito"]:
        falta.append("las horas por crédito")
    punto("datos", "Datos generales completos", "falta" if falta else "ok",
          f"Falta registrar {', '.join(falta)}." if falta else "")
    punto("malla", "El plan tiene asignaturas", "ok" if any(f["sigla"] for f in filas) else "falta",
          "" if any(f["sigla"] for f in filas) else "Agregue asignaturas o cargue un CSV.")
    malas = [f["sigla"] for f in filas if f["sigla"] and not SIGLA.match(f["sigla"])]
    punto("siglas", "Siglas con formato válido", "falta" if malas else "ok", ", ".join(malas))
    en_plan = {f["sigla"] for f in filas if f["sigla"]}
    inexistentes = sorted({f"{r} (pedido por {f['sigla'] or planes.TIPOS[f['tipo']]})"
                           for f in filas for r in f["requisitos"] if r != "Egresado" and r not in en_plan})
    punto("requisitos", "Todo requisito está en el plan", "falta" if inexistentes else "ok", "; ".join(inexistentes[:5]))
    grafo = {f["sigla"]: [r for r in f["requisitos"] if r != "Egresado"] for f in filas if f["sigla"]}
    ciclo = _hay_ciclo(grafo)
    punto("ciclos_requisitos", "Sin requisitos circulares", "falta" if ciclo else "ok",
          " → ".join(ciclo) if ciclo else "")
    vacios = []
    if p["duracion_semestres"]:
        usados = {f["semestre"] for f in filas if f["semestre"]}
        vacios = [str(s) for s in range(1, p["duracion_semestres"] + 1) if s not in usados]
        fuera = sorted(s for s in usados if s > p["duracion_semestres"])
        if fuera:
            vacios += [f"{s} (fuera de la duración)" for s in fuera]
    punto("semestres", "Todos los semestres tienen asignaturas", "falta" if vacios else "ok",
          f"Semestres sin asignaturas o fuera de la duración: {', '.join(vacios)}." if vacios else "")
    sin_lista = sorted({f["tipo"] for f in filas if es_casilla(f["tipo"])
                        and not any(g["tipo"] == f["tipo"].replace("casilla_", "") for g in filas)})
    punto("electivas", "Cada casilla de electiva tiene su lista", "falta" if sin_lista else "ok",
          ", ".join(planes.TIPOS[t] for t in sin_lista))
    if p["sistema"] == "creditos":
        sin_medida = [f for f in filas if not f["creditos"]]
    else:
        sin_medida = [f for f in filas if not any((f["horas_teoricas"], f["horas_practicas"], f["horas_laboratorio"]))]
    punto("medida", "Horas o créditos en cada fila", "falta" if sin_medida else "ok",
          ", ".join(f["sigla"] or planes.TIPOS[f["tipo"]] for f in sin_medida[:6]) + ("…" if len(sin_medida) > 6 else ""))
    desiguales = [k for k, (d, c) in planes.totales(pid).items() if d is not None and d != c]
    punto("totales", "Los totales declarados cuadran con la suma", "aviso" if desiguales else "ok",
          f"No coinciden: {', '.join(desiguales)}." if desiguales else "")
    men = menciones.verificar(pid)
    if men:
        res.append(men)
    pendientes = get_db().q("SELECT COUNT(*) n FROM observacion_plan WHERE plan_id = ? AND estado = 'pendiente'", [pid])[0]["n"]
    punto("observaciones", "Observaciones resueltas", "aviso" if pendientes else "ok",
          f"{pendientes} por revisar." if pendientes else "")
    return res


def listo_para_vigencia(pid: int) -> bool:
    return not any(v["nivel"] == "falta" for v in verificar(pid))

