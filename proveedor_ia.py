"""
Módulo del agente de extracción de CV.
Aislado a propósito: si algún día cambias de proveedor de IA (ej. a Groq),
solo tocas este archivo, nada más del sistema se entera del cambio.
"""

import os
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from google import genai

from taxonomia import AREA_NO_DETERMINADA, AREAS, SECTOR_NO_DETERMINADO, SECTORES
from verificacion_cv import verificar_sugerencia

MODELO = (
    "gemini-3.5-flash-lite"  # 500 peticiones/día gratis, vs. 20/día de gemini-3.8-flash
)


class ExperienciaExtraida(BaseModel):
    empresa: Optional[str] = Field(
        None,
        description="Nombre de la empresa actual o más reciente donde trabaja/trabajó la persona",
    )
    cargo: Optional[str] = Field(None, description="Cargo o puesto de trabajo")
    sector: Optional[str] = Field(
        None,
        description="Sector o industria de la empresa, ej. Telecomunicaciones, Finanzas, Tecnología, Salud",
    )
    tecnologias: List[str] = Field(
        default_factory=list,
        description="Tecnologías, lenguajes de programación o herramientas mencionadas en el documento",
    )
    ubicacion: Optional[str] = Field(None, description="Ciudad donde trabaja")


def _cliente(timeout_s: float = None):
    """Crea el cliente de Gemini leyendo la key desde el .env (nunca hardcodeada).
    Con timeout_s, una petición que Google deje colgada se corta en vez de esperar indefinidamente."""
    from google.genai import types

    opciones = types.HttpOptions(timeout=int(timeout_s * 1000)) if timeout_s else None
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=opciones)


def extraer_datos_cv(ruta_pdf: str) -> ExperienciaExtraida:
    """
    Recibe la ruta a un archivo PDF (CV o perfil de LinkedIn exportado) y devuelve
    los datos estructurados extraídos por el modelo.
    """
    client = _cliente()

    archivo_subido = client.files.upload(file=ruta_pdf)

    prompt = (
        "Este documento es la hoja de vida o perfil profesional de un egresado de "
        "Ingeniería de Telecomunicaciones. Debes extraer dos tipos de información, "
        "buscados en partes distintas del documento — no los mezcles:\n\n"
        "1) DATOS DEL TRABAJO MÁS RECIENTE (busca solo en la experiencia laboral más "
        "reciente): empresa, cargo, sector/industria de esa empresa, ciudad donde trabaja.\n\n"
        "2) TECNOLOGÍAS (busca en TODO el documento completo, sin limitarte al trabajo "
        "más reciente): revisa cada sección por separado — habilidades técnicas, "
        "certificaciones, proyectos personales, educación, y cada experiencia laboral que "
        "aparezca sin importar qué tan antigua sea — y lista absolutamente todas las "
        "tecnologías, lenguajes de programación, frameworks y herramientas mencionadas en "
        "cualquier parte del documento. Esta lista es independiente del trabajo más "
        "reciente: una tecnología que solo aparezca en la sección de 'habilidades' o en un "
        "trabajo antiguo igual debe incluirse, aunque no tenga relación con el trabajo actual.\n\n"
        "Si algún dato del punto 1 no aparece explícitamente, déjalo vacío. No inventes "
        "información que no esté en el texto."
    )

    interaction = client.interactions.create(
        model=MODELO,
        input=[
            {
                "type": "document",
                "uri": archivo_subido.uri,
                "mime_type": archivo_subido.mime_type,
            },
            {"type": "text", "text": prompt},
        ],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": ExperienciaExtraida.model_json_schema(),
        },
    )

    return ExperienciaExtraida.model_validate_json(interaction.output_text)


# ---------------------------------------------------------------------------
# Salida estructurada genérica (la usa el Agente 2: generador de reportes)
# ---------------------------------------------------------------------------
def _schema_sin_refs(modelo) -> dict:
    """
    Pydantic genera esquemas con '$defs' y '$ref' cuando hay modelos anidados.
    Los resolvemos aquí para enviar un esquema plano y no depender de que la API
    soporte referencias.
    """
    schema = modelo.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolver(nodo):
        if isinstance(nodo, dict):
            if "$ref" in nodo:
                nombre = nodo["$ref"].split("/")[-1]
                resuelto = resolver(defs[nombre])
                extras = {k: v for k, v in nodo.items() if k != "$ref"}
                return {**resuelto, **extras}
            return {k: resolver(v) for k, v in nodo.items()}
        if isinstance(nodo, list):
            return [resolver(x) for x in nodo]
        return nodo

    return resolver(schema)


def generar_estructurado(
    prompt: str, modelo, nombre_modelo: str = None, timeout: float = None
):
    """Envía un prompt de solo texto y devuelve la respuesta validada con el modelo Pydantic dado."""
    client = _cliente(timeout)
    interaction = client.interactions.create(
        model=nombre_modelo or MODELO,
        input=[{"type": "text", "text": prompt}],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": _schema_sin_refs(modelo),
        },
    )
    return modelo.model_validate_json(interaction.output_text)


# ---------------------------------------------------------------------------
# Llamadas robustas para procesos por lotes: tiempo límite, reintentos visibles y modelo de respaldo
# ---------------------------------------------------------------------------
def _es_cuota(error: Exception) -> bool:
    m = str(error).lower()
    return (
        "429" in m
        or "too_many_requests" in m
        or "resource_exhausted" in m
        or "rate limit" in m
    )


def _es_transitorio(error: Exception) -> bool:
    m = str(error).lower()
    return any(
        s in m
        for s in (
            "503",
            "500",
            "unavailable",
            "high demand",
            "timeout",
            "timed out",
            "sin respuesta",
            "connection",
        )
    )


def _con_limite_de_tiempo(funcion, segundos: float):
    """Red de seguridad independiente del SDK: si no hay resultado en `segundos`, se abandona la llamada."""
    import threading

    caja = {}

    def correr():
        try:
            caja["valor"] = funcion()
        except BaseException as e:  # noqa: BLE001
            caja["error"] = e

    hilo = threading.Thread(target=correr, daemon=True)
    hilo.start()
    hilo.join(segundos)
    if hilo.is_alive():
        raise TimeoutError(f"sin respuesta en {segundos:.0f} s")
    if "error" in caja:
        raise caja["error"]
    return caja["valor"]


def generar_estructurado_robusto(
    prompt: str,
    modelo,
    modelos=None,
    reintentos: int = 2,
    pausa: float = 5.0,
    timeout: float = 60.0,
    estado: dict = None,
    log=print,
):
    """
    Prueba los modelos en orden. Cada llamada tiene tiempo límite. Si un modelo se queda sin cuota (429) o falla
    todos sus reintentos (saturado/colgado), se descarta para el resto de la ejecución (guardado en `estado`)
    y se pasa al siguiente. Devuelve (resultado, nombre_del_modelo_usado).
    """
    import time

    modelos = modelos or [MODELO]
    estado = estado if estado is not None else {}
    caidos = estado.setdefault("caidos", set())
    ultimo_error = None
    for nombre in modelos:
        if nombre in caidos:
            continue
        for intento in range(1, reintentos + 1):
            try:
                resultado = _con_limite_de_tiempo(
                    lambda: generar_estructurado(prompt, modelo, nombre, timeout),
                    timeout * 2 + 15,
                )
                return resultado, nombre
            except Exception as e:  # noqa: BLE001
                ultimo_error = e
                corto = str(e).replace("\n", " ")[:110]
                if _es_cuota(e):
                    log(
                        f"    ! {nombre}: sin cuota ({corto}). Se descarta para el resto de la ejecución."
                    )
                    caidos.add(nombre)
                    break
                if intento < reintentos:
                    espera = pausa * intento
                    log(
                        f"    ! {nombre}: {corto}. Reintento {intento + 1}/{reintentos} en {espera:.0f} s..."
                    )
                    time.sleep(espera)
                    continue
                log(
                    f"    ! {nombre}: falló {reintentos} veces ({corto}). Se descarta para el resto de la ejecución."
                )
                caidos.add(nombre)
    raise RuntimeError(f"No se pudo completar la llamada a la IA: {ultimo_error}")


# ---------------------------------------------------------------------------
# Extracción desde TEXTO (biografías), no desde PDF
# ---------------------------------------------------------------------------
PROMPT_TEXTO = (
    "Este texto es la biografía profesional de un egresado de Ingeniería de Telecomunicaciones. "
    "Debes extraer dos tipos de información, buscados en partes distintas del texto:\n\n"
    "1) DATOS DEL TRABAJO MÁS RECIENTE: empresa, cargo, sector/industria de esa empresa, ciudad donde trabaja.\n\n"
    "2) TECNOLOGÍAS (busca en TODO el texto): lista absolutamente todas las tecnologías, lenguajes, "
    "frameworks, protocolos, plataformas y herramientas mencionadas en cualquier parte, sin omitir ninguna "
    "por parecer menor o repetida.\n\n"
    "Si algún dato del punto 1 no aparece explícitamente, déjalo vacío. No inventes información que no esté en el texto."
)


def extraer_datos_texto(texto: str) -> ExperienciaExtraida:
    """Extrae empresa, cargo, sector, tecnologías y ciudad desde un texto libre (ya anonimizado)."""
    resultado, _ = generar_estructurado_robusto(
        f"{PROMPT_TEXTO}\n\nTEXTO:\n{texto}", ExperienciaExtraida
    )
    return resultado


# ---------------------------------------------------------------------------
# Sugerencia de perfil desde el texto de un CV (ya sin datos personales)
# ---------------------------------------------------------------------------
class PerfilSugerido(BaseModel):
    empresa: Optional[str] = Field(
        default=None,
        description="Empresa del trabajo MÁS RECIENTE que aparece en el CV.",
    )
    cargo: Optional[str] = Field(default=None, description="Cargo en ese trabajo.")
    ciudad: Optional[str] = Field(
        default=None,
        description="Ciudad donde VIVE la persona, según el encabezado o los datos de contacto del CV. Vacío si no aparece ahí.",
    )
    pais: Optional[str] = Field(
        default=None,
        description="País donde VIVE la persona, según el encabezado o los datos de contacto del CV. Vacío si no aparece ahí.",
    )
    sector: Literal[tuple(SECTORES + [SECTOR_NO_DETERMINADO])] = Field(
        description="Sector económico de esa empresa."
    )
    area_funcional: Literal[tuple(AREAS + [AREA_NO_DETERMINADA])] = Field(
        description="Función que cumple el cargo."
    )
    tecnologias: List[str] = Field(
        default_factory=list,
        description="Máximo 10 tecnologías CONCRETAS (lenguajes, frameworks, plataformas, protocolos, herramientas, equipos) más relevantes para el cargo del trabajo más reciente.",
    )
    otras_tecnologias: List[str] = Field(
        default_factory=list,
        description="Todas las demás tecnologías, herramientas, certificaciones y campos técnicos del documento que NO pusiste en 'tecnologias'.",
    )


PROMPT_PERFIL = (
    "Este texto es la hoja de vida de un egresado de Ingeniería de Telecomunicaciones; ya se le quitaron los datos "
    "de contacto. Extrae datos para precargar un formulario. Busca cada tipo de dato en la parte del documento que le corresponde:\n\n"
    "1) TRABAJO MÁS RECIENTE (solo la experiencia laboral más reciente; si hay uno marcado como actual, ese): empresa y cargo.\n"
    '1b) ciudad y pais: donde VIVE la persona, según el encabezado o los datos de contacto del inicio del CV (por ejemplo "Bucaramanga, Colombia"). '
    "NO uses la ciudad de una empresa, de un proyecto, de un intercambio ni de una universidad. Si el encabezado no la dice, déjalos vacíos.\n"
    "2) sector: sector económico de esa EMPRESA. Elige exactamente uno de: "
    + ", ".join(SECTORES)
    + f", {SECTOR_NO_DETERMINADO}.\n"
    "3) area_funcional: función del CARGO (no de la empresa). Elige exactamente uno de: "
    + ", ".join(AREAS)
    + f", {AREA_NO_DETERMINADA}.\n"
    "4) tecnologias: SOLO tecnologías concretas (lenguajes, frameworks, plataformas, protocolos, herramientas, equipos) que sean relevantes "
    "para el CARGO del trabajo más reciente: las que ese trabajo menciona o usa. MÁXIMO 10. Si ese trabajo no menciona ninguna, elige las 8 más "
    "destacadas del documento. NO pongas aquí certificaciones ni campos generales (como 'Desarrollo Web', 'Cloud' o 'Machine Learning').\n"
    "5) otras_tecnologias: todo lo demás que aparezca en el documento y no hayas puesto en 'tecnologias' (otras tecnologías, certificaciones, "
    "campos técnicos y temas de estudio), sin repetir.\n\n"
    "REGLA ESTRICTA: empresa, cargo, ciudad, país y TODA tecnología que devuelvas deben estar ESCRITAS en el texto, tal como aparecen. "
    "NUNCA agregues una tecnología que no esté en el texto, aunque sea típica del cargo o de la carrera.\n"
    f'No inventes. Si no conoces la empresa o el cargo es ambiguo, usa "{SECTOR_NO_DETERMINADO}" / "{AREA_NO_DETERMINADA}". '
    "Si un dato no aparece en el texto, déjalo vacío."
)


def sugerencia_a_dict(s: PerfilSugerido, texto: str = None) -> dict:
    """
    Normaliza la respuesta de la IA a lo que acepta el formulario (mismos límites que valida la base de datos).
    Si se pasa el texto del CV, además VERIFICA por código que lo propuesto esté escrito en él (la IA propone, el código verifica).
    """

    def texto_corto(v, maximo):
        v = (v or "").strip()
        return v[:maximo] if v else None

    def limpiar(lista, maximo, excluir=()):
        vistas, salida = {x.lower() for x in excluir}, []
        for t in lista or []:
            t = str(t).strip()
            if t and len(t) <= 40 and t.lower() not in vistas:
                vistas.add(t.lower())
                salida.append(t)
        return salida[:maximo]

    todas_principales = limpiar(s.tecnologias, 1000)
    principales = todas_principales[:10]  # las del cargo: precargadas
    # si el modelo se pasó de 10, el sobrante NO se pierde: pasa a las opciones
    otras = limpiar(
        todas_principales[10:] + list(s.otras_tecnologias or []),
        30,
        excluir=principales,
    )
    resultado = {
        "empresa": texto_corto(s.empresa, 120),
        "cargo": texto_corto(s.cargo, 120),
        "ciudad": texto_corto(s.ciudad, 80),
        "pais": texto_corto(s.pais, 80),
        "sector": None if s.sector == SECTOR_NO_DETERMINADO else s.sector,
        "area": None if s.area_funcional == AREA_NO_DETERMINADA else s.area_funcional,
        "tecnologias": principales,
        "otras_tecnologias": otras,
    }
    return verificar_sugerencia(resultado, texto) if texto else resultado


def sugerir_perfil_desde_texto(texto: str) -> dict:
    """Texto de un CV (sin datos personales) -> sugerencia para el formulario. Con tiempo límite y reintentos."""
    resultado, _ = generar_estructurado_robusto(
        f"{PROMPT_PERFIL}\n\nTEXTO DEL CV:\n{texto}",
        PerfilSugerido,
        reintentos=2,
        timeout=60.0,
    )
    return sugerencia_a_dict(resultado, texto)


if __name__ == "__main__":
    # Prueba rápida manual: python proveedor_ia.py mi_cv.pdf
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    ruta = sys.argv[1] if len(sys.argv) > 1 else "prueba.pdf"
    resultado = extraer_datos_cv(ruta)
    print(resultado.model_dump_json(indent=2))
