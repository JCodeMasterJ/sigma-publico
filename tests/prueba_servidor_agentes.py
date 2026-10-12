"""Pruebas del endpoint /agentes/sugerir-perfil (servicio de agentes) con un 'modelo' simulado."""

import os, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ.update(
    AGENTES_API_KEY="clave",
    SUPABASE_URL="https://x.supabase.co",
    SUPABASE_SERVICE_KEY="dummy",
    GEMINI_API_KEY="dummy",
)
from fastapi.testclient import TestClient
import proveedor_ia as pi, main

resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:100]) if d else "")


c, H = TestClient(main.app), {"x-api-key": "clave"}
CV = (
    "Akumaya Educación | Instructor de Programación | 2025 - Actualidad\nEnseñanza de Python, Scratch y Minecraft a niños y jóvenes en Bucaramanga.\n"
    "Telecom del Oriente | Practicante | 2023 - 2024\nCisco y TCP/IP.\nCertificaciones\nCCNA, Azure Fundamentals\n"
)
chequear(
    "1. esquema sin $ref y con listas cerradas",
    "$ref" not in str(pi._schema_sin_refs(pi.PerfilSugerido))
    and "No determinado" in str(pi._schema_sin_refs(pi.PerfilSugerido)),
)
chequear(
    "2. el prompt exige que todo esté escrito en el texto",
    "REGLA ESTRICTA" in pi.PROMPT_PERFIL
    and "NUNCA agregues" in pi.PROMPT_PERFIL
    and "MÁXIMO 10" in pi.PROMPT_PERFIL,
)
chequear(
    "2b. el prompt pide ciudad y país de RESIDENCIA desde el encabezado, no la ciudad de una empresa",
    "VIVE" in pi.PROMPT_PERFIL
    and "encabezado" in pi.PROMPT_PERFIL
    and "NO uses la ciudad de una empresa" in pi.PROMPT_PERFIL,
)
chequear(
    "3. sin clave: 401",
    c.post("/agentes/sugerir-perfil", json={"texto": CV * 3}).status_code == 401,
)
chequear(
    "4. texto demasiado corto: 422",
    c.post("/agentes/sugerir-perfil", json={"texto": "corto"}, headers=H).status_code
    == 422,
)
chequear(
    "5. texto demasiado largo (más de 20 000 caracteres): 422",
    c.post(
        "/agentes/sugerir-perfil", json={"texto": "x" * 20001}, headers=H
    ).status_code
    == 422,
)


def modelo_que_inventa(
    prompt, esquema, reintentos=2, timeout=60.0
):  # el caso real que reportó el usuario
    return pi.PerfilSugerido(
        empresa="Akumaya Educación",
        cargo="Instructor de Programación",
        ciudad="Bucaramanga",
        pais="Colombia",
        sector="Educación",
        area_funcional="Docencia e investigación",
        tecnologias=[
            "Java",
            "IoT",
            "AWS",
            "Docker",
            "VoIP",
            "Python",
            "Scratch",
            "Minecraft",
        ],
        otras_tecnologias=["CCNA", "Kubernetes"],
    ), "modelo"


pi.generar_estructurado_robusto = modelo_que_inventa
r = c.post("/agentes/sugerir-perfil", json={"texto": CV}, headers=H)
s = r.json().get("sugerencia", {})
chequear(
    "6. con clave y texto válido responde 200", r.status_code == 200, r.status_code
)
chequear(
    "7. EL CASO REAL: las tecnologías que la IA inventó (Java, IoT, AWS, Docker, VoIP, Kubernetes) NO llegan a la persona",
    not any(
        x in s["tecnologias"] + s["otras_tecnologias"]
        for x in ["Java", "IoT", "AWS", "Docker", "VoIP", "Kubernetes"]
    ),
    s,
)
chequear(
    "8. quedan las del cargo (Python, Scratch, Minecraft) y la certificación escrita (CCNA) como opción",
    s["tecnologias"] == ["Python", "Scratch", "Minecraft"]
    and s["otras_tecnologias"] == ["CCNA"],
    s,
)
chequear(
    "9. un país que no está escrito en el CV ('Colombia') se descarta; la ciudad escrita se conserva",
    s["pais"] is None and s["ciudad"] == "Bucaramanga",
)
chequear(
    "10. se informa cuántas propuestas se descartaron (6 tecnologías + el país = 7)",
    s["descartadas"] == 7,
    s["descartadas"],
)


def falla(prompt, esquema, reintentos=2, timeout=60.0):
    raise RuntimeError("503 high demand TEXTO_SECRETO_DEL_CV")


pi.generar_estructurado_robusto = falla
r = c.post("/agentes/sugerir-perfil", json={"texto": "CONFIDENCIAL " * 20}, headers=H)
chequear(
    "11. si la IA falla: 502 con aviso genérico, SIN filtrar el texto del CV ni detalles internos",
    r.status_code == 502
    and "CONFIDENCIAL" not in r.text
    and "503" not in r.text
    and "SECRETO" not in r.text,
    r.text,
)
d = pi.sugerencia_a_dict(
    pi.PerfilSugerido(
        empresa="  Huawei  ",
        cargo="x" * 300,
        sector="No determinado",
        area_funcional="Redes y telecomunicaciones",
        tecnologias=["Python", " python ", "5G", "", "T" * 41],
    )
)
chequear(
    "12. sin texto de referencia solo normaliza: recorta largos, quita repetidas y vacías, 'No determinado' queda vacío",
    d["empresa"] == "Huawei"
    and len(d["cargo"]) == 120
    and d["sector"] is None
    and d["tecnologias"] == ["Python", "5G"],
    d,
)
print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
