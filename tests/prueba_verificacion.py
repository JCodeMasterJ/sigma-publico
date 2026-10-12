import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import verificacion_cv as v

CV = """Experiencia
Akumaya Educación | Instructor de Programación | 2025 - Actualidad
Enseñanza de Python, Scratch y Minecraft a niños y jóvenes. Cursos de Machine Learning, Computer Vision y Desarrollo Web.
Telecom del Oriente | Practicante de Redes | 2023 - 2024
Configuración de enrutamiento y conmutación, TCP/IP y Subnetting con Cisco.
Educación
Universidad Santo Tomás, Ingeniería de Telecomunicaciones, 2020 - 2025
Certificaciones
CCNA, HCIA-Datacom, Microsoft Azure Fundamentals, Python Essentials 1
Proyectos
App móvil con Flutter, Dart y Firebase. Servidor con Node.js y Express. Control de versiones con Git y GitHub.
"""
resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:110]) if d else "")


sug = {
    "empresa": "Akumaya Educación",
    "cargo": "Instructor de Programación",
    "ciudad": None,
    "pais": None,
    "tecnologias": [
        "Java",
        "IoT",
        "AWS",
        "Docker",
        "VoIP",
        "Python",
        "Scratch",
        "Minecraft",
    ],
    "otras_tecnologias": ["Machine Learning", "Flutter", "CCNA", "Kubernetes"],
    "sector": "Educación",
    "area": "Docencia e investigación",
}
r = v.verificar_sugerencia(sug, CV)
print("\nprincipales:", r["tecnologias"])
print("opciones:   ", r["otras_tecnologias"])
print("descartadas:", r["descartadas"], "\n")
chequear(
    "1. las inventadas (VoIP, AWS, IoT, Docker, Java, Kubernetes) se DESCARTAN: no están en el CV",
    not any(
        x in r["tecnologias"] + r["otras_tecnologias"]
        for x in ["VoIP", "AWS", "IoT", "Docker", "Java", "Kubernetes"]
    ),
)
chequear(
    "2. se cuentan como descartadas (5 en principales + 1 en opciones = 6)",
    r["descartadas"] == 6,
    r["descartadas"],
)
chequear(
    "3. las del cargo actual quedan como PRINCIPALES: Python, Scratch, Minecraft",
    r["tecnologias"] == ["Python", "Scratch", "Minecraft"],
    r["tecnologias"],
)
chequear(
    "4. Machine Learning aparece en la descripción de ESE trabajo, pero el modelo la puso en 'otras': se conserva como opción",
    "Machine Learning" in r["otras_tecnologias"],
)

sug2 = dict(
    sug,
    tecnologias=["Python", "CCNA", "Flutter", "TCP/IP", "Scratch"],
    otras_tecnologias=[],
)
r2 = v.verificar_sugerencia(sug2, CV)
chequear(
    "5. certificaciones, proyectos y otro empleo (no son de ese trabajo) pasan de 'principales' a opciones, sin perderse",
    r2["tecnologias"] == ["Python", "Scratch"]
    and set(r2["otras_tecnologias"]) == {"CCNA", "Flutter", "TCP/IP"},
    (r2["tecnologias"], r2["otras_tecnologias"]),
)
chequear("6. y no se descarta nada: todo eso SÍ está en el CV", r2["descartadas"] == 0)

sug3 = {
    "empresa": "Ericsson Suecia",
    "cargo": "Director Regional",
    "ciudad": "Estocolmo",
    "pais": "Suecia",
    "tecnologias": ["Python"],
    "otras_tecnologias": [],
}
r3 = v.verificar_sugerencia(sug3, CV)
chequear(
    "7. empresa, cargo, ciudad y país que NO aparecen en el CV se descartan",
    all(r3[k] is None for k in ("empresa", "cargo", "ciudad", "pais"))
    and r3["descartadas"] == 4,
    r3["descartadas"],
)
sug4 = {
    "empresa": "Akumaya Educación",
    "cargo": "Instructor",
    "ciudad": None,
    "pais": None,
    "tecnologias": [],
    "otras_tecnologias": [],
}
chequear(
    "8. un cargo escrito más corto que en el CV ('Instructor') sí se acepta",
    v.verificar_sugerencia(sug4, CV)["cargo"] == "Instructor",
)

# una palabra INVENTADA dentro de algo que sí existe también se descarta (el caso que dejaba pasar la versión anterior)
rt = v.verificar_sugerencia(
    {
        "empresa": "Akumaya Tech Colombia",
        "cargo": "Instructor Senior de Programación",
        "ciudad": "Bucaramanga Metropolitana",
        "pais": None,
        "tecnologias": [],
        "otras_tecnologias": [],
    },
    CV + "\nBucaramanga, Colombia",
)
chequear(
    "8b. 'Akumaya Tech Colombia', 'Instructor Senior de Programación' y 'Bucaramanga Metropolitana' se descartan: llevan palabras que el CV no tiene",
    rt["empresa"] is None
    and rt["cargo"] is None
    and rt["ciudad"] is None
    and rt["descartadas"] == 3,
    rt,
)
rs = v.verificar_sugerencia(
    {
        "empresa": "Akumaya Educación S.A.S",
        "cargo": "Instructor de Programación",
        "ciudad": "Bucaramanga",
        "pais": "Colombia",
        "tecnologias": [],
        "otras_tecnologias": [],
    },
    CV + "\nBucaramanga, Colombia",
)
chequear(
    "8c. las palabras cortas o siglas ('S.A.S', 'de') no hacen descartar un dato correcto",
    rs["empresa"] == "Akumaya Educación S.A.S"
    and rs["cargo"] == "Instructor de Programación"
    and rs["ciudad"] == "Bucaramanga"
    and rs["descartadas"] == 0,
    rs,
)

casos = [
    ("Node.js/Express", True),
    ("NodeJS", True),
    ("node.js", True),
    ("Computer Vision", True),
    ("TCP/IP", True),
    ("Python Essentials 1", True),
    ("Microsoft Azure Fundamentals", True),
    ("HCIA-Datacom", True),
    ("GitHub", True),
    ("Ruby", False),
    ("VoIP", False),
    ("AWS", False),
    ("Kubernetes", False),
    ("", False),
]
idx = v.Indice(CV)
mal = [(t, esp) for t, esp in casos if idx.contiene(t) != esp]
chequear(
    "9. variantes de escritura (Node.js/NodeJS, mayúsculas, tildes, '/') se reconocen; lo ausente no",
    not mal,
    mal,
)
chequear(
    "10. 'Go' no coincide por accidente dentro de 'Google', y 'R' sí se reconoce como lenguaje",
    not v.Indice("Trabajo con Google y Python.").contiene("Go")
    and v.Indice("Lenguajes: R y Python").contiene("R"),
)

w = v.ventana_trabajo_reciente(CV, "Akumaya Educación", "Instructor de Programación")
chequear(
    "11. la ventana del trabajo reciente incluye su descripción y NO el siguiente empleo ni los estudios",
    "scratch" in w
    and "machine learning" in w
    and "telecom del oriente" not in w
    and "ccna" not in w,
    w[:80],
)
chequear(
    "12. si la empresa no se encuentra en el texto, no se inventa una ventana",
    v.ventana_trabajo_reciente(CV, "Empresa Inexistente", None) is None,
)
CV_SIN_FECHAS = "Trabajo actual en Huawei como Ingeniero. Usa Python, 5G y Ansible. Habilidades: Docker, Linux."
r5 = v.verificar_sugerencia(
    {
        "empresa": "Huawei",
        "cargo": "Ingeniero",
        "tecnologias": ["Python", "5G", "Docker"],
        "otras_tecnologias": [],
    },
    CV_SIN_FECHAS,
)
chequear(
    "13. un CV sin fechas ni estructura no rompe nada",
    r5["descartadas"] == 0 and "Python" in r5["tecnologias"],
    r5,
)

muchas = [f"Tec{i}" for i in range(40)]
r6 = v.verificar_sugerencia(
    {"empresa": "X", "cargo": None, "tecnologias": muchas, "otras_tecnologias": []},
    "X " + " ".join(muchas),
)
chequear(
    "14. máximo 10 principales y 30 opciones; el sobrante pasa a opciones",
    len(r6["tecnologias"]) == 10 and len(r6["otras_tecnologias"]) == 30,
    (len(r6["tecnologias"]), len(r6["otras_tecnologias"])),
)
chequear(
    "15. entradas vacías no rompen nada",
    v.verificar_sugerencia({}, "")["descartadas"] == 0,
)
print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
