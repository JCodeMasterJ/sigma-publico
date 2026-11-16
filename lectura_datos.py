"""
Lectura COMPLETA de una tabla de Supabase.

PostgREST (la API de Supabase) devuelve como máximo 1.000 filas por respuesta. Una lectura simple (`select("*")`) con más
de 1.000 filas devuelve solo las primeras 1.000, SIN avisar, y el resto de los datos simplemente no aparece. Esta función
lee por páginas hasta traer todo, y la usan tanto el dashboard como el agente de reportes, para que sus cifras nunca difieran.
"""


def leer_todo(
    client, tabla: str, columnas: str = "*", pagina: int = 1000, orden: str = "id"
) -> list:
    """
    Devuelve todas las filas de `tabla`. Pide el total exacto al servidor y pagina con un orden estable (`orden`),
    porque sin orden, páginas sucesivas pueden repetir o saltarse filas. Aguanta que el servidor recorte las páginas
    a menos filas de las pedidas: sigue desde donde quedó, no desde donde esperaba.
    """
    filas, inicio, total = [], 0, None
    while True:
        consulta = client.table(tabla).select(columnas, count="exact")
        if orden:
            consulta = consulta.order(orden)
        respuesta = consulta.range(inicio, inicio + pagina - 1).execute()
        lote = respuesta.data or []
        if total is None:
            total = getattr(respuesta, "count", None)
        filas.extend(lote)
        if not lote:  # no hay más
            break
        if total is not None and len(filas) >= total:  # ya está todo
            break
        inicio += len(lote)
    return filas
