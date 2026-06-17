"""UI Streamlit del Implica Anonimizador — flujo unificado.

Dos tabs:
1. Anonimizar: subes archivos → auto-detecta tipo → muestra UN solo conjunto
   deduplicado de candidatos → confirmas y descargas ZIP.
2. Rehydrate: para revertir codenames a nombres reales después del análisis.
"""
from __future__ import annotations

import hashlib
import io
import os
import pickle
import re
import secrets
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from implica_anon import (
    accounting,
    audit,
    doctype as doctype_mod,
    formats,
    mapping as mapping_mod,
    rehydrate as rehydrate_mod,
)
from implica_anon.detectors import (
    Candidate,
    candidates_from_pgc,
    cluster_variants,
    detect_candidates,
)
from implica_anon.interactive import DEFAULT_PLACEHOLDERS, KIND_LABELS


# --- Caché de sesión por proyecto (para "reanudar" tras refresco/reinicio) ---
# Guarda en local el último análisis (archivos + tabla) para no re-subir.
# Vive en projects/.cache (gitignored) y va CIFRADA con Fernet (AES). La LLAVE se
# guarda en %LOCALAPPDATA% (fuera del proyecto): así, aunque la caché cifrada se
# sincronice a OneDrive/Drive, nadie sin TU equipo puede abrirla. Si falta el
# paquete 'cryptography', NO se escribe nada (jamás se vuelca cliente en claro).
# Aun así, bórrala al terminar (botón en la UI).
def _session_cache_path(project: str) -> Path:
    d = mapping_mod.PROJECTS_DIR / ".cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{project.lower()}.session.pkl"


def _cache_key_path() -> Path:
    """Ruta de la llave de cifrado, FUERA de la carpeta del proyecto para que no
    se sincronice junto con la caché (LOCALAPPDATA en Windows; ~ como fallback)."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or str(Path.home())
    d = Path(base) / "implica-anonimizador"
    d.mkdir(parents=True, exist_ok=True)
    return d / "cache.key"


_CIPHER = None
_CIPHER_TRIED = False


def _get_cipher():
    """Devuelve un Fernet (cifrado simétrico autenticado) o None si 'cryptography'
    no está disponible. La llave se crea una vez y vive solo en este equipo."""
    global _CIPHER, _CIPHER_TRIED
    if _CIPHER_TRIED:
        return _CIPHER
    _CIPHER_TRIED = True
    try:
        from cryptography.fernet import Fernet
        kp = _cache_key_path()
        if kp.exists():
            key = kp.read_bytes()
        else:
            key = Fernet.generate_key()
            kp.write_bytes(key)
            try:
                os.chmod(kp, 0o600)  # solo el usuario (best-effort en Windows)
            except Exception:
                pass
        _CIPHER = Fernet(key)
    except Exception:
        _CIPHER = None
    return _CIPHER


def _save_session_cache(project: str, payload: dict) -> None:
    cipher = _get_cipher()
    if cipher is None:
        return  # fail-safe: sin cifrado NO escribimos datos de cliente en claro
    try:
        blob = cipher.encrypt(pickle.dumps(payload))
        with _session_cache_path(project).open("wb") as f:
            f.write(blob)
    except Exception:
        pass  # best-effort, nunca rompe el flujo


def _load_session_cache(project: str):
    p = _session_cache_path(project)
    if not p.exists():
        return None
    try:
        data = p.read_bytes()
    except Exception:
        return None
    cipher = _get_cipher()
    if cipher is not None:
        try:
            # Fernet autentica: si descifra, el contenido no se ha manipulado.
            return pickle.loads(cipher.decrypt(data))
        except Exception:
            pass
    # Compatibilidad: caché antigua sin cifrar (pickle plano). Se re-cifra al
    # siguiente guardado.
    try:
        return pickle.loads(data)
    except Exception:
        return None


def _clear_session_cache(project: str) -> None:
    try:
        _session_cache_path(project).unlink(missing_ok=True)
    except Exception:
        pass

st.set_page_config(
    page_title="Implica Anonimizador",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Auth opcional ---
def _check_password() -> bool:
    required = os.environ.get("IMPLICA_ANON_PASSWORD", "")
    if not required:
        return True
    if st.session_state.get("auth_ok"):
        return True
    st.title("🔒 Implica Anonimizador")
    pwd = st.text_input("Contraseña", type="password", key="pwd_input")
    if st.button("Entrar"):
        # compare_digest: comparación de tiempo constante (anti timing-attack)
        if secrets.compare_digest(
            hashlib.sha256(pwd.encode()).hexdigest(),
            hashlib.sha256(required.encode()).hexdigest(),
        ):
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    return False


if not _check_password():
    st.stop()


st.title("🔒 Implica Anonimizador")
st.caption("Anonimiza documentos M&A reemplazando nombres por codenames.")

# Banner de demo cuando se ejecuta en Streamlit Cloud o cualquier despliegue público
if os.environ.get("IMPLICA_ANON_PUBLIC_DEMO", "").lower() in ("1", "true", "yes"):
    st.error(
        "⚠️ **MODO DEMO PÚBLICO** — esta versión está alojada en Streamlit Cloud. "
        "**NO subas documentos reales de clientes.** Usa solo los archivos sintéticos de "
        "ejemplo proporcionados (`tests/fixtures/`). Para producción real, el equipo "
        "Implica usará la versión instalada en el servidor interno, donde los archivos "
        "**nunca salen de la red de Implica**.",
        icon="⚠️",
    )
else:
    st.caption("**100% local.** Nada sale de esta máquina.")


# --- Sidebar: proyecto ---
with st.sidebar:
    st.header("Proyecto")
    existing_projects = mapping_mod.list_projects()

    project_mode = st.radio(
        "Modo", ["Nuevo proyecto", "Continuar proyecto existente"]
    )

    if project_mode == "Nuevo proyecto":
        project_input = st.text_input(
            "Codename del proyecto",
            placeholder="paradise",
            help="Nombre interno del deal.",
        )
        project = (project_input or "").strip().lower()
    else:
        if not existing_projects:
            st.info("No hay proyectos guardados.")
            project = ""
        else:
            project = st.selectbox("Selecciona", existing_projects)

    # Empresa principal del mandato (la de las cuentas): se sustituye por el
    # codename del proyecto. Si la indicas, NO se adivina por frecuencia.
    main_company = ""
    if project:
        main_company = st.text_input(
            "Empresa principal (nombre real)",
            key=f"main_{project}",
            placeholder="Clínica Dental Sonrisa S.L.",
            help="La empresa del mandato / de las cuentas. Se reemplaza por el codename "
                 "del proyecto. Déjalo vacío y el sistema la deduce por frecuencia.",
        ).strip()

    if project:
        pm = mapping_mod.load(project)
        total = sum(len(v) for v in pm.entries.values())
        st.metric("Entradas en mapping", total)
        if pm.updated_at:
            st.caption(f"Actualizado: {pm.updated_at}")

        # Reanudar último análisis (memoria entre refrescos/reinicios)
        if "df" not in st.session_state or st.session_state.get("proj") != project:
            cached = _load_session_cache(project)
            if cached:
                n = len(cached.get("upload_data", []))
                st.caption(
                    "🔒 La caché va **cifrada** en disco y la llave solo está en este "
                    "equipo (no se sincroniza). Aun así, bórrala al terminar si el "
                    "equipo es compartido."
                )
                if st.button(f"▶️ Reanudar último análisis ({n} archivo/s)",
                             use_container_width=True,
                             help="Recupera el último análisis sin volver a subir el documento."):
                    st.session_state["df"] = cached["df"]
                    st.session_state["upload_data"] = cached["upload_data"]
                    st.session_state["proj"] = project
                    st.session_state["is_accounting"] = cached.get("is_accounting", False)
                    st.session_state["clusters_raw"] = cached.get("clusters_raw", [])
                    # Reconstruir contextos desde el df (no se persiste el dict aparte)
                    st.session_state["_ctx"] = _contexts_from_df(cached["df"])
                    st.rerun()
                if st.button("🗑️ Borrar caché de este proyecto", use_container_width=True,
                             help="Elimina del disco el documento y la tabla guardados (confidencialidad)."):
                    _clear_session_cache(project)
                    st.success("Caché borrada.")

        with st.expander("Ver mapping actual"):
            if not pm.entries:
                st.write("_Sin entradas._")
            else:
                for kind, entries in pm.entries.items():
                    if not entries:
                        continue
                    with st.container():
                        st.markdown(f"**{KIND_LABELS.get(kind, kind)}** ({len(entries)})")
                        st.dataframe(
                            pd.DataFrame([{"Original": k, "Codename": v} for k, v in entries.items()]),
                            hide_index=True, use_container_width=True,
                            height=min(200, 35 * (len(entries) + 1)),
                        )

    st.divider()

    # Botón para limpiar estado y empezar de nuevo
    if st.button("🔄 Empezar de nuevo", use_container_width=True, help="Limpia los archivos cargados y la tabla de candidatos (y la caché en disco). No borra mappings guardados."):
        if project:
            _clear_session_cache(project)  # evita reanudar contexto/archivo viejo
        for key in ("df", "upload_data", "proj", "is_accounting", "clusters_raw", "codename_mode_used", "_ctx"):
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()
    st.caption(
        "🛡️ Confidencialidad: nada sale de esta máquina. "
        "Los mappings (`projects/<codename>.json`) son sólo nombres↔codenames, "
        "no contienen los documentos."
    )


# --- Tabs ---
tab_anon, tab_rehydrate, tab_help = st.tabs([
    "📂 Anonimizar",
    "↩️ Rehydrate",
    "ℹ️ Ayuda",
])


# =========================
# Helpers
# =========================

def _require_project():
    if not project:
        st.warning("Introduce un codename de proyecto en la barra lateral.")
        return False
    if not re.match(r"^[a-z0-9_-]+$", project):
        st.error("Codename solo minúsculas, números, guion, guion bajo.")
        return False
    return True


def _scan_files(uploaded_files):
    """Auto-detecta tipo de cada archivo y junta candidatos deduplicados."""
    pgc_entities = []
    named_entities: list[tuple[str, str]] = []
    all_texts: list[str] = []
    doctypes_by_file: dict[str, doctype_mod.DocTypeGuess] = {}
    errors: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        paths = []
        for uf in uploaded_files:
            p = tmpdir_path / uf.name
            p.write_bytes(uf.getvalue())
            paths.append(p)

        # Auto-detect
        for p in paths:
            try:
                dt = doctype_mod.guess_doctype(p)
                doctypes_by_file[p.name] = dt
            except Exception as e:
                errors.append(f"Error detectando tipo en {p.name}: {e}")
                continue

            # Extraer texto siempre (para regex)
            try:
                texts = formats.extract_text(p)
                all_texts.extend(texts)
            except Exception as e:
                errors.append(f"Error extrayendo {p.name}: {e}")
                continue

            # Si es contable, también escaneo PGC
            if dt.doctype == doctype_mod.DocType.ACCOUNTING:
                try:
                    scan = accounting.scan_workbook(p)
                    pgc_entities.extend(scan.entities)
                except Exception as e:
                    errors.append(f"Error escaneando PGC en {p.name}: {e}")

            # Columnas de nombre etiquetadas (Cliente/Proveedor/Razón social...):
            # la celda completa ES la entidad. Determinista, no depende de spaCy.
            # Captura nombres de varias palabras y cortos que spaCy recorta o salta.
            if p.suffix.lower() in (".xlsx", ".xlsm"):
                try:
                    named_entities.extend(accounting.scan_named_columns(p))
                except Exception as e:
                    errors.append(f"Error leyendo columnas de nombre en {p.name}: {e}")

    return all_texts, pgc_entities, named_entities, doctypes_by_file, errors


def _build_candidates(all_texts, pgc_entities, named_entities, use_ner: bool):
    """Combina candidatos PGC + columnas-nombre + regex (+ NER si toca) y clusteriza."""
    candidates = []

    # 1) Si hay PGC entities, candidatos PGC son AUTORITATIVOS
    if pgc_entities:
        class _FakeScan:
            def __init__(self, ents): self.entities = ents
        candidates.extend(candidates_from_pgc(_FakeScan(pgc_entities)))

    # 2) Columnas de nombre: celda completa = entidad (determinista, autoritativo)
    if named_entities:
        from collections import Counter
        counts = Counter(named_entities)
        for (text, kind), cnt in counts.items():
            candidates.append(Candidate(text=text, kind=kind, count=cnt, source="column"))

    # 3) Regex siempre (CIF, IBAN, email, teléfono, dirección)
    candidates.extend(detect_candidates(all_texts, skip_ner=not use_ner))

    return cluster_variants(candidates)


def _build_contexts(upload_data, wanted_texts) -> dict[str, str]:
    """Para los nombres detectados, busca una FILA de ejemplo en los Excels
    subidos (su CIF/importe/factura), para que el usuario distinga nombres
    truncados o abreviados. Solo aplica a Excel; otros formatos → sin contexto."""
    wanted = {re.sub(r"\s+", " ", str(t).strip().lower())
              for t in wanted_texts if t and str(t).strip()}
    if not wanted:
        return {}
    ctx: dict[str, str] = {}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in upload_data:
                if Path(name).suffix.lower() not in (".xlsx", ".xlsm"):
                    continue
                p = Path(tmp) / name
                p.write_bytes(data)
                try:
                    part = accounting.row_contexts(p, wanted)
                except Exception:
                    continue
                for k, v in part.items():
                    ctx.setdefault(k, v)
    except Exception:
        return ctx
    return ctx


def _md_escape(s: str) -> str:
    """Escapa caracteres que Streamlit interpretaría como markdown/LaTeX, para
    mostrar texto del documento (que puede traer _ * ` $ [ ] < > etc.) tal cual."""
    out = []
    for ch in str(s):
        if ch in "\\`*_{}[]()#+-.!|<>$":
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def _attach_contexts(df: pd.DataFrame, contexts: dict) -> pd.DataFrame:
    """Añade/actualiza la columna 'Contexto' (fila de ejemplo en el documento)."""
    if df is None or df.empty:
        return df
    contexts = contexts or {}

    def _ctx_for(row) -> str:
        variants = row["_variants"]
        if not isinstance(variants, (list, tuple)):
            variants = []  # defensivo: pickle corrupto / NaN
        cands = [re.sub(r"\s+", " ", str(row["Canónico"]).lower())]
        cands += [re.sub(r"\s+", " ", str(v).lower()) for v in variants]
        for c in cands:
            if c in contexts:
                return contexts[c]
        return "—"

    df["Contexto"] = [_ctx_for(r) for _, r in df.iterrows()]
    return df


def _contexts_from_df(df) -> dict:
    """Reconstruye {nombre_lower: contexto} desde la columna 'Contexto' de un df
    cacheado. Evita persistir el dict de contextos por separado en disco."""
    if df is None or "Contexto" not in getattr(df, "columns", []):
        return {}
    out: dict = {}
    for _, r in df.iterrows():
        ctx = str(r.get("Contexto", "") or "").strip()
        if ctx and ctx != "—":
            out[re.sub(r"\s+", " ", str(r["Canónico"]).lower())] = ctx
    return out


PGC_KIND_LABELS_SHORT = {
    "CLIENTE": "Cliente",
    "PROVEEDOR": "Proveedor",
    "DEUDOR": "Deudor",
    "PERSONA": "Persona",
    "GRUPO": "Grupo",
    "BANCO": "Banco",
}

# Mapeo Tipo (etiqueta corta editable en la tabla) ↔ kind interno.
# Permite reclasificar en la tabla: "esto no es Empresa, es Cliente".
TIPO_TO_KIND = {
    "Empresa": "ORG",
    "Cliente": "CLIENTE",
    "Proveedor": "PROVEEDOR",
    "Deudor": "DEUDOR",
    "Grupo": "GRUPO",
    "Banco": "BANCO",
    "Persona": "PER",
    "Dirección": "ADDRESS",
    "Email": "EMAIL",
    "Teléfono": "PHONE",
    "CIF/NIF": "CIF",
    "IBAN": "IBAN",
    "Dominio web": "DOMINIO",
}
KIND_TO_TIPO = {
    "ORG": "Empresa", "CLIENTE": "Cliente", "PROVEEDOR": "Proveedor",
    "DEUDOR": "Deudor", "GRUPO": "Grupo", "BANCO": "Banco",
    "PER": "Persona", "PERSONA": "Persona", "ADDRESS": "Dirección",
    "EMAIL": "Email", "PHONE": "Teléfono", "CIF": "CIF/NIF", "NIF": "CIF/NIF",
    "IBAN": "IBAN", "DOMINIO": "Dominio web",
}
TIPO_OPCIONES = list(TIPO_TO_KIND.keys())


def _codename_from_account_code(kind: str, account_code: str, mode: str) -> str:
    """Genera el codename a partir del código de cuenta PGC.

    mode = "full"       → [Cliente-4300000125]
    mode = "short"      → [Cliente-125]  (últimos 3 dígitos)
    mode = "sequential" → usa contador externo, esta función no aplica
    """
    label = PGC_KIND_LABELS_SHORT.get(kind, kind.capitalize())
    code = account_code.strip()
    if mode == "full":
        return f"[{label}-{code}]"
    if mode == "short":
        # Últimos 3-5 dígitos significativos (sin el grupo PGC inicial)
        digits = "".join(ch for ch in code if ch.isdigit())
        if len(digits) <= 3:
            suffix = digits.zfill(3)
        else:
            # Quitar los primeros 3 dígitos del grupo PGC, dejar el resto sin ceros a la izquierda
            rest = digits[3:].lstrip("0") or "0"
            suffix = rest.zfill(3) if len(rest) < 3 else rest
        return f"[{label}-{suffix}]"
    return f"[{label}-{code}]"


def _clusters_to_df(
    clusters,
    pm: mapping_mod.ProjectMapping,
    project: str,
    *,
    codename_mode: str = "account_full",
    main_company: str = "",
) -> pd.DataFrame:
    """Genera tabla deduplicada por canonical text.

    codename_mode:
      - "account_full": para PGC usa el código completo, [Cliente-4300000125]
      - "account_short": para PGC usa los últimos dígitos, [Cliente-125]
      - "sequential": todo usa contador, [Cliente-001], [Cliente-002]
    """
    seen: dict[tuple, dict] = {}
    counters_by_kind: dict[str, int] = {
        kind: len(pm.entries.get(kind, {})) for kind in DEFAULT_PLACEHOLDERS
    }
    pgc_kinds = set(PGC_KIND_LABELS_SHORT.keys())

    # La empresa PRINCIPAL (target/mandante) usa el codename del proyecto; el resto
    # de empresas son entidades distintas → [Empresa-NNN]. Como los clusters vienen
    # ordenados por frecuencia, la 1ª ORG nueva es la más probable principal.
    project_codename = project.capitalize()
    org_empresa_counter = 0
    main_norm = main_company.strip().lower()
    # Si el usuario indicó la empresa principal, NO se deduce por frecuencia.
    principal_org_asignada = (not main_norm) and any(
        cn == project_codename for cn in pm.entries.get("ORG", {}).values()
    )

    def _is_main(c):
        """¿Este cluster es la empresa principal indicada por el usuario?"""
        if not main_norm:
            return False
        cands = [c.canonical.lower()] + [v.lower() for v in c.variants]
        return any(main_norm in x or x in main_norm for x in cands)

    for c in clusters:
        norm_key = (c.kind, c.canonical.strip().lower())
        if norm_key in seen:
            existing = seen[norm_key]
            existing["_variants"] = list(set(existing["_variants"]) | set(c.variants))
            existing["Variantes"] = " | ".join(v for v in existing["_variants"] if v != existing["Canónico"]) or "—"
            existing["Ocurrencias"] += c.total_count
            # Fusionar account_codes
            existing_codes = set(existing.get("_account_codes", []))
            new_codes = set(c.account_codes or [])
            existing["_account_codes"] = sorted(existing_codes | new_codes)
            continue

        # Buscar codename ya asignado (case-insensitive, para coincidir con el
        # reemplazo del Replacer que ignora mayúsculas/minúsculas)
        existing_codename = None
        for v in c.variants:
            v_low = v.lower()
            for kind_entries in pm.entries.values():
                for orig, cod in kind_entries.items():
                    if orig.lower() == v_low:
                        existing_codename = cod
                        break
                if existing_codename:
                    break
            if existing_codename:
                break

        if existing_codename:
            codename = existing_codename
        elif _is_main(c):
            # Empresa principal indicada por el usuario → codename del proyecto
            codename = project_codename
            principal_org_asignada = True
        elif c.kind in pgc_kinds and c.account_codes and codename_mode in ("account_full", "account_short"):
            # Codename derivado del código de cuenta
            mode_str = "full" if codename_mode == "account_full" else "short"
            codename = _codename_from_account_code(c.kind, c.account_codes[0], mode_str)
        else:
            template = DEFAULT_PLACEHOLDERS.get(c.kind)
            if c.kind == "ORG":
                # Si el usuario NO indicó la principal, la 1ª ORG por frecuencia
                # se asume principal. Si SÍ la indicó, las demás son [Empresa-NNN].
                if (not main_norm) and (not principal_org_asignada):
                    codename = project_codename
                    principal_org_asignada = True
                else:
                    org_empresa_counter += 1
                    codename = f"[Empresa-{org_empresa_counter:03d}]"
            elif template:
                counters_by_kind[c.kind] = counters_by_kind.get(c.kind, 0) + 1
                codename = template.format(counters_by_kind[c.kind])
            else:
                codename = f"[{c.kind}-{len(seen)+1:03d}]"

        seen[norm_key] = {
            "_rowid": len(seen),  # id único estable para el merge tras editar
            "Anonimizar": True,
            "Tipo": KIND_TO_TIPO.get(c.kind, "Empresa"),  # etiqueta corta editable
            "_kind": c.kind,
            "Canónico": c.canonical,
            "_variants": list(c.variants),
            "_account_codes": list(c.account_codes or []),
            "Variantes": " | ".join(v for v in c.variants if v != c.canonical) or "—",
            "Cuenta(s)": ", ".join(c.account_codes) if c.account_codes else "—",
            "Ocurrencias": c.total_count,
            "Codename": codename,
        }

    # Garantizar que la empresa principal indicada SIEMPRE se reemplaza, aunque
    # el detector no la haya encontrado como candidata.
    if main_norm and not any(r["Codename"] == project_codename for r in seen.values()):
        seen[("ORG", main_norm)] = {
            "_rowid": len(seen),
            "Anonimizar": True,
            "Tipo": "Empresa",
            "_kind": "ORG",
            "Canónico": main_company.strip(),
            "_variants": [main_company.strip()],
            "_account_codes": [],
            "Variantes": "—",
            "Cuenta(s)": "—",
            "Ocurrencias": 0,
            "Codename": project_codename,
        }

    rows = list(seen.values())
    rows.sort(key=lambda r: (-r["Ocurrencias"], r["Canónico"]))
    return pd.DataFrame(rows)


def _render_merge_suggestions(df_full, project: str) -> None:
    """Muestra grupos de candidatos que PODRÍAN ser la misma entidad y permite
    unificarlos (darles el mismo codename) con un botón. Cubre el caso
    'Mercadona' / 'Mercad' / 'Merca' que el clustering estricto no une solo."""
    from implica_anon.detectors import suggest_unifications

    entries = [
        (int(r["_rowid"]), r["_kind"], r["Canónico"])
        for _, r in df_full.iterrows()
    ]
    groups = suggest_unifications(entries)
    # Confirmación de la última unificación (sobrevive al rerun vía session_state)
    if st.session_state.get("_merge_msg"):
        st.success(st.session_state.pop("_merge_msg"))
    if not groups:
        if not st.session_state.get("_merge_done"):
            return
        st.caption("✅ No quedan duplicados pendientes de unificar.")
        return

    rowid_to_row = {int(r["_rowid"]): r for _, r in df_full.iterrows()}
    with st.expander(f"💡 {len(groups)} posible(s) duplicado(s) — revisa y unifica",
                     expanded=len(groups) <= 12):
        st.caption(
            "Marca solo los que SÍ son la misma empresa (desmarca los que no encajen), "
            "elige el codename y pulsa **Unificar marcados**. Para añadir uno que no "
            "salga aquí, ponle el mismo codename a mano en la tabla de abajo."
        )
        st.caption(
            "⚠️ Si los nombres están **truncados/abreviados** en tu Excel "
            "(p.ej. `CONST. A`, `CONST. Y`), pueden ser empresas **distintas**. "
            "Fíjate en el **contexto** (CIF, importe, factura) antes de unir — y si lo son, desmárcalas."
        )
        for gi, group in enumerate(groups):
            members = [rowid_to_row[rid] for rid in group if rid in rowid_to_row]
            if len(members) < 2:
                continue
            best = max(members, key=lambda m: m["Ocurrencias"])
            st.markdown("---")
            selected = []
            seen_ctx = set()
            for m in members:
                rid = int(m["_rowid"])
                # Por defecto marcado; el usuario desmarca los que no van
                if st.checkbox(
                    f"{m['Canónico']}  ·  {m['Ocurrencias']}×  ({m['Codename']})",
                    value=True, key=f"mrg_{gi}_{rid}",
                ):
                    selected.append(rid)
                # Contexto: fila de ejemplo del documento (distingue truncados).
                # Escapamos markdown/LaTeX porque el texto viene del documento y
                # puede contener _ * ` $ [ ] < > que romperían el render. No repetimos
                # el mismo contexto si dos variantes salen de la misma fila.
                ctx = str(m.get("Contexto", "") or "").strip()
                if ctx and ctx != "—" and ctx not in seen_ctx:
                    seen_ctx.add(ctx)
                    st.caption("↳ " + _md_escape(ctx))
            col_t, col_b = st.columns([3, 1])
            target = col_t.text_input(
                "Codename a aplicar", value=best["Codename"],
                key=f"mrgt_{gi}", label_visibility="collapsed",
            )
            if col_b.button("Unificar marcados", key=f"mrgb_{gi}"):
                if len(selected) >= 1 and target.strip():
                    nombres = [rowid_to_row[r]["Canónico"] for r in selected if r in rowid_to_row]
                    for rid in selected:
                        idx = df_full[df_full["_rowid"] == rid].index
                        if len(idx) > 0:
                            df_full.loc[idx[0], "Codename"] = target.strip()
                    st.session_state["df"] = df_full
                    # Mensaje de confirmación que se mostrará tras el rerun
                    st.session_state["_merge_msg"] = (
                        f"✅ Unificados {len(selected)} nombres → «{target.strip()}»: "
                        + ", ".join(nombres[:5]) + ("…" if len(nombres) > 5 else "")
                    )
                    st.session_state["_merge_done"] = True
                    try:
                        st.toast(f"Unificados {len(selected)} → {target.strip()}")
                    except Exception:
                        pass
                    st.rerun()
                else:
                    st.warning("Marca al menos un nombre y escribe un codename.")


def _df_to_mapping(df: pd.DataFrame, project: str) -> mapping_mod.ProjectMapping:
    pm = mapping_mod.load(project)
    for _, row in df.iterrows():
        if not row["Anonimizar"]:
            continue
        codename = (row["Codename"] or "").strip()
        if not codename:
            continue
        for variant in row["_variants"]:
            pm.add(row["_kind"], variant, codename)
    return pm


def _process_files(uploaded_data, mapping: mapping_mod.ProjectMapping, *, inverse=False):
    """Procesa los archivos y devuelve (zip_bytes, leaks).

    `leaks` es un dict {archivo: [originales que sobrevivieron]} — vacío si la
    anonimización fue limpia. En modo inverse (rehydrate) no se verifica fuga
    porque ahí el objetivo es justamente devolver los nombres reales.
    """
    project = mapping.project.lower()
    if inverse:
        replacements = rehydrate_mod.invert_mapping(mapping)
        suffix = "rehidratado"
    else:
        replacements = mapping.all_replacements()
        suffix = project

    leaks: dict[str, list[str]] = {}
    unverifiable: list[str] = []
    warnings_by_file: dict[str, list[str]] = {}
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            for name, data in uploaded_data:
                src = tmpdir_path / name
                src.write_bytes(data)
                if not formats.is_supported(src):
                    continue
                out_name = f"{Path(name).stem}.{suffix}{Path(name).suffix}"
                dst = tmpdir_path / out_name
                try:
                    result = formats.apply_replacements(src, replacements, dst)
                    zf.write(dst, arcname=out_name)
                    if not inverse:
                        if result.surviving:
                            leaks[name] = result.surviving
                        if not result.verifiable:
                            unverifiable.append(name)
                        if result.warnings:
                            warnings_by_file[name] = result.warnings
                except Exception as e:
                    zf.writestr(f"{Path(name).stem}.ERROR.txt", f"ERROR: {e}\n")
    return zip_buf.getvalue(), {
        "leaks": leaks,
        "unverifiable": unverifiable,
        "warnings": warnings_by_file,
    }


# =========================
# Tab: Anonimizar
# =========================
with tab_anon:
    if not _require_project():
        st.stop()

    uploaded = st.file_uploader(
        "Sube los archivos (Excel, Word, PowerPoint, PDF)",
        type=["xlsx", "xlsm", "docx", "pptx", "pdf"],
        accept_multiple_files=True,
        key="uploader",
    )

    if not uploaded:
        st.info("⬆️ Arrastra los archivos para empezar.")
        st.stop()

    st.write(f"**{len(uploaded)} archivo(s)**:")
    st.dataframe(
        pd.DataFrame([{"Archivo": f.name, "Tamaño (KB)": f.size // 1024} for f in uploaded]),
        hide_index=True, use_container_width=True,
    )

    # Selector manual de tipo (default = Auto)
    doctype_override = st.selectbox(
        "Tipo de documento",
        options=[
            ("auto", "🤖 Auto-detectar (recomendado)"),
            ("accounting", "📊 Sumas y saldos / Libro contable"),
            ("teaser_im", "📑 Teaser / IM / Presentación corporativa"),
            ("legal", "⚖️ Contrato / NDA / SPA / Legal"),
            ("generic", "📄 Documento general (NER estándar)"),
        ],
        format_func=lambda x: x[1],
        help=(
            "**Auto-detectar**: la herramienta mira el contenido y decide.\n\n"
            "**Cuándo cambiar manualmente**:\n"
            "- Tu Excel es un sumas y saldos pero no tiene las columnas estándar (Cuenta/Debe/Haber) → fuerza 'Sumas y saldos' para que use PGC.\n"
            "- Un PDF/PPT es un teaser pero el auto-detect lo clasifica como genérico → fuerza 'Teaser/IM'.\n"
            "- Quieres forzar el flujo estándar NER sin auto-magic."
        ),
    )
    doctype_forced = doctype_override[0]

    if st.button("🔍 Analizar", type="primary"):
        try:
            with st.spinner("Detectando tipo de documento..."):
                all_texts, pgc_entities, named_entities, doctypes, errors = _scan_files(uploaded)
        except Exception as e:
            st.error(f"Error escaneando archivos: {e}")
            st.stop()

        # Mostrar diagnóstico de detección
        if doctypes:
            cols = st.columns(min(3, len(doctypes)))
            for i, (name, dt) in enumerate(doctypes.items()):
                with cols[i % len(cols)]:
                    st.metric(
                        Path(name).name[:30],
                        doctype_mod.LABELS[dt.doctype].split(maxsplit=1)[1] if " " in doctype_mod.LABELS[dt.doctype] else doctype_mod.LABELS[dt.doctype],
                        f"{dt.confidence*100:.0f}% confianza",
                    )

        for err in errors:
            st.warning(err)

        # Aplicar override del usuario si lo hay
        if doctype_forced == "accounting" and not pgc_entities:
            # Usuario fuerza accounting pero auto no detectó PGC — intentar más agresivo
            st.warning(
                "Has forzado 'sumas y saldos' pero el auto-detect no encontró cuentas PGC con headers reconocibles. "
                "Intentando detección por contenido (buscar columnas con códigos numéricos)..."
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                for uf in uploaded:
                    p = tmpdir_path / uf.name
                    p.write_bytes(uf.getvalue())
                    if p.suffix.lower() in (".xlsx", ".xlsm"):
                        try:
                            scan = accounting.scan_workbook(p)
                            pgc_entities.extend(scan.entities)
                        except Exception as e:
                            st.warning(f"Error: {e}")

        is_accounting = bool(pgc_entities) and doctype_forced in ("auto", "accounting")
        if doctype_forced in ("teaser_im", "legal", "generic"):
            # Usuario fuerza un flujo NER — ignorar PGC aunque se haya detectado
            is_accounting = False
            pgc_entities = []
            st.info(f"Modo forzado: **{doctype_override[1]}**. Usando NER + regex.")
        # Para libros contables, no usamos NER (es ruidoso y lento); solo PGC + regex.
        # Para documentos narrativos, sí usamos NER.
        use_ner = not is_accounting

        if is_accounting:
            st.info(
                f"📊 Detecté libros contables ({len(pgc_entities)} cuentas PGC totales). "
                "Anonimización masiva sin pasar por NER."
            )
        else:
            st.info("📄 Documentos narrativos. Usando NER + regex.")

        # Mensaje distinto si es la primera vez que se usa NER (descarga modelo spaCy ~40MB)
        if is_accounting:
            spinner_msg = "Clusterizando entidades del libro contable..."
        else:
            spinner_msg = (
                "Detectando entidades con NER+regex... "
                "(la primera vez en este servidor descarga el modelo de español, ~40MB, tarda 30-60s)"
            )

        try:
            with st.spinner(spinner_msg):
                clusters = _build_candidates(all_texts, pgc_entities, named_entities, use_ner=use_ner)
        except RuntimeError as e:
            st.error(
                f"Error cargando el modelo de NLP: {e}\n\n"
                "Si estás en Streamlit Cloud, intenta refrescar la página. "
                "El modelo se descarga la primera vez y a veces tarda."
            )
            st.stop()
        except Exception as e:
            st.error(f"Error inesperado al analizar: {e}")
            st.stop()

        if not clusters:
            st.warning(
                "No se detectaron candidatos a anonimizar. "
                "Si el archivo SÍ tiene nombres a anonimizar, prueba a forzar el tipo "
                "manualmente en el selector de arriba."
            )
            st.stop()

        pm = mapping_mod.load(project)
        # Por defecto, para libros contables usamos codename basado en código de cuenta completo
        default_mode = "account_full" if is_accounting else "sequential"
        df = _clusters_to_df(clusters, pm, project, codename_mode=default_mode,
                             main_company=main_company)
        upload_data = [(f.name, f.getvalue()) for f in uploaded]
        # Contexto: fila de ejemplo (importe/factura, CIF enmascarado) para distinguir
        # nombres truncados o abreviados. Solo si hay Excel (otros formatos no tienen
        # filas). El CIF va enmascarado y NO se persiste el dict aparte (va dentro del
        # df cacheado, que ya contiene la tabla).
        has_excel = any(Path(n).suffix.lower() in (".xlsx", ".xlsm") for n, _ in upload_data)
        contexts = {}
        if has_excel:
            wanted = set(df["Canónico"].tolist())
            for vs in df["_variants"].tolist():
                wanted.update(vs)
            contexts = _build_contexts(upload_data, wanted)
            _attach_contexts(df, contexts)
        st.session_state["df"] = df
        st.session_state["upload_data"] = upload_data
        st.session_state["proj"] = project
        st.session_state["is_accounting"] = is_accounting
        st.session_state["main_company"] = main_company
        st.session_state["clusters_raw"] = clusters  # para regenerar si cambia modo
        st.session_state["_ctx"] = contexts
        # Guardar caché para poder reanudar tras refresco/reinicio sin re-subir.
        # NO guardamos el dict de contextos aparte; el df ya lleva la columna
        # 'Contexto' (con el CIF enmascarado) y de ahí se reconstruye al reanudar.
        _save_session_cache(project, {
            "upload_data": upload_data,
            "df": df,
            "is_accounting": is_accounting,
            "clusters_raw": clusters,
        })
        st.success(f"Detectados {len(df)} grupos únicos.")

        # Estado de la capa opcional GLiNER (si está activada)
        from implica_anon import gliner_detector as _gd
        if _gd.is_enabled():
            msg = _gd.status_message()
            if msg:
                st.caption(f"🤖 {msg}.")  # p.ej. "GLiNER no disponible, usando motor clásico"
            else:
                st.caption("🤖 Capa GLiNER activa (detección de entidades M&A reforzada).")

    if "df" in st.session_state and st.session_state.get("proj") == project:
        st.divider()
        st.subheader("Candidatos detectados")

        # Selector de estrategia de codename (solo si hay cuentas PGC)
        if st.session_state.get("is_accounting"):
            col_strat, _ = st.columns([2, 1])
            with col_strat:
                strategy = st.radio(
                    "Estrategia de codename para cuentas PGC:",
                    options=[
                        ("account_full", "Código completo: `[Cliente-4300000125]` — trazabilidad perfecta con tu sumas y saldos"),
                        ("account_short", "Código corto: `[Cliente-125]` — más legible para Claude"),
                        ("sequential", "Secuencial: `[Cliente-001]`, `[Cliente-002]` — anonimización máxima"),
                    ],
                    format_func=lambda x: x[1],
                    key="codename_strategy",
                )
                # Si cambia, regenerar df
                new_mode = strategy[0]
                current_mode = st.session_state.get("codename_mode_used", "account_full")
                if new_mode != current_mode and "clusters_raw" in st.session_state:
                    pm_now = mapping_mod.load(project)
                    df_new = _clusters_to_df(
                        st.session_state["clusters_raw"], pm_now, project,
                        codename_mode=new_mode,
                        main_company=st.session_state.get("main_company", ""),
                    )
                    df_new = _attach_contexts(df_new, st.session_state.get("_ctx", {}))
                    st.session_state["df"] = df_new
                    st.session_state["codename_mode_used"] = new_mode

        st.caption(
            "🔍 Cada fila = una entidad única. Puedes editar 3 columnas: **Anonimizar** (sí/no), "
            "**Tipo** (si detectó mal: Empresa→Cliente, etc.) y **Codename**. "
            "Navega con flechas y marca con **Espacio**; **Tab** salta entre celdas."
        )
        df_full = st.session_state["df"]

        # --- Sugerencias de unificación (Mercadona / Mercad / Merca → la misma) ---
        _render_merge_suggestions(df_full, project)

        # --- Selección masiva con botones (alternativa al clic uno a uno) ---
        cols_sel = st.columns(4)
        if cols_sel[0].button("☑️ Marcar todas"):
            df_full["Anonimizar"] = True
            st.session_state["df"] = df_full
            st.rerun()
        if cols_sel[1].button("⬜ Desmarcar todas"):
            df_full["Anonimizar"] = False
            st.session_state["df"] = df_full
            st.rerun()
        if cols_sel[2].button("🔄 Invertir"):
            df_full["Anonimizar"] = ~df_full["Anonimizar"].astype(bool)
            st.session_state["df"] = df_full
            st.rerun()

        # Filtro por tipo (para revisar por categorías)
        all_types = sorted(set(df_full["Tipo"].tolist()))
        selected_types = cols_sel[3].multiselect(
            "Ver solo:", all_types, default=all_types, key="type_filter",
        )
        df_filtered = df_full[df_full["Tipo"].isin(selected_types)].reset_index(drop=True)

        edited = st.data_editor(
            df_filtered,
            column_config={
                "Anonimizar": st.column_config.CheckboxColumn("Anonimizar", default=True, width="small"),
                "Tipo": st.column_config.SelectboxColumn(
                    "Tipo", options=TIPO_OPCIONES, width="small", required=True,
                    help="Cambia si se detectó mal (p.ej. era Cliente y puso Empresa).",
                ),
                "_rowid": None,
                "_kind": None,
                "_variants": None,
                "_account_codes": None,
                "Canónico": st.column_config.TextColumn("Canónico", disabled=True, width="medium"),
                "Variantes": st.column_config.TextColumn("Variantes", disabled=True, width="medium"),
                "Contexto": st.column_config.TextColumn(
                    "Contexto (ejemplo en el doc)", disabled=True, width="large",
                    help="Una fila real donde aparece este nombre (su CIF/importe/factura). "
                         "Ayuda a distinguir nombres truncados o abreviados en origen.",
                ),
                "Cuenta(s)": st.column_config.TextColumn("Cuenta(s) PGC", disabled=True, width="small"),
                "Ocurrencias": st.column_config.NumberColumn("#", disabled=True, width="small"),
                "Codename": st.column_config.TextColumn("Codename →", width="medium"),
            },
            hide_index=True, use_container_width=True, num_rows="fixed", key="editor",
        )

        # Merge cambios al df full (Anonimizar, Tipo y Codename son editables)
        for _, row in edited.iterrows():
            full_idx = df_full[df_full["_rowid"] == row["_rowid"]].index
            if len(full_idx) > 0:
                df_full.loc[full_idx[0], "Anonimizar"] = row["Anonimizar"]
                df_full.loc[full_idx[0], "Codename"] = row["Codename"]
                # Si cambió el Tipo, actualizar también el kind interno
                if row["Tipo"] != df_full.loc[full_idx[0], "Tipo"]:
                    df_full.loc[full_idx[0], "Tipo"] = row["Tipo"]
                    df_full.loc[full_idx[0], "_kind"] = TIPO_TO_KIND.get(row["Tipo"], "ORG")
        st.session_state["df"] = df_full
        # Persistir el estado ACTUAL (ediciones de codename/tipo + merges aplicados)
        # para que "Reanudar" tras un refresco conserve los cambios manuales.
        if "upload_data" in st.session_state:
            _save_session_cache(project, {
                "upload_data": st.session_state["upload_data"],
                "df": df_full,
                "is_accounting": st.session_state.get("is_accounting", False),
                "clusters_raw": st.session_state.get("clusters_raw", []),
            })

        if st.button("✅ Anonimizar y descargar", type="primary"):
            try:
                with st.spinner("Aplicando reemplazos y verificando..."):
                    pm = _df_to_mapping(df_full, project)
                    mapping_mod.save(pm)
                    zip_bytes, report = _process_files(st.session_state["upload_data"], pm)
            except Exception as e:
                st.error(f"No se pudo generar el archivo anonimizado: {type(e).__name__}: {e}. "
                         "Tu análisis sigue guardado — no tienes que repetirlo.")
                st.stop()

            leaks = report["leaks"]
            unverifiable = report["unverifiable"]
            warnings_by_file = report["warnings"]

            # 1) Fuga de datos: nombres reales que sobrevivieron
            if leaks:
                st.error("⚠️ **ATENCIÓN: posible fuga de datos.** Estos nombres reales "
                         "siguen apareciendo en el archivo anonimizado. **Revisa antes de "
                         "compartirlo:**")
                for fname, names in leaks.items():
                    st.markdown(f"- **{fname}**: {', '.join(names[:20])}"
                                + (f" _(+{len(names)-20} más)_" if len(names) > 20 else ""))
                st.caption("Causa habitual: el nombre aparece dentro de una imagen o con un "
                           "formato que el detector no capturó. Añádelo manualmente y reprocesa.")

            # 2) No verificable: escaneado / sin texto → no dar falso OK
            if unverifiable:
                st.warning("🔍 **No se pudo verificar** estos archivos (sin texto legible, "
                           "posible escaneo): " + ", ".join(f"**{f}**" for f in unverifiable)
                           + ". Revísalos a mano o pásalos por un OCR antes de compartir.")

            # 3) Avisos (imágenes, etc.)
            for fname, warns in warnings_by_file.items():
                for w in warns:
                    st.caption(f"ℹ️ {fname}: {w}")

            # 4) Todo limpio
            if not leaks and not unverifiable:
                st.success(f"✅ Verificado: ningún nombre real sobrevive. "
                           f"{sum(len(v) for v in pm.entries.values())} entradas en el mapping.")

            # Registro de auditoría (metadata agregada, sin PII)
            audit.log_event(
                project,
                "anonymize",
                files=len(st.session_state["upload_data"]),
                entities=sum(len(v) for v in pm.entries.values()),
                leaks=sum(len(v) for v in leaks.values()),
                unverifiable=len(unverifiable),
            )

            st.download_button(
                f"⬇️ Descargar {project}_anonimizado.zip",
                data=zip_bytes,
                file_name=f"{project}_anonimizado.zip",
                mime="application/zip",
                type="primary",
            )


# =========================
# Tab: Rehydrate
# =========================
with tab_rehydrate:
    st.caption(
        "Convierte codenames de vuelta a nombres reales. Útil cuando Claude te ha "
        "devuelto un análisis con `[Cliente-125]` y quieres ver el nombre real."
    )

    if not _require_project():
        st.stop()

    pm = mapping_mod.load(project)
    total = sum(len(v) for v in pm.entries.values())
    if total == 0:
        st.warning(f"El proyecto '{project}' no tiene mapping. Anonimiza algo primero.")
        st.stop()

    st.write(f"Mapping del proyecto **{project}**: {total} entradas")

    mode = st.radio(
        "Qué quieres rehidratar:",
        ["Texto pegado", "Archivos"],
        horizontal=True,
    )

    if mode == "Texto pegado":
        text_input = st.text_area("Pega el texto con codenames", height=300)
        if st.button("↩️ Rehidratar texto", type="primary"):
            if text_input.strip():
                rehydrated, n = rehydrate_mod.rehydrate_text(text_input, pm)
                st.success(f"{n} reemplazos.")
                st.text_area("Resultado (PII real)", rehydrated, height=400)
                st.warning("⚠️ Contiene nombres reales. No lo pegues fuera de Implica.")
    else:
        rh_files = st.file_uploader(
            "Sube los archivos con codenames",
            type=["xlsx", "xlsm", "docx", "pptx", "pdf"],
            accept_multiple_files=True,
        )
        if rh_files and st.button("↩️ Rehidratar", type="primary"):
            with st.spinner("Rehidratando..."):
                upload_data = [(f.name, f.getvalue()) for f in rh_files]
                zip_bytes, _ = _process_files(upload_data, pm, inverse=True)
            st.success("Listo.")
            st.warning("⚠️ Contienen nombres reales.")
            st.download_button(
                f"⬇️ Descargar {project}_rehidratado.zip",
                data=zip_bytes,
                file_name=f"{project}_rehidratado.zip",
                mime="application/zip",
                type="primary",
            )


# =========================
# Tab: Ayuda
# =========================
with tab_help:
    st.markdown(
        """
        ### Flujo en 4 pasos

        1. Introduce el **codename del proyecto** en la barra lateral (ej. `paradise`).
        2. **Sube** los archivos en la tab Anonimizar.
        3. Pulsa **🔍 Analizar** — auto-detecta el tipo (libro contable, teaser, contrato, etc.) y muestra los candidatos.
        4. **Revisa la tabla**, edita si quieres, y pulsa **✅ Anonimizar y descargar**.

        ### Cómo agrupa las variantes

        Si "Global Menta S.L.", "GlobalMenta" y "Global Menta" aparecen en el doc, se muestran **en una sola fila** con todas las variantes listadas. Editas un único codename y se aplica a las tres.

        ### Cómo evita repetir preguntas

        - Las cuentas PGC (430xxx clientes, 410xxx proveedores) se auto-asignan a `[Cliente-001]`, `[Proveedor-001]` etc. sin preguntar — solo te muestran para que revises.
        - Si el detector PGC ya captó una entidad, el NER no la duplica.
        - Si dos clusters tienen exactamente el mismo nombre, se fusionan en una fila.

        ### Flujo de due diligence con Claude

        1. Subes el sumas y saldos → tab **Anonimizar** → ZIP anonimizado.
        2. Pasas el ZIP a Claude para análisis (QoE, partes vinculadas, DFN, etc.).
        3. Claude responde con `[Cliente-125] representa el 23%...`
        4. Pegas la respuesta en tab **↩️ Rehydrate** → ves los nombres reales en tu informe interno.

        ### Limitaciones

        - PDFs escaneados sin OCR no se detectan.
        - Fórmulas de Excel no se tocan (intencional).
        - Imágenes/logos no se anonimizan.
        """
    )
