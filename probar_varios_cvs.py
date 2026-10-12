"""
Prueba el agente de extracción contra varios CVs a la vez.
Uso: pon 3-5 PDFs en una carpeta llamada 'cvs_prueba' (junto a este script) y corre:
    python probar_varios_cvs.py
No toca Supabase - solo imprime lo que el agente extrae de cada uno, para revisar
si funciona bien con distintos formatos de CV, no solo el tuyo.
"""

import os
import glob
from dotenv import load_dotenv
from proveedor_ia import extraer_datos_cv

load_dotenv()

CARPETA = "cvs_prueba"


def main():
    pdfs = glob.glob(os.path.join(CARPETA, "*.pdf"))
    if not pdfs:
        print(
            f"No encontré ningún PDF en la carpeta '{CARPETA}/'. Crea la carpeta y pon ahí los CVs de prueba."
        )
        return

    print(f"Encontrados {len(pdfs)} archivos. Procesando...\n")

    for ruta in pdfs:
        nombre = os.path.basename(ruta)
        print(f"{'=' * 60}\n{nombre}\n{'=' * 60}")
        try:
            datos = extraer_datos_cv(ruta)
            print(datos.model_dump_json(indent=2))
        except Exception as e:
            print(f"ERROR procesando este archivo: {e}")
        print()


if __name__ == "__main__":
    main()
