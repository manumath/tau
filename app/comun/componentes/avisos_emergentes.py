"""Avisos emergentes («toasts») de `add_toast`, sin JavaScript en el HTML (CSP estricta).

Reemplaza a `fasthtml.toaster.setup_toasts`, que agrega un script en línea y retira cada aviso con
`hx-on` (código evaluado). Se usa el mismo `add_toast` (guarda los avisos en la sesión) y el mismo
estilo; static/js/avisos.js crea el contenedor y retira cada aviso tras `data-duracion` ms.
"""
from fasthtml.common import Div, Span, Style
from fasthtml.core import FtResponse
from fasthtml.toaster import sk, tcid, toast_css
from fastcore.xml import FT

DURACION = 5000


def _avisos(sess):
    return Div(*[Div(Span(msg), cls=f"fh-toast fh-toast-{tipo}", role="status", data_duracion=DURACION)
                 for msg, tipo, _ in sess.pop(sk, [])],
               id=tcid, hx_swap_oob=f"beforeend:#{tcid}")


def _despues(resp, req, sess):
    if sk in sess and (not resp or isinstance(resp, (tuple, FT, FtResponse))):
        req.injects.append(_avisos(sess))


def montar(app):
    app.hdrs += [Style(toast_css)]
    app.after.append(_despues)
