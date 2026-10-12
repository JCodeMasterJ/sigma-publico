"""
Servicio de agentes de IA. Corre por separado del dashboard de Streamlit.
Local:  uvicorn main:app --reload
"""

import hmac
import os
import tempfile
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client
from dotenv import load_dotenv

from agente_reportes import SinDatosError, generar_reporte
from proveedor_ia import extraer_datos_cv, sugerir_perfil_desde_texto

load_dotenv()

app = FastAPI(title="SIGMA - Agentes de IA")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def verificar_api_key(x_api_key: str = Header(default=None)):
    """
    Protege los endpoints que gastan cuota de IA o escriben datos.
    Si AGENTES_API_KEY no está definida en el entorno, el acceso queda abierto
    (útil solo en desarrollo local).
    """
    esperada = os.environ.get("AGENTES_API_KEY")
    if esperada and not hmac.compare_digest(x_api_key or "", esperada):
        raise HTTPException(status_code=401, detail="Clave de acceso inválida")


class ExtraerCVRequest(BaseModel):
    egresado_id: str
    cv_storage_path: str  # ej: "60241a41-926f-4650-a6a9-cc534b9fd8e3/prueba.pdf"


class SugerirPerfilRequest(BaseModel):
    texto: str = Field(
        min_length=100, max_length=20000
    )  # texto de un CV YA sin datos personales


class GenerarReporteRequest(BaseModel):
    fuente: Literal["real", "sintetico", "todos"] = "real"
    ventana: Literal["5_anios", "historico"] = "5_anios"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agentes/extraer-cv", dependencies=[Depends(verificar_api_key)])
def extraer_cv(payload: ExtraerCVRequest):
    # 1. Descargar el archivo desde Supabase Storage
    try:
        contenido = supabase.storage.from_("cvs").download(payload.cv_storage_path)
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"No se pudo descargar el archivo: {e}"
        )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contenido)
        tmp_path = tmp.name

    # 2. Llamar al agente de extracción
    try:
        datos = extraer_datos_cv(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al procesar con IA: {e}")
    finally:
        os.remove(tmp_path)

    # 3. Guardar la experiencia laboral extraída
    supabase.table("experiencia_laboral").insert(
        {
            "egresado_id": payload.egresado_id,
            "empresa": datos.empresa,
            "cargo": datos.cargo,
            "sector": datos.sector,
            "tecnologias": datos.tecnologias,
            "ubicacion": datos.ubicacion,
            "fuente": "real",
        }
    ).execute()

    # 4. Marcar el documento como procesado
    supabase.table("documentos_cv").update({"estado": "procesado"}).eq(
        "egresado_id", payload.egresado_id
    ).eq("url_storage", payload.cv_storage_path).execute()

    return {"status": "ok", "datos_extraidos": datos.model_dump()}


@app.post("/agentes/generar-reporte", dependencies=[Depends(verificar_api_key)])
def generar_reporte_endpoint(payload: GenerarReporteRequest):
    try:
        resultado = generar_reporte(supabase, payload.fuente, payload.ventana)
    except SinDatosError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al generar el reporte: {e}")

    # Guardar el reporte con los indicadores exactos que lo sustentan (trazabilidad).
    # Si guardar falla, igual devolvemos el reporte: es el producto principal.
    reporte_id, advertencia = None, None
    try:
        programa = supabase.table("programas").select("id").limit(1).execute()
        programa_id = programa.data[0]["id"] if programa.data else None
        guardado = (
            supabase.table("reportes_ia")
            .insert(
                {
                    "programa_id": programa_id,
                    "cohorte": "ultimos_5_anios"
                    if payload.ventana == "5_anios"
                    else "historico",
                    "narrativa": resultado["narrativa_markdown"],
                    "indicadores_usados": {
                        "indicadores": resultado["indicadores"],
                        "reporte": resultado["reporte"],
                        "verificacion": resultado["verificacion"],
                    },
                }
            )
            .execute()
        )
        reporte_id = guardado.data[0]["id"]
    except Exception as e:
        advertencia = (
            f"El reporte se generó pero no se pudo guardar en la base de datos: {e}"
        )

    return {
        "status": "ok",
        "reporte_id": reporte_id,
        "advertencia": advertencia,
        **resultado,
    }


@app.post("/agentes/sugerir-perfil", dependencies=[Depends(verificar_api_key)])
def sugerir_perfil(payload: SugerirPerfilRequest):
    """Recibe SOLO texto (el PDF nunca llega aquí ni se guarda) y devuelve datos para precargar el formulario."""
    try:
        return {"status": "ok", "sugerencia": sugerir_perfil_desde_texto(payload.texto)}
    except Exception as e:  # noqa: BLE001
        # no se devuelve el texto del CV ni detalles internos
        raise HTTPException(
            status_code=502,
            detail="El servicio de IA no pudo analizar el texto en este momento.",
        ) from e
