// Avisos emergentes: los del servidor (add_toast, que llegan fuera de banda al contenedor
// #fh-toast-container) y los de error de las peticiones HTMX. Sin código en línea (CSP estricta).
(() => {
  const DURACION = 5000;
  function contenedor() {
    let c = document.getElementById('fh-toast-container');
    if (!c) { c = document.createElement('div'); c.id = 'fh-toast-container'; document.body.appendChild(c); }
    return c;
  }
  // Cada aviso se retira solo; los del servidor indican su duración en data-duracion.
  function programar(el) {
    if (el.dataset.programado) return;
    el.dataset.programado = '1';
    setTimeout(() => el.remove(), Number(el.dataset.duracion) || DURACION);
  }
  function revisar(raiz) {
    (raiz.matches && raiz.matches('.fh-toast') ? [raiz] : []).concat([...raiz.querySelectorAll('.fh-toast')])
      .forEach(programar);
  }
  document.addEventListener('DOMContentLoaded', () => { contenedor(); revisar(document); });
  document.addEventListener('htmx:load', e => revisar(e.detail.elt));
  document.addEventListener('htmx:oobAfterSwap', e => revisar(e.detail.target));

  const mensajes = {
    403: 'No tiene permiso para esta acción.',
    404: 'No se encontró: puede que lo hayan eliminado. Recargue la página.',
    413: 'El archivo es demasiado grande.',
    503: 'El sistema está en mantenimiento: por ahora solo se puede consultar.',
  };
  function aviso(texto) {
    const d = document.createElement('div');
    d.className = 'fh-toast fh-toast-error';
    d.setAttribute('role', 'alert');
    d.textContent = texto;
    d.dataset.duracion = '6000';
    contenedor().appendChild(d);
    programar(d);
  }
  document.addEventListener('htmx:responseError', e => {
    const s = e.detail.xhr.status;
    aviso(mensajes[s] || (s >= 500 ? 'Ocurrió un error en el servidor. Intente de nuevo; si persiste, '
                                    + 'avise a la administración.' : `Error ${s}.`));
  });
  document.addEventListener('htmx:sendError', () => aviso('Sin conexión con el servidor. Revise su red.'));
})();
