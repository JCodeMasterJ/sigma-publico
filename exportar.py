"""
Exportaciones de SIGMA.

* Indicadores en CSV: cifras AGRUPADAS (sin datos de personas) para llevarlas a Excel, Power BI, hojas de cálculo u otra aplicación.
* Copia de los datos de una persona en JSON: es su derecho de acceso (ver el aviso de privacidad).
"""

import csv
import io
import json
from datetime import datetime


def _aplanar(valor, ruta=()):
    """Recorre diccionarios anidados y entrega pares (ruta, valor simple). Las listas se unen con '; '."""
    if isinstance(valor, dict):
        for clave, v in valor.items():
            yield from _aplanar(v, ruta + (str(clave),))
    elif isinstance(valor, (list, tuple)):
        yield ruta, "; ".join(str(x) for x in valor)
    else:
        yield ruta, valor


def indicadores_a_filas(indicadores: dict) -> list:
    """(categoria, indicador, valor): la categoría es el primer nivel y el indicador, el resto de la ruta."""
    filas = []
    for ruta, valor in _aplanar(indicadores):
        if not ruta:
            continue
        indicador = " / ".join(ruta[1:]) if len(ruta) > 1 else ruta[0]
        filas.append((ruta[0], indicador, "" if valor is None else valor))
    return filas


def indicadores_a_csv(indicadores: dict, metadatos: dict = None) -> bytes:
    """CSV en UTF-8 con marca de orden (Excel muestra bien las tildes). Columnas: categoria, indicador, valor."""
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(["categoria", "indicador", "valor"])
    for clave, valor in (metadatos or {}).items():
        escritor.writerow(["metadatos", clave, valor])
    for fila in indicadores_a_filas(indicadores):
        escritor.writerow(fila)
    return salida.getvalue().encode("utf-8-sig")


def mis_datos_json(
    correo: str, perfil: dict, experiencias: list, generado_en: datetime = None
) -> bytes:
    """Todo lo que el sistema guarda sobre la persona, en un JSON legible."""
    contenido = {
        "generado_en": (generado_en or datetime.now()).isoformat(timespec="seconds"),
        "descripcion": "Copia de los datos que SIGMA guarda sobre ti, entregada en ejercicio de tu derecho de acceso.",
        "cuenta": {"correo": correo},
        "perfil": perfil or {},
        "experiencia_laboral": experiencias or [],
        "no_incluye": [
            "Tu contraseña: la gestiona el servicio de autenticación y no es visible para SIGMA.",
            "El PDF de tu CV: nunca se guarda; se lee en memoria y se descarta.",
        ],
    }
    return json.dumps(contenido, ensure_ascii=False, indent=2, default=str).encode(
        "utf-8"
    )
