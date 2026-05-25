"""Genera un sumas y saldos sintético realista para testing.

Estructura típica del PGC español:
- Grupo 1: Financiación básica (capital, reservas)
- Grupo 2: Activo no corriente (inmovilizado)
- Grupo 3: Existencias
- Grupo 4: Acreedores y deudores (CLIENTES 430-433, PROVEEDORES 400-411, DEUDORES 440-449)
- Grupo 5: Cuentas financieras (BANCOS 572-579)
- Grupo 6: Compras y gastos (incluye 6230 servicios profesionales)
- Grupo 7: Ventas e ingresos

Todos los nombres son sintéticos. Cualquier coincidencia es casual.
"""
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

random.seed(42)  # determinístico

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)


# --- Datos sintéticos ---

NOMBRE_EMPRESA = "Innovaciones Mediterráneas del Sur S.L."
CIF_EMPRESA = "B85432109"
PERIODO = "01/01/2024 a 31/12/2024"

# Apellidos y nombres frecuentes en España
APELLIDOS = [
    "García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez",
    "Pérez", "Gómez", "Martín", "Jiménez", "Ruiz", "Hernández", "Díaz", "Moreno",
    "Muñoz", "Álvarez", "Romero", "Alonso", "Gutiérrez", "Navarro", "Torres",
    "Domínguez", "Vázquez", "Ramos", "Gil", "Ramírez", "Serrano", "Blanco",
    "Suárez", "Castro", "Ortega", "Rubio", "Marín", "Sanz",
]

NOMBRES = [
    "Juan", "María", "Carlos", "Ana", "Pedro", "Laura", "José", "Carmen",
    "Antonio", "Isabel", "Manuel", "Cristina", "Francisco", "Marta", "Javier",
    "Lucía", "David", "Elena", "Miguel", "Pilar", "Daniel", "Patricia",
    "Alejandro", "Sara", "Pablo", "Andrea", "Sergio", "Beatriz", "Jorge", "Rocío",
]

# Tokens para formar nombres comerciales
PREFIJOS_COMERCIALES = [
    "Distribuciones", "Industrias", "Servicios", "Construcciones", "Importaciones",
    "Exportaciones", "Logística", "Comercial", "Talleres", "Manufacturas",
    "Fabricación", "Mayoristas", "Especialidades", "Soluciones", "Tecnologías",
    "Sistemas", "Productos", "Suministros", "Centro", "Grupo", "Hermanos",
    "Almacenes", "Maderas", "Frutas", "Pescados", "Carnes", "Confecciones",
    "Aceites", "Vinos", "Cárnicas", "Hostelería", "Catering",
]

SUFIJOS_TEMATICOS = [
    "del Sur", "del Norte", "del Levante", "Mediterráneas", "Atlánticas",
    "Ibéricas", "Castellanas", "Andaluzas", "Catalanas", "Valencianas",
    "y Asociados", "y Compañía", "Reunidos", "Hispania", "Iberia", "España",
    "Premium", "Selectos", "Excelencia", "Global", "Internacional", "Europe",
]

SECTORES = [
    "Frutas", "Hortalizas", "Pescados", "Carnes", "Vinos", "Aceites",
    "Textil", "Madera", "Acero", "Aluminio", "Cerámicas", "Plásticos",
    "Electrónica", "Software", "Hostelería", "Transporte", "Logística",
    "Construcción", "Pintura", "Limpieza", "Seguridad", "Energía",
]

BANCOS_REALES = [
    "Banco Santander", "BBVA", "CaixaBank", "Banco Sabadell", "Bankinter",
    "Kutxabank", "Unicaja Banco", "ING Direct", "Deutsche Bank",
]

CUENTAS_PGC_GENERICAS = {
    "100": "Capital social",
    "112": "Reserva legal",
    "113": "Reservas voluntarias",
    "121": "Resultados negativos ejercicios anteriores",
    "129": "Resultado del ejercicio",
    "170": "Deudas a largo plazo con entidades de crédito",
    "200": "Investigación",
    "210": "Terrenos y bienes naturales",
    "211": "Construcciones",
    "213": "Maquinaria",
    "215": "Otras instalaciones",
    "216": "Mobiliario",
    "217": "Equipos para procesos de información",
    "218": "Elementos de transporte",
    "281": "Amortización acumulada inmovilizado material",
    "300": "Mercaderías",
    "310": "Materias primas",
    "320": "Otros aprovisionamientos",
    "390": "Deterioro de valor de las mercaderías",
    "470": "Hacienda Pública, deudora",
    "472": "Hacienda Pública, IVA soportado",
    "473": "Hacienda Pública, retenciones y pagos a cuenta",
    "475": "Hacienda Pública, acreedora",
    "476": "Organismos de la Seguridad Social, acreedores",
    "477": "Hacienda Pública, IVA repercutido",
    "520": "Deudas a corto plazo con entidades de crédito",
    "570": "Caja, euros",
    "600": "Compras de mercaderías",
    "601": "Compras de materias primas",
    "602": "Compras de otros aprovisionamientos",
    "607": "Trabajos realizados por otras empresas",
    "608": "Devoluciones de compras",
    "609": "Rappels por compras",
    "621": "Arrendamientos y cánones",
    "622": "Reparaciones y conservación",
    "623": "Servicios de profesionales independientes",
    "624": "Transportes",
    "625": "Primas de seguros",
    "626": "Servicios bancarios y similares",
    "627": "Publicidad, propaganda y RRPP",
    "628": "Suministros",
    "629": "Otros servicios",
    "630": "Impuesto sobre beneficios",
    "631": "Otros tributos",
    "640": "Sueldos y salarios",
    "642": "Seguridad Social a cargo de la empresa",
    "649": "Otros gastos sociales",
    "662": "Intereses de deudas",
    "668": "Diferencias negativas de cambio",
    "678": "Gastos excepcionales",
    "681": "Amortización del inmovilizado material",
    "693": "Pérdidas por deterioro de existencias",
    "700": "Ventas de mercaderías",
    "701": "Ventas de productos terminados",
    "705": "Prestaciones de servicios",
    "708": "Devoluciones de ventas",
    "709": "Rappels sobre ventas",
    "752": "Ingresos por arrendamientos",
    "759": "Ingresos por servicios diversos",
    "769": "Otros ingresos financieros",
    "778": "Ingresos excepcionales",
}


def gen_cif() -> str:
    """Genera un CIF español sintético con prefijo común."""
    letra = random.choice("ABCDEFGHJ")
    digitos = "".join(str(random.randint(0, 9)) for _ in range(7))
    control = random.choice("0123456789")
    return f"{letra}{digitos}{control}"


def gen_iban() -> str:
    """IBAN español sintético."""
    digitos = "".join(str(random.randint(0, 9)) for _ in range(22))
    return f"ES{digitos}"


def gen_nombre_persona() -> str:
    nombre = random.choice(NOMBRES)
    ap1 = random.choice(APELLIDOS)
    ap2 = random.choice(APELLIDOS)
    return f"{nombre} {ap1} {ap2}"


def gen_nombre_empresa(con_sufijo: bool = True) -> str:
    """Genera nombres de empresa realistas."""
    pattern = random.choice([
        # "Distribuciones García"
        lambda: f"{random.choice(PREFIJOS_COMERCIALES)} {random.choice(APELLIDOS)}",
        # "Industrias del Sur"
        lambda: f"{random.choice(PREFIJOS_COMERCIALES)} {random.choice(SUFIJOS_TEMATICOS)}",
        # "Frutas Hermanos García"
        lambda: f"{random.choice(SECTORES)} Hermanos {random.choice(APELLIDOS)}",
        # "García y Asociados"
        lambda: f"{random.choice(APELLIDOS)} y Asociados",
        # "Comercial Frutas y Verduras"
        lambda: f"{random.choice(PREFIJOS_COMERCIALES)} {random.choice(SECTORES)}",
        # "Talleres García Hermanos"
        lambda: f"{random.choice(PREFIJOS_COMERCIALES)} {random.choice(APELLIDOS)} Hermanos",
    ])
    nombre = pattern()
    if con_sufijo:
        sufijo = random.choice([" S.L.", " S.L.U.", " S.A.", " S.A.U.", "", " S.L."])
        nombre = nombre + sufijo
    return nombre


def gen_amounts(magnitud: float = 10000) -> tuple[float, float, float, float]:
    """Devuelve (saldo_inicial, debe, haber, saldo_final) consistentes."""
    saldo_ini = round(random.uniform(-magnitud * 0.3, magnitud), 2)
    debe = round(random.uniform(0, magnitud * 5), 2)
    haber = round(random.uniform(0, magnitud * 5), 2)
    saldo_fin = round(saldo_ini + debe - haber, 2)
    return saldo_ini, debe, haber, saldo_fin


# --- Construir el sumas y saldos ---

print("Generando sumas y saldos sintético...")

rows: list[tuple] = []

# Cabecera de la entidad (algunos exports tienen esto en filas superiores)
header_rows = [
    [NOMBRE_EMPRESA, "", "", "", "", ""],
    [f"CIF: {CIF_EMPRESA}", "", "", "", "", ""],
    [f"Sumas y saldos del {PERIODO}", "", "", "", "", ""],
    ["", "", "", "", "", ""],  # fila blanca
    ["Cuenta", "Descripción", "Saldo Inicial", "Debe", "Haber", "Saldo Final"],
]

# Grupo 1 y 2: capital + inmovilizado (genéricos, sin nombres)
for code, desc in CUENTAS_PGC_GENERICAS.items():
    if code.startswith(("1", "2", "3")):
        amounts = gen_amounts(50000)
        rows.append((code, desc, *amounts))

# Grupo 4: clientes (430xxx) — el grueso
print("  Generando clientes...")
num_clientes = 400
clientes_creados: list[str] = []
for i in range(num_clientes):
    code = f"43000{i:05d}"
    nombre = gen_nombre_empresa()
    clientes_creados.append(nombre)
    # 20% de los clientes incluyen CIF en la descripción
    if random.random() < 0.2:
        desc = f"{nombre} ({gen_cif()})"
    else:
        desc = nombre
    amounts = gen_amounts(magnitud=random.uniform(1000, 80000))
    rows.append((code, desc, *amounts))

# Algunas variantes de los top 10 clientes (sin sufijo, abreviadas)
print("  Generando variantes de top clientes...")
for nombre in clientes_creados[:10]:
    # Variante sin sufijo societario
    variante_sin = nombre.replace(" S.L.", "").replace(" S.A.", "").replace(" S.L.U.", "").replace(" S.A.U.", "")
    if variante_sin != nombre and random.random() < 0.5:
        code = f"43010{random.randint(0, 9999):05d}"
        amounts = gen_amounts(magnitud=5000)
        rows.append((code, variante_sin, *amounts))

# Proveedores 410xxx
print("  Generando proveedores...")
num_proveedores = 200
for i in range(num_proveedores):
    code = f"41000{i:05d}"
    nombre = gen_nombre_empresa()
    if random.random() < 0.15:
        desc = f"{nombre}, CIF {gen_cif()}"
    else:
        desc = nombre
    amounts = gen_amounts(magnitud=random.uniform(500, 50000))
    rows.append((code, desc, *amounts))

# Acreedores varios 410xxx
print("  Generando acreedores...")
for i in range(40):
    code = f"41100{i:05d}"
    nombre = gen_nombre_empresa()
    amounts = gen_amounts(magnitud=random.uniform(500, 10000))
    rows.append((code, nombre, *amounts))

# Deudores varios 440xxx
print("  Generando deudores...")
for i in range(60):
    code = f"44000{i:05d}"
    # Mezcla de empresas y personas
    if random.random() < 0.4:
        nombre = gen_nombre_persona()
    else:
        nombre = gen_nombre_empresa()
    amounts = gen_amounts(magnitud=random.uniform(200, 8000))
    rows.append((code, nombre, *amounts))

# Personal 460xxx (anticipos)
print("  Generando personal...")
for i in range(15):
    code = f"46000{i:05d}"
    nombre = gen_nombre_persona()
    desc = f"Anticipo {nombre}"
    amounts = gen_amounts(magnitud=1500)
    rows.append((code, desc, *amounts))

# Cuentas HP, SS, IVA (genéricas, sin anonimización)
for code, desc in CUENTAS_PGC_GENERICAS.items():
    if code.startswith("47"):
        amounts = gen_amounts(20000)
        rows.append((code, desc, *amounts))

# Bancos 572xxx
print("  Generando bancos...")
for i, banco in enumerate(BANCOS_REALES):
    code = f"57200{i:04d}0"
    iban = gen_iban()
    desc = f"{banco} - {iban}"
    amounts = gen_amounts(magnitud=80000)
    rows.append((code, desc, *amounts))

# Caja 570
amounts = gen_amounts(magnitud=2000)
rows.append(("570", "Caja, euros", *amounts))

# Préstamos a corto 520xxx
for i in range(3):
    code = f"52000{i:05d}"
    banco = random.choice(BANCOS_REALES)
    desc = f"Préstamo {banco} ref. {random.randint(100000, 999999)}"
    amounts = gen_amounts(magnitud=120000)
    rows.append((code, desc, *amounts))

# Grupo 6: gastos
print("  Generando gastos...")
for code, desc in CUENTAS_PGC_GENERICAS.items():
    if code.startswith("6"):
        # 623 (servicios profesionales) suele tener subcuentas por proveedor
        if code == "623":
            for i in range(5):
                sub = f"6230{i:05d}"
                desc_sub = f"Servicios profesionales {gen_nombre_empresa()}"
                amounts = gen_amounts(magnitud=15000)
                rows.append((sub, desc_sub, *amounts))
        else:
            amounts = gen_amounts(magnitud=random.uniform(5000, 100000))
            rows.append((code, desc, *amounts))

# Grupo 7: ingresos
print("  Generando ingresos...")
for code, desc in CUENTAS_PGC_GENERICAS.items():
    if code.startswith("7"):
        amounts = gen_amounts(magnitud=random.uniform(50000, 800000))
        rows.append((code, desc, *amounts))


# --- Escribir Excel ---

print(f"\nTotal filas generadas: {len(rows)}")
print("Escribiendo Excel...")

wb = Workbook()
ws = wb.active
ws.title = "Sumas y Saldos 2024"

# Header rows
for r in header_rows:
    ws.append(r)

# Estilo cabecera empresa
ws["A1"].font = Font(bold=True, size=14)
ws["A2"].font = Font(size=11)
ws["A3"].font = Font(italic=True, size=10)

# Estilo fila de columnas
header_fill = PatternFill("solid", fgColor="0066CC")
header_font = Font(bold=True, color="FFFFFF")
for col in range(1, 7):
    c = ws.cell(row=5, column=col)
    c.fill = header_fill
    c.font = header_font
    c.alignment = Alignment(horizontal="center")

# Data rows
for row in rows:
    ws.append(row)

# Anchos columna
for col, width in zip("ABCDEF", [16, 60, 16, 16, 16, 16]):
    ws.column_dimensions[col].width = width

# Formato numérico en columnas C-F
from openpyxl.styles import NamedStyle
for r in range(6, ws.max_row + 1):
    for col in (3, 4, 5, 6):
        ws.cell(row=r, column=col).number_format = "#,##0.00"

# Hoja con desglose mensual de top clientes (más oportunidades de clustering)
ws2 = wb.create_sheet("Mayor Cliente Top 5")
ws2.append([f"Mayor analítico - {NOMBRE_EMPRESA}"])
ws2.append(["Periodo:", PERIODO])
ws2.append([])
ws2.append(["Cliente", "Mes", "Facturado", "Cobrado", "Pendiente"])

for cliente in clientes_creados[:5]:
    # Versiones del nombre
    base = cliente.replace(" S.L.", "").replace(" S.A.", "").replace(" S.L.U.", "").replace(" S.A.U.", "")
    versions = [cliente, base, base.upper()]
    for mes in ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio"]:
        v = random.choice(versions)
        facturado = round(random.uniform(5000, 50000), 2)
        cobrado = round(facturado * random.uniform(0.6, 1.0), 2)
        pendiente = round(facturado - cobrado, 2)
        ws2.append([v, mes, facturado, cobrado, pendiente])

# Hoja extra con info de contactos comerciales
ws3 = wb.create_sheet("Contactos")
ws3.append([f"Contactos comerciales - {NOMBRE_EMPRESA}"])
ws3.append([])
ws3.append(["Cliente", "Contacto", "Cargo", "Email", "Teléfono", "Dirección"])
for cliente in clientes_creados[:15]:
    contacto = gen_nombre_persona()
    cargo = random.choice(["Director General", "CFO", "Director Comercial", "Responsable de Compras", "CEO"])
    base = cliente.lower().replace(" s.l.", "").replace(" s.a.", "").replace(" ", "")[:20]
    email = f"{contacto.split()[0].lower()}.{contacto.split()[1].lower()}@{base}.com"
    telefono = f"+34 {random.randint(600, 999)} {random.randint(100, 999)} {random.randint(100, 999)}"
    direccion = f"C/ {random.choice(['Mayor', 'Real', 'Gran Vía', 'Princesa', 'Castellana', 'Diagonal'])} {random.randint(1, 200)}, {random.choice(['Madrid', 'Barcelona', 'Valencia', 'Sevilla', 'Bilbao'])}"
    ws3.append([cliente, contacto, cargo, email, telefono, direccion])

for col, width in zip("ABCDEF", [40, 25, 22, 35, 18, 50]):
    ws3.column_dimensions[col].width = width

out = FIXTURES / "sumas_saldos_sintetico.xlsx"
wb.save(str(out))

# Stats
n_clientes = sum(1 for r in rows if r[0].startswith("43"))
n_proveedores = sum(1 for r in rows if r[0].startswith(("410", "411")))
n_deudores = sum(1 for r in rows if r[0].startswith("44"))
n_personal = sum(1 for r in rows if r[0].startswith("46"))
n_total = ws.max_row - 5

print(f"\n=== Fixture generado ===")
print(f"  Archivo:        {out}")
print(f"  Filas totales:  {n_total}")
print(f"  Clientes:       {n_clientes}")
print(f"  Proveedores:    {n_proveedores}")
print(f"  Deudores:       {n_deudores}")
print(f"  Personal:       {n_personal}")
print(f"  Hojas:          {[s for s in wb.sheetnames]}")
print(f"  Tamaño:         {out.stat().st_size // 1024} KB")
