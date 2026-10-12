"""
Comprueba, contra tu Supabase REAL, que los permisos están bien cerrados.
Solo LEE (y un intento de escritura que debe fallar): no cambia ningún dato.

  Parte 1 (sin sesión): usa la llave pública. NINGUNA tabla debe devolver datos.
  Parte 2 (opcional, con una cuenta): pide un correo y una contraseña (la contraseña no se muestra
          ni se guarda) y comprueba que esa cuenta ve solo lo que su rol permite.

Correr:  python verificar_rls.py
"""

import getpass
import os

TABLAS = [
    "egresados",
    "experiencia_laboral",
    "usuarios_app",
    "documentos_cv",
    "reportes_ia",
    "encuestas",
    "preguntas_encuesta",
    "respuestas_encuesta",
    "programas",
]


def _contar(cliente, tabla):
    """(filas_visibles | None si fue denegado, detalle)"""
    try:
        r = cliente.table(tabla).select("*").limit(5).execute()
        return len(r.data), f"devolvió {len(r.data)} fila(s)"
    except Exception as e:  # noqa: BLE001
        return None, f"denegado ({str(e)[:60]})"


def verificar_sin_sesion(cliente) -> list:
    resultados = []
    for t in TABLAS:
        n, detalle = _contar(cliente, t)
        resultados.append((f"sin sesión: {t}", n in (None, 0), detalle))
    return resultados


FUNCIONES_PROTEGIDAS = [
    ("vincular_mi_registro", {}),
    ("crear_mi_perfil", {"p_nombre": "Prueba De Seguridad", "p_anio_grado": 2020}),
    (
        "guardar_mi_perfil",
        {"p_situacion": "empleado", "p_empresa": "x", "p_consentimiento": True},
    ),
    ("marcar_revisado", {"p_egresado_id": "00000000-0000-0000-0000-000000000000"}),
    ("descartar_perfil", {"p_egresado_id": "00000000-0000-0000-0000-000000000000"}),
    ("registrar_uso_cv", {}),
]


def verificar_funciones_sin_sesion(cliente) -> list:
    """Sin sesión, ninguna función de escritura debe poder ejecutarse (todas deben dar error)."""
    resultados = []
    for nombre, params in FUNCIONES_PROTEGIDAS:
        try:
            cliente.rpc(nombre, params).execute()
            resultados.append(
                (f"sin sesión: función {nombre}", False, "SE EJECUTÓ sin sesión")
            )
        except Exception as e:  # noqa: BLE001
            resultados.append(
                (f"sin sesión: función {nombre}", True, f"denegado ({str(e)[:45]})")
            )
    return resultados


def verificar_con_sesion(cliente, rol: str, user_id: str) -> list:
    resultados = []
    n_egr, det = _contar(cliente, "egresados")
    if rol == "admin":
        resultados.append(
            ("admin ve egresados", bool(n_egr), det + " (debe ver datos)")
        )
    else:
        resultados.append(
            (
                "egresado ve como máximo SU registro",
                (n_egr or 0) <= 1,
                det + " (máximo 1)",
            )
        )
    for t in ("reportes_ia", "documentos_cv"):
        n, det = _contar(cliente, t)
        resultados.append((f"{rol} no lee {t}", n in (None, 0), det))
    # un egresado no puede marcar ni descartar perfiles (solo la administración)
    if rol != "admin":
        for funcion, texto in (
            ("marcar_revisado", "marcar perfiles como revisados"),
            ("descartar_perfil", "descartar perfiles"),
        ):
            try:
                cliente.rpc(
                    funcion, {"p_egresado_id": "00000000-0000-0000-0000-000000000000"}
                ).execute()
                resultados.append((f"{rol} no puede {texto}", False, "SE EJECUTÓ"))
            except Exception as e:  # noqa: BLE001
                resultados.append(
                    (f"{rol} no puede {texto}", True, f"denegado ({str(e)[:45]})")
                )
    # nadie escribe directo en la tabla de egresados (todo pasa por funciones con validación)
    try:
        fila = (
            cliente.table("usuarios_app")
            .select("egresado_id")
            .eq("user_id", user_id)
            .execute()
            .data
        )
        eid = fila[0]["egresado_id"] if fila else None
        if eid:
            nombre = (
                cliente.table("egresados")
                .select("nombre")
                .eq("id", eid)
                .execute()
                .data[0]["nombre"]
            )
            r = (
                cliente.table("egresados")
                .update({"nombre": nombre})
                .eq("id", eid)
                .execute()
            )
            resultados.append(
                (
                    f"{rol} no puede escribir directo en egresados",
                    len(r.data) == 0,
                    f"el intento afectó {len(r.data)} fila(s)",
                )
            )
    except Exception as e:  # noqa: BLE001
        resultados.append(
            (
                f"{rol} no puede escribir directo en egresados",
                True,
                f"denegado ({str(e)[:45]})",
            )
        )
    # intento de hacerse administrador: DEBE fallar
    try:
        r = (
            cliente.table("usuarios_app")
            .update({"rol": "admin"})
            .eq("user_id", user_id)
            .execute()
        )
        resultados.append(
            (
                f"{rol} no puede cambiarse el rol",
                len(r.data) == 0,
                f"el intento afectó {len(r.data)} fila(s)",
            )
        )
    except Exception as e:  # noqa: BLE001
        resultados.append(
            (f"{rol} no puede cambiarse el rol", True, f"denegado ({str(e)[:50]})")
        )
    return resultados


def imprimir(resultados) -> bool:
    for nombre, ok, detalle in resultados:
        print(("  OK    " if ok else "  FALLA "), f"{nombre:42s} {detalle}")
    return all(ok for _, ok, _ in resultados)


def main(crear_cliente=None, preguntar=input, clave=getpass.getpass):
    if crear_cliente is None:
        from dotenv import load_dotenv
        from supabase import create_client

        load_dotenv()
        url, key = os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"]
        crear_cliente = lambda: create_client(url, key)  # noqa: E731

    print("PARTE 1 — Visitante sin sesión (llave pública)")
    cliente_anonimo = crear_cliente()
    ok1 = imprimir(
        verificar_sin_sesion(cliente_anonimo)
        + verificar_funciones_sin_sesion(cliente_anonimo)
    )
    print(
        "  => "
        + (
            "TODO CERRADO: la llave pública no lee nada."
            if ok1
            else "ATENCIÓN: hay datos expuestos a la llave pública."
        )
    )

    correo = preguntar(
        "\nPARTE 2 (opcional) — correo de una cuenta para probar (Enter para omitir): "
    ).strip()
    ok2 = True
    if correo:
        cliente = crear_cliente()
        try:
            sesion = cliente.auth.sign_in_with_password(
                {"email": correo, "password": clave("Contraseña (no se muestra): ")}
            )
        except Exception as e:  # noqa: BLE001
            print(f"  No se pudo iniciar sesión: {str(e)[:80]}")
            return ok1
        uid = sesion.user.id
        fila = (
            cliente.table("usuarios_app")
            .select("rol")
            .eq("user_id", uid)
            .execute()
            .data
        )
        rol = fila[0]["rol"] if fila else "egresado"
        print(f"\n  Sesión iniciada como: {correo} (rol: {rol})")
        ok2 = imprimir(verificar_con_sesion(cliente, rol, uid))
        cliente.auth.sign_out()
    return ok1 and ok2


if __name__ == "__main__":
    main()
