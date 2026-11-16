"""
Datos FICTICIOS para el modo demostración (stands y visitas).

Se generan en memoria, de forma determinista (la misma semilla da siempre los mismos datos): no usan la base de datos, así que la demo
funciona aunque Supabase esté pausado o no haya internet hacia él. No corresponden a ninguna persona real: los nombres son
«Egresado ficticio NNNN» a propósito, para que nadie pueda confundirlos con alguien de verdad.

Tienen las mismas columnas y categorías que los datos reales (sectores y áreas de taxonomia.py), para que el panel, los indicadores, el
informe y el PDF funcionen exactamente igual que con datos reales.
"""

import json
import random
from datetime import datetime, timedelta

import pandas as pd

from taxonomia import AREAS, SECTORES

N_DEMO = 4000
SEMILLA = 2026
COHORTES = list(range(2005, 2026))

CIUDADES = [
    ("Bucaramanga", 30),
    ("Bogotá", 20),
    ("Barrancabermeja", 5),
    ("Medellín", 7),
    ("Floridablanca", 4),
    ("Cúcuta", 4),
    ("Cali", 4),
    ("Barranquilla", 3),
    ("Piedecuesta", 2),
    ("Girón", 2),
    ("Cartagena", 2),
    ("Pereira", 2),
    ("Tunja", 1),
    ("Ciudad de México", 2),
    ("Madrid", 2),
    ("Lima", 1),
    ("Santiago de Chile", 1),
    ("Toronto", 1),
]

# área -> [(sector típico, peso)], para que sector y área sean coherentes entre sí
AREA_SECTOR = {
    "Redes y telecomunicaciones": [
        ("Telecomunicaciones", 8),
        ("Tecnología", 1),
        ("Energía", 1),
        ("Consultoría", 1),
    ],
    "Desarrollo de software": [
        ("Tecnología", 6),
        ("Financiero", 3),
        ("Consultoría", 2),
        ("Telecomunicaciones", 2),
        ("Salud", 1),
        ("Comercio", 1),
    ],
    "Soporte e infraestructura TI": [
        ("Tecnología", 4),
        ("Telecomunicaciones", 2),
        ("Financiero", 2),
        ("Salud", 1),
        ("Educación", 1),
        ("Gobierno", 1),
    ],
    "Datos y analítica": [
        ("Financiero", 3),
        ("Tecnología", 3),
        ("Comercio", 2),
        ("Salud", 1),
        ("Consultoría", 1),
    ],
    "Ciberseguridad": [
        ("Financiero", 3),
        ("Tecnología", 2),
        ("Gobierno", 1),
        ("Telecomunicaciones", 1),
    ],
    "Gestión de proyectos": [
        ("Consultoría", 3),
        ("Construcción", 2),
        ("Energía", 2),
        ("Telecomunicaciones", 2),
        ("Tecnología", 1),
    ],
    "Ventas y preventa técnica": [
        ("Tecnología", 3),
        ("Telecomunicaciones", 3),
        ("Comercio", 2),
    ],
    "Docencia e investigación": [("Educación", 8)],
    "Operaciones y campo": [
        ("Telecomunicaciones", 4),
        ("Energía", 3),
        ("Construcción", 2),
        ("Transporte y logística", 1),
        ("Manufactura", 1),
    ],
    "Administración y gestión": [
        ("Comercio", 2),
        ("Financiero", 2),
        ("Gobierno", 2),
        ("Manufactura", 1),
        ("Otro", 1),
    ],
    "Otra": [("Otro", 3), ("Comercio", 1)],
}
AREA_PESO = {
    "Redes y telecomunicaciones": 22,
    "Desarrollo de software": 20,
    "Soporte e infraestructura TI": 14,
    "Datos y analítica": 9,
    "Ciberseguridad": 5,
    "Gestión de proyectos": 8,
    "Ventas y preventa técnica": 5,
    "Docencia e investigación": 5,
    "Operaciones y campo": 7,
    "Administración y gestión": 3,
    "Otra": 2,
}
TECNOLOGIAS = {
    "Redes y telecomunicaciones": [
        "Cisco",
        "Huawei",
        "Fibra óptica",
        "5G",
        "LTE",
        "Linux",
        "Zabbix",
        "MPLS",
        "BGP",
        "Python",
    ],
    "Desarrollo de software": [
        "Python",
        "Java",
        "JavaScript",
        "SQL",
        "Docker",
        "Git",
        "AWS",
        "React",
        "Node.js",
        "Kubernetes",
    ],
    "Soporte e infraestructura TI": [
        "Windows Server",
        "Linux",
        "VMware",
        "Active Directory",
        "Azure",
        "Cisco",
        "Zabbix",
    ],
    "Datos y analítica": [
        "Python",
        "SQL",
        "Power BI",
        "Excel",
        "Pandas",
        "Tableau",
        "Spark",
    ],
    "Ciberseguridad": [
        "Linux",
        "Wireshark",
        "Fortinet",
        "Splunk",
        "Python",
        "Kali Linux",
    ],
    "Gestión de proyectos": ["Excel", "MS Project", "Jira", "Scrum", "Power BI"],
    "Ventas y preventa técnica": ["Cisco", "Huawei", "Excel", "CRM"],
    "Docencia e investigación": ["MATLAB", "Python", "LaTeX", "Linux", "Excel"],
    "Operaciones y campo": ["Fibra óptica", "OTDR", "Huawei", "AutoCAD", "Excel"],
    "Administración y gestión": ["Excel", "SAP", "Power BI"],
    "Otra": ["Excel"],
}
CARGOS = {
    "Redes y telecomunicaciones": [
        "Ingeniero de redes",
        "Ingeniera de transmisión",
        "Especialista NOC",
    ],
    "Desarrollo de software": [
        "Desarrollador backend",
        "Desarrolladora full stack",
        "Ingeniero de software",
    ],
    "Soporte e infraestructura TI": [
        "Analista de soporte",
        "Administrador de infraestructura",
    ],
    "Datos y analítica": ["Analista de datos", "Científica de datos"],
    "Ciberseguridad": ["Analista de seguridad", "Consultor de ciberseguridad"],
    "Gestión de proyectos": ["Coordinador de proyectos", "Gerente de proyecto"],
    "Ventas y preventa técnica": [
        "Ingeniero de preventa",
        "Ejecutivo técnico de cuentas",
    ],
    "Docencia e investigación": ["Docente universitario", "Investigadora"],
    "Operaciones y campo": ["Ingeniero de campo", "Supervisor de operaciones"],
    "Administración y gestión": ["Analista administrativo", "Jefe de área"],
    "Otra": ["Profesional independiente"],
}


def _eleccion(rng, pares):
    valores, pesos = zip(*pares)
    return rng.choices(valores, weights=pesos)[0]


def generar_datos_demo(n: int = N_DEMO, semilla: int = SEMILLA):
    """Devuelve (egresados, experiencia) como DataFrames, con las columnas que usa el panel."""
    rng = random.Random(semilla)
    ahora = datetime(2026, 10, 1)
    pesos_cohorte = [1 + (a - 2005) * 0.15 for a in COHORTES]
    egresados, experiencia = [], []
    for i in range(1, n + 1):
        anio = rng.choices(COHORTES, weights=pesos_cohorte)[0]
        p_desc = max(
            0.12, 0.46 - 0.018 * (anio - 2005)
        )  # las promociones antiguas tienen más situaciones desconocidas
        resto = 1 - p_desc
        situacion = rng.choices(
            ["empleado", "desempleado", "desconocido", "estudios_posteriores"],
            weights=[0.82 * resto, 0.06 * resto, p_desc, 0.12 * resto],
        )[0]
        declarada = situacion != "desconocido" and anio >= 2018 and rng.random() < 0.15
        egresados.append(
            {
                "id": f"demo-{i:05d}",
                "nombre": f"Egresado ficticio {i:04d}",
                "email": None,
                "cohorte": str(anio),
                "situacion_laboral": situacion,
                "fuente": "sintetico",
                "ciudad_residencia": _eleccion(rng, CIUDADES)
                if rng.random() < 0.55
                else None,
                "pais_residencia": None,
                "situacion_origen": "declarada_por_egresado"
                if declarada
                else "institucional_historico",
                "situacion_actualizada_en": (
                    ahora - timedelta(days=rng.randint(1, 180))
                ).isoformat()
                if declarada
                else None,
                "por_revisar": False,
                "fecha_registro": None,
            }
        )
        if situacion == "empleado":
            area = _eleccion(rng, list(AREA_PESO.items()))
            experiencia.append(
                {
                    "egresado_id": f"demo-{i:05d}",
                    "empresa": f"Empresa ficticia {rng.randint(1, 300)}",
                    "cargo": rng.choice(CARGOS[area]),
                    "sector": _eleccion(rng, AREA_SECTOR[area]),
                    "area_funcional": area,
                    "tecnologias": rng.sample(
                        TECNOLOGIAS[area],
                        rng.randint(1, min(4, len(TECNOLOGIAS[area]))),
                    ),
                    "tipo_empresa": _eleccion(
                        rng, [("Privada", 80), ("Publica", 15), ("Mixta", 5)]
                    ),
                    "clasificacion_origen": "declarado" if declarada else "inferido_ia",
                    "fecha_fin": None,
                }
            )
    return pd.DataFrame(egresados), pd.DataFrame(experiencia)


def _formato(v):
    return f"{v:.1f}".replace(".", ",")


def informe_de_ejemplo(egresados: pd.DataFrame, experiencia: pd.DataFrame) -> dict:
    """
    Informe con la MISMA forma que uno real (indicadores, verificación, notas, texto) pero con el texto armado por una plantilla a partir de
    los indicadores, sin IA: así la demo no depende de internet ni gasta cuota. La verificación automática es la de verdad.
    """
    import agente_reportes as ar  # importación tardía: solo se necesita en la demo

    cols_e = ar.COLS_EGRESADOS
    cols_x = ar.COLS_EXPERIENCIA
    ind = ar.calcular_indicadores(
        egresados.reindex(columns=cols_e),
        experiencia.reindex(columns=cols_x),
        "sintetico",
        "historico",
    )
    ind = json.loads(
        json.dumps(ind, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    )

    total, eg = ind["totales"]["egresados"], ind["empleabilidad_general"]
    cohortes = ind["empleabilidad_por_cohorte"]
    peor = max(cohortes.items(), key=lambda kv: kv[1]["porcentaje_desconocido"])
    ciudades = ind["ubicacion_top"]["ciudades"]
    ciudad = next(iter(ciudades))
    sectores = ind["sectores_top"]["sectores"]
    sector = next(iter(sectores))
    tecnologias = ind["tecnologias_top"].get("tecnologias") or {}

    hallazgos = [
        ar.Hallazgo(
            afirmacion=f"El {_formato(eg['tasa_sobre_total'])} % de los {total} egresados figura como empleado, y el {_formato(eg['tasa_sobre_conocidos'])} % si se "
            "cuenta solo a quienes tienen situación laboral conocida.",
            indicadores_citados=["empleabilidad_general"],
        ),
        ar.Hallazgo(
            afirmacion=f"La promoción {peor[0]} es la de mayor información faltante: el {_formato(peor[1]['porcentaje_desconocido'])} % de sus egresados tiene situación "
            "desconocida.",
            indicadores_citados=["empleabilidad_por_cohorte"],
        ),
        ar.Hallazgo(
            afirmacion=f"{ciudad} es la ciudad con más egresados registrados ({ciudades[ciudad]} de {ind['ubicacion_top']['egresados_con_ciudad']} con ciudad conocida).",
            indicadores_citados=["ubicacion_top"],
        ),
        ar.Hallazgo(
            afirmacion=f"{sector} es el sector con más egresados ({sectores[sector]} experiencias), clasificado por IA a partir de la empresa y el cargo.",
            indicadores_citados=["sectores_top"],
        ),
    ]
    if tecnologias:
        tec = next(iter(tecnologias))
        hallazgos.append(
            ar.Hallazgo(
                afirmacion=f"{tec} es la tecnología más mencionada ({tecnologias[tec]} menciones).",
                indicadores_citados=["tecnologias_top"],
            )
        )
    reporte = ar.ReporteAcreditacion(
        resumen_ejecutivo=(
            f"(Texto de ejemplo) Este informe usa datos ficticios de {total} egresados. El {_formato(eg['tasa_sobre_total'])} % figura como empleado y el "
            f"{_formato(eg['porcentaje_situacion_desconocida'])} % tiene situación desconocida, por lo que las cifras deben leerse con cautela."
        ),
        hallazgos=hallazgos,
        limitaciones_de_los_datos=[
            "Son datos ficticios creados para esta demostración: no describen a egresados reales.",
            f"El {_formato(eg['porcentaje_situacion_desconocida'])} % de los egresados tiene situación desconocida, que no equivale a desempleo.",
            "Sector y área aparecen como inferidos por IA y no como datos declarados por las personas.",
        ],
        recomendaciones=[
            "Invitar a los egresados a actualizar su perfil en el portal para reducir la situación desconocida.",
            "Revisar periódicamente los perfiles nuevos antes de incluirlos en los informes.",
        ],
    )
    notas = ar.notas_metodologicas(ind)
    return {
        "indicadores": ind,
        "reporte": reporte.model_dump(),
        "verificacion": ar.verificar_reporte(reporte, ind),
        "notas_metodologicas": notas,
        "narrativa_markdown": "> **Informe de ejemplo con datos ficticios.** El texto lo arma una plantilla, no la IA.\n\n"
        + ar.a_markdown(reporte, ind, notas),
        "advertencia": None,
        "es_ejemplo": True,
    }
