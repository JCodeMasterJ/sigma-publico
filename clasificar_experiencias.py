"""
Clasifica el SECTOR de la empresa y el ÁREA DE DESEMPEÑO del cargo de egresados REALES,
usando IA. Es una inferencia, no un dato que alguien declaró: queda marcada como 'inferido_ia'.

Dos pasos, a propósito:
  1) python clasificar_experiencias.py            -> PRUEBA. Llama a la IA, NO escribe en la base de datos.
                                                    Guarda clasificacion_resultados.json y revision_clasificacion.csv
                                                    (una muestra de 30 para que revises si está bien).
     (si se interrumpe o falla, vuelve a correr el mismo comando: continúa donde quedó;
      con --grande prueba primero el modelo grande, que conoce mejor las empresas pero tiene solo 20 peticiones/día)
  2) python clasificar_experiencias.py --guardar  -> Escribe en la base de datos exactamente lo que revisaste
                                                    (lee el archivo del paso 1; no vuelve a llamar a la IA).
     Con --guardar --solo-alta solo se guarda lo clasificado con confianza ALTA (lo "media" queda sin clasificar).

Privacidad: solo se envían nombre de empresa y cargo. Nunca nombres de personas.
"""

import csv
import json
import os
import random
import re
import sys
import time
import unicodedata
from collections import Counter
from typing import List, Literal

from pydantic import BaseModel

from proveedor_ia import MODELO, generar_estructurado_robusto
from taxonomia import (
    AREA_NO_DETERMINADA,
    AREAS,
    ORIGEN_INFERIDO,
    SECTOR_NO_DETERMINADO,
    SECTORES,
)

ARCHIVO_RESULTADOS = "clasificacion_resultados.json"
ARCHIVO_REVISION = "revision_clasificacion.csv"
ARCHIVO_PARCIAL = "clasificacion_parcial.json"  # avance guardado después de cada lote
TAMANO_LOTE = 25
MODELOS = [MODELO]  # por defecto el liviano: rápido y con 500 peticiones/día gratis
MODELOS_GRANDE = [
    "gemini-3.8-flash",
    MODELO,
]  # con --grande: prueba primero el grande (20/día), con respaldo
EMPRESAS_NO_EMPLEADORAS = {"estudiante"}  # no son un empleo: no se clasifican


# ---------------------------------------------------------------------------
# Lo que la IA debe devolver
# ---------------------------------------------------------------------------
class ItemClasificado(BaseModel):
    id: int
    sector: Literal[tuple(SECTORES + [SECTOR_NO_DETERMINADO])]
    area_funcional: Literal[tuple(AREAS + [AREA_NO_DETERMINADA])]
    confianza_sector: Literal["alta", "media", "baja"]
    confianza_area: Literal["alta", "media", "baja"]


class LoteClasificado(BaseModel):
    items: List[ItemClasificado]


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ASCII", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def construir_prompt(lote: list) -> str:
    lineas = "\n".join(
        f'[id {p["id"]}] empresa: "{p["empresa"]}" | cargo: "{p["cargo"] or "(sin cargo)"}"'
        for p in lote
    )
    return f"""Clasifica cada par (empresa, cargo) de egresados de Ingeniería de Telecomunicaciones de Colombia.

CAMPOS:
- sector: sector económico de la EMPRESA. Elige exactamente uno de: {", ".join(SECTORES)}, {SECTOR_NO_DETERMINADO}.
- area_funcional: función que cumple el CARGO (no la empresa). Elige exactamente uno de: {", ".join(AREAS)}, {AREA_NO_DETERMINADA}.
- confianza_sector: "alta" si conoces la empresa o su nombre es inequívoco; "media" si es una inferencia razonable; "baja" si es solo un intento.
- confianza_area: "alta" si el cargo indica claramente la función; "media" si es razonable; "baja" si el cargo es ambiguo o falta.
  (Son dos juicios independientes: puedes desconocer la empresa y aun así tener un cargo muy claro.)

REGLAS:
R1. No adivines. Si no conoces la empresa y su nombre no deja claro el sector, usa "{SECTOR_NO_DETERMINADO}" con confianza_sector "baja". Es mejor no clasificar que clasificar mal.
R2. "Independiente" o "Freelance" no son una empresa: sector "{SECTOR_NO_DETERMINADO}"; clasifica el área solo por el cargo.
R3. Universidades, institutos, SENA y colegios son "Educación". Alcaldías, ministerios, gobernaciones y entidades estatales son "Gobierno".
R4. El área se decide por lo que dice el cargo, aunque no conozcas la empresa; si el cargo no está o es ambiguo, usa "{AREA_NO_DETERMINADA}" con confianza_area "baja".
R5. Devuelve un elemento por cada id recibido, con el mismo id.

PARES A CLASIFICAR:
{lineas}"""


def aplicar_reglas(item: dict) -> dict:
    """Reglas que NO dependen de que la IA las cumpla: confianza baja => no determinado, campo por campo."""
    item = dict(item)
    if item["confianza_sector"] == "baja":
        item["sector"] = SECTOR_NO_DETERMINADO
    if item["confianza_area"] == "baja":
        item["area_funcional"] = AREA_NO_DETERMINADA
    return item


# ---------------------------------------------------------------------------
# Paso 1: clasificar pares únicos (empresa, cargo)
# ---------------------------------------------------------------------------
def fetch_all(supabase, tabla, columnas, page=1000):
    filas, inicio = [], 0
    while True:
        r = (
            supabase.table(tabla)
            .select(columnas)
            .range(inicio, inicio + page - 1)
            .execute()
        )
        filas.extend(r.data)
        if len(r.data) < page:
            return filas
        inicio += page


def filas_pendientes(supabase) -> list:
    """Experiencias reales con empresa, sin sector declarado y aún sin clasificar por IA."""
    filas = fetch_all(
        supabase,
        "experiencia_laboral",
        "id,empresa,cargo,sector,fuente,clasificacion_origen",
    )
    return [
        f
        for f in filas
        if f.get("fuente") == "real"
        and f.get("empresa")
        and not f.get("sector")
        and not f.get("clasificacion_origen")
        and _norm(f["empresa"]) not in EMPRESAS_NO_EMPLEADORAS
    ]


def pares_unicos(filas: list) -> list:
    vistos = {}
    for f in filas:
        clave = (_norm(f["empresa"]), _norm(f.get("cargo")))
        if clave not in vistos:
            vistos[clave] = {
                "id": len(vistos) + 1,
                "empresa": f["empresa"].strip(),
                "cargo": (f.get("cargo") or "").strip(),
                "clave": list(clave),
            }
    return list(vistos.values())


def clasificar_pares(
    pares: list,
    generar=generar_estructurado_robusto,
    modelos=None,
    previos=None,
    al_terminar_lote=None,
) -> dict:
    """Devuelve {'resultados': {id: item}, 'modelos_usados': [...], 'sin_respuesta': [ids]}.
    `previos` son resultados ya obtenidos (para retomar); `al_terminar_lote` guarda el avance."""
    modelos = modelos or MODELOS
    estado = {}  # recuerda qué modelos se descartaron (sin cuota o colgados) durante toda la ejecución
    resultados = dict(previos or {})
    modelos_usados = set()
    total_lotes = -(-len(pares) // TAMANO_LOTE)
    for i in range(0, len(pares), TAMANO_LOTE):
        n = i // TAMANO_LOTE + 1
        lote = pares[i : i + TAMANO_LOTE]
        ids_lote = {p["id"] for p in lote}
        if ids_lote <= set(resultados):
            print(f"  lote {n}/{total_lotes}: ya estaba hecho (retomando)")
            continue
        t0 = time.time()
        print(f"  lote {n}/{total_lotes}: enviando {len(lote)} pares...")
        respuesta, modelo = generar(
            construir_prompt(lote), LoteClasificado, modelos, estado=estado
        )
        modelos_usados.add(modelo)
        for it in respuesta.items:
            if it.id in ids_lote:  # ignora ids que no pedimos
                resultados[it.id] = aplicar_reglas(it.model_dump())
        print(
            f"  lote {n}/{total_lotes}: listo en {time.time() - t0:.0f} s (modelo: {modelo})"
        )
        if al_terminar_lote:
            al_terminar_lote(resultados)
    sin_respuesta = [p["id"] for p in pares if p["id"] not in resultados]
    for pid in (
        sin_respuesta
    ):  # lo que la IA omitió se marca como no determinado, nunca se inventa
        resultados[pid] = {
            "id": pid,
            "sector": SECTOR_NO_DETERMINADO,
            "area_funcional": AREA_NO_DETERMINADA,
            "confianza_sector": "baja",
            "confianza_area": "baja",
        }
    return {
        "resultados": resultados,
        "modelos_usados": sorted(modelos_usados),
        "sin_respuesta": sin_respuesta,
    }


def resumen(pares: list, resultados: dict, filas: list):
    por_clave = {tuple(p["clave"]): resultados[p["id"]] for p in pares}
    sectores = Counter()
    areas = Counter()
    conf_s = Counter()
    conf_a = Counter()
    for f in filas:
        r = por_clave[(_norm(f["empresa"]), _norm(f.get("cargo")))]
        sectores[r["sector"]] += 1
        areas[r["area_funcional"]] += 1
        conf_s[r["confianza_sector"]] += 1
        conf_a[r["confianza_area"]] += 1
    total = len(filas)
    print(
        f"\nResumen sobre {total} experiencias reales ({len(pares)} pares únicos empresa/cargo):"
    )
    nd = sectores[SECTOR_NO_DETERMINADO]
    print(
        f"  Sector clasificado: {total - nd} ({(total - nd) / total * 100:.0f}%) | No determinado: {nd} ({nd / total * 100:.0f}%)"
    )
    nda = areas[AREA_NO_DETERMINADA]
    print(
        f"  Área clasificada:   {total - nda} ({(total - nda) / total * 100:.0f}%) | No determinada: {nda} ({nda / total * 100:.0f}%)"
    )
    print("  Confianza del sector:", dict(conf_s), "| del área:", dict(conf_a))
    print("  Sectores:", dict(sectores.most_common()))
    print("  Áreas:   ", dict(areas.most_common()))


def escribir_revision(pares: list, resultados: dict, n=30, semilla=7):
    random.seed(semilla)
    muestra = random.sample(pares, min(n, len(pares)))
    with open(ARCHIVO_REVISION, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "empresa",
                "cargo",
                "sector_propuesto",
                "area_propuesta",
                "confianza_sector",
                "confianza_area",
                "sector_correcto (s/n)",
                "area_correcta (s/n)",
            ]
        )
        for p in muestra:
            r = resultados[p["id"]]
            w.writerow(
                [
                    p["empresa"],
                    p["cargo"],
                    r["sector"],
                    r["area_funcional"],
                    r["confianza_sector"],
                    r["confianza_area"],
                    "",
                    "",
                ]
            )
    print(
        f"\nMuestra de {len(muestra)} guardada en {ARCHIVO_REVISION}: ábrela en Excel y marca s/n en las dos últimas columnas."
    )


def _cargar_parcial(pares: list) -> dict:
    """Resultados de una ejecución interrumpida, solo si corresponden a EXACTAMENTE los mismos pares."""
    if not os.path.exists(ARCHIVO_PARCIAL):
        return {}
    try:
        with open(ARCHIVO_PARCIAL, encoding="utf-8") as f:
            parcial = json.load(f)
    except (OSError, ValueError):
        return {}
    if parcial.get("claves") != [p["clave"] for p in pares]:
        return {}
    return {int(k): v for k, v in parcial["resultados"].items()}


def paso_prueba(supabase, generar=generar_estructurado_robusto, modelos=None):
    filas = filas_pendientes(supabase)
    if not filas:
        print("No hay experiencias pendientes de clasificar. Nada que hacer.")
        return
    pares = pares_unicos(filas)
    previos = _cargar_parcial(pares)
    print(
        f"{len(filas)} experiencias pendientes -> {len(pares)} pares únicos empresa/cargo."
        + (
            f" Retomando: ya hay {len(previos)} clasificados."
            if previos
            else " Clasificando..."
        )
    )
    print(f"Modelo(s): {', '.join(modelos or MODELOS)}\n")

    def guardar_avance(resultados):
        with open(ARCHIVO_PARCIAL, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "claves": [p["clave"] for p in pares],
                    "resultados": {str(k): v for k, v in resultados.items()},
                },
                f,
                ensure_ascii=False,
            )

    try:
        salida = clasificar_pares(pares, generar, modelos, previos, guardar_avance)
    except KeyboardInterrupt:
        print(
            f"\nInterrumpido por ti. El avance quedó guardado: vuelve a correr el mismo comando para continuar."
        )
        return
    except Exception as e:  # noqa: BLE001
        print(f"\nNo se pudo terminar: {e}")
        print(
            "El avance quedó guardado. Espera unos minutos y vuelve a correr el mismo comando: continúa donde quedó."
        )
        return

    with open(ARCHIVO_RESULTADOS, "w", encoding="utf-8") as f:
        json.dump(
            {
                "pares": pares,
                "resultados": {str(k): v for k, v in salida["resultados"].items()},
                "modelos_usados": salida["modelos_usados"],
            },
            f,
            ensure_ascii=False,
            indent=1,
        )
    if os.path.exists(ARCHIVO_PARCIAL):
        os.remove(ARCHIVO_PARCIAL)
    if salida["sin_respuesta"]:
        print(
            f"  Aviso: la IA omitió {len(salida['sin_respuesta'])} pares; se marcaron como no determinados."
        )
    resumen(pares, salida["resultados"], filas)
    escribir_revision(pares, salida["resultados"])
    print(
        f"\nNo se escribió nada en la base de datos. Cuando estés conforme: python clasificar_experiencias.py --guardar"
    )


# ---------------------------------------------------------------------------
# Paso 2: guardar lo que se revisó
# ---------------------------------------------------------------------------
def paso_guardar(supabase, confianza_minima="media"):
    """confianza_minima='alta': lo que la IA clasificó con confianza 'media' se guarda como no determinado."""
    if not os.path.exists(ARCHIVO_RESULTADOS):
        print(
            f"No existe {ARCHIVO_RESULTADOS}. Primero corre la prueba (sin --guardar)."
        )
        return
    with open(ARCHIVO_RESULTADOS, encoding="utf-8") as f:
        guardado = json.load(f)
    por_clave = {
        tuple(p["clave"]): guardado["resultados"][str(p["id"])]
        for p in guardado["pares"]
    }

    filas = filas_pendientes(
        supabase
    )  # solo las que siguen sin clasificar: así es seguro repetirlo
    escritas = sin_resultado = 0
    for f in filas:
        r = por_clave.get((_norm(f["empresa"]), _norm(f.get("cargo"))))
        if r is None:
            sin_resultado += 1
            continue
        if confianza_minima == "alta":
            r = dict(r)
            if r["confianza_sector"] != "alta":
                r["sector"] = SECTOR_NO_DETERMINADO
            if r["confianza_area"] != "alta":
                r["area_funcional"] = AREA_NO_DETERMINADA
        supabase.table("experiencia_laboral").update(
            {
                "sector": r["sector"],
                "area_funcional": r["area_funcional"],
                "clasificacion_origen": ORIGEN_INFERIDO,
                "sector_confianza": r["confianza_sector"],
                "area_confianza": r["confianza_area"],
            }
        ).eq("id", f["id"]).execute()
        escritas += 1
    print(
        f"Guardadas {escritas} experiencias como 'inferido_ia' (confianza mínima: {confianza_minima}). Sin resultado en el archivo: {sin_resultado}."
    )


def main(argv=None, supabase=None, generar=generar_estructurado_robusto):
    argv = sys.argv[1:] if argv is None else argv
    if supabase is None:
        from dotenv import load_dotenv
        from supabase import create_client

        load_dotenv()
        supabase = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
        )
    if "--guardar" in argv:
        paso_guardar(supabase, "alta" if "--solo-alta" in argv else "media")
    else:
        paso_prueba(
            supabase, generar, MODELOS_GRANDE if "--grande" in argv else MODELOS
        )


if __name__ == "__main__":
    main()
