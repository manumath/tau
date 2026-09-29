"""Cargo y «unidad o grupo» de cada persona, calculados (PLAN.md, sección 27). No se escriben a mano.

- **Cargo:** «Docente Investigador» si su periodo de vínculo vigente tiene carga de investigación;
  «Docente» si tiene vínculo sin ella; nada si no tiene vínculo vigente.
- **Unidad o grupo**, en este orden y sin repetir:
  1. los proyectos vigentes de los que es responsable o co-responsable;
  2. los proyectos vigentes en que participa con otro rol;
  3. el detalle de «Extensión y servicios» de su vínculo vigente (si tiene horas de extensión);
  4. el detalle de «Gestión» (si tiene horas de gestión);
  si nada de eso aplica, «Carrera de Matemática».

Solo consulta tablas (proyectos y vínculos): `comun` no importa de los otros paquetes.
"""
from app.comun import unidades, vinculos
from app.comun.db import get_db

DOCENTE_INVESTIGADOR = "Docente Investigador"
DOCENTE = "Docente"
SEPARADOR = " · "


def cargo(uid: int) -> str | None:
    v = vinculos.vigente(uid)
    if not v:
        return None
    c = vinculos.carga_de(v)
    return DOCENTE_INVESTIGADOR if c and c["actividades"]["investigacion"] else DOCENTE


def grupos(uid: int) -> list[str]:
    hoy = vinculos.hoy().isoformat()
    proyectos = get_db().q(
        """SELECT p.nombre, pp.rol IN ('responsable', 'co_responsable') AS dirige FROM proyecto_participante pp
           JOIN proyecto p ON p.id = pp.proyecto_id
           WHERE pp.investigador_id = ? AND p.estado = 'vigente'
             AND (pp.fecha_hasta IS NULL OR pp.fecha_hasta >= ?)
           ORDER BY dirige DESC, p.nombre""", [uid, hoy])
    res = [x["nombre"] for x in proyectos]
    c = vinculos.carga_de(vinculos.vigente(uid))
    if c:
        for actividad in ("extension", "gestion"):
            if c["actividades"][actividad] and c["detalles"].get(actividad):
                res.append(c["detalles"][actividad])
    res = list(dict.fromkeys(res))  # sin repetir, conservando el orden
    return res or [unidades.obtener(unidades.id_de(unidades.CARRERA))["nombre"]]


def unidad(uid: int) -> str:
    return SEPARADOR.join(grupos(uid))


def completar(fila: dict, clave: str = "id") -> dict:
    """Agrega «cargo» y «unidad» calculados a una fila con el id de la persona."""
    fila["cargo"] = cargo(fila[clave])
    fila["unidad"] = unidad(fila[clave])
    return fila
