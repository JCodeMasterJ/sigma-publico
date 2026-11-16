"""Pruebas del estilo visual: sin emojis ni íconos, tema azul y dorado coherente con el PDF, y que no dependa de internet ni obligue al movimiento."""

import os, re, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.update(
    SUPABASE_URL="https://x.supabase.co",
    SUPABASE_SERVICE_KEY="dummy",
    SUPABASE_ANON_KEY="dummy",
    GEMINI_API_KEY="dummy",
    AGENTES_URL="https://servicio.test",
    AGENTES_API_KEY="clave-de-prueba",
)

resultados = []


def chequear(n, ok, d=""):
    resultados.append(bool(ok))
    print(("OK   " if ok else "FALLA"), n, ("-> " + str(d)[:140]) if d else "")


# emojis, pictogramas, flechas y símbolos decorativos (no las tildes, ¿ ¡ « » — ni el punto medio ·)
BASE = "\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff\u2190-\u21ff\u2300-\u23ff"
EMOJI = re.compile(f"[{BASE}\ufe0f\u200d]")


def con_emojis(texto):
    return sorted({m for m in EMOJI.findall(texto)})


codigo = (RAIZ / "app.py").read_text(encoding="utf-8")
lineas = [
    (i, l.strip()[:80]) for i, l in enumerate(codigo.split("\n"), 1) if EMOJI.search(l)
]
chequear(
    "S1. app.py no tiene ningún emoji ni símbolo decorativo", not lineas, lineas[:3]
)
chequear(
    "S2. ni el aviso de privacidad ni los textos de la demostración los tienen",
    not con_emojis((RAIZ / "aviso_privacidad.py").read_text(encoding="utf-8"))
    and not con_emojis((RAIZ / "datos_demo.py").read_text(encoding="utf-8")),
)

# lo que se ve de verdad en pantalla (acceso y demostración con todas sus pestañas), por si algún texto se arma en tiempo de ejecución
import supabase as _supabase


def _caido(*a, **k):
    raise RuntimeError("sin Supabase")


_supabase.create_client = _caido
from streamlit.testing.v1 import AppTest


def textos(at):
    salida = []
    for tipo in (
        "markdown",
        "caption",
        "info",
        "warning",
        "success",
        "error",
        "subheader",
        "header",
        "title",
        "button",
        "tabs",
        "expander",
        "radio",
        "selectbox",
        "metric",
        "download_button",
    ):
        for e in (
            at.get(tipo) if tipo in ("download_button",) else getattr(at, tipo, [])
        ):
            for campo in ("value", "label"):
                v = getattr(e, campo, None)
                if isinstance(v, str):
                    salida.append(v)
            if tipo == "download_button":
                salida.append(e.proto.label)
    return salida


at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=120)
at.run()
pantalla_acceso = textos(at)
at.button(key="entrar_demo").click()
at.run()
pantalla_demo = textos(at)
chequear(
    "S3. en la pantalla de acceso no aparece ningún emoji",
    not any(con_emojis(t) for t in pantalla_acceso) and not at.exception,
    [t for t in pantalla_acceso if con_emojis(t)][:2],
)
chequear(
    "S4. en la demostración completa (egresado, panel, informe de ejemplo y privacidad) no aparece ninguno",
    not any(con_emojis(t) for t in pantalla_demo),
    [t for t in pantalla_demo if con_emojis(t)][:2],
)
html = " ".join(m.value for m in at.markdown)
chequear(
    "S5. la cabecera es tipográfica: el nombre SIGMA, la frase y la línea dorada, sin título con ícono",
    "sigma-marca" in html
    and "Observatorio de trayectoria y empleabilidad" in html
    and not at.get("title"),
)


# el tema
def leer_toml(ruta):
    """Lectura mínima de pares clave = valor por sección (sin depender de la versión de Python)."""
    datos, sec = {}, ""
    for l in ruta.read_text(encoding="utf-8").split("\n"):
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        if l.startswith("["):
            sec = l.strip("[]")
            continue
        k, _, v = l.partition("=")
        datos[f"{sec}.{k.strip()}"] = v.strip().strip('"')
    return datos


cfg_ruta = RAIZ / ".streamlit" / "config.toml"
cfg = leer_toml(cfg_ruta) if cfg_ruta.exists() else {}
NAVY = re.search(r'^NAVY = "(#[0-9A-Fa-f]{6})"', codigo, re.M).group(1).upper()
GOLD = re.search(r'^GOLD = "(#[0-9A-Fa-f]{6})"', codigo, re.M).group(1).upper()
chequear(
    "S6. existe .streamlit/config.toml con la barra de herramientas mínima y las tipografías de Streamlit como respaldo",
    cfg_ruta.exists()
    and cfg.get("client.toolbarMode") == "minimal"
    and cfg.get("theme.font") == "sans serif"
    and cfg.get("theme.headingFont") == "serif",
    cfg,
)
chequear(
    "S7. el tema usa el azul y el dorado de la aplicación (NAVY y GOLD): color principal azul y, en la barra lateral, el dorado",
    cfg.get("theme.primaryColor", "").upper() == NAVY
    and cfg.get("theme.sidebar.primaryColor", "").upper() == GOLD
    and cfg.get("theme.sidebar.backgroundColor", "").upper() == NAVY,
    (NAVY, GOLD),
)
paleta = (
    set(re.findall(r"#[0-9A-Fa-f]{6}", cfg.get("theme.chartCategoricalColors", "")))
    if cfg
    else set()
)
paleta_app = set(
    c.upper()
    for c in re.findall(
        r"#[0-9A-Fa-f]{6}",
        re.search(r"^PALETA = \[(.*?)\]", codigo, re.M | re.S).group(1),
    )
) | {NAVY, GOLD}
chequear(
    "S8. las gráficas del tema usan los mismos colores que la paleta de la aplicación",
    {c.upper() for c in paleta} <= paleta_app
    and {NAVY, GOLD} <= {c.upper() for c in paleta},
    paleta,
)
import informe_pdf as ip

a_hex = lambda rgb: "#%02X%02X%02X" % rgb
chequear(
    "S9. el azul y el dorado de la pantalla son EXACTAMENTE los del informe en PDF (una sola identidad)",
    a_hex(ip.NAVY) == NAVY and a_hex(ip.GOLD) == GOLD,
    (a_hex(ip.NAVY), a_hex(ip.GOLD)),
)

# accesibilidad y robustez del estilo (se lee el CSS directamente del código)
ESTILO = re.search(r'ESTILO = """(.*?)""".replace', codigo, re.S).group(1)
reducido = re.search(
    r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", ESTILO, re.S
)
chequear(
    "S10. quien prefiere menos movimiento no ve animaciones (el nombre, las cifras y los avisos se quedan quietos)",
    bool(reducido)
    and all(
        sel in reducido.group(1)
        for sel in (
            ".sigma-marca",
            '[data-testid="stMetric"]',
            ".metric-card",
            '[data-testid="stAlert"]',
        )
    )
    and "animation: none" in reducido.group(1),
)
chequear(
    "S11. el estilo no pide NADA a internet (ni fuentes, ni imágenes, ni importaciones): funciona igual sin conexión en un stand",
    not re.search(r"@import|https?:|url\(", ESTILO),
)
duraciones = [float(x) for x in re.findall(r"animation:[^;]*?([\d.]+)s", ESTILO)]
chequear(
    "S12. el movimiento es sutil: ninguna animación dura más de 1,2 segundos",
    duraciones and max(duraciones) <= 1.2,
    duraciones,
)


def luminancia(hex_):
    r, g, b = (int(hex_[i : i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a, b):
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def variable(nombre):
    m = re.search(
        rf"--{nombre}: (#[0-9A-Fa-f]{{6}})",
        ESTILO.replace("__NAVY__", NAVY).replace("__GOLD__", GOLD),
    )
    return m.group(1) if m else None


V = {
    n: variable(n)
    for n in ("navy", "ink", "muted", "pagina", "tarjeta", "gold-soft", "blue-soft")
}
V["gold"], V["blanco"], V["exito"], V["error"] = GOLD, "#FFFFFF", "#E3F1EC", "#FBE7E3"
faltan_var = [n for n, v in V.items() if v is None]
V = {n: (v or "#000000") for n, v in V.items()}
pares = [
    ("texto sobre el marfil", V["ink"], V["pagina"], 4.5),
    ("texto sobre las tarjetas", V["ink"], V["tarjeta"], 4.5),
    ("etiquetas grises sobre el marfil", V["muted"], V["pagina"], 4.5),
    ("etiquetas grises sobre las tarjetas", V["muted"], V["tarjeta"], 4.5),
    ("azul sobre el marfil (títulos, pestaña activa)", V["navy"], V["pagina"], 4.5),
    ("azul sobre las tarjetas", V["navy"], V["tarjeta"], 4.5),
    ("blanco sobre azul (botones y barra lateral)", V["blanco"], V["navy"], 4.5),
    ("dorado sobre azul (cifras grandes)", V["gold"], V["navy"], 3.0),
    ("dorado sobre azul (texto pequeño al pasar el cursor)", V["gold"], V["navy"], 4.5),
    ("texto sobre aviso azul", V["ink"], V["blue-soft"], 4.5),
    ("texto sobre aviso dorado", V["ink"], V["gold-soft"], 4.5),
    ("texto sobre aviso verde", V["ink"], V["exito"], 4.5),
    ("texto sobre aviso rojo", V["ink"], V["error"], 4.5),
]
malos = (
    [
        (n, round(contraste(a, b), 2), minimo)
        for n, a, b, minimo in pares
        if contraste(a, b) < minimo
    ]
    if not faltan_var
    else [("faltan las variables de color", faltan_var, 0)]
)
chequear(
    f"S13. los {len(pares)} pares de color texto/fondo cumplen el contraste de accesibilidad WCAG AA (4,5 para texto normal, 3 para letra grande)",
    not malos,
    malos,
)

# la barra superior de Streamlit (60 px; con Compartir, favorito y editar para el dueño) va ENCIMA del contenido: debe quedar espacio de sobra
margen = re.search(
    r'\[data-testid="stMainBlockContainer"\] \{ padding-top: ([\d.]+)rem', ESTILO
)
movil = re.search(
    r"@media \(max-width: 640px\) \{.*?stMainBlockContainer\"\] \{ padding-top: ([\d.]+)rem",
    ESTILO,
    re.S,
)
chequear(
    "S15. el contenido arranca por debajo de la barra superior de Streamlit (al menos 4,5 rem, es decir 72 px, en escritorio y en celular)",
    margen and movil and float(margen.group(1)) >= 4.5 and float(movil.group(1)) >= 4.5,
    (margen and margen.group(1), movil and movil.group(1)),
)

# el tema y el estilo propio tienen que decir lo mismo (si no, la página se vería distinta según se cargue uno u otro)
sin_alfa = lambda c: (c or "").upper()
chequear(
    "S16. el fondo del tema (marfil), el de las tarjetas y el color de los bordes son los mismos que usa el estilo propio",
    cfg.get("theme.backgroundColor", "").upper() == sin_alfa(variable("pagina"))
    and cfg.get("theme.secondaryBackgroundColor", "").upper()
    == sin_alfa(variable("tarjeta"))
    and cfg.get("theme.borderColor", "").upper() == sin_alfa(variable("line")),
    (cfg.get("theme.backgroundColor"), variable("pagina")),
)

# las tipografías propias: dentro del proyecto, con su licencia y con respaldo
carpeta = RAIZ / "fuentes"
woff2 = sorted(carpeta.glob("*.woff2")) if carpeta.exists() else []
firmas_ok = all(f.read_bytes()[:4] == b"wOF2" for f in woff2)
licencias = {
    n: (carpeta / n).read_text(encoding="utf-8") if (carpeta / n).exists() else ""
    for n in ("OFL-Fraunces.txt", "OFL-PublicSans.txt")
}
chequear(
    "S17. las tipografías (Fraunces y Public Sans) van DENTRO del proyecto: 3 archivos woff2 válidos, de poco peso, con la licencia libre que exige su uso",
    len(woff2) == 3
    and firmas_ok
    and sum(f.stat().st_size for f in woff2) < 200_000
    and all("SIL OPEN FONT LICENSE" in v for v in licencias.values()),
    ([f.name for f in woff2], sum(f.stat().st_size for f in woff2)),
)


def css_var(n):
    m = re.search(rf"--{n}: ([^;]+);", ESTILO)
    return m.group(1) if m else ""


serif, sans = css_var("serif"), css_var("sans")
chequear(
    "S18. si una tipografía no cargara, hay respaldo: Georgia para los títulos y la del sistema para el texto",
    serif.strip().startswith('"Fraunces"')
    and "Georgia" in serif
    and serif.strip().endswith("serif")
    and sans.strip().startswith('"Public Sans"')
    and "sans-serif" in sans,
    (serif, sans),
)
estilo_vivo = " ".join(m.value for m in at.markdown if "@font-face" in m.value)
caras = re.findall(r"font-family: '([^']+)'; font-style: (\w+)", estilo_vivo)
chequear(
    "S19. en la aplicación en marcha, las tipografías llegan incrustadas (Fraunces normal y cursiva, Public Sans) y sin ninguna dirección de internet",
    sorted(caras)
    == [("Fraunces", "italic"), ("Fraunces", "normal"), ("Public Sans", "normal")]
    and "data:font/woff2;base64," in estilo_vivo
    and not re.search(r"https?:", estilo_vivo),
    caras,
)
import tempfile, shutil
import streamlit as _st

_st.cache_resource.clear()  # sin esto, la memoria entregaría el resultado de la corrida anterior (que sí tenía las tipografías)
with tempfile.TemporaryDirectory() as tmp:
    shutil.copy(
        RAIZ / "app.py", Path(tmp) / "app.py"
    )  # una copia SIN la carpeta fuentes/
    sin = AppTest.from_file(str(Path(tmp) / "app.py"), default_timeout=120)
    sin.run()
    estilo_sin = " ".join(m.value for m in sin.markdown if "font-family" in m.value)
    chequear(
        "S20. si faltaran los archivos de tipografía, la aplicación igual abre sin errores y usa las tipografías de respaldo (no se rompe nada)",
        not sin.exception
        and "@font-face" not in estilo_sin
        and "Georgia" in estilo_sin,
        list(sin.exception)[:1],
    )

# el repositorio público debe llevarse el tema, pero JAMÁS los secretos
script = RAIZ / "preparar_repo_limpio.py"
if script.exists():
    import importlib.util, tempfile

    espec = importlib.util.spec_from_file_location("preparar_repo_limpio", script)
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        (raiz / ".streamlit").mkdir()
        for nombre in ("config.toml", "secrets.toml", "credentials.toml"):
            (raiz / ".streamlit" / nombre).write_text("x = 1", encoding="utf-8")
        (raiz / ".env").write_text("A=1", encoding="utf-8")
        copia = {
            n: modulo.debe_copiarse(raiz / ".streamlit" / n, raiz)[0]
            for n in ("config.toml", "secrets.toml", "credentials.toml")
        }
        copia[".env"] = modulo.debe_copiarse(raiz / ".env", raiz)[0]
        (raiz / "fuentes").mkdir()
        (raiz / "otra").mkdir()
        for nombre in (
            "Fraunces-normal-600.woff2",
            "OFL-Fraunces.txt",
            "notas.txt",
            "datos.csv",
        ):
            (raiz / "fuentes" / nombre).write_text("x", encoding="utf-8")
        (raiz / "otra" / "x.woff2").write_text("x", encoding="utf-8")
        fuentes = {
            n: modulo.debe_copiarse(raiz / "fuentes" / n, raiz)[0]
            for n in (
                "Fraunces-normal-600.woff2",
                "OFL-Fraunces.txt",
                "notas.txt",
                "datos.csv",
            )
        }
        fuentes["otra/x.woff2"] = modulo.debe_copiarse(raiz / "otra" / "x.woff2", raiz)[
            0
        ]
    chequear(
        "S14. el script del repositorio público copia el tema (config.toml) pero NO los secretos ni ningún otro archivo de .streamlit, ni el .env",
        copia
        == {
            "config.toml": True,
            "secrets.toml": False,
            "credentials.toml": False,
            ".env": False,
        },
        copia,
    )
    chequear(
        "S14b. y copia las tipografías woff2 con su licencia OFL, pero ningún otro archivo de fuentes/ ni tipografías sueltas en otras carpetas",
        fuentes
        == {
            "Fraunces-normal-600.woff2": True,
            "OFL-Fraunces.txt": True,
            "notas.txt": False,
            "datos.csv": False,
            "otra/x.woff2": False,
        },
        fuentes,
    )
else:
    chequear("S14. (omitida: aquí no está el script del repositorio público)", True)

print(f"\n{sum(resultados)}/{len(resultados)} pruebas correctas")
sys.exit(0 if all(resultados) else 1)
