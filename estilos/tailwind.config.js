// Configuración de Tailwind (compilada con scripts/estilos.sh).
//
// - Modo oscuro por selector (html.dark), como la que MonsterUI pasaba al CDN.
// - Colores del tema: las variables HSL de Franken UI (--primary: 221.2 83.2% 53.3%, …), con
//   soporte de opacidad (bg-primary/10). Antes las aportaba daisyUI, que ya no se carga.
// - Las clases se buscan en el código Python del sistema, en static/js y en el de MonsterUI (MONSTERUI_DIR lo
//   fija scripts/estilos.sh). MonsterUI arma algunas en tiempo de ejecución (md:{…},
//   grid-cols-{n}): esas van en clases_dinamicas.txt.
const tema = (nombre) => `hsl(var(--${nombre}) / <alpha-value>)`;
const colores = {};
for (const c of ["background", "foreground", "card", "card-foreground", "popover", "popover-foreground",
                 "primary", "primary-foreground", "secondary", "secondary-foreground", "muted",
                 "muted-foreground", "accent", "accent-foreground", "destructive",
                 "destructive-foreground", "border", "input", "ring"]) {
  colores[c] = tema(c);
}

module.exports = {
  darkMode: "selector",
  content: [
    "./main.py",
    "./app/**/*.py",
    "./static/js/**/*.js",
    "./estilos/clases_dinamicas.txt",
    `${process.env.MONSTERUI_DIR}/**/*.py`,
  ],
  theme: { extend: { colors: colores } },
};
