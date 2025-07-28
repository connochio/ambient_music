from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, CONF_PLAYLISTS

class PlaylistSelectedSensor(BinarySensorEntity):
    def __init__(self, playlist_name: str, input_select_entity: str):
        self._playlist_name = playlist_name
        self._input_select_entity = input_select_entity
        self._attr_name = f"Playlist: {playlist_name} Selected"
        self._attr_unique_id = f"{input_select_entity}_{playlist_name.replace(' ', '_').lower()}_selected"
        self._attr_is_on = False

    async def async_added_to_hass(self):
        self._update_state()

        @callback
        def handle_state_change(event):
            self._update_state()

        async_track_state_change_event(
            self.hass, [self._input_select_entity], handle_state_change
        )

    def _update_state(self):
        current = self.hass.states.get(self._input_select_entity)
        if current and current.state == self._playlist_name:
            self._attr_is_on = True
        else:
            self._attr_is_on = False
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self._attr_is_on


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data = entry.data
    input_select_entity = data.get(CONF_PLAYLISTS)
    playlist_state = hass.states.get(input_select_entity)

    if not playlist_state or not hasattr(playlist_state, "attributes"):
        return

    playlist_options = playlist_state.attributes.get("options", [])
    entities = [
        PlaylistSelectedSensor(name, input_select_entity)
        for name in playlist_options
    ]
    async_add_entities(entities)
