import re
from dataclasses import dataclass
from typing import Callable, Optional

@dataclass
class PlaylistProvider:
    name: str
    id_pattern: re.Pattern
    url_patterns: list[str]
    uri_template: str
    keywords: list[str]
    extract_id: Optional[Callable[[str], str]] = None

    def __post_init__(self):
        if self.extract_id is None:
            self.extract_id = self._generic_extract

    def _generic_extract(self, text: str) -> str:
        if not text:
            return ""
        s = text.strip()

        if self.id_pattern.fullmatch(s):
            return s

        for url_pattern in self.url_patterns:
            m = re.search(url_pattern, s, flags=re.IGNORECASE)
            if m:
                extracted = m.group(1)
                if self.id_pattern.fullmatch(extracted):
                    return extracted
        return ""

PROVIDERS = {
    "spotify": PlaylistProvider(
        name="spotify",
        id_pattern=re.compile(r"^[A-Za-z0-9]{22}$"),
        url_patterns=[
            r"(?:spotify:playlist:|open\.spotify\.com/playlist/|spotify://playlist/)([A-Za-z0-9]{22})",
        ],
        uri_template="spotify://playlist/{id}",
        keywords=["spotify"],
    ),
    "youtube": PlaylistProvider(
        name="youtube",
        id_pattern=re.compile(r"^[A-Za-z0-9_-]{34}$"),
        url_patterns=[
            r"(?:list=|youtube:playlist:|ytmusic://playlist/)([A-Za-z0-9_-]{34})",
        ],
        uri_template="ytmusic://playlist/{id}",
        keywords=["youtube", "music.youtube.com", "ytmusic"],
    ),
    "local": PlaylistProvider(
        name="local",
        id_pattern=re.compile(r"^[0-9]{1,3}$"),
        url_patterns=[
            r"(?:media-source://mass/playlists/|library://playlist/)([0-9]{1,3})",
        ],
        uri_template="library://playlist/{id}",
        keywords=["library", "media-source"],
    ),
    "tidal": PlaylistProvider(
        name="tidal",
        id_pattern=re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
        url_patterns=[
            r"(?:tidal://playlist/|(?:https?://)?(?:www\.)?tidal\.com/playlist/)([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        ],
        uri_template="tidal://playlist/{id}",
        keywords=["tidal"],
    ),
    "apple": PlaylistProvider(
        name="apple",
        id_pattern=re.compile(r"^[A-Za-z0-9]{32}$"),
        url_patterns=[
            r"(?:https?://)?(?:www\.)?music\.apple\.com/[a-z]{2}/playlist/[^/]+/pl\.([A-Za-z0-9]{32})",
        ],
        uri_template="apple_music://playlist/{id}",
        keywords=["apple", "apple_music", "music.apple.com"],
    ),
    "deezer": PlaylistProvider(
        name="deezer",
        id_pattern=re.compile(r"^[0-9]{7,12}$"),
        url_patterns=[
            r"(?:(?:https?://)?(?:www\.)?deezer\.com/(?:[a-zA-Z]{2,3}/)?playlist/|deezer://playlist/)([0-9]{7,12})",
        ],
        uri_template="deezer://playlist/{id}",
        keywords=["deezer"],
    ),
}

def get_provider_for_id(playlist_id: str) -> Optional[PlaylistProvider]:
    if not playlist_id:
        return None
    
    for provider in PROVIDERS.values():
        if provider.id_pattern.fullmatch(playlist_id):
            return provider
    
    return None

def parse_playlist_input(text: str) -> tuple[Optional[str], str]:
    if not text:
        return None, ""
    
    s = text.strip()
    for provider_name, provider in PROVIDERS.items():
        for keyword in provider.keywords:
            if keyword in s:
                playlist_id = provider.extract_id(s)
                if playlist_id:
                    return provider_name, playlist_id
    for provider_name, provider in PROVIDERS.items():
        playlist_id = provider.extract_id(s)
        if playlist_id:
            return provider_name, playlist_id
    
    return None, ""

def playlist_id_to_uri(playlist_id: str) -> tuple[Optional[str], str]:
    if not playlist_id:
        return None, ""
    
    provider = get_provider_for_id(playlist_id)
    if not provider:
        return None, ""
    
    uri = provider.uri_template.format(id=playlist_id)
    return provider.name, uri
