# Instancias

Una **instancia** es la carpeta con lo propio de una unidad: sus unidades, su marca, sus planes de estudio, su marco de
calidad y sus catálogos. El sistema no trae esos datos en el código ni en el esquema (PLAN §74):
`scripts/instalar.py` los carga en una base nueva y `TAU_INSTANCIA` dice cuál rige mientras el sistema corre.

| Carpeta | Qué es |
|---|---|
| `ejemplo/` | Una carrera ficticia y chica. Es la instancia por omisión y el punto de partida para armar la propia |
| `cmat/` | La de la Carrera de Matemática (UMSA): planes 2017, marco de calidad, plan de mejora, líneas, MSC2020 y marca. **No se versiona en el repositorio público** (decisión del 17-nov-2026): vive en el equipo de desarrollo. La usan el seed, las capturas y las pruebas que dependen de sus datos |

Una instancia puede traer también su **manual de usuario** en `manual/` (capítulos, estilo y capturas; lo arma
`scripts/manual.py`): el de Matemática está en `cmat/manual/` y no se versiona. El plan para el del sistema genérico
está en `docs/manual-plan.md`.

La instancia de una unidad real vive **fuera del repositorio**. El formato de cada archivo y los pasos para instalar
están en `docs/despliegue.md` §3.
