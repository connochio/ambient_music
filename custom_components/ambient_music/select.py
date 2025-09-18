from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEVICE_INFO, CONF_PLAYLISTS

def _get_playlist_mapping(entry: ConfigEntry) -> dict[str, str]:
    raw = entry.options.get(CONF_PLAYLISTS, {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}

def _to_playlist_uri(stored_id: str) -> tuple[str, str]:
    if not stored_id:
        return ("", "")
    if len(stored_id) == 34:
        return ("youtube", f"ytmusic://playlist/{stored_id}")
    if len(stored_id) == 22:
        return ("spotify", f"spotify:playlist:{stored_id}")
    if len(stored_id) < 4:
        return ("local", f"library://playlist/{stored_id}")
    return ("", "")

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    mapping = _get_playlist_mapping(entry)
    playlists = list(mapping.keys())
    entity = AmbientMusicPlaylistSelect(playlists, mapping)
    async_add_entities([entity])

class AmbientMusicPlaylistSelect(SelectEntity, RestoreEntity):
    _attr_should_poll = False
    _attr_name = "Ambient Music Playlists"
    _attr_unique_id = "ambient_music_playlists"

    def __init__(self, options: list[str], mapping: dict[str, str]):
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
        for name, cid in self._mapping.items():
            prov, uri = _to_playlist_uri(cid)
            uri_map[name] = uri
            provider_map[name] = prov

        attrs = {
            "playlists": dict(self._mapping),
            "playlist_uris": uri_map,
            "playlist_providers": provider_map,
        }

        current_name = self._attr_current_option or ""
        current_cid = self._mapping.get(current_name, "")
        curr_prov, curr_uri = _to_playlist_uri(current_cid)

        attrs["current_playlist_id"] = current_cid
        attrs["current_playlist_uri"] = curr_uri
        attrs["current_spotify_id"] = current_cid if curr_prov == "spotify" else ""
        attrs["current_spotify_uri"] = curr_uri if curr_prov == "spotify" else ""

        return attrs
