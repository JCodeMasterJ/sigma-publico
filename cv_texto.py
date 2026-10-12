"""
Leer el texto de un CV en PDF, EN MEMORIA (el archivo no se guarda en ningún lado), y limpiarlo antes de enviarlo.

Como el PDF lo sube una persona, se ponen límites: tamaño, número de páginas y tiempo de lectura.
Todo error se devuelve como CVError con un mensaje para la persona; nunca se muestran detalles internos.
"""

import io
import re
import threading

from privacidad import anonimizar_con_informe

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PAGINAS = 12
MAX_CARACTERES = 20000  # lo máximo que se envía a la IA
MIN_CARACTERES = 200  # menos que esto = PDF escaneado (imagen) o vacío
SEGUNDOS_LECTURA = 25


class CVError(Exception):
    """Error con mensaje listo para mostrarle a la persona."""


def _con_limite(funcion, segundos):
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
        raise CVError(
            "Tu PDF tardó demasiado en leerse. Prueba con otra versión del archivo o llena el formulario a mano."
        )
    if "error" in caja:
        raise caja["error"]
    return caja["valor"]


def extraer_texto_pdf(datos: bytes) -> str:
    if not datos or not datos.startswith(b"%PDF"):
        raise CVError(
            "El archivo no parece un PDF. Sube tu hoja de vida en formato PDF."
        )
    if len(datos) > MAX_BYTES:
        raise CVError(
            f"El archivo pesa más de {MAX_BYTES // (1024 * 1024)} MB. Sube una versión más liviana."
        )
    try:
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(datos))
        if lector.is_encrypted:
            try:
                if not lector.decrypt(""):
                    raise CVError(
                        "Tu PDF está protegido con contraseña. Sube una versión sin protección."
                    )
            except CVError:
                raise
            except Exception:  # noqa: BLE001
                raise CVError(
                    "Tu PDF está protegido con contraseña. Sube una versión sin protección."
                )
        if len(lector.pages) > MAX_PAGINAS:
            raise CVError(
                f"Tu archivo tiene {len(lector.pages)} páginas; para un CV el máximo es {MAX_PAGINAS}."
            )
        texto = _con_limite(
            lambda: "\n".join((p.extract_text() or "") for p in lector.pages),
            SEGUNDOS_LECTURA,
        )
    except CVError:
        raise
    except ImportError:
        raise CVError(
            "La lectura de PDF no está disponible en este momento. Llena el formulario a mano."
        )
    except Exception:  # noqa: BLE001
        raise CVError(
            "No pudimos leer ese PDF. Prueba con otra versión del archivo o llena el formulario a mano."
        )
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    if len(texto) < MIN_CARACTERES:
        raise CVError(
            "Tu PDF parece una imagen escaneada, no tiene texto que podamos leer. "
            "Sube un PDF con texto seleccionable o llena el formulario a mano."
        )
    return texto


def preparar_texto_cv(datos: bytes, nombre: str):
    """PDF -> (texto sin datos personales, informe de lo que se quitó). Lo único que sale del servidor es ese texto."""
    texto = extraer_texto_pdf(datos)
    limpio, informe = anonimizar_con_informe(texto, nombre)
    if len(limpio) < 100:
        raise CVError(
            "Después de quitar los datos personales casi no quedó contenido que analizar. "
            "Llena el formulario a mano."
        )
    informe["truncado"] = len(limpio) > MAX_CARACTERES
    return limpio[:MAX_CARACTERES], informe
