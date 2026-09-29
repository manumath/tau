"""Llenar una plantilla XLSX ajena sin alterarla: se editan solo las celdas indicadas, directamente
en el XML de cada hoja. openpyxl no sirve para esto porque al guardar descarta los gráficos y las
imágenes de la plantilla (la Guía de Antecedentes de IAC-CINDA trae ambos).

Lo demás (estilos, celdas combinadas, validaciones, gráficos, comentarios) queda como estaba. Al
abrir, Excel recalcula las fórmulas (`fullCalcOnLoad`); se quita la cadena de cálculo guardada y,
si se pide, los vínculos a libros externos.
"""
import io
import posixpath
import re
import zipfile

from lxml import etree
from openpyxl.formula.translate import Translator

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_CELDA = re.compile(r"^([A-Z]+)(\d+)$")
# Caracteres que XML 1.0 no admite (p. ej., controles pegados desde otro programa).
_INVALIDOS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _q(tag: str, ns: str = NS) -> str:
    return f"{{{ns}}}{tag}"


def columna_a_numero(col: str) -> int:
    n = 0
    for c in col:
        n = n * 26 + ord(c) - 64
    return n


def numero_a_columna(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class Plantilla:
    def __init__(self, contenido: bytes):
        self._zip = zipfile.ZipFile(io.BytesIO(contenido))
        self._archivos = {n: self._zip.read(n) for n in self._zip.namelist()}
        self._hojas = self._rutas_de_hojas()
        self._valores: dict[str, dict[str, object]] = {}
        self._formulas: dict[str, dict[str, str]] = {}
        self._sin_vinculos_externos = False

    def _rutas_de_hojas(self) -> dict[str, str]:
        libro = etree.fromstring(self._archivos["xl/workbook.xml"])
        rels = etree.fromstring(self._archivos["xl/_rels/workbook.xml.rels"])
        destino = {r.get("Id"): r.get("Target") for r in rels}
        rutas = {}
        for h in libro.iter(_q("sheet")):
            t = destino[h.get(_q("id", NS_R))]
            rutas[h.get("name")] = t.lstrip("/") if t.startswith("/") else posixpath.normpath(posixpath.join("xl", t))
        return rutas

    @property
    def hojas(self) -> list[str]:
        return list(self._hojas)

    def escribir(self, hoja: str, celda: str, valor):
        """Texto, número o None (vacía la celda). Una fórmula se escribe con `formula`."""
        if hoja not in self._hojas:
            raise KeyError(f"La plantilla no tiene la hoja «{hoja}»")
        self._valores.setdefault(hoja, {})[celda] = valor

    def formula(self, hoja: str, celda: str, texto: str):
        self._formulas.setdefault(hoja, {})[celda] = texto.lstrip("=")

    def valor_original(self, hoja: str, celda: str):
        """Lo que la plantilla trae en la celda: fórmula (con «=»), texto o número (None si nada)."""
        c = self._buscar_celda(etree.fromstring(self._archivos[self._hojas[hoja]]), celda)
        if c is None:
            return None
        f = c.find(_q("f"))
        if f is not None and f.text:
            return "=" + f.text
        if c.get("t") == "s":
            return self._compartidas()[int(c.findtext(_q("v")))]
        if c.get("t") == "inlineStr":
            return "".join(c.find(_q("is")).itertext())
        return c.findtext(_q("v"))

    def quitar_vinculos_externos(self):
        self._sin_vinculos_externos = True

    # --- Escritura --------------------------------------------------------------------------------

    def _compartidas(self) -> list[str]:
        if not hasattr(self, "_cache_compartidas"):
            raiz = etree.fromstring(self._archivos.get("xl/sharedStrings.xml", b"<sst xmlns='%s'/>" % NS.encode()))
            self._cache_compartidas = ["".join(si.itertext()) for si in raiz.iter(_q("si"))]
        return self._cache_compartidas

    @staticmethod
    def _buscar_celda(raiz, ref: str):
        m = _CELDA.match(ref)
        fila = raiz.find(f"{_q('sheetData')}/{_q('row')}[@r='{m.group(2)}']")
        return None if fila is None else fila.find(f"{_q('c')}[@r='{ref}']")

    @staticmethod
    def _fila(datos, numero: int):
        for f in datos.iter(_q("row")):
            r = int(f.get("r"))
            if r == numero:
                return f
            if r > numero:
                nueva = etree.Element(_q("row"), r=str(numero))
                f.addprevious(nueva)
                return nueva
        return etree.SubElement(datos, _q("row"), r=str(numero))

    @staticmethod
    def _ultima_numerada(datos) -> int | None:
        """Última fila de la tabla de la plantilla: la última con un número en la columna A (las
        tablas de las guías numeran sus filas 1, 2, 3…)."""
        ultima = None
        for f in datos.iter(_q("row")):
            a = f.find(f"{_q('c')}[@r='A{f.get('r')}']")
            if a is not None and a.get("t") is None and (a.findtext(_q("v")) or "").strip().isdigit():
                ultima = int(f.get("r"))
        return ultima

    @staticmethod
    def _estilo(datos, fila: int, col: str) -> str | None:
        f = datos.find(f"{_q('row')}[@r='{fila}']")
        c = None if f is None else f.find(f"{_q('c')}[@r='{col}{fila}']")
        return None if c is None else c.get("s")

    def _celda(self, datos, ref: str):
        col, num = _CELDA.match(ref).groups()
        fila = self._fila(datos, int(num))
        n = columna_a_numero(col)
        for c in fila.iter(_q("c")):
            ccol = _CELDA.match(c.get("r")).group(1)
            if ccol == col:
                return c
            if columna_a_numero(ccol) > n:
                nueva = etree.Element(_q("c"), r=ref)
                c.addprevious(nueva)
                break
        else:
            nueva = etree.SubElement(fila, _q("c"), r=ref)
        return nueva

    @staticmethod
    def _separar_compartida(datos, c):
        """Si la celda es la maestra de una fórmula compartida, escribe la fórmula explícita en cada
        celda que dependía de ella (si no, al sobrescribirla, Excel declararía el archivo dañado)."""
        f = c.find(_q("f"))
        if f is None or f.get("t") != "shared" or not f.get("ref") or not f.text:
            return
        si, origen = f.get("si"), c.get("r")
        for otra in datos.iter(_q("c")):
            g = otra.find(_q("f"))
            if otra is c or g is None or g.get("t") != "shared" or g.get("si") != si:
                continue
            g.text = Translator("=" + f.text, origin=origen).translate_formula(otra.get("r")).lstrip("=")
            for atributo in ("t", "si", "ref"):
                g.attrib.pop(atributo, None)

    @staticmethod
    def _limpiar(c):
        for hijo in list(c):
            c.remove(hijo)
        c.attrib.pop("t", None)

    def _aplicar(self, ruta: str, valores: dict, formulas: dict) -> bytes:
        raiz = etree.fromstring(self._archivos[ruta])
        datos = raiz.find(_q("sheetData"))
        # Filas que se agregan después de la tabla de la plantilla: con el formato de su última fila.
        modelo = self._ultima_numerada(datos)
        for ref in [*valores, *formulas]:
            col, num = _CELDA.match(ref).groups()
            if modelo and int(num) > modelo:
                estilo = self._estilo(datos, modelo, col)
                if estilo:
                    self._celda(datos, ref).set("s", estilo)
        for ref, v in valores.items():
            c = self._celda(datos, ref)
            self._separar_compartida(datos, c)
            self._limpiar(c)
            if v is None or v == "":
                continue
            if isinstance(v, bool):
                v = "Sí" if v else "No"
            if isinstance(v, (int, float)):
                etree.SubElement(c, _q("v")).text = repr(v) if isinstance(v, float) else str(v)
            else:
                c.set("t", "inlineStr")
                t = etree.SubElement(etree.SubElement(c, _q("is")), _q("t"))
                t.text = _INVALIDOS.sub("", str(v))
                if t.text != t.text.strip():
                    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        for ref, f in formulas.items():
            c = self._celda(datos, ref)
            self._separar_compartida(datos, c)
            self._limpiar(c)
            etree.SubElement(c, _q("f")).text = f
        for f in datos.iter(_q("row")):
            f.attrib.pop("spans", None)   # pista opcional de columnas; puede quedar desactualizada
        ultima = max((int(f.get("r")) for f in datos.iter(_q("row"))), default=1)
        dim = raiz.find(_q("dimension"))
        if dim is not None and ":" in dim.get("ref", ""):
            ini, fin = dim.get("ref").split(":")
            col, num = _CELDA.match(fin).groups()
            if int(num) < ultima:
                dim.set("ref", f"{ini}:{col}{ultima}")
        return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)

    def _sin_cadena_de_calculo(self):
        """Quita calcChain (Excel la rehace) y pide recalcular todo al abrir."""
        self._archivos.pop("xl/calcChain.xml", None)
        self._quitar_relacion("xl/_rels/workbook.xml.rels", "calcChain")
        self._quitar_tipo("/xl/calcChain.xml")
        libro = etree.fromstring(self._archivos["xl/workbook.xml"])
        calc = libro.find(_q("calcPr"))
        if calc is None:
            calc = etree.SubElement(libro, _q("calcPr"))
        calc.set("fullCalcOnLoad", "1")
        self._archivos["xl/workbook.xml"] = etree.tostring(libro, xml_declaration=True, encoding="UTF-8",
                                                           standalone=True)

    def _quitar_relacion(self, rels: str, tipo: str) -> list[str]:
        raiz = etree.fromstring(self._archivos[rels])
        quitados = []
        for r in list(raiz):
            if r.get("Type", "").endswith("/" + tipo):
                quitados.append(r.get("Id"))
                raiz.remove(r)
        self._archivos[rels] = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
        return quitados

    def _quitar_tipo(self, parte: str):
        raiz = etree.fromstring(self._archivos["[Content_Types].xml"])
        for o in list(raiz):
            if o.get("PartName") == parte:
                raiz.remove(o)
        self._archivos["[Content_Types].xml"] = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8",
                                                               standalone=True)

    def _quitar_externos(self):
        self._quitar_relacion("xl/_rels/workbook.xml.rels", "externalLink")
        libro = etree.fromstring(self._archivos["xl/workbook.xml"])
        ext = libro.find(_q("externalReferences"))
        if ext is not None:
            libro.remove(ext)
        self._archivos["xl/workbook.xml"] = etree.tostring(libro, xml_declaration=True, encoding="UTF-8",
                                                           standalone=True)
        for nombre in [n for n in self._archivos if n.startswith("xl/externalLinks/")]:
            del self._archivos[nombre]
            if not nombre.startswith("xl/externalLinks/_rels/"):
                self._quitar_tipo("/" + nombre)

    def guardar(self) -> bytes:
        for hoja in set(self._valores) | set(self._formulas):
            ruta = self._hojas[hoja]
            self._archivos[ruta] = self._aplicar(ruta, self._valores.get(hoja, {}), self._formulas.get(hoja, {}))
        self._sin_cadena_de_calculo()
        if self._sin_vinculos_externos:
            self._quitar_externos()
        salida = io.BytesIO()
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
            # [Content_Types].xml primero, como lo escribe Excel.
            for nombre in sorted(self._archivos, key=lambda n: n != "[Content_Types].xml"):
                z.writestr(nombre, self._archivos[nombre])
        return salida.getvalue()
