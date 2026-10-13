"""Pruebas del informe: indicadores de ciudades, topes de texto, gráficos de la app y gráficos del PDF."""

import io, os, random, sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.update(
    SUPABASE_URL="https://x.supabase.co",
    SUPABASE_SERVICE_KEY="dummy",
    SUPABASE_ANON_KEY="dummy",
    GEMINI_API_KEY="dummy",
    AGENTES_URL="https://servicio.test",
    AGENTES_API_KEY="clave-de-prueba",
)

import agente_reportes as ar
import graficos_reporte as gr
from informe_pdf import generar_pdf
from pypdf import PdfReader

resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:120]) if d else "")


# ---------- datos de prueba (inventados): 12 ciudades, 296 egresados, 176 con ciudad ----------
random.seed(7)
CIUDADES = [
    ("Bucaramanga", 61),
    ("Bogotá", 38),
    ("Medellín", 21),
    ("Cali", 12),
    ("Barrancabermeja", 11),
    ("Cúcuta", 9),
    ("Floridablanca", 8),
    ("Barranquilla", 6),
    ("Pereira", 4),
    ("Madrid (España)", 3),
    ("Manizales", 2),
    ("Valledupar", 1),
]
SECT = [
    "Telecomunicaciones",
    "Tecnología / Software",
    "Energía y petróleo",
    "Educación",
    "Salud",
    "Banca y finanzas",
    "Consultoría",
]
AREAS = [
    "Redes y telecomunicaciones",
    "Desarrollo de software",
    "Gestión de proyectos",
    "Soporte técnico",
    "Docencia e investigación",
    "Ventas / comercial",
]
TEC = [
    "Python",
    "Cisco",
    "Linux",
    "AWS",
    "SQL",
    "Docker",
    "Huawei",
    "Fibra óptica",
    "5G",
    "Java",
    "Excel",
    "Zabbix",
]
egr, exp, i = [], [], 0
for ciudad, n in CIUDADES + [(None, 120)]:
    for _ in range(n):
        i += 1
        sit = (
            "desconocido"
            if ciudad is None
            else random.choices(
                ["empleado", "desempleado", "desconocido", "estudios_posteriores"],
                [50, 4, 42, 4],
            )[0]
        )
        egr.append(
            {
                "id": f"e{i}",
                "cohorte": str(random.choice([2021, 2022, 2023, 2024, 2025])),
                "situacion_laboral": sit,
                "fuente": "real",
                "ciudad_residencia": ciudad,
                "especializacion_posterior": None,
                "maestria_posterior": None,
                "doctorado_posterior": None,
                "situacion_origen": "institucional_historico",
            }
        )
        if sit == "empleado":
            exp.append(
                {
                    "egresado_id": f"e{i}",
                    "sector": random.choice(SECT),
                    "tecnologias": random.sample(TEC, random.randint(0, 3)) or None,
                    "tipo_empresa": None,
                    "area_funcional": random.choice(AREAS),
                    "clasificacion_origen": "inferido_ia",
                    "fecha_fin": None,
                }
            )


class Q:
    def __init__(s, t):
        s.t, s._r = t, (0, 10**9)

    def select(s, c):
        return s

    def range(s, a, b):
        s._r = (a, b)
        return s

    def limit(s, n):
        return s

    def execute(s):
        d = {"egresados": egr, "experiencia_laboral": exp, "programas": [{"id": "p1"}]}[
            s.t
        ]
        return SimpleNamespace(data=d[s._r[0] : s._r[1] + 1])


class SB:
    def table(s, t):
        return Q(t)


def ia_verbosa(
    prompt, modelo, nombre_modelo=None, timeout=None
):  # una IA que NO obedece los topes de longitud
    h = lambda t: ar.Hallazgo(afirmacion=t, indicadores_citados=["totales"])
    return ar.ReporteAcreditacion(
        resumen_ejecutivo="HALLAZGO-RESUMEN. El informe describe la situación de los egresados con los datos disponibles.",
        hallazgos=[
            h(f"HALLAZGO-{k} afirmación de ejemplo sobre los egresados.")
            for k in range(1, 10)
        ],
        limitaciones_de_los_datos=[
            f"LIMITACION-{k} limitación de ejemplo." for k in range(1, 8)
        ],
        recomendaciones=[
            f"RECOMENDACION-{k} sugerencia de ejemplo." for k in range(1, 7)
        ],
    )


ar.generar_estructurado = ia_verbosa
rep = ar.generar_reporte(SB(), "real", "historico")
ind, texto_rep = rep["indicadores"], rep["reporte"]

# ===== A. el agente: indicadores y topes de texto =====
ciu = ind["ubicacion_top"]["ciudades"]
chequear(
    "A1. el indicador de ciudades trae las 10 principales (antes 5)",
    len(ciu) == 10,
    len(ciu),
)
chequear(
    "A2. ordenadas de mayor a menor, y con la cobertura (176 de 296)",
    list(ciu.values()) == sorted(ciu.values(), reverse=True)
    and ind["ubicacion_top"]["egresados_con_ciudad"] == 176
    and ind["totales"]["egresados"] == 296,
)
chequear(
    "A3. aunque la IA devuelva 9 hallazgos, 7 limitaciones y 6 recomendaciones, el sistema deja 5, 4 y 3",
    (
        len(texto_rep["hallazgos"]),
        len(texto_rep["limitaciones_de_los_datos"]),
        len(texto_rep["recomendaciones"]),
    )
    == (5, 4, 3),
)
chequear(
    "A4. y la verificación automática sigue limpia",
    rep["verificacion"]
    == {"citas_invalidas": [], "hallazgos_sin_cita": [], "cifras_sin_respaldo": []},
    rep["verificacion"],
)
chequear(
    "A5. el prompt le pide ser breve y no enumerar lo que ya está en los gráficos",
    "NO las enumeres" in ar.construir_prompt(ind)
    and "máximo 4 limitaciones" in ar.construir_prompt(ind),
)

# ===== B. los gráficos de la app =====
figs = gr.figuras_del_reporte(ind)
claves = [f["clave"] for f in figs]
chequear(
    "B1. salen los 5 gráficos: cohortes, ciudades, sectores, áreas y tecnologías",
    claves == ["cohortes", "ciudades", "sectores", "areas", "tecnologias"],
    claves,
)
chequear(
    "B2. el de cohortes va a todo el ancho y los otros cuatro de a dos",
    [f["ancho"] for f in figs] == ["completo", "medio", "medio", "medio", "medio"],
)
barras = {
    f["clave"]: len(f["figura"].data[0].x) for f in figs if f["clave"] != "cohortes"
}
chequear(
    "B3. ciudades y tecnologías muestran hasta 10 barras; sectores y áreas, hasta 5",
    barras["ciudades"] == 10
    and barras["tecnologias"] <= 10
    and barras["sectores"] <= 5
    and barras["areas"] <= 5,
    barras,
)
chequear(
    "B4. el gráfico de ciudades pone primero la más grande (Bucaramanga, 61)",
    figs[1]["figura"].data[0].y[-1] == "Bucaramanga"
    and figs[1]["figura"].data[0].x[-1] == 61,
)
chequear(
    "B5. CADA gráfico dice cuántos datos hay detrás: 'Ciudad registrada en 176 de 296 egresados (59 %)'",
    "176 de 296 egresados (59 %)" in figs[1]["pie"],
    figs[1]["pie"],
)
chequear(
    "B6. y avisa lo inferido por IA en sector y área",
    all(
        "inferidas por IA" in f["pie"]
        for f in figs
        if f["clave"] in ("sectores", "areas")
    ),
)
chequear(
    "B7. con indicadores vacíos no revienta: devuelve una lista vacía",
    gr.figuras_del_reporte({}) == []
    and gr.figuras_del_reporte({"ubicacion_top": {"ciudades": {}}}) == [],
)

# ===== C. el PDF =====
pdf = generar_pdf(rep)
lector = PdfReader(io.BytesIO(pdf))
texto_pdf = "\n".join(p.extract_text() for p in lector.pages)
chequear(
    "C1. el PDF se genera y se puede leer",
    pdf[:4] == b"%PDF" and len(lector.pages) >= 2,
    len(lector.pages),
)
chequear(
    "C2. incluye las figuras 2 a 5 con sus títulos",
    all(
        t in texto_pdf
        for t in (
            "Figura 2. Ciudades de residencia",
            "Figura 3. Sector",
            "Figura 4. Áreas",
            "Figura 5. Tecnologías",
        )
    ),
)
chequear(
    "C3. las ciudades salen DIBUJADAS con su cifra (Bucaramanga 61), y la cobertura dice 176 de 296",
    "Bucaramanga" in texto_pdf
    and "Barrancabermeja" in texto_pdf
    and "Ciudad registrada en 176 de 296" in texto_pdf,
)
chequear(
    "C4. ya no existe la línea de texto 'Ciudades principales: …' (ahora es el gráfico)",
    "Ciudades principales:" not in texto_pdf
    and "Sectores principales" not in texto_pdf,
)
chequear(
    "C5. el PDF también respeta los topes: no aparece el hallazgo 6, ni la limitación 5, ni la recomendación 4",
    "HALLAZGO-5" in texto_pdf
    and "HALLAZGO-6" not in texto_pdf
    and "LIMITACION-4" in texto_pdf
    and "LIMITACION-5" not in texto_pdf
    and "RECOMENDACION-3" in texto_pdf
    and "RECOMENDACION-4" not in texto_pdf,
)
rep_viejo = {
    **rep,
    "reporte": {
        **rep["reporte"],
        "hallazgos": [
            {"afirmacion": f"HALLAZGO-{k} texto.", "indicadores_citados": ["totales"]}
            for k in range(1, 10)
        ],
    },
}  # un reporte guardado antes del tope
t_viejo = "\n".join(
    p.extract_text() for p in PdfReader(io.BytesIO(generar_pdf(rep_viejo))).pages
)
chequear(
    "C6. aunque el reporte guardado traiga 9 hallazgos, el PDF muestra solo 5",
    "HALLAZGO-5" in t_viejo and "HALLAZGO-6" not in t_viejo,
)
sin_ciudades = {
    **rep,
    "indicadores": {
        **ind,
        "ubicacion_top": {"egresados_con_ciudad": 0, "ciudades": {}},
    },
}
t_sin = "\n".join(
    p.extract_text() for p in PdfReader(io.BytesIO(generar_pdf(sin_ciudades))).pages
)
chequear(
    "C7. sin datos de ciudad no se dibuja un gráfico vacío y el resto se numera bien (Figura 2 = sectores)",
    "Ciudades de residencia" not in t_sin and "Figura 2. Sector" in t_sin,
    [l for l in t_sin.split("\n") if "Figura" in l],
)
chequear(
    "C8. el informe es breve: máximo 5 páginas con 12 ciudades y todos los gráficos",
    len(lector.pages) <= 5,
    len(lector.pages),
)

# ===== D. la pestaña de reportes en la app =====
import requests as _requests
import streamlit as _st
from streamlit.testing.v1 import AppTest
import json

reporte_json = json.loads(json.dumps(rep, default=str))
LLAMADAS = []


class _Resp:
    status_code = 200
    text = ""

    def json(self):
        return reporte_json


def _post(url, json=None, headers=None, timeout=None):
    LLAMADAS.append((url, json))
    return _Resp()


_requests.post = _post


class Consulta:
    def __init__(s, d):
        s.d = d

    def select(s, *a, **k):
        return s

    def eq(s, *a, **k):
        return s

    def is_(s, *a, **k):
        return s

    def limit(s, *a, **k):
        return s

    def range(s, *a, **k):
        return s

    def execute(s):
        return SimpleNamespace(data=s.d)


class Cliente:
    auth = SimpleNamespace(get_session=lambda: object())

    def table(s, n):
        return Consulta(
            [
                {
                    **e,
                    "nombre": f"Egresado {k}",
                    "email": None,
                    "pais_residencia": None,
                    "situacion_actualizada_en": None,
                    "por_revisar": False,
                    "fecha_registro": None,
                }
                for k, e in enumerate(egr)
            ]
            if n == "egresados"
            else exp
        )


def abrir_admin():
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60)
    at.session_state["auth"] = {
        "cliente": Cliente(),
        "user_id": "u-admin",
        "email": "admin@ejemplo.com",
        "rol": "admin",
        "egresado_id": None,
    }
    at.run()
    return at


at = abrir_admin()
chequear(
    "D0. el panel de administración carga sin errores",
    not at.exception,
    [e.value for e in at.exception][:1],
)
antes = len(at.get("plotly_chart"))
[b for b in at.button if b.label == "Generar reporte"][0].click()
at.run()
despues = len(at.get("plotly_chart"))
chequear(
    "D1. al generar el reporte aparecen los 5 gráficos nuevos en la pestaña",
    despues - antes == 5 and not at.exception,
    (antes, despues),
)
md = " ".join(m.value for m in at.markdown)
chequear(
    "D2. con el título 'Panorama en gráficos', antes del texto",
    "Panorama en gráficos" in md,
)
chequear(
    "D3. el texto del informe va dentro de un panel 'Informe redactado…', abierto por defecto, y se sigue viendo",
    any("Informe redactado" in e.label for e in at.expander)
    and "HALLAZGO-RESUMEN" in md,
)
chequear(
    "D4. cada gráfico muestra su nota de cobertura",
    any("176 de 296 egresados" in c.value for c in at.caption),
)
botones_pdf = [b.proto.label for b in at.get("download_button")]
chequear(
    "D5. sigue la verificación automática (en verde) y el botón para descargar el PDF",
    any("Verificación automática" in s.value for s in at.success)
    and any("PDF" in l for l in botones_pdf),
    botones_pdf,
)
# si los gráficos fallan, el informe escrito NUNCA se esconde
gr_original = gr.figuras_del_reporte


def _rota(ind):
    raise RuntimeError("fallo simulado")


gr.figuras_del_reporte = _rota
at2 = abrir_admin()
[b for b in at2.button if b.label == "Generar reporte"][0].click()
at2.run()
md2 = " ".join(m.value for m in at2.markdown)
chequear(
    "D6. si los gráficos fallan: aviso corto, SIN excepción, y el informe escrito sigue visible",
    not at2.exception
    and any("No se pudieron dibujar los gráficos" in c.value for c in at2.caption)
    and "HALLAZGO-RESUMEN" in md2,
)
gr.figuras_del_reporte = gr_original

print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
