"""
Migra Egresados_Telecomunicaciones_LIMPIO.xlsx a las tablas de Supabase.
Correr UNA sola vez (si lo corres dos veces, duplica los 615 registros).
"""

import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

url = os.environ["SUPABASE_URL"]
key = os.environ[
    "SUPABASE_SERVICE_KEY"
]  # service_role: nos salta el RLS, solo para este script
supabase = create_client(url, key)

EXCEL_PATH = "Egresados_Telecomunicaciones_LIMPIO.xlsx"  # debe estar en la misma carpeta que este script


def val(x):
    """None si el valor es 'Falta', NaN o vacío; si no, el valor tal cual."""
    if (
        x is None
        or (isinstance(x, float) and pd.isna(x))
        or str(x).strip() in ("Falta", "")
    ):
        return None
    return x


def derivar_situacion(empresa):
    """Devuelve (situacion_laboral, empresa_para_guardar)."""
    if empresa and "DESEMPLE" in str(empresa).upper():
        return "desempleado", None
    if val(empresa):
        return "empleado", empresa
    return "desconocido", None


def si_no_a_bool(x):
    x = val(x)
    if x is None:
        return None
    return str(x).strip().lower() in ("sí", "si")


def main():
    df = pd.read_excel(EXCEL_PATH, sheet_name="Egresados")
    print(f"Leídas {len(df)} filas del Excel.")

    # Verificación de seguridad: si ya hay egresados cargados, no seguir (evita duplicar)
    existentes = supabase.table("egresados").select("id", count="exact").execute()
    if existentes.count and existentes.count > 0:
        print(
            f"Ya hay {existentes.count} egresados en la base de datos. Cancelando para no duplicar."
        )
        print(
            "Si de verdad quieres volver a cargar, borra la tabla 'egresados' primero desde Supabase."
        )
        return

    programa = (
        supabase.table("programas")
        .select("id")
        .eq("nombre", "Ingeniería de Telecomunicaciones")
        .execute()
    )
    programa_id = programa.data[0]["id"]

    egresados_rows = []
    experiencia_pendiente = []  # se arma después de insertar, cuando ya tenemos los ids

    for _, row in df.iterrows():
        situacion, empresa_limpia = derivar_situacion(row["empresa_actual"])
        fecha_grado = row["fecha_grado"]
        fecha_grado = fecha_grado.date().isoformat() if pd.notna(fecha_grado) else None
        cohorte = (
            str(int(row["fecha_grado"].year))
            if pd.notna(fecha_grado) and pd.notna(row["fecha_grado"])
            else None
        )

        egresados_rows.append(
            {
                "programa_id": programa_id,
                "nombre": row["nombre_completo"],
                "email": val(row["correo_personal"]),
                "cohorte": cohorte,
                "fecha_grado": fecha_grado,
                "situacion_laboral": situacion,
                "fuente": "real",
                "consentimiento_datos": False,  # dato institucional histórico, no consentimiento explícito nuevo
                "bio": val(row["descripcion_perfil"]),
                "especializacion_posterior": si_no_a_bool(
                    row["especializacion_posterior"]
                ),
                "maestria_posterior": si_no_a_bool(row["maestria_posterior"]),
                "doctorado_posterior": si_no_a_bool(row["doctorado_posterior"]),
                "titulos_posteriores": val(row["titulos_posteriores"]),
                "_empresa_actual": empresa_limpia,  # se usa abajo, no va a esta tabla
                "_cargo_actual": val(row["cargo_actual"]),
                "_ciudad": val(row["ciudad_residencia"]),
                "_tipo_empresa": val(row["tipo_empresa"]),
            }
        )

    # separar los campos que sí van a la tabla egresados de los auxiliares
    egresados_payload = [
        {k: v for k, v in r.items() if not k.startswith("_")} for r in egresados_rows
    ]

    print("Insertando egresados...")
    inserted = supabase.table("egresados").insert(egresados_payload).execute()
    print(f"{len(inserted.data)} egresados insertados.")

    # ahora que tenemos los ids reales (en el mismo orden en que se insertaron), armamos experiencia_laboral
    experiencia_payload = []
    for original, nuevo in zip(egresados_rows, inserted.data):
        if original["situacion_laboral"] == "empleado":
            experiencia_payload.append(
                {
                    "egresado_id": nuevo["id"],
                    "empresa": original["_empresa_actual"],
                    "cargo": original["_cargo_actual"],
                    "ubicacion": original["_ciudad"],
                    "tipo_empresa": original["_tipo_empresa"],
                    "fuente": "real",
                }
            )

    print(f"Insertando {len(experiencia_payload)} filas de experiencia laboral...")
    supabase.table("experiencia_laboral").insert(experiencia_payload).execute()

    print("\n✅ Migración completa.")
    print(f"   egresados: {len(inserted.data)}")
    print(f"   experiencia_laboral: {len(experiencia_payload)}")


if __name__ == "__main__":
    main()
