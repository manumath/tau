# Planes de estudio

Planes de estudio que carga el sistema al instalar la instancia (`app/instalacion.py`, `app/academico/importar_planes.py`). Un plan
posterior se crea en pantalla dentro de una reforma curricular (PLAN §65) y su malla se arma a mano o subiendo un CSV con
el formato de abajo (Docencia → Planes → Malla → Importar, que ofrece la plantilla).

## planes.csv — un plan por fila

`archivo` (CSV del plan), `programa`, `nivel` (licenciatura, maestria…), `plan` («Plan 2017»),
`resolucion`, `vigente_desde` (año), `sistema` (`horas` o `creditos`), `semanas_semestre`,
`horas_por_credito`, `nota_minima` y los totales que declara el documento (`total_teoricas`,
`total_practicas`, `total_laboratorio`, `total_creditos`), que la carga compara con la suma.

## Un CSV por plan — una fila por asignatura o casilla de electiva

`sigla`, `nombre`, `tipo`, `semestre`, `ciclo`, `horas_teoricas`, `horas_practicas`,
`horas_laboratorio` (semanales) o `creditos`, y `requisitos` (siglas separadas por «;» o `egresado`).

Tipos: `obligatoria`, `trabajo_final`; en las listas de electivas (sin semestre) `electiva_a`,
`electiva_b` o `electiva`; y las casillas de un semestre que se llenan con una electiva
(`casilla_electiva_a`, `casilla_electiva_b`, `casilla_electiva`, sin sigla).

## lineas-formativas.csv

Una fila por asignatura (`sigla`): su `linea_formativa` (Fundamentos, Métodos, Aplicaciones…) y, si corresponde, el `area` de
investigación o la `linea` oficial con que se relaciona (por nombre; si trae línea, el área sale de ella). Es propia de
la asignatura, no del plan. La cargó la migración 0063, con la clasificación que usó la Comisión de calidad en el
informe de autoevaluación (PLAN §61).

## observaciones.csv

Inconsistencias que solo se ven leyendo el documento. Las demás (totales que no cuadran,
requisitos inexistentes, asignaturas repetidas, nombres distintos para una sigla) las detecta la
carga. Todas quedan en el sistema para que la Dirección Académica las revise.
