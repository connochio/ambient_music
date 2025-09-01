import re
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_MEDIA_PLAYERS,
    CONF_PLAYLISTS,
    CONF_SPOTIFY_ID,
)

_SPOTIFY_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")


def _extract_spotify_id(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip()
    if _SPOTIFY_ID_RE.fullmatch(text):
        return text
    m = re.search(r"(?:playlist/|playlist:)([A-Za-z0-9]{22})", text)
    return m.group(1) if m else ""


def _get_players_and_map(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    opts = entry.options or {}
    players = opts.get(CONF_MEDIA_PLAYERS, [])
    playlist_map = opts.get(CONF_PLAYLISTS, {})
    if not isinstance(players, list):
        players = []
    if not isinstance(playlist_map, dict):
        playlist_map = {}
    playlist_map = {str(k): str(v) for k, v in playlist_map.items()}
    return players, playlist_map


def _add_schema(default_name: str = "", default_sid: str = "") -> vol.Schema:
    return vol.Schema({
        vol.Required("name", default=default_name): TextSelector(
            TextSelectorConfig(multiline=False)
        ),
        vol.Required(CONF_SPOTIFY_ID, default=default_sid): TextSelector(
            TextSelectorConfig(multiline=False)
        ),
    })

def _edit_choice_schema(names: list[str]) -> vol.Schema:
    return vol.Schema({
        vol.Required("action"): SelectSelector(
            SelectSelectorConfig(
                options=["Edit", "Remove"],
                multiple=False,
                custom_value=False,
            )
        ),
        vol.Required("playlist"): SelectSelector(
            SelectSelectorConfig(
                options=names,
                multiple=False,
                custom_value=False,
            )
        ),
    })

def _readonly_name_and_id_schema(name: str, default_sid: str) -> vol.Schema:
    return vol.Schema({
        vol.Required("playlist_name", default=name): SelectSelector(
            SelectSelectorConfig(
                options=[name],
                multiple=False,
                custom_value=False,
            )
        ),
        vol.Required(CONF_SPOTIFY_ID, default=default_sid): TextSelector(
            TextSelectorConfig(multiline=False)
        ),
    })

class AmbientMusicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Ambient Music", data={})

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._edit_target = None

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "add_playlist": "Add Playlist",
                "manage_playlists": "Manage Playlists",
                "media_players": "Media Players",
            },
        )

    async def async_step_media_players(self, user_input=None):
        current_players, playlist_map = _get_players_and_map(self.hass, self.config_entry)

        if user_input is not None:
            options = {
                CONF_MEDIA_PLAYERS: user_input[CONF_MEDIA_PLAYERS],
                CONF_PLAYLISTS: playlist_map,
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="media_players",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_MEDIA_PLAYERS,
                    default=current_players
                ): EntitySelector(
                    EntitySelectorConfig(domain="media_player", multiple=True)
                ),
            }),
        )

    async def async_step_add_playlist(self, user_input=None):
        _, playlist_map = _get_players_and_map(self.hass, self.config_entry)

        if user_input is not None:
            name = str(user_input["name"]).strip()
            raw = str(user_input[CONF_SPOTIFY_ID]).strip()
            sid = _extract_spotify_id(raw)

            errors = {}
            if not name:
                errors["name"] = "required"
            else:
                existing_lower = {n.lower() for n in playlist_map}
                if name.lower() in existing_lower:
                    errors["name"] = "already_configured"
            if not sid:
                errors[CONF_SPOTIFY_ID] = "invalid_spotify_id"

            if errors:
                return self.async_show_form(
                    step_id="add_playlist",
                    data_schema=_add_schema(default_name=name, default_sid=raw),
                    errors=errors,
                )

            playlist_map[name] = sid
            options = {
                CONF_MEDIA_PLAYERS: _get_players_and_map(self.hass, self.config_entry)[0],
                CONF_PLAYLISTS: playlist_map,
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(step_id="add_playlist", data_schema=_add_schema())

    async def async_step_manage_playlists(self, user_input=None):
        _, playlist_map = _get_players_and_map(self.hass, self.config_entry)
        names = list(playlist_map.keys())

        if not names:
            return self.async_show_form(
                step_id="manage_playlists",
                data_schema=vol.Schema({}),
                errors={"base": "no_playlists"},
            )

        if user_input is not None:
            action = user_input["action"]
            chosen = user_input["playlist"]
            if action == "Edit":
                self._edit_target = chosen
                return await self.async_step_edit_playlist()
            return await self.async_step_remove_playlists()

        return self.async_show_form(
            step_id="manage_playlists",
            data_schema=_edit_choice_schema(names),
        )

    async def async_step_edit_playlist(self, user_input=None):
        players, playlist_map = _get_players_and_map(self.hass, self.config_entry)
        old_name = self._edit_target or ""
        old_id = playlist_map.get(old_name, "")

        if user_input is not None:
            raw = str(user_input.get(CONF_SPOTIFY_ID, "")).strip()
            sid = _extract_spotify_id(raw)

            errors = {}
            if not sid:
                errors[CONF_SPOTIFY_ID] = "invalid_spotify_id"

            if errors:
                return self.async_show_form(
                    step_id="edit_playlist",
                    data_schema=_readonly_name_and_id_schema(old_name, raw),
                    errors=errors,
                )

            playlist_map[old_name] = sid
            options = {
                CONF_MEDIA_PLAYERS: players,
                CONF_PLAYLISTS: playlist_map,
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="edit_playlist",
            data_schema=_readonly_name_and_id_schema(old_name, old_id),
        )

    async def async_step_remove_playlists(self, user_input=None):
        players, playlist_map = _get_players_and_map(self.hass, self.config_entry)
        names = list(playlist_map.keys())

        if user_input is not None:
            to_remove = set(user_input.get(CONF_PLAYLISTS, []))
            for n in list(playlist_map.keys()):
                if n in to_remove:
                    playlist_map.pop(n, None)

            options = {
                CONF_MEDIA_PLAYERS: players,
                CONF_PLAYLISTS: playlist_map,
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="remove_playlists",
            data_schema=vol.Schema({
                vol.Required(CONF_PLAYLISTS, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=names,
                        multiple=True,
                        custom_value=False,
                    )
                ),
            }),
        )
