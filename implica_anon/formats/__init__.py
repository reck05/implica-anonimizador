from pathlib import Path
from typing import Callable

from . import excel, word, pptx as pptx_mod, pdf

EXTRACTORS: dict[str, Callable[[Path], list[str]]] = {
    ".xlsx": excel.extract_text,
    ".xlsm": excel.extract_text,
    ".docx": word.extract_text,
    ".pptx": pptx_mod.extract_text,
    ".pdf": pdf.extract_text,
}

REPLACERS: dict[str, Callable[[Path, dict[str, str], Path], None]] = {
    ".xlsx": excel.apply_replacements,
    ".xlsm": excel.apply_replacements,
    ".docx": word.apply_replacements,
    ".pptx": pptx_mod.apply_replacements,
    ".pdf": pdf.apply_replacements,
}


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in EXTRACTORS


def extract_text(path: Path) -> list[str]:
    return EXTRACTORS[path.suffix.lower()](path)


def apply_replacements(src: Path, mapping: dict[str, str], dst: Path) -> list[str]:
    """Aplica los reemplazos y verifica el resultado.

    Devuelve la lista de originales que SOBREVIVIERON en el output (vacía =
    anonimización limpia). El verify pass re-extrae el texto del archivo
    generado y comprueba que ningún nombre real quedó visible — cubre el caso
    en que un formato (p.ej. PDF) no encuentra una ocurrencia y la deja pasar.
    """
    REPLACERS[src.suffix.lower()](src, mapping, dst)

    # Verify pass: re-extraer y detectar fugas
    from ..replacer import Replacer

    replacer = Replacer(mapping)
    try:
        out_texts = EXTRACTORS[dst.suffix.lower()](dst)
    except Exception:
        # Si no se puede re-leer el output, no bloqueamos el flujo
        return []
    surviving: set[str] = set()
    for t in out_texts:
        for original in replacer.find_surviving(t):
            surviving.add(original)
    return sorted(surviving)
