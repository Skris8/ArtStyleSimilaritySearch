# Backend de ArtSim

Aplicación FastAPI que sirve el frontend estático y coordina tres fuentes de datos:

- Qdrant contiene los embeddings, las imágenes y los resultados de similaridad.
- MySQL conserva metadatos, administradores, mensajes y reportes exportados.
- `ipynb/ArtStylesDataset/` permite recuperar imágenes locales para el detalle y los reportes.

## Ejecución

```bash
python -m pip install -r backend/requirements.txt
# Iniciar el servidor desde la raíz del proyecto.
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

La configuración se obtiene primero de variables de entorno y luego de
`frontend/.config/secrets.toml`. El archivo `frontend/.config/secrets.toml.example`
documenta las claves admitidas.

## Endpoints principales

- `GET /api/types` — lista de estilos almacenados en Qdrant.
- `GET /api/records?limit=12&type=...` — lista de imágenes de Qdrant con `base64`, `id`, `type`, `title`, `resolution`.
- `GET /api/records/{id}/similar?type=...` — devuelve imágenes similares calculadas por Qdrant, opcionalmente limitadas a un estilo.
- `GET /api/records/{id}/similar-report` — genera el informe DOCX y registra su contenido en MySQL.
- `GET /api/records/{id}` — recupera una imagen mediante su ruta relativa dentro del dataset local.
- `/api/contact`, `/api/messages`, `/api/login` y `/api/exported-files` sostienen los flujos de contacto y administración.

Los endpoints de tipos, registros y similitud responden `503 Service Unavailable` cuando Qdrant no está configurado o no se encuentra disponible. No cargan imágenes del dataset local como fallback.

## Mantenimiento

- `scripts/sync_artworks_metadata.py` sincroniza el dataset, Qdrant y la tabla `artworks`.
- `backend/migrations/001_exported_files_history.sql` migra el historial para almacenar cada DOCX como BLOB.
- `python -m unittest discover -s backend/tests -v` ejecuta las pruebas del contrato con Qdrant.
- `node --test frontend/tests/*.test.js` ejecuta las pruebas del frontend.
