# IA en TAU: decisiones de diseño

Registro de cómo se aplicó la hoja de ruta «IA con criterio humano en TAU» (PLAN §59). La hoja de ruta pide adaptarse a
la arquitectura y anotar aquí cada adaptación. Una entrada por etapa, con fecha.

## Etapa 0a: fundaciones (8-nov-2026)

### Adaptaciones a la arquitectura
- **Paquete `app/ia`**, no `ia/`, como los demás paquetes. Las instrucciones están en
  `app/ia/instrucciones/<clave>/v<n>.md`.
- **Variables `PORTAL_IA_*`**, no `TAU_IA_*`, por la convención de `config.py` (los nombres técnicos conservan
  «portal»). Hay un límite de tiempo configurable (`PORTAL_IA_TIEMPO_S`, 300 s por omisión) porque un modelo local en
  procesador es lento.
- **El catálogo de funciones vive en el código** (`funciones.py`): módulo, nivel máximo, seudonimización, si puede ir
  afuera, quién la pide y quién aprueba. La tabla `ia_funcion` guarda solo si está activa, su responsable y quién la
  cambió. Así, una función no existe sin código ni pruebas, y la base no puede declarar un nivel distinto del
  programado.
- **La decisión humana va en el estado de `ia_uso`**: `generando` → `borrador_ia` → `aprobada`, `editada` o
  `rechazada` (o `error`). La hoja de ruta tenía un campo `decision` aparte. El nivel de datos y si se seudonimizó
  también se registran, para auditar el enrutamiento.
- **La auditoría es la existente** (`db.auditar`), con estas acciones:
  - `ia_invocar`, `ia_borrador`, `ia_error` y `ia_decision`;
  - `ia_bloqueada` y `ia_datos_rechazados`;
  - `ia_crear_politica`, `ia_aprobar_politica`, `ia_activar` y `ia_desactivar`.
- **Cliente HTTP:** `httpx2`, que ya era dependencia.

### Decisiones del agente (por confirmar)
- **Activar una función exige una política de uso aprobada** y una persona responsable activa. La hoja de ruta exige el
  responsable; la política es una condición agregada por gobernanza.
- **Módulos vedados en dos capas:**
  - `funciones.VEDADOS` impide registrar una función de esos módulos;
  - `servicio.ARCHIVOS_VEDADOS` bloquea una llamada que venga de sus archivos (revisa la pila de llamadas) y la
    audita;
  - una prueba estática comprueba, además, que esos archivos no importan `app.ia`.

  Todo el trámite de grado (`servicios/grado.py`) queda vedado por ahora. Si más adelante se quiere ayuda para redactar
  el perfil, se separará lo del tribunal.
- **Seudonimización:** reemplaza cada nombre de persona completo, y cada palabra suya de más de 2 letras, por
  `[PERSONA_n]` en todos los datos. Así un apellido suelto tampoco sale. La correspondencia queda solo en memoria y
  los nombres se restituyen en la respuesta.
- **Preferencia de proveedor:** el externo, cuando el nivel y la retención cero lo permiten; si falla, el local. Si
  ambos fallan, el uso queda en `error` y la persona sigue manualmente.
- **Distancia de edición:** `1 − SequenceMatcher.ratio()` de `difflib` (0 = sin cambios, 1 = todo distinto).
- **Quién aprueba:** por omisión, quien pidió el borrador. Cada función puede exigir otro rol (`puede_aprobar`).

### Pruebas que verifican los principios (`tests/test_ia.py`)
| Principio | Prueba |
|---|---|
| 1. La persona decide | `test_la_salida_no_surte_efecto_sin_decision_humana` |
| 2. Módulos vedados | `test_no_se_registra_una_funcion_de_un_modulo_vedado`, `test_invocar_desde_un_modulo_vedado_falla_y_queda_auditado`, `test_los_modulos_vedados_no_importan_la_ia` |
| 3. Datos sensibles | `test_datos_sensibles_o_sin_clasificar_se_rechazan`, `test_seudonimizacion_los_nombres_no_salen_y_se_restituyen` |
| 4. Etiquetado | `test_la_salida_no_surte_efecto_sin_decision_humana` (marca de borrador y de aprobación) |
| 5. Trazabilidad | `test_cada_uso_queda_en_la_auditoria` |
| 6. Apagado por defecto | `test_todo_nace_apagado_y_activar_exige_politica_y_responsable` |
| 7. Sin calificación de personas | Se vela en cada función: ninguna produce puntajes; el módulo «personas» está vedado |
| Anexo A | `test_sin_retencion_cero_no_sale_nada_al_externo`, `test_cada_solicitud_externa_lleva_retencion_cero_y_su_clave`, `test_nivel_2_sin_seudonimizar_nunca_va_al_externo`, `test_si_el_externo_falla_se_usa_el_local_y_si_todo_falla_queda_error`, `test_una_funcion_solo_local_no_sale_aunque_el_nivel_lo_permita` |

## Etapas 0b a 4 (8-nov-2026)

### Adaptaciones a la arquitectura
- **Un solo lugar arma el contexto:** `app/ia/catalogo.py` registra las 7 funciones y tiene un `datos_<función>` para
  cada una. Las pantallas no arman lo que se envía al modelo: así se audita qué ve la IA leyendo un archivo.
- **Entidad por documento:** cada uso guarda en `entidad_tipo` el documento al que pertenece, como
  `memoria:<desde>_<hasta>`, `informe_proyecto:<id>:<desde>-<hasta>`, `producto:<id>`, `investigador:<id>`,
  `encuesta:<id>:<pregunta>`, `evidencias:<autoevaluación>:<criterio>` o `juicio:<autoevaluación>:<criterio>`. La
  función decide con ella si la persona puede pedir y aprobar.
- **Funciones de elección** (líneas de un producto y evidencias): el borrador es una lista de valores que la persona
  marca. Si deja exactamente lo sugerido, cuenta como «aprobada»; si cambia algo, como «editada».
- **Efectos de la aprobación** (`al_aprobar`): solo se ejecutan tras la decisión humana, cuando la función produce
  algo:
  - `producto_linea` para las líneas de un producto;
  - `investigador.bio` para el resumen del perfil;
  - una evidencia de tipo enlace para cada sugerencia aceptada;
  - `juicio_criterio.juicio` para la narrativa del criterio.
- **Todas las funciones corren en segundo plano** con aviso al terminar, porque un modelo local puede tardar. El panel
  se actualiza cada 3 segundos.
- **Orígenes clasificados nuevos:**
  - nivel 0: `marcadores.texto`;
  - nivel 1: `pregunta.texto`, `juicio_criterio.fortalezas` y `juicio_criterio.debilidades`;
  - nivel 2: `encuesta.respuestas_agregadas`, solo local.
- **Migración 0062:** el plan preveía la 0061 para guardar las secciones aprobadas de la memoria, pero no hizo falta
  (se guardan en `ia_salida`). La 0062 agrupa `ia_cierre`, `producto_linea` y el área de capacitación.

### Decisiones del agente (por confirmar)
1. **Panel con dos botones, Aprobar y Descartar**, en lugar de tres. «Aprobar con cambios» es aprobar después de
   corregir el texto en el mismo panel: el sistema lo distingue solo, comparando con el borrador.
2. **La página «Uso de IA en TAU» va en el menú del usuario**, para todo el personal. En el grupo Administración solo
   aparece «IA: administración y piloto», para quienes la gestionan o ven sus resultados. Así las personas sin rol no
   ven ese grupo.
3. **Memoria:** puede aprobar el borrador cualquier persona con el rol de Dirección del Instituto, no solo quien lo
   pidió.
4. **Síntesis de encuestas:**
   - siempre con el modelo local, aunque la encuesta sea nominal;
   - la piden y la aprueban quienes gestionan encuestas (Dirección de Carrera y Coordinación académica);
   - las respuestas abiertas juntas y mezcladas cuentan como nivel 2, mientras que una respuesta anónima suelta sigue
     siendo nivel 3.
5. **Sin citas textuales:** se omite todo tramo de 8 palabras o más copiado de una respuesta. Esto cubre también los
   temas con menos de 10 respuestas.
6. **Líneas de un producto:**
   - las directas se suman a las heredadas de sus proyectos (`lineas.de_registro` devuelve ambas);
   - el investigador puede quitar una línea directa;
   - aprobar una sugerencia agrega líneas y nunca quita las que ya estaban;
   - las líneas directas cuentan como uso de la línea, así que esa línea ya no se puede eliminar.
7. **Evidencias sugeridas:** los candidatos son los productos, proyectos y actividades del periodo de la autoevaluación
   (hasta 60, 40 y 60). La IA elige hasta 8. Cada una aceptada se registra como enlace con la dirección
   `PORTAL_URL` + la ruta del registro.
8. **Narrativa del criterio:** al aprobarla reemplaza el texto del juicio y conserva el nivel, las fortalezas y las
   debilidades. Solo se ofrece con la autoevaluación en curso.
9. **Sesgos:** se señala una línea o un tipo de producto que se descarta al menos 1,5 veces más que el promedio, con
   5 sugerencias o más y al menos 2 descartes.
10. **Cierre del piloto:** lo registra la Dirección de Carrera (`gestionar_ia`) con un fundamento de al menos 20
    caracteres; «retirar» apaga la función.
11. **El indicador `personal_capacitado_ia` está disponible pero no se agregó al marco de calidad:** hacerlo es
    decisión de la Dirección.
12. **Política sugerida:** al crear la primera versión, el formulario trae un borrador de 8 puntos para que la
    Dirección lo ajuste. No rige hasta que la Dirección lo aprueba.

### Pruebas (`tests/test_ia_etapas.py`)
| Etapa | Prueba |
|---|---|
| 0b | `test_pantallas_por_rol`, `test_administrar_politica_y_funciones` |
| 1a | `test_memoria_cifras_desde_la_base_y_marca` (ninguna cifra del modelo; sin aprobar no entra al documento) |
| 1b | `test_informe_de_proyecto_solo_el_responsable`, `test_medicion_y_cierre_del_piloto` |
| 2 | `test_clasificar_producto_solo_guarda_lo_confirmado`, `test_resumen_del_perfil_seudonimizado`, `test_reporte_de_sesgos` |
| 3a | `test_sintesis_de_respuestas_abiertas` (≥ 10, solo local, sin metadatos, sin citas), `test_textos_sin_citas_y_cifras` |
| 3b | `test_evidencias_y_narrativa_de_un_criterio` (el nivel sigue siendo humano; la página pública no usa texto de IA) |
| 4 | `test_capacitacion_en_ia_en_el_cv_y_el_indicador`, `test_plantilla_de_percepcion_de_la_ia` |
