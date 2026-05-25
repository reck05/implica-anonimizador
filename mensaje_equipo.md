# Mensaje listo para enviar al equipo

> Copia y pega los bloques que necesites. Sustituye `<IP>`, `<CONTRASEÑA>` y `<TU_NOMBRE>` por los valores reales.

---

## Versión corta (Slack / Teams)

```
Hola equipo 👋

He montado una herramienta interna para anonimizar documentos M&A
(teasers, datapacks, memos). Reemplaza nombres de empresas y datos
sensibles (CIF, NIF, IBAN, personas) por los codenames de proyecto que
usamos en los teasers — por ejemplo "Global Menta S.L." → "Paradise".

🔗 URL: http://<IP>:8501
🔑 Contraseña: <CONTRASEÑA>

Funciona con Excel, Word, PowerPoint y PDF. 100% en nuestro servidor,
ningún documento sale de Implica.

Guía de uso: archivo USER_GUIDE.md en la carpeta del servidor (o pídeme
una copia).

Cualquier duda o si echáis en falta algo, decidme.

— <TU_NOMBRE>
```

---

## Versión larga (email)

**Asunto:** Nueva herramienta interna: anonimizador de documentos M&A

```
Hola a todos,

Hemos puesto en marcha una herramienta interna para automatizar la
anonimización de documentos en deals, algo que hasta ahora hacíamos
manualmente con buscar-y-reemplazar y nos llevaba bastante tiempo
en datapacks grandes.

QUÉ HACE
--------
Reemplaza en un documento (o varios a la vez) los nombres de empresas
y datos identificadores por los codenames de proyecto del teaser.
Detecta automáticamente:

  - Nombres de empresa (todas sus variantes: "Global Menta S.L.",
    "GlobalMenta", "Global Menta" se reemplazan por "Paradise")
  - Personas (CEO, accionistas, contactos)
  - CIF, NIF, IBAN, emails, teléfonos, direcciones

Funciona con Excel, Word, PowerPoint y PDF, manteniendo el formato
original.

CÓMO USARLA
-----------
1. Conéctate a la red de oficina (o VPN).
2. Abre el navegador en: http://<IP>:8501
3. Contraseña: <CONTRASEÑA>
4. Introduce el codename del proyecto (paradise, eden, atlas…)
5. Sube los archivos
6. Revisa los candidatos detectados (descarta falsos positivos,
   ajusta codenames)
7. Descarga el ZIP con todo anonimizado

La primera vez por proyecto te pregunta los codenames; las siguientes
veces los reutiliza automáticamente.

SEGURIDAD
---------
- Todo corre en nuestro servidor de oficina, ningún archivo sale a
  internet.
- Acceso solo desde la red interna (o VPN).
- Los archivos subidos se borran al cerrar la pestaña.
- Los codenames que usemos en un deal se guardan para reutilizarlos
  en datapacks que lleguen después del mismo deal.

LIMITACIONES
------------
- PDFs escaneados sin OCR no se detectan. Pasadlos por Acrobat
  primero ("Reconocer texto").
- Imágenes/logos dentro de un Excel no se tocan. Borradlas a mano si
  hay riesgo.
- Si la herramienta no detecta un nombre concreto, decidme y lo añado
  al diccionario.

PRÓXIMOS PASOS
--------------
Probadla con un deal real esta semana. Recopilaremos feedback y
mejoraremos lo que haga falta:
  - Más formatos
  - Reglas específicas por sector
  - Integración con OneDrive/SharePoint si tiene sentido

Cualquier bug, sugerencia o documento donde no funcione bien:
mandádmelo y le echo un ojo.

Un saludo,
<TU_NOMBRE>
```

---

## Notas para ti (Ricardo)

Cuando IT te dé la IP del servidor donde se instale:

1. Sustituye `<IP>` y `<CONTRASEÑA>` arriba.
2. Mándale el mensaje al equipo por el canal habitual.
3. Avisa también de que la **carpeta `projects/` del servidor contiene los nombres reales** de los clientes asociados a cada codename — quien tenga acceso al servidor puede ver esas correspondencias. Restringid el acceso al servidor a la gente que ya tiene acceso al CRM.
4. Considera un primer training rápido (15 min en una reunión) la primera vez: subir un teaser real, ver cómo detecta variantes, etc. Es más útil que cualquier doc.
