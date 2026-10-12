"""
Rellena egresados.ciudad_residencia:
- Reales: tomada del Excel limpio (independiente de si están empleados).
- Sintéticos: una ciudad aleatoria, igual de donde salieron sus trabajos sintéticos.
Correr UNA sola vez.
"""

import os
import random
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

CIUDADES_SINTETICAS = [
    "Bucaramanga",
    "Bogotá",
    "Medellín",
    "Cali",
    "Barranquilla",
    "Floridablanca",
]


def val(x):
    if (
        x is None
        or (isinstance(x, float) and pd.isna(x))
        or str(x).strip() in ("Falta", "")
    ):
        return None
    return x


def main():
    # 1. Reales: desde el Excel, emparejando por nombre exacto
    df = pd.read_excel(
        "Egresados_Telecomunicaciones_LIMPIO.xlsx", sheet_name="Egresados"
    )
    actualizados = 0
    for _, row in df.iterrows():
        ciudad = val(row["ciudad_residencia"])
        if ciudad:
            supabase.table("egresados").update({"ciudad_residencia": ciudad}).eq(
                "nombre", row["nombre_completo"]
            ).eq("fuente", "real").execute()
            actualizados += 1
    print(f"Reales actualizados con ciudad: {actualizados}")

    # 2. Sintéticos: los que todavía no tengan ciudad, les asignamos una al azar
    sinteticos_sin_ciudad = (
        supabase.table("egresados")
        .select("id")
        .eq("fuente", "sintetico")
        .is_("ciudad_residencia", "null")
        .execute()
    )
    for row in sinteticos_sin_ciudad.data:
        supabase.table("egresados").update(
            {"ciudad_residencia": random.choice(CIUDADES_SINTETICAS)}
        ).eq("id", row["id"]).execute()
    print(f"Sintéticos actualizados con ciudad: {len(sinteticos_sin_ciudad.data)}")

    print("\n✅ Listo.")


if __name__ == "__main__":
    main()
