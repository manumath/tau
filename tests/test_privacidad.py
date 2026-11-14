"""Aviso de privacidad (PLAN §72, etapa 8): la página pública y el aviso de cada formulario con datos personales."""
import importlib
import inspect

from app.comun import privacidad
from app.comun.componentes.layout import aviso_privacidad
from tests.conftest import HX, PASS_TEMP, login


def test_todo_formulario_con_datos_personales_lleva_su_aviso():
    for modulo, clave in privacidad.FORMULARIOS:
        assert clave in privacidad.TRATAMIENTOS, clave
        fuente = inspect.getsource(importlib.import_module(modulo))
        assert f'aviso_privacidad("{clave}")' in fuente, f"{modulo} no muestra el aviso «{clave}»"


def test_cada_tratamiento_esta_completo():
    for clave, t in privacidad.TRATAMIENTOS.items():
        assert all(len(x) > 20 for x in (t.datos, t.finalidad, t.quien_ve, t.conservacion, t.aviso)), clave
        assert t.aviso.endswith(".") and len(t.aviso) < 260, clave       # una frase breve sobre el botón


def test_el_aviso_enlaza_a_su_seccion():
    html = str(aviso_privacidad("buzon"))
    assert 'data-aviso="privacidad"' in html and 'href="/publico/privacidad#buzon"' in html


def test_pagina_publica_sin_sesion(client):
    r = client.get("/publico/privacidad")
    assert r.status_code == 200
    for clave, t in privacidad.TRATAMIENTOS.items():
        assert f'id="{clave}"' in r.text and t.titulo in r.text
    assert "Dirección de Carrera" in r.text


def test_el_formulario_del_perfil_muestra_el_aviso(client):
    from app.comun import usuarios
    uid = usuarios.por_email("inv@test.cl")["id"]
    usuarios.cambiar_password(uid, PASS_TEMP, temporal=False)
    login(client, "inv@test.cl", PASS_TEMP)
    r = client.get("/perfil/datos/editar", headers=HX)
    assert r.status_code == 200 and 'data-aviso="privacidad"' in r.text
