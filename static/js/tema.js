// Tema claro, oscuro o el del sistema. La preferencia se guarda en el navegador (localStorage
// "__FRANKEN__".mode, la misma clave que lee Franken UI al cargar cada página, así no hay parpadeo).
(function () {
  const CLAVE = "__FRANKEN__";
  const sistemaOscuro = window.matchMedia("(prefers-color-scheme: dark)");

  function leer() {
    try { return JSON.parse(localStorage.getItem(CLAVE) || "{}"); } catch (e) { return {}; }
  }

  function modo() {
    return leer().mode || "sistema";
  }

  function aplicar() {
    const m = modo();
    const oscuro = m === "dark" || (m === "sistema" && sistemaOscuro.matches);
    document.documentElement.classList.toggle("dark", oscuro);
    document.querySelectorAll("[data-tema]").forEach(function (b) {
      const activo = (b.dataset.tema === "sistema" ? "sistema" : b.dataset.tema) === m;
      b.setAttribute("aria-pressed", activo ? "true" : "false");
      b.classList.toggle("bg-muted", activo);
      b.classList.toggle("text-primary", activo);
    });
  }

  function elegir(valor) {
    const datos = leer();
    if (valor === "sistema") { delete datos.mode; } else { datos.mode = valor; }
    try { localStorage.setItem(CLAVE, JSON.stringify(datos)); } catch (e) { /* sin almacenamiento: solo esta página */ }
    aplicar();
  }

  document.addEventListener("click", function (e) {
    const b = e.target.closest("[data-tema]");
    if (b) { e.preventDefault(); elegir(b.dataset.tema); }
  });
  sistemaOscuro.addEventListener("change", aplicar);
  document.addEventListener("htmx:load", aplicar);
  document.addEventListener("DOMContentLoaded", aplicar);
})();
