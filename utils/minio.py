from minio import Minio
from core.config import config

minio_client = Minio(
    config.minio_endpoint,
    access_key=config.minio_bucket_access_key,
    secret_key=config.minio_bucket_secret_key,
)
