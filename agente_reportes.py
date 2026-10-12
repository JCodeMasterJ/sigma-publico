"""
Agente 2: genera un reporte narrativo para acreditación.

Reparto de responsabilidades (a propósito):
  1. Los NÚMEROS los calcula código (pandas). La IA no calcula nada.
  2. La IA solo redacta, y cada hallazgo debe citar qué indicador lo sustenta.
  3. Después el código VERIFICA el resultado: que las citas existan y que las
     cifras escritas en el texto aparezcan en los indicadores.
"""

import json
import re
from collections import Counter
from datetime import datetime
from typing import List

import pandas as pd
from pydantic import BaseModel, Field

from proveedor_ia import generar_estructurado

COLS_EGRESADOS = [
    "id",
    "cohorte",
    "situacion_laboral",
    "fuente",
    "ciudad_residencia",
    "especializacion_posterior",
    "maestria_posterior",
    "doctorado_posterior",
    "situacion_origen",
]
COLS_EXPERIENCIA = [
    "egresado_id",
    "sector",
    "tecnologias",
    "tipo_empresa",
    "area_funcional",
    "clasificacion_origen",
    "fecha_fin",
]

UMBRAL_MUESTRA_PEQUENA = 10  # egresados de situación conocida
UMBRAL_DESCONOCIDOS_ALTO = 30  # porcentaje
VALIDACION_MUESTRA = (
    "de 30 pares empresa/cargo revisados a mano, el sector fue correcto en 26 de 28 clasificados (93 %) y el área en "
    "23 de 26 (88 %); la IA no clasificó el resto. Muestra pequeña: el margen de error es amplio"
)


class SinDatosError(Exception):
    """El filtro pedido no devuelve ningún egresado."""


# ---------------------------------------------------------------------------
# Lo que la IA debe devolver
# ---------------------------------------------------------------------------
class Hallazgo(BaseModel):
    afirmacion: str = Field(
        description="Afirmación redactada para un informe de acreditación. Usa únicamente cifras que estén en los indicadores."
    )
    indicadores_citados: List[str] = Field(
        description="Claves exactas de primer nivel del JSON de indicadores que sustentan esta afirmación."
    )


class ReporteAcreditacion(BaseModel):
    resumen_ejecutivo: str = Field(
        description="Párrafo breve (3 a 5 frases) con lo esencial."
    )
    hallazgos: List[Hallazgo] = Field(
        description="Entre 4 y 7 hallazgos, cada uno con sus citas."
    )
    limitaciones_de_los_datos: List[str] = Field(
        description="Limitaciones que el lector debe conocer: datos desconocidos, muestras pequeñas, campos vacíos."
    )
    recomendaciones: List[str] = Field(
        description="Máximo 3 sugerencias prácticas para revisión institucional (por ejemplo, mejorar la cobertura o actualización de los datos). No incluyas hipótesis sobre causas."
    )


# ---------------------------------------------------------------------------
# 1) Cálculo de indicadores (código, no IA)
# ---------------------------------------------------------------------------
def _fetch_all(supabase, tabla, columnas, page=1000):
    """Trae todas las filas (PostgREST limita a 1000 por petición)."""
    filas, inicio = [], 0
    while True:
        r = (
            supabase.table(tabla)
            .select(columnas)
            .range(inicio, inicio + page - 1)
            .execute()
        )
        filas.extend(r.data)
        if len(r.data) < page:
            break
        inicio += page
    return filas


def _pct(parte, total):
    return round(parte / total * 100, 1) if total else None


def _asegurar_columnas(df, columnas):
    for c in columnas:
        if c not in df.columns:
            df[c] = None
    return df


def calcular_indicadores(
    egresados, experiencia, fuente="real", ventana="5_anios", anio_actual=None
):
    anio_actual = anio_actual or datetime.now().year
    egr = _asegurar_columnas(egresados.copy(), COLS_EGRESADOS)
    exp = _asegurar_columnas(experiencia.copy(), COLS_EXPERIENCIA)

    df = egr
    if fuente != "todos":
        df = df[df["fuente"] == fuente]
    if ventana == "5_anios":
        valida = df["cohorte"].notna() & df["cohorte"].astype(str).str.isdigit()
        df = df[valida]
        df = df[df["cohorte"].astype(int) >= anio_actual - 5]

    # solo la experiencia vigente: la que un egresado cerró al cambiar de situación no cuenta como actual
    exp_f = exp[exp["egresado_id"].isin(df["id"]) & exp["fecha_fin"].isna()]
    total = len(df)

    sit = df["situacion_laboral"].value_counts()
    n_emp = int(sit.get("empleado", 0))
    n_des = int(sit.get("desempleado", 0))
    n_desc = int(sit.get("desconocido", 0))
    n_est = int(sit.get("estudios_posteriores", 0))

    descripciones_fuente = {
        "real": "Datos reales provenientes de registros institucionales de la facultad.",
        "sintetico": "Datos SINTÉTICOS generados para demostración; no representan egresados reales.",
        "todos": "Mezcla de datos reales y datos SINTÉTICOS de demostración.",
    }
    ventana_txt = (
        f"Últimos 5 años (cohortes desde {anio_actual - 5})"
        if ventana == "5_anios"
        else "Histórico completo"
    )

    por_cohorte = {}
    for cohorte in sorted(df["cohorte"].dropna().astype(str).unique()):
        g = df[df["cohorte"].astype(str) == cohorte]
        t = len(g)
        e = int((g["situacion_laboral"] == "empleado").sum())
        d = int((g["situacion_laboral"] == "desempleado").sum())
        u = int((g["situacion_laboral"] == "desconocido").sum())
        # A propósito NO se incluye la tasa sobre el total por cohorte: una cohorte con muchos
        # desconocidos parecería tener baja empleabilidad solo por falta de datos.
        por_cohorte[cohorte] = {
            "total": t,
            "empleados": e,
            "desempleados": d,
            "desconocidos": u,
            "estudios_posteriores": int(
                (g["situacion_laboral"] == "estudios_posteriores").sum()
            ),
            "conocidos": e + d,
            "tasa_sobre_conocidos": _pct(e, e + d),
            "porcentaje_desconocido": _pct(u, t),
        }

    ciudades = df["ciudad_residencia"].dropna().value_counts()

    def _clasificacion(campo, no_determinado):
        valores = exp_f[campo].dropna()
        sin_clasificar = int((valores == no_determinado).sum())
        con_valor = valores[valores != no_determinado]
        inferidas = int(
            (
                (exp_f["clasificacion_origen"] == "inferido_ia")
                & exp_f[campo].notna()
                & (exp_f[campo] != no_determinado)
            ).sum()
        )
        declaradas = int(
            (
                (exp_f["clasificacion_origen"] == "declarado")
                & exp_f[campo].notna()
                & (exp_f[campo] != no_determinado)
            ).sum()
        )
        return (
            con_valor.value_counts(),
            int(len(con_valor)),
            sin_clasificar,
            inferidas,
            declaradas,
        )

    sectores, n_sector, sector_sin_clasificar, sector_inferido, sector_declarado = (
        _clasificacion("sector", "No determinado")
    )
    areas, n_area, area_sin_clasificar, area_inferida, area_declarada = _clasificacion(
        "area_funcional", "No determinada"
    )
    n_declaradas = int((df["situacion_origen"] == "declarada_por_egresado").sum())
    tipo_emp = exp_f["tipo_empresa"].dropna().value_counts()

    contador_tech = Counter()
    con_tech = 0
    for lista in exp_f["tecnologias"]:
        if isinstance(lista, list) and lista:
            con_tech += 1
            contador_tech.update(lista)

    continuidad = {}
    for etiqueta, col in [
        ("especializacion", "especializacion_posterior"),
        ("maestria", "maestria_posterior"),
        ("doctorado", "doctorado_posterior"),
    ]:
        s = df[col].dropna()
        continuidad[etiqueta] = {
            "con_dato": int(len(s)),
            "si": int(s.astype(bool).sum()),
        }

    indicadores = {
        "alcance": {
            "fuente": fuente,
            "descripcion_fuente": descripciones_fuente[fuente],
            "incluye_datos_sinteticos": fuente != "real",
            "ventana": ventana_txt,
            "fecha_generacion": datetime.now().strftime("%Y-%m-%d"),
        },
        "totales": {
            "egresados": total,
            "cohortes_representadas": len(por_cohorte),
            **(
                {"egresados_sin_cohorte": int(df["cohorte"].isna().sum())}
                if df["cohorte"].isna().any()
                else {}
            ),
        },
        "empleabilidad_general": {
            "empleados": n_emp,
            "desempleados": n_des,
            "desconocidos": n_desc,
            "estudios_posteriores": n_est,
            "tasa_sobre_total": _pct(n_emp, total),
            "tasa_sobre_conocidos": _pct(n_emp, n_emp + n_des),
            "porcentaje_situacion_desconocida": _pct(n_desc, total),
            "definicion": (
                "tasa_sobre_total = empleados / total de egresados. "
                "tasa_sobre_conocidos = empleados / (empleados + desempleados), "
                "excluye a quienes no tienen situación laboral conocida. "
                "estudios_posteriores = egresados que declaran estar estudiando (posgrado, idiomas u otros): "
                "no cuentan como empleados ni como desempleados."
            ),
        },
        "empleabilidad_por_cohorte": por_cohorte,
        "ubicacion_top": {
            "egresados_con_ciudad": int(len(df["ciudad_residencia"].dropna())),
            "ciudades": {str(k): int(v) for k, v in ciudades.head(5).items()},
        },
        "tipo_empresa": {
            "experiencias_con_dato": int(len(exp_f["tipo_empresa"].dropna())),
            "conteo": {str(k): int(v) for k, v in tipo_emp.items()},
        },
        "sectores_top": {
            "experiencias_totales": int(len(exp_f)),
            "experiencias_con_sector": n_sector,
            "experiencias_sin_clasificar": sector_sin_clasificar,
            "experiencias_con_sector_inferido_ia": sector_inferido,
            "experiencias_con_sector_declarado": sector_declarado,
            "sectores": {str(k): int(v) for k, v in sectores.head(5).items()},
        },
        "areas_top": {
            "experiencias_con_area": n_area,
            "experiencias_sin_clasificar": area_sin_clasificar,
            "experiencias_con_area_inferida_ia": area_inferida,
            "experiencias_con_area_declarada": area_declarada,
            "areas": {str(k): int(v) for k, v in areas.head(5).items()},
        },
        "situacion_declarada_por_egresados": {
            "egresados": n_declaradas,
            "porcentaje_del_total": _pct(n_declaradas, total),
            "descripcion": "Egresados que declararon su situación laboral desde el portal, con fecha de actualización.",
        },
        "tecnologias_top": {
            "experiencias_con_tecnologias": int(con_tech),
            "tecnologias": {str(k): int(v) for k, v in contador_tech.most_common(10)},
        },
        "continuidad_academica": continuidad,
        "criterios_de_analisis": {
            "umbral_muestra_pequena_conocidos": UMBRAL_MUESTRA_PEQUENA,
            "umbral_desconocidos_alto_porcentaje": UMBRAL_DESCONOCIDOS_ALTO,
            "descripcion": (
                "Criterios fijados por el sistema: una cohorte con menos egresados de situación conocida "
                "que el primer umbral es una muestra pequeña; una cohorte con más porcentaje de desconocidos "
                "que el segundo umbral tiene poca información."
            ),
        },
    }
    return indicadores


# ---------------------------------------------------------------------------
# 2) Prompt
# ---------------------------------------------------------------------------
REGLAS = """Eres un analista institucional que redacta informes de seguimiento a egresados \
para procesos de acreditación de la Facultad de Ingeniería de Telecomunicaciones.

Recibirás un JSON con indicadores YA CALCULADOS. Tu trabajo es explicarlos, no recalcularlos.

REGLAS OBLIGATORIAS:
1. Usa únicamente cifras que aparezcan en el JSON. No calcules cifras nuevas, no promedies, no inventes datos.
2. No atribuyas causas ni ofrezcas hipótesis sobre por qué los datos son como son (admisiones, currículo, mercado laboral, etc.): no tienes información para ello. Describe qué muestran los datos y qué información falta.
3. Declara siempre la fuente de los datos (alcance.descripcion_fuente). Si incluye datos sintéticos, aclara que son de demostración y no constituyen evidencia real.
4. Menciona como limitación el porcentaje de situación laboral desconocida, las cohortes cuyo campo "conocidos" sea menor que criterios_de_analisis.umbral_muestra_pequena_conocidos (muestra pequeña) y los campos con poca cobertura (sector, tecnologías, continuidad académica).
5. Cada hallazgo debe citar en "indicadores_citados" las claves de primer nivel del JSON que lo sustentan, escritas exactamente igual.
6. Si un indicador no tiene datos suficientes, dilo; no lo rellenes.
7. Al comparar cohortes, usa "tasa_sobre_conocidos" y menciona el "porcentaje_desconocido" de cada cohorte que cites. Una cohorte cuyo porcentaje_desconocido supere criterios_de_analisis.umbral_desconocidos_alto_porcentaje tiene poca información: no la presentes como evidencia de baja empleabilidad. No presentes como máximo, mínimo ni tendencia a cohortes con muestra pequeña.
8. Siempre que cites una tasa sobre conocidos, aclara que no incluye a los egresados de situación desconocida y que puede no representar a toda la cohorte.
9. Redacta para un lector externo, con tus propias palabras: no copies ni menciones estas reglas ni uses expresiones como "no deben presentarse". Cada hallazgo debe tener máximo dos frases; no enumeres todas las cifras de una tabla, destaca lo relevante y remite al indicador citado. No uses nombres técnicos de campos (como "campo de conocidos"): escribe "egresados de situación conocida".
10. El sector y el área de desempeño de egresados reales provienen de dos orígenes distintos: INFERIDOS POR IA a partir de la empresa y el cargo (sectores_top.experiencias_con_sector_inferido_ia y areas_top.experiencias_con_area_inferida_ia) y DECLARADOS por las propias personas (experiencias_con_sector_declarado y experiencias_con_area_declarada). Si los citas, distingue ambos orígenes, y menciona cuántas experiencias quedaron sin clasificar.
11. Español formal, claro y sin exageraciones. Sin adjetivos triunfalistas."""


def construir_prompt(indicadores: dict) -> str:
    claves = ", ".join(indicadores.keys())
    return (
        f"{REGLAS}\n\n"
        f"CLAVES DE PRIMER NIVEL DISPONIBLES PARA CITAR: {claves}\n\n"
        f"INDICADORES (JSON):\n{json.dumps(indicadores, ensure_ascii=False, indent=2)}"
    )


# ---------------------------------------------------------------------------
# 3) Verificación del resultado (código, no IA)
# ---------------------------------------------------------------------------
def _numeros_en(obj, acumulado):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acumulado.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numeros_en(v, acumulado)
    elif isinstance(obj, list):
        for v in obj:
            _numeros_en(v, acumulado)


def _cifras_sin_respaldo(texto: str, indicadores: dict) -> List[str]:
    """Cifras escritas en el texto que no aparecen (con tolerancia de redondeo) en los indicadores."""
    respaldo: List[float] = []
    _numeros_en(indicadores, respaldo)
    sin_respaldo = set()
    for token in re.findall(r"\d+(?:[.,]\d+)?", texto):
        n = float(token.replace(",", "."))
        if 1990 <= n <= 2100:  # años
            continue
        if n <= 10 and n == int(
            n
        ):  # enteros pequeños ("cinco cohortes", "tres categorías")
            continue
        if not any(abs(n - m) <= 0.51 for m in respaldo):
            sin_respaldo.add(token)
    return sorted(sin_respaldo)


def verificar_reporte(reporte: ReporteAcreditacion, indicadores: dict) -> dict:
    claves_validas = set(indicadores.keys())
    citas_invalidas, hallazgos_sin_cita = [], []
    for h in reporte.hallazgos:
        if not h.indicadores_citados:
            hallazgos_sin_cita.append(h.afirmacion)
        for c in h.indicadores_citados:
            if c not in claves_validas:
                citas_invalidas.append(c)
    texto = " ".join(
        [reporte.resumen_ejecutivo]
        + [h.afirmacion for h in reporte.hallazgos]
        + reporte.limitaciones_de_los_datos
        + reporte.recomendaciones
    )
    return {
        "citas_invalidas": sorted(set(citas_invalidas)),
        "hallazgos_sin_cita": hallazgos_sin_cita,
        "cifras_sin_respaldo": _cifras_sin_respaldo(texto, indicadores),
    }


# ---------------------------------------------------------------------------
# Notas metodológicas: texto FIJO generado por código, no por la IA.
# Son avisos que no pueden depender de que el modelo "se acuerde" de escribirlos.
# ---------------------------------------------------------------------------
def _f(v):
    return "n/d" if v is None else f"{v}"


def _a_los(n: int) -> str:
    return "al único egresado" if n == 1 else f"a los {n} egresados"


def _nota_fecha(ind: dict) -> str:
    base = (
        "Los registros históricos de origen no tienen fecha de actualización: su situación laboral corresponde al "
        "momento, no registrado, en que se recolectó cada dato."
    )
    d = ind.get("situacion_declarada_por_egresados", {})
    if d.get("egresados"):
        base += (
            f" En cambio, {d['egresados']} egresados ({_f(d['porcentaje_del_total'])} %) declararon su situación desde el "
            "portal, con fecha de actualización."
        )
    return base


def notas_metodologicas(ind: dict) -> List[str]:
    eg = ind["empleabilidad_general"]
    total = ind["totales"]["egresados"]
    inferior = eg["tasa_sobre_total"]
    superior = _pct(eg["empleados"] + eg["desconocidos"], total)
    notas = [
        (
            f"Con la información disponible, la empleabilidad de los egresados registrados se ubica entre "
            f"{_f(inferior)} % (si todos los de situación desconocida estuvieran sin empleo) y {_f(superior)} % "
            f"(si todos estuvieran empleados). La tasa sobre conocidos ({_f(eg['tasa_sobre_conocidos'])} %) excluye "
            f"{_a_los(eg['desconocidos'])} de situación desconocida ({_f(eg['porcentaje_situacion_desconocida'])} %) "
            f"y puede no representar a toda la población."
        ),
        _nota_fecha(ind),
        "No se puede confirmar que el registro incluya a todos los graduados de cada cohorte: las cifras describen "
        "a los egresados registrados, no a la población total.",
    ]
    n_s = ind["sectores_top"].get("experiencias_con_sector_inferido_ia", 0)
    n_a = ind.get("areas_top", {}).get("experiencias_con_area_inferida_ia", 0)
    if n_s or n_a:
        nota = (
            f"El sector ({n_s} experiencias) y el área de desempeño ({n_a}) de egresados reales fueron inferidos por IA a partir "
            "del nombre de la empresa y el cargo; no son datos declarados por las personas y pueden contener errores."
        )
        if VALIDACION_MUESTRA:
            nota += f" Validación manual de una muestra: {VALIDACION_MUESTRA}."
        notas.append(nota)
    d_s = ind["sectores_top"].get("experiencias_con_sector_declarado", 0)
    d_a = ind.get("areas_top", {}).get("experiencias_con_area_declarada", 0)
    if d_s or d_a:
        notas.append(
            f"El sector ({d_s} experiencias) y el área de desempeño ({d_a}) restantes fueron declarados por los propios "
            "egresados desde el portal."
        )
    if ind["alcance"].get("incluye_datos_sinteticos"):
        notas.append(
            "Este reporte incluye datos sintéticos de demostración: esas cifras no describen egresados reales."
        )
    return notas


def a_markdown(
    reporte: ReporteAcreditacion, indicadores: dict, notas: List[str] = None
) -> str:
    alcance = indicadores["alcance"]
    lineas = [
        f"**Fuente de datos:** {alcance['descripcion_fuente']}",
        f"**Periodo:** {alcance['ventana']}",
        "",
        "### Resumen ejecutivo",
        reporte.resumen_ejecutivo,
        "",
        "### Hallazgos",
    ]
    for h in reporte.hallazgos:
        citas = ", ".join(f"`{c}`" for c in h.indicadores_citados) or "_sin cita_"
        lineas.append(f"- {h.afirmacion} _(indicadores: {citas})_")
    lineas += ["", "### Limitaciones de los datos"]
    lineas += [f"- {x}" for x in reporte.limitaciones_de_los_datos]
    if notas:
        lineas += [
            "",
            "### Notas metodológicas (generadas por el sistema, no por la IA)",
        ]
        lineas += [f"- {x}" for x in notas]
    lineas += ["", "### Recomendaciones para revisión institucional"]
    lineas += [f"- {x}" for x in reporte.recomendaciones]
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------
def generar_reporte(supabase, fuente="real", ventana="5_anios") -> dict:
    egr = pd.DataFrame(
        _fetch_all(supabase, "egresados", ",".join(COLS_EGRESADOS)),
        columns=COLS_EGRESADOS,
    )
    exp = pd.DataFrame(
        _fetch_all(supabase, "experiencia_laboral", ",".join(COLS_EXPERIENCIA)),
        columns=COLS_EXPERIENCIA,
    )

    indicadores = calcular_indicadores(egr, exp, fuente, ventana)
    # normalizar tipos numpy a tipos nativos de Python (para guardar como JSON)
    indicadores = json.loads(
        json.dumps(
            indicadores, default=lambda o: o.item() if hasattr(o, "item") else str(o)
        )
    )

    if indicadores["totales"]["egresados"] == 0:
        raise SinDatosError(
            "No hay egresados que cumplan ese filtro; no se puede generar un reporte."
        )

    reporte = generar_estructurado(
        construir_prompt(indicadores), ReporteAcreditacion, timeout=90
    )  # sin tiempo límite una petición colgada espera para siempre
    notas = notas_metodologicas(indicadores)
    return {
        "indicadores": indicadores,
        "reporte": reporte.model_dump(),
        "verificacion": verificar_reporte(reporte, indicadores),
        "notas_metodologicas": notas,
        "narrativa_markdown": a_markdown(reporte, indicadores, notas),
    }
