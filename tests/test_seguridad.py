import re

from app.seguridad import errores_password, hash_password, password_temporal, verificar_password


def test_hash_y_verificacion():
    h = hash_password("una-clave-larga-1")
    assert h.startswith("$argon2")
    assert verificar_password(h, "una-clave-larga-1")
    assert not verificar_password(h, "otra")
    assert not verificar_password(None, "cualquiera")
    assert not verificar_password("basura", "cualquiera")


def test_password_temporal_legible_y_unica():
    p = password_temporal()
    assert re.fullmatch(r"[A-Za-z2-9]{4}-[A-Za-z2-9]{4}-[A-Za-z2-9]{4}", p)
    assert not set(p) & set("0O1lI")
    assert len({password_temporal() for _ in range(50)}) == 50


def test_politica_de_password():
    assert errores_password("buena-clave-9", "buena-clave-9") == []
    assert any("10 caracteres" in e for e in errores_password("corta1", "corta1"))
    assert any("confirmación" in e for e in errores_password("buena-clave-9", "otra-clave-9"))
    assert any("distinta" in e for e in errores_password("misma-clave-1", "misma-clave-1",
                                                           actual="misma-clave-1"))
    assert any("letras con números" in e for e in errores_password("soloLetrasAqui", "soloLetrasAqui"))
