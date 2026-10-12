"""
Prueba del vertical slice: sube un archivo de prueba a Supabase Storage
y crea el registro correspondiente en la tabla documentos_cv.
"""

import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
supabase = create_client(url, key)

LOCAL_FILE = "prueba.pdf"  # <- pon aquí el nombre de cualquier PDF que tengas a la mano, en la misma carpeta


def main():
    # 1. Tomamos un egresado cualquiera ya migrado, solo para asociar el archivo de prueba
    egresado = supabase.table("egresados").select("id, nombre").limit(1).execute()
    egresado_id = egresado.data[0]["id"]
    print(f"Usando egresado de prueba: {egresado.data[0]['nombre']}")

    # 2. Subir el archivo al bucket 'cvs'
    storage_path = f"{egresado_id}/prueba.pdf"
    with open(LOCAL_FILE, "rb") as f:
        supabase.storage.from_("cvs").upload(
            storage_path, f, {"content-type": "application/pdf", "upsert": "true"}
        )
    print(f"Archivo subido a: {storage_path}")

    # 3. Registrar el documento en la base de datos
    resultado = (
        supabase.table("documentos_cv")
        .insert(
            {
                "egresado_id": egresado_id,
                "url_storage": storage_path,
                "estado": "pendiente",
            }
        )
        .execute()
    )
    print("Registro creado en documentos_cv:", resultado.data[0]["id"])

    print(
        "\n✅ Vertical slice funcionando: archivo -> Storage -> registro en base de datos."
    )


if __name__ == "__main__":
    main()
