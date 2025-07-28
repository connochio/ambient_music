from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, DEVICE_INFO

NUMBER_ENTITIES = [
    ("Default Volume", 0, 1, 0.01),
    ("Previous Volume", 0, 1, 0.01),
    ("Playlist Switch Wait Seconds", 0, 20, 1),
    ("Volume Fade Down Seconds", 0, 20, 1),
    ("Volume Fade Up Seconds", 0, 20, 1)
]

class AmbientMusicNumber(NumberEntity):
    def __init__(self, name, min_val, max_val, step):
        self._attr_name = f"Ambient Music {name}"
        self._attr_unique_id = self._attr_name.lower().replace(" ", "_")
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_value = min_val
        self._attr_mode = "auto"
    
    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()

    @property
    def device_info(self):
        return DEVICE_INFO

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    entities = [AmbientMusicNumber(name, min_val, max_val, step) for name, min_val, max_val, step in NUMBER_ENTITIES]
    async_add_entities(entities)
