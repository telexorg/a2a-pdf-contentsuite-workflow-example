from apps import (
    pdf_to_markdown,
    pptx_creator,
    mailer,
    podcast_creator,
    spotify_uploader,
    text_to_speech
)

from core.agent_list import get_agent_config_by_id

pdf_to_markdown_agent = get_agent_config_by_id("pdf-to-markdown")
pdf_to_markdown_agent.router = pdf_to_markdown.router
pdf_to_markdown_agent.app = pdf_to_markdown.app

# pptx_creator_agent = get_agent_config_by_id("pptx-creator")
# pptx_creator_agent.router = pptx_creator.router

# mailer_agent = get_agent_config_by_id("mailer")
# mailer_agent.router = mailer.router

# podcast_creator_agent = get_agent_config_by_id("podcast-creator")
# podcast_creator_agent.router = podcast_creator.router

# spotify_uploader_agent = get_agent_config_by_id("spotify-uploader")
# spotify_uploader_agent.router = spotify_uploader.router

text_to_speed_agent = get_agent_config_by_id("text-to-speech")
text_to_speed_agent.router = text_to_speech.router
text_to_speed_agent.app = text_to_speech.app

AGENT_APPS = [
    pdf_to_markdown_agent,
    # pptx_creator_agent,
    # mailer_agent,
    # podcast_creator_agent,
    # spotify_uploader_agent,
    text_to_speed_agent
]
