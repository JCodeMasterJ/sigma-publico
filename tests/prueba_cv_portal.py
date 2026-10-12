"""Pruebas de pantalla del análisis de CV en el portal del egresado (simula Supabase y el servicio de IA)."""

import os, re, sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.update(
    SUPABASE_URL="https://x.supabase.co",
    SUPABASE_ANON_KEY="dummy",
    AGENTES_URL="https://servicio.test",
    AGENTES_API_KEY="clave-de-prueba",
)

import requests as _requests
import streamlit as _st
from fpdf import FPDF
from PIL import Image
from streamlit.testing.v1 import AppTest

resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:120]) if d else "")


# ---------- PDF de prueba, con datos personales INVENTADOS ----------
def pdf_cv(lineas, imagen=False):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    if imagen:
        pdf.image(
            Image.new("RGB", (400, 300), "white"), x=10, y=10, w=180
        )  # imagen en memoria: sin archivos temporales
    else:
        for l in lineas:
            pdf.multi_cell(0, 6, l, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


CV = pdf_cv(
    [
        "ANA REAL GARCIA",
        "Ingeniera de Telecomunicaciones",
        "Direccion: Carrera 27 # 45-12, Barrio Cabecera, Bucaramanga",
        "Telefono: +57 300 123 4567",
        "Correo: ana.real.garcia@ejemplo.com",
        "C.C. 1.098.765.432 de Bucaramanga",
        "",
        "EXPERIENCIA",
        "Huawei Colombia | Ingeniera de Redes | 2022 - Actualidad",
        "Despliegue de EPC/IMS y redes 5G. Python, Ansible, Grafana, Cisco.",
        "Jefe inmediato: Maria Rodriguez, cel 315 3899060",
        "Claro Colombia | Ingeniera de Soporte | 2019 - 2022",
        "Core de datos, MPLS, BGP, Linux.",
        "",
        "EDUCACION",
        "Universidad Santo Tomas, Ingenieria de Telecomunicaciones, 2016 - 2021",
        "",
        "REFERENCIAS PERSONALES",
        "Carlos Martinez - Gerente - 320 555 1234",
        "Ana Torres - ana.torres@empresa.com",
        "",
        "HABILIDADES",
        "Python, SQL, Docker, Linux, Kubernetes",
    ]
)


# ---------- base de datos simulada ----------
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

    def execute(s):
        return SimpleNamespace(data=s.d)


class Llamada:
    def __init__(s, cli, n, p):
        s.cli, s.n, s.p = cli, n, p

    def execute(s):
        s.cli.llamadas.append((s.n, s.p))
        if s.n == "registrar_uso_cv":
            if s.cli.usos >= 5:
                raise Exception(
                    "{'message': 'SIGMA: Ya analizaste tu CV 5 veces hoy. Revisa los datos que te propusimos o llena el formulario a mano.'}"
                )
            s.cli.usos += 1
            return SimpleNamespace(data=4)
        return SimpleNamespace(data=None)


class Cliente:
    def __init__(s, exp_tecnologias=None):
        s.llamadas, s.usos = [], 0
        s.egresados = [
            {
                "nombre": "Ana Real",
                "cohorte": "2022",
                "situacion_laboral": "desconocido",
                "ciudad_residencia": None,
                "pais_residencia": None,
                "consentimiento_datos": False,
                "situacion_actualizada_en": None,
                "situacion_origen": "institucional_historico",
                "por_revisar": False,
            }
        ]
        s.exp = [
            {
                "empresa": None,
                "cargo": None,
                "sector": None,
                "area_funcional": None,
                "tecnologias": exp_tecnologias or [],
                "clasificacion_origen": None,
            }
        ]

    auth = SimpleNamespace(
        get_session=lambda: object()
    )  # la app comprueba que la sesión siga vigente

    def table(s, n):
        return Consulta(s.egresados if n == "egresados" else s.exp)

    def rpc(s, n, p):
        return Llamada(s, n, p)


# ---------- servicio de IA y cargador de archivos simulados ----------
class Subida:
    def __init__(s, d):
        s.d, s.name, s.size = d, "cv.pdf", len(d)

    def getvalue(s):
        return s.d

    def read(s):
        return s.d


UPLOAD = {"f": None}
_st.file_uploader = lambda *a, **k: UPLOAD["f"]
ENVIOS, RESP = [], {}


class _Resp:
    def __init__(s):
        s.status_code = RESP["codigo"]
        s.text = ""

    def json(s):
        return {"status": "ok", "sugerencia": RESP["sug"]}


def _post(url, json=None, headers=None, timeout=None):
    ENVIOS.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
    if RESP.get("error"):
        raise RESP["error"]
    return _Resp()


_requests.post = _post
SUG = {
    "empresa": "Huawei Colombia",
    "cargo": "Ingeniera de Redes",
    "ciudad": "Bogotá",
    "pais": None,
    "sector": "Telecomunicaciones",
    "area": "Redes y telecomunicaciones",
    "tecnologias": ["Python", "Ansible"],
    "otras_tecnologias": ["Cisco", "Docker", "Python"],
    "descartadas": 3,
}


def reiniciar(codigo=200, error=None, sug=None):
    ENVIOS.clear()
    RESP.update(codigo=codigo, error=error, sug=dict(sug or SUG))


def abrir(exp_tecnologias=None):
    cli = Cliente(exp_tecnologias)
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30)
    at.session_state["auth"] = {
        "cliente": cli,
        "user_id": "u1",
        "email": "ana@x.com",
        "rol": "egresado",
        "egresado_id": "e1",
    }
    at.run()
    return cli, at


def textos(at):
    return " ".join(
        str(x.value)
        for x in list(at.markdown)
        + list(at.caption)
        + list(at.success)
        + list(at.error)
        + list(at.info)
        + list(at.warning)
    )


def boton_cv(at):
    return [b for b in at.button if b.key == "cv_analizar_0"][0]


def campo(at, etiqueta):
    return [t for t in at.text_input if t.label == etiqueta][0]


def selector(at, etiqueta):
    return [s for s in at.selectbox if s.label == etiqueta][0]


def consent(at):
    return [c for c in at.checkbox if c.key is None][0]


def analizar(at, archivo=CV):
    UPLOAD["f"] = Subida(archivo)
    at.run()
    at.checkbox(key="cv_acepto_0").set_value(True)
    at.run()
    boton_cv(at).click()
    at.run()


# ===== 1. la opción y su bloqueo =====
reiniciar()
cli, at = abrir()
UPLOAD["f"] = None
at.run()
chequear(
    "1. el egresado ve la opción de CV con el aviso de privacidad",
    any("proponga los datos" in e.label for e in at.expander)
    and "no se guarda" in textos(at),
)
chequear("1. el botón está bloqueado sin archivo ni aceptación", boton_cv(at).disabled)
UPLOAD["f"] = Subida(CV)
at.run()
chequear("1. con archivo pero SIN aceptar, sigue bloqueado", boton_cv(at).disabled)
at.checkbox(key="cv_acepto_0").set_value(True)
at.run()
chequear("1. con archivo y aceptación se habilita", not boton_cv(at).disabled)

# ===== 2. lo que sale hacia la IA =====
reiniciar()
cli, at = abrir()
analizar(at)
chequear(
    "2. se llamó al servicio una vez, con clave y tiempo límite",
    len(ENVIOS) == 1
    and ENVIOS[0]["url"].endswith("/agentes/sugerir-perfil")
    and ENVIOS[0]["headers"]["x-api-key"] == "clave-de-prueba"
    and ENVIOS[0]["timeout"] == 120,
)
enviado = ENVIOS[0]["json"]["texto"] if ENVIOS else ""
prohibidos = [
    "ANA",
    "REAL",
    "GARCIA",
    "300 123",
    "ana.real",
    "ejemplo",
    "1.098.765",
    "Carrera 27",
    "Cabecera",
    "Maria Rodriguez",
    "315 3899060",
    "Carlos Martinez",
    "320 555",
    "ana.torres",
    "empresa.com",
]
fugas = [
    x
    for x in prohibidos
    if re.search(r"(?<!\w)" + re.escape(x) + r"(?!\w)", enviado, re.I)
]
chequear(
    "2. PRIVACIDAD: el texto enviado NO tiene nombre, correo, teléfono, dirección, cédula ni referencias",
    not fugas,
    fugas,
)
chequear(
    "2. y conserva el contenido profesional",
    all(
        x in enviado
        for x in [
            "Huawei Colombia",
            "Ingeniera de Redes",
            "2022 - Actualidad",
            "Python",
            "MPLS",
            "Kubernetes",
        ]
    ),
)
chequear(
    "2. solo se envía texto (no el PDF)", list(ENVIOS[0]["json"].keys()) == ["texto"]
)
chequear("2. se contó un uso", cli.usos == 1)

# ===== 3. formulario precargado =====
t_ = textos(at)
chequear(
    "3. empresa y cargo precargados",
    campo(at, "Empresa (si trabajas)").value == "Huawei Colombia"
    and campo(at, "Cargo").value == "Ingeniera de Redes",
)
chequear(
    "3. sector y área precargados",
    selector(at, "Sector de tu empresa").value == "Telecomunicaciones"
    and selector(at, "Área de tu trabajo").value == "Redes y telecomunicaciones",
)
chequear(
    "3. SOLO las tecnologías del cargo precargadas",
    campo(at, "Tecnologías que usas (separadas por comas)").value == "Python, Ansible",
)
ms = [m for m in at.multiselect if "Otras tecnologías" in m.label]
chequear(
    "3. el resto queda como opciones para marcar, sin repetir",
    ms and list(ms[0].options) == ["Cisco", "Docker"] and ms[0].value == [],
    ms[0].options if ms else None,
)
chequear("3. LA SITUACIÓN LABORAL NO SE RELLENA SOLA", at.radio[0].value is None)
chequear(
    "3. avisa qué se quitó y que el PDF no se guardó",
    "Antes de enviarlo a la IA quitamos" in t_ and "Tu PDF no se guardó" in t_,
)
chequear(
    "3. VERIFICACIÓN VISIBLE: dice cuántas sugerencias de la IA se descartaron por no estar en el CV",
    "descartamos 3 sugerencias de la IA que no aparecían en él" in t_,
    t_[-200:],
)
reiniciar(sug=dict(SUG, descartadas=1))
cli, at1 = abrir()
analizar(at1)
chequear(
    "3. en singular cuando es una ('1 sugerencia')",
    "descartamos 1 sugerencia de la IA" in textos(at1),
)
reiniciar(sug=dict(SUG, descartadas=0))
cli, at0 = abrir()
analizar(at0)
chequear(
    "3. y si no hubo nada que descartar lo dice ('todo aparece en él')",
    "todo aparece en él" in textos(at0),
)

# ===== 4. guardar =====
reiniciar()
cli, at = abrir()
analizar(at)
at.radio[0].set_value("Estoy empleado/a (o trabajo de forma independiente)")
[m for m in at.multiselect if "Otras tecnologías" in m.label][0].set_value(["Docker"])
consent(at).set_value(True)
[b for b in at.button if b.label == "Guardar mi información"][0].click()
at.run()
g = [p for n, p in cli.llamadas if n == "guardar_mi_perfil"]
chequear(
    "4. se guarda lo precargado MÁS lo marcado, sin repetir",
    g
    and g[0]["p_empresa"] == "Huawei Colombia"
    and g[0]["p_tecnologias"] == ["Python", "Ansible", "Docker"]
    and g[0]["p_situacion"] == "empleado",
    g[:1],
)
chequear(
    "4. tras guardar se borra lo propuesto y se reinicia el cargador",
    "sugerencia_cv" not in at.session_state
    and "texto_enviado_cv" not in at.session_state
    and at.session_state["cv_ronda"] == 1,
)

# ===== 5. errores: nunca bloquean el formulario manual =====
reiniciar()
cli, at = abrir()
analizar(at, archivo=pdf_cv([], imagen=True))
chequear(
    "5. PDF escaneado: aviso claro, sin llamar a la IA ni gastar un uso",
    any("imagen escaneada" in e.value for e in at.error)
    and not ENVIOS
    and cli.usos == 0,
)
reiniciar()
cli, at = abrir()
analizar(at, archivo=b"PK\x03\x04 no es un pdf")
chequear(
    "5. un archivo que no es PDF se rechaza sin llamar a la IA",
    any("no parece un PDF" in e.value for e in at.error) and not ENVIOS,
)
reiniciar()
cli, at = abrir()
cli.usos = 5
analizar(at)
chequear(
    "5. límite diario: aviso claro y no se llama a la IA",
    any("5 veces hoy" in e.value for e in at.error) and not ENVIOS,
)
reiniciar(codigo=502)
cli, at = abrir()
analizar(at)
chequear(
    "5. IA saturada: aviso claro, sin detalles técnicos",
    any("ocupado" in e.value and "a mano" in e.value for e in at.error),
)
at.radio[0].set_value("Estoy buscando empleo")
consent(at).set_value(True)
[b for b in at.button if b.label == "Guardar mi información"][0].click()
at.run()
chequear(
    "5. y el formulario manual SIGUE funcionando",
    any(
        n == "guardar_mi_perfil" and p["p_situacion"] == "desempleado"
        for n, p in cli.llamadas
    ),
)
reiniciar(error=_requests.exceptions.Timeout("t"))
cli, at = abrir()
analizar(at)
chequear(
    "5. tiempo agotado: aviso claro y sin excepción",
    not at.exception and any("tardó demasiado" in e.value for e in at.error),
)
reiniciar(codigo=401)
cli, at = abrir()
analizar(at)
chequear(
    "5. error 401: aviso genérico que no revela la configuración",
    any("No pudimos analizar tu CV" in e.value for e in at.error)
    and "401" not in textos(at),
)

# ===== 6. procedencia: qué había y qué trajo el CV =====
reiniciar()
cli, at = abrir(exp_tecnologias=["Cisco", "Linux"])
cli.egresados[0]["ciudad_residencia"] = "Cali"
analizar(at)
t6 = textos(at)
chequear(
    "6. las tecnologías ya registradas se conservan y se agregan las del cargo",
    campo(at, "Tecnologías que usas (separadas por comas)").value
    == "Cisco, Linux, Python, Ansible",
)
chequear(
    "6. LA PROCEDENCIA SE VE: 'Ya tenías registradas: Cisco, Linux. De tu CV agregamos: Python, Ansible.'",
    "Ya tenías registradas: Cisco, Linux. De tu CV agregamos: Python, Ansible." in t6,
    t6[-250:],
)
chequear(
    "6. las opciones no repiten lo que ya está en el campo (Cisco)",
    [m for m in at.multiselect if "Otras tecnologías" in m.label][0].options
    == ["Docker"],
)
chequear(
    "6. la ciudad del encabezado del CV se propone y se AVISA qué había antes",
    campo(at, "Ciudad donde vives").value == "Bogotá" and "Antes teníamos: Cali" in t6,
    campo(at, "Ciudad donde vives").value,
)
reiniciar(sug=dict(SUG, ciudad=None, pais=None))
cli, at = abrir()
cli.egresados[0]["ciudad_residencia"] = "Cali"
analizar(at)
chequear(
    "6. si el CV no trae ciudad, la registrada se conserva y no se muestra ningún aviso de cambio",
    campo(at, "Ciudad donde vives").value == "Cali"
    and "Antes teníamos" not in textos(at),
)
reiniciar()
cli, at = abrir()
analizar(at)
chequear(
    "6. sin nada registrado antes, no se muestra el aviso de 'ya tenías' (no hay nada que comparar)",
    "Ya tenías registradas" not in textos(at) and "Antes teníamos" not in textos(at),
)

# ===== 7. aislamiento =====
reiniciar()
cli, at = abrir()
analizar(at)
[b for b in at.button if b.label == "Cerrar sesión"][0].click()
at.run()
chequear(
    "7. cerrar sesión borra la sugerencia y el texto enviado",
    "texto_enviado_cv" not in at.session_state
    and "sugerencia_cv" not in at.session_state
    and "auth" not in at.session_state,
)

print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
