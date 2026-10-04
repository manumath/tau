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
//   data-resumen-errores              resumen de errores: al llegar en una respuesta recibe el foco
//   data-escape-vaciar="id"           en un campo: Escape vacía #id (p. ej., las sugerencias de la búsqueda)
//   data-cerrar-fuera                 desplegable: un clic fuera de él lo vacía
//   tecla «/»                         lleva a la búsqueda global (#busqueda-global), salvo al escribir
//
// Además (accesibilidad y envíos):
//   - el modal recibe el foco al abrirse (en el primer campo), lo retiene con Tab y, al cerrarse, lo
//     devuelve al elemento que lo abrió;
//   - mientras dura una petición que envía datos, su botón (o los de envío del formulario) queda
//     deshabilitado: un doble clic con la red lenta no registra dos veces.
//   - las confirmaciones (hx-confirm) se preguntan en un diálogo propio, no en el confirm() del navegador:
//     el botón dice qué hace («Eliminar», «Quitar»…) y es rojo si la acción destruye algo.
(() => {
  const MODAL = 'modal';
  const ENFOCABLES = 'a[href], button:not([disabled]), input:not([type=hidden]):not([disabled]), ' +
    'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
  let abridor = null;  // quien abrió el modal: recupera el foco al cerrarlo
  const modal = () => document.getElementById(MODAL);
  const dialogo = () => document.querySelector('#' + MODAL + ' [role=dialog]');
  const visibles = raiz => [...raiz.querySelectorAll(ENFOCABLES)].filter(x => x.offsetParent !== null);
  const devolverFoco = () => {
    if (abridor && abridor.isConnected) abridor.focus();
    abridor = null;
  };
  const cerrarModal = () => { const m = modal(); if (m) m.innerHTML = ''; devolverFoco(); };

  document.addEventListener('click', e => {
    document.querySelectorAll('[data-cerrar-fuera]').forEach(d => {
      if (d.children.length && !d.parentElement.contains(e.target)) d.innerHTML = '';
    });
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
    const escribiendo = e.target.closest && e.target.closest('input, textarea, select, [contenteditable]');
    if (e.key === '/' && !escribiendo && !e.ctrlKey && !e.metaKey && !dialogo()) {
      const b = document.getElementById('busqueda-global');
      if (b && b.offsetParent !== null) { e.preventDefault(); b.focus(); }
      return;
    }
    if (e.key === 'Escape' && e.target.dataset && e.target.dataset.escapeVaciar) {
      const r = document.getElementById(e.target.dataset.escapeVaciar);
      if (r) r.innerHTML = '';
      return;
    }
    if (e.key === 'Escape' && document.querySelector('[data-fondo-modal]')) { cerrarModal(); return; }
    // Con el modal abierto, Tab recorre solo sus elementos (no la página de atrás).
    const d = e.key === 'Tab' ? dialogo() : null;
    if (d) {
      const lista = visibles(d);
      if (!lista.length) return;
      const primero = lista[0], ultimo = lista[lista.length - 1];
      if (!d.contains(document.activeElement)) { e.preventDefault(); primero.focus(); }
      else if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
      else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
      return;
    }
    const modo = e.key === 'Enter' && e.target.dataset ? e.target.dataset.enter : null;
    if (!modo) return;
    e.preventDefault();
    if (modo.startsWith('clic:')) { const b = document.getElementById(modo.slice(5)); if (b) b.click(); }
  });

  document.addEventListener('submit', e => { if (e.target.matches('[data-sin-envio]')) e.preventDefault(); });

  document.addEventListener('htmx:beforeRequest', e => {
    const el = e.detail.elt;
    // Quien pide algo para el modal (vacío) es quien lo abre.
    const destino = e.detail.target;
    const m = modal();
    if (destino && destino.id === MODAL && m && !m.children.length) abridor = document.activeElement;
    // Envíos: deshabilita el botón o los botones de envío del formulario mientras dura la petición.
    const verbo = (e.detail.requestConfig && e.detail.requestConfig.verb) || 'get';
    if (verbo !== 'get' && el) {
      const botones = el.tagName === 'FORM' ? [...el.querySelectorAll('button[type=submit], button:not([type])')]
        : (el.tagName === 'BUTTON' ? [el] : []);
      botones.filter(b => !b.disabled).forEach(b => { b.disabled = true; b.dataset.enEnvio = '1'; });
    }
    if (el && el.matches && el.matches('[data-pestana]')) {
      el.closest('ul').querySelectorAll('li').forEach(li => li.classList.remove('uk-active'));
      el.parentElement.classList.add('uk-active');
    }
  });

  document.addEventListener('htmx:afterRequest', e => {
    const el = e.detail.elt;
    if (el && el.querySelectorAll) {
      [...(el.dataset && el.dataset.enEnvio ? [el] : []), ...el.querySelectorAll('[data-en-envio]')]
        .forEach(b => { b.disabled = false; delete b.dataset.enEnvio; });
    }
    const ids = el && el.dataset ? el.dataset.trasPedidoLimpiar : null;
    // Si el servidor redirigió un error a otro lugar (HX-Retarget), no se limpia lo escrito.
    if (!ids || !e.detail.successful || e.detail.xhr.getResponseHeader('HX-Retarget')) return;
    const [buscar, resultados] = ids.split(',');
    const b = buscar && document.getElementById(buscar);
    const r = resultados && document.getElementById(resultados);
    if (b) { b.value = ''; b.focus(); }
    if (r) r.innerHTML = '';
  });

  // Lo que llega en una respuesta: un resumen de errores recibe el foco (el lector de pantalla lo anuncia);
  // un modal recién abierto, en su primer campo (o en el cuadro, si no tiene campos).
  document.addEventListener('htmx:load', e => {
    const el = e.detail.elt;
    if (!el || !el.querySelector || el === document.body) return;
    const errores = el.matches('[data-resumen-errores]') ? el : el.querySelector('[data-resumen-errores]');
    if (errores) { errores.focus(); return; }
    const fondo = el.matches('[data-fondo-modal]') ? el : el.querySelector('[data-fondo-modal]');
    if (fondo) {
      const d = fondo.querySelector('[role=dialog]');
      const campo = d && visibles(d).find(x => x.matches('input, select, textarea'));
      (campo || d || fondo).focus();
    }
  });

  // Confirmaciones: un <dialog> nativo (retiene el foco, Escape cancela). El texto va con textContent.
  const DESTRUCTIVAS = /^¿?(Eliminar|Quitar|Retirar|Fusionar|Desactivar|Dar de baja|Desvincular)/i;
  function confirmar(pregunta, verbo) {
    return new Promise(resolver => {
      const d = document.createElement('dialog');
      d.className = 'confirmacion';
      d.setAttribute('aria-labelledby', 'confirmacion-texto');
      const texto = document.createElement('p');
      texto.id = 'confirmacion-texto';
      texto.textContent = pregunta;
      const accion = (pregunta.match(/^¿?\s*([A-Za-zÁÉÍÓÚÑáéíóúñ]+)/) || [])[1];
      const destructiva = verbo === 'delete' || DESTRUCTIVAS.test(pregunta.trim());
      const si = document.createElement('button');
      si.type = 'button';
      si.className = 'uk-btn ' + (destructiva ? 'uk-btn-destructive' : 'uk-btn-primary');
      si.textContent = accion && accion.length > 2 && pregunta.trim().startsWith('¿') ? accion : 'Continuar';
      const no = document.createElement('button');
      no.type = 'button';
      no.className = 'uk-btn uk-btn-ghost';
      no.textContent = 'Cancelar';
      const botones = document.createElement('div');
      botones.className = 'confirmacion-botones';
      botones.append(no, si);
      d.append(texto, botones);
      document.body.appendChild(d);
      const fin = ok => { d.close(); d.remove(); resolver(ok); };
      si.addEventListener('click', () => fin(true));
      no.addEventListener('click', () => fin(false));
      d.addEventListener('cancel', e => { e.preventDefault(); fin(false); });
      d.showModal();
      (destructiva ? no : si).focus();  // en lo destructivo, Enter no confirma sin querer
    });
  }
  document.addEventListener('htmx:confirm', e => {
    if (!e.detail.question) return;
    e.preventDefault();
    confirmar(e.detail.question, e.detail.verb).then(ok => { if (ok) e.detail.issueRequest(true); });
  });

  // El servidor también cierra el modal (lo vacía al guardar): el foco vuelve a quien lo abrió.
  document.addEventListener('htmx:afterSettle', () => {
    const m = modal();
    if (abridor && m && !m.children.length) devolverFoco();
  });
})();
