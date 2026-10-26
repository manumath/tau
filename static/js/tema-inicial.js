// Tema inicial de Franken UI (tema «cmat»: colores de la Carrera, estilos/tema-cmat.css) (lo que MonsterUI ponía en línea con headers_theme): clases de tema y
// modo oscuro antes de pintar la página. Se carga sin defer en <head>. tests/test_csp.py comprueba que
// coincide con headers_theme('cmat', mode='auto', radii/shadows/font = sm).
const htmlElement = document.documentElement;
        
          
          const __FRANKEN__ = JSON.parse(localStorage.getItem("__FRANKEN__") || "{}");
    
          if (
            __FRANKEN__.mode === "dark" ||
            (!__FRANKEN__.mode &&
              window.matchMedia("(prefers-color-scheme: dark)").matches)
          ) {
            htmlElement.classList.add("dark");
          } else {
            htmlElement.classList.remove("dark");
          }
        
          htmlElement.classList.add(__FRANKEN__.theme || "uk-theme-cmat");
          htmlElement.classList.add(__FRANKEN__.radii || "uk-radii-sm");
          htmlElement.classList.add(__FRANKEN__.shadows || "uk-shadows-sm");
          htmlElement.classList.add(__FRANKEN__.font || "uk-font-sm");
