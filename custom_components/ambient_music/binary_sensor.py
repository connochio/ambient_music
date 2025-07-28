from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, CONF_PLAYLISTS, DEVICE_INFO

SELECT_ENTITY_ID = "select.ambient_music_playlists"

class PlaylistEnabledSensor(BinarySensorEntity, RestoreEntity):
    def __init__(self, hass: HomeAssistant, playlist_name: str):
        self.hass = hass
        self._playlist_name = playlist_name
        self._attr_name = f"Ambient Music {playlist_name} Enabled"
        self._attr_unique_id = f"ambient_music_{playlist_name.lower().replace(' ', '_')}_enabled"
        self._attr_is_on = False

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()):
            self._attr_is_on = last_state.state == "on"

        async_track_state_change_event(self.hass, SELECT_ENTITY_ID, self._handle_select_change)
        self._update_state()

    @callback
    def _handle_select_change(self, event):
        self._update_state()

    @callback
    def _update_state(self):
        state = self.hass.states.get(SELECT_ENTITY_ID)
        if state and state.state:
            self._attr_is_on = state.state == self._playlist_name
            self.async_write_ha_state()

    @property
    def is_on(self):
        return self._attr_is_on

    @property
    def device_info(self):
        return DEVICE_INFO

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    playlists = entry.data.get(CONF_PLAYLISTS, [])
    if isinstance(playlists, str):
        playlists = playlists.splitlines()

    sensors = [PlaylistEnabledSensor(hass, name) for name in playlists]
    async_add_entities(sensors, True)
