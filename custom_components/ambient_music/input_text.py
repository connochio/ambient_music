from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEVICE_INFO

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    entity = AmbientMusicText("Previous Playlist")
    async_add_entities([entity])

class AmbientMusicText(TextEntity):
    def __init__(self, name):
        self._attr_name = f"Ambient Music {name}"
        self._attr_unique_id = self._attr_name.lower().replace(" ", "_")
        self._attr_native_value = ""

    @property
    def device_info(self):
        return DEVICE_INFO