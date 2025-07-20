from apps import (
    pdf_to_markdown,
    pptx_creator,
    mailer,
    podcast_creator,
    spotify_uploader,
)

from core.agent_list import get_agent_config_by_id

pdf_to_markdown_agent = get_agent_config_by_id("pdf-to-markdown")
pdf_to_markdown_agent.app = pdf_to_markdown.app

pptx_creator_agent = get_agent_config_by_id("pptx-creator")
pptx_creator_agent.app = pptx_creator.app

mailer_agent = get_agent_config_by_id("mailer")
mailer_agent.app = mailer.app

podcast_creator_agent = get_agent_config_by_id("podcast-creator")
podcast_creator_agent.app = podcast_creator.app

spotify_uploader_agent = get_agent_config_by_id("spotify-uploader")
spotify_uploader_agent.app = spotify_uploader.app

AGENT_APPS = [
    pdf_to_markdown_agent,
    pptx_creator_agent,
    mailer_agent,
    podcast_creator_agent,
    spotify_uploader_agent,
]
