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


def _looks_like_excel_artifact(text: str) -> bool:
    """True si el texto huele a artefacto de Excel (fórmula, referencia, fragmento)."""
    if not text or len(text) < 2:
        return True
    s = text.strip()
    for pat in FORMULA_PATTERNS:
        if pat.search(s):
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


@lru_cache(maxsize=1)
def _load_nlp():
    """Carga spaCy en español. Cacheado porque es lento.

    Si el modelo no está instalado (típico en Streamlit Cloud la primera vez),
    lo descarga automáticamente. Solo se hace en el primer uso.
    """
    try:
        import spacy
    except ImportError as e:
        raise RuntimeError(
            "spaCy no está instalado. Ejecuta: pip install spacy"
        ) from e

    model_name = "es_core_news_md"
    try:
        return spacy.load(model_name)
    except OSError:
        # Modelo no instalado — descargar al vuelo (~40MB)
        import subprocess
        import sys
        try:
            subprocess.run(
                [sys.executable, "-m", "spacy", "download", model_name],
                check=True,
                capture_output=True,
                timeout=300,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(
                f"No se pudo descargar el modelo {model_name}. "
                "Ejecuta manualmente: python -m spacy download es_core_news_md"
            ) from e
        return spacy.load(model_name)


def detect_candidates(
    texts: Iterable[str],
    *,
    skip_ner: bool = False,
) -> list[Candidate]:
    """Detecta candidatos en una lista de strings (celdas, párrafos).

    `skip_ner=True` ejecuta solo regex (CIF/NIF/IBAN/email/teléfono/dirección)
    y omite spaCy. Útil cuando ya tienes el detector PGC dándote las
    empresas/personas con 100% de cobertura y no quieres que spaCy meta ruido.
    """
    if not skip_ner:
        nlp = _load_nlp()
    else:
        nlp = None

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

    if nlp is None:
        # Modo regex-only: salimos sin pasar por spaCy
        candidates: list[Candidate] = []
        for kind, values in structured.items():
            for value in values:
                count = full_text.count(value)
                candidates.append(Candidate(text=value, kind=kind, count=count, source="regex"))
        return candidates

    # spaCy para ORG y PER
    for text in texts:
        if not text or len(text) > 1_000_000:
            continue
        doc = nlp(text)
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

    return candidates


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
    per_like_kinds = {"PER", "PERSONA"}

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

        # Para ORG-like/PER-like: fuzzy clustering greedy
        is_org_like = kind in org_like_kinds
        normalize = normalize_org if is_org_like else normalize_person
        items_sorted = sorted(items, key=lambda c: (-len(c.text), -c.count))
        clusters_for_kind: list[Cluster] = []

        for cand in items_sorted:
            norm = normalize(cand.text)
            if not norm:
                continue
            # Si después de normalizar quedan menos de 4 chars (palabras genéricas
            # como "asociados" tras quitar sufijo), saltar al cluster propio sin
            # hacer fuzzy match — evita falsas fusiones.
            skip_fuzzy = len(norm) < 5

            matched = None
            if not skip_fuzzy:
                for cluster in clusters_for_kind:
                    for variant in cluster.variants:
                        norm_variant = normalize(variant)
                        # Doble verificación: token_sort_ratio Y ratio simple.
                        # token_set_ratio es muy permisivo; lo evitamos.
                        sort_score = fuzz.token_sort_ratio(norm, norm_variant)
                        simple_score = fuzz.ratio(norm, norm_variant)
                        if sort_score >= threshold and simple_score >= (threshold - 10):
                            matched = cluster
                            break
                    if matched:
                        break
            if matched:
                matched.variants.append(cand.text)
                matched.total_count += cand.count
                if cand.account_code and cand.account_code not in matched.account_codes:
                    matched.account_codes.append(cand.account_code)
                if len(cand.text) > len(matched.canonical):
                    matched.canonical = cand.text
            else:
                clusters_for_kind.append(
                    Cluster(
                        kind=kind,
                        canonical=cand.text,
                        variants=[cand.text],
                        total_count=cand.count,
                        account_codes=[cand.account_code] if cand.account_code else [],
                    )
                )

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

    deduped_clusters: list[Cluster] = []
    for c in clusters:
        if c.kind in ("ORG", "PER"):
            # ¿Alguna de sus variantes ya está en un cluster PGC?
            in_pgc = False
            for v in c.variants:
                if normalize_org(v) in pgc_texts_normalized or normalize_person(v) in pgc_texts_normalized:
                    in_pgc = True
                    break
            if in_pgc:
                continue  # descartamos el cluster NER, el PGC ya lo cubre
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
