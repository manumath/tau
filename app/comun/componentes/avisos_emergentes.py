"""Avisos emergentes («toasts») de `add_toast`, sin JavaScript en el HTML (CSP estricta).

Reemplaza a `fasthtml.toaster.setup_toasts`, que agrega un script en línea y retira cada aviso con
`hx-on` (código evaluado). Se usa el mismo `add_toast` (guarda los avisos en la sesión) y el mismo
estilo; static/js/avisos.js crea el contenedor y retira cada aviso tras `data-duracion` ms.

`aviso_con_deshacer(sess, mensaje, **hx)`: un aviso con el botón «Deshacer», que hace la petición indicada en
`hx` (p. ej. `hx_post=…, hx_vals=…`). Para acciones reversibles, en lugar de pedir confirmación antes
(PLAN.md §48, paso 4): queda a la vista más tiempo (`DURACION_DESHACER`).
"""
import fasthtml.common as fh
from fasthtml.common import Div, Span, Style
from fasthtml.core import FtResponse
from fasthtml.toaster import sk, tcid, toast_css
from fastcore.xml import FT

DURACION = 5000
DURACION_DESHACER = 10000
CLAVE_DESHACER = "avisos_deshacer"


def aviso_con_deshacer(sess, mensaje: str, **hx):
    sess.setdefault(CLAVE_DESHACER, []).append({"mensaje": mensaje, "hx": hx})


def _avisos(sess):
    simples = [Div(Span(msg), cls=f"fh-toast fh-toast-{tipo}", role="status", data_duracion=DURACION)
               for msg, tipo, _ in sess.pop(sk, [])]
    con_deshacer = [Div(Span(a["mensaje"]),
                        fh.Button("Deshacer", type="button",
                                  cls="ml-3 font-semibold underline underline-offset-2", **a["hx"]),
                        cls="fh-toast fh-toast-success", role="status", data_duracion=DURACION_DESHACER)
                    for a in sess.pop(CLAVE_DESHACER, [])]
    return Div(*simples, *con_deshacer, id=tcid, hx_swap_oob=f"beforeend:#{tcid}")


def _despues(resp, req, sess):
    if (sk in sess or CLAVE_DESHACER in sess) and (not resp or isinstance(resp, (tuple, FT, FtResponse))):
        req.injects.append(_avisos(sess))


def montar(app):
    app.hdrs += [Style(toast_css)]
    app.after.append(_despues)
