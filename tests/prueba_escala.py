"""
Prueba con una base MÁS EXTENSA de egresados (20 000 inventados): ¿se leen todos, se calculan bien los indicadores,
se genera el informe y el panel muestra el total correcto?

Por qué importa: Supabase devuelve como máximo 1 000 filas por respuesta. El simulador de esta prueba IMITA ese límite: una lectura
simple trae solo las primeras 1 000 y las demás no aparecen. Antes de esta corrección, el panel se habría quedado con 1 000 sin avisar.

OJO con los tiempos que imprime: son de CÁLCULO en memoria. En la nube se suman la red (20 lecturas para 20 000 filas) y la IA.
"""

import io, os, random, re, sys, time
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

import pandas as pd
from pypdf import PdfReader
import agente_reportes as ar
from informe_pdf import generar_pdf
from lectura_datos import leer_todo

resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:130]) if d else "")


# ---------- 20 000 egresados inventados ----------
N, N_SINTETICOS = 20000, 1000
random.seed(11)
CIUDADES = [
    "Bucaramanga",
    "Bogotá",
    "Medellín",
    "Cali",
    "Barrancabermeja",
    "Cúcuta",
    "Floridablanca",
    "Barranquilla",
    "Pereira",
    "Manizales",
    "Piedecuesta",
    "Girón",
    "Tunja",
    "Villavicencio",
    "Ibagué",
    "Neiva",
    "Armenia",
    "Santa Marta",
    "Cartagena",
    "Pasto",
    "Madrid (España)",
    "Lima (Perú)",
]
SECT = [
    "Telecomunicaciones",
    "Tecnología / Software",
    "Energía y petróleo",
    "Educación",
    "Salud",
    "Banca y finanzas",
    "Consultoría",
    "Gobierno",
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
    "Kubernetes",
    "Git",
]
egr, exp = [], []
for i in range(N):
    sit = random.choices(
        ["empleado", "desempleado", "desconocido", "estudios_posteriores"],
        [45, 5, 45, 5],
    )[0]
    egr.append(
        {
            "id": f"e{i:06d}",
            "nombre": f"Egresado {i}",
            "email": None,
            "cohorte": str(random.randint(2005, 2025)),
            "situacion_laboral": sit,
            "fuente": "sintetico" if i < N_SINTETICOS else "real",
            "ciudad_residencia": random.choice(CIUDADES)
            if random.random() < 0.4
            else None,
            "pais_residencia": None,
            "especializacion_posterior": None,
            "maestria_posterior": None,
            "doctorado_posterior": None,
            "situacion_origen": "institucional_historico",
            "situacion_actualizada_en": None,
            "por_revisar": False,
            "fecha_registro": None,
        }
    )
    if sit == "empleado":
        exp.append(
            {
                "id": f"x{i:06d}",
                "egresado_id": f"e{i:06d}",
                "empresa": f"Empresa {i % 900}",
                "cargo": "Ingeniero",
                "sector": random.choice(SECT),
                "tecnologias": random.sample(TEC, random.randint(0, 3)) or None,
                "tipo_empresa": None,
                "area_funcional": random.choice(AREAS),
                "clasificacion_origen": "inferido_ia",
                "fecha_fin": None,
            }
        )
N_REALES = N - N_SINTETICOS


# ---------- Supabase simulado, CON el límite real de filas por respuesta ----------
class Servidor:
    def __init__(s, tope=1000, con_conteo=True, datos=None):
        s.tope, s.con_conteo, s.peticiones = tope, con_conteo, 0
        s.datos = datos or {
            "egresados": egr,
            "experiencia_laboral": exp,
            "programas": [{"id": "p1"}],
        }

    def table(s, t):
        return Tabla(s, s.datos[t])


class Tabla:
    def __init__(s, srv, filas):
        s.srv, s.f, s._r, s._cuenta = srv, filas, (0, 10**9), False

    def select(s, *a, **k):
        s._cuenta = k.get("count") == "exact"
        return s

    def order(s, *a, **k):
        return s  # las filas ya están ordenadas por id

    def range(s, a, b):
        s._r = (a, b)
        return s

    def limit(s, n):
        s._r = (0, n - 1)
        return s

    def eq(s, *a, **k):
        return s

    def execute(s):
        s.srv.peticiones += 1
        a, b = s._r
        lote = s.f[
            a : min(b + 1, a + s.srv.tope)
        ]  # el servidor corta en `tope` filas por respuesta
        return SimpleNamespace(
            data=lote, count=len(s.f) if (s._cuenta and s.srv.con_conteo) else None
        )


# ===== A. la lectura paginada =====
srv = Servidor()
chequear(
    "A1. EL LÍMITE ES REAL: una lectura simple trae solo 1 000 de 20 000 filas (lo que pasaba antes en el panel)",
    len(srv.table("egresados").select("*").execute().data) == 1000,
)
srv = Servidor()
filas = leer_todo(srv, "egresados")
ids = [f["id"] for f in filas]
chequear(
    "A2. leer_todo trae las 20 000 filas, sin repetir ni saltarse ninguna y en orden",
    len(filas) == N and len(set(ids)) == N and ids == sorted(ids),
    len(filas),
)
chequear(
    "A3. y lo hace con el mínimo de peticiones (20 páginas de 1 000)",
    srv.peticiones == 20,
    srv.peticiones,
)
srv = Servidor(con_conteo=False)
chequear(
    "A4. si el servidor no informa el total, igual trae todo (con una petición vacía de cierre)",
    len(leer_todo(srv, "egresados")) == N and srv.peticiones <= 21,
    srv.peticiones,
)
chequear(
    "A5. si el servidor recorta aún más (500 por respuesta), igual trae todo",
    len(leer_todo(Servidor(tope=500), "egresados")) == N,
)
casos = {}
for n_filas in (0, 1, 999, 1000, 1001, 2000):
    s_ = Servidor(datos={"t": [{"id": f"{k:05d}"} for k in range(n_filas)]})
    casos[n_filas] = (
        len(leer_todo(s_, "t")) == n_filas and s_.peticiones <= n_filas // 1000 + 2
    )
chequear(
    "A6. casos de borde (0, 1, 999, 1 000, 1 001 y 2 000 filas): ni faltan filas ni se queda en un ciclo",
    all(casos.values()),
    casos,
)

# ===== B. indicadores, informe y PDF con la base grande =====
t0 = time.time()


def ia(prompt, modelo, nombre_modelo=None, timeout=None):
    return ar.ReporteAcreditacion(
        resumen_ejecutivo="Resumen de ejemplo.",
        hallazgos=[
            ar.Hallazgo(
                afirmacion="Hallazgo de ejemplo.", indicadores_citados=["totales"]
            )
        ],
        limitaciones_de_los_datos=["Limitación de ejemplo."],
        recomendaciones=["Recomendación de ejemplo."],
    )


ar.generar_estructurado = ia
t0 = time.time()
reporte = ar.generar_reporte(Servidor(), "real", "historico")
t_reporte = time.time() - t0
ind = reporte["indicadores"]
chequear(
    f"B1. el AGENTE cuenta a los {N_REALES} egresados reales (no 1 000); el cálculo toma {t_reporte:.1f} s (sin red ni IA)",
    ind["totales"]["egresados"] == N_REALES and t_reporte < 30,
    (ind["totales"]["egresados"], round(t_reporte, 1)),
)
eg = ind["empleabilidad_general"]
chequear(
    "B2. los indicadores son coherentes: empleo sobre conocidos entre 0 y 100 y el % desconocido cerca del 45 % inventado",
    0 < eg["tasa_sobre_conocidos"] < 100
    and 40 < eg["porcentaje_situacion_desconocida"] < 50,
    eg,
)
chequear(
    "B3. la verificación automática del informe sigue limpia con tantos datos",
    reporte["verificacion"]
    == {"citas_invalidas": [], "hallazgos_sin_cita": [], "cifras_sin_respaldo": []},
)
chequear(
    "B4. el indicador de ciudades trae las 10 principales, ordenadas, con 22 ciudades posibles",
    len(ind["ubicacion_top"]["ciudades"]) == 10
    and list(ind["ubicacion_top"]["ciudades"].values())
    == sorted(ind["ubicacion_top"]["ciudades"].values(), reverse=True),
)
t0 = time.time()
pdf = generar_pdf(reporte)
t_pdf = time.time() - t0
texto_pdf = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
chequear(
    f"B5. el PDF se genera con todos los gráficos (Figura 2, ciudades) en {t_pdf:.1f} s (sin red ni IA)",
    pdf[:4] == b"%PDF"
    and "Figura 2. Ciudades de residencia" in texto_pdf
    and t_pdf < 30,
    round(t_pdf, 1),
)

# ===== C. el panel de administración con la base grande =====
import streamlit as _st
from streamlit.testing.v1 import AppTest


class Cliente:
    auth = SimpleNamespace(get_session=lambda: object())

    def __init__(s):
        s.srv = Servidor()

    def table(s, n):
        return s.srv.table(n)


at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180)
cli = Cliente()
at.session_state["auth"] = {
    "cliente": cli,
    "user_id": "u-admin",
    "email": "admin@ejemplo.com",
    "rol": "admin",
    "egresado_id": None,
}
t0 = time.time()
at.run()
[r for r in at.radio if r.label == "Periodo"][0].set_value("Histórico completo")
at.run()
t_panel = time.time() - t0
html = " ".join(m.value for m in at.markdown)
m = re.search(
    r"Egresados en esta vista</div><div class=\"valor\">([\d\.\,]+)</div>", html
)
mostrado = int(re.sub(r"\D", "", m.group(1))) if m else None
chequear(
    f"C1. EL PANEL MUESTRA LOS {N} EGRESADOS (antes: 1 000); el cálculo toma {t_panel:.1f} s (sin red)",
    not at.exception and mostrado == N and t_panel < 120,
    (mostrado, round(t_panel, 1)),
)
chequear(
    "C2. y para leer las 2 tablas (egresados y experiencia) hizo las peticiones esperadas, no una por fila",
    0 < cli.srv.peticiones <= 2 * (N // 1000) + 12,
    cli.srv.peticiones,
)

print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
