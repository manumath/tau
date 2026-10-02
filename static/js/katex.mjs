// KaTeX: renderiza \( \), $ $ y $$ $$ en todo contenido nuevo (carga inicial y swaps de HTMX).
import renderMathInElement from '../vendor/katex/contrib/auto-render.mjs';

const opciones = {
  delimiters: [
    {left: '$$', right: '$$', display: true},
    {left: '\\(', right: '\\)', display: false},
    {left: '$', right: '$', display: false},
  ],
  ignoredClasses: ['nomath'],
  throwOnError: false,
};
const render = el => renderMathInElement(el || document.body, opciones);
render(document.body);
document.addEventListener('htmx:load', e => render(e.detail.elt));
