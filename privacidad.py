"""
Quitar datos personales de un texto ANTES de enviarlo a un servicio externo (IA).

Se usa para las biografías y para los CV. Conserva lo profesional (empresas, cargos, tecnologías, fechas)
y quita: nombre de la persona, correos, teléfonos, enlaces y usuarios de redes, direcciones, documentos de
identidad, datos de nacimiento y estado civil, y las secciones de referencias (datos de terceros).

Limitación honesta: es una limpieza por reglas, no una garantía absoluta. Por eso la persona confirma el
procesamiento y puede ver exactamente qué texto se envió.
"""

import re
import unicodedata

_CLASES = {
    "a": "[aáàäâ]",
    "e": "[eéèëê]",
    "i": "[iíìïî]",
    "o": "[oóòöô]",
    "u": "[uúùüû]",
    "n": "[nñ]",
}

# Etiquetas que introducen un dato personal: se elimina la línea completa ("Teléfono: 300 123 4567")
_ETIQUETAS = (
    r"direcci[oó]n|domicilio|residencia|tel[eé]fono|tel\.?|celular|cel\.?|m[oó]vil|whatsapp|"
    r"correo(?: electr[oó]nico)?|e-?mail|fecha de nacimiento|lugar de nacimiento|nacimiento|edad|"
    r"c[eé]dula|documento(?: de identidad)?|identificaci[oó]n|nit|estado civil|nacionalidad|"
    r"libreta militar|pasaporte|g[eé]nero|sexo|tipo de sangre|jefe inmediato|jefe directo|contacto|"
    r"linkedin|github|portafolio|portfolio|sitio web|p[aá]gina web"
)
_RE_LINEA_PERSONAL = re.compile(
    rf"^[ \t]*(?:{_ETIQUETAS})[ \t]*[:\-–][^\n]*$", re.IGNORECASE | re.MULTILINE
)
_RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_RE_ENLACE = re.compile(
    r"(?:https?://\S+|www\.\S+|\S*(?:linkedin|github|gitlab|behance|facebook|instagram|twitter|x)\.com\S*)",
    re.IGNORECASE,
)
_RE_USUARIO = re.compile(r"(?<![\w.])@[A-Za-z0-9_.]{3,}")
_RE_TELEFONO = re.compile(r"\+?\d[\d\s().-]{5,}\d")
_RE_DOCUMENTO = re.compile(
    r"\b(?:c\.?\s?c\.?|cc|c[eé]dula(?: de ciudadan[ií]a)?|t\.?\s?i\.?|pasaporte)\s*(?:n[oº°]\.?|#)?\s*[\d.\s]{6,}",
    re.IGNORECASE,
)
_RE_DIRECCION = re.compile(
    r"\b(?:calle|carrera|cra\.?|cr\.?|cl\.?|kr\.?|avenida|av\.?|diagonal|diag\.?|transversal|tv\.?|manzana|mz\.?)"
    r"\s*\d+[\w]*(?:\s*(?:#|no\.?|n[oº°])?\s*\d+[\w]*)?(?:\s*[-–]\s*\d+)?(?:[ ,]+(?:barrio|apto\.?|apartamento|casa|torre|int\.?)\s*[\w ]{0,25})?",
    re.IGNORECASE,
)
# Secciones de referencias: contienen datos de OTRAS personas
_RE_ENCABEZADO_REFERENCIAS = re.compile(
    r"^[ \t]*referencias?(?:\s+(?:personales|laborales|profesionales|familiares))?\s*:?\s*$",
    re.IGNORECASE,
)
_RE_ENCABEZADO_SECCION = re.compile(
    r"^[ \t]*[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ \t/&-]{3,40}:?[ \t]*$"
)


# Palabras que delatan que una línea es un título, un encabezado de sección o un perfil, y NO un nombre de persona
_NO_ES_NOMBRE = re.compile(
    r"ingenier|t[eé]cnic|tecn[oó]log|analista|desarrollador|gerente|coordinador|director|especialista|estudiante|profesional|"
    r"telecomunic|redes|software|sistemas|curr[ií]culum|hoja de vida|resume|\bcv\b|perfil|datos|informaci|contacto|experiencia|"
    r"educaci|formaci|habilidades|competencias|universidad|developer|engineer|manager|analyst|student|senior|junior|consultor|"
    r"dise[nñ]ador|administrador|arquitect|l[ií]der|auxiliar|asistente|egresado|magister|mag[ií]ster|especializaci",
    re.IGNORECASE,
)


_PARTICULAS = {"de", "del", "la", "las", "los", "y", "van", "von", "da", "dos", "san"}


def _quitar_nombre_encabezado(texto: str):
    """
    El nombre de la persona casi siempre es la primera línea del CV, y puede no coincidir con el del registro
    (segundo apellido, nombres de más o de menos). Si una de las 3 primeras líneas parece un nombre
    (2 a 5 palabras, solo letras, sin palabras de cargo ni de sección) se reemplaza SOLO esa línea.
    """
    lineas, vistas = texto.split("\n"), 0  # devuelve (texto, nombre_detectado o "")
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        vistas += 1
        if vistas > 3:
            break
        limpia = linea.strip()
        palabras = limpia.split()
        parece_nombre = (
            2 <= len(palabras) <= 5
            and len(limpia) <= 60
            and re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ.' -]+", limpia) is not None
            and not _NO_ES_NOMBRE.search(limpia)
            # un nombre tiene todas sus palabras en mayúscula inicial (salvo "de", "del"...); una frase con verbos no
            and all(w[0].isupper() or w.lower() in _PARTICULAS for w in palabras)
        )
        if parece_nombre:
            lineas[i] = "[PERSONA]"
            return "\n".join(lineas), limpia
    return texto, ""


def _clases(token: str) -> str:
    """Un token como patrón que acepta con o sin tildes (Páez = Paez)."""
    base = (
        unicodedata.normalize("NFKD", token).encode("ASCII", "ignore").decode().lower()
    )
    return "".join(_CLASES.get(c, re.escape(c)) for c in base)


def _patron_sin_tildes(token: str) -> str:
    return r"\b" + _clases(token) + r"\b"


def _enmascarar_nombre(texto: str, nombre: str):
    """
    Una vez detectado el nombre en el encabezado, se enmascara DONDE SEA que aparezca completo o en partes de 2 o más
    palabras seguidas ("Camilo Andrés", "Rojas Mejía"...). Es lo que atrapa los encabezados repetidos de cada página.
    No se enmascaran palabras sueltas del nombre (podrían ser parte de una empresa); las del nombre registrado sí, aparte.
    """
    tokens = [w for w in re.findall(r"[^\W\d_]+", nombre) if len(w) >= 2]
    total = 0
    for largo in range(len(tokens), 1, -1):
        for i in range(len(tokens) - largo + 1):
            secuencia = tokens[i : i + largo]
            if all(w.lower() in _PARTICULAS for w in secuencia):
                continue
            patron = r"\b" + r"[ \t]+".join(_clases(w) for w in secuencia) + r"\b"
            texto, n = re.subn(patron, "[PERSONA]", texto, flags=re.IGNORECASE)
            total += n
    return texto, total


def _quitar_referencias(texto: str):
    """Elimina el bloque que sigue a un encabezado 'Referencias' hasta el siguiente encabezado en mayúsculas."""
    lineas, salida, quitadas, omitiendo = texto.split("\n"), [], 0, False
    for linea in lineas:
        if _RE_ENCABEZADO_REFERENCIAS.match(linea):
            omitiendo, quitadas = True, quitadas + 1
            continue
        if (
            omitiendo
            and _RE_ENCABEZADO_SECCION.match(linea)
            and not _RE_ENCABEZADO_REFERENCIAS.match(linea)
        ):
            omitiendo = False
        if omitiendo:
            quitadas += 1 if linea.strip() else 0
            continue
        salida.append(linea)
    return "\n".join(salida), quitadas


def anonimizar_con_informe(
    texto: str, nombre: str = "", detectar_encabezado: bool = True
):
    """
    Devuelve (texto_limpio, informe) donde el informe cuenta qué se quitó, para mostrárselo a la persona.
    `detectar_encabezado` solo tiene sentido en un CV (el nombre va en la primera línea); en prosa se desactiva.
    """
    t = str(texto or "").replace("\r\n", "\n").replace("\r", "\n")
    informe = {}

    cuenta_tel = {"n": 0}

    def _telefono(m):
        digitos = re.sub(r"\D", "", m.group())
        # 9+ dígitos (o 8+ con '+') es un teléfono; un rango de años como "2015 - 2020" (8 dígitos) se conserva
        if len(digitos) >= 9 or (
            m.group().lstrip().startswith("+") and len(digitos) >= 8
        ):
            cuenta_tel["n"] += 1
            return " "
        return m.group()

    t = _RE_TELEFONO.sub(_telefono, t)
    informe["telefonos"] = cuenta_tel["n"]

    nombre_encabezado, n_encabezado = "", 0
    if detectar_encabezado:
        t, nombre_encabezado = _quitar_nombre_encabezado(t)
        if nombre_encabezado:
            n_encabezado = 1
            t, repetidos = _enmascarar_nombre(
                t, nombre_encabezado
            )  # encabezados repetidos, pies de página, etc.
            n_encabezado += repetidos
    t, informe["referencias"] = _quitar_referencias(t)
    t, informe["lineas_personales"] = _RE_LINEA_PERSONAL.subn("", t)
    t, informe["correos"] = _RE_CORREO.subn(" ", t)
    t, informe["enlaces"] = _RE_ENLACE.subn(" ", t)
    t, n_usuarios = _RE_USUARIO.subn(" ", t)
    informe["enlaces"] += n_usuarios
    t, informe["documentos"] = _RE_DOCUMENTO.subn(" ", t)
    t, informe["direcciones"] = _RE_DIRECCION.subn(" ", t)

    nombre_quitado = 0
    for token in re.findall(r"\w+", str(nombre or "")):
        if len(token) >= 3:
            t, n = re.subn(
                _patron_sin_tildes(token), "[PERSONA]", t, flags=re.IGNORECASE
            )
            nombre_quitado += n
    informe["nombre"] = nombre_quitado + n_encabezado

    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"(?:[ \t]*\n){3,}", "\n\n", t).strip()
    return t, informe


def anonimizar(texto: str, nombre: str = "") -> str:
    """Versión simple para PROSA (biografías): solo el texto, sin detectar encabezado de CV."""
    return anonimizar_con_informe(texto, nombre, detectar_encabezado=False)[0]


def resumen_informe(informe: dict) -> str:
    """Frase para la persona: 'Quitamos: 1 correo, 2 teléfonos…'"""
    nombres = [
        ("correos", "correo", "correos"),
        ("telefonos", "teléfono", "teléfonos"),
        ("enlaces", "enlace o usuario de red", "enlaces o usuarios de red"),
        ("direcciones", "dirección", "direcciones"),
        ("documentos", "documento de identidad", "documentos de identidad"),
        (
            "lineas_personales",
            "línea de datos personales",
            "líneas de datos personales",
        ),
        ("referencias", "línea de referencias", "líneas de referencias"),
        ("nombre", "mención de tu nombre", "menciones de tu nombre"),
    ]
    partes = [
        f"{informe[k]} {s if informe[k] == 1 else p}"
        for k, s, p in nombres
        if informe.get(k)
    ]
    return (
        ", ".join(partes) if partes else "no encontramos datos de contacto que quitar"
    )
