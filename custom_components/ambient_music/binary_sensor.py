import re
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er

from .const import CONF_PLAYLISTS, DEVICE_INFO

SELECT_ENTITY_ID = "select.ambient_music_playlists"

def _slugify_playlist(playlist_name: str) -> str:
    slug = playlist_name.lower()
    slug = re.sub(r"\s+", "_", slug)
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug

def _get_playlist_names(entry: ConfigEntry):
    raw = entry.options.get(CONF_PLAYLISTS, entry.data.get(CONF_PLAYLISTS, {}))
    if isinstance(raw, dict):
        return list(raw.keys())
    if isinstance(raw, list):
        return [s for s in (x.strip() for x in raw) if s]
    if isinstance(raw, str):
        return [s for s in (x.strip() for x in raw.splitlines()) if s]
    return []

class PlaylistEnabledSensor(BinarySensorEntity, RestoreEntity):
    def __init__(self, hass: HomeAssistant, playlist_name: str):
        self.hass = hass
        self._playlist_name = playlist_name
        self._attr_name = f"Ambient Music {playlist_name} Enabled"
        self._attr_unique_id = f"ambient_music_{_slugify_playlist(playlist_name)}_enabled"
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
    playlists = _get_playlist_names(entry)

    ent_reg = er.async_get(hass)
    valid_slugs = {_slugify_playlist(p) for p in playlists}

    for entity_id, entity_entry in list(ent_reg.entities.items()):
        if (
            entity_entry.domain == "binary_sensor"
            and entity_entry.unique_id.startswith("ambient_music_")
            and entity_entry.unique_id.endswith("_enabled")
        ):
            slug = entity_entry.unique_id[len("ambient_music_"):-len("_enabled")]
            if slug not in valid_slugs:
                ent_reg.async_remove(entity_id)

    sensors = [PlaylistEnabledSensor(hass, name) for name in playlists]
    async_add_entities(sensors, True)
