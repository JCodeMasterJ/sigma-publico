"""
Genera egresados sintéticos (fuente='sintetico') para reforzar las cohortes
2021-2025, que tienen muy pocos egresados reales.
Correr UNA sola vez (si lo corres dos veces, duplica los sintéticos).
"""

import os
import random
import unicodedata
from datetime import date


def sin_tildes(s):
    return unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode()


from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

random.seed(42)  # reproducible: si lo corres de nuevo (tras borrar), genera lo mismo

TARGET_POR_COHORTE = 20
AÑOS = [2021, 2022, 2023, 2024, 2025]

NOMBRES = [
    "Juan",
    "Carlos",
    "Andrés",
    "Santiago",
    "Camilo",
    "Felipe",
    "David",
    "Daniel",
    "Sebastián",
    "Nicolás",
    "Miguel",
    "Alejandro",
    "Diego",
    "Cristian",
    "Julián",
    "Laura",
    "María",
    "Valentina",
    "Daniela",
    "Camila",
    "Natalia",
    "Paula",
    "Alejandra",
    "Carolina",
    "Juliana",
    "Sofía",
    "Mariana",
    "Luisa",
    "Andrea",
    "Gabriela",
]
APELLIDOS = [
    "Rodríguez",
    "González",
    "Martínez",
    "López",
    "Ramírez",
    "Pérez",
    "Sánchez",
    "Torres",
    "Díaz",
    "Vargas",
    "Castro",
    "Ruiz",
    "Álvarez",
    "Romero",
    "Suárez",
    "Rojas",
    "Moreno",
    "Muñoz",
    "Jiménez",
    "Gómez",
    "Herrera",
    "Medina",
    "Guerrero",
]
EMPRESAS = [
    "Claro Colombia",
    "Movistar Colombia",
    "Tigo UNE",
    "ETB",
    "Huawei Colombia",
    "Ericsson",
    "Nokia",
    "Globant",
    "Platzi",
    "Indra",
    "IBM Colombia",
    "Avantel",
    "EPM Telecomunicaciones",
    "Accenture",
    "Rappi",
    "Falabella Tech",
    "Bancolombia",
    "Grupo Bolívar",
    "Amazon Web Services",
    "Google Colombia",
]
CARGOS = [
    "Ingeniero de Redes",
    "Ingeniero de Telecomunicaciones",
    "Ingeniero de Soporte",
    "Desarrollador de Software",
    "Ingeniero de Infraestructura",
    "Analista de Datos",
    "Ingeniero DevOps",
    "Consultor de Redes",
    "Ingeniero de Ciberseguridad",
    "Ingeniero de Sistemas Embebidos",
    "Project Manager de Redes",
    "Ingeniero de Datos",
]
TECNOLOGIAS_POOL = [
    "Python",
    "Java",
    "SQL",
    "AWS",
    "Azure",
    "Linux",
    "Docker",
    "Kubernetes",
    "Redes 5G",
    "Fibra óptica",
    "Cisco",
    "MATLAB",
    "JavaScript",
    "React",
    "Node.js",
    "Machine Learning",
    "Ciberseguridad",
    "VoIP",
    "SDN",
    "IoT",
    "C++",
]
CIUDADES = [
    "Bucaramanga",
    "Bogotá",
    "Medellín",
    "Cali",
    "Barranquilla",
    "Floridablanca",
]
SECTORES = ["Telecomunicaciones", "Tecnología", "Financiero", "Energía", "Consultoría"]


def nombre_aleatorio():
    return f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"


def generar_egresado_sintetico(anio):
    situacion = random.choices(
        ["empleado", "desempleado", "desconocido"], weights=[80, 10, 10]
    )[0]
    nombre = nombre_aleatorio()
    mes = random.randint(1, 12)
    dia = random.randint(1, 28)
    return {
        "nombre": nombre,
        "email": f"{sin_tildes(nombre.lower()).replace(' ', '.')}.sintetico{random.randint(100, 999)}@ejemplo.com",
        "cohorte": str(anio),
        "fecha_grado": date(anio, mes, dia).isoformat(),
        "situacion_laboral": situacion,
        "fuente": "sintetico",
        "consentimiento_datos": True,  # persona ficticia, no aplica un consentimiento real
    }


def generar_experiencia_sintetica(egresado_id):
    return {
        "egresado_id": egresado_id,
        "empresa": random.choice(EMPRESAS),
        "cargo": random.choice(CARGOS),
        "sector": random.choice(SECTORES),
        "tecnologias": random.sample(TECNOLOGIAS_POOL, k=random.randint(3, 7)),
        "ubicacion": random.choice(CIUDADES),
        "fuente": "sintetico",
    }


def main():
    # Seguridad: no duplicar si ya se corrió antes
    existentes = (
        supabase.table("egresados")
        .select("id", count="exact")
        .eq("fuente", "sintetico")
        .execute()
    )
    if existentes.count and existentes.count > 0:
        print(
            f"Ya hay {existentes.count} egresados sintéticos. Cancelando para no duplicar."
        )
        print(
            "Si quieres regenerarlos, bórralos primero (fuente = 'sintetico') desde Supabase."
        )
        return

    # Contar cuántos reales hay ya por cohorte, para saber cuántos sintéticos faltan
    reales = (
        supabase.table("egresados").select("cohorte").eq("fuente", "real").execute()
    )
    conteo_real = {}
    for r in reales.data:
        c = r["cohorte"]
        if c:
            conteo_real[c] = conteo_real.get(c, 0) + 1

    print("Conteo real actual por cohorte (2021-2025):")
    for anio in AÑOS:
        print(f"  {anio}: {conteo_real.get(str(anio), 0)} reales")

    egresados_payload = []
    for anio in AÑOS:
        actuales = conteo_real.get(str(anio), 0)
        faltantes = max(0, TARGET_POR_COHORTE - actuales)
        print(f"  -> generando {faltantes} sintéticos para {anio}")
        for _ in range(faltantes):
            egresados_payload.append(generar_egresado_sintetico(anio))

    print(f"\nTotal de egresados sintéticos a crear: {len(egresados_payload)}")

    inserted = supabase.table("egresados").insert(egresados_payload).execute()
    print(f"{len(inserted.data)} egresados sintéticos insertados.")

    experiencia_payload = [
        generar_experiencia_sintetica(row["id"])
        for row, original in zip(inserted.data, egresados_payload)
        if original["situacion_laboral"] == "empleado"
    ]
    supabase.table("experiencia_laboral").insert(experiencia_payload).execute()
    print(
        f"{len(experiencia_payload)} filas de experiencia laboral sintética insertadas."
    )

    print("\n✅ Datos sintéticos generados.")


if __name__ == "__main__":
    main()
