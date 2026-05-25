"""Genera un PPT teaser sintético tipo M&A para testing.

20 slides cubriendo las secciones típicas de un teaser/IM:
- Portada
- Disclaimer
- Resumen ejecutivo
- Empresa y producto
- Mercado y competencia
- Equipo
- KPIs / financieros
- Proyecciones
- Oportunidad de inversión
- Contacto

Todos los nombres son sintéticos.
"""
import random
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

random.seed(42)

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

# --- Datos sintéticos ---
EMPRESA = "Innovaciones Mediterráneas del Sur S.L."
EMPRESA_CORTA = "Innovaciones Mediterráneas"
EMPRESA_ABREV = "IMS"
CIF = "B85432109"

# Equipo directivo sintético
EQUIPO = [
    ("Juan García Pérez", "CEO & Founder", "20 años en sector. Ex-Director General de Industrias Catalanas S.A."),
    ("María López Hernández", "CFO", "15 años. Anteriormente CFO en Distribuciones del Norte S.L."),
    ("Carlos Sánchez Ruiz", "COO", "10 años. Ingeniero industrial, MBA por IESE."),
    ("Ana Martínez Gómez", "Chief Commercial Officer", "Desarrollo de negocio internacional. Ex-Servicios Mediterráneos."),
    ("Pedro Jiménez Alonso", "CTO", "Ingeniero informático. Llegó con la adquisición de Tecnologías Premium S.L. en 2021."),
]

# Top clientes mencionados
TOP_CLIENTES = [
    "Distribuciones García y Asociados S.L.",
    "Carrefour España S.A.",
    "Mercadona S.A.",
    "Grupo El Corte Inglés",
    "DIA España S.A.U.",
    "Industrias Hermanos Romero S.L.",
    "Comercial del Levante S.L.U.",
    "Maderas Sánchez Hermanos",
    "Frutas Catalanas Premium S.A.",
    "Servicios Logística Iberia",
]

# Competidores reales/sintéticos
COMPETIDORES = [
    "Industrias Reunidos S.A.",
    "Manufacturas Hispania",
    "Productos Atlánticos S.L.",
    "Grupo Ibérico Premium",
    "Tecnologías del Sur S.A.U.",
]

# Sedes
SEDES = [
    "C/ Mayor 25, Madrid",
    "Avenida Diagonal 405, Barcelona",
    "Polígono Industrial El Plantío, Sevilla",
    "Parque Tecnológico de Bizkaia, Bilbao",
]

prs = Presentation()
prs.slide_width = Inches(13.33)
prs.slide_height = Inches(7.5)

# Helper para añadir slide con título y bullets
def add_slide(title: str, bullets: list[str], section: str = ""):
    slide = prs.slides.add_slide(prs.slide_layouts[5])  # Title Only
    title_shape = slide.shapes.title
    title_shape.text = title
    title_shape.text_frame.paragraphs[0].font.size = Pt(28)
    title_shape.text_frame.paragraphs[0].font.bold = True
    title_shape.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 102, 204)

    if section:
        section_box = slide.shapes.add_textbox(Inches(0.3), Inches(0.2), Inches(4), Inches(0.4))
        section_box.text_frame.text = section
        section_box.text_frame.paragraphs[0].font.size = Pt(11)
        section_box.text_frame.paragraphs[0].font.color.rgb = RGBColor(100, 100, 100)

    # Body
    body_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(12), Inches(5.5))
    tf = body_box.text_frame
    tf.word_wrap = True
    for i, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = "• " + bullet
        p.font.size = Pt(14)

    # Footer con nombre de empresa
    footer = slide.shapes.add_textbox(Inches(0.3), Inches(7.0), Inches(12), Inches(0.4))
    footer.text_frame.text = f"{EMPRESA_CORTA}  |  Confidencial  |  {section or ''}"
    footer.text_frame.paragraphs[0].font.size = Pt(9)
    footer.text_frame.paragraphs[0].font.color.rgb = RGBColor(150, 150, 150)
    return slide


# === Slide 1: Portada ===
slide1 = prs.slides.add_slide(prs.slide_layouts[0])
slide1.shapes.title.text = "Project Atlas"
slide1.placeholders[1].text = (
    f"Confidential Information Memorandum\n"
    f"{EMPRESA}\nMayo 2026\nPreparado por Implica Corporate Finance"
)

# === Slide 2: Disclaimer ===
add_slide(
    "Disclaimer",
    [
        f"Este documento ha sido preparado por Implica Corporate Finance en nombre de {EMPRESA}.",
        f"La información contenida es confidencial y propiedad exclusiva de {EMPRESA_CORTA}.",
        "Su uso queda restringido a las partes destinatarias firmantes del NDA.",
        f"Para consultas: contactar con Ricardo González en Implica Corporate Finance.",
    ],
    "Disclaimer",
)

# === Slide 3: Resumen Ejecutivo ===
add_slide(
    f"Resumen Ejecutivo — {EMPRESA_ABREV}",
    [
        f"{EMPRESA} es líder en el sector de soluciones industriales mediterráneas.",
        f"Fundada en 2008 por Juan García Pérez, con sede en C/ Mayor 25, Madrid.",
        "Facturación 2024: 45,2 M€ (+18% YoY). EBITDA: 8,7 M€ (margen 19,2%).",
        f"Equipo de 245 personas distribuidas entre Madrid y Barcelona.",
        f"CIF: {CIF}. Web: www.innovacionesmediterraneas.com",
    ],
    "1. Resumen Ejecutivo",
)

# === Slide 4: La compañía ===
add_slide(
    f"La Compañía — {EMPRESA_CORTA}",
    [
        f"Razón social: {EMPRESA}",
        f"CIF: {CIF}",
        "Sede social: C/ Mayor 25, Madrid",
        "Centros productivos: Madrid, Barcelona, Sevilla, Bilbao",
        "Filiales: Innovaciones Mediterráneas Portugal (Lisboa), IMS France (Lyon)",
        f"Auditoría: PwC España. Asesoramiento legal: Garrigues.",
    ],
    "2. La Compañía",
)

# === Slide 5: Producto ===
add_slide(
    "Producto y Tecnología",
    [
        f"{EMPRESA_CORTA} desarrolla equipos de eficiencia energética para industria.",
        "Tres líneas: IMS-Cool (refrigeración), IMS-Heat (calefacción industrial), IMS-Air (ventilación).",
        "Tecnología propia patentada (3 patentes activas en España, 1 internacional).",
        "Centro I+D propio en Parque Tecnológico de Bizkaia, dirigido por Pedro Jiménez Alonso.",
        "Inversión en I+D: 2,3 M€ anuales (5% facturación).",
    ],
    "3. Producto",
)

# === Slide 6: Mercado ===
add_slide(
    "Mercado y Competencia",
    [
        "Mercado español de eficiencia energética industrial: 1.200 M€ (CAGR 2020-2024: +12%).",
        "Cuota de mercado de Innovaciones Mediterráneas: ~3,8% en España.",
        f"Principales competidores: {', '.join(COMPETIDORES[:3])}.",
        f"Diferenciación: tecnología propia + servicio postventa (NPS 78 vs media sector 42).",
    ],
    "4. Mercado",
)

# === Slide 7: Equipo ===
add_slide(
    "Equipo Directivo",
    [f"{nombre} — {cargo}" for nombre, cargo, _ in EQUIPO],
    "5. Equipo",
)

# === Slide 8: Bios extendidas (texto largo) ===
slide = prs.slides.add_slide(prs.slide_layouts[5])
slide.shapes.title.text = "Equipo — Biografías"
body = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(12.3), Inches(5.7))
tf = body.text_frame
tf.word_wrap = True
for i, (nombre, cargo, bio) in enumerate(EQUIPO):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    p.text = f"{nombre} ({cargo}): {bio}"
    p.font.size = Pt(12)

# === Slide 9-11: Financieros ===
add_slide(
    "Cuenta de Resultados 2022-2024",
    [
        "Ingresos: 2022: 31,5 M€  |  2023: 38,4 M€  |  2024: 45,2 M€",
        "EBITDA: 2022: 5,1 M€ (16,2%)  |  2023: 6,9 M€ (18,0%)  |  2024: 8,7 M€ (19,2%)",
        "Beneficio neto: 2022: 2,8 M€  |  2023: 3,9 M€  |  2024: 5,1 M€",
        "DFN/EBITDA: 1,2x en 2024.",
    ],
    "6. Financieros",
)

add_slide(
    "Top 5 Clientes (% facturación 2024)",
    [
        f"{TOP_CLIENTES[0]}: 14,2%",
        f"{TOP_CLIENTES[1]}: 11,8%",
        f"{TOP_CLIENTES[2]}: 9,5%",
        f"{TOP_CLIENTES[3]}: 7,1%",
        f"{TOP_CLIENTES[4]}: 5,4%",
        "Concentración Top 5: 48% (anteriormente 52% en 2022, mejora de diversificación)",
    ],
    "6. Financieros — Clientes",
)

add_slide(
    "Cartera completa de clientes recurrentes",
    [f"{c}" for c in TOP_CLIENTES],
    "6. Financieros — Cartera",
)

# === Slide 12: Proveedores clave ===
add_slide(
    "Proveedores clave",
    [
        "Materias primas: Maderas Sánchez Hermanos, Industrias Hermanos Romero S.L.",
        "Logística: Servicios Logística Iberia (contrato exclusivo desde 2019).",
        "IT y software: Tecnologías Premium S.L. (filial desde 2021).",
        "Asesoría: Garrigues (legal), PwC (auditoría y fiscal).",
    ],
    "7. Operaciones",
)

# === Slide 13: Proyecciones ===
add_slide(
    "Proyecciones 2025-2027",
    [
        "Ingresos 2025E: 52,8 M€ (+17%). 2026E: 61,5 M€ (+16%). 2027E: 70,2 M€ (+14%).",
        "EBITDA margin: estabilización en 19,5-20,0%.",
        "CAPEX: 3,5 M€/año (nueva planta Sevilla operativa Q3 2026).",
        "Plan de expansión: Italia 2025, Francia 2026, ampliar Portugal.",
    ],
    "8. Proyecciones",
)

# === Slide 14: Oportunidad de inversión ===
add_slide(
    "Oportunidad de Inversión",
    [
        f"Los accionistas de {EMPRESA_CORTA} ({EMPRESA_ABREV}) buscan un socio estratégico/financiero.",
        "Operación target: venta del 100% del capital.",
        "Múltiplos comparables: 8-10x EBITDA en transacciones recientes del sector.",
        "Valoración orientativa: rango 70-90 M€ enterprise value.",
        "Apertura de proceso: junio 2026. Cierre estimado: Q4 2026.",
    ],
    "9. Oportunidad",
)

# === Slide 15: Highlights ===
add_slide(
    "Investment Highlights",
    [
        "✓ Líder en nicho de alto crecimiento (CAGR 12%).",
        "✓ Tecnología propia patentada con barreras de entrada.",
        "✓ Equipo directivo experimentado con track record probado.",
        "✓ Diversificación de clientes mejorando (Top 5 baja del 52% al 48%).",
        "✓ Plan de expansión internacional ya iniciado.",
        "✓ Márgenes EBITDA en expansión: 16% → 19% en 3 años.",
    ],
    "10. Highlights",
)

# === Slide 16-17: Anexo cap table y accionistas ===
add_slide(
    "Cap Table",
    [
        f"Juan García Pérez (CEO): 52% del capital.",
        "Family office Hermanos García (3 hermanos del fundador): 18%.",
        "Auriga Capital Partners (VC entrada 2019): 15%.",
        "María López Hernández (CFO): 4%.",
        "Pedro Jiménez Alonso (CTO): 4%.",
        "Empleados via stock options: 7%.",
    ],
    "Anexo A",
)

add_slide(
    "Estructura societaria",
    [
        f"{EMPRESA} (matriz, CIF {CIF}) — España.",
        "Innovaciones Mediterráneas Portugal Lda. — 100% participada, sede Lisboa.",
        "IMS France SAS — 100% participada, sede Lyon.",
        "Tecnologías Premium S.L. (CIF B98765432) — 100% participada desde 2021.",
    ],
    "Anexo A",
)

# === Slide 18: Sedes ===
add_slide(
    "Localizaciones",
    [f"📍 {sede}" for sede in SEDES],
    "Anexo B",
)

# === Slide 19: Contacto ===
add_slide(
    "Contacto",
    [
        "Implica Corporate Finance",
        "Ricardo González — Analyst",
        "Email: ricardo.gonzalez@implicacf.com",
        "Móvil: +34 612 345 678",
        "Oficina: C/ Velázquez 28, 28001 Madrid",
        "Web: www.implicacf.com",
    ],
    "Contacto",
)

# === Slide 20: Disclaimer final ===
add_slide(
    "Disclaimer Final",
    [
        f"Este documento es propiedad de {EMPRESA} y de Implica Corporate Finance.",
        "Cualquier reproducción no autorizada está prohibida.",
        "La información financiera no auditada está sujeta a verificación en due diligence.",
        f"Contacto único para cuestiones: Ricardo González (Implica) — ricardo.gonzalez@implicacf.com",
    ],
    "Disclaimer",
)

# Notas de speaker en algunas slides
for i, slide in enumerate(prs.slides):
    if i in (2, 3, 5):
        notes = slide.notes_slide.notes_text_frame
        notes.text = (
            f"Slide {i+1}: enfatizar la trayectoria de Juan García Pérez como fundador y "
            f"la solidez del equipo directivo. {EMPRESA_CORTA} tiene un track record sólido."
        )

out = FIXTURES / "teaser_atlas.pptx"
prs.save(str(out))
print(f"Generado: {out}")
print(f"Slides: {len(prs.slides)}")
print(f"Tamaño: {out.stat().st_size // 1024} KB")
