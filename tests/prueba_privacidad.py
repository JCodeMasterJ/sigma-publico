"""Pruebas de la limpieza de datos personales (privacidad.py)."""

import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import privacidad as p

resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:100]) if d else "")


CV = """JUAN PÉREZ GÓMEZ
Ingeniero de Telecomunicaciones
Dirección: Carrera 27 # 45-12, Barrio Cabecera, Bucaramanga
Teléfono: +57 300 123 4567
Correo: juan.perez.gomez@ejemplo.com
LinkedIn: linkedin.com/in/juanperezgomez
C.C. 1.098.765.432 de Bucaramanga
Fecha de nacimiento: 15/03/1998

PERFIL
Ingeniero con 4 años de experiencia en redes móviles. Juan trabaja con 5G, Python, Cisco y AWS. Contacto en https://github.com/jperez y @jperez_dev

EXPERIENCIA
Huawei Colombia | Ingeniero de Redes | 2022 - Actualidad
Despliegue de EPC/IMS en Bogotá. Python, Ansible, Grafana.
Jefe inmediato: María Rodríguez, cel 315 3899060
Claro Colombia | Ingeniero de Soporte | 2019 - 2022
Core de datos, MPLS, BGP.

EDUCACIÓN
Universidad Santo Tomás, Ingeniería de Telecomunicaciones, 2016 - 2021

REFERENCIAS PERSONALES
Carlos Martínez - Gerente - 320 555 1234
Ana Torres - Coordinadora - ana.torres@empresa.com

HABILIDADES
Python, SQL, Docker, Linux
"""
limpio, informe = p.anonimizar_con_informe(CV, "Juan Pérez Gómez")
prohibidos = [
    "Juan",
    "Pérez",
    "Gómez",
    "PÉREZ",
    "300 123",
    "juan.perez",
    "linkedin",
    "github",
    "@jperez",
    "1.098.765",
    "15/03/1998",
    "Carrera 27",
    "Cabecera",
    "María Rodríguez",
    "315 3899060",
    "Carlos Martínez",
    "ana.torres",
    "320 555",
    "Ana Torres",
]
requeridos = [
    "Huawei Colombia",
    "Ingeniero de Redes",
    "2022 - Actualidad",
    "EPC/IMS",
    "Python",
    "Ansible",
    "Claro Colombia",
    "MPLS",
    "BGP",
    "Universidad Santo Tomás",
    "2016 - 2021",
    "Docker",
    "Linux",
    "5G",
    "Cisco",
    "AWS",
]
chequear(
    "1. no queda ningún dato personal (nombre, dirección, teléfono, correo, cédula, redes, nacimiento, referencias)",
    not [x for x in prohibidos if x.lower() in limpio.lower()],
    [x for x in prohibidos if x.lower() in limpio.lower()],
)
chequear(
    "2. no se pierde nada del contenido profesional (empresas, cargos, fechas, tecnologías)",
    not [x for x in requeridos if x not in limpio],
    [x for x in requeridos if x not in limpio],
)
chequear(
    "3. el informe cuenta lo que se quitó",
    informe["lineas_personales"] >= 5
    and informe["referencias"] >= 2
    and informe["nombre"] >= 2
    and informe["enlaces"] >= 2,
    informe,
)
chequear(
    "4. entradas vacías no rompen nada",
    p.anonimizar("", "x") == "" and p.anonimizar(None, "x") == "",
)
chequear(
    "5. un rango de años ('2015 - 2020') NO se confunde con un teléfono",
    "2015 - 2020" in p.anonimizar("Trabajé 2015 - 2020 en Huawei", ""),
)
a = p.anonimizar("José Sebastián trabaja en Python", "Jose Sebastian")
chequear(
    "6. el nombre se quita con o sin tildes y se conserva el resto",
    "Jos" not in a and "Python" in a,
    a,
)
chequear(
    "7. sin datos de contacto el texto queda igual",
    p.anonimizar("Ingeniero con experiencia en 5G y redes.", "Juan Pérez")
    == "Ingeniero con experiencia en 5G y redes.",
)
chequear(
    "8. el resumen para la persona es legible",
    p.resumen_informe({}) == "no encontramos datos de contacto que quitar"
    and "teléfono" in p.resumen_informe({"telefonos": 1}),
)

# el nombre del encabezado puede NO coincidir con el del registro (segundo apellido, nombres de más)
l2 = p.anonimizar_con_informe(
    "ANA REAL GARCIA\nIngeniera de Telecomunicaciones\nExperiencia: Huawei, Python, Cisco\n",
    "Ana Real",
)[0]
chequear(
    "9. el nombre del CV se quita aunque no coincida con el registrado (segundo apellido)",
    "GARCIA" not in l2 and "Huawei" in l2 and "Ingeniera de Telecomunicaciones" in l2,
    l2,
)
l3 = p.anonimizar_con_informe(
    "CURRICULUM VITAE\nMaría Fernanda López Quintero\nEspecialista en Redes\nHuawei, Python",
    "Maria Lopez",
)[0]
chequear(
    "10. con 'CURRICULUM VITAE' arriba, igual detecta el nombre en la segunda línea",
    "Quintero" not in l3
    and "Fernanda" not in l3
    and "CURRICULUM VITAE" in l3
    and "Especialista en Redes" in l3,
    l3,
)
titulos = [
    "Ingeniero de Telecomunicaciones",
    "Especialista en Redes Móviles",
    "Python Developer",
    "Analista de Datos Senior",
    "Hoja de Vida",
]
chequear(
    "11. un título profesional en la primera línea NO se confunde con un nombre",
    all(
        p.anonimizar_con_informe(t + "\nHuawei Python 5G", "Pedro Gómez")[0].startswith(
            t
        )
        for t in titulos
    ),
)
frases = [
    "José Sebastián trabaja en Python",
    "Ingeniero con experiencia en Python y 5G",
    "Trabajó en Huawei con redes 5G",
]
chequear(
    "12. una FRASE con verbos no se borra por parecer un nombre",
    all(
        (
            "Python" in p.anonimizar_con_informe(f, "Jose Sebastian")[0]
            or "5G" in p.anonimizar_con_informe(f, "Jose Sebastian")[0]
        )
        for f in frases
    ),
)
chequear(
    "13. en prosa (biografías) la detección de encabezado está apagada",
    p.anonimizar("Pedro Gómez Ruiz\nTrabajó con 5G", "")
    == "Pedro Gómez Ruiz\nTrabajó con 5G",
)
l4 = p.anonimizar_con_informe(
    "Pedro Gómez Ruiz\nTrabajó en Ruiz Telecomunicaciones con 5G", "Pedro Gomez"
)[0]
chequear(
    "14. solo se reemplaza la línea del encabezado, no palabras sueltas del contenido",
    l4.startswith("[PERSONA]") and "Telecomunicaciones" in l4 and "5G" in l4,
    l4,
)

# el nombre aparece también en encabezados repetidos junto a un teléfono (cada página)
cv5 = "Camilo Andrés Rojas Mejía 311 555 0199\n1\nCamilo Andrés Rojas Mejía\nBucaramanga, Colombia - 311 555 0199\nExperiencia en Python\nCamilo Andrés Rojas Mejía 311 555 0199\nHabilidades: Cisco"
l5 = p.anonimizar_con_informe(cv5, "Otro Nombre Distinto")[0]
chequear(
    "15. un encabezado 'Nombre Apellido + teléfono' repetido en cada página no deja el nombre en ninguna parte",
    all(x not in l5 for x in ("Camilo", "Andrés", "Rojas", "Mejía", "311")),
    l5,
)
chequear(
    "16. ...pero conserva la ciudad del encabezado y el contenido",
    "Bucaramanga, Colombia" in l5 and "Python" in l5 and "Cisco" in l5,
)
l6 = p.anonimizar_con_informe(
    "Pedro Gómez Ruiz\nEmpresa Ruiz Hermanos SAS. Pedro dirige a Gómez Ruiz y a Ruiz.",
    "x",
)[0]
chequear(
    "17. solo se enmascaran el nombre completo y sus pares de palabras; un apellido suelto de una empresa se conserva",
    "Ruiz Hermanos" in l6 and "Gómez Ruiz" not in l6,
    l6,
)
print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
