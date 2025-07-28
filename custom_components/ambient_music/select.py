from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEVICE_INFO, CONF_PLAYLISTS

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    # CONF_PLAYLISTS is now a list, not a multiline string
    playlists = entry.data.get(CONF_PLAYLISTS, [])
    if not isinstance(playlists, list):
        playlists = [line.strip() for line in playlists.splitlines() if line.strip()]
    
    entity = AmbientMusicPlaylistSelect(playlists)
    async_add_entities([entity])

class AmbientMusicPlaylistSelect(SelectEntity):
    def __init__(self, options):
        self._attr_name = "Ambient Music Playlists"
        self._attr_unique_id = "ambient_music_playlists"
        self._attr_options = options
        self._attr_current_option = options[0] if options else None

    @property
    def device_info(self):
        return DEVICE_INFO

    async def async_select_option(self, option: str) -> None:
        if option in self._attr_options:
            self._attr_current_option = option
            self.async_write_ha_state()
