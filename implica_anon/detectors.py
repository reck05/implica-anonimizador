"""Detección de entidades sensibles en texto.

Combina spaCy NER (empresas, personas) con regex (NIF/CIF/IBAN/direcciones).
Hace clustering de variantes ("Global Menta S.L." y "GlobalMenta" → mismo grupo).
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable

from rapidfuzz import fuzz

# --- Regex para identificadores estructurados ---

# CIF español: letra inicial (A-W exc I,Ñ,O,T) + 7 dígitos + dígito o letra de control
CIF_RE = re.compile(r"\b[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]\b")

# NIF/NIE: 8 dígitos + letra (NIF) o X/Y/Z + 7 dígitos + letra (NIE)
NIF_RE = re.compile(r"\b[XYZ]?\d{7,8}[A-HJ-NP-TV-Z]\b")

# IBAN español: ES + 22 dígitos (con o sin espacios cada 4)
IBAN_RE = re.compile(r"\bES\d{2}(?:[ -]?\d{4}){5}\b")

# Direcciones: prefijo + nombre de vía + número (obligatorio).
# Usamos [ \t] en vez de \s para no cruzar saltos de línea.
ADDRESS_RE = re.compile(
    r"\b(?:C/|Calle|Avenida|Avda\.?|Plaza|Pza\.?|Paseo|Ps\.?|Ronda|Carrer|Travesía|Carretera|Ctra\.?)[ \t]+"
    r"[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ.\- ]{2,60}?"
    r"(?:,[ \t]*\d+|[ \t]+\d+)(?:[A-Za-z])?"
    r"(?:[ \t]*,[ \t]*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ ]{2,40})?",
    re.UNICODE,
)

# Emails y teléfonos (bonus)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_ES_RE = re.compile(r"\b(?:\+?34[\s.-]?)?(?:6\d{2}|7[1-9]\d|9\d{2}|8\d{2})[\s.-]?\d{2,3}[\s.-]?\d{3}\b")


# Sufijos societarios que normalizamos al clusterizar
SOCIETY_SUFFIXES = (
    "s.l.u.", "s.l.u", "slu",
    "s.a.u.", "s.a.u", "sau",
    "s.l.", "s.l", "sl",
    "s.a.", "s.a", "sa",
    "s.coop.", "scoop", "s.coop",
    "s.l.l.", "sll",
    "s.l.p.", "slp",
    "ltd.", "ltd", "limited",
    "inc.", "inc",
    "corp.", "corp", "corporation",
    "gmbh", "ag", "bv", "nv",
)

# Términos genéricos que spaCy a veces marca como ORG/PER pero no son nombres reales.
# Headers de tabla, conceptos contables, abreviaturas fiscales, etc.
GENERIC_STOPWORDS = frozenset(
    s.lower()
    for s in [
        # Headers generales
        "Compañía", "Compañia", "Empresa", "Sociedad", "Cliente", "Proveedor",
        "Contacto", "Email", "Dirección", "Direccion", "Teléfono", "Telefono",
        "CIF", "NIF", "IBAN", "Razón Social", "Concepto", "Comentario",
        # Conceptos financieros
        "Ingresos", "Gastos", "EBITDA", "EBIT", "Resultado", "Margen",
        "Ventas", "Costes", "Coste", "Total", "Subtotal", "Beneficio",
        "Beneficios", "Pérdida", "Pérdidas", "Saldo", "Importe", "Cantidad",
        "Movimiento", "Movimientos", "Mvto", "Debe", "Haber", "Apertura",
        "Cierre", "Inicial", "Final", "Acumulado", "Periodo", "Período",
        "Ejercicio", "Trimestre", "Bimestre", "Semestre",
        # Tributos y abreviaturas fiscales/contables españolas
        "HP", "H.P.", "H.P", "HACIENDA", "Hacienda Pública", "Hacienda Publica",
        "SS", "S.S.", "Seguridad Social", "TGSS",
        "IS", "I.S.", "IRPF", "I.R.P.F.", "IVA", "I.V.A.",
        "IVA SOPORTADO", "IVA REPERCUTIDO", "REPERCUTIDO", "SOPORTADO",
        "IVA INTRACOMUNITARIO", "Intracomunitario",
        "Retención", "Retenciones", "Retencion",
        # Conceptos contables PGC
        "Activo", "Pasivo", "Patrimonio", "Patrimonio Neto", "PN",
        "Inmovilizado", "Amortización", "Amortizacion", "Provisión", "Provision",
        "Existencias", "Tesorería", "Tesoreria", "Caja", "Bancos",
        "Capital", "Reservas", "Aplicación", "Aplicacion",
        "Aplazamientos", "Préstamos", "Prestamos", "Créditos", "Creditos",
        "Anticipo", "Anticipos",
        # Gastos típicos
        "Publicidad", "Propaganda", "Marketing", "Suministros", "Material",
        "Materiales", "Oficina", "Decoración", "Decoracion", "Mobiliario",
        "Tarjeta", "Tarjetas", "TPV", "Comisión", "Comision", "Comisiones",
        "Asesoría", "Asesoria", "Consultoría", "Consultoria",
        "Eventos", "Catering", "Ropa", "Real", "Casa",
        "Transporte", "Transportes", "TR", "Mob", "MOB", "Móvil",
        # Tipos varios
        "Año", "Mes", "Fecha", "Día", "Dia", "Semana",
        "Profundidad", "Central", "Sucursal", "Delegación", "Delegacion",
        "Persona", "Personal", "Profesional", "Profesionales",
        "C empresas", "C Empresas", "Para Impto Sdades", "Sdades", "Sociedades",
        "Ganancia", "Ganancias", "Aplazamiento",
        "Coop", "S.Coop", "Fundación", "Fundacion",
        # Etiquetas de mes-mes típicas en sumas y saldos mensualizados
        "Enero-Enero", "Febrero-Febrero", "Marzo-Marzo", "Abril-Abril",
        "Mayo-Mayo", "Junio-Junio", "Julio-Julio", "Agosto-Agosto",
        "Septiembre-Septiembre", "Octubre-Octubre", "Noviembre-Noviembre",
        "Diciembre-Diciembre",
        "Ene-Ene", "Feb-Feb", "Mar-Mar", "Abr-Abr", "May-May", "Jun-Jun",
        "Jul-Jul", "Ago-Ago", "Sep-Sep", "Oct-Oct", "Nov-Nov", "Dic-Dic",
        "Apertura-Ene", "Apertura-Feb", "Apertura-Mar", "Apertura-Abr",
        "Apertura-May", "Apertura-Jun", "Apertura-Jul", "Apertura-Ago",
        "Apertura-Sep", "Apertura-Oct", "Apertura-Nov", "Apertura-Dic",
        # Monedas/unidades
        "Euros", "Euro", "€", "EUR", "Dólares", "Dolares", "USD",
        # Otras palabras frecuentes en exports que NO son nombres propios
        "Inmob", "Inmobiliaria", "Arte", "Arte Hortensia Herrero",
    ]
)

# Regex patterns para descartar strings que parecen fórmula o referencia rota
FORMULA_PATTERNS = [
    re.compile(r"^\s*=", re.IGNORECASE),
    re.compile(r"\b(SUMIFS|SUMIF|VLOOKUP|HLOOKUP|INDEX|MATCH|IFERROR|SUBSTITUTE|CONCATENATE|ROUND|AVERAGE)\s*\(", re.IGNORECASE),
    re.compile(r"!\$?[A-Z]+\$?\d*(:\$?[A-Z]+\$?\d*)?"),  # referencias Hoja!$A:$A
    re.compile(r"^\$?[A-Z]{1,3}\$?\d+(\s*[+\-*/]\s*\$?[A-Z]{1,3}\$?\d+)+$"),  # A1+B2
    re.compile(r"^\$?[A-Z]{1,3}\$?\d+$"),  # solo una ref tipo A10, AB141
    re.compile(r"^Agregado!", re.IGNORECASE),
]

# Referencias documentales (facturas, albaranes, pedidos...). NO son nombres de empresa.
# El nombre de la empresa es lo que se anonimiza; el número de factura NO.
DOC_PREFIXES = frozenset([
    "factura", "facturas", "fact", "fac", "fra", "fras",
    "albaran", "albarán", "albaranes", "pedido", "pedidos",
    "presupuesto", "presupuestos", "ticket", "recibo", "recibos", "abono",
    "ref", "referencia", "asiento", "apunte", "documento", "nº", "núm", "num", "n.º",
])
# Código tipo factura: "FAC-PRE25-00761", "ALB/2025-001", "PRE25-04761"
DOC_CODE_RE = re.compile(r"[A-Za-z]{2,}[-/][A-Za-z0-9]*\d{2,}")
# 5+ dígitos seguidos = número de documento/referencia (las empresas con año tienen 4)
MANY_DIGITS_RE = re.compile(r"\d{5,}")


def _is_document_ref(text: str) -> bool:
    """True si el texto es una referencia de factura/albarán/pedido, no un nombre."""
    s = text.strip()
    if not s:
        return False
    tokens = s.split()
    if tokens:
        first = tokens[0].lower().strip(".:#-º")
        if first in DOC_PREFIXES:
            return True
    if DOC_CODE_RE.search(s):
        return True
    if MANY_DIGITS_RE.search(s):
        return True
    return False


def _looks_like_excel_artifact(text: str) -> bool:
    """True si el texto huele a artefacto de Excel (fórmula, referencia, fragmento)
    o a referencia documental (factura, albarán...)."""
    if not text or len(text) < 2:
        return True
    s = text.strip()
    for pat in FORMULA_PATTERNS:
        if pat.search(s):
            return True
    # Referencias documentales (facturas, albaranes, pedidos): no son empresas
    if _is_document_ref(s):
        return True
    # Strings cortos de 1-3 chars en mayúsculas con dígitos = referencia rota
    if re.fullmatch(r"[A-Z]{1,3}\d{1,4}", s):
        return True
    # Strings que son sólo símbolos/operadores
    if re.fullmatch(r"[+\-*/=\s\$\(\)]+", s):
        return True
    return False


# Nombres propios españoles muy comunes — si aparecen sueltos (sin apellido) son ruido.
COMMON_GIVEN_NAMES = frozenset(s.lower() for s in [
    "Juan", "María", "Maria", "José", "Jose", "Antonio", "Manuel", "Francisco",
    "David", "Daniel", "Carlos", "Javier", "Pedro", "Alejandro", "Miguel",
    "Pablo", "Sergio", "Jorge", "Luis", "Andrés", "Andres", "Rafael", "Ángel",
    "Angel", "Adrián", "Adrian", "Diego", "Iván", "Ivan", "Rubén", "Ruben",
    "Carmen", "Ana", "Isabel", "Pilar", "Cristina", "Laura", "Marta", "Lucía",
    "Lucia", "Elena", "Patricia", "Sara", "Andrea", "Beatriz", "Rocío", "Rocio",
    "Sandra", "Carolina", "Clara", "Alba", "Belén", "Belen", "Adriana", "Ada",
    "Natalia", "Eva", "Silvia", "Raquel", "Mónica", "Monica", "Nuria",
    "Hortensia",
])


def _is_lone_first_name(text: str) -> bool:
    """True si el texto es un solo nombre propio frecuente, sin apellido."""
    s = text.strip()
    tokens = s.split()
    if len(tokens) != 1:
        return False
    return tokens[0].lower() in COMMON_GIVEN_NAMES

# Prefijos contables/de columna que spaCy puede pegar al nombre de la empresa
# ("Ingresos Tropical Frutas" → queremos solo "Tropical Frutas")
ACCOUNTING_PREFIXES = (
    "Ingresos", "Gastos", "EBITDA", "EBIT", "Resultado", "Margen",
    "Ventas", "Costes", "Coste", "Cliente", "Proveedor", "Total", "Subtotal",
    "Importe", "Cantidad",
)


@dataclass
class Candidate:
    """Una entidad detectada en el texto."""
    text: str
    kind: str  # "ORG" | "PER" | "CIF" | "NIF" | "IBAN" | "ADDRESS" | "EMAIL" | "PHONE"
              # | "CLIENTE" | "PROVEEDOR" | "DEUDOR" | "PERSONA" | "GRUPO" | "BANCO"
    count: int = 1
    source: str = "ner"  # "ner" | "regex" | "pgc"
    account_code: str | None = None  # Solo para candidatos PGC: el código de cuenta


@dataclass
class Cluster:
    """Grupo de variantes que se refieren a la misma entidad."""
    kind: str
    canonical: str  # la variante "más completa"
    variants: list[str] = field(default_factory=list)
    total_count: int = 0
    account_codes: list[str] = field(default_factory=list)  # códigos PGC asociados


def _strip_accounting_prefix(name: str) -> str:
    """Quita prefijos contables como 'Ingresos Tropical Frutas' → 'Tropical Frutas'."""
    for prefix in ACCOUNTING_PREFIXES:
        if name.lower().startswith(prefix.lower() + " "):
            return name[len(prefix) + 1 :].strip()
    return name


def normalize_org(name: str) -> str:
    """Normaliza nombre de empresa para clustering: minúsculas, sin sufijos societarios,
    sin prefijos contables, sin espacios para tolerar 'GlobalMenta' vs 'Global Menta'."""
    n = _strip_accounting_prefix(name).lower().strip()
    n = re.sub(r"[,;:.]+$", "", n)
    for suffix in SOCIETY_SUFFIXES:
        if n.endswith(" " + suffix):
            n = n[: -len(suffix) - 1].strip()
            break
        if n.endswith("," + suffix):
            n = n[: -len(suffix) - 1].strip()
            break
    # Colapsar espacios para que "GlobalMenta" ≈ "Global Menta"
    n_compact = re.sub(r"\s+", "", n)
    return n_compact


def normalize_person(name: str) -> str:
    return re.sub(r"\s+", " ", name.lower().strip())


# Razón por la que spaCy no está disponible (para avisar en la UI). None = disponible.
NLP_UNAVAILABLE_REASON: str | None = None


@lru_cache(maxsize=1)
def _load_nlp():
    """Carga spaCy en español. Devuelve el modelo, o None si no está disponible.

    NO lanza excepción: si spaCy no está instalado, el modelo no se puede
    descargar, o el sistema lo bloquea (p.ej. Application Control de Windows),
    devuelve None y el detector cae a heurísticas regex (`_heuristic_entities`).
    Así la herramienta funciona aunque spaCy esté bloqueado.
    """
    global NLP_UNAVAILABLE_REASON
    try:
        import spacy
    except Exception as e:  # ImportError, o DLL bloqueado al importar
        NLP_UNAVAILABLE_REASON = f"spaCy no se pudo importar ({type(e).__name__}). Usando detector heurístico."
        return None

    model_name = "es_core_news_md"
    try:
        return spacy.load(model_name)
    except OSError:
        # Modelo no instalado — intentar descargar al vuelo (~40MB)
        import subprocess
        import sys
        try:
            subprocess.run(
                [sys.executable, "-m", "spacy", "download", model_name],
                check=True,
                capture_output=True,
                timeout=300,
            )
            return spacy.load(model_name)
        except Exception as e:
            NLP_UNAVAILABLE_REASON = (
                f"No se pudo cargar/descargar el modelo es_core_news_md "
                f"({type(e).__name__}). Usando detector heurístico."
            )
            return None
    except Exception as e:
        # Cualquier otro fallo (DLL bloqueado por Application Control, etc.)
        NLP_UNAVAILABLE_REASON = (
            f"spaCy no se pudo cargar ({type(e).__name__}). Usando detector heurístico."
        )
        return None


# --- Detector heurístico de respaldo (sin spaCy) ---

# Empresas: nombre + sufijo societario. Alta precisión.
HEURISTIC_ORG_RE = re.compile(
    r"\b([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ&./\- ]{1,70}?)"
    r"[,\s]+"
    r"(S\.?L\.?U\.?|S\.?A\.?U\.?|S\.?L\.?L\.?|S\.?L\.?P\.?|S\.?L\.?|S\.?A\.?|"
    r"S\.?Coop\.?|S\.?C\.?P\.?|S\.?C\.?|Ltda?\.?|Limited|Inc\.?|Corp\.?|GmbH|AG|BV|NV|PLC)"
    r"(?=\s|$|[,;:.)\"'\n])",
    re.UNICODE,
)

# Empresas en MAYÚSCULAS: 2+ palabras de 3+ letras todas en mayúsculas.
HEURISTIC_UPPER_RE = re.compile(
    r"\b([A-ZÁÉÍÓÚÑ]{3,}(?:[ &\-][A-ZÁÉÍÓÚÑ]{2,}){1,5})\b"
)


def _heuristic_entities(texts: Iterable[str]) -> tuple[Counter, Counter]:
    """Detecta empresas y personas sin spaCy, por reglas.

    Conservador: prioriza precisión (pocos falsos positivos) sobre cobertura,
    porque el usuario revisa la tabla. Cubre el caso de spaCy bloqueado.
    """
    org_counts: Counter[str] = Counter()
    per_counts: Counter[str] = Counter()

    # Procesar cada texto único una sola vez (los Excel repiten mucho el mismo valor)
    for text in dict.fromkeys(t for t in texts if t):
        if not text:
            continue

        # Empresas con sufijo societario (nombre completo CON sufijo)
        for m in HEURISTIC_ORG_RE.finditer(text):
            full = m.group(0).strip().rstrip(",")
            name_part = m.group(1).strip()
            if name_part.lower() in GENERIC_STOPWORDS:
                continue
            if _looks_like_excel_artifact(full):
                continue
            org_counts[full] += 1

        # Empresas en MAYÚSCULAS (sin sufijo): "DISTRIBUCIONES BADIA"
        for m in HEURISTIC_UPPER_RE.finditer(text):
            val = m.group(1).strip()
            if val.lower() in GENERIC_STOPWORDS:
                continue
            # Evitar capturar cabeceras tipo "SALDO INICIAL", "TOTAL DEBE"
            tokens = val.split()
            if all(t.lower() in GENERIC_STOPWORDS for t in tokens):
                continue
            if _looks_like_excel_artifact(val):
                continue
            org_counts[val] += 1

        # Personas: nombre común español + 1-2 apellidos capitalizados
        tokens = text.split()
        i = 0
        while i < len(tokens):
            tok = tokens[i].strip(".,;:()\"'")
            if tok.lower() in COMMON_GIVEN_NAMES:
                # recoger apellidos siguientes capitalizados
                name_parts = [tok]
                j = i + 1
                while j < len(tokens) and j < i + 3:
                    nxt = tokens[j].strip(".,;:()\"'")
                    if nxt and nxt[0:1].isupper() and nxt.lower() not in GENERIC_STOPWORDS and nxt.isalpha():
                        name_parts.append(nxt)
                        j += 1
                    else:
                        break
                if len(name_parts) >= 2:  # nombre + al menos 1 apellido
                    per_counts[" ".join(name_parts)] += 1
                i = j
            else:
                i += 1

    return org_counts, per_counts


def detect_candidates(
    texts: Iterable[str],
    *,
    skip_ner: bool = False,
) -> list[Candidate]:
    """Detecta candidatos en una lista de strings (celdas, párrafos).

    `skip_ner=True` ejecuta solo regex (CIF/NIF/IBAN/email/teléfono/dirección)
    y omite spaCy. Útil cuando ya tienes el detector PGC dándote las
    empresas/personas con 100% de cobertura y no quieres que spaCy meta ruido.

    Si `skip_ner=False` pero spaCy no está disponible (bloqueado/ausente), cae
    a un detector heurístico por reglas en vez de spaCy.
    """
    nlp = None if skip_ner else _load_nlp()
    # Si queremos NER pero spaCy no carga, usamos heurística regex.
    use_heuristic = (not skip_ner) and (nlp is None)

    org_counts: Counter[str] = Counter()
    per_counts: Counter[str] = Counter()
    structured: dict[str, set[str]] = defaultdict(set)

    full_text = "\n".join(t for t in texts if t)

    # Regex primero — son rápidos y deterministas
    for m in CIF_RE.finditer(full_text):
        structured["CIF"].add(m.group())
    for m in NIF_RE.finditer(full_text):
        val = m.group()
        # Evitar duplicar con CIF (los CIF empiezan por letras válidas)
        if val not in structured.get("CIF", set()):
            structured["NIF"].add(val)
    for m in IBAN_RE.finditer(full_text):
        structured["IBAN"].add(m.group())
    for m in ADDRESS_RE.finditer(full_text):
        structured["ADDRESS"].add(m.group().strip())
    for m in EMAIL_RE.finditer(full_text):
        structured["EMAIL"].add(m.group())
    for m in PHONE_ES_RE.finditer(full_text):
        structured["PHONE"].add(m.group().strip())

    # Pre-computar valores estructurados para descartar coincidencias en NER
    structured_values: set[str] = set()
    for values in structured.values():
        structured_values.update(values)

    if skip_ner:
        # Modo regex-only (PGC ya cubre empresas/personas): salimos sin NER
        candidates: list[Candidate] = []
        for kind, values in structured.items():
            for value in values:
                count = full_text.count(value)
                candidates.append(Candidate(text=value, kind=kind, count=count, source="regex"))
        return candidates

    if use_heuristic:
        # Fallback sin spaCy: detección por reglas
        h_orgs, h_pers = _heuristic_entities(texts)
        for value, cnt in h_orgs.items():
            if value.lower() in GENERIC_STOPWORDS or value in structured_values:
                continue
            org_counts[value] += cnt
        for value, cnt in h_pers.items():
            if value.lower() in GENERIC_STOPWORDS:
                continue
            per_counts[value] += cnt

    # spaCy para ORG y PER (solo si está disponible).
    # Optimización clave: procesar cada texto ÚNICO una sola vez (los Excel repiten
    # muchísimo el mismo nombre) + por lotes (nlp.pipe) + desactivando los
    # componentes que no usamos (solo necesitamos NER). Esto baja de ~23s a ~2-3s.
    if nlp is not None:
        unique_texts = list(dict.fromkeys(
            t for t in texts if t and len(t) <= 100_000
        ))
        keep = {"ner", "tok2vec", "transformer"}
        disable = [p for p in nlp.pipe_names if p not in keep]
        docs_iter = nlp.pipe(unique_texts, batch_size=64, disable=disable)
    else:
        docs_iter = []
    for doc in docs_iter:
        for ent in doc.ents:
            label = ent.label_
            value = ent.text.strip(" .,;:\"'()")
            if not value or len(value) < 2:
                continue
            # Descartar si coincide con identificador estructurado
            if value in structured_values:
                continue
            # Descartar si es exactamente un CIF/NIF/IBAN/email/phone (spaCy a veces los marca PER)
            if (
                CIF_RE.fullmatch(value)
                or NIF_RE.fullmatch(value)
                or IBAN_RE.fullmatch(value)
                or EMAIL_RE.fullmatch(value)
            ):
                continue
            # Descartar términos genéricos
            if value.lower() in GENERIC_STOPWORDS:
                continue
            # Descartar artefactos de Excel (fórmulas, referencias)
            if _looks_like_excel_artifact(value):
                continue
            # Descartar nombres propios sueltos sin apellido
            if _is_lone_first_name(value):
                continue
            # Descartar valores puramente numéricos o demasiado cortos sin info
            if value.replace(" ", "").isdigit():
                continue

            if label == "ORG":
                # Limpiar prefijo contable
                cleaned = _strip_accounting_prefix(value)
                if cleaned.lower() in GENERIC_STOPWORDS:
                    continue
                org_counts[cleaned] += 1
            elif label == "PER":
                per_counts[value] += 1
            elif label == "LOC" and any(
                value.startswith(p) for p in ("C/", "Calle", "Avenida", "Plaza", "Paseo")
            ):
                structured["ADDRESS"].add(value)

    # Expandir cada ORG con sus apariciones que incluyen sufijo societario.
    # spaCy a menudo recorta el sufijo ("Global Menta" en vez de "Global Menta S.L.")
    # pero queremos reemplazar también la versión con sufijo.
    expanded_orgs = dict(org_counts)
    # Lookahead en vez de \b porque \b backtrackea para evitar consumir el punto final.
    suffix_pattern = re.compile(
        r"[ \t]*,?[ \t]*(?:S\.?L\.?U\.?|S\.?A\.?U\.?|S\.?L\.?L\.?|S\.?L\.?P\.?|S\.?L\.?|S\.?A\.?|S\.?Coop\.?|Ltd\.?|Inc\.?|Corp\.?|GmbH|AG|BV|NV)(?=\s|$|[,;:\)\"\']|$)",
        re.IGNORECASE,
    )
    for org in list(org_counts.keys()):
        # Buscar ocurrencias de "ORG <sufijo>" en el texto
        pattern = re.compile(re.escape(org) + suffix_pattern.pattern, re.IGNORECASE)
        for m in pattern.finditer(full_text):
            full_variant = m.group(0).strip().rstrip(",")
            if full_variant != org and full_variant not in expanded_orgs:
                expanded_orgs[full_variant] = full_text.count(full_variant)

    candidates: list[Candidate] = []
    for text, count in expanded_orgs.items():
        candidates.append(Candidate(text=text, kind="ORG", count=count, source="ner"))
    for text, count in per_counts.items():
        candidates.append(Candidate(text=text, kind="PER", count=count, source="ner"))
    for kind, values in structured.items():
        for value in values:
            count = full_text.count(value)
            candidates.append(Candidate(text=value, kind=kind, count=count, source="regex"))

    # Capa OPCIONAL GLiNER (solo en modo NER / texto libre, nunca en PGC).
    # Desactivada por defecto; añade candidatos nuevos sin tocar el resto.
    candidates.extend(_gliner_candidates(full_text, candidates))

    return candidates


def _gliner_candidates(full_text: str, existing: list[Candidate]) -> list[Candidate]:
    """Augmentación opcional con GLiNER. Devuelve [] si está desactivado o no
    disponible. Deduplica contra los candidatos ya detectados (spaCy/regex/heurística)
    y aplica los mismos filtros de ruido. NUNCA rompe el pipeline."""
    try:
        from . import gliner_detector
    except Exception:
        return []
    if not gliner_detector.is_enabled():
        return []
    try:
        raw = gliner_detector.detect_gliner_entities(full_text)
    except Exception:
        return []
    if not raw:
        return []

    existing_norm = {c.text.strip().lower() for c in existing}
    seen: set = set()
    out: list[Candidate] = []
    for text, label, _score in raw:
        t = text.strip()
        key = t.lower()
        if not t or key in existing_norm or key in seen:
            continue  # dedup vs spaCy/regex y vs sí mismo
        if key in GENERIC_STOPWORDS or _looks_like_excel_artifact(t):
            continue  # mismos filtros de ruido que el resto
        kind = gliner_detector.GLINER_LABEL_TO_KIND.get(label, "ORG")
        seen.add(key)
        out.append(
            Candidate(
                text=t,
                kind=kind,
                count=full_text.count(t) or 1,
                source=f"gliner:{label}",  # etiqueta fina M&A para trazabilidad
            )
        )
    return out


def _same_entity_norm(na: str, nb: str) -> bool:
    """Igual que `_maybe_same_entity` pero recibe nombres YA normalizados
    (compactados por `normalize_org`, sin espacios). Evita re-normalizar en
    cada comparación — crítico para el rendimiento de `suggest_unifications`,
    que compara muchos pares dentro de un mismo bloque."""
    if not na or not nb or na == nb:
        return False
    short, lng = sorted([na, nb], key=len)
    # 1) Abreviatura/prefijo: el corto (≥4 chars) es prefijo del largo. Muy fiable:
    #    "mercad" → "mercadona", "distrib" → "distribuciones".
    if len(short) >= 4 and lng.startswith(short):
        return True
    # 2) Fuzzy SOLO para nombres con cuerpo (≥6 chars) y banda ALTA (typos reales),
    #    con token_sort_ratio (no token_set, que es demasiado permisivo con siglas
    #    cortas y agrupaba 'ORIOL' con 'BRICOL'). Por debajo de 6 chars, solo prefijo.
    if len(short) >= 6:
        score = fuzz.token_sort_ratio(na, nb)
        if 82 <= score < 95:
            return True
    return False


def _maybe_same_entity(a: str, b: str) -> bool:
    """Heurística para SUGERIR (no decidir) que dos nombres son la misma entidad.

    Más laxa que el clustering automático (umbral 90): captura la zona gris
    (similitud media o abreviaturas tipo 'Mercad' → 'Mercadona') para que el
    humano confirme. NO se aplica automáticamente — solo genera sugerencias.
    """
    return _same_entity_norm(normalize_org(a), normalize_org(b))


# Kinds que SÍ son nombres y tiene sentido sugerir unificar (empresas/personas).
# Los identificadores estructurados (CIF/NIF/IBAN/email/teléfono/dirección) son
# valores únicos: NUNCA se "unifican" por parecido — dos CIF que difieren en un
# dígito NO son la misma entidad. Excluirlos también evita el coste de comparar
# miles de CIF casi idénticos por fuzzy.
_UNIFIABLE_KINDS = frozenset({
    "ORG", "PER", "CLIENTE", "PROVEEDOR", "DEUDOR", "PERSONA", "GRUPO", "BANCO",
})


def suggest_unifications(entries: list[tuple]) -> list[list]:
    """Agrupa candidatos que PODRÍAN ser la misma entidad (para sugerir al usuario).

    `entries`: lista de (id, kind, nombre). Devuelve grupos [[id, id, ...]] con
    2+ miembros del mismo kind que parecen la misma empresa pero que el
    clustering automático no unió. El usuario decide si unificarlos.

    Solo considera nombres (empresas/personas); los identificadores estructurados
    (CIF/NIF/IBAN/email/teléfono/dirección) se ignoran — son valores únicos.
    """
    # Índice por bloque (kind + primeros 2 chars del nombre normalizado) para no
    # comparar todos contra todos en cada rerun de la UI. Casi O(n). El coste real
    # estaba en re-normalizar ambos nombres en cada comparación; ahora usamos el
    # `nm` ya cacheado (`_same_entity_norm`), así que el bloque de 2 chars vuela.
    norm_map: dict = {}
    by_block: dict = defaultdict(list)
    order: list = []
    for id_, kind, name in entries:
        if kind not in _UNIFIABLE_KINDS:
            continue  # CIF/NIF/IBAN/... no se sugieren para unificar
        nm = normalize_org(name)
        norm_map[id_] = (kind, name, nm)
        order.append(id_)
        if nm:
            by_block[(kind, nm[:2])].append(id_)

    # Salvaguarda anti-cuelgue: un bloque enorme (miles de nombres casi idénticos)
    # daría O(n²) dentro del bloque. Por encima de este tamaño no sugerimos para ese
    # bloque — las sugerencias son una comodidad opcional, no deben colgar la UI.
    MAX_BLOCK = 600

    groups: list[list] = []
    used: set = set()
    for id_a in order:
        if id_a in used:
            continue
        kind_a, name_a, nm_a = norm_map[id_a]
        if not nm_a:
            continue
        block = by_block.get((kind_a, nm_a[:2]), ())
        if len(block) > MAX_BLOCK:
            continue
        group = [id_a]
        for id_b in block:  # solo el mismo bloque
            if id_b == id_a or id_b in used:
                continue
            if _same_entity_norm(nm_a, norm_map[id_b][2]):  # norm ya cacheado
                group.append(id_b)
        if len(group) > 1:
            groups.append(group)
            used.update(group)
    return groups


def candidates_from_pgc(scan_result) -> list[Candidate]:
    """Convierte un AccountingScanResult en candidatos directamente.

    Esto bypasea completamente spaCy: el código de cuenta es autoritativo —
    si una cuenta empieza por 430, su descripción ES un cliente, punto.

    Returns candidatos con kinds específicos del PGC (CLIENTE/PROVEEDOR/etc.)
    y account_code propagado para poder generar codenames basados en cuenta.
    """
    from .accounting import clean_description

    # Agrupar por (kind, texto_limpio) y mantener los códigos asociados
    grouped: dict[tuple[str, str], dict] = {}
    for entity in scan_result.entities:
        cleaned = clean_description(entity.kind, entity.description)
        if not cleaned:
            continue
        key = (entity.kind, cleaned)
        if key not in grouped:
            grouped[key] = {"count": 0, "codes": []}
        grouped[key]["count"] += 1
        if entity.code and entity.code not in grouped[key]["codes"]:
            grouped[key]["codes"].append(entity.code)

    candidates = []
    for (kind, text), info in grouped.items():
        # Si hay múltiples códigos, usamos el primero (más relevante)
        account_code = info["codes"][0] if info["codes"] else None
        candidates.append(
            Candidate(
                text=text,
                kind=kind,
                count=info["count"],
                source="pgc",
                account_code=account_code,
            )
        )
    return candidates


def cluster_variants(
    candidates: list[Candidate], threshold: int = 90
) -> list[Cluster]:
    """Agrupa candidatos del mismo kind cuyos nombres son fuzzy-similar.

    Los kinds estructurados (CIF/NIF/IBAN/EMAIL/PHONE) no se clusterizan — cada valor es único.

    Los kinds PGC (CLIENTE/PROVEEDOR/...) sí se clusterizan, pero también pasan
    por el cross-kind ORG dedup al final por si spaCy también los detectó.
    """
    structured_kinds = {"CIF", "NIF", "IBAN", "EMAIL", "PHONE", "ADDRESS"}
    org_like_kinds = {"ORG", "CLIENTE", "PROVEEDOR", "DEUDOR", "GRUPO", "BANCO"}

    by_kind: dict[str, list[Candidate]] = defaultdict(list)
    for c in candidates:
        by_kind[c.kind].append(c)

    clusters: list[Cluster] = []

    for kind, items in by_kind.items():
        if kind in structured_kinds:
            for c in items:
                clusters.append(
                    Cluster(
                        kind=kind,
                        canonical=c.text,
                        variants=[c.text],
                        total_count=c.count,
                        account_codes=[c.account_code] if c.account_code else [],
                    )
                )
            continue

        # Para ORG-like/PER-like: fuzzy clustering con ÍNDICE POR BLOQUES.
        # En vez de comparar cada nombre contra todos (O(n²) + normalizar en cada
        # comparación, que colgaba el servidor con cientos de nombres), normalizamos
        # UNA vez y solo comparamos contra clusters del mismo bloque (primeros 2
        # caracteres del nombre normalizado) y de longitud parecida → casi O(n).
        is_org_like = kind in org_like_kinds
        normalize = normalize_org if is_org_like else normalize_person
        items_sorted = sorted(items, key=lambda c: (-len(c.text), -c.count))
        clusters_for_kind: list[Cluster] = []
        blocks: dict[str, list[dict]] = defaultdict(list)  # bkey -> [{cluster, norm}]

        for cand in items_sorted:
            norm = normalize(cand.text)
            if not norm:
                continue
            # Menos de 5 chars tras normalizar (genéricos como "asociados" sin sufijo)
            # → cluster propio sin fuzzy, evita falsas fusiones.
            skip_fuzzy = len(norm) < 5

            matched = None
            if not skip_fuzzy:
                bkey = norm[:2]
                for entry in blocks.get(bkey, ()):  # solo el mismo bloque
                    cn = entry["norm"]  # norm del canónico, ya cacheado
                    if abs(len(cn) - len(norm)) > 6:
                        continue  # longitudes muy dispares → no es variante
                    if (fuzz.token_sort_ratio(norm, cn) >= threshold
                            and fuzz.ratio(norm, cn) >= threshold - 10):
                        matched = entry
                        break
            if matched:
                cl = matched["cluster"]
                cl.variants.append(cand.text)
                cl.total_count += cand.count
                if cand.account_code and cand.account_code not in cl.account_codes:
                    cl.account_codes.append(cand.account_code)
                if len(cand.text) > len(cl.canonical):
                    cl.canonical = cand.text  # el canónico cambia, su norm no re-indexa
            else:
                cl = Cluster(
                    kind=kind,
                    canonical=cand.text,
                    variants=[cand.text],
                    total_count=cand.count,
                    account_codes=[cand.account_code] if cand.account_code else [],
                )
                clusters_for_kind.append(cl)
                if not skip_fuzzy:
                    blocks[norm[:2]].append({"cluster": cl, "norm": norm})

        clusters.extend(clusters_for_kind)

    # Cross-source dedup: si una entidad detectada por PGC también la detectó NER,
    # mantenemos solo la versión PGC (que tiene la clasificación correcta CLIENTE/PROVEEDOR).
    # Comparamos por texto normalizado.
    pgc_kinds = {"CLIENTE", "PROVEEDOR", "DEUDOR", "PERSONA", "GRUPO", "BANCO"}
    pgc_texts_normalized: set[str] = set()
    for c in clusters:
        if c.kind in pgc_kinds:
            for v in c.variants:
                pgc_texts_normalized.add(normalize_org(v))
                pgc_texts_normalized.add(normalize_person(v))

    # Conjunto compactado (sin espacios) de los nombres autoritativos, para
    # detectar fragmentos que spaCy recortó: "sirena" ⊂ "lasirena" (LA SIRENA SL).
    pgc_compact = {n for n in pgc_texts_normalized if len(n) >= 4}

    deduped_clusters: list[Cluster] = []
    for c in clusters:
        if c.kind in ("ORG", "PER"):
            # ¿Alguna de sus variantes ya está en un cluster PGC/columna-nombre,
            # exacta o como fragmento contenido en un nombre más completo?
            in_pgc = False
            for v in c.variants:
                nv = normalize_org(v)
                if nv in pgc_texts_normalized or normalize_person(v) in pgc_texts_normalized:
                    in_pgc = True
                    break
                # Fragmento recortado por spaCy contenido en un nombre completo
                # autoritativo ("ALMACENES" ⊂ "RIVASALMACENES"). Solo descartamos si
                # es RARO (aparece <3 veces) y MUCHO más corto (<60% del nombre
                # completo): así no perdemos una empresa legítima corta que sea
                # frecuente o solo algo más corta que otra (p.ej. "Azul" cliente real
                # vs "Azul Marketing SL"). Prima NO perder cobertura (= no dejar
                # nombres sin anonimizar) sobre quitar una fila de ruido.
                if (len(nv) >= 4 and c.total_count < 3
                        and any(nv != pn and nv in pn and len(nv) < 0.6 * len(pn)
                                for pn in pgc_compact)):
                    in_pgc = True
                    break
            if in_pgc:
                continue  # descartamos el cluster NER, el autoritativo ya lo cubre
        deduped_clusters.append(c)
    clusters = deduped_clusters

    # Cross-kind ORG↔PER: si un cluster PER es muy similar a uno ORG, fusionar a ORG.
    # (spaCy a veces marca "GlobalMenta" como PER cuando es la empresa).
    org_clusters = [c for c in clusters if c.kind == "ORG"]
    per_clusters = [c for c in clusters if c.kind == "PER"]
    other_clusters = [c for c in clusters if c.kind not in ("ORG", "PER")]

    surviving_per: list[Cluster] = []
    for per in per_clusters:
        norm_per = normalize_org(per.canonical)  # usar normalize_org para comparar compactado
        matched_org = None
        for org in org_clusters:
            for variant in org.variants:
                score = fuzz.token_set_ratio(norm_per, normalize_org(variant))
                if score >= 90:
                    matched_org = org
                    break
            if matched_org:
                break
        if matched_org:
            matched_org.variants.extend(per.variants)
            matched_org.total_count += per.total_count
        else:
            surviving_per.append(per)

    clusters = org_clusters + surviving_per + other_clusters

    # Ordenar por relevancia
    clusters.sort(key=lambda c: (-c.total_count, c.canonical))
    return clusters
