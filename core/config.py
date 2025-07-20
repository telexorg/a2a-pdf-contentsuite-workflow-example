import os
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

    common_model = CommonModel

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5700"))
    base_path = os.getenv("BASE_PATH", "")

def create_config() -> Config:
    base_url = os.getenv("BASE_URL", "http://localhost:5700")

    return Config(
        base_url=base_url,
        pdf_to_markdown=PDFToMarkdownConfig(base_url=f"{base_url}/pdf-to-markdown"),
        pptx_creator=PPTXCreatorConfig(base_url=f"{base_url}/pptx-creator"),
        mailer=MailerConfig(base_url=f"{base_url}/mailer"),
        podcast_creator=PodcastCreatorConfig(base_url=f"{base_url}/podcast-creator"),
        spotify_uploader=SpotifyUploaderConfig(base_url=f"{base_url}/spotify-uploader"),
    )


config = create_config()
