from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_PLAYLISTS, DEVICE_INFO

SELECT_ENTITY_ID = "select.ambient_music_playlist"

class PlaylistEnabledSensor(BinarySensorEntity):
    def __init__(self, hass: HomeAssistant, playlist_name: str):
        self.hass = hass
        self._playlist_name = playlist_name
        self._attr_name = f"{playlist_name} Enabled"
        self._attr_unique_id = f"ambient_music_{DOMAIN}_{playlist_name.lower().replace(' ', '_')}_enabled"
        self._attr_is_on = False

    async def async_added_to_hass(self):
        self._update_state()

        @callback
        def handle_select_change(event):
            self._update_state()

        async_track_state_change_event(self.hass, SELECT_ENTITY_ID, handle_select_change)

    def _update_state(self):
        state = self.hass.states.get(SELECT_ENTITY_ID)
        self._attr_is_on = state and state.state == self._playlist_name
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
    async_add_entities(sensors)
