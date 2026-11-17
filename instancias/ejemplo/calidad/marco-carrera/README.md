# Marco de calidad de la Carrera (borrador)

Borrador del marco del Sistema Interno de Aseguramiento de la Calidad (SIAC) de la Carrera (PLAN §57). La migración
0051 lo carga una sola vez; después se edita en **Aseguramiento de la Calidad → Marco de calidad**, y la pantalla lo
exporta en XLSX con estas mismas columnas.

| Archivo | Una fila por | Columnas |
|---|---|---|
| `marco.csv` | dato del marco | `campo` (nombre, version, descripcion, vigente_desde, ventana_anios), `valor` |
| `escala.csv` | nivel de la escala de valoración | `valor` (1 = el más bajo), `nombre`, `descripcion` |
| `atributos.csv` | criterio de calidad de la política de la universidad | `clave`, `nombre`, `descripcion` |
| `dimensiones.csv` | dimensión | `codigo`, `nombre`, `descripcion`, `referencia` |
| `criterios.csv` | criterio | `dimension` (código), `codigo`, `nombre`, `descripcion` |
| `indicadores.csv` | indicador | `criterio` (código), `codigo`, `nombre`, `tipo`, `formula`, `fuente`, `unidad_medida`, `frecuencia`, `sentido`, `responsable`, `referencia`, `atributos` (claves separadas por «\|») |

- `tipo`: estructura, proceso, resultado, percepcion o contexto (los de la Política de Calidad).
- `fuente`: `manual` (la cifra se registra a mano) o `auto:<clave>` (la calcula el sistema; las claves están en
  `app/calidad/marco.py`, `FUENTES_AUTOMATICAS`).
- `frecuencia`: anual, semestral o por_periodo (una vez por periodo de evaluación). `sentido`: mayor, menor o
  informativo (sin semáforo).
- No incluye correspondencias con los criterios de una agencia: esas son privadas y no se versionan.
