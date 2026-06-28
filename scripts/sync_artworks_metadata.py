"""Sincroniza metadatos del dataset entre Qdrant y la tabla MySQL ``artworks``."""

from pathlib import Path
import argparse
import glob
import os

from dotenv import load_dotenv
from PIL import Image, ExifTags
from qdrant_client import QdrantClient
import mysql.connector
import toml


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "ipynb" / "ArtStylesDataset"
SECRETS_PATH = ROOT / "frontend" / ".config" / "secrets.toml"
QDRANT_COLLECTION = "ArtStyles_images"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
REQUIRED_META_FIELDS = ("title", "author_name", "style_name", "source_name", "source_url")


load_dotenv(dotenv_path=ROOT / "ipynb" / ".env")


# Configuración compartida por las conexiones externas.
def load_secrets():
    """Carga el archivo local sin exigir que exista en otros entornos."""

    if SECRETS_PATH.exists():
        return toml.load(SECRETS_PATH)
    return {}


def load_mysql_config():
    """Combina variables de entorno, secretos locales y valores de conexión seguros."""

    secrets = load_secrets()
    return {
        "host": os.environ.get("MYSQL_HOST") or secrets.get("mysql_host") or "127.0.0.1",
        "port": int(os.environ.get("MYSQL_PORT") or secrets.get("mysql_port") or 3306),
        "user": os.environ.get("MYSQL_USER") or secrets.get("mysql_user"),
        "password": os.environ.get("MYSQL_PASSWORD")
        if os.environ.get("MYSQL_PASSWORD") is not None
        else secrets.get("mysql_password"),
        "database": os.environ.get("MYSQL_DATABASE") or secrets.get("mysql_database"),
    }


def load_qdrant_config():
    """Obtiene la URL y la clave requeridas por Qdrant."""

    secrets = load_secrets()
    return {
        "url": os.environ.get("QDRANT_URL") or os.environ.get("QDRANT_DB_URL") or secrets.get("qdrant_db_url"),
        "api_key": os.environ.get("QDRANT_API_KEY") or os.environ.get("QDRANT_APIKEY") or secrets.get("qdrant_api_key"),
    }


def clean_meta(value):
    """Convierte metadatos EXIF heterogéneos en texto limpio o ``None``."""

    if value is None:
        return None
    if isinstance(value, bytes):
        for encoding in ("utf-16le", "utf-8", "latin-1"):
            text = value.decode(encoding, errors="ignore").replace("\x00", "").strip()
            if text:
                return text
        return None
    if isinstance(value, (list, tuple)):
        parts = [clean_meta(item) for item in value]
        return ", ".join(part for part in parts if part) or None
    text = str(value).strip()
    return text or None


def read_artwork_metadata(image_path):
    """Extrae campos descriptivos desde EXIF y los metadatos del formato."""

    with Image.open(image_path) as img:
        exif = {ExifTags.TAGS.get(k, k): v for k, v in (img.getexif() or {}).items()}
        info = img.info or {}
    return {
        "title": clean_meta(exif.get("XPTitle") or exif.get("ImageDescription") or info.get("Title") or info.get("Description")),
        "author_name": clean_meta(exif.get("XPAuthor") or exif.get("Artist") or info.get("Author") or info.get("Artist")),
        "source_name": clean_meta(exif.get("XPSubject") or info.get("Subject")),
        "source_url": clean_meta(exif.get("Copyright") or info.get("Copyright")),
    }


def image_paths():
    """Enumera de forma estable todas las imágenes compatibles del dataset."""

    paths = []
    for suffix in IMAGE_SUFFIXES:
        paths.extend(Path(p) for p in glob.glob(str(DATASET_DIR / "**" / f"*{suffix}"), recursive=True))
    return sorted(path for path in paths if path.is_file())


def path_keys(path):
    """Genera variantes de ruta para enlazar archivos locales con payloads históricos."""

    rel_dataset = path.relative_to(DATASET_DIR).as_posix()
    rel_root = path.relative_to(ROOT).as_posix()
    keys = {
        path.as_posix(),
        str(path.resolve()).replace("\\", "/"),
        rel_root,
        rel_dataset,
        f"ArtStylesDataset/{rel_dataset}",
        f"./ArtStylesDataset/{rel_dataset}",
    }
    return {key.lower().replace("\\", "/") for key in keys}


def payload_path_keys(payload):
    """Extrae las rutas que pudo haber usado una versión anterior del payload."""

    keys = set()
    for field in ("image_path", "file_path", "path"):
        value = payload.get(field)
        if value:
            text = str(value).replace("\\", "/")
            keys.add(text.lower())
            keys.add(text.lstrip("./").lower())
    return keys


def qdrant_id_map():
    """Asocia cada ruta conocida con el identificador actual de su punto."""

    cfg = load_qdrant_config()
    if not cfg["url"] or not cfg["api_key"]:
        return {}
    client = QdrantClient(url=cfg["url"], api_key=cfg["api_key"])
    mapping = {}
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=QDRANT_COLLECTION,
            with_payload=True,
            limit=256,
            offset=offset,
        )
        for record in records:
            payload = getattr(record, "payload", {}) or {}
            for key in payload_path_keys(payload):
                mapping[key] = str(getattr(record, "id"))
        if offset is None:
            break
    return mapping


def build_artwork_row(path, index, qdrant_mapping, include_incomplete):
    """Prepara una fila y comunica qué metadatos obligatorios están ausentes."""

    metadata = read_artwork_metadata(path)
    metadata["title"] = metadata["title"] or path.stem
    qdrant_id = None
    for key in path_keys(path):
        qdrant_id = qdrant_mapping.get(key)
        if qdrant_id:
            break
    if qdrant_id is None:
        qdrant_id = str(index)

    row = {
        "title": metadata["title"],
        "author_name": metadata["author_name"],
        "style_name": path.parent.name,
        "source_name": metadata["source_name"],
        "source_url": metadata["source_url"],
        "file_path": str(path.relative_to(ROOT)).replace("/", os.sep),
        "id_qdrant_point": qdrant_id,
    }
    missing = [field for field in REQUIRED_META_FIELDS if not row.get(field)]
    if missing and not include_incomplete:
        return None, missing
    return row, missing


def upsert_rows(rows, dry_run):
    """Inserta o actualiza las filas preparadas, salvo en modo de simulación."""

    if dry_run or not rows:
        return 0
    cfg = load_mysql_config()
    if not cfg["user"] or not cfg["database"]:
        raise RuntimeError("Configura MYSQL_USER y MYSQL_DATABASE en variables de entorno o frontend/.config/secrets.toml.")
    conn = mysql.connector.connect(charset="utf8mb4", **cfg)
    cursor = conn.cursor()
    sql = """
    INSERT INTO artworks
    (title, author_name, style_name, source_name, source_url, file_path, id_qdrant_point)
    VALUES (%(title)s, %(author_name)s, %(style_name)s, %(source_name)s, %(source_url)s, %(file_path)s, %(id_qdrant_point)s)
    ON DUPLICATE KEY UPDATE
    title = VALUES(title),
    author_name = VALUES(author_name),
    style_name = VALUES(style_name),
    source_name = VALUES(source_name),
    source_url = VALUES(source_url),
    file_path = VALUES(file_path)
    """
    try:
        cursor.executemany(sql, rows)
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        conn.close()


def main():
    """Ejecuta el inventario, la asociación con Qdrant y la escritura en MySQL."""

    parser = argparse.ArgumentParser(description="Sincroniza metadata de imagenes hacia la tabla artworks.")
    parser.add_argument("--include-incomplete", action="store_true", help="Inserta tambien imagenes con author/source faltante.")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en MySQL; solo muestra el resumen.")
    args = parser.parse_args()

    paths = image_paths()
    mapping = qdrant_id_map()
    rows = []
    skipped = []
    incomplete = []
    for index, path in enumerate(paths):
        try:
            row, missing = build_artwork_row(path, index, mapping, args.include_incomplete)
        except Exception as exc:
            skipped.append((path, [str(exc)]))
            continue
        if row is None:
            skipped.append((path, missing))
            continue
        if missing:
            incomplete.append((path, missing))
        rows.append(row)

    affected = upsert_rows(rows, args.dry_run)
    action = "se insertarian/actualizarian" if args.dry_run else "insertadas/actualizadas"
    print(f"Imagenes encontradas: {len(paths)}")
    print(f"Filas preparadas: {len(rows)}")
    print(f"Filas {action} en MySQL: {affected if not args.dry_run else len(rows)}")
    print(f"Filas incompletas incluidas: {len(incomplete)}")
    print(f"Imagenes omitidas: {len(skipped)}")
    for path, missing in skipped[:30]:
        print(f"OMITIDA {path}: faltan {', '.join(missing)}")
    if len(skipped) > 30:
        print(f"... {len(skipped) - 30} omitidas adicionales")


if __name__ == "__main__":
    main()
