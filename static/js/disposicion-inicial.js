// Menú lateral plegado (PLAN.md §53): se aplica antes de pintar la página para que no salte. Se carga sin
// defer en <head>. La elección la guarda static/js/acciones.js (data-accion="plegar-lateral").
try {
  if (localStorage.getItem('tau-menu') === 'plegado') document.documentElement.dataset.lateral = 'plegado';
  // Grupos del menú plegados (PLAN.md §54): claves separadas por espacios; estilos/entrada.css los oculta.
  const grupos = localStorage.getItem('tau-grupos');
  if (grupos) document.documentElement.dataset.grupos = grupos;
} catch (e) { /* sin almacenamiento (modo privado): menú desplegado */ }
