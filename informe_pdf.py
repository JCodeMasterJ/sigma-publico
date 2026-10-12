"""
Genera el informe de acreditación en PDF a partir de la respuesta del agente de reportes.

Usa fpdf2 (Python puro, sin dependencias del sistema). Las fuentes estándar de PDF solo
cubren Latin-1 (suficiente para español), por eso se normalizan unos pocos signos
tipográficos que a veces escribe el modelo (comillas curvas, guiones largos, puntos suspensivos).
"""

from datetime import datetime

from fpdf import FPDF
from fpdf.fonts import FontFace

NAVY = (11, 42, 94)
GOLD = (201, 162, 39)
GRIS = (90, 90, 90)
ROJO_FONDO = (253, 236, 234)
ROJO_TEXTO = (150, 30, 20)
VERDE_FONDO = (232, 244, 234)
VERDE_TEXTO = (30, 100, 50)

_REEMPLAZOS = {
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2026": "...",
    "\u2022": "-",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u2192": "->",
    "\u00a0": " ",
    "\u00d7": "x",
}


def _t(texto) -> str:
    """Texto seguro para fuentes Latin-1."""
    s = "" if texto is None else str(texto)
    for k, v in _REEMPLAZOS.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _num(valor, decimales=1) -> str:
    if valor is None:
        return "-"
    if isinstance(valor, float):
        return f"{valor:.{decimales}f}"
    return str(valor)


class _Informe(FPDF):
    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(*GRIS)
        self.cell(
            140,
            8,
            _t(
                "SIGMA · Redactado con apoyo de IA a partir de indicadores calculados por el sistema (ver anexo)."
            ),
        )
        self.cell(0, 8, _t(f"Página {self.page_no()}/{{nb}}"), align="R")


def _asegurar_espacio(pdf, mm):
    """Si no caben `mm` milímetros en la página actual, salta a una nueva (evita títulos huérfanos)."""
    if pdf.get_y() + mm > pdf.page_break_trigger:
        pdf.add_page()


def _titulo(pdf, texto, espacio=32):
    _asegurar_espacio(pdf, espacio)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 7, _t(texto), new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, y, pdf.l_margin + 25, y)
    pdf.ln(2.5)
    pdf.set_text_color(30, 30, 30)


def _parrafo(pdf, texto, tam=10):
    _asegurar_espacio(
        pdf, 5.2 * (1 + len(str(texto)) // 95) + 2
    )  # estimación de líneas: no partir el párrafo
    pdf.set_font("Helvetica", "", tam)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 5.2, _t(texto), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _vineta(pdf, texto, fuente=None):
    x0 = pdf.l_margin
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.set_x(x0)
    pdf.cell(5, 5.2, "-")
    pdf.multi_cell(0, 5.2, _t(texto), new_x="LMARGIN", new_y="NEXT")
    if fuente:
        pdf.set_x(x0 + 5)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*GRIS)
        pdf.multi_cell(0, 4.2, _t(f"Fuente: {fuente}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.2)


def _tabla(pdf, cabecera, filas, anchos, alineacion):
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(30, 30, 30)
    pdf.set_fill_color(
        255, 255, 255
    )  # evita arrastrar el color del recuadro de verificación
    pdf.set_draw_color(
        210, 214, 222
    )  # líneas grises suaves, no el dorado de los títulos
    pdf.set_line_width(0.2)
    with pdf.table(
        col_widths=anchos,
        text_align=alineacion,
        headings_style=FontFace(
            emphasis="BOLD", color=(255, 255, 255), fill_color=NAVY
        ),
        line_height=4.3,
        padding=0.7,
        borders_layout="HORIZONTAL_LINES",
    ) as tabla:
        fila = tabla.row()
        for c in cabecera:
            fila.cell(_t(c))
        for datos in filas:
            fila = tabla.row()
            for d in datos:
                fila.cell(_t(d))
    pdf.ln(2)


AZUL_DESEMPLEADO = (91, 127, 185)
GRIS_DESCONOCIDO = (190, 194, 202)
VERDE_ESTUDIOS = (127, 183, 164)


def _grafico_cohortes(pdf, cohortes):
    """Barras apiladas (empleado / desempleado / desconocido) por cohorte, dibujadas con rectángulos."""
    n = len(cohortes)
    paso, alto_barra = 6.6, 4.6
    _asegurar_espacio(pdf, 22 + n * paso + 8)

    x0 = pdf.l_margin
    ancho_util = pdf.w - pdf.l_margin - pdf.r_margin
    ancho_etiqueta, ancho_n = 16, 22
    ancho_barra = ancho_util - ancho_etiqueta - ancho_n

    pdf.ln(3)
    pdf.set_x(x0)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*NAVY)
    pdf.cell(
        0,
        6,
        _t("Figura 1. Situación laboral por cohorte (número de egresados)"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    y = pdf.get_y() + 1
    x = x0 + ancho_etiqueta
    pdf.set_font("Helvetica", "", 8)
    hay_estudiando = any(v.get("estudios_posteriores", 0) for v in cohortes.values())
    leyenda = [(GOLD, "Empleado"), (AZUL_DESEMPLEADO, "Desempleado")]
    if hay_estudiando:
        leyenda.append((VERDE_ESTUDIOS, "Estudiando"))
    leyenda.append((GRIS_DESCONOCIDO, "Situación desconocida"))
    for color, texto in leyenda:
        pdf.set_fill_color(*color)
        pdf.rect(x, y + 0.9, 3, 3, "F")
        pdf.set_xy(x + 4, y)
        pdf.set_text_color(30, 30, 30)
        ancho_texto = pdf.get_string_width(_t(texto)) + 1
        pdf.cell(ancho_texto, 4.8, _t(texto))
        x += ancho_texto + 9
    y += 8

    for cohorte, v in cohortes.items():
        total = v["total"]
        pdf.set_xy(x0, y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(ancho_etiqueta, alto_barra, _t(cohorte))
        xb = x0 + ancho_etiqueta
        for clave, color, color_texto in [
            ("empleados", GOLD, (30, 30, 30)),
            ("desempleados", AZUL_DESEMPLEADO, (255, 255, 255)),
            ("estudios_posteriores", VERDE_ESTUDIOS, (30, 30, 30)),
            ("desconocidos", GRIS_DESCONOCIDO, (60, 60, 60)),
        ]:
            cantidad = v.get(clave, 0)
            if total and cantidad:
                w = ancho_barra * cantidad / total
                pdf.set_fill_color(*color)
                pdf.rect(xb, y, w, alto_barra, "F")
                if w >= 6:
                    pdf.set_xy(xb, y)
                    pdf.set_font("Helvetica", "B", 7)
                    pdf.set_text_color(*color_texto)
                    pdf.cell(w, alto_barra, str(cantidad), align="C")
                xb += w
        pdf.set_xy(x0 + ancho_etiqueta + ancho_barra + 2, y)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*GRIS)
        pdf.cell(ancho_n - 2, alto_barra, _t(f"n = {total}"))
        y += paso

    pdf.set_y(y + 1)
    pdf.set_x(x0)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*GRIS)
    pdf.multi_cell(
        0,
        4.2,
        _t(
            "El gris indica situación laboral desconocida: no equivale a desempleo. Una cohorte con mucho gris "
            "tiene poca información, no necesariamente baja empleabilidad."
            + (
                " «Estudiando» agrupa a quienes declaran estar estudiando (posgrado, idiomas u otros): "
                "no cuentan como empleo ni como desempleo."
                if hay_estudiando
                else ""
            )
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(1)


def generar_pdf(reporte: dict) -> bytes:
    """`reporte` es la respuesta JSON de POST /agentes/generar-reporte."""
    ind = reporte["indicadores"]
    rep = reporte["reporte"]
    ver = reporte["verificacion"]
    alc = ind["alcance"]

    pdf = _Informe(format="A4")
    pdf.set_margins(20, 18, 20)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.alias_nb_pages()
    pdf.set_title("Informe de seguimiento a egresados - SIGMA")
    pdf.set_author("SIGMA")
    pdf.add_page()

    # Encabezado
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 30, "F")
    pdf.set_xy(20, 9)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(
        0,
        8,
        _t("SIGMA - Informe de seguimiento a egresados"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GOLD)
    pdf.cell(
        0,
        6,
        _t("Facultad de Ingeniería de Telecomunicaciones · Universidad Santo Tomás"),
    )
    pdf.set_y(36)

    # Datos del reporte
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRIS)
    for etiqueta, valor in [
        ("Fuente de datos", alc.get("descripcion_fuente", "")),
        ("Periodo", alc.get("ventana", "")),
        (
            "Fecha de generación",
            alc.get("fecha_generacion", datetime.now().strftime("%Y-%m-%d")),
        ),
        ("Identificador del reporte", reporte.get("reporte_id") or "no guardado"),
    ]:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(42, 5, _t(etiqueta + ":"))
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, _t(valor), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Estado de la verificación automática
    problemas = []
    if ver.get("cifras_sin_respaldo"):
        problemas.append(
            "cifras que no aparecen en los indicadores: "
            + ", ".join(ver["cifras_sin_respaldo"])
        )
    if ver.get("citas_invalidas"):
        problemas.append(
            "citas a indicadores inexistentes: " + ", ".join(ver["citas_invalidas"])
        )
    if ver.get("hallazgos_sin_cita"):
        problemas.append(f"{len(ver['hallazgos_sin_cita'])} hallazgo(s) sin cita")
    if alc.get("incluye_datos_sinteticos"):
        problemas.append(
            "incluye datos SINTÉTICOS de demostración: no constituye evidencia real"
        )

    if problemas:
        pdf.set_fill_color(*ROJO_FONDO)
        pdf.set_text_color(*ROJO_TEXTO)
        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(
            0,
            5,
            _t("REQUIERE REVISIÓN ANTES DE USARSE: " + "; ".join(problemas) + "."),
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
            padding=2,
        )
    else:
        pdf.set_fill_color(*VERDE_FONDO)
        pdf.set_text_color(*VERDE_TEXTO)
        pdf.set_font("Helvetica", "B", 9)
        pdf.multi_cell(
            0,
            5,
            _t(
                "Verificación automática superada: las cifras del texto coinciden con los indicadores y cada hallazgo cita su fuente."
            ),
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
            padding=2,
        )

    _titulo(pdf, "Resumen ejecutivo")
    _parrafo(pdf, rep["resumen_ejecutivo"])

    _titulo(pdf, "Hallazgos")
    for h in rep["hallazgos"]:
        _vineta(
            pdf,
            h["afirmacion"],
            ", ".join(h.get("indicadores_citados", [])) or "sin cita",
        )

    cohortes_fig = ind.get("empleabilidad_por_cohorte", {})
    if cohortes_fig:
        _grafico_cohortes(pdf, cohortes_fig)

    _titulo(pdf, "Limitaciones de los datos")
    for x in rep["limitaciones_de_los_datos"]:
        _vineta(pdf, x)

    notas = reporte.get("notas_metodologicas") or []
    if notas:
        _titulo(pdf, "Notas metodológicas (generadas por el sistema, no por la IA)")
        for x in notas:
            _vineta(pdf, x)

    _titulo(pdf, "Recomendaciones para revisión institucional")
    for x in rep["recomendaciones"]:
        _vineta(pdf, x)

    # Anexo: los indicadores exactos que recibió la IA
    _asegurar_espacio(pdf, 90)
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, _t("Anexo - Indicadores utilizados"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(*GRIS)
    pdf.multi_cell(
        0,
        4.5,
        _t(
            "Estas cifras fueron calculadas por el sistema, no por la IA. La IA solo redactó el texto anterior a partir de ellas."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    eg = ind["empleabilidad_general"]
    _titulo(pdf, "Empleabilidad general")
    _tabla(
        pdf,
        ["Indicador", "Valor"],
        [
            ["Egresados analizados", _num(ind["totales"]["egresados"])],
            ["Empleados", _num(eg["empleados"])],
            ["Desempleados", _num(eg["desempleados"])],
            *(
                [
                    [
                        "Estudiando (posgrado, idiomas u otros)",
                        _num(eg["estudios_posteriores"]),
                    ]
                ]
                if eg.get("estudios_posteriores")
                else []
            ),
            ["Situación desconocida", _num(eg["desconocidos"])],
            *(
                [
                    [
                        "Situación declarada por el egresado, con fecha",
                        _num(ind["situacion_declarada_por_egresados"]["egresados"]),
                    ]
                ]
                if (ind.get("situacion_declarada_por_egresados") or {}).get("egresados")
                else []
            ),
            ["Tasa sobre el total (%)", _num(eg["tasa_sobre_total"])],
            ["Tasa sobre conocidos (%)", _num(eg["tasa_sobre_conocidos"])],
            ["Situación desconocida (%)", _num(eg["porcentaje_situacion_desconocida"])],
        ],
        (110, 60),
        ("LEFT", "RIGHT"),
    )

    cohortes = ind.get("empleabilidad_por_cohorte", {})
    if cohortes:
        _titulo(pdf, "Empleabilidad por cohorte (año de grado)")
        _tabla(
            pdf,
            [
                "Cohorte",
                "Total",
                "Empl.",
                "Desempl.",
                "Desconoc.",
                "Tasa s/ conoc. (%)",
                "Desconoc. (%)",
            ],
            [
                [
                    c,
                    _num(v["total"]),
                    _num(v["empleados"]),
                    _num(v["desempleados"]),
                    _num(v["desconocidos"]),
                    _num(v.get("tasa_sobre_conocidos")),
                    _num(v.get("porcentaje_desconocido")),
                ]
                for c, v in cohortes.items()
            ],
            (22, 18, 20, 22, 24, 38, 26),
            ("LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"),
        )

    sec, tec, cont, ubi = (
        ind["sectores_top"],
        ind["tecnologias_top"],
        ind["continuidad_academica"],
        ind["ubicacion_top"],
    )
    areas = ind.get("areas_top") or {}
    sec_inf = sec.get("experiencias_con_sector_inferido_ia", 0)
    area_inf = areas.get("experiencias_con_area_inferida_ia", 0)
    sec_decl = sec.get("experiencias_con_sector_declarado", 0)
    area_decl = areas.get("experiencias_con_area_declarada", 0)
    _titulo(pdf, "Cobertura de los datos")
    filas_cobertura = [
        ["Ciudad de residencia", _num(ubi["egresados_con_ciudad"])],
        ["Tipo de empresa", _num(ind["tipo_empresa"]["experiencias_con_dato"])],
        [
            "Sector clasificado (de "
            + _num(sec["experiencias_totales"])
            + " experiencias)",
            _num(sec["experiencias_con_sector"]),
        ],
    ]
    if sec_inf:
        filas_cobertura.append(
            ["    de las cuales, inferido por IA (no declarado)", _num(sec_inf)]
        )
    if sec_decl:
        filas_cobertura.append(
            ["    de las cuales, declarado por el egresado", _num(sec_decl)]
        )
    if areas:
        filas_cobertura.append(
            [
                "Área de desempeño clasificada",
                _num(areas.get("experiencias_con_area", 0)),
            ]
        )
        if area_inf:
            filas_cobertura.append(
                ["    de las cuales, inferida por IA (no declarada)", _num(area_inf)]
            )
        if area_decl:
            filas_cobertura.append(
                ["    de las cuales, declarada por el egresado", _num(area_decl)]
            )
    filas_cobertura += [
        [
            "Tecnologías (texto escrito por la persona)",
            _num(tec["experiencias_con_tecnologias"]),
        ],
        [
            "Continuidad académica (especialización)",
            _num(cont["especializacion"]["con_dato"]),
        ],
    ]
    _tabla(
        pdf,
        ["Campo", "Registros con dato"],
        filas_cobertura,
        (110, 60),
        ("LEFT", "RIGHT"),
    )
    if ubi["ciudades"]:
        _parrafo(
            pdf,
            "Ciudades principales: "
            + ", ".join(f"{c} ({n})" for c, n in ubi["ciudades"].items()),
            tam=9,
        )
    if sec.get("sectores"):
        etiqueta = " (inferidos por IA)" if sec_inf else ""
        _parrafo(
            pdf,
            f"Sectores principales{etiqueta}: "
            + ", ".join(f"{c} ({n})" for c, n in sec["sectores"].items()),
            tam=9,
        )
    if areas.get("areas"):
        etiqueta = " (inferidas por IA)" if area_inf else ""
        _parrafo(
            pdf,
            f"Áreas de desempeño principales{etiqueta}: "
            + ", ".join(f"{c} ({n})" for c, n in areas["areas"].items()),
            tam=9,
        )
    crit = ind.get("criterios_de_analisis")
    if crit:
        _parrafo(
            pdf,
            f"Criterios del sistema: muestra pequeña si hay menos de {crit['umbral_muestra_pequena_conocidos']} "
            f"egresados de situación conocida; poca información si más de {crit['umbral_desconocidos_alto_porcentaje']} % "
            "de la cohorte tiene situación desconocida.",
            tam=9,
        )

    return bytes(pdf.output())
