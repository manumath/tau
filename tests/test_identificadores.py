import pytest

from app.investigacion.identificadores import (digito_control_orcid, normalizar_arxiv, normalizar_mr,
                                               normalizar_orcid, normalizar_scholar, normalizar_todos,
                                               normalizar_url, normalizar_zbmath)


@pytest.mark.parametrize("entrada", [
    "0000-0002-1825-0097", "https://orcid.org/0000-0002-1825-0097", "orcid.org/0000000218250097",
    " 0000 0002 1825 0097 ",
])
def test_orcid_formas_validas(entrada):
    assert normalizar_orcid(entrada) == "0000-0002-1825-0097"


def test_orcid_con_x_como_verificador():
    assert digito_control_orcid("000000021694233") == "X"
    assert normalizar_orcid("0000-0002-1694-233x") == "0000-0002-1694-233X"


@pytest.mark.parametrize("entrada,mensaje", [
    ("0000-0002-1825-0098", "dígito verificador"), ("1234", "forma"), ("abcd-efgh-ijkl-mnop", "forma"),
])
def test_orcid_invalido(entrada, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        normalizar_orcid(entrada)


def test_mathscinet():
    assert normalizar_mr("123456") == "123456"
    assert normalizar_mr("MR123456") == "123456"
    assert normalizar_mr("https://mathscinet.ams.org/mathscinet/MRAuthorID/98765") == "98765"
    with pytest.raises(ValueError):
        normalizar_mr("noether")


def test_zbmath():
    assert normalizar_zbmath("Noether.Emmy") == "noether.emmy"
    assert normalizar_zbmath("https://zbmath.org/authors/?q=ai:noether.emmy") == "noether.emmy"
    assert normalizar_zbmath("https://zbmath.org/authors/noether.emmy") == "noether.emmy"
    assert normalizar_zbmath("ai:ramanujan.srinivasa-aiyangar") == "ramanujan.srinivasa-aiyangar"
    with pytest.raises(ValueError):
        normalizar_zbmath("emmy")


def test_arxiv():
    assert normalizar_arxiv("https://arxiv.org/a/turing_a_1") == "turing_a_1"
    assert normalizar_arxiv("arxiv.org/a/Turing_A_1.html") == "turing_a_1"
    with pytest.raises(ValueError):
        normalizar_arxiv("alan turing")


def test_scholar():
    esperado = "https://scholar.google.com/citations?user=AbC-123_xyz0"
    assert normalizar_scholar("https://scholar.google.es/citations?hl=es&user=AbC-123_xyz0") == esperado
    assert normalizar_scholar("AbC-123_xyz0") == esperado
    with pytest.raises(ValueError):
        normalizar_scholar("https://example.com")


def test_url():
    assert normalizar_url("www.instituto.cl/~emmy") == "https://www.instituto.cl/~emmy"
    with pytest.raises(ValueError):
        normalizar_url("no es una url")


def test_normalizar_todos_reporta_errores_por_campo():
    valores, errores = normalizar_todos({"orcid": "https://orcid.org/0000-0002-1825-0097",
                                         "mr_id": "abc", "zbmath_id": ""})
    assert valores["orcid"] == "0000-0002-1825-0097"
    assert valores["zbmath_id"] is None
    assert list(errores) == ["mr_id"] and valores["mr_id"] == "abc"  # conserva lo tipeado
