from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.tod.binary_sensor import TimeOfDaySensor

from .const import (
    CONF_DAY_START,
    CONF_DAY_END,
    CONF_NIGHT_START,
    CONF_NIGHT_END,
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = entry.data
    entities = []

    if data.get(CONF_DAY_START) and data.get(CONF_DAY_END):
        entities.append(TimeOfDaySensor(
            name="Ambient Music Daytime",
            after=data[CONF_DAY_START],
            before=data[CONF_DAY_END],
        ))

    if data.get(CONF_NIGHT_START) and data.get(CONF_NIGHT_END):
        entities.append(TimeOfDaySensor(
            name="Ambient Music Nighttime",
            after=data[CONF_NIGHT_START],
            before=data[CONF_NIGHT_END],
        ))

    async_add_entities(entities)
