from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_INFO, CONF_PLAYLISTS


def _get_playlist_mapping(entry: ConfigEntry):
    raw = entry.options.get(CONF_PLAYLISTS, entry.data.get(CONF_PLAYLISTS, {}))
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return {s: "" for s in (x.strip() for x in raw) if s}
    if isinstance(raw, str):
        return {s: "" for s in (x.strip() for x in raw.splitlines()) if s}
    return {}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    mapping = _get_playlist_mapping(entry)
    playlists = list(mapping.keys())
    entity = AmbientMusicPlaylistSelect(playlists, mapping)
    async_add_entities([entity])


class AmbientMusicPlaylistSelect(SelectEntity):
    def __init__(self, options, mapping):
        self._attr_name = "Ambient Music Playlists"
        self._attr_unique_id = "ambient_music_playlists"
        self._attr_options = options
        self._attr_current_option = options[0] if options else None
        self._mapping = mapping  # {name: spotify_id}

    @property
    def device_info(self):
        return DEVICE_INFO

    async def async_select_option(self, option: str) -> None:
        if option in self._attr_options:
            self._attr_current_option = option
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        attrs = {"playlists": self._mapping}
        if self._attr_current_option:
            attrs["current_spotify_id"] = self._mapping.get(
                self._attr_current_option, ""
            )
        return attrs
