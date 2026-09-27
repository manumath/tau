"""«Mis datos personales»: lo que el instituto registra de cada persona (grados y fecha de nacimiento),
de solo lectura. Para quien no tiene perfil de investigación; los investigadores lo ven en «Mi perfil»."""
from fasthtml.common import A, APIRouter, Div, Li, P, Ul
from monsterui.all import H2, H3, Card, TextPresets

from app.comun import academicos
from app.comun.componentes import datos_personales
from app.comun.componentes.layout import pagina

rt = APIRouter()


@rt("/mis-datos")
def get(auth):
    grados = academicos.grados(auth["id"])
    return pagina(
        "Mis datos personales",
        H2("Mis datos personales"),
        P("Lo que el instituto registra de usted para la acreditación. Si algo no es correcto, pida a la "
          "administración que lo corrija.", cls=(TextPresets.muted_sm, "mb-6")),
        Div(Card(H3("Grados académicos", cls="text-base font-semibold mb-2"),
                 Ul(*[Li(academicos.texto_grado(g), cls="text-sm py-1") for g in grados]) if grados
                 else P("Sin grados registrados.", cls=TextPresets.muted_sm)),
            datos_personales.tarjeta(auth["id"]),
            (A("Ver «Mi perfil»", href="/perfil", cls="text-sm text-primary hover:underline")
             if auth["es_investigador"] else ""),
            cls="space-y-6 max-w-2xl"),
        usuario=auth)
