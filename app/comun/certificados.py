"""Certificados que una persona emite de lo que hizo (tutorías y tribunales; PLAN §68, etapa 6, y §73): el código de
verificación y el formato que usan los aportes de cada módulo (punto `certificados`). No se guarda nada: el código se
calcula del tipo, del registro y de la persona."""
import hashlib


def codigo(tipo: str, ref: int, uid: int) -> str:
    return "TAU-" + hashlib.sha256(f"{tipo}:{ref}:{uid}".encode()).hexdigest()[:10].upper()


def cert(tipo: str, tipo_nombre: str, ref: int, uid: int, titulo: str, detalle: str, fecha: str | None, texto: str,
         **extra) -> dict:
    """`texto` completa «Se certifica que <persona> …» en la constancia impresa."""
    return {"tipo": tipo, "tipo_nombre": tipo_nombre, "ref": ref, "titulo": titulo, "detalle": detalle,
            "fecha": (fecha or "")[:10], "codigo": codigo(tipo, ref, uid), "usuario_id": uid, "texto": texto, **extra}
