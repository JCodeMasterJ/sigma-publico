"""
Verificación POR CÓDIGO de lo que propone la IA al leer un CV.

Principio (el mismo del informe de acreditación): la IA propone, el código verifica.
  1. Todo dato que la IA proponga (tecnología, empresa, cargo, ciudad, país) debe APARECER en el texto del CV.
     Si no aparece, se descarta: así no puede "completar" con cosas que suenan razonables pero la persona no escribió.
  2. Las tecnologías "del cargo" deben aparecer en la descripción de ESE trabajo (el más reciente), no en cualquier
     parte del CV. Si aparecen en otra sección (educación, cursos, otro empleo), no se pierden: pasan a las opciones.

El sector y el área SON inferencias (no aparecen en el texto) y se tratan aparte: siempre se muestran como propuestas.
"""

import re
import unicodedata

# rangos de fechas que abren un trabajo o una formación: "2022 - Actualidad", "2019 - 2022", "03/2019 - 05/2021"
_RE_FECHAS = re.compile(
    r"(?:\b\d{1,2}[/.]\d{4}|\b(?:19|20)\d{2})\s*(?:-|–|—|a|hasta)\s*(?:\d{1,2}[/.]\d{4}|(?:19|20)\d{2}|actualidad|presente|actual|la fecha|hoy)",
    re.IGNORECASE,
)
_RE_TOKEN = re.compile(r"[a-z0-9+#]+")
MAX_VENTANA = 1500


def normalizar(s) -> str:
    return (
        unicodedata.normalize("NFKD", str(s or ""))
        .encode("ASCII", "ignore")
        .decode()
        .lower()
    )


def _tokens(s) -> list:
    """Palabras significativas: sin tildes ni mayúsculas; se ignoran letras sueltas (salvo C y R)."""
    return [
        t
        for t in _RE_TOKEN.findall(normalizar(s))
        if len(t) >= 2 or t in ("c", "r") or t.isdigit()
    ]


class Indice:
    """Texto normalizado, listo para comprobar rápido si algo aparece en él."""

    def __init__(self, texto: str):
        self.normal = normalizar(texto)
        self.tokens = set(_RE_TOKEN.findall(self.normal))
        self.compacto = re.sub(r"[^a-z0-9+#]", "", self.normal)

    def contiene(self, valor: str, estricto: bool = True) -> bool:
        """
        estricto=True  (tecnologías): TODAS las palabras del valor deben aparecer ("Node.js/Express" -> node, js, express).
        estricto=False (empresa, cargo, ciudad, país): TODAS las palabras de 3 o más letras deben aparecer; se ignoran las
                        cortas ("de", "y", "S.A.S"). Así "Akumaya Tech" se descarta si "Tech" no está escrito, pero "Instructor"
                        (más corto que "Instructor de Programación") sí se acepta.
        Tolera escrituras pegadas ("NodeJS" cuando el CV dice "Node.js").
        """
        toks = _tokens(valor)
        if not toks:
            return False
        if estricto:
            if all(t in self.tokens for t in toks):
                return True
            pegado = "".join(toks)
            return len(pegado) >= 5 and pegado in self.compacto
        significativas = [t for t in toks if len(t) >= 3]
        return bool(significativas) and all(t in self.tokens for t in significativas)


def ventana_trabajo_reciente(texto: str, empresa, cargo):
    """
    Texto que describe el trabajo más reciente: desde donde aparece la empresa (o el cargo) hasta el encabezado
    del SIGUIENTE trabajo o formación (el siguiente rango de fechas). Devuelve None si no se puede ubicar.
    """
    tn = normalizar(texto)
    posiciones = [
        tn.find(normalizar(c)) for c in (empresa, cargo) if c and normalizar(c).strip()
    ]
    posiciones = [p for p in posiciones if p >= 0]
    if not posiciones:
        return None
    resto = tn[min(posiciones) :]
    fechas = list(_RE_FECHAS.finditer(resto))
    # el primer rango de fechas, si está pegado al encabezado, es el del PROPIO trabajo; el siguiente abre otro bloque
    if fechas and fechas[0].start() <= 150:
        siguiente = fechas[1] if len(fechas) > 1 else None
    else:
        siguiente = fechas[0] if fechas else None
    fin = len(resto)
    if siguiente:
        # se corta al INICIO de la línea del siguiente encabezado ("Empresa | Cargo | 2023 - 2024"), no en la fecha
        salto = resto.rfind("\n", 0, siguiente.start())
        fin = salto if salto > 0 else siguiente.start()
    return resto[: min(fin, MAX_VENTANA)]


def verificar_sugerencia(sugerencia: dict, texto: str) -> dict:
    """
    Aplica las dos reglas a una sugerencia ya normalizada. Devuelve la sugerencia depurada y cuántas
    propuestas se descartaron por NO aparecer en el CV (clave 'descartadas').
    """
    idx = Indice(texto)
    descartadas = 0

    def dato(valor):
        nonlocal descartadas
        if valor and not idx.contiene(valor, estricto=False):
            descartadas += 1
            return None
        return valor

    s = dict(sugerencia)
    for campo in ("empresa", "cargo", "ciudad", "pais"):
        s[campo] = dato(s.get(campo))

    ventana = ventana_trabajo_reciente(texto, s.get("empresa"), s.get("cargo"))
    idx_ventana = Indice(ventana) if ventana else None

    principales, otras = [], []
    for t in s.get("tecnologias") or []:
        if not idx.contiene(t):
            descartadas += 1  # no está en el CV: la IA lo inventó
        elif idx_ventana is not None and not idx_ventana.contiene(t):
            otras.append(t)  # está en el CV pero no en ese trabajo: pasa a las opciones
        else:
            principales.append(t)
    for t in s.get("otras_tecnologias") or []:
        if idx.contiene(t):
            otras.append(t)
        else:
            descartadas += 1

    vistas = {t.lower() for t in principales}
    otras_limpias = []
    for t in otras:
        if t.lower() not in vistas:
            vistas.add(t.lower())
            otras_limpias.append(t)
    s["tecnologias"], s["otras_tecnologias"] = (
        principales[:10],
        (principales[10:] + otras_limpias)[:30],
    )
    s["descartadas"] = descartadas
    return s
