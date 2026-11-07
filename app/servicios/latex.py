"""Documentos LaTeX del perfil de proyecto de grado (PLAN §58): la nota de presentación al Director de Carrera y el
perfil con la plantilla de la Carrera (clase `perfil-cmat`). Se entregan en un ZIP con la clase, para compilarlos con
pdfLaTeX o seguir en Overleaf.

Los datos de la persona (nombres, tutor, RU) se escapan. El título y las secciones van tal cual: el estudiante escribe en
LaTeX (fórmulas entre $…$). Una bibliografía con entradas BibTeX (@article{…}) va a `referencias.bib`; si no, cada línea
es un \\bibitem.
"""
import io
import re
import zipfile
from datetime import date

from app.comun import config
from app.servicios import grado

_ESPECIALES = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
               "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
         "diciembre")

CLASE = r"""\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{perfil-cmat}[2026/11/07 Perfil de proyecto de grado, Carrera de Matematica]
\LoadClass[11pt,a4paper]{article}
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage[spanish,es-noindentfirst]{babel}
\RequirePackage{amsmath,amssymb,amsthm}
\RequirePackage[margin=2.5cm]{geometry}
\RequirePackage{enumitem}
\RequirePackage{hyperref}
\newcommand{\@universidad}{}\newcommand{\universidad}[1]{\renewcommand{\@universidad}{#1}}
\newcommand{\@facultad}{}\newcommand{\facultad}[1]{\renewcommand{\@facultad}{#1}}
\newcommand{\@carrera}{}\newcommand{\carrera}[1]{\renewcommand{\@carrera}{#1}}
\newcommand{\@modalidad}{}\newcommand{\modalidad}[1]{\renewcommand{\@modalidad}{#1}}
\newcommand{\@postulante}{}\newcommand{\@ru}{}
\newcommand{\postulante}[2]{\renewcommand{\@postulante}{#1}\renewcommand{\@ru}{#2}}
\newcommand{\@tutor}{}\newcommand{\tutor}[1]{\renewcommand{\@tutor}{#1}}
\renewcommand{\maketitle}{%
  \begin{center}
    {\large\bfseries \@universidad}\\[2pt]
    \@facultad\\ \@carrera\\[1.5cm]
    {\Large Perfil de \@modalidad}\\[0.8cm]
    {\LARGE\bfseries \@title}\\[1.5cm]
    \begin{tabular}{rl}
      Postulante: & \@postulante\\
      R.\,U.: & \@ru\\
      Tutor: & \@tutor\\
    \end{tabular}\\[1cm]
    \@date
  \end{center}
  \thispagestyle{empty}\clearpage}
"""


def escapar(texto: str | None) -> str:
    return "".join(_ESPECIALES.get(c, c) for c in (texto or ""))


def _fecha(d: date | None = None) -> str:
    d = d or date.today()
    return f"La Paz, {d.day} de {MESES[d.month - 1]} de {d.year}"


def _lista(texto: str, entorno: str = "itemize") -> str:
    lineas = [x.strip(" -•\t") for x in (texto or "").splitlines() if x.strip()]
    if not lineas:
        return ""
    return f"\\begin{{{entorno}}}\n" + "\n".join(f"  \\item {x}" for x in lineas) + f"\n\\end{{{entorno}}}\n"


def es_bibtex(texto: str) -> bool:
    return bool(re.search(r"^\s*@\w+\s*\{", texto or "", re.M))


def _bibliografia(texto: str) -> str:
    if es_bibtex(texto):
        return "\\nocite{*}\n\\bibliographystyle{plain}\n\\bibliography{referencias}\n"
    lineas = [x.strip() for x in (texto or "").splitlines() if x.strip()]
    if not lineas:
        return ""
    items = "\n".join(f"\\bibitem{{r{i}}} {x}" for i, x in enumerate(lineas, 1))
    return f"\\begin{{thebibliography}}{{{len(lineas)}}}\n{items}\n\\end{{thebibliography}}\n"


def _tutor(t: dict) -> str:
    return escapar(f"{t['tutor_nombres']} {t['tutor_apellidos']}") if t.get("tutor_id") else "(por definir)"


def perfil_tex(t: dict) -> str:
    s = t["secciones"]
    partes = [
        "\\documentclass{perfil-cmat}",
        f"\\universidad{{{escapar(config.UNIVERSIDAD)}}}",
        f"\\facultad{{{escapar(config.FACULTAD)}}}",
        f"\\carrera{{{escapar(config.NOMBRE_CARRERA)}}}",
        f"\\modalidad{{{escapar(grado.MODALIDADES[t['modalidad']].lower())}}}",
        f"\\title{{{t['titulo']}}}",
        f"\\postulante{{{escapar(t['nombres'] + ' ' + t['apellidos'])}}}{{{escapar(t.get('ru') or '')}}}",
        f"\\tutor{{{_tutor(t)}}}",
        f"\\date{{{_fecha()}}}",
        "", "\\begin{document}", "\\maketitle", ""]
    for k in grado.seleccion(t):
        texto = s.get(k) or ""
        if k == "objetivo_general":
            partes += ["\\section{Objetivos}", "\\subsection{Objetivo general}", texto, ""]
        elif k == "objetivos_especificos":
            partes += ["\\subsection{Objetivos específicos}", _lista(texto, "enumerate")]
        elif k == "calendario":
            partes += ["\\section{Calendario}", _lista(texto)]
        elif k == "bibliografia":
            partes += [_bibliografia(texto)]
        else:
            partes += [f"\\section{{{grado.SECCIONES[k][0]}}}", texto, ""]
    partes += ["\\end{document}", ""]
    return "\n".join(partes)


def nota_tex(t: dict) -> str:
    nombre = escapar(f"{t['nombres']} {t['apellidos']}")
    que = "el perfil" if t["tipo"] == "perfil" else "el documento final"
    return "\n".join([
        "\\documentclass[11pt,a4paper]{letter}",
        "\\usepackage[utf8]{inputenc}", "\\usepackage[T1]{fontenc}", "\\usepackage[spanish]{babel}",
        "\\usepackage[margin=2.5cm]{geometry}",
        f"\\signature{{{nombre}\\\\ R.\\,U. {escapar(t.get('ru') or '')}}}",
        f"\\date{{{_fecha()}}}",
        "\\begin{document}",
        f"\\begin{{letter}}{{Señor(a)\\\\ Director(a) de la {escapar(config.NOMBRE_CARRERA)}\\\\ "
        f"{escapar(config.FACULTAD)}\\\\ {escapar(config.UNIVERSIDAD)}\\\\ Presente}}",
        "\\opening{Ref.: Presentación de " + que + " de " + escapar(grado.MODALIDADES[t['modalidad']].lower()) + "}",
        f"De mi mayor consideración:\n\nMediante la presente, me permito presentar a su autoridad {que} de "
        f"{escapar(grado.MODALIDADES[t['modalidad']].lower())} titulado «{t['titulo']}», bajo la tutoría de {_tutor(t)}, "
        "para su consideración y la designación del tribunal correspondiente.",
        "\\closing{Atentamente,}",
        "\\end{letter}", "\\end{document}", ""])


def zip_perfil(t: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("perfil.tex", perfil_tex(t))
        z.writestr("nota.tex", nota_tex(t))
        z.writestr("perfil-cmat.cls", CLASE)
        if es_bibtex(t["secciones"].get("bibliografia") or ""):
            z.writestr("referencias.bib", t["secciones"]["bibliografia"])
        z.writestr("LEAME.txt", "Compile con pdflatex: pdflatex perfil.tex (y bibtex perfil si hay referencias.bib).\n"
                   "La nota de presentación: pdflatex nota.tex\n")
    return buf.getvalue()
