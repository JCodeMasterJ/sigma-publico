# Pruebas automaticas de SIGMA

Todas las pruebas usan datos inventados y simulan Supabase y la IA: **no tocan tu base de datos real, no gastan cuota de Gemini
y no envian nada por internet.** Se pueden correr cuantas veces quieras.

## Como correrlas

Desde la carpeta del proyecto (la que tiene `app.py`), con el entorno virtual activado:

    python tests/ejecutar_todas.py

Al final muestra una tabla con cuantas pasaron de cuantas. Tarda uno o dos minutos. Si ves avisos de `ScriptRunContext`, ignoralos:
son normales al probar Streamlit sin abrir el navegador.

Para correr una sola:

    python tests/prueba_privacidad.py

## Que prueba cada archivo

| Archivo | Que comprueba |
|---|---|
| `prueba_privacidad.py` | Que al limpiar un CV no quede ningun dato personal (nombre, telefono, correo, direccion, cedula, referencias) y SI quede el contenido profesional |
| `prueba_lectura_pdf.py` | Que la lectura de PDF rechace con un mensaje claro los escaneados, con contrasena, corruptos, vacios, demasiado grandes o que no son PDF |
| `prueba_verificacion_cv.py` | Que lo que la IA propone al leer un CV tenga que estar ESCRITO en el CV: si inventa tecnologias, se descartan |
| `prueba_servidor_agentes.py` | El servicio de agentes: exige clave, limita el tamano, no filtra el texto del CV si falla y no deja pasar datos inventados |
| `prueba_cv_portal.py` | La pantalla del egresado de punta a punta: lo que sale hacia la IA, la precarga del formulario, los errores y los limites de uso |

## Si falla alguna

Pega aqui la parte que dice `FALLA` y el texto de abajo. Si dice que falta una libreria, instala la que indique.