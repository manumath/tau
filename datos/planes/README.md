# Planes de estudio

Datos de los planes de estudio que carga el portal (`app/academico/importar_planes.py`). La
migración 0028 cargó los planes 2017; un plan nuevo se agrega con una fila en `planes.csv` y su
propio CSV (luego se cargará desde la interfaz).

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

## observaciones.csv

Inconsistencias que solo se ven leyendo el documento. Las demás (totales que no cuadran,
requisitos inexistentes, asignaturas repetidas, nombres distintos para una sigla) las detecta la
carga. Todas quedan en el portal para que la Dirección Académica las revise.

## Origen de los planes 2017

Documentos de la Dirección Académica de la Carrera de Matemática (Resolución HCU 041/2017),
transcritos de los PDF por la posición de las columnas y verificados contra los totales declarados:
las horas teóricas y prácticas coinciden en ambas licenciaturas; las de laboratorio no (queda
marcado). Los nombres se copian tal como están en cada documento.
