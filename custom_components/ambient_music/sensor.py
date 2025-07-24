from datetime import datetime
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN, DEVICE_INFO

TIME_SENSORS = [
    ("Daytime Hours", "input_datetime.ambient_music_daytime_start", "input_datetime.ambient_music_daytime_end"),
    ("Nighttime Hours", "input_datetime.ambient_music_nighttime_start", "input_datetime.ambient_music_nighttime_end")
]

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    async_add_entities([
        AmbientMusicTimeOfDaySensor(hass, name, start_entity_id, end_entity_id)
        for name, start_entity_id, end_entity_id in TIME_SENSORS
    ])

class AmbientMusicTimeOfDaySensor(BinarySensorEntity):
    def __init__(self, hass, name, start_entity_id, end_entity_id):
        self.hass = hass
        self._attr_name = f"Ambient Music {name}"
        self._attr_unique_id = self._attr_name.lower().replace(" ", "_")
        self._start_entity_id = start_entity_id
        self._end_entity_id = end_entity_id
        self._attr_is_on = False

    async def async_added_to_hass(self):
        self._update_state()
        async_track_time_change(
            self.hass, self._handle_time_change,
            hour="*", minute="*", second=0
        )

    @callback
    def _handle_time_change(self, now):
        self._update_state()

    def _get_time_from_entity(self, entity_id):
        state = self.hass.states.get(entity_id)
        if state and state.state and ":" in state.state:
            try:
                return datetime.strptime(state.state, "%H:%M:%S").time()
            except ValueError:
                try:
                    return datetime.strptime(state.state, "%H:%M").time()
                except ValueError:
                    return None
        return None

    def _update_state(self):
        start_time = self._get_time_from_entity(self._start_entity_id)
        end_time = self._get_time_from_entity(self._end_entity_id)
        now = datetime.now().time()

        if start_time and end_time:
            if start_time <= end_time:
                self._attr_is_on = start_time <= now <= end_time
            else:
                self._attr_is_on = now >= start_time or now <= end_time
        else:
            self._attr_is_on = False

        self.async_write_ha_state()

    @property
    def device_info(self):
        return DEVICE_INFO