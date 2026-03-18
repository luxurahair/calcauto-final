"""
Supabase Storage — Module pour upload/download de fichiers
Bucket: calcauto-data
Structure:
  calcauto-data/
    monthly/{mois}{annee}/           -- donnees mensuelles extraites
      sci_lease_rates.json
      key_incentives.json
      program_meta.json
      sci_residuals.json
      source.pdf                     -- PDF source uploade
    reference/                       -- fichiers de reference permanents
      2025_pdfs/{vehicule}.pdf
      calcauto/{vehicule}.pdf
      fca_product_codes_2025.json
      ...
"""
import os
import json
import logging
from pathlib import Path
from supabase import create_client

logger = logging.getLogger("calcauto")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
BUCKET = "calcauto-data"

_client = None

def _get_client():
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL ou SUPABASE_SERVICE_KEY manquant dans .env")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def ensure_bucket():
    """Cree le bucket s'il n'existe pas."""
    client = _get_client()
    try:
        client.storage.get_bucket(BUCKET)
    except Exception:
        client.storage.create_bucket(BUCKET, options={"public": False})
        logger.info(f"[Storage] Bucket '{BUCKET}' cree")


def upload_file(remote_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload un fichier vers Supabase Storage. Retourne le path."""
    client = _get_client()
    try:
        client.storage.from_(BUCKET).remove([remote_path])
    except Exception:
        pass
    client.storage.from_(BUCKET).upload(
        path=remote_path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"}
    )
    logger.info(f"[Storage] Uploaded: {remote_path} ({len(data)} bytes)")
    return remote_path


def download_file(remote_path: str) -> bytes:
    """Telecharge un fichier depuis Supabase Storage."""
    client = _get_client()
    data = client.storage.from_(BUCKET).download(remote_path)
    return data


def file_exists(remote_path: str) -> bool:
    """Verifie si un fichier existe dans le Storage."""
    client = _get_client()
    try:
        folder = "/".join(remote_path.split("/")[:-1])
        filename = remote_path.split("/")[-1]
        files = client.storage.from_(BUCKET).list(folder)
        return any(f["name"] == filename for f in files)
    except Exception:
        return False


def list_files(folder: str) -> list:
    """Liste les fichiers dans un dossier."""
    client = _get_client()
    try:
        files = client.storage.from_(BUCKET).list(folder)
        return [f["name"] for f in files if f.get("name")]
    except Exception as e:
        logger.error(f"[Storage] List error for {folder}: {e}")
        return []


def upload_local_file(local_path: str, remote_path: str) -> str:
    """Upload un fichier local vers Supabase."""
    ext = Path(local_path).suffix.lower()
    content_types = {
        ".pdf": "application/pdf",
        ".json": "application/json",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv": "text/csv",
    }
    ct = content_types.get(ext, "application/octet-stream")
    with open(local_path, "rb") as f:
        data = f.read()
    return upload_file(remote_path, data, ct)


def download_to_local(remote_path: str, local_path: str) -> str:
    """Telecharge un fichier et le sauvegarde localement."""
    data = download_file(remote_path)
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(data)
    return local_path


# Month abbreviation mapping
EN_MONTHS = ["", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def upload_monthly_json(local_path: str, file_type: str, month: int, year: int):
    """Upload un JSON mensuel vers Supabase. file_type: sci_lease_rates, key_incentives, etc."""
    remote = f"monthly/{EN_MONTHS[month]}{year}/{file_type}.json"
    upload_local_file(local_path, remote)


def sync_from_supabase(data_dir: str):
    """Au demarrage: telecharge les JSON mensuels depuis Supabase vers le cache local."""
    try:
        ensure_bucket()
    except Exception as e:
        logger.warning(f"[Storage] Supabase non disponible, utilisation du cache local: {e}")
        return

    Path(data_dir).mkdir(parents=True, exist_ok=True)

    # List all monthly folders
    monthly_folders = list_files("monthly")
    logger.info(f"[Storage] Found {len(monthly_folders)} monthly folders on Supabase")

    for folder_name in monthly_folders:
        files = list_files(f"monthly/{folder_name}")
        for fname in files:
            if fname.endswith('.json'):
                remote_path = f"monthly/{folder_name}/{fname}"
                # Convert folder name to local filename
                # e.g. monthly/mar2026/sci_lease_rates.json -> sci_lease_rates_mar2026.json
                local_name = fname.replace('.json', f'_{folder_name}.json')
                local_path = os.path.join(data_dir, local_name)
                if not os.path.exists(local_path):
                    try:
                        download_to_local(remote_path, local_path)
                        logger.info(f"[Storage] Synced: {remote_path} -> {local_path}")
                    except Exception as e:
                        logger.warning(f"[Storage] Failed to sync {remote_path}: {e}")

    # Also sync reference files (JSON only, not PDFs - too large for startup)
    ref_files = list_files("reference")
    for fname in ref_files:
        if fname.endswith('.json') or fname.endswith('.xlsx'):
            remote_path = f"reference/{fname}"
            local_path = os.path.join(data_dir, fname)
            if not os.path.exists(local_path):
                try:
                    download_to_local(remote_path, local_path)
                    logger.info(f"[Storage] Synced ref: {remote_path} -> {local_path}")
                except Exception as e:
                    logger.warning(f"[Storage] Failed to sync ref {remote_path}: {e}")
