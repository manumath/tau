# Catálogos de referencia

## MSC2020.tsv

Mathematics Subject Classification 2020, obtenida de <https://msc2020.org/MSC_2020.csv>
y convertida de ISO-8859-1 a UTF-8.

La publican en conjunto Mathematical Reviews (AMS) y zbMATH Open bajo licencia
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Este archivo se
redistribuye sin cambios de contenido, bajo la misma licencia y con esta atribución.

La migración `migrations/0004-msc2020.py` lo carga en la tabla `msc`. Los textos traen
notación TeX en línea, como `\(p\)-adic`, que la interfaz muestra con KaTeX.
