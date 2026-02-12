from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEVICE_INFO

NUMBER_ENTITIES = [
    ("default_volume", 0, 1, 0.01),
    ("playlist_switch_wait_seconds", 0, 20, 1),
    ("volume_fade_down_seconds", 0, 20, 1),
    ("volume_fade_up_seconds", 0, 20, 1),
]

class AmbientMusicNumber(NumberEntity, RestoreEntity):
    _attr_should_poll = False
    _attr_device_class = None
    _attr_has_entity_name = True

    def __init__(self, key: str, min_val: float, max_val: float, step: float) -> None:
        self._attr_translation_key = key
        self._attr_unique_id = f"ambient_music_{key}"
        self._attr_native_min_value = float(min_val)
        self._attr_native_max_value = float(max_val)
        self._attr_native_step = float(step)
        self._attr_mode = "auto"
        self._attr_native_value = float(min_val)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last = await self.async_get_last_state()
        if last and last.state not in (None, "", "unknown", "unavailable"):
            try:
                restored = float(last.state)
                if restored != self._attr_native_value:
                    self._attr_native_value = restored
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        v = float(value)
        if self._attr_native_value == v:
            return
        self._attr_native_value = v
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        return float(self._attr_native_value)

    @property
    def device_info(self):
        return DEVICE_INFO

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
    ) -> None:
    entities = [
        AmbientMusicNumber(key, min_val, max_val, step)
        for key, min_val, max_val, step in NUMBER_ENTITIES
    ]
    async_add_entities(entities)
