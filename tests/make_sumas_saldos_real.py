"""Genera un sumas y saldos sintético que REPLICA los patrones reales que
romperon la herramienta:

- Múltiples hojas mensuales ("Mayo 25", "Septiembre 25", "Mayo 24"...)
- Hoja "Agregado" con fórmulas SUMIFS cruzadas entre hojas
- Headers de Sage/A3 ("Subcuenta", "Concepto", "Saldo Anterior", "Mvto. Debe")
- Datos con abreviaturas fiscales (HP, SS, IS, IVA SOPORTADO, IVA REPERCUTIDO)
- Algunos contactos solo con nombre propio (típico de cuentas de crédito a personas)
- Cuentas mezcladas: PGC formales + extras tipo "PRESTAMOS A C/P JUAN PEDRO"

Todos los datos son sintéticos.
"""
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

random.seed(7)
FIXTURES = Path(__file__).parent / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

EMPRESA = "Aromas y Sabores del Mediterráneo S.L."

# Empresas y personas que deben detectarse
EMPRESAS = [
    ("4300000001", "BANCO SABADELL, S.A."),
    ("4300000002", "CAIXABANK, SA"),
    ("4300000003", "PREVENPYME, SL"),
    ("4300000004", "EVENTOS MEDITERRÁNEOS, SL"),
    ("4300000005", "DISTRIBUCIONES BADIA"),
    ("4300000006", "INMOBILIARIA TUSET SLU"),
    ("4300000007", "ASESORÍA MIRALLES"),
    ("4300000008", "FRUTAS CARIÑENA S.L."),
    ("4300000009", "ARNAU TORRES DKAIDEK"),
    ("4300000010", "NATALIA POLO CHOCANO"),
    ("4300000011", "ADRIANA HUERTAS"),
    ("4300000012", "HORTENSIA HERRERO"),
    ("4300000013", "FUNDACIÓN ARTE HORTENSIA HERRERO"),
    ("4300000014", "TALLERES MONTANER"),
    ("4300000015", "BENLLOCH Y ASOCIADOS"),
    ("4300000016", "MODICA E HIJOS S.L."),
    ("4300000017", "ASENSI CONSULTORES"),
    ("4300000018", "RIERA INVERSIONES SL"),
    ("4300000019", "BELLO LOGÍSTICA"),
    ("4300000020", "VALCARCEL HERMANOS"),
    # Cuentas extra con personas en la descripción
    ("4400000001", "PRÉSTAMOS A C/P JUAN PEDRO"),
    ("4400000002", "CRÉDITOS A C/P MIGUEL CAMACHO"),
    ("4400000003", "ANTICIPO LAURA GURREA"),
    ("4400000004", "ANTICIPO BEATRIZ HERGUETA"),
    ("4400000005", "ANTICIPO CAROLINA LLARIO"),
    ("4400000006", "ANTICIPO CLARA SANTAMARIA"),
    # Proveedores
    ("4100000001", "DISTRIBUCIONES CHUST S.L."),
    ("4100000002", "MAYORISTAS LAMATA"),
    ("4100000003", "TR LOGÍSTICA Y TRANSPORTES JUAN LARA SL"),
    ("4100000004", "PUBLICIDAD ALBA EVENTOS"),
]

# Cuentas PGC genéricas que NO se deben anonimizar (cabeceras / tributos / generales)
GENERICAS = [
    ("100", "Capital social"),
    ("129", "Resultado del ejercicio"),
    ("281", "Amortización acumulada del inmovilizado material"),
    ("4720", "H.P. IVA SOPORTADO"),
    ("4770", "H.P. IVA REPERCUTIDO"),
    ("4751", "H.P. Acreedora por IS"),
    ("4752", "H.P. Acreedora por IRPF"),
    ("4760", "Organismos de la Seguridad Social acreedores"),
    ("570", "Caja, euros"),
    ("572", "Bancos e instituciones de crédito c/c vista, euros"),
    ("600", "Compras de mercaderías"),
    ("621", "Arrendamientos y cánones"),
    ("622", "Reparaciones y conservación"),
    ("623", "Servicios de profesionales independientes"),
    ("624", "Transportes"),
    ("625", "Primas de seguros"),
    ("627", "Publicidad, propaganda y RRPP"),
    ("628", "Suministros"),
    ("629", "Otros servicios"),
    ("630", "Impuesto sobre beneficios"),
    ("631", "Otros tributos"),
    ("640", "Sueldos y salarios"),
    ("642", "Seguridad Social a cargo de la empresa"),
    ("700", "Ventas de mercaderías"),
    ("705", "Prestaciones de servicios"),
]

# Estructura tipo Sage/A3 con columnas:
# Subcuenta | Concepto | Saldo Anterior | Mvto. Debe | Mvto. Haber | Saldo Actual

def gen_amounts(mag=10000):
    sa = round(random.uniform(-mag * 0.3, mag), 2)
    md = round(random.uniform(0, mag * 4), 2)
    mh = round(random.uniform(0, mag * 4), 2)
    sf = round(sa + md - mh, 2)
    return sa, md, mh, sf


def build_monthly_sheet(ws, mes_label, with_formulas: bool = False):
    """Construye una hoja mensual estilo Sage."""
    # Filas de cabecera (info empresa + periodo)
    ws.append([EMPRESA])
    ws.append([f"Sumas y Saldos {mes_label}"])
    ws.append([])
    # Header de la tabla (estilo Sage: Subcuenta, Concepto, Saldo Anterior, Mvto. Debe, Mvto. Haber, Saldo Actual)
    headers = ["Subcuenta", "Concepto", "Saldo Anterior", "Mvto. Debe", "Mvto. Haber", "Saldo Actual"]
    ws.append(headers)
    header_fill = PatternFill("solid", fgColor="305496")
    header_font = Font(bold=True, color="FFFFFF")
    for c in range(1, 7):
        cell = ws.cell(row=4, column=c)
        cell.fill = header_fill
        cell.font = header_font

    # Datos
    all_rows = []
    for code, desc in GENERICAS:
        all_rows.append((code, desc, *gen_amounts(20000)))
    for code, desc in EMPRESAS:
        all_rows.append((code, desc, *gen_amounts(15000)))

    # Si queremos fórmulas, insertamos algunas filas con fórmulas SUMIFS rotas
    # (esto simula lo que vi en el archivo real)
    if with_formulas:
        for i in range(5):
            row = [
                f"99{i:03d}",  # código fake
                f"FÓRMULA EXTERNA {i}",
                f"=SUMIFS('Mayo 25'!$E:$E,'Mayo 25'!$A:$A,A{10+i})",
                f"=+AB{10+i}+BK{10+i}",
                f"=SUMIFS('Septiembre 25'!$F:$F,'Septiembre 25'!$A:$A,A{20+i})",
                f"=H{10+i}+AQ{10+i}-SUMIFS('Octubre 25'!$F:$F,'Octubre 25'!$A:$A,A{10+i})",
            ]
            all_rows.append(tuple(row))

    for row in all_rows:
        ws.append(row)

    # Anchos
    for col, width in zip("ABCDEF", [16, 50, 16, 16, 16, 16]):
        ws.column_dimensions[col].width = width


# Construir el workbook
wb = Workbook()
ws_default = wb.active
wb.remove(ws_default)

# 5 hojas mensuales
for mes in ["Mayo 24", "Junio 24", "Septiembre 24", "Octubre 24", "Mayo 25"]:
    ws = wb.create_sheet(mes)
    build_monthly_sheet(ws, mes, with_formulas=True)

# Hoja "Agregado" con fórmulas cruzadas
ws_agr = wb.create_sheet("Agregado")
ws_agr.append([EMPRESA])
ws_agr.append(["Sumas y Saldos AGREGADO 2024-2025"])
ws_agr.append([])
ws_agr.append(["Subcuenta", "Concepto", "Total Debe", "Total Haber", "Saldo Final"])
for code, desc in (GENERICAS + EMPRESAS):
    ws_agr.append([
        code,
        desc,
        f"=SUMIFS('Mayo 25'!$D:$D,'Mayo 25'!$A:$A,A5)",
        f"=SUMIFS('Mayo 25'!$E:$E,'Mayo 25'!$A:$A,A5)",
        f"=+C5-D5",
    ])

out = FIXTURES / "sumas_saldos_realista.xlsx"
wb.save(str(out))
print(f"Generado: {out}")
print(f"Hojas: {wb.sheetnames}")
print(f"Tamaño: {out.stat().st_size // 1024} KB")
print(f"Empresas a detectar: {len(EMPRESAS)}")
print(f"Cuentas PGC genéricas (NO deben anonimizarse): {len(GENERICAS)}")
