"""
Limpia los datos de prueba (Pasos 26 y 29) que quedaron pegados por accidente
al registro real de "Jean Paul Junior Cervantes Lopez", al usar un egresado
cualquiera como conejillo de indias para probar Storage y el agente de IA.

Primero MUESTRA qué va a borrar. Solo borra si confirmas escribiendo 'si'.
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def main():
    # 1. Buscar la experiencia laboral de prueba (tu CV, mal atribuido)
    exp_prueba = (
        supabase.table("experiencia_laboral")
        .select("*, egresados(nombre)")
        .eq("empresa", "Akumaya Educación")
        .eq("fuente", "real")
        .execute()
    )

    # 2. Buscar los documentos de prueba (archivos llamados exactamente 'prueba.pdf')
    docs_prueba = (
        supabase.table("documentos_cv")
        .select("*, egresados(nombre)")
        .ilike("url_storage", "%prueba.pdf")
        .execute()
    )

    print("=== Esto se va a borrar ===\n")
    print(f"Experiencia laboral de prueba ({len(exp_prueba.data)} fila/s):")
    for row in exp_prueba.data:
        nombre = (
            row.get("egresados", {}).get("nombre", "?") if row.get("egresados") else "?"
        )
        print(f"  - {nombre}: {row['empresa']} / {row['cargo']}")

    print(f"\nDocumentos de prueba ({len(docs_prueba.data)} fila/s):")
    for row in docs_prueba.data:
        nombre = (
            row.get("egresados", {}).get("nombre", "?") if row.get("egresados") else "?"
        )
        print(f"  - {nombre}: {row['url_storage']}")

    if not exp_prueba.data and not docs_prueba.data:
        print("\nNo encontré nada que coincida. No se borra nada.")
        return

    respuesta = (
        input("\n¿Confirmas que esto es correcto y quieres borrarlo? (si/no): ")
        .strip()
        .lower()
    )
    if respuesta != "si":
        print("Cancelado, no se borró nada.")
        return

    for row in exp_prueba.data:
        supabase.table("experiencia_laboral").delete().eq("id", row["id"]).execute()
    for row in docs_prueba.data:
        supabase.table("documentos_cv").delete().eq("id", row["id"]).execute()

    print(
        f"\n✅ Borrados: {len(exp_prueba.data)} experiencia(s) laboral(es), {len(docs_prueba.data)} documento(s)."
    )
    print(
        "El registro real de Jean Paul Junior Cervantes Lopez queda solo con su dato original (Unidrogas)."
    )


if __name__ == "__main__":
    main()
