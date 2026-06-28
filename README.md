# ArtStyle Image Similarity Search

Aplicación web en FastAPI para consultar imágenes y resultados de similitud almacenados en Qdrant. MySQL conserva administradores, mensajes, metadatos y reportes. El frontend es estático y no requiere `npm install`.

## Requisitos para Windows 10/11

- Python `3.13.x` de 64 bits, con el lanzador `py` disponible.
- Acceso a Internet durante la instalación de paquetes.
- Qdrant remoto accesible con la colección `ArtStyles_images` ya cargada.
- MySQL instalado en el equipo, con la base, tablas y datos del proyecto ya restaurados.
- Node.js `22.x` únicamente para ejecutar las pruebas del frontend.
- Para usar el notebook: VS Code con las extensiones oficiales **Python** y **Jupyter**, o JupyterLab como alternativa.

Comprueba las herramientas desde PowerShell:

```powershell
py -3.13 --version
node --version
```

## Transferir el proyecto

Transfiere el código completo, incluidos estos recursos necesarios:

- `backend/templates/`, que contiene la plantilla de los reportes DOCX.
- `ipynb/ArtStylesDataset/`, utilizado para imágenes locales y reportes.
- `frontend/.config/secrets.toml`, con las conexiones existentes.

No reutilices ni transfieras `.venv/`, `.venv-notebook/`, `.cache/` ni los reportes generados en `exports/reports/`. Los entornos virtuales contienen rutas específicas del equipo donde fueron creados y deben reconstruirse en el destino.

> **Credenciales:** `frontend/.config/secrets.toml` contiene datos sensibles. El proyecto solo debe entregarse a receptores autorizados mediante un canal privado. No publiques ese archivo ni compartas una copia del proyecto sin retirar o rotar primero las credenciales.

La configuración actual espera MySQL en `localhost`. Por ello, copiar `secrets.toml` no copia la base de datos: antes de iniciar la aplicación, MySQL debe estar instalado y la base original debe haberse restaurado en el equipo destino.

## Instalar y ejecutar la aplicación

Abre PowerShell en la raíz del proyecto y crea un entorno limpio:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Los comandos usan directamente el Python del entorno, por lo que no es necesario activarlo ni cambiar la política de ejecución de PowerShell.

Inicia el servidor siempre desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Abre `http://127.0.0.1:8000/`. El servidor también entrega el frontend, por lo que no se necesita iniciar otro proceso.

## Comprobar la instalación

Con el servidor activo, valida en este orden:

1. `http://127.0.0.1:8000/` abre la galería.
2. `http://127.0.0.1:8000/api/qdrant_status` responde con `"connected": true` y muestra la colección esperada.
3. `http://127.0.0.1:8000/api/types` devuelve los estilos disponibles.
4. La galería muestra registros e imágenes sin errores de red.
5. `http://127.0.0.1:8000/admin` permite iniciar sesión con un administrador existente. Consulta los mensajes o genera un reporte para confirmar también la conexión con MySQL, el dataset y la plantilla DOCX.

Ejecuta las pruebas del backend con el entorno de la aplicación:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
```

Las pruebas del frontend utilizan únicamente el ejecutor incluido en Node.js; no existe un `package.json` ni hay paquetes npm que instalar:

```powershell
node --test frontend/tests/*.test.js
```

## Entorno opcional del notebook

El notebook de generación y carga de embeddings usa dependencias pesadas que no son necesarias para ejecutar la web. Instálalas en un entorno separado:

```powershell
py -3.13 -m venv .venv-notebook
.\.venv-notebook\Scripts\python.exe -m pip install --upgrade pip
.\.venv-notebook\Scripts\python.exe -m pip install -r ipynb\requirements.txt
.\.venv-notebook\Scripts\python.exe -m pip check
.\.venv-notebook\Scripts\python.exe -c "import pandas, torch, transformers, qdrant_client, mysql.connector, PIL, dotenv; print('Imports correctos')"
```

`ipykernel`, incluido en `ipynb/requirements.txt`, permite utilizar `.venv-notebook` como kernel, pero no instala una interfaz para abrir notebooks.

La opción recomendada es abrir el proyecto en VS Code, instalar las extensiones oficiales **Python** (`ms-python.python`) y **Jupyter** (`ms-toolsai.jupyter`), abrir `ipynb/get-image-embeddings.ipynb` y seleccionar `.venv-notebook` como kernel.

Si no se utilizará VS Code, instala JupyterLab dentro del entorno y ejecútalo desde la raíz del proyecto:

```powershell
.\.venv-notebook\Scripts\python.exe -m pip install jupyterlab
.\.venv-notebook\Scripts\python.exe -m jupyter lab
```

JupyterLab es opcional y por eso no forma parte de `ipynb/requirements.txt`: no es necesario cuando el notebook se abre desde VS Code. La primera ejecución de las celdas de inferencia descarga el modelo `microsoft/resnet-50` desde Hugging Face y necesita Internet.

El notebook es una herramienta de mantenimiento, no un paso de instalación. Contiene celdas que recrean la colección de Qdrant, cargan vectores, sincronizan MySQL y pueden vaciar `artworks`; no ejecutes todas las celdas automáticamente sobre los servicios existentes.

## Problemas frecuentes

- **`py -3.13` no encuentra Python:** instala Python 3.13 de 64 bits y habilita el lanzador para Windows durante la instalación.
- **Falla la creación del entorno:** elimina únicamente el entorno virtual incompleto y vuelve a crearlo; no copies uno desde otro equipo.
- **Qdrant indica `credentials_missing`:** verifica que `frontend/.config/secrets.toml` exista en esa ruta y conserve `qdrant_db_url` y `qdrant_api_key`.
- **Qdrant no conecta:** comprueba Internet, firewall, vigencia de la clave y acceso a la colección `ArtStyles_images`.
- **Login, mensajes o reportes fallan:** confirma que el servicio MySQL esté iniciado y que la base restaurada coincida con `mysql_database` en `secrets.toml`.
- **Faltan imágenes o falla un reporte:** comprueba que `ipynb/ArtStylesDataset/` y la plantilla dentro de `backend/templates/` se transfirieron completas.
- **Node falla al ejecutar pruebas:** utiliza Node.js 22.x y ejecuta el comando desde la raíz del proyecto.

La descripción de endpoints y tareas de mantenimiento del backend permanece en [`backend/README.md`](backend/README.md).
