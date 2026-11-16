"""Pruebas del aviso de privacidad, de 'Descargar mis datos', de la exportación de indicadores (CSV) y del punto de acceso de lectura."""

import csv, io, json, os, random, re, sys
from datetime import datetime
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
os.environ.pop("CONTACTO_PRIVACIDAD", None)

import agente_reportes as ar
import aviso_privacidad as av
import exportar as ex

resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:120]) if d else "")


# ===== A. el texto del aviso =====
TEXTO_DE_LA_FACULTAD = (
    "La Facultad de Ingeniería de Telecomunicaciones de la Universidad Santo Tomás agradece su colaboración en el diligenciamiento de la "
    "información solicitada. De conformidad con la Ley 1581 de 2012, el Decreto 1074 de 2015 y demás normas vigentes sobre protección de datos "
    "personales, solicita su autorización previa, libre, expresa e informada para el tratamiento de los datos suministrados a través de esta "
    "aplicación. La información será utilizada para mantener actualizados los datos de los graduados, facilitar la comunicación institucional, "
    "promover actividades académicas y de relacionamiento, y fortalecer el vínculo entre los graduados, la Facultad y la Universidad."
)
texto = av.aviso_markdown()
chequear(
    "A1. tiene las 11 secciones numeradas",
    all(f"### {i}. " in texto for i in range(1, 12)),
    [i for i in range(1, 12) if f"### {i}. " not in texto],
)
chequear(
    "A2. dice quién es el responsable y que es un proyecto académico",
    "Universidad Santo Tomás" in texto
    and "Facultad de Ingeniería de Telecomunicaciones" in texto
    and "proyecto académico" in texto,
)
chequear(
    "A3. explica la finalidad en SIGMA (indicadores e informes) además de la de la Facultad, y que no se venden ni se usan con fines comerciales",
    "indicadores e informes de seguimiento y acreditación" in texto
    and "No vendemos tus datos" in texto
    and "fines comerciales" in texto,
)
chequear(
    "A4. el inventario de datos cubre cuenta, perfil, CV (que NO se guarda) y contador de uso",
    all(
        x in texto
        for x in (
            "Nombre, año de grado y correo",
            "Situación laboral, empresa",
            "Tu CV en PDF",
            "No se guarda",
            "Cuántas veces usaste el análisis de CV",
        )
    ),
)
chequear(
    "A5. nombra a los 4 proveedores y avisa que los datos pueden salir del país",
    all(
        x in texto
        for x in ("Supabase", "Streamlit Community Cloud", "Render", "Google (Gemini)")
    )
    and "fuera del país" in texto
    and "São Paulo" in texto,
)
chequear(
    "A6. sobre la IA: plan gratuito, la IA solo propone, y los informes usan indicadores agrupados",
    "plan gratuito" in texto
    and "La IA solo propone" in texto
    and "indicadores agrupados" in texto,
)
chequear(
    "A7. los derechos: conocer, rectificar, suprimir, revocar, quejas ante la SIC, Ley 1581 de 2012 y Decreto 1074 de 2015",
    all(
        x in texto
        for x in (
            "conocer, actualizar y rectificar",
            "revocar la autorización",
            "supresión",
            "Superintendencia de Industria y Comercio",
            "Ley 1581 de 2012",
            "Decreto 1074 de 2015",
        )
    ),
)
chequear(
    "A8. cómo ejercerlos: corregir en 'Mi perfil', descargar la copia y los plazos de ley (10 y 15 días hábiles)",
    "«Mi perfil»" in texto
    and "Descargar mis datos" in texto
    and "10 días hábiles" in texto
    and "15 días hábiles" in texto,
)
chequear(
    "A9. EL TEXTO DE LA FACULTAD está completo y literal (ni una coma distinta) y es la sección 1",
    av.TEXTO_AUTORIZACION == TEXTO_DE_LA_FACULTAD
    and "### 1. Aviso de privacidad y autorización de la Facultad\n"
    + TEXTO_DE_LA_FACULTAD
    in texto,
)
chequear(
    "A9b. aclara qué es de la Facultad (secciones 1 y 2) y qué es descripción técnica, y ya no dice 'borrador' sobre la autorización",
    "Las secciones 1 y 2 son el aviso de la Facultad" in texto
    and "borrador" not in texto.lower()
    and "BORRADOR" not in texto,
)
chequear(
    "A10. avisa que parte de los datos son ficticios y están marcados",
    "datos ficticios" in texto,
)
chequear(
    "A11. sin configurar, el canal de contacto dice que está pendiente (no inventa uno)",
    "pendiente de definir por la Facultad" in texto,
)
os.environ["CONTACTO_PRIVACIDAD"] = "datos@ejemplo.com"
chequear(
    "A12. con CONTACTO_PRIVACIDAD configurado, el canal aparece en el aviso",
    "datos@ejemplo.com" in av.aviso_markdown()
    and "pendiente de definir" not in av.aviso_markdown(),
)
os.environ.pop("CONTACTO_PRIVACIDAD")
fuente = (RAIZ / "aviso_privacidad.py").read_text(encoding="utf-8")
chequear(
    "A13. NINGÚN correo queda escrito en el código del aviso (se configura aparte, así el repositorio público se puede armar)",
    not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", fuente.replace("datos@ejemplo.com", "")),
)

# ===== B. CSV de indicadores =====
IND = {
    "alcance": {
        "fuente": "real",
        "ventana": "Histórico completo",
        "fecha_generacion": "2026-10-27",
    },
    "totales": {"egresados": 615, "empleados": 317},
    "empleabilidad_por_cohorte": {
        "2023": {"total": 50, "empleados": 30},
        "2024": {"total": 40, "empleados": 22},
    },
    "ubicacion_top": {
        "egresados_con_ciudad": 300,
        "ciudades": {"Bogotá": 80, "Bucaramanga": 120},
    },
    "criterios_de_analisis": {"lista": ["uno", "dos"], "vacio": None},
}
datos_csv = ex.indicadores_a_csv(IND, {"origen": "SIGMA"})
filas = list(csv.reader(io.StringIO(datos_csv.decode("utf-8-sig"))))
cuerpo = {(f[0], f[1]): f[2] for f in filas[1:]}
chequear(
    "B1. el CSV empieza con la marca de orden UTF-8 (Excel muestra bien las tildes) y su encabezado es categoria, indicador, valor",
    datos_csv[:3] == b"\xef\xbb\xbf"
    and filas[0] == ["categoria", "indicador", "valor"],
)
chequear(
    "B2. los indicadores salen con su valor exacto",
    cuerpo[("totales", "egresados")] == "615"
    and cuerpo[("totales", "empleados")] == "317",
)
chequear(
    "B3. lo anidado se aplana con la ruta completa (cohorte 2023, empleados = 30)",
    cuerpo[("empleabilidad_por_cohorte", "2023 / empleados")] == "30"
    and cuerpo[("empleabilidad_por_cohorte", "2024 / total")] == "40",
)
chequear(
    "B4. las ciudades salen una por fila con su cifra, con tildes",
    cuerpo[("ubicacion_top", "ciudades / Bogotá")] == "80"
    and cuerpo[("ubicacion_top", "ciudades / Bucaramanga")] == "120",
)
chequear(
    "B5. las listas se unen con '; ' y lo vacío queda en blanco",
    cuerpo[("criterios_de_analisis", "lista")] == "uno; dos"
    and cuerpo[("criterios_de_analisis", "vacio")] == "",
)
chequear(
    "B6. los metadatos opcionales van primero, y el alcance (fuente, periodo, fecha) viaja en el propio CSV",
    filas[1] == ["metadatos", "origen", "SIGMA"]
    and cuerpo[("alcance", "ventana")] == "Histórico completo"
    and ("alcance", "fecha_generacion") in cuerpo,
)
chequear(
    "B7. es una tabla 'larga' (una cifra por fila): cualquier herramienta puede leerla",
    all(len(f) == 3 for f in filas),
)

# ===== C. copia de los datos de una persona =====
perfil = {
    "id": "e1",
    "nombre": "Ana Real",
    "cohorte": "2022",
    "situacion_laboral": "empleado",
    "fecha_registro": datetime(2026, 1, 2, 3, 4, 5),
    "ciudad_residencia": "Bogotá",
}
exper = [
    {
        "empresa": "Huawei Colombia",
        "cargo": "Ingeniera de Redes",
        "tecnologias": ["Python", "5G"],
    }
]
j = json.loads(
    ex.mis_datos_json(
        "ana@ejemplo.com", perfil, exper, datetime(2026, 10, 27, 12, 0, 0)
    ).decode("utf-8")
)
chequear(
    "C1. la copia es un JSON válido con la cuenta, el perfil y la experiencia",
    j["cuenta"]["correo"] == "ana@ejemplo.com"
    and j["perfil"]["nombre"] == "Ana Real"
    and j["experiencia_laboral"][0]["empresa"] == "Huawei Colombia",
)
chequear(
    "C2. dice qué NO incluye (la contraseña y el PDF del CV) y cuándo se generó",
    any("contraseña" in x for x in j["no_incluye"])
    and any("PDF" in x for x in j["no_incluye"])
    and j["generado_en"].startswith("2026-10-27T12:00:00"),
)
chequear(
    "C3. las fechas y las tildes se guardan legibles (sin \\u00e1)",
    "2026-01-02" in str(j["perfil"]["fecha_registro"])
    and "Bogotá" in ex.mis_datos_json("a@x", perfil, exper).decode("utf-8"),
)
vacio = json.loads(ex.mis_datos_json("a@x", None, None).decode("utf-8"))
chequear(
    "C4. sin perfil ni experiencia no revienta: entrega listas y diccionarios vacíos",
    vacio["perfil"] == {} and vacio["experiencia_laboral"] == [],
)

# ===== D. punto de acceso de lectura para otras aplicaciones =====
random.seed(5)
CIUDADES = ["Bucaramanga", "Bogotá", "Cali", None]
egr = [
    {
        "id": f"e{i:04d}",
        "cohorte": "2023",
        "situacion_laboral": random.choice(["empleado", "desconocido", "desempleado"]),
        "fuente": "real",
        "ciudad_residencia": random.choice(CIUDADES),
        "especializacion_posterior": None,
        "maestria_posterior": None,
        "doctorado_posterior": None,
        "situacion_origen": "institucional_historico",
    }
    for i in range(80)
]
exp = [
    {
        "id": f"x{i}",
        "egresado_id": f"e{i:04d}",
        "sector": "Educación",
        "tecnologias": ["Python"],
        "tipo_empresa": None,
        "area_funcional": "Docencia e investigación",
        "clasificacion_origen": "inferido_ia",
        "fecha_fin": None,
    }
    for i in range(30)
]


class Tabla:
    def __init__(s, filas):
        s.f, s._r, s._c = filas, (0, 10**9), False

    def select(s, *a, **k):
        s._c = k.get("count") == "exact"
        return s

    def order(s, *a, **k):
        return s

    def range(s, a, b):
        s._r = (a, b)
        return s

    def limit(s, n):
        return s

    def execute(s):
        return SimpleNamespace(
            data=s.f[s._r[0] : s._r[1] + 1], count=len(s.f) if s._c else None
        )


class SB:
    def table(s, t):
        return Tabla(
            {"egresados": egr, "experiencia_laboral": exp, "programas": [{"id": "p1"}]}[
                t
            ]
        )


def ia_prohibida(*a, **k):
    raise AssertionError("el punto de acceso de lectura NO debe usar la IA")


ar.generar_estructurado = ia_prohibida
from fastapi.testclient import TestClient
import main

main.supabase = SB()
c, H = TestClient(main.app), {"x-api-key": "clave-de-prueba"}
chequear(
    "D1. sin la clave de acceso: 401", c.get("/api/indicadores").status_code == 401
)
r = c.get("/api/indicadores", headers=H)
chequear(
    "D2. con la clave: 200 y los indicadores en JSON, con el total de egresados reales",
    r.status_code == 200
    and r.json()["indicadores"]["totales"]["egresados"] == 80
    and r.json()["fuente"] == "real",
    r.status_code,
)
chequear(
    "D3. NO usa IA (si la usara, la prueba fallaría) y devuelve solo cifras agrupadas: ni nombres, ni identificadores, ni correos de personas",
    r.status_code == 200
    and '"nombre"' not in r.text
    and '"email"' not in r.text
    and not re.search(r"\be\d{4}\b", r.text)
    and "@" not in r.text,
)
r = c.get("/api/indicadores?formato=csv&ventana=historico", headers=H)
chequear(
    "D4. en CSV: tipo text/csv, marca UTF-8, se descarga con nombre de archivo",
    r.status_code == 200
    and r.headers["content-type"].startswith("text/csv")
    and r.content[:3] == b"\xef\xbb\xbf"
    and "indicadores_sigma.csv" in r.headers["content-disposition"],
    r.headers.get("content-type"),
)
filas_api = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
chequear(
    "D5. el CSV del servicio trae los metadatos (fuente, periodo, generado_en) y las ciudades",
    ["metadatos", "fuente", "real"] in filas_api
    and ["metadatos", "periodo", "historico"] in filas_api
    and any(f[1].startswith("ciudades / ") for f in filas_api),
)
chequear(
    "D6. un parámetro inválido se rechaza (422)",
    c.get("/api/indicadores?fuente=otra", headers=H).status_code == 422
    and c.get("/api/indicadores?formato=xml", headers=H).status_code == 422,
)
r = c.get("/api/indicadores?fuente=sintetico", headers=H)
chequear(
    "D7. si no hay datos para ese filtro: 400 con el motivo",
    r.status_code == 400 and "No hay egresados" in r.json()["detail"],
    r.status_code,
)

# ===== E. las pantallas =====
import requests as _requests
from streamlit.testing.v1 import AppTest


class Consulta:
    def __init__(s, cli, tabla, datos):
        s.cli, s.t, s.d = cli, tabla, datos

    def select(s, *a, **k):
        return s

    def eq(s, col, val):
        s.cli.eqs.append((s.t, col, val))
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


class Llamada:
    def __init__(s, cli, n, p):
        s.cli, s.n, s.p = cli, n, p

    def execute(s):
        s.cli.llamadas.append((s.n, s.p))
        return SimpleNamespace(data=None)


class ClienteEgresado:
    auth = SimpleNamespace(get_session=lambda: object())

    def __init__(s):
        s.eqs, s.llamadas = [], []
        s.egresados = [
            {
                "id": "e1",
                "nombre": "Ana Real",
                "cohorte": "2022",
                "email": "ana@ejemplo.com",
                "situacion_laboral": "empleado",
                "ciudad_residencia": "Cali",
                "pais_residencia": "Colombia",
                "consentimiento_datos": True,
                "situacion_actualizada_en": None,
                "situacion_origen": "institucional_historico",
                "por_revisar": False,
            }
        ]
        s.exp = [
            {
                "id": "x1",
                "egresado_id": "e1",
                "empresa": "Huawei Colombia",
                "cargo": "Ingeniera de Redes",
                "sector": "Telecomunicaciones",
                "area_funcional": None,
                "tecnologias": ["Python"],
                "clasificacion_origen": "declarado",
                "fecha_fin": None,
            }
        ]

    def table(s, n):
        return Consulta(s, n, s.egresados if n == "egresados" else s.exp)

    def rpc(s, n, p):
        return Llamada(s, n, p)


def abrir_egresado(egresado_id="e1", vinculo=None):
    cli = ClienteEgresado()
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60)
    auth = {
        "cliente": cli,
        "user_id": "u1",
        "email": "ana@ejemplo.com",
        "rol": "egresado",
        "egresado_id": egresado_id,
    }
    if vinculo:
        auth["vinculo"] = vinculo
    at.session_state["auth"] = auth
    at.run()
    return cli, at


def boton(at, clave):
    return [b for b in at.button if b.key == clave][0]


def descargas(at):
    return [b.proto.label for b in at.get("download_button")]


def texto_total(at):
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
at0.run()
chequear(
    "E1. ANTES de entrar, la pantalla de acceso tiene 4 pestañas y la última es 'Privacidad', con el aviso a la vista",
    [t.label for t in at0.tabs][:4]
    == ["Iniciar sesión", "Crear cuenta", "Confirmar correo", "Privacidad"]
    and "Quién es el responsable" in texto_total(at0),
    [t.label for t in at0.tabs],
)

cli, at = abrir_egresado()
chequear(
    "E2. el egresado ve 'Privacidad y mis datos' con el aviso y el botón 'Preparar mi copia', SIN descarga todavía",
    any("Privacidad y mis datos" in e.label for e in at.expander)
    and "Quién es el responsable" in texto_total(at)
    and boton(at, "preparar_mis_datos")
    and not descargas(at),
)
boton(at, "preparar_mis_datos").click()
at.run()
copia = json.loads(at.session_state["mis_datos"].decode("utf-8"))
chequear(
    "E3. al preparar la copia aparece 'Descargar mis datos (JSON)' con su perfil y su experiencia",
    any("Descargar mis datos" in l for l in descargas(at))
    and copia["perfil"]["nombre"] == "Ana Real"
    and copia["experiencia_laboral"][0]["empresa"] == "Huawei Colombia"
    and copia["cuenta"]["correo"] == "ana@ejemplo.com",
)
chequear(
    "E4. la copia se pide FILTRADA por el id de la persona (no se trae lo de otros)",
    ("egresados", "id", "e1") in cli.eqs
    and ("experiencia_laboral", "egresado_id", "e1") in cli.eqs,
    cli.eqs,
)
# guardar el perfil deja la copia desactualizada: se descarta
at.radio[0].set_value("Estoy buscando empleo")
[c_ for c_ in at.checkbox if c_.key is None][0].set_value(True)
[b for b in at.button if b.label == "Guardar mi información"][0].click()
at.run()
chequear(
    "E5. al guardar cambios la copia anterior se descarta (para no entregar datos viejos)",
    "mis_datos" not in at.session_state
    and any(n == "guardar_mi_perfil" for n, p in cli.llamadas),
)
cli, at = abrir_egresado()
boton(at, "preparar_mis_datos").click()
at.run()
[b for b in at.button if b.label == "Cerrar sesión"][0].click()
at.run()
chequear(
    "E6. al cerrar sesión se borra la copia de la memoria",
    "mis_datos" not in at.session_state and "auth" not in at.session_state,
)
cli, at = abrir_egresado(egresado_id=None, vinculo="sin_coincidencia")
chequear(
    "E7. quien aún no tiene perfil (crear perfil nuevo) ve el aviso, pero SIN botón de descarga (no hay nada que descargar)",
    any("Privacidad y mis datos" in e.label for e in at.expander)
    and "Quién es el responsable" in texto_total(at)
    and not [b for b in at.button if b.key == "preparar_mis_datos"],
)

cli, at = abrir_egresado()
casilla = [c_ for c_ in at.checkbox if c_.key is None][0]
dentro = [
    m.value
    for e in at.expander
    if "texto completo de la autorización" in e.label
    for m in e.markdown
]
chequear(
    "E10. el formulario usa el TEXTO DE LA FACULTAD: la casilla dice 'Autorizo… el tratamiento de mis datos personales' y el texto completo es el literal, sin 'BORRADOR'",
    casilla.label.startswith(
        "Autorizo a la Facultad de Ingeniería de Telecomunicaciones de la Universidad Santo Tomás el tratamiento de mis datos personales"
    )
    and any(TEXTO_DE_LA_FACULTAD in v for v in dentro)
    and "BORRADOR" not in texto_total(at)
    and "borrador" not in texto_total(at).lower(),
    casilla.label[:90],
)


# --- administración ---
class Cli2(ClienteEgresado):
    def table(s, n):
        filas = (
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
        return Consulta(s, n, filas)


ar.generar_estructurado = lambda p, m, nombre_modelo=None, timeout=None: (
    ar.ReporteAcreditacion(
        resumen_ejecutivo="Resumen de ejemplo.",
        hallazgos=[
            ar.Hallazgo(
                afirmacion="Hallazgo de ejemplo.", indicadores_citados=["totales"]
            )
        ],
        limitaciones_de_los_datos=["Limitación de ejemplo."],
        recomendaciones=["Recomendación de ejemplo."],
    )
)
reporte_json = json.loads(
    json.dumps(ar.generar_reporte(SB(), "real", "historico"), default=str)
)


class _Resp:
    status_code, text = 200, ""

    def json(s):
        return reporte_json


_requests.post = lambda url, json=None, headers=None, timeout=None: _Resp()

at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60)
at.session_state["auth"] = {
    "cliente": Cli2(),
    "user_id": "u-admin",
    "email": "admin@ejemplo.com",
    "rol": "admin",
    "egresado_id": None,
}
at.run()
chequear(
    "E8. el administrador tiene 5 pestañas y la última es 'Privacidad', con el mismo aviso",
    len(at.tabs) == 5
    and at.tabs[-1].label == "Privacidad"
    and any("Quién es el responsable" in m.value for m in at.tabs[-1].markdown),
    [t.label for t in at.tabs],
)
[b for b in at.button if b.label == "Generar reporte"][0].click()
at.run()
etiquetas = descargas(at)
chequear(
    "E9. tras generar el reporte hay DOS descargas: el informe en PDF y los indicadores en CSV",
    any("PDF" in l for l in etiquetas)
    and any("CSV" in l for l in etiquetas)
    and not at.exception,
    etiquetas,
)

print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
