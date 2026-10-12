"""
Ejecuta todas las pruebas de esta carpeta e imprime un resumen.

Uso (desde la carpeta del proyecto, con el entorno virtual activado):
    python tests/ejecutar_todas.py
"""

import os
import re
import subprocess
import sys
from pathlib import Path

carpeta = Path(__file__).resolve().parent
entorno = {
    **os.environ,
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}  # que las tildes no dependan del idioma de la consola

# Las pruebas necesitan estas librerias; si falta alguna se avisa claro en vez de mostrar un error largo
faltan = []
for modulo, paquete in [
    ("streamlit", "streamlit"),
    ("fastapi", "fastapi"),
    ("httpx", "httpx"),
    ("pypdf", "pypdf"),
    ("fpdf", "fpdf2"),
    ("PIL", "pillow"),
]:
    try:
        __import__(modulo)
    except ImportError:
        faltan.append(paquete)
if faltan:
    print(
        "Faltan librerias para correr las pruebas. Instalalas con:\n    pip install "
        + " ".join(faltan)
    )
    sys.exit(2)

total_ok = total = 0
filas = []
for archivo in sorted(carpeta.glob("prueba_*.py")):
    r = subprocess.run(
        [sys.executable, str(archivo)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=carpeta.parent,
        env=entorno,
    )
    m = re.search(r"(\d+)/(\d+) pruebas correctas", r.stdout)
    ok, n = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    total_ok, total = total_ok + ok, total + n
    estado = "OK" if (m and ok == n and r.returncode == 0) else "FALLA"
    filas.append((archivo.name, ok, n, estado))
    if estado == "FALLA":
        print(f"\n===== {archivo.name}: salida =====")
        print(
            "\n".join(
                l
                for l in r.stdout.splitlines()
                if l.startswith("FALLA") or "Traceback" in l or "Error" in l
            )[-1500:]
        )
        print(r.stderr[-1200:])

print("\n" + "-" * 62)
for nombre, ok, n, estado in filas:
    print(f"{estado:6s} {nombre:36s} {ok}/{n}")
print("-" * 62 + f"\nTOTAL: {total_ok}/{total}")
sys.exit(0 if total_ok == total and total else 1)
