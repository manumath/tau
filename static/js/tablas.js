// Tablas que se pueden trabajar: toda <table data-tabla="nombre-del-archivo"> gana, sin recargar,
//   - orden por columna (clic en el encabezado; números, fechas y texto en español),
//   - filtro por texto (sin distinguir tildes ni mayúsculas) con el conteo «N de M filas»,
//   - «Descargar CSV» de las filas visibles (UTF-8 con BOM, como los CSV del servidor).
// Las columnas sin título (acciones) no se ordenan ni se exportan. Una celda puede traer
// data-valor con el valor para ordenar (p. ej., una fecha ISO si muestra otra cosa).
// Se aplica también al contenido que llega por htmx (evento htmx:load) y se actualiza si htmx
// reemplaza las filas (p. ej., un buscador del servidor que cambia el <tbody>).
(function () {
  const normal = (t) => (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const NUMERO = /^[-+]?\d+(?:[.,]\d+)?(?:\s*(?:%|h\/mes))?$/;
  const VACIO = /^(|—|-)$/;
  const NEUTRA = "\u2195\uFE0E";  // ↕ como texto (sin \uFE0E, macOS lo dibuja como emoji)

  function texto(celda) {
    const sel = celda.querySelector("select");
    if (sel && sel.selectedOptions.length) return sel.selectedOptions[0].textContent.trim();
    return celda.textContent.replace(/\s+/g, " ").trim();
  }

  function valor(celda) {
    return celda.dataset.valor !== undefined ? celda.dataset.valor : texto(celda);
  }

  function comparar(a, b) {
    if (NUMERO.test(a) && NUMERO.test(b)) return parseFloat(a.replace(",", ".")) - parseFloat(b.replace(",", "."));
    return a.localeCompare(b, "es", { sensitivity: "base", numeric: true });
  }

  function csvSeguro(v) {
    // Neutraliza fórmulas (=, +, -, @) como las exportaciones del servidor.
    const t = /^[=+\-@]/.test(v) && !NUMERO.test(v) ? "'" + v : v;
    return /[",\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
  }

  function mejorar(tabla) {
    if (tabla.dataset.tablaLista) return;
    tabla.dataset.tablaLista = "1";
    const cuerpo = () => tabla.tBodies[0];
    const encabezados = tabla.tHead ? Array.from(tabla.tHead.rows[0].cells) : [];
    if (!cuerpo() || !encabezados.length) return;
    // Una fila que ocupa todo el ancho es el aviso de «no hay datos»: no se ordena ni se exporta.
    const esAviso = (f) => f.cells.length === 1 && f.cells[0].colSpan > 1;
    const filas = () => Array.from(cuerpo().rows).filter((f) => !esAviso(f));
    const conFiltro = tabla.dataset.tablaFiltro !== "no";  // p. ej., listas con buscador propio del servidor

    // Barra: filtro, conteo y descarga (no se imprime).
    const barra = document.createElement("div");
    barra.className = "no-imprimir flex flex-wrap items-center gap-3 mb-2";
    barra.innerHTML =
      '<input type="search" class="uk-input h-8 w-60 text-sm" placeholder="Filtrar…" aria-label="Filtrar la tabla">' +
      '<span class="text-xs text-muted-foreground" aria-live="polite"></span>' +
      '<button type="button" class="ml-auto inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-muted">' +
      "Descargar CSV</button>";
    const [filtro, conteo, boton] = barra.children;
    if (!conFiltro) filtro.remove();
    const contenedor = tabla.closest(".overflow-x-auto") || tabla;
    contenedor.parentNode.insertBefore(barra, contenedor);

    function contar() {
      const total = filas().length;
      const visibles = filas().filter((f) => !f.hidden).length;
      conteo.textContent = visibles === total ? `${total} fila${total === 1 ? "" : "s"}` : `${visibles} de ${total} filas`;
    }
    function filtrar() {
      const q = conFiltro ? normal(filtro.value.trim()) : "";
      filas().forEach((f) => {
        f.hidden = q !== "" && !normal(Array.from(f.cells).map(texto).join(" ")).includes(q);
      });
      contar();
    }
    if (conFiltro) filtro.addEventListener("input", filtrar);
    tabla._tablaRefrescar = function () {  // htmx cambió las filas: se vuelve a filtrar y contar
      const activo = encabezados.find((th) => ["ascending", "descending"].includes(th.getAttribute("aria-sort")));
      if (activo) {
        encabezados.forEach((o) => { if (o.getAttribute("aria-sort")) o.setAttribute("aria-sort", "none"); });
        encabezados.forEach((o) => { const f = o.querySelector("span[aria-hidden]"); if (f) f.textContent = NEUTRA; });
      }
      filtrar();
    };
    filtrar();

    // Orden por columna.
    encabezados.forEach(function (th, i) {
      if (!th.textContent.trim()) return;
      th.setAttribute("aria-sort", "none");
      th.classList.add("cursor-pointer", "select-none", "whitespace-nowrap");
      th.title = "Ordenar por esta columna";
      const flecha = document.createElement("span");
      flecha.className = "ml-1 text-muted-foreground";
      flecha.setAttribute("aria-hidden", "true");
      flecha.textContent = NEUTRA;
      th.appendChild(flecha);
      th.tabIndex = 0;
      const ordenar = function () {
        const asc = th.getAttribute("aria-sort") !== "ascending";
        encabezados.forEach((o) => {
          if (o.getAttribute("aria-sort")) {
            o.setAttribute("aria-sort", "none");
            const f = o.querySelector("span[aria-hidden]");
            if (f) f.textContent = NEUTRA;
          }
        });
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        flecha.textContent = asc ? "↑" : "↓";
        const orden = filas().sort((a, b) => {
          const x = valor(a.cells[i] || a), y = valor(b.cells[i] || b);
          const vx = VACIO.test(x), vy = VACIO.test(y);
          if (vx || vy) return vx === vy ? 0 : vx ? 1 : -1;  // los vacíos al final, en ambos sentidos
          const r = comparar(x, y);
          return asc ? r : -r;
        });
        orden.forEach((f) => cuerpo().appendChild(f));
      };
      th.addEventListener("click", ordenar);
      th.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ordenar(); } });
    });

    // Descarga de lo visible.
    boton.addEventListener("click", function () {
      const columnas = encabezados.map((th, i) => [i, th.firstChild ? th.firstChild.textContent.trim() : ""])
        .filter(([, t]) => t);
      const lineas = [columnas.map(([, t]) => csvSeguro(t)).join(",")];
      filas().filter((f) => !f.hidden).forEach(function (f) {
        lineas.push(columnas.map(([i]) => csvSeguro(f.cells[i] ? texto(f.cells[i]) : "")).join(","));
      });
      const blob = new Blob(["﻿" + lineas.join("\r\n")], { type: "text/csv;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${tabla.dataset.tabla || "tabla"}-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
    });
  }

  function aplicar(raiz) {
    (raiz || document).querySelectorAll("table[data-tabla]").forEach(mejorar);
    if (raiz && raiz.matches && raiz.matches("table[data-tabla]")) mejorar(raiz);
  }
  document.addEventListener("DOMContentLoaded", () => aplicar(document));
  document.addEventListener("htmx:load", (e) => aplicar(e.detail.elt));
  document.addEventListener("htmx:afterSettle", function () {
    document.querySelectorAll("table[data-tabla-lista]").forEach((t) => t._tablaRefrescar && t._tablaRefrescar());
  });
})();
