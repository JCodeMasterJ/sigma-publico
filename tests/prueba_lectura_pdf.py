"""Pruebas de la lectura de PDF (cv_texto.py) con casos normales y hostiles."""

import io, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from fpdf import FPDF
from PIL import Image
from pypdf import PdfReader, PdfWriter
import cv_texto as c

resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:100]) if d else "")


def pdf_texto(lineas, paginas=1):
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    for _ in range(paginas):
        pdf.add_page()
        for l in lineas:
            pdf.multi_cell(0, 6, l, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


CV = [
    "JUAN PEREZ GOMEZ",
    "Ingeniero de Telecomunicaciones",
    "Direccion: Carrera 27 # 45-12, Bucaramanga",
    "Telefono: +57 300 123 4567",
    "Correo: juan.perez@ejemplo.com",
    "",
    "EXPERIENCIA",
    "Huawei Colombia | Ingeniero de Redes | 2022 - Actualidad",
    "Despliegue de EPC/IMS y redes 5G. Python, Ansible, Grafana, Cisco, AWS.",
    "Claro Colombia | Ingeniero de Soporte | 2019 - 2022",
    "Core de datos, MPLS, BGP, Linux, Docker.",
    "",
    "HABILIDADES",
    "Python, SQL, Docker, Linux, Kubernetes, Git, Zabbix",
]
normal = pdf_texto(CV)
pdf = FPDF()
pdf.add_page()
pdf.image(Image.new("RGB", (400, 300), "white"), x=10, y=10, w=180)
escaneado = bytes(pdf.output())  # solo imagen, sin texto
w = PdfWriter()
[w.add_page(pg) for pg in PdfReader(io.BytesIO(normal)).pages]
w.encrypt("secreta123")
b = io.BytesIO()
w.write(b)
protegido = b.getvalue()


def intentar(datos):
    try:
        return "ok", c.preparar_texto_cv(datos, "Juan Perez Gomez")
    except c.CVError as e:
        return "rechaza", str(e)


est, (texto, informe) = intentar(normal)
chequear("1. un CV normal se lee", est == "ok" and "Huawei" in texto)
chequear(
    "2. el texto que sale NO tiene datos personales y SÍ el contenido profesional",
    all(
        x.lower() not in texto.lower()
        for x in ("PEREZ", "300 123", "juan.perez", "Carrera 27")
    )
    and all(x in texto for x in ("Huawei", "Python", "MPLS", "Kubernetes")),
    texto[:60],
)
for nombre, datos, frase in [
    ("PDF escaneado (solo imagen)", escaneado, "imagen escaneada"),
    ("PDF con contraseña", protegido, "contraseña"),
    ("demasiadas páginas (15)", pdf_texto(CV, 15), "15 páginas"),
    ("archivo que no es PDF", b"PK\x03\x04 zip", "no parece un PDF"),
    ("archivo vacío", b"", "no parece un PDF"),
    ("PDF corrupto", b"%PDF-1.4\nbasura sin estructura", "No pudimos leer"),
    ("PDF de 6 MB", normal + b"0" * (6 * 1024 * 1024), "5 MB"),
]:
    est, msg = intentar(datos)
    chequear(
        f"3. {nombre}: se rechaza con un mensaje claro y sin romper",
        est == "rechaza" and frase in msg,
        msg,
    )


# --- el caso que reveló el CV real: cada página repite "Nombre + teléfono" como encabezado ---
class ConEncabezado(FPDF):
    def header(self):
        self.set_font("Helvetica", size=9)
        self.cell(
            0, 6, "Marta Lucia Ospina Duran 300 111 2222", new_x="LMARGIN", new_y="NEXT"
        )


cv2 = ConEncabezado()
cv2.set_font("Helvetica", size=11)
for pagina in (1, 2):
    cv2.add_page()
    cuerpo = (
        [
            "Marta Lucia Ospina Duran",
            "Bucaramanga, Colombia - 300 111 2222 - marta.ospina@ejemplo.com - linkedin.com/in/marta-ospina",
            "",
            "Experiencia",
            "Claro Colombia | Ingeniera de Redes | 2022 - Actualidad",
            "Despliegue de redes 5G con Python y Ansible. Trabajo de Marta Lucia Ospina en el area de core.",
        ]
        if pagina == 1
        else [
            "Habilidades",
            "Python, SQL, Docker, Linux, Kubernetes, Git, Zabbix, Wireshark, MATLAB, Grafana, Ansible, Cisco, 5G, MPLS, BGP",
        ]
    )
    for l in cuerpo:
        cv2.multi_cell(0, 6, l, new_x="LMARGIN", new_y="NEXT")
est, (texto2, inf2) = intentar(
    bytes(cv2.output())
)  # el registro tiene OTRO nombre (como una cuenta vinculada a un registro distinto)
est2, (texto2, inf2) = (
    "ok",
    c.preparar_texto_cv(bytes(cv2.output()), "Jhoan Jesus Vargas"),
)
restos = [
    x
    for x in (
        "Marta",
        "Lucia",
        "Ospina",
        "Duran",
        "300 111",
        "marta.ospina",
        "linkedin",
    )
    if x.lower() in texto2.lower()
]
chequear(
    "4. ENCABEZADO REPETIDO en cada página (nombre + teléfono): el nombre NO queda en ningún lado aunque el registro tenga otro nombre",
    not restos,
    restos,
)
chequear(
    "4. ...y se conserva el contenido profesional y la ciudad del encabezado",
    all(
        x in texto2
        for x in (
            "Claro Colombia",
            "Ingeniera de Redes",
            "Python",
            "Kubernetes",
            "Bucaramanga, Colombia",
        )
    ),
    texto2[:90],
)
print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
