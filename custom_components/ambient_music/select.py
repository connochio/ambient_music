from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_INFO, CONF_PLAYLISTS

def _get_playlist_mapping(entry: ConfigEntry) -> dict[str, str]:
    """Strictly from options: {name: spotify_id}."""
    raw = entry.options.get(CONF_PLAYLISTS, {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}

def _to_uri_map(mapping: dict[str, str]) -> dict[str, str]:
    return {name: (f"spotify:playlist:{sid}" if sid else "") for name, sid in mapping.items()}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    mapping = _get_playlist_mapping(entry)          # {name: id}
    playlists = list(mapping.keys())
    entity = AmbientMusicPlaylistSelect(playlists, mapping)
    async_add_entities([entity])

class AmbientMusicPlaylistSelect(SelectEntity):
    _attr_name = "Ambient Music Playlists"
    _attr_unique_id = "ambient_music_playlists"

    def __init__(self, options: list[str], mapping: dict[str, str]):
        self._attr_options = options
        self._attr_current_option = options[0] if options else None
        self._mapping = mapping                  # {name: id}
        self._uri_map = _to_uri_map(mapping)     # {name: uri}

    @property
    def device_info(self):
        return DEVICE_INFO

    async def async_select_option(self, option: str) -> None:
        if option in self._attr_options:
            self._attr_current_option = option
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        attrs = {
            "playlists": self._mapping,      # {name: spotify_id}
            "playlist_uris": self._uri_map,  # {name: spotify:playlist:<id>}
        }
        current_id = ""
        current_uri = ""
        if self._attr_current_option:
            current_id = self._mapping.get(self._attr_current_option, "")
            current_uri = self._uri_map.get(self._attr_current_option, "")
        attrs["current_spotify_id"] = current_id
        attrs["current_spotify_uri"] = current_uri
        return attrs
