"""
Listas cerradas para clasificar sector y área de desempeño.
Una sola definición para todo el sistema (clasificador, agentes, dashboard, reportes).

Los cinco primeros sectores coinciden con los que ya usan los datos sintéticos,
para que los gráficos no se dividan en etiquetas distintas.
"""

SECTORES = [
    "Telecomunicaciones",
    "Tecnología",
    "Financiero",
    "Energía",
    "Consultoría",
    "Educación",
    "Gobierno",
    "Salud",
    "Manufactura",
    "Comercio",
    "Construcción",
    "Transporte y logística",
    "Otro",  # sector identificado, pero que no está en la lista
]
SECTOR_NO_DETERMINADO = "No determinado"  # no se pudo saber

AREAS = [
    "Redes y telecomunicaciones",
    "Desarrollo de software",
    "Soporte e infraestructura TI",
    "Datos y analítica",
    "Ciberseguridad",
    "Gestión de proyectos",
    "Ventas y preventa técnica",
    "Docencia e investigación",
    "Operaciones y campo",
    "Administración y gestión",
    "Otra",
]
AREA_NO_DETERMINADA = "No determinada"

ORIGEN_INFERIDO = "inferido_ia"  # clasificado por IA a partir de empresa y cargo
ORIGEN_EXTRAIDO = "extraido_cv"  # leído de un CV o biografía escrita por la persona

CONFIANZAS = ["alta", "media", "baja"]
