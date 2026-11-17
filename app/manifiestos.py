"""Catálogo de módulos del sistema (PLAN §73): junta lo que declara cada paquete en su `modulo.py`.

Lo usan `main.py` al arrancar y los scripts que preparan una base (el seed). Un paquete nuevo se agrega a `PAQUETES`.
Vive aquí, y no en `app/comun`, porque `comun` no importa de los otros paquetes.
"""
from app.academico import modulo as academico
from app.calidad import modulo as calidad
from app.comun import modulo as comun
from app.comun import modulos
from app.egresados import modulo as egresados
from app.estudiantil import modulo as estudiantil
from app.ia import modulo as ia
from app.informes import modulo as informes
from app.investigacion import modulo as investigacion
from app.servicios import modulo as servicios

PAQUETES = (comun, investigacion, informes, academico, estudiantil, egresados, servicios, calidad, ia)


def registrar():
    for paquete in PAQUETES:
        modulos.registrar(*paquete.MODULOS)
