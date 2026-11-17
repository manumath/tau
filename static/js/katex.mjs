// KaTeX: renderiza \( \), $ $ y $$ $$ en todo contenido nuevo (carga inicial y swaps de HTMX).
// Bajo demanda (PLAN §62, etapa 6): la biblioteca y su hoja de estilos (unos 300 KB) se piden solo la primera vez
// que aparece un delimitador; la URL versionada de la hoja viene en <meta name="katex-css">.
const opciones = {
  delimiters: [
    {left: '$$', right: '$$', display: true},
    {left: '\\(', right: '\\)', display: false},
    {left: '$', right: '$', display: false},
  ],
  ignoredClasses: ['nomath'],
  throwOnError: false,
};
let cargada = null;
function cargar() {
  if (!cargada) {
    const css = document.querySelector('meta[name="katex-css"]');
    if (css) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = css.content;
      document.head.appendChild(link);
    }
    cargada = import('../vendor/katex/contrib/auto-render.mjs').then(m => m.default);
  }
  return cargada;
}
const conFormulas = el => /\$|\\\(/.test(el.textContent || '');
const render = el => {
  el = el || document.body;
  if (conFormulas(el)) cargar().then(renderMathInElement => renderMathInElement(el, opciones));
};
render(document.body);
document.addEventListener('htmx:load', e => render(e.detail.elt));
