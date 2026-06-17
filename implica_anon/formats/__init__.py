from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import excel, word, pptx as pptx_mod, pdf


@dataclass
class VerifyResult:
    """Resultado de anonimizar + verificar un archivo.

    - surviving: nombres reales del mapping que SIGUEN visibles en el output (fuga).
    - verifiable: False si no se pudo comprobar (p.ej. escaneado sin texto).
    - warnings: avisos legibles para el usuario (imágenes, escaneo, etc.).
    """
    surviving: list[str] = field(default_factory=list)
    verifiable: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return self.verifiable and not self.surviving

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


def apply_replacements(src: Path, mapping: dict[str, str], dst: Path) -> VerifyResult:
    """Aplica los reemplazos y verifica el resultado.

    Devuelve un VerifyResult. El verify pass re-extrae el texto del archivo
    generado y comprueba que ningún nombre real quedó visible — cubre el caso
    en que un formato (p.ej. PDF) no encuentra una ocurrencia y la deja pasar.

    Detecta también el punto ciego: si el documento no tiene texto legible
    (escaneado / basado en imágenes), marca verifiable=False para no dar un
    falso "OK" — el contenido podría tener nombres que no se pueden tocar.
    """
    REPLACERS[src.suffix.lower()](src, mapping, dst)

    from ..replacer import Replacer

    result = VerifyResult()
    replacer = Replacer(mapping)
    try:
        out_texts = EXTRACTORS[dst.suffix.lower()](dst)
    except Exception:
        result.verifiable = False
        result.warnings.append(
            "No se pudo re-leer el archivo de salida para verificar. Revísalo a mano."
        )
        return result

    total_text_len = sum(len(t) for t in out_texts)
    surviving: set[str] = set()
    for t in out_texts:
        for original in replacer.find_surviving(t):
            surviving.add(original)
    result.surviving = sorted(surviving)

    # Punto ciego: documento sin texto legible (escaneado / solo imágenes)
    if total_text_len < 20 and src.stat().st_size > 10_000:
        result.verifiable = False
        result.warnings.append(
            "El documento no contiene texto legible (¿escaneado o basado en imágenes?). "
            "La anonimización de texto no puede actuar ni verificar — revísalo a mano "
            "o pásalo antes por un OCR."
        )

    # Aviso de imágenes en PDF (los nombres dentro de imágenes no se anonimizan)
    if dst.suffix.lower() == ".pdf":
        n_imgs = pdf.count_images(dst)
        if n_imgs:
            result.warnings.append(
                f"El PDF contiene {n_imgs} imagen(es). Si algún nombre aparece DENTRO "
                "de una imagen (logo, captura, escaneo), NO se anonimiza. Revísalas."
            )
        # Truncamiento por límite de páginas: lo que está más allá NO se procesó
        # NI se verificó → no demos un falso "OK".
        try:
            n_pages = pdf.page_count(src)
            if n_pages > pdf.MAX_PDF_PAGES:
                result.verifiable = False
                result.warnings.append(
                    f"El PDF tiene {n_pages} páginas y solo se procesaron las primeras "
                    f"{pdf.MAX_PDF_PAGES}. Las páginas {pdf.MAX_PDF_PAGES + 1}+ NO se "
                    "anonimizaron ni verificaron — divídelo y procésalo por partes."
                )
        except Exception:
            pass

    return result
