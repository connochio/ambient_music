from homeassistant.components.input_datetime import InputDatetimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEVICE_INFO

ENTITIES = [
    ("Daytime Start", "daytime_start"),
    ("Daytime End", "daytime_end"),
    ("Nighttime Start", "nighttime_start"),
    ("Nighttime End", "nighttime_end")
]

DEFAULT_TIMES = {
    "daytime_start": "07:00:00",
    "daytime_end": "19:00:00",
    "nighttime_start": "19:00:00",
    "nighttime_end": "07:00:00"
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    entities = [
        AmbientMusicInputDatetime(name, uid, DEFAULT_TIMES[uid])
        for name, uid in ENTITIES
    ]
    async_add_entities(entities)

class AmbientMusicInputDatetime(InputDatetimeEntity):
    def __init__(self, name: str, uid: str, default_time: str):
        self._attr_name = f"Ambient Music {name}"
        self._attr_unique_id = f"ambient_music_{uid}"
        hour, minute, second = map(int, default_time.split(":"))
        self._attr_has_date = False
        self._attr_has_time = True
        self._attr_native_value = None
        self._hour = hour
        self._minute = minute
        self._second = second

    async def async_added_to_hass(self):
        self._attr_native_value = self._create_time(self._hour, self._minute, self._second)

    def _create_time(self, hour, minute, second):
        from datetime import time
        return time(hour=hour, minute=minute, second=second)

    @property
    def device_info(self):
        return DEVICE_INFO