// Comportamientos de la interfaz sin JavaScript en el HTML (la CSP no admite onclick=…, hx-on… ni
// scripts en línea). Cada elemento declara con atributos data-* qué hace; aquí hay un solo manejador
// por tipo de evento (delegación), así que también funciona en lo que llega por HTMX.
//
//   data-accion="cerrar-modal"        vacía el modal (#modal)
//   data-accion="subir" | "bajar"     mueve la fila <li> que contiene al botón
//   data-accion="quitar"              quita la fila: <li>, o el elemento indicado en data-quitar (selector closest)
//   data-accion="vaciar"              vacía el contenido de #data-objetivo
//   data-accion="elegir-archivo"      abre el selector de archivos del formulario
//   data-accion="imprimir"            window.print()
//   data-accion="copiar"              copia data-copiar o el texto de #data-copiar-de; muestra data-copiado
//   data-accion="con-busqueda"        en un enlace: agrega la búsqueda actual (?…) a su href
//   data-navegar="/ruta?x="           en un select: va a esa ruta + el valor elegido
//   data-mostrar-modo                 en un select: muestra los [data-modo] del formulario que coinciden
//   data-enter="prevenir" | "clic:ID" en un campo: Enter no envía el formulario (o pulsa #ID)
//   data-sin-envio                    en un formulario: no se envía (lo maneja HTMX)
//   data-fondo-modal                  fondo del modal: un clic fuera del cuadro lo cierra; Escape también
//   data-tras-pedido-limpiar="b,r"    tras una petición HTMX exitosa: vacía el campo #b y el contenido de #r
//   data-pestana                      en un enlace de pestañas HTMX: la marca activa al pedirla
(() => {
  const MODAL = 'modal';
  const cerrarModal = () => { const m = document.getElementById(MODAL); if (m) m.innerHTML = ''; };

  document.addEventListener('click', e => {
    const fondo = e.target.closest('[data-fondo-modal]');
    if (fondo && e.target === fondo) { cerrarModal(); return; }
    const el = e.target.closest('[data-accion]');
    if (!el) return;
    switch (el.dataset.accion) {
      case 'cerrar-modal': cerrarModal(); break;
      case 'subir': {
        const li = el.closest('li');
        if (li && li.previousElementSibling) li.parentNode.insertBefore(li, li.previousElementSibling);
        break;
      }
      case 'bajar': {
        const li = el.closest('li');
        if (li && li.nextElementSibling) li.parentNode.insertBefore(li.nextElementSibling, li);
        break;
      }
      case 'quitar': { const f = el.closest(el.dataset.quitar || 'li'); if (f) f.remove(); break; }
      case 'vaciar': { const o = document.getElementById(el.dataset.objetivo); if (o) o.innerHTML = ''; break; }
      case 'elegir-archivo': { const f = el.closest('form'); const i = f && f.querySelector('input[type=file]'); if (i) i.click(); break; }
      case 'imprimir': window.print(); break;
      case 'copiar': {
        const fuente = el.dataset.copiarDe ? document.getElementById(el.dataset.copiarDe) : null;
        const texto = fuente ? fuente.innerText : (el.dataset.copiar || '');
        if (navigator.clipboard) navigator.clipboard.writeText(texto).then(() => {
          if (el.dataset.copiado && el.lastChild) el.lastChild.textContent = ' ' + el.dataset.copiado;
        });
        break;
      }
      case 'con-busqueda': el.href = el.getAttribute('href').split('?')[0] + location.search; break;
    }
  });

  document.addEventListener('change', e => {
    const el = e.target;
    if (el.dataset && el.dataset.navegar !== undefined) {
      location.href = el.dataset.navegar + encodeURIComponent(el.value);
    } else if (el.dataset && el.dataset.mostrarModo !== undefined && el.form) {
      el.form.querySelectorAll('[data-modo]').forEach(x => x.classList.toggle('hidden', x.dataset.modo !== el.value));
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && document.querySelector('[data-fondo-modal]')) { cerrarModal(); return; }
    const modo = e.key === 'Enter' && e.target.dataset ? e.target.dataset.enter : null;
    if (!modo) return;
    e.preventDefault();
    if (modo.startsWith('clic:')) { const b = document.getElementById(modo.slice(5)); if (b) b.click(); }
  });

  document.addEventListener('submit', e => { if (e.target.matches('[data-sin-envio]')) e.preventDefault(); });

  document.addEventListener('htmx:beforeRequest', e => {
    const el = e.detail.elt;
    if (el && el.matches && el.matches('[data-pestana]')) {
      el.closest('ul').querySelectorAll('li').forEach(li => li.classList.remove('uk-active'));
      el.parentElement.classList.add('uk-active');
    }
  });

  document.addEventListener('htmx:afterRequest', e => {
    const el = e.detail.elt;
    const ids = el && el.dataset ? el.dataset.trasPedidoLimpiar : null;
    // Si el servidor redirigió un error a otro lugar (HX-Retarget), no se limpia lo escrito.
    if (!ids || !e.detail.successful || e.detail.xhr.getResponseHeader('HX-Retarget')) return;
    const [buscar, resultados] = ids.split(',');
    const b = buscar && document.getElementById(buscar);
    const r = resultados && document.getElementById(resultados);
    if (b) { b.value = ''; b.focus(); }
    if (r) r.innerHTML = '';
  });

  // El modal recibe el foco al abrirse (para que Escape funcione sin hacer clic antes).
  document.addEventListener('htmx:load', e => {
    const f = e.detail.elt && e.detail.elt.querySelector ? (e.detail.elt.matches('[data-fondo-modal]')
      ? e.detail.elt : e.detail.elt.querySelector('[data-fondo-modal]')) : null;
    if (f) f.focus();
  });
})();
