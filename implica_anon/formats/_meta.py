"""Metadatos del documento (propiedades core) — extracción y limpieza.

Los metadatos (autor, empresa, título, asunto, palabras clave...) son una fuga
SILENCIOSA: aunque anonimices el cuerpo del documento, el fichero sale con el
nombre real del autor/analista y a veces del cliente en sus propiedades, y la UI
no lo muestra. Cualquiera puede verlo en «Propiedades» del archivo o con exiftool.

Política:
- Campos de IDENTIDAD (autor, last_modified_by) → se VACÍAN (un entregable
  anonimizado no debe llevar autoría real).
- Campos DESCRIPTIVOS (título, asunto, keywords, comentarios, categoría) → se
  pasan por el mapping (si contienen un nombre mapeado, queda como codename).

`extract_core_props` los incluye en la extracción para que la detección los vea y,
sobre todo, para que el verify pass los re-lea y avise si algo quedó sin anonimizar.
"""
from __future__ import annotations

# Nombres de atributo distintos: python-docx/python-pptx (CoreProperties) vs openpyxl.
_FIELDS = {
    "core": {  # python-docx y python-pptx comparten estos nombres
        "identity": ("author", "last_modified_by"),
        "text": ("title", "subject", "keywords", "comments", "category"),
    },
    "openpyxl": {
        "identity": ("creator", "lastModifiedBy"),
        "text": ("title", "subject", "keywords", "description", "category"),
    },
}


def _spec(kind: str) -> dict:
    return _FIELDS["openpyxl"] if kind == "openpyxl" else _FIELDS["core"]


def extract_core_props(props, kind: str = "core") -> list[str]:
    """Valores string no vacíos de los metadatos, para detección + verify."""
    if props is None:
        return []
    spec = _spec(kind)
    out: list[str] = []
    for attr in spec["identity"] + spec["text"]:
        try:
            val = getattr(props, attr, None)
        except Exception:
            val = None
        if isinstance(val, str) and val.strip():
            out.append(val.strip())
    return out


def scrub_core_props(props, replacer, kind: str = "core") -> None:
    """Limpia metadatos antes de guardar: identidad → vacío; descriptivos → mapping."""
    if props is None:
        return
    spec = _spec(kind)
    for attr in spec["identity"]:
        try:
            if getattr(props, attr, None):
                setattr(props, attr, "")
        except Exception:
            pass
    for attr in spec["text"]:
        try:
            val = getattr(props, attr, None)
            if isinstance(val, str) and val.strip():
                new, _ = replacer.apply(val)
                setattr(props, attr, new)
        except Exception:
            pass
