from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEVICE_INFO, CONF_PLAYLISTS, CONF_PLAYLIST_RADIO_MODE
from .providers import playlist_id_to_uri

def _get_playlist_mapping(entry: ConfigEntry) -> dict[str, dict]:
    raw = entry.options.get(CONF_PLAYLISTS, {})
    if not isinstance(raw, dict):
        return {}
    
    mapping = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            mapping[str(k)] = v
        else:
            mapping[str(k)] = {"id": str(v), CONF_PLAYLIST_RADIO_MODE: False}
    
    return mapping

def _playlist_to_id(playlist_data) -> str:
    if isinstance(playlist_data, dict):
        return playlist_data.get("id", "")
    return str(playlist_data) if playlist_data else ""

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    mapping = _get_playlist_mapping(entry)
    playlists = list(mapping.keys())
    entity = AmbientMusicPlaylistSelect(playlists, mapping)
    async_add_entities([entity])

class AmbientMusicPlaylistSelect(SelectEntity, RestoreEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "playlists"
    _attr_unique_id = "ambient_music_playlists"

    def __init__(self, options: list[str], mapping: dict[str, dict]):
        self._attr_options = options
        self._mapping = mapping
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in (self._attr_options or []):
            self._attr_current_option = last.state

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return
        if option == self._attr_current_option:
            return
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def device_info(self):
        return DEVICE_INFO

    @property
    def extra_state_attributes(self):
        uri_map: dict[str, str] = {}
        provider_map: dict[str, str] = {}
        radio_mode_map: dict[str, bool] = {}
        
        for name, playlist_data in self._mapping.items():
            playlist_id = _playlist_to_id(playlist_data)
            prov, uri = playlist_id_to_uri(playlist_id)
            uri_map[name] = uri if prov else ""
            provider_map[name] = prov if prov else ""
            radio_mode_map[name] = bool(
                playlist_data.get(CONF_PLAYLIST_RADIO_MODE, False)
                if isinstance(playlist_data, dict) else False
            )

        attrs = {
            "playlists": {},
            "playlist_uris": uri_map,
            "playlist_providers": provider_map,
            "playlist_radio_modes": radio_mode_map,
        }

        for name, playlist_data in self._mapping.items():
            attrs["playlists"][name] = _playlist_to_id(playlist_data)

        current_name = self._attr_current_option or ""
        current_data = self._mapping.get(current_name, {})
        current_cid = _playlist_to_id(current_data)
        curr_prov, curr_uri = playlist_id_to_uri(current_cid)
        current_radio_mode = bool(
            current_data.get(CONF_PLAYLIST_RADIO_MODE, False)
            if isinstance(current_data, dict) else False
        )

        attrs["current_playlist_id"] = current_cid
        attrs["current_playlist_uri"] = curr_uri if curr_prov else ""
        attrs["current_playlist_radio_mode"] = current_radio_mode

        return attrs
