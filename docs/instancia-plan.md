# Plan: separar la «instancia» y empezar de cero (propuesta, 16-nov-2026)

**Hecho (I1 a I5, 17-nov-2026):** lo construido y las decisiones están en `PLAN.md` §74; este documento conserva el
diseño original. Los nombres técnicos pasaron a `TAU_*` y `tau.db` el 17-nov-2026; el historial nuevo de git sigue por confirmar.

Era una propuesta de trabajo. Parte de un dato nuevo del usuario (16-nov-2026): los datos
que hoy tiene el sistema son de prueba, nada es crítico y el despliegue empezará de cero. Sigue a
[modularizacion-plan.md](modularizacion-plan.md) y a `PLAN.md` §73.

## 1. Qué cambia al poder empezar de cero

La regla «nunca edite una migración aplicada» protege bases en uso. Si ninguna base debe conservarse, las 96
migraciones se pueden **reemplazar por un esquema base limpio**. Eso resuelve de una vez lo que antes era el punto más
difícil: los datos de la Carrera de Matemática que las migraciones siembran.

Lo que hoy es de la Carrera y está dentro del código o del esquema:

| Qué | Dónde está hoy |
|---|---|
| Las cuatro unidades (UMSA, FCPN, CMAT, IIMAT) | Migración `0022` |
| Planes de estudio 2017 y líneas formativas | `datos/planes/`, migraciones `0028` y `0063` (en Python) |
| Marco de calidad y plan de mejora | `datos/calidad/`, migración `0051` (en Python) |
| Líneas y áreas de investigación | Migraciones `0021` y `0060` |
| Marca: colores, isotipo, logotipo, logo del instituto, iconos | `app/comun/marca.py`, `static/img/marca/`, `static/img/membrete/` |
| Textos con nombres propios | Unas 80 menciones de UMSA, FCPN, CMAT o IIMAT en `app/` |

Lo que es de referencia y sirve a cualquier unidad (se queda en el esquema base): tipos de producto y de actividad,
índices, grados académicos.

Las pruebas dependen de esos datos: 40 archivos usan `id_de("CMAT")` y similares, 19 usan los planes de 2017 y 13 el
marco de calidad. No hay que reescribirlas: basta con que la base de las pruebas cargue una instancia de ejemplo.

## 2. Diseño

### 2.1 Una instancia es una carpeta

```
instancias/<nombre>/
  instancia.toml      nombre del sistema, perfil de módulos, dirección del membrete, contacto de privacidad
  unidades.csv        tipo, sigla, nombre (universidad, facultad, carrera, instituto)
  marca/              marca.toml (colores), isotipo, logotipo, versiones en blanco, logo del instituto, iconos
  planes/             los CSV de planes de estudio (formato actual de datos/planes/)
  calidad/            marco de calidad y plan de mejora (formato actual de datos/calidad/)
  catalogos/          líneas y áreas de investigación, líneas formativas
```

- El repositorio lleva **una instancia de ejemplo**; la de cada unidad vive fuera del repositorio y se indica con una
  variable de entorno (`TAU_INSTANCIA=/ruta`).
- `scripts/instalar.py --instancia <carpeta>` carga una base **vacía** con los importadores que ya existen
  (`importar_planes`, `marco_csv`, `importar_mejora`, `unidades.configurar`) y fija el perfil de módulos. Sobre una base
  con datos se niega, salvo que se pida reemplazar.
- La marca se sirve desde la carpeta de la instancia, con la genérica como respaldo.

### 2.2 Esquema base

- `migrations/0001-esquema.sql`: el esquema actual completo (165 tablas) más los datos de referencia, sin nada de una
  unidad. Las migraciones siguientes parten de ahí.
- Se verifica comparando el esquema de una base migrada con las 96 migraciones actuales contra el de la base nueva:
  deben ser iguales tabla por tabla.
- Se mantiene **una sola carpeta de migraciones**. No conviene repartir el esquema por módulo: hay claves foráneas
  entre tablas de módulos distintos y la regla «apagar oculta y no borra» sigue siendo la más simple.

### 2.3 Marca genérica

- Por defecto, un isotipo τ y una paleta neutra. La instancia los reemplaza con su `marca.toml` y sus imágenes.
- Los colores pasan a una hoja de estilos propia, generada de la marca, para no recompilar Tailwind por instalación
  (hoy `estilos/tema-cmat.css` entra en la compilación). Hay que comprobar que no rompe la prueba de contraste.

## 3. Etapas

Cada una es un commit con sus pruebas. Esfuerzos gruesos, sin medir.

| Etapa | Qué se hace | Esfuerzo |
|---|---|---|
| **I1. Instancia y cargador** | Formato de la carpeta, `scripts/instalar.py`, instancia de ejemplo con lo que hoy está en `datos/`. La base de las pruebas carga la instancia de ejemplo | 2–3 días |
| **I2. Esquema base** | `0001-esquema.sql` reemplaza las 96 migraciones; se comparan los esquemas; se recrean la base de desarrollo y la desplegada | 2–3 días |
| **I3. Marca** | Marca genérica, marca de la instancia, colores en hoja aparte, logos del membrete desde la instancia | 2–3 días |
| **I4. Textos** | Las menciones de UMSA, FCPN, CMAT e IIMAT en `app/` salen de la configuración o de la instancia; una prueba impide que vuelvan | 2–4 días |
| **I5. Despliegue desde cero** | Guía de instalación para otra unidad, instalación de punta a punta probada, limpieza de `datos/` y de lo que ya no se usa | 1–2 días |

I1 e I2 van juntas en la práctica: el esquema base no puede cargar los planes si no existe el cargador.

## 4. Qué pasa con los otros dos pendientes

**2. Repartir los cálculos de los indicadores.** El riesgo principal desaparece: no hay cifras oficiales en uso que
puedan cambiar. Queda el riesgo normal de mover código, que cubren las pruebas de indicadores que ya existen más una
comparación antes y después sobre la instancia de ejemplo. Pasa de «no vale la pena» a «factible, unos 3 a 5 días».
Sigue siendo necesario solo si se hace el 3.

**3. Quitar la carpeta de un módulo apagado.** Empezar de cero no lo bloquea ni lo facilita mucho: lo que falta es
deshacer los cruces de código (el pendiente 2 y los de servicios con proyectos, oferta y empleadores) y que el
registro tolere que falte un paquete. El esquema seguiría completo aunque falte el código, por lo dicho en §2.2. Su
valor sigue siendo de distribución: repartir un paquete más chico.

Orden recomendado: 1 completo; después 2 y 3 juntos, solo si se quiere distribuir un núcleo reducido.

## 5. Decisiones que hacen falta antes de empezar

1. **Instancia de ejemplo:** ¿los planes y el marco de la Carrera de Matemática quedan en el repositorio público como
   ejemplo, o se arma un ejemplo ficticio y chico? Lo primero no obliga a tocar las pruebas; lo segundo, sí (unas 30
   dependen de asignaturas como MAT-111).
2. **Esquema base:** confirmar que se pueden borrar `data/tau.db` y la base desplegada. Es irreversible para esas
   bases.
3. **Historial de git:** ¿se conserva, o el repositorio público empieza con un historial nuevo? Empezar de nuevo
   resuelve de paso el archivo de la agencia que quedó en commits antiguos.
4. **Nombres técnicos:** ¿se mantienen `TAU_*` y `tau.db`? Es el único momento en que cambiarlos no cuesta una
   migración de configuración.
5. **Catálogo MSC2020:** su licencia sigue sin verificar. Puede pasar a ser un catálogo opcional de la instancia.
