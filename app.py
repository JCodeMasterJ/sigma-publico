import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from collections import Counter

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv

from cv_texto import CVError, preparar_texto_cv
from privacidad import resumen_informe
from taxonomia import AREAS, SECTORES

# Colombia no tiene horario de verano: UTC-5 fijo. Así la hora es la misma en tu computador y en la nube (que usa UTC).
HORA_COLOMBIA = timezone(timedelta(hours=-5))

load_dotenv()

st.set_page_config(
    page_title="SIGMA · Egresados Telecomunicaciones", page_icon="📡", layout="wide"
)

NAVY = "#0B2A5E"
GOLD = "#C9A227"
PALETA = [GOLD, NAVY, "#5B7FB9", "#E3C567", "#2F4C7E", "#8C9BB5"]

st.markdown(
    f"""
<style>
.metric-card {{
    background: linear-gradient(135deg, {NAVY} 0%, #123a7a 100%);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    color: white;
}}
.metric-card .valor {{ font-size: 2.1rem; font-weight: 700; color: {GOLD}; }}
.metric-card .etiqueta {{ font-size: 0.85rem; opacity: 0.85; }}
div[data-testid="stTabs"] button[aria-selected="true"] {{ color: {GOLD} !important; border-color: {GOLD} !important; }}
</style>
""",
    unsafe_allow_html=True,
)


def nuevo_cliente():
    """Un cliente NUEVO por sesión. Al iniciar sesión el cliente cambia sus propias cabeceras para llevar el
    token de esa persona, así que NUNCA debe compartirse entre usuarios (nada de @st.cache_resource aquí)."""
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])


def _con_columnas(filas, columnas):
    """DataFrame que siempre trae las columnas esperadas, aunque la tabla esté vacía."""
    df = pd.DataFrame(filas)
    for c in columnas:
        if c not in df.columns:
            df[c] = None
    return df


@st.cache_data(ttl=300)
def cargar_datos(user_id, _cliente):
    """`user_id` forma parte de la clave de caché: los datos de una cuenta nunca se reutilizan para otra."""
    client = _cliente
    egresados = _con_columnas(
        client.table("egresados").select("*").execute().data,
        [
            "id",
            "nombre",
            "cohorte",
            "situacion_laboral",
            "fuente",
            "ciudad_residencia",
            "pais_residencia",
            "email",
            "situacion_origen",
            "situacion_actualizada_en",
            "por_revisar",
            "fecha_registro",
        ],
    )
    experiencia = _con_columnas(
        client.table("experiencia_laboral").select("*").execute().data,
        [
            "egresado_id",
            "empresa",
            "cargo",
            "sector",
            "tecnologias",
            "tipo_empresa",
            "area_funcional",
            "clasificacion_origen",
            "fecha_fin",
        ],
    )
    # la hora se guarda JUNTO con los datos: así "Última actualización" dice cuándo se cargaron de verdad
    return egresados, experiencia, datetime.now(HORA_COLOMBIA)


def aplicar_filtros(egresados, fuente_sel, ventana_sel):
    df = egresados.copy()
    if fuente_sel != "Todos":
        df = df[df["fuente"] == fuente_sel.lower()]
    if ventana_sel == "Últimos 5 años (2021-2025)":
        anio_actual = datetime.now().year
        cohorte_valida = df["cohorte"].notna() & df["cohorte"].astype(str).str.isdigit()
        df = df[cohorte_valida]
        df = df[df["cohorte"].astype(int) >= anio_actual - 5]
    return df


def tasa_empleabilidad_por_cohorte(egresados_filtrados):
    tabla = (
        egresados_filtrados.groupby("cohorte")["situacion_laboral"]
        .value_counts(normalize=True)
        .unstack(fill_value=0)
        * 100
    )
    return tabla.round(1).sort_index()


def tecnologias_mas_frecuentes(experiencia_filtrada, top_n=10):
    todas = []
    for lista in experiencia_filtrada["tecnologias"].dropna():
        if isinstance(lista, list):
            todas.extend(lista)
    conteo = Counter(todas)
    return pd.DataFrame(conteo.most_common(top_n), columns=["Tecnología", "Menciones"])


def distribucion_sector(experiencia_filtrada):
    s = experiencia_filtrada["sector"].dropna()
    s = s[s != "No determinado"]
    return s.value_counts().rename_axis("Sector").reset_index(name="Egresados")


def distribucion_area(experiencia_filtrada):
    a = experiencia_filtrada["area_funcional"].dropna()
    a = a[a != "No determinada"]
    return a.value_counts().rename_axis("Área").reset_index(name="Egresados")


def conteos_clasificacion(experiencia_filtrada, campo, no_determinado):
    """(clasificadas, inferidas_por_IA, sin_clasificar, declaradas_por_el_egresado) para sector o área."""
    valores = experiencia_filtrada[campo]
    con_dato = valores.notna()
    sin_clasificar = int((valores == no_determinado).sum())
    clasificadas = int(con_dato.sum()) - sin_clasificar
    util = con_dato & (valores != no_determinado)
    inferidas = int(
        ((experiencia_filtrada["clasificacion_origen"] == "inferido_ia") & util).sum()
    )
    declaradas = int(
        ((experiencia_filtrada["clasificacion_origen"] == "declarado") & util).sum()
    )
    return clasificadas, inferidas, sin_clasificar, declaradas


def nota_clasificacion(clasificadas, inferidas, sin_clasificar, declaradas, plural):
    """Etiqueta visible: aclara qué parte de lo mostrado es inferencia de la IA y qué parte lo declaró la persona."""
    partes = []
    if inferidas:
        partes.append(
            f"🏷️ {inferidas} de {clasificadas} {plural} fueron **inferidos por IA** a partir de la empresa y el cargo; "
            "no son datos declarados por los egresados."
        )
    if declaradas:
        partes.append(
            f"✍️ {declaradas} fueron **declarados por los propios egresados** desde el portal."
        )
    resto = clasificadas - inferidas - declaradas
    if resto > 0:
        partes.append(
            "El resto son datos de ejemplo o extraídos de un CV."
            if (inferidas or declaradas)
            else "Datos de ejemplo (sintéticos)."
        )
    if sin_clasificar:
        partes.append(f"{sin_clasificar} sin clasificar.")
    return " ".join(partes)


def distribucion_ciudad(egresados_filtrados, top_n=10):
    if "ciudad_residencia" not in egresados_filtrados.columns:
        return pd.DataFrame(columns=["Ciudad", "Egresados"])
    return (
        egresados_filtrados["ciudad_residencia"]
        .dropna()
        .value_counts()
        .head(top_n)
        .rename_axis("Ciudad")
        .reset_index(name="Egresados")
    )


def metrica(col, etiqueta, valor):
    col.markdown(
        f'<div class="metric-card"><div class="etiqueta">{etiqueta}</div>'
        f'<div class="valor">{valor}</div></div>',
        unsafe_allow_html=True,
    )


OPCIONES_FUENTE = {
    "Solo datos reales (recomendado para acreditación)": "real",
    "Solo datos sintéticos (demostración)": "sintetico",
    "Reales + sintéticos (demostración)": "todos",
}
OPCIONES_VENTANA = {"Últimos 5 años": "5_anios", "Histórico completo": "historico"}


def pestana_reporte():
    st.subheader("Reporte narrativo para acreditación")
    st.caption(
        "Un agente de IA redacta el informe a partir de indicadores ya calculados. "
        "Los números los calcula el sistema, no la IA: cada afirmación cita el indicador que la "
        "sustenta y el sistema comprueba que las cifras del texto existan en los indicadores."
    )

    agentes_url = os.environ.get("AGENTES_URL", "").rstrip("/")
    agentes_key = os.environ.get("AGENTES_API_KEY", "")

    c1, c2 = st.columns(2)
    fuente_txt = c1.selectbox("Datos que usará el reporte", list(OPCIONES_FUENTE))
    ventana_txt = c2.selectbox("Periodo", list(OPCIONES_VENTANA))

    if not agentes_url:
        st.warning("Falta configurar AGENTES_URL (la dirección del servicio de IA).")
        return

    if st.button("Generar reporte", type="primary"):
        with st.spinner(
            "Analizando indicadores y redactando… la primera vez puede tardar cerca de un minuto mientras el servicio de IA despierta."
        ):
            try:
                resp = requests.post(
                    f"{agentes_url}/agentes/generar-reporte",
                    json={
                        "fuente": OPCIONES_FUENTE[fuente_txt],
                        "ventana": OPCIONES_VENTANA[ventana_txt],
                    },
                    headers={"x-api-key": agentes_key},
                    timeout=180,
                )
                if resp.status_code == 200:
                    st.session_state["reporte"] = resp.json()
                elif resp.status_code == 400:
                    st.warning(
                        resp.json().get("detail", "No hay datos para ese filtro.")
                    )
                elif resp.status_code == 401:
                    st.error(
                        "El dashboard no tiene la clave correcta para el servicio de IA (AGENTES_API_KEY)."
                    )
                else:
                    st.error(
                        f"El servicio de IA respondió con un error ({resp.status_code}): {resp.text[:300]}"
                    )
            except requests.exceptions.RequestException:
                st.error(
                    "No se pudo conectar con el servicio de IA. Intenta de nuevo en un minuto."
                )

    reporte = st.session_state.get("reporte")
    if not reporte:
        st.info("Elige los datos y el periodo, y pulsa «Generar reporte».")
        return

    st.divider()
    ver = reporte["verificacion"]
    if (
        ver["citas_invalidas"]
        or ver["hallazgos_sin_cita"]
        or ver["cifras_sin_respaldo"]
    ):
        st.warning(
            "**Verificación automática: revisar antes de usar este texto.**\n\n"
            + (
                f"- Cifras del texto que no aparecen en los indicadores: {', '.join(ver['cifras_sin_respaldo'])}\n"
                if ver["cifras_sin_respaldo"]
                else ""
            )
            + (
                f"- Citas a indicadores que no existen: {', '.join(ver['citas_invalidas'])}\n"
                if ver["citas_invalidas"]
                else ""
            )
            + (
                f"- Hallazgos sin cita: {len(ver['hallazgos_sin_cita'])}\n"
                if ver["hallazgos_sin_cita"]
                else ""
            )
        )
    else:
        st.success(
            "Verificación automática: las cifras del texto coinciden con los indicadores y cada hallazgo cita su fuente."
        )
    if reporte.get("advertencia"):
        st.caption(reporte["advertencia"])

    # Los gráficos primero: se entienden de un vistazo y reducen lo que hay que leer. Un fallo al dibujarlos nunca esconde el informe.
    try:
        from graficos_reporte import figuras_del_reporte

        figuras = figuras_del_reporte(reporte["indicadores"])
        if figuras:
            st.markdown("### Panorama en gráficos")
        pendientes = []
        for f in figuras:
            if f["ancho"] == "completo":
                st.plotly_chart(f["figura"], use_container_width=True)
                st.caption(f["pie"])
            else:
                pendientes.append(f)
        for i in range(0, len(pendientes), 2):
            for col, f in zip(st.columns(2), pendientes[i : i + 2]):
                with col:
                    st.plotly_chart(f["figura"], use_container_width=True)
                    st.caption(f["pie"])
    except Exception:  # noqa: BLE001
        st.caption(
            "No se pudieron dibujar los gráficos; el informe escrito y el PDF siguen disponibles."
        )

    with st.expander(
        "Informe redactado: resumen, hallazgos, limitaciones y recomendaciones",
        expanded=True,
    ):
        st.markdown(reporte["narrativa_markdown"])

    try:
        from informe_pdf import generar_pdf

        st.download_button(
            "⬇️ Descargar informe en PDF",
            data=generar_pdf(reporte),
            file_name=f"informe_sigma_{datetime.now():%Y%m%d}.pdf",
            mime="application/pdf",
        )
    except ImportError:
        st.caption(
            "Para descargar el PDF falta instalar la librería fpdf2 en este entorno."
        )
    except (
        Exception
    ) as e:  # un fallo del PDF nunca debe tumbar la visualización del reporte
        st.caption(f"No se pudo generar el PDF: {e}")

    with st.expander("Ver los indicadores exactos que recibió la IA"):
        st.json(reporte["indicadores"])


def vista_admin(auth):
    egresados, experiencia, cargado_en = cargar_datos(auth["user_id"], auth["cliente"])

    with st.sidebar:
        st.header("Filtros")
        fuente_sel = st.radio(
            "Datos a mostrar", ["Todos", "Real", "Sintetico"], index=0
        )
        ventana_sel = st.radio(
            "Periodo", ["Histórico completo", "Últimos 5 años (2021-2025)"], index=1
        )
        st.caption(f"Última actualización: {cargado_en.strftime('%d/%m/%Y %H:%M')}")
        # on_click se ejecuta ANTES de que la página se vuelva a dibujar: al hacer clic ya se cargan datos nuevos
        st.button(
            "🔄 Actualizar datos",
            on_click=cargar_datos.clear,
            help="Los datos se guardan 5 minutos. Úsalo para ver de inmediato lo que acaban de registrar.",
        )

    egresados_f = aplicar_filtros(egresados, fuente_sel, ventana_sel)
    # solo la experiencia vigente (sin fecha de fin): la que cerró un egresado al cambiar de situación no cuenta como actual
    vigentes = experiencia[experiencia["fecha_fin"].isna()]
    experiencia_f = vigentes[vigentes["egresado_id"].isin(egresados_f["id"])]
    n_por_revisar = int((egresados["por_revisar"] == True).sum())  # noqa: E712

    tab_indicadores, tab_directorio, tab_reporte, tab_revisar = st.tabs(
        [
            "📊 Indicadores",
            "🔎 Directorio de egresados",
            "📝 Reporte de acreditación",
            f"🧾 Por revisar ({n_por_revisar})",
        ]
    )

    with tab_indicadores:
        total = len(egresados_f)
        empleados = (egresados_f["situacion_laboral"] == "empleado").sum()
        tasa_general = (empleados / total * 100) if total else 0

        desempleados = (egresados_f["situacion_laboral"] == "desempleado").sum()
        desconocidos = (egresados_f["situacion_laboral"] == "desconocido").sum()
        conocidos = empleados + desempleados
        # Misma definición que usa el agente de reportes: empleados / (empleados + desempleados)
        tasa_conocidos = f"{empleados / conocidos * 100:.1f}%" if conocidos else "n/d"
        pct_desconocido = (desconocidos / total * 100) if total else 0

        c1, c2, c3, c4 = st.columns(4)
        metrica(c1, "Egresados en esta vista", total)
        metrica(c2, "Empleabilidad (sobre el total)", f"{tasa_general:.1f}%")
        metrica(c3, "Empleabilidad (sobre conocidos)", tasa_conocidos)
        metrica(c4, "Situación laboral desconocida", f"{pct_desconocido:.1f}%")
        st.caption(
            "«Sobre el total» incluye en el denominador a los egresados de situación desconocida; "
            "«sobre conocidos» los excluye y puede no representar a toda la población."
        )
        declaradas = int(
            (egresados_f["situacion_origen"] == "declarada_por_egresado").sum()
        )
        st.caption(
            f"✍️ Situación declarada por el propio egresado desde el portal (con fecha): {declaradas} de {total}."
        )

        st.write("")
        st.subheader("Empleabilidad por cohorte")
        tabla_emp = tasa_empleabilidad_por_cohorte(egresados_f)
        if not tabla_emp.empty:
            etiquetas = {
                "empleado": "Empleado",
                "desempleado": "Desempleado",
                "estudios_posteriores": "Estudiando",
                "desconocido": "Situación desconocida",
            }
            # "Estudiando" solo aparece (barra y leyenda) si hay alguien así en la vista actual
            hay_estudiando = (
                "estudios_posteriores" in tabla_emp.columns
                and tabla_emp["estudios_posteriores"].sum() > 0
            )
            if not hay_estudiando:
                etiquetas.pop("estudios_posteriores")
            largo = (
                tabla_emp.reindex(columns=list(etiquetas), fill_value=0)
                .rename(columns=etiquetas)
                .reset_index()
                .melt(id_vars="cohorte", var_name="Situación", value_name="Porcentaje")
            )
            fig = px.bar(
                largo,
                x="cohorte",
                y="Porcentaje",
                color="Situación",
                barmode="stack",
                color_discrete_map={
                    "Empleado": GOLD,
                    "Desempleado": "#5B7FB9",
                    "Estudiando": "#7FB7A4",
                    "Situación desconocida": "#4A4F5C",
                },
                category_orders={"Situación": list(etiquetas.values())},
                labels={"cohorte": "Cohorte"},
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", yaxis_ticksuffix="%", legend_title_text=""
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "La parte gris son egresados cuya situación laboral no se conoce: "
                "no equivale a desempleo. Una cohorte con mucho gris tiene poca información, no baja empleabilidad."
                + (
                    " «Estudiando» agrupa a quienes declaran estar estudiando (posgrado, idiomas u otros): "
                    "no cuentan como empleo ni como desempleo."
                    if hay_estudiando
                    else ""
                )
            )
        else:
            st.info(
                "No hay suficientes datos para esta vista con los filtros actuales."
            )

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Tecnologías más mencionadas")
            tech = tecnologias_mas_frecuentes(experiencia_f)
            if not tech.empty:
                fig = px.bar(
                    tech,
                    x="Menciones",
                    y="Tecnología",
                    orientation="h",
                    color_discrete_sequence=[NAVY],
                )
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(categoryorder="total ascending"),
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption(
                    "Salen de texto escrito por la propia persona (CV o biografía); no se infieren desde la empresa."
                )
            else:
                st.info(
                    "Sin datos en esta vista. Las tecnologías solo salen de texto que escribió la persona "
                    "(CV o biografía); no se infieren desde la empresa. Con 'Sintético' hay datos de ejemplo."
                )
        with col_b:
            st.subheader("Distribución por sector")
            sector = distribucion_sector(experiencia_f)
            if not sector.empty:
                fig = px.pie(
                    sector,
                    names="Sector",
                    values="Egresados",
                    color_discrete_sequence=PALETA,
                    hole=0.45,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sin datos de sector en esta vista.")
            nota = nota_clasificacion(
                *conteos_clasificacion(experiencia_f, "sector", "No determinado"),
                "experiencias con sector",
            )
            if nota:
                st.caption(nota)

        col_c, col_d = st.columns(2)
        with col_c:
            st.subheader("Áreas de desempeño")
            area = distribucion_area(experiencia_f)
            if not area.empty:
                fig = px.bar(
                    area,
                    x="Egresados",
                    y="Área",
                    orientation="h",
                    color_discrete_sequence=[NAVY],
                )
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(categoryorder="total ascending"),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(
                    "Sin datos de área en esta vista. El área se calcula para egresados reales a partir del cargo; "
                    "los datos sintéticos no la incluyen."
                )
            nota = nota_clasificacion(
                *conteos_clasificacion(
                    experiencia_f, "area_funcional", "No determinada"
                ),
                "experiencias con área",
            )
            if nota:
                st.caption(nota)
        with col_d:
            st.subheader("📍 Ubicación de egresados")
            ciudad = distribucion_ciudad(egresados_f)
            if not ciudad.empty:
                fig = px.bar(
                    ciudad, x="Ciudad", y="Egresados", color_discrete_sequence=[GOLD]
                )
                fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sin datos de ciudad en esta vista.")

    with tab_directorio:
        st.subheader("Buscar egresados")
        busqueda = st.text_input(
            "Buscar por nombre", placeholder="Escribe un nombre..."
        )
        directorio = egresados_f.merge(
            experiencia_f[["egresado_id", "empresa", "cargo"]],
            left_on="id",
            right_on="egresado_id",
            how="left",
        )
        if busqueda:
            directorio = directorio[
                directorio["nombre"].str.contains(busqueda, case=False, na=False)
            ]
        columnas = [
            "nombre",
            "cohorte",
            "situacion_laboral",
            "empresa",
            "cargo",
            "ciudad_residencia",
            "fuente",
        ]
        columnas_presentes = [c for c in columnas if c in directorio.columns]
        st.dataframe(
            directorio[columnas_presentes], use_container_width=True, hide_index=True
        )

    with tab_reporte:
        pestana_reporte()

    with tab_revisar:
        pestana_por_revisar(auth, egresados, vigentes)


# ---------------------------------------------------------------------------
# Acceso: inicio de sesión, registro y roles
# ---------------------------------------------------------------------------
MIN_CLAVE = 8


def traducir_error_auth(e: Exception) -> str:
    m = str(e).lower()
    if "invalid login credentials" in m:
        return "Correo o contraseña incorrectos."
    if "email not confirmed" in m:
        return (
            "Aún no has confirmado tu correo. Escribe el código que te enviamos en la pestaña «Confirmar correo» "
            "(ahí mismo puedes pedir uno nuevo)."
        )
    if "token has expired" in m or "otp_expired" in m or "otp" in m and "invalid" in m:
        return "El código no es válido o ya venció. Pide uno nuevo con «Reenviar código» y usa el más reciente."
    if "not authorized" in m and "email" in m:
        return (
            "Este correo todavía no puede recibir mensajes del sistema: el servicio de correo de pruebas solo envía a "
            "miembros del equipo. Avisa a la administración del proyecto."
        )
    if "only request this after" in m:
        return "Espera un minuto antes de pedir otro correo."
    if "rate limit" in m or "over_email_send_rate_limit" in m or "too many" in m:
        return "Se hicieron demasiados intentos o envíos de correo en poco tiempo. Espera unos minutos e inténtalo de nuevo."
    if "already registered" in m or "already been registered" in m:
        return "Ese correo ya tiene una cuenta. Usa la pestaña «Iniciar sesión»."
    if "password" in m and ("least" in m or "weak" in m or "short" in m):
        return f"La contraseña es muy débil. Usa al menos {MIN_CLAVE} caracteres."
    return "No se pudo completar la operación. Inténtalo de nuevo en un momento."


def _abrir_sesion(cliente, usuario, correo: str):
    """Lee el rol de la cuenta y deja la sesión en st.session_state['auth']. Devuelve (ok, mensaje)."""
    try:
        fila = (
            cliente.table("usuarios_app")
            .select("rol,egresado_id")
            .eq("user_id", usuario.id)
            .execute()
            .data
        )
    except Exception as e:  # noqa: BLE001
        return False, traducir_error_auth(e)
    rol = fila[0]["rol"] if fila else "egresado"
    st.session_state["auth"] = {
        "cliente": cliente,
        "user_id": usuario.id,
        "email": usuario.email or correo.strip(),
        "rol": rol,
        "egresado_id": fila[0].get("egresado_id") if fila else None,
    }
    st.session_state.pop("pendiente_confirmar", None)
    return True, ""


def iniciar_sesion(correo: str, clave: str):
    """Devuelve (ok, mensaje). Si es ok, deja la sesión en st.session_state['auth']."""
    cliente = nuevo_cliente()  # uno por sesión
    try:
        resp = cliente.auth.sign_in_with_password(
            {"email": correo.strip(), "password": clave}
        )
    except Exception as e:  # noqa: BLE001
        return False, traducir_error_auth(e)
    return _abrir_sesion(cliente, resp.user, correo)


def confirmar_codigo(correo: str, codigo: str):
    """Confirma la cuenta con el código de 6 dígitos del correo. Si es correcto, la persona queda con la sesión iniciada."""
    correo, codigo = correo.strip(), re.sub(r"\s+", "", codigo or "")
    if "@" not in correo or "." not in correo.split("@")[-1]:
        return False, "Escribe el correo con el que te registraste."
    if not re.fullmatch(r"\d{6,10}", codigo):
        return (
            False,
            "El código son solo números (6 dígitos). Cópialo tal como llegó al correo.",
        )
    cliente = nuevo_cliente()
    try:
        resp = cliente.auth.verify_otp(
            {"email": correo, "token": codigo, "type": "signup"}
        )
        if resp.user is None:
            return False, traducir_error_auth(
                Exception("token has expired or is invalid")
            )
    except Exception as e:  # noqa: BLE001
        return False, traducir_error_auth(e)
    return _abrir_sesion(cliente, resp.user, correo)


def crear_cuenta(correo: str, clave: str, clave2: str):
    if "@" not in correo or "." not in correo.split("@")[-1]:
        return False, "Escribe un correo válido."
    if len(clave) < MIN_CLAVE:
        return False, f"La contraseña debe tener al menos {MIN_CLAVE} caracteres."
    if clave != clave2:
        return False, "Las contraseñas no coinciden."
    try:
        nuevo_cliente().auth.sign_up({"email": correo.strip(), "password": clave})
    except Exception as e:  # noqa: BLE001
        return False, traducir_error_auth(e)
    st.session_state["pendiente_confirmar"] = correo.strip()
    return True, (
        f"Te enviamos un código de 6 dígitos a {correo.strip()}. Escríbelo en el Paso 2 para activar tu cuenta. "
        "Si no llega en unos minutos, revisa la carpeta de spam."
    )


def reenviar_confirmacion(correo: str):
    """Pide un código NUEVO (el anterior deja de servir). No revela si el correo tiene cuenta."""
    if "@" not in correo or "." not in correo.split("@")[-1]:
        return False, "Escribe un correo válido."
    try:
        nuevo_cliente().auth.resend({"type": "signup", "email": correo.strip()})
    except Exception as e:  # noqa: BLE001
        return False, traducir_error_auth(e)
    return True, (
        "Si ese correo tiene una cuenta pendiente de confirmar, le enviamos un código nuevo. "
        "Usa el más reciente: los anteriores dejan de servir."
    )


def cerrar_sesion():
    auth = st.session_state.get("auth")
    if auth:
        try:
            auth["cliente"].auth.sign_out()
        except Exception:  # noqa: BLE001
            pass
    st.session_state.clear()  # también borra el último reporte generado: no debe verlo la siguiente persona


def sesion_vigente(auth) -> bool:
    """get_session() renueva el token si está por vencer; si ya no hay sesión, se saca a la persona."""
    try:
        return auth["cliente"].auth.get_session() is not None
    except Exception:  # noqa: BLE001
        return False


def formulario_codigo(prefijo: str):
    """Correo + código de 6 dígitos. Se usa en el 'Paso 2' del registro y en la pestaña 'Confirmar correo'."""
    clave_correo = f"cod_correo_{prefijo}"
    if clave_correo not in st.session_state and st.session_state.get(
        "pendiente_confirmar"
    ):
        st.session_state[clave_correo] = st.session_state["pendiente_confirmar"]
    correo = st.text_input("Correo con el que te registraste", key=clave_correo)
    with st.form(f"form_codigo_{prefijo}"):
        codigo = st.text_input(
            "Código de 6 dígitos", max_chars=12, key=f"cod_codigo_{prefijo}"
        )
        if st.form_submit_button("Confirmar y entrar", type="primary"):
            ok, msg = confirmar_codigo(correo, codigo)
            if ok:
                st.rerun()
            st.error(msg)
    if st.button("Reenviar código", key=f"cod_reenviar_{prefijo}"):
        ok, msg = reenviar_confirmacion(correo)
        (st.success if ok else st.error)(msg)


def pantalla_acceso(aviso: str = ""):
    _, centro, _ = st.columns([1, 1.4, 1])
    with centro:
        if aviso:
            st.warning(aviso)
        tab_in, tab_nueva, tab_codigo = st.tabs(
            ["Iniciar sesión", "Crear cuenta", "Confirmar correo"]
        )
        with tab_in:
            st.caption(
                "¿Te acabas de registrar? Primero confirma tu correo con el código, en la pestaña «Confirmar correo»."
            )
            with st.form("form_login"):
                correo = st.text_input("Correo")
                clave = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Entrar", type="primary"):
                    ok, msg = iniciar_sesion(correo, clave)
                    if ok:
                        st.rerun()
                    st.error(msg)
        with tab_nueva:
            st.caption(
                "Para egresados de la facultad. Usamos tu correo solo para tu acceso."
            )
            with st.form("form_registro"):
                correo = st.text_input("Correo", key="reg_correo")
                clave = st.text_input(
                    f"Contraseña (mínimo {MIN_CLAVE} caracteres)",
                    type="password",
                    key="reg_clave",
                )
                clave2 = st.text_input(
                    "Repite la contraseña", type="password", key="reg_clave2"
                )
                if st.form_submit_button("Crear cuenta"):
                    ok, msg = crear_cuenta(correo, clave, clave2)
                    (st.success if ok else st.error)(msg)
            if st.session_state.get("pendiente_confirmar"):
                st.markdown("**Paso 2.** Escribe el código que te llegó al correo.")
                formulario_codigo("registro")
        with tab_codigo:
            st.caption(
                "Si ya te registraste y todavía no confirmas tu correo, escribe aquí el código que te enviamos. "
                "¿Se perdió o venció? Pide uno nuevo con «Reenviar código»."
            )
            formulario_codigo("tab")


# ---------------------------------------------------------------------------
# Portal del egresado ("Mi perfil") y revisión de perfiles nuevos
# ---------------------------------------------------------------------------
CONSENTIMIENTO_RESUMEN = (
    "Autorizo a la Facultad de Ingeniería de Telecomunicaciones de la Universidad Santo Tomás a tratar los datos que "
    "registro aquí para el seguimiento a egresados y los procesos de acreditación."
)
CONSENTIMIENTO_TEXTO = """
**⚠️ BORRADOR: este texto debe reemplazarse por el texto oficial de la Universidad Santo Tomás
(Política de Tratamiento de Datos Personales y formato de autorización, Ley 1581 de 2012).**

- **Qué datos:** situación laboral, empresa, cargo, ciudad y país de residencia y, si los diligencias, sector, área de
  desempeño y tecnologías.
- **Para qué:** conocer la trayectoria de los egresados, calcular indicadores de empleabilidad y apoyar los procesos de
  acreditación de la Facultad.
- **Cómo se usan:** los informes y gráficos presentan datos agregados. Tu información individual solo la ve el personal
  autorizado de la Facultad.
- **Tus derechos:** puedes conocer, actualizar, rectificar o solicitar la supresión de tus datos, y revocar esta
  autorización, escribiendo a la administración del programa.
"""
OPCIONES_SITUACION = {
    "Estoy empleado/a (o trabajo de forma independiente)": "empleado",
    "Estoy buscando empleo": "desempleado",
    "Estoy estudiando (posgrado, idiomas u otros)": "estudios_posteriores",
}
SIN_RESPUESTA = "(prefiero no decirlo)"


def mensaje_error_sigma(e: Exception) -> str:
    """Las funciones de la base de datos escriben sus avisos con el prefijo 'SIGMA:'. Solo se muestran esos."""
    texto = str(getattr(e, "message", None) or e)
    if "SIGMA:" in texto:
        return texto.split("SIGMA:", 1)[1].split("\n")[0].strip().rstrip("'\"}")
    return "No se pudo completar la operación. Inténtalo de nuevo en un momento."


def llamar_funcion(auth, nombre, parametros=None):
    return auth["cliente"].rpc(nombre, parametros or {}).execute().data


def formulario_crear_perfil(auth):
    st.info(
        "No encontramos tu correo entre los registros de la facultad. Cuéntanos quién eres y crearemos tu perfil; "
        "la administración lo revisará para evitar duplicados."
    )
    with st.form("form_crear_perfil"):
        nombre = st.text_input("Nombre completo")
        anio = st.number_input(
            "Año de grado",
            min_value=1980,
            max_value=datetime.now().year + 1,
            value=datetime.now().year - 1,
            step=1,
        )
        if st.form_submit_button("Crear mi perfil", type="primary"):
            try:
                auth["egresado_id"] = llamar_funcion(
                    auth,
                    "crear_mi_perfil",
                    {"p_nombre": nombre, "p_anio_grado": int(anio)},
                )
            except Exception as e:  # noqa: BLE001
                st.error(mensaje_error_sigma(e))
            else:
                cargar_datos.clear()  # que el perfil nuevo aparezca en "Por revisar" sin esperar
                st.rerun()


def _vigente(filas):
    return filas[0] if filas else {}


PRIVACIDAD_CV = (
    "Tu PDF se lee en memoria y **no se guarda**. Antes de enviar el texto a la IA le quitamos tu nombre, correos, teléfonos, "
    "direcciones, documentos y enlaces. La IA es el plan **gratuito** de Google Gemini: según sus términos, Google puede usar los "
    "textos que recibe para mejorar sus productos. Si prefieres no usar esta opción, llena el formulario a mano."
)


def analizar_cv(auth, datos: bytes, nombre: str):
    """
    PDF -> sugerencia para el formulario. Devuelve (ok, mensaje, sugerencia, informe, texto_enviado).
    Nunca lanza: todo problema llega como un mensaje para la persona, y el formulario manual sigue disponible.
    Orden: (1) leer y limpiar en ESTE servidor, (2) contar el uso, (3) solo entonces enviar el texto limpio.
    """
    try:
        texto, informe = preparar_texto_cv(datos, nombre)
    except CVError as e:
        return False, str(e), None, None, None
    try:
        llamar_funcion(auth, "registrar_uso_cv")
    except Exception as e:  # noqa: BLE001
        return False, mensaje_error_sigma(e), None, None, None
    url = os.environ.get("AGENTES_URL", "").rstrip("/")
    if not url:
        return (
            False,
            "El análisis de CV no está disponible en este entorno. Llena el formulario a mano.",
            None,
            None,
            None,
        )
    try:
        resp = requests.post(
            f"{url}/agentes/sugerir-perfil",
            json={"texto": texto},
            headers={"x-api-key": os.environ.get("AGENTES_API_KEY", "")},
            timeout=120,
        )
    except requests.exceptions.RequestException:
        return (
            False,
            (
                "El servicio de IA tardó demasiado o no respondió. Inténtalo en un minuto o llena el formulario a mano."
            ),
            None,
            None,
            None,
        )
    if resp.status_code == 200:
        return True, "", resp.json().get("sugerencia") or {}, informe, texto
    if resp.status_code == 502:
        return (
            False,
            "El servicio de IA está ocupado en este momento. Inténtalo en un minuto o llena el formulario a mano.",
            None,
            None,
            None,
        )
    return (
        False,
        "No pudimos analizar tu CV en este momento. Llena el formulario a mano.",
        None,
        None,
        None,
    )


def seccion_cv(auth, perfil):
    ronda = st.session_state.get("cv_ronda", 0)
    sug = st.session_state.get("sugerencia_cv")
    with st.expander(
        "📄 ¿Tienes tu CV en PDF? Deja que el sistema te proponga los datos",
        expanded=bool(sug),
    ):
        st.caption(
            "Subes tu CV, el sistema propone empresa, cargo, sector, área y tecnologías, y tú lo revisas y lo corriges "
            "antes de guardar. Tu situación laboral la eliges tú."
        )
        st.markdown(PRIVACIDAD_CV)
        archivo = st.file_uploader(
            "Tu CV en PDF (máximo 5 MB)", type=["pdf"], key=f"cv_archivo_{ronda}"
        )
        acepto = st.checkbox(
            "Entiendo cómo se procesa mi CV y quiero continuar",
            key=f"cv_acepto_{ronda}",
        )
        if st.button(
            "Analizar mi CV",
            disabled=not (archivo and acepto),
            key=f"cv_analizar_{ronda}",
        ):
            with st.spinner(
                "Leyendo tu CV… si el servicio estaba dormido puede tardar cerca de un minuto."
            ):
                ok, msg, sugerencia, informe, texto = analizar_cv(
                    auth, archivo.getvalue(), perfil["nombre"]
                )
            if ok:
                (
                    st.session_state["sugerencia_cv"],
                    st.session_state["informe_cv"],
                    st.session_state["texto_enviado_cv"],
                ) = sugerencia, informe, texto
                st.rerun()
            st.error(msg)
        if sug:
            st.success(
                "Listo: rellenamos el formulario con lo que entendimos de tu CV. Revísalo y corrígelo antes de guardar."
            )
            st.caption(
                "Antes de enviarlo a la IA quitamos: "
                + resumen_informe(st.session_state.get("informe_cv") or {})
                + ". Tu PDF no se guardó."
            )
            descartadas = sug.get("descartadas", 0)
            st.caption(
                "Verificamos por código que lo propuesto esté escrito en tu CV: "
                + (
                    f"descartamos {descartadas} {'sugerencia' if descartadas == 1 else 'sugerencias'} de la IA que no aparecían en él."
                    if descartadas
                    else "todo aparece en él."
                )
            )
            with st.expander("Ver el texto exacto que se envió a la IA"):
                st.text(st.session_state.get("texto_enviado_cv", ""))


def _unir_tecnologias(texto: str, extras) -> list:
    """Lo escrito en el campo + lo marcado en la lista, sin repetir (sin importar mayúsculas)."""
    vistas, salida = set(), []
    for t in [x.strip() for x in texto.split(",")] + [
        str(x).strip() for x in (extras or [])
    ]:
        if t and t.lower() not in vistas:
            vistas.add(t.lower())
            salida.append(t)
    return salida or None


def formulario_perfil(auth):
    cli, eid = auth["cliente"], auth["egresado_id"]
    try:  # la base de datos solo deja leer lo propio
        perfil = _vigente(
            cli.table("egresados")
            .select(
                "nombre,cohorte,situacion_laboral,ciudad_residencia,pais_residencia,consentimiento_datos,"
                "situacion_actualizada_en,situacion_origen,por_revisar"
            )
            .eq("id", eid)
            .execute()
            .data
        )
        exp = _vigente(
            cli.table("experiencia_laboral")
            .select(
                "empresa,cargo,sector,area_funcional,tecnologias,clasificacion_origen"
            )
            .eq("egresado_id", eid)
            .is_("fecha_fin", "null")
            .limit(1)
            .execute()
            .data
        )
    except Exception:  # noqa: BLE001
        st.error("No pudimos cargar tu perfil. Inténtalo de nuevo en un momento.")
        return
    if not perfil:
        st.error("No encontramos tu registro. Escribe a la administración.")
        return

    if st.session_state.get("aviso_guardado"):
        st.success(st.session_state.pop("aviso_guardado"))
    st.markdown(f"Hola, **{perfil['nombre']}** · cohorte {perfil['cohorte']}")
    if perfil.get("por_revisar"):
        st.caption(
            "Tu perfil se creó desde el portal y está pendiente de revisión por la administración."
        )
    if perfil.get("situacion_origen") == "declarada_por_egresado" and perfil.get(
        "situacion_actualizada_en"
    ):
        st.caption(
            f"Última actualización tuya: {str(perfil['situacion_actualizada_en'])[:10]}"
        )
    else:
        st.info(
            "La facultad tiene un dato antiguo sobre ti, sin fecha. Confírmalo o actualízalo: toma un minuto."
        )

    seccion_cv(auth, perfil)
    sug = (
        st.session_state.get("sugerencia_cv") or {}
    )  # lo propuesto desde el CV: solo precarga, la persona decide
    claves = list(OPCIONES_SITUACION.values())
    actual = perfil.get("situacion_laboral")
    with st.form("form_perfil"):
        etiqueta = st.radio(
            "¿Cuál es tu situación actual?",
            list(OPCIONES_SITUACION),
            index=claves.index(actual) if actual in claves else None,
        )
        c1, c2 = st.columns(2)
        empresa = c1.text_input(
            "Empresa (si trabajas)",
            value=sug.get("empresa") or exp.get("empresa") or "",
        )
        cargo = c2.text_input("Cargo", value=sug.get("cargo") or exp.get("cargo") or "")
        c3, c4 = st.columns(2)
        # la ciudad y el país propuestos son los del ENCABEZADO del CV (donde vive); si difieren de lo registrado, se avisa abajo
        ciudad = c3.text_input(
            "Ciudad donde vives",
            value=sug.get("ciudad") or perfil.get("ciudad_residencia") or "",
        )
        pais = c4.text_input(
            "País donde vives",
            value=sug.get("pais") or perfil.get("pais_residencia") or "",
        )
        antes = [
            x
            for x in (perfil.get("ciudad_residencia"), perfil.get("pais_residencia"))
            if x
        ]
        if (
            (sug.get("ciudad") or sug.get("pais"))
            and antes
            and (
                sug.get("ciudad") != perfil.get("ciudad_residencia")
                or sug.get("pais") != perfil.get("pais_residencia")
            )
        ):
            st.caption(
                "Ciudad y país propuestos desde el encabezado de tu CV. Antes teníamos: "
                + ", ".join(antes)
                + ". Déjalo como esté si lo anterior sigue siendo correcto."
            )

        with st.expander("Opcional: sector, área y tecnologías", expanded=bool(sug)):
            if sug:
                st.caption(
                    "Propuesto a partir de tu CV. Revísalo y corrígelo si hace falta."
                )
            if exp.get("clasificacion_origen") == "inferido_ia" and (
                exp.get("sector") or exp.get("area_funcional")
            ):
                st.caption(
                    f"La facultad estimó con IA tu sector ({exp.get('sector') or '—'}) y tu área "
                    f"({exp.get('area_funcional') or '—'}). Puedes confirmarlo o corregirlo aquí."
                )

            def _indice(lista, valor, sugerido=None):
                if sugerido in lista:
                    return lista.index(sugerido) + 1
                return (
                    lista.index(valor) + 1
                    if (
                        exp.get("clasificacion_origen") == "declarado"
                        and valor in lista
                    )
                    else 0
                )

            sector = st.selectbox(
                "Sector de tu empresa",
                [SIN_RESPUESTA] + SECTORES,
                index=_indice(SECTORES, exp.get("sector"), sug.get("sector")),
            )
            area = st.selectbox(
                "Área de tu trabajo",
                [SIN_RESPUESTA] + AREAS,
                index=_indice(AREAS, exp.get("area_funcional"), sug.get("area")),
            )
            ya = list(exp.get("tecnologias") or [])
            nuevas = [
                t
                for t in (sug.get("tecnologias") or [])
                if t.lower() not in {x.lower() for x in ya}
            ]
            tecnologias = st.text_input(
                "Tecnologías que usas (separadas por comas)",
                value=", ".join(ya + nuevas),
            )
            if sug and ya:
                st.caption(
                    "Ya tenías registradas: "
                    + ", ".join(ya)
                    + ". De tu CV agregamos: "
                    + (", ".join(nuevas) if nuevas else "ninguna nueva")
                    + "."
                )
            en_campo = {x.lower() for x in ya + nuevas}
            otras = [
                t
                for t in (sug.get("otras_tecnologias") or [])
                if t.lower() not in en_campo
            ]
            extras = []
            if otras:
                extras = st.multiselect(
                    "Otras tecnologías, certificaciones y temas que encontramos en tu CV (marca las que quieras agregar)",
                    otras,
                )

        acepto = st.checkbox(
            CONSENTIMIENTO_RESUMEN, value=bool(perfil.get("consentimiento_datos"))
        )
        with st.expander("Ver el texto completo de la autorización"):
            st.markdown(CONSENTIMIENTO_TEXTO)

        if st.form_submit_button("Guardar mi información", type="primary"):
            parametros = {
                "p_situacion": OPCIONES_SITUACION.get(etiqueta),
                "p_ciudad": ciudad,
                "p_pais": pais,
                "p_empresa": empresa,
                "p_cargo": cargo,
                "p_sector": None if sector == SIN_RESPUESTA else sector,
                "p_area": None if area == SIN_RESPUESTA else area,
                "p_tecnologias": _unir_tecnologias(tecnologias, extras),
                "p_consentimiento": bool(acepto),
            }
            try:
                llamar_funcion(auth, "guardar_mi_perfil", parametros)
            except Exception as e:  # noqa: BLE001
                st.error(mensaje_error_sigma(e))
            else:
                cargar_datos.clear()  # que el dashboard de la administración vea el cambio
                for k in ("sugerencia_cv", "informe_cv", "texto_enviado_cv"):
                    st.session_state.pop(k, None)
                st.session_state["cv_ronda"] = st.session_state.get("cv_ronda", 0) + 1
                st.session_state["aviso_guardado"] = (
                    "¡Gracias! Tu información quedó guardada."
                )
                st.rerun()


def vista_egresado(auth):
    st.subheader("👋 Mi perfil")
    if not auth.get("egresado_id"):
        if auth.get("vinculo") == "sin_coincidencia":
            formulario_crear_perfil(auth)
            return
        try:
            res = llamar_funcion(auth, "vincular_mi_registro") or {}
        except Exception as e:  # noqa: BLE001
            st.error(mensaje_error_sigma(e))
            return
        estado = res.get("estado") if isinstance(res, dict) else None
        if estado in ("vinculado", "ya_vinculado"):
            auth["egresado_id"] = res.get("egresado_id")
            st.rerun()
        elif estado == "ya_reclamado":
            st.warning(
                "Tu correo coincide con un registro que ya está vinculado a otra cuenta. "
                "Escribe a la administración del programa para que lo revise."
            )
            return
        else:
            auth["vinculo"] = "sin_coincidencia"
            formulario_crear_perfil(auth)
            return
    formulario_perfil(auth)


def _tokens_nombre(nombre) -> set:
    s = (
        unicodedata.normalize("NFKD", str(nombre or ""))
        .encode("ASCII", "ignore")
        .decode()
        .lower()
    )
    return {t for t in re.findall(r"[a-z]+", s) if len(t) > 2}


def posibles_duplicados(nombre, egresados, excluir_id, limite=5):
    """Registros reales con un nombre parecido (comparten al menos 2 palabras y la mayoría de las del más corto)."""
    base = _tokens_nombre(nombre)
    encontrados = []
    for _, fila in egresados[egresados["fuente"] == "real"].iterrows():
        if fila["id"] == excluir_id:
            continue
        otro = _tokens_nombre(fila["nombre"])
        comunes = len(base & otro)
        if comunes >= 2 and comunes / max(1, min(len(base), len(otro))) >= 0.66:
            encontrados.append(
                (
                    comunes,
                    fila["nombre"],
                    fila["cohorte"],
                    bool(fila.get("por_revisar")),
                )
            )
    encontrados.sort(key=lambda x: -x[0])
    return encontrados[:limite]


def pestana_por_revisar(auth, egresados, vigentes):
    st.subheader("Perfiles nuevos por revisar")
    st.caption(
        "Son personas que se registraron y no estaban en la base. Revisa lo que declararon y si ya existe un registro "
        "parecido. Si todo está bien, márcalo como revisado; si hay inconsistencias o es un duplicado, descártalo."
    )
    if st.session_state.get("aviso_revision"):
        st.success(st.session_state.pop("aviso_revision"))
    pendientes = egresados[egresados["por_revisar"] == True]  # noqa: E712
    if pendientes.empty:
        st.info("No hay perfiles pendientes de revisión.")
        return
    st.dataframe(
        pendientes[
            ["nombre", "cohorte", "email", "situacion_laboral", "fecha_registro"]
        ],
        use_container_width=True,
        hide_index=True,
    )
    nombres = dict(zip(pendientes["id"], pendientes["nombre"]))
    elegido = st.selectbox(
        "Elige un perfil para ver el detalle",
        list(nombres),
        format_func=lambda i: nombres[i],
    )
    fila = pendientes[pendientes["id"] == elegido].iloc[0]
    exp = vigentes[vigentes["egresado_id"] == elegido]

    st.markdown(
        f"**{fila['nombre']}** · cohorte {fila['cohorte']} · {fila.get('email') or 'sin correo'}"
    )
    detalle = [
        f"Situación declarada: **{fila.get('situacion_laboral') or '—'}**",
        f"Ciudad: {fila.get('ciudad_residencia') or '—'}",
        f"País: {fila.get('pais_residencia') or '—'}",
    ]
    if not exp.empty:
        detalle.append(
            f"Empresa: {exp.iloc[0].get('empresa') or '—'} · Cargo: {exp.iloc[0].get('cargo') or '—'}"
        )
    st.caption(" · ".join(detalle))
    similares = posibles_duplicados(fila["nombre"], egresados, elegido)
    if similares:
        st.warning(
            "⚠️ Posibles duplicados: "
            + "; ".join(
                f"{n} (cohorte {c}{', también por revisar' if r else ''})"
                for _, n, c, r in similares
            )
        )
    else:
        st.caption("No se encontraron nombres parecidos en la base.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Marcar como revisado"):
            try:
                llamar_funcion(auth, "marcar_revisado", {"p_egresado_id": elegido})
            except Exception as e:  # noqa: BLE001
                st.error(mensaje_error_sigma(e))
            else:
                cargar_datos.clear()
                st.rerun()
    with c2:
        seguro = st.checkbox(
            "Entiendo que descartar borra este perfil y lo que declaró",
            key=f"seguro_descartar_{elegido}",
        )
        if st.button("Descartar perfil", disabled=not seguro):
            try:
                llamar_funcion(auth, "descartar_perfil", {"p_egresado_id": elegido})
            except Exception as e:  # noqa: BLE001
                st.error(mensaje_error_sigma(e))
            else:
                cargar_datos.clear()
                st.session_state["aviso_revision"] = (
                    f"Perfil de {fila['nombre']} descartado."
                )
                st.rerun()


def main():
    st.title("📡 SIGMA — Observatorio de Trayectoria y Empleabilidad")
    st.caption("Facultad de Ingeniería de Telecomunicaciones · Universidad Santo Tomás")

    auth = st.session_state.get("auth")
    if not auth:
        pantalla_acceso()
        return
    if not sesion_vigente(auth):
        cerrar_sesion()
        pantalla_acceso("Tu sesión expiró. Vuelve a iniciar sesión.")
        return

    with st.sidebar:
        st.caption(
            f"👤 {auth['email']} · {'Administración' if auth['rol'] == 'admin' else 'Egresado'}"
        )
        if st.button("Cerrar sesión"):
            cerrar_sesion()
            st.rerun()

    if auth["rol"] == "admin":
        vista_admin(auth)
    else:
        vista_egresado(
            auth
        )  # nunca carga los datos agregados: ni siquiera se piden a la base de datos


if __name__ == "__main__":
    main()
