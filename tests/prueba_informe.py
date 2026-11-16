"""Pruebas del informe: indicadores de ciudades, topes de texto, gráficos del PDF y la pestaña de reportes (resumen en la página)."""

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
        s.t, s._r, s._cuenta = t, (0, 10**9), False

    def select(s, c, count=None):
        s._cuenta = count == "exact"
        return s

    def order(s, *a, **k):
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
        return SimpleNamespace(
            data=d[s._r[0] : s._r[1] + 1], count=len(d) if s._cuenta else None
        )


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

# ===== P. la pestaña de reportes: la página da el RESUMEN; el informe completo, con gráficos, está en el PDF =====
import json
import requests as _requests
import streamlit as _st
from streamlit.testing.v1 import AppTest

reporte_json = json.loads(json.dumps(rep, default=str))
ESC = {"codigo": 200, "texto": "", "json": reporte_json, "error": None}


class _Resp:
    def __init__(s):
        s.status_code, s.text = ESC["codigo"], ESC["texto"]

    def json(s):
        if ESC["json"] is None:
            raise ValueError("no es JSON")
        return ESC["json"]


def _post(url, json=None, headers=None, timeout=None):
    if ESC["error"]:
        raise ESC["error"]
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

    def order(s, *a, **k):
        return s

    def execute(s):
        return SimpleNamespace(data=s.d, count=len(s.d))


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


def escenario(codigo=200, texto="", json_=reporte_json, error=None, verificacion=None):
    ESC.update(codigo=codigo, texto=texto, json=json_, error=error)
    reporte_json["verificacion"] = verificacion or {
        "citas_invalidas": [],
        "hallazgos_sin_cita": [],
        "cifras_sin_respaldo": [],
    }


def generar(**kw):
    escenario(**kw)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60)
    at.session_state["auth"] = {
        "cliente": Cliente(),
        "user_id": "u-admin",
        "email": "admin@ejemplo.com",
        "rol": "admin",
        "egresado_id": None,
    }
    at.run()
    antes = len(at.get("plotly_chart"))
    [b for b in at.button if b.label == "Generar reporte"][0].click()
    at.run()
    return at, antes


def visibles_y_ocultos(at):
    todos = [m.value for m in at.markdown]
    dentro = [m.value for e in at.expander for m in e.markdown]
    for v in dentro:
        if v in todos:
            todos.remove(v)
    return todos, dentro


def todo_el_texto(at):
    return " ".join(
        str(x.value)
        for x in list(at.markdown)
        + list(at.caption)
        + list(at.info)
        + list(at.warning)
        + list(at.error)
        + list(at.success)
    )


at0 = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60)
at0.session_state["auth"] = {
    "cliente": Cliente(),
    "user_id": "u-admin",
    "email": "admin@ejemplo.com",
    "rol": "admin",
    "egresado_id": None,
}
at0.run()
chequear(
    "P0. el panel de administración carga sin errores",
    not at0.exception,
    [e.value for e in at0.exception][:1],
)

at, antes = generar()
visibles, ocultos = visibles_y_ocultos(at)
chequear(
    "P1. la página NO dibuja gráficos del informe: no aparece ninguno nuevo al generarlo",
    len(at.get("plotly_chart")) == antes
    and "Panorama en gráficos" not in todo_el_texto(at),
    (antes, len(at.get("plotly_chart"))),
)
chequear(
    "P2. sí muestra el resumen ejecutivo",
    any("HALLAZGO-RESUMEN" in v for v in visibles),
    visibles[-3:],
)
eg = ind["empleabilidad_general"]
valores = {m.label: m.value for m in at.metric}
esperado = {
    "Egresados analizados": f"{ind['totales']['egresados']:,}".replace(",", "."),
    "Empleo sobre el total": f"{eg['tasa_sobre_total']:.1f} %".replace(".", ","),
    "Empleo sobre conocidos": f"{eg['tasa_sobre_conocidos']:.1f} %".replace(".", ","),
    "Situación desconocida": f"{eg['porcentaje_situacion_desconocida']:.1f} %".replace(
        ".", ","
    ),
}
chequear(
    "P3. muestra 4 cifras clave: egresados, empleo sobre el total y sobre conocidos (siempre juntas), y el % desconocido",
    valores == esperado,
    valores,
)
botones = [b.proto.label for b in at.get("download_button")]
chequear(
    "P4. avisa que el informe completo con gráficos está en el PDF, y el botón de descarga es visible",
    any(
        "informe completo" in i.value and "PDF" in i.value and "gráficos" in i.value
        for i in at.info
    )
    and any("PDF" in l for l in botones),
    botones,
)
exp_texto = [e for e in at.expander if "texto completo del informe" in e.label]
chequear(
    "P5. los hallazgos, limitaciones y recomendaciones NO están a la vista: solo dentro de un panel cerrado",
    exp_texto
    and exp_texto[0].proto.expanded is False
    and any("HALLAZGO-3" in v for v in ocultos)
    and not any("HALLAZGO-3" in v for v in visibles),
    exp_texto[0].proto.expanded if exp_texto else None,
)
chequear(
    "P6. se mantiene la verificación automática (en verde)",
    any("Verificación automática" in s.value for s in at.success),
)

at, _ = generar(
    verificacion={
        "citas_invalidas": [],
        "hallazgos_sin_cita": [],
        "cifras_sin_respaldo": ["99,9"],
    }
)
chequear(
    "P7. si la verificación encuentra una cifra sin respaldo, lo avisa en la página",
    any("99,9" in w.value for w in at.warning)
    and not any("Verificación automática: las cifras" in s.value for s in at.success),
)

import informe_pdf as _ipdf

_gen_original = _ipdf.generar_pdf
_ipdf.generar_pdf = lambda r: (_ for _ in ()).throw(
    RuntimeError("fallo simulado del PDF")
)
at, _ = generar()
v9, _o = visibles_y_ocultos(at)
chequear(
    "P8. si el PDF falla: aviso corto, SIN excepción, y el resumen sigue visible",
    not at.exception
    and any("No se pudo generar el PDF" in c.value for c in at.caption)
    and any("HALLAZGO-RESUMEN" in v for v in v9),
)
_ipdf.generar_pdf = _gen_original

html = "<!DOCTYPE html><html><head><title>502</title><style>@font-face{font-family:Roobert}</style></head><body>Bad gateway</body></html>"
casos_ok = True
for codigo in (502, 503, 504):
    at, _ = generar(codigo=codigo, texto=html, json_=None)
    t = todo_el_texto(at)
    casos_ok = (
        casos_ok
        and any("despertando" in w.value for w in at.warning)
        and "<!DOCTYPE" not in t
        and "<html" not in t
        and "Roobert" not in t
        and not at.exception
    )
chequear(
    "P9. si Render responde 502, 503 o 504 (despertando o desplegando): aviso amable, NUNCA la página web cruda",
    casos_ok,
)
at, _ = generar(codigo=500, texto="<html><body>boom interno</body></html>", json_=None)
chequear(
    "P10. un error 500 muestra solo el código, sin volcar el cuerpo de la respuesta",
    any("(500)" in e.value for e in at.error)
    and "boom interno" not in todo_el_texto(at)
    and "<html" not in todo_el_texto(at),
)
at, _ = generar(codigo=401, json_=None)
chequear(
    "P11. clave incorrecta (401): lo dice con claridad",
    any("AGENTES_API_KEY" in e.value for e in at.error),
)
at, _ = generar(
    codigo=400, json_={"detail": "No hay egresados que cumplan ese filtro."}
)
chequear(
    "P12. filtro sin datos (400): muestra el motivo que da el servicio",
    any("No hay egresados que cumplan ese filtro." in w.value for w in at.warning),
)
at, _ = generar(error=_requests.exceptions.ConnectionError("sin red"))
chequear(
    "P13. sin conexión con el servicio: aviso claro y sin excepción",
    not at.exception and any("No se pudo conectar" in e.value for e in at.error),
)
escenario()

print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
