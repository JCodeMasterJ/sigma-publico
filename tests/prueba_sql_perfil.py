import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
try:  # estas pruebas usan un Postgres embebido: son OPCIONALES (pip install pgserver psycopg2-binary)
    import psycopg2, pgserver
    from psycopg2 import errors
except ImportError as _e:
    print(
        f"OMITIDA: faltan librerias para el Postgres de pruebas ({_e.name}). Instalalas con:  pip install pgserver psycopg2-binary"
    )
    sys.exit(77)
import re, tempfile, uuid, json

import taxonomia

SQL_2A = open(str(RAIZ / "fase2a_seguridad.sql"), encoding="utf-8").read()
SQL_2B = open(str(RAIZ / "fase2b_perfil.sql"), encoding="utf-8").read()
SCHEMA = open(str(RAIZ / "schema.sql"), encoding="utf-8").read()
FASE1 = open(str(RAIZ / "fase1_esquema.sql"), encoding="utf-8").read()
PROMO = open(str(RAIZ / "promover_admin.sql"), encoding="utf-8").read()

try:
    srv = pgserver.get_server(tempfile.mkdtemp())
except (
    Exception
) as _e:  # p. ej. un antivirus o permisos que impiden arrancar el Postgres embebido
    print(
        f"OMITIDA: no se pudo iniciar el Postgres embebido ({type(_e).__name__}: {str(_e)[:120]})"
    )
    sys.exit(77)
uri = srv.get_uri()


def ejecutar(sql, params=None):
    c = psycopg2.connect(uri)
    c.autocommit = True
    cur = c.cursor()
    cur.execute(sql, params)
    try:
        r = cur.fetchall()
    except psycopg2.ProgrammingError:
        r = None
    c.close()
    return r


# ---------- Mini Supabase ----------
ejecutar("""
do $$ begin
  if not exists (select from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select from pg_roles where rolname = 'service_role') then create role service_role nologin bypassrls; end if;
end $$;
create schema if not exists auth;
create table if not exists auth.users (id uuid primary key default gen_random_uuid(), email text, email_confirmed_at timestamptz default now());
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.uid() to anon, authenticated, service_role;
""")
ejecutar(SCHEMA)
ejecutar("""
alter table egresados add column if not exists bio text;
alter table egresados add column if not exists ciudad_residencia text;
alter table experiencia_laboral add column if not exists tipo_empresa text;
alter table egresados enable row level security; alter table experiencia_laboral enable row level security;
alter table documentos_cv enable row level security; alter table reportes_ia enable row level security;
grant usage on schema public to anon, service_role;
grant all on all tables in schema public to service_role;
""")
ejecutar(FASE1)
for _ in (1, 2):
    ejecutar(SQL_2A)
for _ in (1, 2):
    ejecutar(SQL_2B)  # repetible
SQL_DESC = open(str(RAIZ / "fase2b_descartar_perfiles.sql"), encoding="utf-8").read()
SQL_CV = open(str(RAIZ / "fase2c_cv.sql"), encoding="utf-8").read()
for _ in (1, 2):
    ejecutar(SQL_DESC)  # repetible
for _ in (1, 2):
    ejecutar(SQL_CV)  # repetible
SQL_COH = open(str(RAIZ / "fase3_cohorte.sql"), encoding="utf-8").read()
for _ in (1, 2):
    ejecutar(SQL_COH)  # repetible
print("2A y 2B corrieron (cada una 2 veces) sin error\n")


# ---------- Datos de prueba ----------
def nuevo_usuario(email, confirmado=True):
    uid = str(uuid.uuid4())
    ejecutar(
        "insert into auth.users (id, email, email_confirmed_at) values (%s, %s, %s)",
        (uid, email, "now()" if confirmado else None)
        if False
        else (
            uid,
            email,
            None if not confirmado else __import__("datetime").datetime.now(),
        ),
    )
    return uid


def nuevo_egresado(nombre, email=None, fuente="real", cohorte="2022"):
    eid = str(uuid.uuid4())
    ejecutar(
        "insert into egresados (id, nombre, email, cohorte, fuente) values (%s,%s,%s,%s,%s)",
        (eid, nombre, email, cohorte, fuente),
    )
    return eid


E = {
    "ana": nuevo_egresado("Ana Real", "ana@x.com"),
    "beto": nuevo_egresado("Beto Real", "beto@x.com"),
    "sint": nuevo_egresado("Sintetica", "sint@x.com", "sintetico"),
    "carlos": nuevo_egresado("Carlos Real", "carlos@x.com"),
    "maria": nuevo_egresado("Maria Real", "maria@x.com"),
    "r4": nuevo_egresado("R4 Reclamado", "dup@x.com"),
}
ejecutar(
    """insert into experiencia_laboral (egresado_id, empresa, cargo, sector, area_funcional, clasificacion_origen, sector_confianza, area_confianza, tipo_empresa, fuente)
            values (%s,'Claro Colombia','Ingeniero','Telecomunicaciones','Redes y telecomunicaciones','inferido_ia','alta','media','Privada','real')""",
    (E["ana"],),
)
ejecutar(
    """insert into experiencia_laboral (egresado_id, empresa, cargo, fuente) values (%s,'Empresa de Beto','Analista','real')""",
    (E["beto"],),
)

U = {
    "ana": nuevo_usuario("ana@x.com"),
    "beto": nuevo_usuario("beto@x.com"),
    "nuevo": nuevo_usuario("nuevo@x.com"),
    "sinconf": nuevo_usuario("sinconf@x.com", False),
    "dup": nuevo_usuario("dup@x.com"),
    "otro": nuevo_usuario("otro@x.com"),
    "sint": nuevo_usuario("sint@x.com"),
    "caso": nuevo_usuario("MARIA@X.com"),
    "carlos": nuevo_usuario("carlos@x.com"),
    "admin": nuevo_usuario("admin@x.com"),
    "nuevo2": nuevo_usuario("nuevo2@x.com"),
}
ejecutar(
    "update usuarios_app set egresado_id = %s where user_id = %s",
    (E["beto"], U["beto"]),
)  # Beto ya vinculado
ejecutar(
    "update usuarios_app set egresado_id = %s where user_id = %s", (E["r4"], U["otro"])
)  # R4 reclamado por otra cuenta
ejecutar(
    PROMO.replace("TU_CORREO@ejemplo.com", "admin@x.com").replace(
        "CORREO_DE_LA_PROFESORA@ejemplo.com", "nadie@x.com"
    )
)

resultados = []


def chequear(nombre, ok, detalle=""):
    resultados.append(bool(ok))
    print(
        ("OK   " if ok else "FALLA"),
        f"{nombre:70s}",
        ("-> " + str(detalle)[:70]) if detalle else "",
    )


def llamar(usuario, sql, params=None, rol="authenticated"):
    """Ejecuta como esa cuenta (rol + sub del JWT). Devuelve ('ok', filas) o ('error', mensaje)."""
    c = psycopg2.connect(uri)
    c.autocommit = False
    cur = c.cursor()
    try:
        cur.execute(f"set local role {rol}")
        if usuario:
            cur.execute(
                "select set_config('request.jwt.claim.sub', %s, true)", (U[usuario],)
            )
        cur.execute(sql, params)
        try:
            r = cur.fetchall()
        except psycopg2.ProgrammingError:
            r = None
        c.commit()
        return "ok", r
    except errors.InsufficientPrivilege as e:
        c.rollback()
        return "denegado", str(e)
    except psycopg2.Error as e:
        c.rollback()
        return "error", str(e).strip()
    finally:
        c.close()


def guardar(usuario, **kw):
    args = {
        "p_situacion": "empleado",
        "p_ciudad": None,
        "p_pais": None,
        "p_empresa": None,
        "p_cargo": None,
        "p_sector": None,
        "p_area": None,
        "p_tecnologias": None,
        "p_consentimiento": True,
    }
    args.update(kw)
    return llamar(
        usuario,
        """select public.guardar_mi_perfil(p_situacion := %(p_situacion)s, p_ciudad := %(p_ciudad)s,
        p_pais := %(p_pais)s, p_empresa := %(p_empresa)s, p_cargo := %(p_cargo)s, p_sector := %(p_sector)s,
        p_area := %(p_area)s, p_tecnologias := %(p_tecnologias)s::text[], p_consentimiento := %(p_consentimiento)s)""",
        args,
    )


def fila(sql, params=None):
    return ejecutar(sql, params)


print("==== Vincular la cuenta con su registro ====")
est, r = llamar("ana", "select public.vincular_mi_registro()")
chequear(
    "correo coincide: se vincula",
    est == "ok"
    and r[0][0]["estado"] == "vinculado"
    and r[0][0]["egresado_id"] == E["ana"],
    r,
)
chequear(
    "   ...y la cuenta quedó apuntando al registro de Ana",
    str(
        fila("select egresado_id from usuarios_app where user_id=%s", (U["ana"],))[0][0]
    )
    == E["ana"],
)
est, r = llamar("ana", "select public.vincular_mi_registro()")
chequear("repetir no cambia nada ('ya_vinculado')", r[0][0]["estado"] == "ya_vinculado")
est, r = llamar("caso", "select public.vincular_mi_registro()")
chequear(
    "el correo se compara sin importar mayúsculas (MARIA@X.com)",
    r[0][0]["estado"] == "vinculado",
    r,
)
est, r = llamar("nuevo", "select public.vincular_mi_registro()")
chequear(
    "correo sin coincidencia: 'sin_coincidencia' y no se vincula nada",
    r[0][0]["estado"] == "sin_coincidencia"
    and fila("select egresado_id from usuarios_app where user_id=%s", (U["nuevo"],))[0][
        0
    ]
    is None,
)
est, r = llamar("sint", "select public.vincular_mi_registro()")
chequear(
    "un registro SINTÉTICO con ese correo NO se reclama",
    r[0][0]["estado"] == "sin_coincidencia",
    r,
)
est, r = llamar("dup", "select public.vincular_mi_registro()")
chequear(
    "registro ya reclamado por otra cuenta: 'ya_reclamado'",
    r[0][0]["estado"] == "ya_reclamado",
    r,
)
est, r = llamar("sinconf", "select public.vincular_mi_registro()")
chequear(
    "correo SIN confirmar: se rechaza", est == "error" and "no está confirmado" in r, r
)
est, r = llamar(None, "select public.vincular_mi_registro()", rol="anon")
chequear("visitante sin sesión no puede llamarla", est == "denegado", est)
try:
    ejecutar(
        "update usuarios_app set egresado_id = %s where user_id = %s",
        (E["ana"], U["carlos"]),
    )
    ok = False
except psycopg2.errors.UniqueViolation:
    ok = True
chequear("la base impide que 2 cuentas reclamen el mismo registro (índice único)", ok)

print("\n==== Crear perfil nuevo (correo sin coincidencia) ====")
est, r = llamar(
    "nuevo",
    "select public.crear_mi_perfil(%s, %s)",
    ("  Nuevo   Egresado Prueba ", 2020),
)
perfil_nuevo = r[0][0] if est == "ok" else None
datos = (
    fila(
        "select nombre, cohorte, fuente, por_revisar, email, situacion_laboral from egresados where id=%s",
        (perfil_nuevo,),
    )[0]
    if perfil_nuevo
    else None
)
chequear(
    "se crea el perfil, con el nombre normalizado y marcado 'por revisar'",
    datos
    == ("Nuevo Egresado Prueba", "2020", "real", True, "nuevo@x.com", "desconocido"),
    datos,
)
chequear(
    "   ...y queda vinculado a la cuenta",
    str(
        fila("select egresado_id from usuarios_app where user_id=%s", (U["nuevo"],))[0][
            0
        ]
    )
    == perfil_nuevo,
)
est, r = llamar(
    "nuevo", "select public.crear_mi_perfil(%s, %s)", ("Otro Nombre Largo", 2021)
)
chequear(
    "no puede crear un segundo perfil", est == "error" and "ya está vinculada" in r, r
)
est, r = llamar("nuevo2", "select public.crear_mi_perfil(%s, %s)", ("ab", 2020))
chequear(
    "nombre demasiado corto: se rechaza", est == "error" and "nombre completo" in r, r
)
est, r = llamar(
    "nuevo2", "select public.crear_mi_perfil(%s, %s)", ("Nombre Valido Largo", 1900)
)
chequear(
    "año de grado imposible: se rechaza", est == "error" and "año de grado" in r, r
)
est, r = llamar(
    "carlos", "select public.crear_mi_perfil(%s, %s)", ("Carlos Que Se Duplica", 2020)
)
chequear(
    "si su correo YA está en un registro sin reclamar, no puede duplicarse",
    est == "error" and "ya coincide" in r,
    r,
)

print("\n==== Guardar la información ====")
est, r = guardar("ana", p_consentimiento=False, p_empresa="X")
chequear(
    "sin aceptar el consentimiento: se rechaza",
    est == "error" and "consentimiento" in r,
    r,
)
est, r = guardar("ana", p_situacion=None, p_consentimiento=False)
chequear(
    "sin situación Y sin consentimiento: avisa primero lo que se lee primero (la situación)",
    est == "error" and "situación" in r,
    r,
)
est, r = guardar("ana", p_situacion="rico")
chequear("situación inventada: se rechaza", est == "error" and "situación" in r, r)
est, r = guardar("ana", p_situacion="empleado", p_empresa="   ")
chequear("empleado sin empresa: se rechaza", est == "error" and "empresa" in r, r)
est, r = guardar("ana", p_empresa="X", p_sector="Sector Inventado")
chequear(
    "sector fuera de la lista: se rechaza",
    est == "error" and "Sector no válido" in r,
    r,
)
est, r = guardar("ana", p_empresa="X", p_area="Area Inventada")
chequear(
    "área fuera de la lista: se rechaza", est == "error" and "Área no válida" in r, r
)
est, r = guardar("ana", p_empresa="E" * 500)
chequear(
    "empresa de 500 caracteres: se rechaza",
    est == "error" and "demasiado largos" in r,
    r,
)
est, r = guardar("ana", p_empresa="X", p_tecnologias=[f"t{i}" for i in range(31)])
chequear(
    "más de 30 tecnologías: se rechaza", est == "error" and "30 tecnologías" in r, r
)
est, r = guardar("nuevo2", p_empresa="X")
chequear(
    "cuenta sin registro vinculado: se rechaza",
    est == "error" and "no está vinculada" in r,
    r,
)
chequear(
    "   ...y nada de lo rechazado cambió los datos de Ana",
    fila(
        "select situacion_origen, consentimiento_datos from egresados where id=%s",
        (E["ana"],),
    )[0]
    == ("institucional_historico", False),
)

# --- guardado correcto, misma empresa, sin declarar sector ---
est, r = guardar(
    "ana",
    p_situacion="empleado",
    p_ciudad="Bogotá",
    p_pais="Colombia",
    p_empresa="claro colombia",
    p_cargo="Ingeniero Senior",
    p_tecnologias=["Python", " Cisco ", "Python", "", "python"],
)
g = fila(
    "select situacion_laboral, ciudad_residencia, pais_residencia, consentimiento_datos, consentimiento_en is not null, situacion_origen, situacion_actualizada_en is not null from egresados where id=%s",
    (E["ana"],),
)[0]
chequear(
    "guardar: egresado actualizado (situación, ciudad, país, consentimiento, origen y fecha)",
    est == "ok"
    and g
    == ("empleado", "Bogotá", "Colombia", True, True, "declarada_por_egresado", True),
    g,
)
x = fila(
    "select count(*), max(cargo), max(sector), max(clasificacion_origen), max(tipo_empresa), max(tecnologias::text) from experiencia_laboral where egresado_id=%s and fecha_fin is null",
    (E["ana"],),
)[0]
chequear(
    "   ...se ACTUALIZA la experiencia (no se duplica) y, al seguir en la misma empresa, conserva sector inferido y tipo",
    x[0] == 1
    and x[1] == "Ingeniero Senior"
    and x[2] == "Telecomunicaciones"
    and x[3] == "inferido_ia"
    and x[4] == "Privada",
    x,
)
chequear(
    "   ...tecnologías limpias (sin vacíos ni repetidas exactas)",
    x[5] == "{Python,Cisco,python}",
    x[5],
)

# --- cambia de empresa sin declarar sector: lo anterior ya no aplica ---
est, r = guardar("ana", p_empresa="Huawei", p_cargo="Ingeniero RF")
x = fila(
    "select count(*), max(empresa), max(sector), max(clasificacion_origen), max(tipo_empresa), max(tecnologias::text) from experiencia_laboral where egresado_id=%s and fecha_fin is null",
    (E["ana"],),
)[0]
chequear(
    "cambia de empresa: el sector inferido y el tipo de la empresa anterior se limpian",
    x[0] == 1 and x[1] == "Huawei" and x[2] is None and x[3] is None and x[4] is None,
    x,
)
chequear(
    "   ...pero las tecnologías ya declaradas se conservan",
    x[5] == "{Python,Cisco,python}",
    x[5],
)

# --- declara sector y área ---
est, r = guardar(
    "ana", p_empresa="Huawei", p_sector="Educación", p_area="Docencia e investigación"
)
x = fila(
    "select sector, area_funcional, clasificacion_origen from experiencia_laboral where egresado_id=%s and fecha_fin is null",
    (E["ana"],),
)[0]
chequear(
    "si declara sector y área: quedan como 'declarado'",
    x == ("Educación", "Docencia e investigación", "declarado"),
    x,
)

# --- deja de estar empleado: se CIERRA, no se borra ---
est, r = guardar("ana", p_situacion="desempleado")
vig = fila(
    "select count(*) from experiencia_laboral where egresado_id=%s and fecha_fin is null",
    (E["ana"],),
)[0][0]
cerr = fila(
    "select count(*) from experiencia_laboral where egresado_id=%s and fecha_fin = current_date",
    (E["ana"],),
)[0][0]
chequear(
    "pasa a desempleado: la experiencia se CIERRA con fecha (no se borra)",
    est == "ok" and vig == 0 and cerr == 1,
    (vig, cerr),
)
est, r = guardar("ana", p_situacion="empleado", p_empresa="Nueva Empresa")
tot = fila(
    "select count(*), count(*) filter (where fecha_fin is null) from experiencia_laboral where egresado_id=%s",
    (E["ana"],),
)[0]
chequear(
    "vuelve a emplearse: se crea una experiencia NUEVA y la anterior queda en el historial",
    tot == (2, 1),
    tot,
)
est, r = guardar("ana", p_situacion="estudios_posteriores")
chequear(
    "estudiando: también cierra la experiencia vigente",
    fila(
        "select count(*) from experiencia_laboral where egresado_id=%s and fecha_fin is null",
        (E["ana"],),
    )[0][0]
    == 0,
)

print("\n==== Aislamiento entre cuentas ====")
antes_ana = fila(
    "select situacion_laboral, ciudad_residencia from egresados where id=%s",
    (E["ana"],),
)[0]
est, r = guardar(
    "beto",
    p_situacion="empleado",
    p_ciudad="Cali",
    p_empresa="Otra",
    p_consentimiento=True,
)
despues_ana = fila(
    "select situacion_laboral, ciudad_residencia from egresados where id=%s",
    (E["ana"],),
)[0]
beto = fila(
    "select situacion_laboral, ciudad_residencia from egresados where id=%s",
    (E["beto"],),
)[0]
chequear(
    "la cuenta de Beto solo modifica a Beto; Ana queda intacta",
    beto == ("empleado", "Cali") and antes_ana == despues_ana,
    (beto, despues_ana),
)
est, r = llamar(
    "ana", "update egresados set nombre = 'hackeado' where id = %s", (E["beto"],)
)
chequear("sigue sin poder escribir directo sobre egresados", est == "denegado")
est, r = llamar(
    "ana",
    "insert into experiencia_laboral (egresado_id, empresa) values (%s, 'x')",
    (E["ana"],),
)
chequear("sigue sin poder insertar directo en experiencia_laboral", est == "denegado")
est, r = llamar("ana", "select count(*) from egresados")
chequear("sigue viendo solo SU registro", r[0][0] == 1, r)
for fn, sql, params in (
    (
        "guardar_mi_perfil",
        "select public.guardar_mi_perfil(p_situacion := 'empleado', p_consentimiento := true)",
        None,
    ),
    ("crear_mi_perfil", "select public.crear_mi_perfil('Nombre Largo Ok', 2020)", None),
    ("marcar_revisado", "select public.marcar_revisado(%s::uuid)", (E["ana"],)),
):
    est, r = llamar(None, sql, params, rol="anon")
    chequear(f"visitante sin sesión no puede llamar {fn}", est == "denegado", est)

print("\n==== Revisión por la administración ====")
est, r = llamar("ana", "select public.marcar_revisado(%s::uuid)", (perfil_nuevo,))
chequear(
    "un egresado NO puede marcar perfiles como revisados",
    est == "error" and "administración" in r,
    r,
)
est, r = llamar("admin", "select public.marcar_revisado(%s::uuid)", (perfil_nuevo,))
chequear(
    "la administración sí",
    est == "ok"
    and fila("select por_revisar from egresados where id=%s", (perfil_nuevo,))[0][0]
    is False,
)
est, r = llamar("admin", "select count(*) from egresados where por_revisar")
chequear(
    "el admin ve la lista de perfiles por revisar (ya vacía)",
    est == "ok" and r[0][0] == 0,
    r,
)

print("\n==== Descartar perfiles por revisar ====")
# un perfil nuevo con experiencia, creado desde el portal por una cuenta nueva
est, r = llamar(
    "nuevo2", "select public.crear_mi_perfil(%s, %s)", ("Perfil Para Descartar", 2021)
)
perfil2 = r[0][0]
guardar(
    "nuevo2", p_situacion="empleado", p_empresa="Empresa Ficticia", p_cargo="Analista"
)
chequear(
    "preparación: perfil por revisar con una experiencia",
    fila("select por_revisar from egresados where id=%s", (perfil2,))[0][0] is True
    and fila(
        "select count(*) from experiencia_laboral where egresado_id=%s", (perfil2,)
    )[0][0]
    == 1,
)
est, r = llamar("ana", "select public.descartar_perfil(%s::uuid)", (perfil2,))
chequear(
    "un egresado NO puede descartar perfiles",
    est == "error" and "administración" in r,
    r,
)
est, r = llamar(
    None, "select public.descartar_perfil(%s::uuid)", (perfil2,), rol="anon"
)
chequear("un visitante sin sesión no puede llamar la función", est == "denegado", est)
est, r = llamar("admin", "select public.descartar_perfil(%s::uuid)", (E["beto"],))
chequear(
    "el admin NO puede descartar un registro histórico real (no está 'por revisar')",
    est == "error" and "perfiles nuevos" in r,
    r,
)
chequear(
    "   ...y ese registro histórico sigue ahí",
    fila("select count(*) from egresados where id=%s", (E["beto"],))[0][0] == 1,
)
est, r = llamar("admin", "select public.descartar_perfil(%s::uuid)", (E["sint"],))
chequear(
    "el admin NO puede descartar un registro sintético",
    est == "error" and "perfiles nuevos" in r,
    r,
)
est, r = llamar(
    "admin", "select public.descartar_perfil(%s::uuid)", (str(uuid.uuid4()),)
)
chequear(
    "un identificador que no existe: se rechaza",
    est == "error" and "perfiles nuevos" in r,
    r,
)
est, r = llamar("admin", "select public.descartar_perfil(%s::uuid)", (perfil2,))
chequear(
    "el admin descarta el perfil nuevo",
    est == "ok"
    and fila("select count(*) from egresados where id=%s", (perfil2,))[0][0] == 0,
)
chequear(
    "   ...y su experiencia se borra en cascada",
    fila("select count(*) from experiencia_laboral where egresado_id=%s", (perfil2,))[
        0
    ][0]
    == 0,
)
chequear(
    "   ...pero la CUENTA de la persona se conserva, solo queda sin registro vinculado",
    fila("select count(*) from auth.users where id=%s", (U["nuevo2"],))[0][0] == 1
    and fila("select egresado_id from usuarios_app where user_id=%s", (U["nuevo2"],))[
        0
    ][0]
    is None,
)
est, r = llamar(
    "nuevo2", "select public.crear_mi_perfil(%s, %s)", ("Perfil Bien Hecho Ahora", 2021)
)
chequear(
    "   ...y esa persona puede volver a crear su perfil correctamente", est == "ok", r
)

print("\n==== Límite de uso del análisis de CV ====")
est, r = llamar("ana", "select public.registrar_uso_cv()")
chequear(
    "el primer análisis se permite y dice cuántos quedan (4)",
    est == "ok" and r[0][0] == 4,
    r,
)
for i in range(4):
    est, r = llamar("ana", "select public.registrar_uso_cv()")
chequear(
    "los análisis 2 a 5 se permiten; el quinto deja 0", est == "ok" and r[0][0] == 0, r
)
est, r = llamar("ana", "select public.registrar_uso_cv()")
chequear(
    "el sexto en el mismo día se rechaza con un aviso claro",
    est == "error" and "5 veces hoy" in r,
    r,
)
est, r = llamar("beto", "select public.registrar_uso_cv()")
chequear(
    "el límite es POR PERSONA: Beto sí puede usarlo", est == "ok" and r[0][0] == 4, r
)
chequear(
    "se guardó el conteo de Ana y la fecha en que aceptó el procesamiento",
    fila(
        "select n, consentimiento_en is not null from uso_cv where user_id=%s",
        (U["ana"],),
    )[0]
    == (5, True),
)
ejecutar("update uso_cv set dia = current_date - 1 where user_id = %s", (U["ana"],))
est, r = llamar("ana", "select public.registrar_uso_cv()")
chequear(
    "al día siguiente el contador de Ana vuelve a empezar",
    est == "ok" and r[0][0] == 4,
    r,
)
est, r = llamar("dup", "select public.registrar_uso_cv()")
chequear(
    "una cuenta SIN registro vinculado no puede usarlo",
    est == "error" and "no está vinculada" in r,
    r,
)
est, r = llamar(None, "select public.registrar_uso_cv()", rol="anon")
chequear("un visitante sin sesión no puede llamarla", est == "denegado", est)
est, r = llamar("ana", "select * from uso_cv")
chequear(
    "un egresado NO puede leer la tabla de uso (ni la suya ni la de otros)",
    est == "denegado",
    est,
)
est, r = llamar("ana", "update uso_cv set n = 0")
chequear("un egresado NO puede reiniciar su propio contador", est == "denegado", est)
ejecutar("delete from uso_cv")
ejecutar(
    "insert into uso_cv (user_id, dia, n) values (%s, current_date, 150)", (U["otro"],)
)
est, r = llamar("ana", "select public.registrar_uso_cv()")
chequear(
    "al llegar al TOPE GLOBAL del día (150) se rechaza para todos, protegiendo la cuota de la IA",
    est == "error" and "límite de hoy" in r,
    r,
)
ejecutar("delete from uso_cv")

print("\n==== Tu cohorte en cifras ====")
import pandas as pd
import cohorte as coh_mod


def grupo(cohorte, fuente, especificaciones):
    """Crea egresados (y su experiencia) de una promoción. Devuelve sus ids."""
    ids = []
    for esp in especificaciones:
        eid = str(uuid.uuid4())
        ejecutar(
            "insert into egresados (id, nombre, cohorte, fuente, situacion_laboral, ciudad_residencia, por_revisar) values (%s,%s,%s,%s,%s,%s,%s)",
            (
                eid,
                f"Persona {cohorte}-{len(ids)}",
                cohorte,
                fuente,
                esp.get("sit", "desconocido"),
                esp.get("ciudad"),
                esp.get("pend", False),
            ),
        )
        for sector, techs, fin in esp.get("exp", []):
            ejecutar(
                "insert into experiencia_laboral (egresado_id, empresa, cargo, sector, tecnologias, fecha_fin, fuente) values (%s,'Empresa','Cargo',%s,%s::text[],%s,%s)",
                (eid, sector, techs, fin, fuente),
            )
        ids.append(eid)
    return ids


EMP, DES, DSC, EST = "empleado", "desempleado", "desconocido", "estudios_posteriores"
g2018 = grupo(
    "2018",
    "real",
    [
        {
            "sit": EMP,
            "ciudad": "Bucaramanga",
            "exp": [
                ("Telecomunicaciones", ["Python", "Cisco"], None),
                ("Telecomunicaciones", ["Rust"] * 4, "2019-01-01"),
            ],
        },  # la 2.ª ya terminó: no cuenta
        {
            "sit": EMP,
            "ciudad": "Bucaramanga",
            "exp": [("Telecomunicaciones", ["Python", "Cisco"], None)],
        },
        {
            "sit": EMP,
            "ciudad": "Bucaramanga",
            "exp": [("Telecomunicaciones", ["Python"], None)],
        },
        {
            "sit": EMP,
            "ciudad": "Bucaramanga",
            "exp": [("Telecomunicaciones", ["Python", "Linux", "Cisco"], None)],
        },
        {
            "sit": EMP,
            "ciudad": "Bogotá",
            "exp": [("Tecnología", ["Python", "Linux"], None)],
        },
        {"sit": EMP, "ciudad": "Bogotá", "exp": [("Tecnología", ["Go"], None)]},
        {"sit": EMP, "ciudad": "Bogotá", "exp": [("Tecnología", [], None)]},
        {"sit": EMP, "ciudad": "Cali", "exp": [("Salud", None, None)]},
        {"sit": DES, "ciudad": "Bucaramanga"},
        {"sit": DSC, "ciudad": "Cali"},
        {"sit": DSC, "ciudad": "Cúcuta"},
        {"sit": DSC},
        {"sit": DSC},
        {"sit": EST},
    ],
)
# TRAMPAS: no deben contarse en la promoción real 2018
grupo(
    "2018",
    "real",
    [
        {
            "sit": EMP,
            "ciudad": "Bucaramanga",
            "pend": True,
            "exp": [("Telecomunicaciones", ["Python"], None)],
        }
    ],
)  # perfil pendiente de revisión
g2018s = grupo(
    "2018", "sintetico", [{"sit": EMP, "ciudad": "Bucaramanga"}]
)  # otra fuente
grupo(
    "2019", "real", [{"sit": DSC, "ciudad": "Pasto"}] * 12
)  # otra promoción, con una ciudad distinta
g2030 = grupo("2030", "real", [{"sit": EMP}] * 4)  # promoción demasiado pequeña
g2040 = grupo(
    "2040", "real", [{"sit": EMP}] + [{"sit": DSC}] * 15
)  # 16 personas: 1/16 = 6,25 % (empate al redondear)
for clave, eid in (
    ("c2018", g2018[0]),
    ("c2018s", g2018s[0]),
    ("c2030", g2030[0]),
    ("c2040", g2040[0]),
):
    U[clave] = nuevo_usuario(f"{clave}@x.com")
    ejecutar(
        "update usuarios_app set egresado_id = %s where user_id = %s", (eid, U[clave])
    )
    ejecutar(
        "update egresados set situacion_origen = 'declarada_por_egresado' where id = %s",
        (eid,),
    )  # ya guardaron su información: el candado abre


def cohorte_de(usuario, rol="authenticated"):
    return llamar(usuario, "select public.mi_cohorte_en_cifras()", rol=rol)


est, r = cohorte_de("c2018")
c = r[0][0] if est == "ok" else {}
chequear(
    "promoción de 14 personas: devuelve las cifras (n=14, 8 empleados, 1 desempleado, 4 desconocidos, 1 estudiando)",
    est == "ok"
    and c.get("suficiente") is True
    and (
        c["n"],
        c["empleados"],
        c["desempleados"],
        c["desconocidos"],
        c["estudios_posteriores"],
    )
    == (14, 8, 1, 4, 1),
    c,
)
chequear(
    "las tasas coinciden (57,1 % sobre el total, 88,9 % sobre conocidos, 28,6 % desconocidos)",
    (
        c.get("tasa_sobre_total"),
        c.get("tasa_sobre_conocidos"),
        c.get("porcentaje_desconocido"),
    )
    == (57.1, 88.9, 28.6),
)
chequear(
    "NO cuenta ni al perfil pendiente de revisión ni al de otra fuente (el grupo sigue en 14, no 15 ni 16)",
    c.get("n") == 14,
)
chequear(
    "ciudades: solo las de 3 o más personas (Bucaramanga 5, Bogotá 3); Cali (2) y Cúcuta (1) se OCULTAN",
    c.get("ciudades") == {"Bucaramanga": 5, "Bogotá": 3} and c.get("con_ciudad") == 11,
    c.get("ciudades"),
)
chequear(
    "sectores: Telecomunicaciones 4 y Tecnología 3; Salud (1) se oculta",
    c.get("sectores") == {"Telecomunicaciones": 4, "Tecnología": 3},
    c.get("sectores"),
)
chequear(
    "tecnologías: Python 5 y Cisco 3; Linux (2) y Go (1) se ocultan, y la experiencia ya terminada (Rust) NO cuenta",
    c.get("tecnologias") == {"Python": 5, "Cisco": 3},
    c.get("tecnologias"),
)
chequear(
    "no se filtra nada de OTRA promoción (la ciudad Pasto, de 2019, no aparece)",
    "Pasto" not in str(c),
)
est, r = cohorte_de("c2030")
c30 = r[0][0] if est == "ok" else {}
chequear(
    "promoción de 4 personas (menos de 10): NO devuelve ninguna cifra, solo cuántos son y el mínimo",
    est == "ok"
    and c30 == {"suficiente": False, "cohorte": "2030", "n": 4, "minimo": 10},
    c30,
)
est, r = cohorte_de("c2018s")
chequear(
    "una persona sintética solo ve su fuente: su promoción sintética tiene 1 (no suma los 14 reales)",
    est == "ok" and r[0][0]["suficiente"] is False and r[0][0]["n"] == 1,
    r,
)
est, r = cohorte_de("c2040")
c40 = r[0][0] if est == "ok" else {}
chequear(
    "empate al redondear (1/16 = 6,25 % y 15/16 = 93,75 %): Postgres da 6,3 y 93,8",
    (c40.get("tasa_sobre_total"), c40.get("porcentaje_desconocido")) == (6.3, 93.8),
    c40,
)

filas_e = ejecutar(
    "select id::text, cohorte, fuente, situacion_laboral, ciudad_residencia, por_revisar from egresados"
)
filas_x = ejecutar(
    "select egresado_id::text, sector, tecnologias, fecha_fin from experiencia_laboral"
)
df_e = pd.DataFrame(
    filas_e,
    columns=[
        "id",
        "cohorte",
        "fuente",
        "situacion_laboral",
        "ciudad_residencia",
        "por_revisar",
    ],
)
df_x = pd.DataFrame(
    filas_x, columns=["egresado_id", "sector", "tecnologias", "fecha_fin"]
)
iguales = {}
for usuario, coh, fuente_ in (
    ("c2018", "2018", "real"),
    ("c2018s", "2018", "sintetico"),
    ("c2030", "2030", "real"),
    ("c2040", "2040", "real"),
):
    sql_res = cohorte_de(usuario)[1][0][0]
    iguales[usuario] = coh_mod.cifras_de_cohorte(df_e, df_x, coh, fuente_) == sql_res
chequear(
    "EL MOTOR DE PYTHON (demo) Y LA FUNCIÓN DE SQL (portal real) DAN EXACTAMENTE LO MISMO sobre los mismos datos, en los 4 casos",
    all(iguales.values()),
    iguales,
)

# EL CANDADO: la cohorte es una recompensa por participar; quien aún no guardó su información no la ve
U["cinst"] = nuevo_usuario("cinst@x.com")
ejecutar(
    "update usuarios_app set egresado_id = %s where user_id = %s",
    (g2018[1], U["cinst"]),
)  # vinculado a un registro institucional, sin haber guardado nada
est, r = cohorte_de("cinst")
chequear(
    "QUIEN AÚN NO GUARDÓ SU INFORMACIÓN no ve las cifras: la base de datos se lo niega con un aviso claro",
    est == "error" and "Primero guarda tu información" in r,
    r,
)
g2050 = grupo("2050", "real", [{"sit": DSC}] * 10)
U["cg"] = nuevo_usuario("cg@x.com")
ejecutar(
    "update usuarios_app set egresado_id = %s where user_id = %s", (g2050[0], U["cg"])
)
est, r = cohorte_de("cg")
chequear(
    "promoción de 10 (el mínimo justo), antes de guardar: se le niega",
    est == "error" and "Primero guarda tu información" in r,
    r,
)
est, r = guardar("cg", p_empresa="Independiente")
chequear(
    "la persona guarda su información con la función real del portal", est == "ok", r
)
est, r = cohorte_de("cg")
chequear(
    "y AL GUARDAR se le abre: ve su promoción (10 egresados)",
    est == "ok" and r[0][0]["suficiente"] is True and r[0][0]["n"] == 10,
    r,
)
U["huerfano"] = nuevo_usuario(
    "huerfano@x.com"
)  # cuenta recién creada, sin ningún perfil vinculado
est, r = cohorte_de("huerfano")
chequear(
    "una cuenta sin perfil vinculado recibe un aviso claro, no cifras",
    est == "error" and "no está vinculada" in r,
    r,
)
est, r = cohorte_de("admin")
chequear(
    "la administración (sin perfil de egresado) tampoco la usa: aviso claro",
    est == "error" and "no está vinculada" in r,
    r,
)
est, r = llamar(None, "select public.mi_cohorte_en_cifras()")
chequear("sin sesión iniciada: se rechaza", est == "error" and "iniciar sesión" in r, r)
est, r = llamar(None, "select public.mi_cohorte_en_cifras()", rol="anon")
chequear(
    "un visitante anónimo NO puede ejecutarla (permiso denegado)", est == "denegado", r
)

print("\n==== Que el SQL y la aplicación no se desincronicen ====")
sec_sql = re.search(r"v_sectores text\[\] := array\[(.*?)\];", SQL_2B, re.S).group(1)
area_sql = re.search(r"v_areas text\[\] := array\[(.*?)\];", SQL_2B, re.S).group(1)
parse = lambda s: re.findall(r"'([^']+)'", s)
chequear(
    "los sectores del SQL coinciden con taxonomia.py",
    parse(sec_sql) == taxonomia.SECTORES,
    set(parse(sec_sql)) ^ set(taxonomia.SECTORES),
)
chequear(
    "las áreas del SQL coinciden con taxonomia.py",
    parse(area_sql) == taxonomia.AREAS,
    set(parse(area_sql)) ^ set(taxonomia.AREAS),
)

print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
