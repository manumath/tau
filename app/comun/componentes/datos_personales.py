"""Tarjeta «Datos personales» que cada persona ve de sí misma (en «Mi perfil» o en «Mis datos»)."""
from fasthtml.common import Div, P, Span
from monsterui.all import Card, H3, TextPresets, UkIcon

from app.comun import academicos

AVISO = ("El instituto registra su fecha de nacimiento para la acreditación (IAC-CINDA pide la distribución por "
         "edad del cuerpo académico). Solo la ven usted y la Administración del sistema; los informes usan tramos "
         "de edad, nunca la fecha. Si no es correcta, pida a la administración que la corrija.")


def tarjeta(uid: int, id_: str = "datos-personales"):
    fecha = academicos.fecha_nacimiento(uid)
    texto = f"{fecha[8:10]}/{fecha[5:7]}/{fecha[:4]}" if fecha else None
    return Card(
        Div(UkIcon("lock", height=16, width=16), H3("Datos personales", cls="text-base font-semibold"),
            cls="flex items-center gap-2 mb-2"),
        Div(Span("Fecha de nacimiento", cls=(TextPresets.muted_sm, "w-40 shrink-0")),
            Span(texto or "Sin registrar"), cls="flex flex-col sm:flex-row gap-1 py-1"),
        P(AVISO, cls=(TextPresets.muted_sm, "mt-2")),
        id=id_)
