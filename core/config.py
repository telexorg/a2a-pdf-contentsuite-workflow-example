import os
from typing import Literal
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class PDFToMarkdownConfig:
    base_url: str


@dataclass
class PPTXCreatorConfig:
    base_url: str


@dataclass
class MailerConfig:
    base_url: str


@dataclass
class PodcastCreatorConfig:
    base_url: str


@dataclass
class SpotifyUploaderConfig:
    base_url: str


@dataclass
class TextToSpeechAgentConfig:
    base_url: str


class CommonModel:
    name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = os.getenv("GEMINI_API_KEY")


@dataclass
class Config:
    base_url: str
    pdf_to_markdown: PDFToMarkdownConfig
    pptx_creator: PPTXCreatorConfig
    mailer: MailerConfig
    podcast_creator: PodcastCreatorConfig
    spotify_uploader: SpotifyUploaderConfig
    text_to_speech: TextToSpeechAgentConfig

    common_model = CommonModel

    app_env: Literal["local", "staging", "production"] = os.getenv("APP_ENV", "staging")

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5700"))
    base_path = os.getenv("BASE_PATH", "").rstrip("/")

    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    minio_bucket_name = os.getenv("MINIO_BUCKET_NAME")
    minio_bucket_access_key = os.getenv("MINIO_BUCKET_ACCESS_KEY")
    minio_bucket_prefix = os.getenv("MINIO_BUCKET_PREFIX")
    minio_bucket_secret_key=os.getenv("MINIO_BUKCET_SECRET_KEY")

def create_config() -> Config:
    base_url = os.getenv("BASE_URL", "http://localhost:5700")

    return Config(
        base_url=base_url,
        pdf_to_markdown=PDFToMarkdownConfig(base_url=f"{base_url}/pdf-to-markdown"),
        pptx_creator=PPTXCreatorConfig(base_url=f"{base_url}/pptx-creator"),
        mailer=MailerConfig(base_url=f"{base_url}/mailer"),
        podcast_creator=PodcastCreatorConfig(base_url=f"{base_url}/podcast-creator"),
        spotify_uploader=SpotifyUploaderConfig(base_url=f"{base_url}/spotify-uploader"),
        text_to_speech=TextToSpeechAgentConfig(base_url=f"{base_url}/text-to-speech"),
    )


config = create_config()
