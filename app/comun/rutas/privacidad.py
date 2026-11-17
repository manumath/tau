"""Páginas públicas de la plataforma: la entrada `/publico` y la de privacidad (PLAN §72, etapa 8), que muestra los
tratamientos de datos personales de los módulos activos de esta instalación (PLAN §73)."""
from fasthtml.common import APIRouter, Div, P, Redirect
from monsterui.all import H2, H3, Card

from app.comun import config, modulos, privacidad
from app.comun.componentes.publica import pagina_publica, secciones_activas

rt = APIRouter()


@rt("/publico")
def get():
    """A la primera sección pública de un módulo activo (el directorio de investigadores, si lo hay)."""
    return Redirect(secciones_activas()[0][1])


@rt("/publico/privacidad")
def get():
    def fila(titulo, texto):
        return Div(Div(titulo, cls="text-sm font-semibold"), P(texto, cls="text-sm"), cls="space-y-0.5")
    vigentes = modulos.tratamientos_activos()   # solo lo que tratan los módulos activos de esta instalación
    return pagina_publica(
        "Privacidad",
        H2("Sus datos en el sistema"),
        P(f"Qué datos personales guarda {config.NOMBRE_SISTEMA}, para qué, quién los ve y cuánto se conservan. Cada formulario "
          "que pide datos lleva un resumen de esto junto al botón de enviar.", cls="text-sm max-w-3xl my-4"),
        P(privacidad.CONTACTO, cls="text-sm max-w-3xl mb-6"),
        Div(*[Card(H3(t.titulo, cls="text-base font-semibold mb-3"),
                   Div(fila("Qué datos", t.datos), fila("Para qué", t.finalidad), fila("Quién los ve", t.quien_ve),
                       fila("Cuánto se conservan", t.conservacion), cls="space-y-3"), id=clave, cls="scroll-mt-4")
              for clave, t in privacidad.TRATAMIENTOS.items() if clave in vigentes], cls="space-y-4 max-w-3xl"),
        pie=f"{config.NOMBRE_CARRERA} · Política de datos del sistema {config.NOMBRE_SISTEMA}.")
