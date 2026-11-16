"""
«Tu cohorte en cifras»: cómo está la promoción de una persona, sin identificar a nadie.

Dos protecciones de privacidad, que también aplica la función SQL `mi_cohorte_en_cifras` del portal real (y una prueba comprueba que
las dos den lo mismo):
  * Grupo mínimo: si la promoción tiene menos de MINIMO_GRUPO egresados, no se muestra NINGUNA cifra.
  * Celdas pequeñas: una ciudad, sector o tecnología con menos de MINIMO_CELDA egresados no se muestra (con 1 o 2 se podría saber quién es).

La demo la usa con datos ficticios en memoria; el portal real obtiene las mismas cifras desde la base de datos, sin que el cliente vea
filas de otras personas.
"""

from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

MINIMO_GRUPO = 10
MINIMO_CELDA = 3


def _r1(valor):
    """Un decimal, redondeando .x5 hacia arriba (igual que Postgres; el round de Python redondea al par)."""
    return float(Decimal(str(valor)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _porcentaje(parte, total):
    return _r1(Decimal(100 * parte) / Decimal(total))


def _principales(contador: Counter, cuantos: int, celda_minima: int) -> dict:
    """Los `cuantos` más frecuentes entre las categorías con al menos `celda_minima`; empates por orden alfabético."""
    items = sorted(
        ((k, v) for k, v in contador.items() if v >= celda_minima),
        key=lambda kv: (-kv[1], kv[0]),
    )
    return {k: int(v) for k, v in items[:cuantos]}


def cifras_de_cohorte(
    egresados: pd.DataFrame,
    experiencia: pd.DataFrame,
    cohorte,
    fuente: str,
    minimo: int = MINIMO_GRUPO,
    celda_minima: int = MINIMO_CELDA,
) -> dict:
    cohorte = str(cohorte)
    pendiente = (
        egresados["por_revisar"].fillna(False).astype(bool)
        if "por_revisar" in egresados.columns
        else pd.Series(False, index=egresados.index)
    )
    grupo = egresados[
        (egresados["cohorte"].astype(str) == cohorte)
        & (egresados["fuente"] == fuente)
        & ~pendiente
    ]
    n = len(grupo)
    if n < minimo:
        return {"suficiente": False, "cohorte": cohorte, "n": int(n), "minimo": minimo}

    situacion = grupo["situacion_laboral"].value_counts()
    empleados, desempleados = (
        int(situacion.get("empleado", 0)),
        int(situacion.get("desempleado", 0)),
    )
    desconocidos, estudios = (
        int(situacion.get("desconocido", 0)),
        int(situacion.get("estudios_posteriores", 0)),
    )
    conocidos = empleados + desempleados

    vigentes = experiencia[
        experiencia["fecha_fin"].isna() & experiencia["egresado_id"].isin(grupo["id"])
    ]
    sectores = Counter(s for s in vigentes["sector"].dropna() if s != "No determinado")
    tecnologias = Counter(
        t
        for lista in vigentes["tecnologias"].dropna()
        if isinstance(lista, list)
        for t in lista
    )

    return {
        "suficiente": True,
        "cohorte": cohorte,
        "n": int(n),
        "minimo": minimo,
        "celda_minima": celda_minima,
        "empleados": empleados,
        "desempleados": desempleados,
        "desconocidos": desconocidos,
        "estudios_posteriores": estudios,
        "tasa_sobre_total": _porcentaje(empleados, n),
        "tasa_sobre_conocidos": _porcentaje(empleados, conocidos)
        if conocidos
        else None,
        "porcentaje_desconocido": _porcentaje(desconocidos, n),
        "con_ciudad": int(grupo["ciudad_residencia"].notna().sum()),
        "ciudades": _principales(
            Counter(grupo["ciudad_residencia"].dropna()), 5, celda_minima
        ),
        "sectores": _principales(sectores, 3, celda_minima),
        "tecnologias": _principales(tecnologias, 5, celda_minima),
    }
