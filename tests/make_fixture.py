"""Genera un .xlsx sintético para probar el anonimizador.

NO usa datos reales de clientes. Todos los nombres, NIF, IBAN son inventados.
"""
from pathlib import Path

from openpyxl import Workbook

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

wb = Workbook()
ws = wb.active
ws.title = "Resumen Global Menta"

rows = [
    ["Compañía", "CIF", "IBAN", "Contacto", "Email", "Dirección"],
    ["Global Menta S.L.", "B12345678", "ES9121000418450200051332", "Juan Pérez García", "juan.perez@globalmenta.com", "C/ Mayor 25, Madrid"],
    ["GlobalMenta", "B12345678", "ES9121000418450200051332", "María López Ruiz", "maria.lopez@globalmenta.com", "C/ Mayor 25, Madrid"],
    ["Tropical Frutas SA", "A87654321", "ES9000492352082414205416", "Carlos Sánchez", "csanchez@tropicalfrutas.es", "Avenida de la Constitución 100, Sevilla"],
    ["Tropical Frutas, S.A.", "A87654321", "", "Carlos Sánchez", "", ""],
]
for r in rows:
    ws.append(r)

ws2 = wb.create_sheet("EBITDA")
ws2.append(["Concepto", "2023", "2024", "Comentario"])
ws2.append(["Ingresos Global Menta", 12500000, 14200000, "Crecimiento orgánico"])
ws2.append(["EBITDA Global Menta S.L.", 2100000, 2700000, "Mejora de margen Global Menta"])
ws2.append(["Ingresos Tropical Frutas", 5400000, 5900000, ""])

out = FIXTURES / "deal_sintetico.xlsx"
wb.save(str(out))
print(f"Creado: {out}")
