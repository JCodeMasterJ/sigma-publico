"""Pruebas de «Tu cohorte en cifras» (motor, portal real) y del modo demostración para stands (datos ficticios, sin base de datos)."""

import io, os, re, sys
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
import cohorte as co
import datos_demo as dd
from informe_pdf import generar_pdf
from taxonomia import AREAS, SECTORES

resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:120]) if d else "")


# ===== A. el motor de cifras de cohorte =====
def fila(i, sit="desconocido", ciudad=None, coh="2018", fuente="real", pend=False):
    return {
        "id": f"e{i}",
        "cohorte": coh,
        "fuente": fuente,
        "situacion_laboral": sit,
        "ciudad_residencia": ciudad,
        "por_revisar": pend,
    }


def exp(eid, sector, techs, fin=None):
    return {
        "egresado_id": eid,
        "sector": sector,
        "tecnologias": techs,
        "fecha_fin": fin,
    }


E = [
    fila(1, "empleado", "Bucaramanga"),
    fila(2, "empleado", "Bucaramanga"),
    fila(3, "empleado", "Bucaramanga"),
    fila(4, "empleado", "Bucaramanga"),
    fila(5, "empleado", "Bogotá"),
    fila(6, "empleado", "Bogotá"),
    fila(7, "empleado", "Bogotá"),
    fila(8, "empleado", "Cali"),
    fila(9, "desempleado", "Bucaramanga"),
    fila(10, "desconocido", "Cali"),
    fila(11, "desconocido", "Cúcuta"),
    fila(12),
    fila(13),
    fila(14, "estudios_posteriores"),
    fila(20, "empleado", "Bucaramanga", pend=True),
    fila(21, "empleado", "Bucaramanga", fuente="sintetico"),
    fila(22, "desconocido", "Pasto", coh="2019"),
]
X = [
    exp("e1", "Telecomunicaciones", ["Python", "Cisco"]),
    exp("e1", "Telecomunicaciones", ["Rust"] * 4, "2019-01-01"),
    exp("e2", "Telecomunicaciones", ["Python", "Cisco"]),
    exp("e3", "Telecomunicaciones", ["Python"]),
    exp("e4", "Telecomunicaciones", ["Python", "Linux", "Cisco"]),
    exp("e5", "Tecnología", ["Python", "Linux"]),
    exp("e6", "Tecnología", ["Go"]),
    exp("e7", "Tecnología", []),
    exp("e8", "Salud", None),
    exp("e20", "Telecomunicaciones", ["Python"]),
]
dfe, dfx = pd.DataFrame(E), pd.DataFrame(X)
c = co.cifras_de_cohorte(dfe, dfx, "2018", "real")
chequear(
    "A1. promoción de 14: n y situaciones correctas (8 empleados, 1 desempleado, 4 desconocidos, 1 estudiando)",
    c["suficiente"]
    and (
        c["n"],
        c["empleados"],
        c["desempleados"],
        c["desconocidos"],
        c["estudios_posteriores"],
    )
    == (14, 8, 1, 4, 1),
    c,
)
chequear(
    "A2. las tasas: 57,1 % sobre el total, 88,9 % sobre conocidos, 28,6 % desconocidos",
    (c["tasa_sobre_total"], c["tasa_sobre_conocidos"], c["porcentaje_desconocido"])
    == (57.1, 88.9, 28.6),
)
chequear(
    "A3. celdas pequeñas ocultas: ciudades (Cali 2, Cúcuta 1), sectores (Salud 1) y tecnologías (Linux 2, Go 1) no aparecen",
    c["ciudades"] == {"Bucaramanga": 5, "Bogotá": 3}
    and c["sectores"] == {"Telecomunicaciones": 4, "Tecnología": 3}
    and c["tecnologias"] == {"Python": 5, "Cisco": 3},
    (c["ciudades"], c["sectores"], c["tecnologias"]),
)
chequear(
    "A4. no cuenta al perfil pendiente de revisión, ni a otra fuente, ni a otra promoción, ni a la experiencia ya terminada",
    c["n"] == 14 and "Pasto" not in str(c) and "Rust" not in c["tecnologias"],
)
c4 = co.cifras_de_cohorte(dfe, dfx, "2019", "real")
chequear(
    "A5. una promoción con menos de 10 NO entrega ninguna cifra, solo cuántos son y el mínimo",
    c4 == {"suficiente": False, "cohorte": "2019", "n": 1, "minimo": 10},
    c4,
)
chequear(
    "A6. el año puede darse como número o como texto",
    co.cifras_de_cohorte(dfe, dfx, 2018, "real") == c,
)
tie = pd.DataFrame(
    [fila(i, "empleado" if i == 0 else "desconocido", coh="2040") for i in range(16)]
)
ct = co.cifras_de_cohorte(tie, dfx, "2040", "real")
chequear(
    "A7. empate al redondear (1/16 = 6,25 % y 15/16 = 93,75 %) sube: 6,3 y 93,8 (como Postgres; el round de Python daría 6,2)",
    (ct["tasa_sobre_total"], ct["porcentaje_desconocido"]) == (6.3, 93.8),
    ct,
)
nadie = pd.DataFrame([fila(i, "desconocido", coh="2041") for i in range(12)])
cn = co.cifras_de_cohorte(nadie, dfx, "2041", "real")
chequear(
    "A8. si nadie tiene situación conocida, la tasa sobre conocidos es 'sin dato' (no divide por cero)",
    cn["suficiente"]
    and cn["tasa_sobre_conocidos"] is None
    and cn["porcentaje_desconocido"] == 100.0,
    cn,
)
emp = pd.DataFrame([fila(i, "empleado", "Cali", coh="2042") for i in range(10)])
ce = co.cifras_de_cohorte(
    emp,
    pd.DataFrame([exp(f"e{i}", "Salud", ["Excel"]) for i in range(10)]),
    "2042",
    "real",
)
chequear(
    "A9. con 10 personas (el mínimo justo) ya se muestran cifras; con empates se ordena alfabéticamente",
    ce["suficiente"]
    and ce["ciudades"] == {"Cali": 10}
    and ce["tecnologias"] == {"Excel": 10},
)

# ===== B. datos ficticios e informe de ejemplo =====
egr, exa = dd.generar_datos_demo()
chequear(
    "B1. son deterministas: la misma semilla da exactamente los mismos datos",
    dd.generar_datos_demo(300)[0].equals(dd.generar_datos_demo(300)[0])
    and not dd.generar_datos_demo(300, 1)[0].equals(dd.generar_datos_demo(300, 2)[0]),
)
columnas_panel = {
    "id",
    "nombre",
    "cohorte",
    "situacion_laboral",
    "fuente",
    "ciudad_residencia",
    "pais_residencia",
    "email",
    "situacion_origen",
    "situacion_actualizada_en",
    "por_revisar",
    "fecha_registro",
}
columnas_exp = {
    "egresado_id",
    "empresa",
    "cargo",
    "sector",
    "tecnologias",
    "tipo_empresa",
    "area_funcional",
    "clasificacion_origen",
    "fecha_fin",
}
chequear(
    "B2. 4 000 egresados con las mismas columnas que los datos reales, y experiencia solo de los empleados",
    len(egr) == dd.N_DEMO == 4000
    and columnas_panel <= set(egr.columns)
    and columnas_exp <= set(exa.columns)
    and len(exa) == int((egr.situacion_laboral == "empleado").sum()),
)
chequear(
    "B3. TODO es ficticio y está marcado: fuente 'sintetico', nombres 'Egresado ficticio NNNN', sin correos",
    (egr.fuente == "sintetico").all()
    and egr.nombre.str.fullmatch(r"Egresado ficticio \d{4}").all()
    and egr.email.isna().all(),
)
chequear(
    "B4. los sectores y áreas son EXACTAMENTE las categorías oficiales del sistema",
    set(exa.sector) <= set(SECTORES) and set(exa.area_funcional) <= set(AREAS),
)
chequear(
    "B5. sector y área son coherentes (la docencia siempre es del sector Educación)",
    set(exa[exa.area_funcional == "Docencia e investigación"].sector) == {"Educación"},
)
chequear(
    "B6. las 21 promociones (2005 a 2025) tienen al menos 10 egresados: en la demo siempre se muestran cifras",
    egr.cohorte.nunique() == 21 and egr.cohorte.value_counts().min() >= co.MINIMO_GRUPO,
    egr.cohorte.value_counts().min(),
)
chequear(
    "B7. hay datos tanto declarados por el egresado como inferidos por IA (la demo muestra ambas etiquetas)",
    (egr.situacion_origen == "declarada_por_egresado").sum() > 0
    and set(exa.clasificacion_origen) == {"declarado", "inferido_ia"},
)
chequear(
    "B8. las promociones antiguas tienen más situación desconocida que las recientes (para que los gráficos cuenten algo)",
    (egr[egr.cohorte == "2005"].situacion_laboral == "desconocido").mean()
    > (egr[egr.cohorte == "2025"].situacion_laboral == "desconocido").mean(),
)
rep = dd.informe_de_ejemplo(egr, exa)
chequear(
    "B9. el informe de ejemplo pasa la verificación automática REAL (cifras respaldadas y citas válidas) y se declara ejemplo",
    rep["verificacion"]
    == {"citas_invalidas": [], "hallazgos_sin_cita": [], "cifras_sin_respaldo": []}
    and rep["es_ejemplo"] is True
    and rep["reporte"]["resumen_ejecutivo"].startswith("(Texto de ejemplo)"),
)
chequear(
    "B10. tiene la misma forma que un informe real (mismas claves)",
    {
        "indicadores",
        "reporte",
        "verificacion",
        "notas_metodologicas",
        "narrativa_markdown",
    }
    <= set(rep)
    and rep["indicadores"]["totales"]["egresados"] == 4000,
)
texto_pdf = "\n".join(
    p.extract_text() for p in PdfReader(io.BytesIO(generar_pdf(rep))).pages
)
chequear(
    "B11. el PDF del ejemplo dice la verdad: 'EJEMPLO' en el título y 'texto lo arma una plantilla' en el pie, y NO 'redactado con apoyo de IA'",
    "(EJEMPLO)" in texto_pdf
    and "plantilla, no la IA" in texto_pdf
    and "apoyo de IA" not in texto_pdf,
)
real = {k: v for k, v in rep.items() if k != "es_ejemplo"}
texto_real = "\n".join(
    p.extract_text() for p in PdfReader(io.BytesIO(generar_pdf(real))).pages
)
chequear(
    "B12. un informe real NO cambia: sigue diciendo 'Redactado con apoyo de IA' y sin 'EJEMPLO'",
    "apoyo de IA" in texto_real and "EJEMPLO" not in texto_real,
)
chequear(
    "B13. el PDF de ejemplo trae todos los gráficos (figuras de cohortes, ciudades, sectores, áreas y tecnologías)",
    all(f"Figura {i}" in texto_pdf for i in (1, 2, 3, 4, 5)),
)

# ===== C. las pantallas de la demostración =====
import requests as _requests
import supabase as _supabase
from streamlit.testing.v1 import AppTest


def _caido(*a, **k):
    raise RuntimeError("Supabase está pausado o no hay conexión (simulado)")


_supabase.create_client = _caido
_requests.post = _requests.get = (
    _caido  # la demo no debe llamar a NINGÚN servicio externo
)


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


def boton(at, clave):
    return [b for b in at.button if b.key == clave][0]


at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=120)
at.run()
chequear(
    "C1. la pantalla de acceso ofrece 'Explorar SIGMA con datos ficticios' y dice que no hace falta cuenta",
    any("Explorar SIGMA" in b.label for b in at.button)
    and "No necesitas cuenta" in texto_total(at),
    [b.label for b in at.button][:3],
)
boton(at, "entrar_demo").click()
at.run()
etiquetas = [t.label for t in at.tabs]
chequear(
    "C2. con SUPABASE CAÍDO y sin ningún servicio externo, la demo abre sin errores, con el aviso de datos ficticios y sus dos pestañas",
    not at.exception
    and "Modo demostración" in texto_total(at)
    and "Pruébalo como egresado" in etiquetas
    and "Lo que ve la Facultad" in etiquetas,
    (list(at.exception)[:1], etiquetas),
)
html = " ".join(m.value for m in at.markdown)
m = re.search(
    r"Egresados en esta vista</div><div class=\"valor\">([\d\.\,]+)</div>", html
)
chequear(
    "C3. el panel de la demo muestra los 4 000 egresados ficticios (vista histórica por defecto)",
    m and int(re.sub(r"\D", "", m.group(1))) == 4000,
    m.group(1) if m else None,
)
chequear(
    "C4. en la demo NO hay lo que necesita la base de datos: ni «Por revisar», ni «Datos a mostrar», ni «Actualizar datos»",
    not any("Por revisar" in e for e in etiquetas)
    and not any(r.label == "Datos a mostrar" for r in at.radio)
    and not any("Actualizar datos" in b.label for b in at.button),
)
chequear(
    "C5. el informe de la demo se presenta como EJEMPLO, con verificación en verde y las dos descargas (PDF y CSV)",
    "ejemplo con datos ficticios" in texto_total(at)
    and any("Verificación automática" in s.value for s in at.success)
    and any("PDF" in b.proto.label for b in at.get("download_button"))
    and any("CSV" in b.proto.label for b in at.get("download_button")),
    [b.proto.label for b in at.get("download_button")],
)
chequear(
    "C5b. la barra lateral aclara que el filtro de periodo solo afecta a «Lo que ve la Facultad» (no a la pestaña del egresado)",
    any(
        "solo afecta a «Lo que ve la Facultad»" in c_.value for c_ in at.sidebar.caption
    ),
)
chequear(
    "C6. la pestaña de privacidad también está en la demo",
    any(
        "Quién es el responsable" in mk.value
        for t in at.tabs
        if "Privacidad" in t.label
        for mk in t.markdown
    ),
)
sel = [s for s in at.selectbox if s.key == "demo_anio"][0]
sel.select("2015")
at.run()
boton(at, "demo_ver").click()
at.run()
tx = texto_total(at)
chequear(
    "C7. el visitante elige su año y ve 'Tu promoción 2015' con sus cifras agrupadas, sin errores",
    not at.exception
    and "Tu promoción 2015" in tx
    and any(mt.label == "Situación desconocida" for mt in at.metric),
    list(at.exception)[:1],
)
chequear(
    "C8. el mensaje de aporte es concreto y honesto: cuántos de la promoción siguen sin situación conocida, con las frases intactas",
    "**Tu aporte cuenta.** De los " in tx
    and re.search(
        r"De los \d+ egresados de tu promoción, \d+ todavía no tienen situación conocida\. Cada persona que responde completa un poco más la foto\. En el sistema real",
        tx,
    ),
    re.findall(r"De los \d+ egresados[^.]*\.", tx)[:1],
)
chequear(
    "C9. avisa que NO se guarda nada y que en el sistema real solo la ve la Facultad",
    "No se guarda nada" in tx and "solo la ve la Facultad" in tx,
)
boton(at, "salir_demo").click()
at.run()
chequear(
    "C10. 'Salir de la demostración' vuelve a la pantalla de acceso y apaga el modo demo",
    "modo_demo" not in at.session_state
    and any(b.key == "entrar_demo" for b in at.button)
    and not at.exception,
)

# Streamlit dibuja en pantalla cualquier expresión suelta («magia»): una condicional escrita como instrucción imprimiría un «None».
# AppTest no dibuja esa magia, así que esto se comprueba en el propio código.
import ast

_codigo = (RAIZ / "app.py").read_text(encoding="utf-8")
_arbol = ast.parse(_codigo)
_padres = {
    hijo: padre for padre in ast.walk(_arbol) for hijo in ast.iter_child_nodes(padre)
}


def _es_docstring(nodo):
    cuerpo = getattr(_padres.get(nodo), "body", None)
    return (
        isinstance(nodo.value, ast.Constant)
        and isinstance(nodo.value.value, str)
        and isinstance(cuerpo, list)
        and cuerpo[0] is nodo
    )


sueltas = [
    (nodo.lineno, ast.get_source_segment(_codigo, nodo)[:70])
    for nodo in ast.walk(_arbol)
    if isinstance(nodo, ast.Expr)
    and not isinstance(nodo.value, ast.Call)
    and not _es_docstring(nodo)
]
chequear(
    "C11b. app.py no tiene expresiones sueltas que Streamlit dibujaría en pantalla (como un 'None' verde bajo el informe)",
    not sueltas,
    sueltas,
)


# con sesión real, el modo demo no se mete en medio
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


class ClienteAdmin:
    auth = SimpleNamespace(get_session=lambda: object())

    def table(s, n):
        return Consulta([])


at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=120)
at.session_state["auth"] = {
    "cliente": ClienteAdmin(),
    "user_id": "u1",
    "email": "admin@ejemplo.com",
    "rol": "admin",
    "egresado_id": None,
}
at.session_state["modo_demo"] = True
at.run()
chequear(
    "C11. con una sesión real iniciada, la demostración NO se mete en medio: se ve el panel real de la administración",
    not at.exception
    and "Modo demostración" not in texto_total(at)
    and any("Por revisar" in t.label for t in at.tabs),
)

# ===== D. «Tu cohorte en cifras» en el portal real =====
RESPUESTAS = {}


class Llamada:
    def __init__(s, cli, n, p):
        s.cli, s.n, s.p = cli, n, p

    def execute(s):
        s.cli.llamadas.append(s.n)
        if (
            s.n == "guardar_mi_perfil"
        ):  # como la base de datos real: al guardar, la información queda como declarada por la persona
            s.cli.egresados[0]["situacion_origen"] = "declarada_por_egresado"
        r = RESPUESTAS.get(s.n)
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(data=r)


class ClienteEgresado:
    auth = SimpleNamespace(get_session=lambda: object())

    def __init__(s, declarada):
        s.llamadas = []
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
                "por_revisar": False,
                "situacion_origen": "declarada_por_egresado"
                if declarada
                else "institucional_historico",
            }
        ]

    def table(s, n):
        return Consulta(s.egresados if n == "egresados" else [])

    def rpc(s, n, p):
        return Llamada(s, n, p)


COHORTE_OK = {
    "suficiente": True,
    "cohorte": "2022",
    "n": 14,
    "minimo": 10,
    "celda_minima": 3,
    "empleados": 8,
    "desempleados": 1,
    "desconocidos": 4,
    "estudios_posteriores": 1,
    "tasa_sobre_total": 57.1,
    "tasa_sobre_conocidos": 88.9,
    "porcentaje_desconocido": 28.6,
    "con_ciudad": 11,
    "ciudades": {"Bucaramanga": 5, "Bogotá": 3},
    "sectores": {"Telecomunicaciones": 4},
    "tecnologias": {"Python": 5},
}


def portal(declarada=True):
    cli = ClienteEgresado(declarada)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=60)
    at.session_state["auth"] = {
        "cliente": cli,
        "user_id": "u1",
        "email": "ana@ejemplo.com",
        "rol": "egresado",
        "egresado_id": "e1",
    }
    at.run()
    return cli, at


RESPUESTAS["mi_cohorte_en_cifras"] = COHORTE_OK
cli, at = portal(declarada=False)
chequear(
    "D1. QUIEN AÚN NO GUARDÓ su información no puede ver las cifras: la sección explica 'primero compartes tu parte', sin botón y sin consultar nada",
    "Primero compartes tu parte; después ves la de todos" in texto_total(at)
    and not any(b.key == "ver_cohorte" for b in at.button)
    and "mi_cohorte_en_cifras" not in cli.llamadas
    and not at.exception,
)
cli, at = portal(declarada=True)
chequear(
    "D2. quien ya guardó ve 'Tu cohorte en cifras' con su botón, y NO se consulta nada hasta que lo pida",
    "Tu cohorte en cifras" in texto_total(at)
    and boton(at, "ver_cohorte")
    and "mi_cohorte_en_cifras" not in cli.llamadas
    and not at.exception,
)
boton(at, "ver_cohorte").click()
at.run()
chequear(
    "D3. al pedirla, llama a la función de la base de datos y muestra la promoción con sus cifras",
    "mi_cohorte_en_cifras" in cli.llamadas
    and "Tu promoción 2022: 14 egresados" in texto_total(at)
    and {m.label for m in at.metric}
    >= {
        "Empleo sobre el total",
        "Empleo sobre conocidos",
        "Situación desconocida",
        "Con ciudad registrada",
    },
    cli.llamadas,
)
chequear(
    "D4. las cifras se muestran bien: 57,1 % sobre el total y 11 de 14 con ciudad",
    {m.label: m.value for m in at.metric}.get("Empleo sobre el total") == "57,1 %"
    and {m.label: m.value for m in at.metric}.get("Con ciudad registrada")
    == "11 de 14",
)
RESPUESTAS["mi_cohorte_en_cifras"] = {
    "suficiente": False,
    "cohorte": "2022",
    "n": 4,
    "minimo": 10,
}
cli, at = portal()
boton(at, "ver_cohorte").click()
at.run()
chequear(
    "D5. si la promoción es pequeña, explica por qué no hay cifras (mínimo 10) y no muestra ninguna",
    "el mínimo es 10" in texto_total(at)
    and "Tu promoción 2022:" not in texto_total(at)
    and not any(m.label == "Situación desconocida" for m in at.metric),
)
RESPUESTAS["mi_cohorte_en_cifras"] = RuntimeError(
    "{'message': 'SIGMA: Tu cuenta todavía no está vinculada a un perfil de egresado.'}"
)
cli, at = portal()
boton(at, "ver_cohorte").click()
at.run()
chequear(
    "D6. si la base de datos responde con un error propio, se muestra solo el aviso claro y no revienta",
    not at.exception and any("todavía no está vinculada" in e.value for e in at.error),
    [e.value for e in at.error],
)
RESPUESTAS["mi_cohorte_en_cifras"] = COHORTE_OK
cli, at = portal(declarada=False)
at.radio[0].set_value("Estoy buscando empleo")
[c_ for c_ in at.checkbox if c_.key is None][0].set_value(True)
[b for b in at.button if b.label == "Guardar mi información"][0].click()
at.run()
chequear(
    "D7. AL GUARDAR su información, el candado se abre y se le muestra su promoción sin pulsar nada (la recompensa inmediata)",
    "guardar_mi_perfil" in cli.llamadas
    and "mi_cohorte_en_cifras" in cli.llamadas
    and "Tu promoción 2022: 14 egresados" in texto_total(at)
    and "Primero compartes tu parte" not in texto_total(at),
    cli.llamadas,
)

print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
