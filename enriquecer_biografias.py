"""
Lee las biografías profesionales de egresados REALES con el Agente 1 y extrae sus TECNOLOGÍAS.
Es un dato declarado en un texto que escribió la propia persona (no una inferencia).

PRIVACIDAD: el plan gratuito de Gemini puede usar lo que se le envía para mejorar productos de Google,
y sus términos piden no enviar información personal. Por eso:
  - antes de enviar se quitan correos, teléfonos, enlaces y el nombre de la persona;
  - el script muestra un ejemplo de lo que enviará y pide confirmación explícita;
  - se envía UNA sola vez: el resultado queda en un archivo y el paso de guardar no vuelve a enviar nada.

Dos pasos:
  1) python enriquecer_biografias.py            -> (con confirmación) envía y guarda biografias_resultados.json.
                                                  NO escribe en la base de datos.
  2) python enriquecer_biografias.py --guardar  -> escribe las tecnologías en la base de datos.
"""

import json
import os
import re
import sys
import unicodedata
from collections import Counter

ARCHIVO = "biografias_resultados.json"

from privacidad import anonimizar  # noqa: E402,F401  (la limpieza de datos personales vive en un módulo compartido)


def fetch_all(supabase, tabla, columnas, filtro=None, page=1000):
    filas, inicio = [], 0
    while True:
        q = supabase.table(tabla).select(columnas)
        if filtro:
            q = q.eq(*filtro)
        r = q.range(inicio, inicio + page - 1).execute()
        filas.extend(r.data)
        if len(r.data) < page:
            return filas
        inicio += page


def limpiar_tecnologias(lista) -> list:
    vistas, salida = set(), []
    for t in lista or []:
        t = str(t).strip()
        if t and t.lower() not in vistas:
            vistas.add(t.lower())
            salida.append(t)
    return salida


def paso_enviar(supabase, extraer=None, preguntar=input):
    if extraer is None:
        from proveedor_ia import extraer_datos_texto as extraer
    egresados = [
        e
        for e in fetch_all(
            supabase, "egresados", "id,nombre,bio,fuente", ("fuente", "real")
        )
        if e.get("bio") and str(e["bio"]).strip()
    ]
    if not egresados:
        print("No hay biografías de egresados reales en la base de datos.")
        return
    primera = anonimizar(egresados[0]["bio"], egresados[0]["nombre"])
    print(
        f"Se enviarían {len(egresados)} biografías, ya anonimizadas (sin correos, teléfonos, enlaces ni el nombre de la persona)."
    )
    print("Ejemplo de lo que se enviaría (primeros 250 caracteres de la primera):\n")
    print("   ", primera[:250].replace("\n", " "), "...\n")
    print(
        "AVISO: es el plan GRATUITO de Gemini; según sus términos, Google puede usar lo que se envía para mejorar sus"
    )
    print(
        "productos y revisores humanos podrían leerlo. Si no estás seguro de que estas biografías sean de uso público"
    )
    print(
        "(por ejemplo, textos que la facultad ya publica), consúltalo antes de continuar.\n"
    )
    if (
        preguntar("¿Enviar estas biografías anonimizadas a Gemini? (si/no): ")
        .strip()
        .lower()
        != "si"
    ):
        print("Cancelado. No se envió nada.")
        return

    resultados, errores = {}, 0
    for i, e in enumerate(egresados, start=1):
        try:
            datos = extraer(anonimizar(e["bio"], e["nombre"]))
            resultados[e["id"]] = {
                "tecnologias": limpiar_tecnologias(datos.tecnologias)
            }
        except Exception as ex:  # noqa: BLE001
            errores += 1
            print(f"  [{i}] error: {str(ex)[:120]}")
            continue
        t = resultados[e["id"]]["tecnologias"]
        print(
            f"  [{i}/{len(egresados)}] {len(t)} tecnologías: {', '.join(t[:5])}{'...' if len(t) > 5 else ''}"
        )

    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=1)
    todas = Counter(t for r in resultados.values() for t in r["tecnologias"])
    con = sum(1 for r in resultados.values() if r["tecnologias"])
    print(
        f"\nProcesadas {len(resultados)} (errores: {errores}); {con} con al menos una tecnología; {len(todas)} tecnologías distintas."
    )
    print("Más frecuentes:", dict(todas.most_common(8)))
    print(
        f"\nNo se escribió nada en la base de datos. Cuando estés conforme: python enriquecer_biografias.py --guardar"
    )


def paso_guardar(supabase):
    if not os.path.exists(ARCHIVO):
        print(f"No existe {ARCHIVO}. Primero corre el paso de envío (sin --guardar).")
        return
    with open(ARCHIVO, encoding="utf-8") as f:
        resultados = json.load(f)
    filas = fetch_all(
        supabase,
        "experiencia_laboral",
        "id,egresado_id,tecnologias,fuente",
        ("fuente", "real"),
    )
    por_egresado = {}
    for fila in filas:
        por_egresado.setdefault(fila["egresado_id"], []).append(fila)

    guardadas = sin_experiencia = ya_tenia = 0
    for egresado_id, r in resultados.items():
        if not r["tecnologias"]:
            continue
        candidatas = por_egresado.get(egresado_id, [])
        if not candidatas:
            sin_experiencia += (
                1  # tiene biografía pero no hay una experiencia laboral donde guardarlo
            )
            continue
        destino = next((c for c in candidatas if not c.get("tecnologias")), None)
        if destino is None:
            ya_tenia += 1  # idempotente: no se sobrescribe lo ya cargado
            continue
        supabase.table("experiencia_laboral").update(
            {"tecnologias": r["tecnologias"]}
        ).eq("id", destino["id"]).execute()
        guardadas += 1
    print(f"Guardadas tecnologías en {guardadas} experiencias.")
    print(
        f"  Sin experiencia laboral donde guardarlas: {sin_experiencia} | ya tenían tecnologías: {ya_tenia}"
    )


def main(argv=None, supabase=None, extraer=None, preguntar=input):
    argv = sys.argv[1:] if argv is None else argv
    if supabase is None:
        from dotenv import load_dotenv
        from supabase import create_client

        load_dotenv()
        supabase = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
        )
    if "--guardar" in argv:
        paso_guardar(supabase)
    else:
        paso_enviar(supabase, extraer, preguntar)


if __name__ == "__main__":
    main()
