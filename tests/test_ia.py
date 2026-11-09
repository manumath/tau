"""IA con criterio humano, etapa 0a (PLAN §59): cada principio no negociable y el anexo A tienen su prueba.
Ninguna prueba sale a la red: `servicio._enviar` se reemplaza por un proveedor falso que guarda lo que recibiría."""
from pathlib import Path

import pytest

from app.comun import config
from app.comun.db import get_db
from app.ia import clasificacion, funciones, servicio
from app.ia.funciones import Funcion

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def ia(app, monkeypatch, tmp_path):
    """Una función de prueba activa, instrucciones en una carpeta temporal y un proveedor falso."""
    (tmp_path / "prueba").mkdir()
    (tmp_path / "prueba" / "v1.md").write_text("Versión antigua.")
    (tmp_path / "prueba" / "v2.md").write_text("Redacte en español sin inventar cifras.")
    monkeypatch.setattr(servicio, "DIR_INSTRUCCIONES", tmp_path)
    for nombre, valor in {"IA_LOCAL_URL": "http://local.test/v1", "IA_LOCAL_MODELO": "modelo-local",
                          "IA_EXT_URL": "https://externo.test/v1", "IA_EXT_MODELO": "modelo-externo",
                          "IA_EXT_CLAVE": "clave-de-prueba", "IA_EXT_ZDR": True}.items():
        monkeypatch.setattr(config, nombre, valor)
    llamadas, respuestas = [], {}

    def falso(url, cabeceras, datos, tiempo):
        llamadas.append({"url": url, "cabeceras": cabeceras, "datos": datos})
        r = respuestas.get(url, "Borrador sobre [PERSONA_1] y la línea.")
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(servicio, "_enviar", falso)
    monkeypatch.setattr(funciones, "FUNCIONES", {})
    uid = get_db().q("SELECT id FROM usuario ORDER BY id LIMIT 1")[0]["id"]
    otro = get_db().q("SELECT id FROM usuario ORDER BY id LIMIT 1 OFFSET 1")[0]["id"]

    def registrar(**kw):
        datos = dict(clave="prueba", nombre="Función de prueba", modulo="investigacion", descripcion="",
                     nivel_max=clasificacion.PERSONAL, revisor="la Dirección del Instituto",
                     puede_pedir=lambda a, e=None: True)
        return funciones.registrar(Funcion(**{**datos, **kw}))
    registrar()
    servicio.crear_politica("Política de prueba.", uid)
    servicio.aprobar_politica(servicio.politicas()[0]["id"], uid)
    assert servicio.activar("prueba", uid, uid) is None
    return {"llamadas": llamadas, "respuestas": respuestas, "auth": {"id": uid}, "otro": {"id": otro},
            "registrar": registrar}


def _auditoria(accion):
    return get_db().q("SELECT * FROM auditoria WHERE accion = ?", [accion])


# --- Principio 6: apagado por defecto -------------------------------------------------------------------------------

def test_todo_nace_apagado_y_activar_exige_politica_y_responsable(app, monkeypatch):
    monkeypatch.setattr(funciones, "FUNCIONES", {})
    funciones.registrar(Funcion(clave="x", nombre="X", modulo="investigacion", descripcion="", nivel_max=0,
                                revisor="", puede_pedir=lambda a, e=None: True))
    assert get_db().q("SELECT * FROM ia_funcion") == [] and not servicio.activa("x")
    uid = get_db().q("SELECT id FROM usuario LIMIT 1")[0]["id"]
    with pytest.raises(servicio.IANoDisponible):
        servicio.generar("x", [("producto.titulo", "Un título")], {"id": uid})
    assert "política de uso" in servicio.activar("x", uid, uid)
    pid, _ = servicio.crear_politica("Texto.", uid)
    assert servicio.politica_vigente() is None  # una versión nueva no rige hasta aprobarla
    servicio.aprobar_politica(pid, uid)
    assert servicio.activar("x", None, uid) == "Designe a la persona responsable de la función."
    assert servicio.activar("x", uid, uid) is None and servicio.activa("x")
    servicio.desactivar("x", uid)
    assert not servicio.activa("x")
    assert [a["accion"] for a in get_db().q("SELECT accion FROM auditoria WHERE accion LIKE 'ia_%' ORDER BY id")] == [
        "ia_crear_politica", "ia_aprobar_politica", "ia_activar", "ia_desactivar"]


def test_nuevas_versiones_de_la_politica(ia):
    uid = ia["auth"]["id"]
    pid, _ = servicio.crear_politica("Versión 2.", uid)
    assert servicio.politica_vigente()["version"] == 1
    servicio.aprobar_politica(pid, uid)
    assert servicio.politica_vigente()["version"] == 2
    assert servicio.aprobar_politica(pid, uid) == "Esa versión ya fue aprobada."
    assert servicio.crear_politica("  ", uid) == (None, "Escriba el texto de la política.")


# --- Principio 2: módulos vedados -----------------------------------------------------------------------------------

def test_no_se_registra_una_funcion_de_un_modulo_vedado(ia):
    with pytest.raises(ValueError, match="calificación y fases de auxiliaturas"):
        ia["registrar"](clave="nota", modulo="auxiliaturas")


def test_invocar_desde_un_modulo_vedado_falla_y_queda_auditado(ia):
    # El código se ejecuta como si estuviera en app/servicios/auxiliaturas.py.
    codigo = compile('servicio.generar("prueba", [("producto.titulo", "T")], auth)',
                     str(RAIZ / "app/servicios/auxiliaturas.py"), "exec")
    with pytest.raises(servicio.IABloqueada):
        exec(codigo, {"servicio": servicio, "auth": ia["auth"]})
    assert "app/servicios/auxiliaturas.py" in _auditoria("ia_bloqueada")[0]["detalle"]
    # Una función de un módulo vedado que se colara en el catálogo tampoco se ejecuta.
    funciones.FUNCIONES["colada"] = Funcion(clave="colada", nombre="", modulo="tutoria", descripcion="", nivel_max=0,
                                            revisor="", puede_pedir=lambda a, e=None: True)
    with pytest.raises(servicio.IABloqueada):
        servicio.generar("colada", [("producto.titulo", "T")], ia["auth"])
    assert ia["llamadas"] == [] and get_db().q("SELECT * FROM ia_uso") == []


def test_los_modulos_vedados_no_importan_la_ia():
    for rel in servicio.ARCHIVOS_VEDADOS:
        texto = (RAIZ / rel).read_text(encoding="utf-8")
        assert "app.ia" not in texto and "from app import ia" not in texto, rel


# --- Principio 3: datos sensibles y clasificación --------------------------------------------------------------------

def test_datos_sensibles_o_sin_clasificar_se_rechazan(ia):
    for origen in ("datos_personales.fecha_nacimiento", "tutoria_reunion.notas", "respuesta.texto_anonimo",
                   "usuario.email"):
        with pytest.raises(servicio.IADatosNoPermitidos):
            servicio.generar("prueba", [("producto.titulo", "T"), (origen, "x")], ia["auth"])
    assert len(_auditoria("ia_datos_rechazados")) == 4
    with pytest.raises(ValueError, match="sin clasificar"):
        servicio.generar("prueba", [("usuario.telefono_nuevo", "x")], ia["auth"])
    ia["registrar"](nivel_max=clasificacion.INTERNO)
    with pytest.raises(servicio.IADatosNoPermitidos):  # nivel 2 en una función que admite hasta el 1
        servicio.generar("prueba", [("investigador.bio", "x")], ia["auth"])
    assert ia["llamadas"] == []


def test_seudonimizacion_los_nombres_no_salen_y_se_restituyen(ia):
    ia["registrar"](seudonimizar=True)
    uso = servicio.generar("prueba", [("persona.nombre", "Emmy Noether"),
                                      ("investigador.bio", "Emmy Noether trabajó en álgebra; Noether es conocida.")],
                           ia["auth"])
    enviado = str(ia["llamadas"][0]["datos"])
    assert "Emmy" not in enviado and "Noether" not in enviado and "[PERSONA_1]" in enviado
    assert ia["llamadas"][0]["url"] == "https://externo.test/v1"  # nivel 2 seudonimizado puede ir afuera
    assert servicio.obtener(uso)["texto_generado"] == "Borrador sobre Emmy Noether y la línea."
    assert servicio.obtener(uso)["seudonimizado"] == 1


# --- Principio 1: la persona decide ---------------------------------------------------------------------------------

def test_la_salida_no_surte_efecto_sin_decision_humana(ia):
    uso = servicio.generar("prueba", [("producto.titulo", "Grafos de Cayley")], ia["auth"])
    u = servicio.obtener(uso)
    assert (u["estado"], u["version_prompt"], u["proveedor"], u["modelo"]) == ("borrador_ia", 2, "externo", "modelo-externo")
    assert servicio.texto_aprobado(uso) is None and servicio.marca(u) == "Borrador generado con IA"
    assert ia["llamadas"][0]["datos"]["messages"][0]["content"] == "Redacte en español sin inventar cifras."
    # Solo quien corresponde decide; la decisión se registra con la distancia de edición y la valoración.
    assert servicio.decidir(uso, ia["otro"], "aprobar", "Texto") == ["No le corresponde revisar este borrador."]
    assert servicio.decidir(uso, ia["auth"], "aprobar", "") == ["El texto aprobado no puede quedar vacío."]
    assert servicio.decidir(uso, ia["auth"], "aprobar", "x", valoracion="7") == ["La valoración va de 1 a 5."]
    final = "Borrador sobre [PERSONA_1] y la línea de investigación."
    assert servicio.decidir(uso, ia["auth"], "aprobar", final, valoracion="4") == []
    u = servicio.obtener(uso)
    assert (u["estado"], u["valoracion"], u["texto_final"]) == ("editada", 4, final)
    assert 0 < u["distancia_edicion"] < 0.5 and servicio.texto_aprobado(uso) == final
    assert servicio.marca(u).startswith("Elaborado con apoyo de IA; revisado por la Dirección del Instituto, ")
    assert servicio.decidir(uso, ia["auth"], "rechazar") == ["Este borrador ya fue revisado o no está listo."]
    # Sin cambios: «aprobada» con distancia 0; rechazada: sin texto final.
    dos = servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"])
    servicio.decidir(dos, ia["auth"], "aprobar", servicio.obtener(dos)["texto_generado"])
    assert (servicio.obtener(dos)["estado"], servicio.obtener(dos)["distancia_edicion"]) == ("aprobada", 0)
    tres = servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"])
    servicio.decidir(tres, ia["auth"], "rechazar", motivo="No sirve.")
    assert servicio.texto_aprobado(tres) is None and servicio.obtener(tres)["motivo"] == "No sirve."


# --- Principio 5: trazabilidad ---------------------------------------------------------------------------------------

def test_cada_uso_queda_en_la_auditoria(ia):
    uso = servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"])
    servicio.decidir(uso, ia["auth"], "rechazar")
    acciones = [a["accion"] for a in get_db().q("SELECT accion FROM auditoria WHERE entidad = 'ia_uso' AND entidad_id = ?",
                                                 [uso])]
    assert acciones == ["ia_invocar", "ia_borrador", "ia_decision"]
    u = servicio.obtener(uso)
    assert len(u["hash_entrada"]) == 64 and u["nivel_datos"] == 0


# --- Anexo A: enrutamiento por nivel ---------------------------------------------------------------------------------

def test_sin_retencion_cero_no_sale_nada_al_externo(ia, monkeypatch):
    monkeypatch.setattr(config, "IA_EXT_ZDR", False)
    servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"])
    assert [x["url"] for x in ia["llamadas"]] == ["http://local.test/v1"]
    monkeypatch.setattr(config, "IA_LOCAL_URL", None)
    with pytest.raises(servicio.IANoDisponible, match="puede continuar manualmente"):
        servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"])


def test_cada_solicitud_externa_lleva_retencion_cero_y_su_clave(ia):
    servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"])
    externa = ia["llamadas"][0]
    assert externa["datos"]["provider"] == {"zdr": True}
    assert externa["cabeceras"] == {"Authorization": "Bearer clave-de-prueba"}


def test_nivel_2_sin_seudonimizar_nunca_va_al_externo(ia):
    servicio.generar("prueba", [("investigador.bio", "Trabajo en álgebra.")], ia["auth"])
    assert [x["url"] for x in ia["llamadas"]] == ["http://local.test/v1"]
    assert "provider" not in ia["llamadas"][0]["datos"]


def test_si_el_externo_falla_se_usa_el_local_y_si_todo_falla_queda_error(ia):
    ia["respuestas"]["https://externo.test/v1"] = TimeoutError("lento")
    uso = servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"])
    assert (servicio.obtener(uso)["proveedor"], servicio.obtener(uso)["modelo"]) == ("local", "modelo-local")
    ia["respuestas"]["http://local.test/v1"] = ConnectionError("caído")
    uso = servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"])
    u = servicio.obtener(uso)
    assert (u["estado"], u["texto_generado"]) == ("error", None) and "local" in u["error"]
    assert servicio.decidir(uso, ia["auth"], "aprobar", "x") == ["Este borrador ya fue revisado o no está listo."]


def test_una_funcion_solo_local_no_sale_aunque_el_nivel_lo_permita(ia):
    ia["registrar"](externa=False)
    servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"])
    assert [x["url"] for x in ia["llamadas"]] == ["http://local.test/v1"]


def test_en_segundo_plano_avisa_al_terminar(ia):
    import time
    uso = servicio.generar("prueba", [("producto.titulo", "T")], ia["auth"], en_fondo=True)
    for _ in range(100):
        if servicio.obtener(uso)["estado"] != "generando":
            break
        time.sleep(0.05)
    assert servicio.obtener(uso)["estado"] == "borrador_ia"
    assert get_db().q("SELECT 1 FROM notificacion WHERE usuario_id = ? AND asunto LIKE 'Borrador de IA listo%'",
                      [ia["auth"]["id"]])
