"""
Aviso de privacidad y tratamiento de datos de SIGMA.

TEXTO_AUTORIZACION es el aviso de privacidad y autorización de la Facultad de Ingeniería de Telecomunicaciones, tal como lo entregó
la Facultad: NO se modifica ni se parafrasea (hay una prueba que lo vigila). Las demás secciones describen cómo funciona SIGMA con los
datos y son una descripción técnica del proyecto, que la oficina jurídica puede revisar o ampliar.

El canal de contacto se configura con la variable CONTACTO_PRIVACIDAD (en los secretos de Streamlit o en el .env): así el correo no queda
escrito en el código.
"""

import os


TEXTO_AUTORIZACION = (
    "La Facultad de Ingeniería de Telecomunicaciones de la Universidad Santo Tomás agradece su colaboración en el diligenciamiento de la "
    "información solicitada. De conformidad con la Ley 1581 de 2012, el Decreto 1074 de 2015 y demás normas vigentes sobre protección de "
    "datos personales, solicita su autorización previa, libre, expresa e informada para el tratamiento de los datos suministrados a través "
    "de esta aplicación. La información será utilizada para mantener actualizados los datos de los graduados, facilitar la comunicación "
    "institucional, promover actividades académicas y de relacionamiento, y fortalecer el vínculo entre los graduados, la Facultad y la "
    "Universidad."
)


def contacto() -> str:
    return os.environ.get("CONTACTO_PRIVACIDAD", "").strip()


def aviso_markdown() -> str:
    canal = contacto() or "*(pendiente de definir por la Facultad)*"
    return f"""> Las secciones 1 y 2 son el aviso de la Facultad y su canal de contacto. Las demás explican cómo funciona SIGMA con tus datos:
> son una descripción técnica del proyecto que la oficina jurídica de la Universidad puede revisar o ampliar.

### 1. Aviso de privacidad y autorización de la Facultad
{TEXTO_AUTORIZACION}

### 2. Quién es el responsable y cómo contactarnos
Universidad Santo Tomás, seccional Bucaramanga, Facultad de Ingeniería de Telecomunicaciones. SIGMA es un proyecto académico en
desarrollo (Proyecto Integrador 2026-2). Canal para consultas, reclamos y solicitudes sobre tus datos: {canal}.

### 3. Para qué se usan tus datos en SIGMA
Además de las finalidades del aviso de la Facultad (punto 1), en SIGMA tus datos sirven para hacer seguimiento a la trayectoria de los
egresados y producir indicadores e informes de seguimiento y acreditación del programa. Los informes muestran cifras agrupadas, no
personas. No vendemos tus datos ni los usamos con fines comerciales.

### 4. Qué datos se guardan, quién los ve y por cuánto tiempo
| Dato | Para qué | Quién puede verlo | Cuánto se conserva |
|---|---|---|---|
| Nombre, año de grado y correo | Identificarte y vincular tu cuenta a tu registro | Tú y la administración del programa | Mientras dure el proyecto o hasta que pidas eliminarlos |
| Situación laboral, empresa, cargo, ciudad y país | Indicadores de seguimiento y acreditación | Tú y la administración; en los informes solo agrupados | Igual que arriba |
| Sector, área y tecnologías | Indicadores; cuando los propone la IA se marcan «inferido por IA» | Tú y la administración | Igual que arriba |
| Fecha y origen de cada declaración, y tu autorización | Demostrar cuándo y cómo se obtuvo cada dato | Tú y la administración | Igual que arriba |
| Cuenta de acceso (correo y contraseña) | Iniciar sesión. La contraseña la gestiona el servicio de autenticación: ni la administración ni este sistema pueden verla | Solo tú (el correo, también la administración) | Hasta que pidas eliminar tu cuenta |
| Tu CV en PDF | Se lee en memoria para proponerte datos. **No se guarda** | Nadie: se descarta al terminar | No se conserva |
| Cuántas veces usaste el análisis de CV | Limitar el uso para proteger la cuota del servicio | La administración | Mientras dure el proyecto |

### 5. Con quién se comparten (proveedores tecnológicos)
SIGMA funciona con servicios de terceros, que reciben los datos necesarios para su función:

| Proveedor | Para qué | Dónde |
|---|---|---|
| Supabase | Base de datos e inicio de sesión | Región de São Paulo (Brasil) |
| Streamlit Community Cloud | Aplicación web | Fuera de Colombia |
| Render | Servicio de agentes de IA | Fuera de Colombia |
| Google (Gemini) | Análisis de texto con inteligencia artificial | Fuera de Colombia |

Esto implica que los datos pueden ser tratados en servidores fuera del país. La Universidad debe confirmar que esto cumple la
normativa aplicable a transferencias y transmisiones internacionales de datos personales.

### 6. Inteligencia artificial
- **Análisis de tu CV (solo si tú lo pides y aceptas):** antes de enviar nada se le quitan tu nombre, correos, teléfonos,
  direcciones, documentos y enlaces. Solo ese texto limpio sale hacia la IA, y puedes ver exactamente cuál fue.
- **Plan gratuito:** el servicio de IA usado es el plan gratuito de Google, cuyos términos permiten que Google use los textos
  que recibe para mejorar sus productos. Si prefieres no usar esta opción, llena el formulario a mano: siempre es posible.
- **La IA solo propone:** tú revisas y corriges todo antes de guardar. Nada se guarda sin tu confirmación.
- **Informes:** la IA que redacta los informes recibe indicadores agrupados, no datos de personas.

### 7. Tus derechos
Como titular de tus datos puedes, en cualquier momento: conocer, actualizar y rectificar tus datos; solicitar prueba de la
autorización que diste; ser informado sobre el uso que se les da; acceder a ellos de forma gratuita; presentar quejas ante la
Superintendencia de Industria y Comercio; y revocar la autorización o solicitar la supresión de tus datos (Ley 1581 de 2012 y
Decreto 1074 de 2015).

### 8. Cómo ejercerlos
- **Corregir o actualizar:** en «Mi perfil», cuando quieras.
- **Obtener una copia:** en «Privacidad y mis datos», con el botón «Descargar mis datos».
- **Eliminar tu perfil, revocar tu autorización, consultar o reclamar:** escribe al canal indicado en el punto 2. La Ley 1581
  fija como plazo máximo 10 días hábiles para responder consultas y 15 días hábiles para atender reclamos.

### 9. Seguridad
Cada egresado solo puede ver su propio registro (permisos por fila en la base de datos). Las cuentas tienen roles
(egresado y administración). El servicio de agentes exige una clave. Las conexiones usan HTTPS.

### 10. Datos de prueba
Parte de los registros del sistema son datos ficticios creados para pruebas y demostraciones. Están marcados como tales y no
corresponden a personas reales.

### 11. Cambios a este aviso
Si este aviso cambia, se actualizará aquí. La versión vigente es la que ves en esta página.
"""
