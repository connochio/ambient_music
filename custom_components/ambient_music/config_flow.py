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

def _clean_name_list(playlists):
    if isinstance(playlists, str):
        playlists = [line.strip() for line in playlists.splitlines()]
    elif not isinstance(playlists, list):
        playlists = []
    return [p.strip() for p in playlists if p and p.strip()]

def _normalize_mapping(raw):
    if isinstance(raw, dict):
        out = {}
        for k, v in raw.items():
            name = str(k).strip()
            sid = str(v).strip() if v is not None else ""
            if name:
                out[name] = sid
        return out
    names = _clean_name_list(raw)
    return {n: "" for n in names}

_SPOTIFY_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")

def _extract_spotify_id(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    if _SPOTIFY_ID_RE.fullmatch(text):
        return text
    m = re.search(r"(?:playlist/|playlist:)([A-Za-z0-9]{22})", text)
    return m.group(1) if m else ""

def _get_players_and_map(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    opts = entry.options or {}
    data = entry.data or {}
    players = opts.get(CONF_MEDIA_PLAYERS, data.get(CONF_MEDIA_PLAYERS, []))
    playlist_map = _normalize_mapping(opts.get(CONF_PLAYLISTS, data.get(CONF_PLAYLISTS, {})))
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

class AmbientMusicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            user_input[CONF_PLAYLISTS] = _clean_name_list(user_input[CONF_PLAYLISTS])
            return self.async_create_entry(title="Ambient Music", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_MEDIA_PLAYERS): EntitySelector(
                    EntitySelectorConfig(domain="media_player", multiple=True)
                ),
                vol.Required(CONF_PLAYLISTS): TextSelector(
                    TextSelectorConfig(multiline=False, multiple=True)
                ),
            })
        )

    async def async_step_reconfigure(self, user_input=None):
        errors = {}
        current_entry = self._get_reconfigure_entry()
        current_data = current_entry.data

        if user_input is not None:
            user_input[CONF_PLAYLISTS] = _clean_name_list(user_input[CONF_PLAYLISTS])
            return self.async_update_reload_and_abort(
                current_entry,
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_MEDIA_PLAYERS,
                    default=current_data.get(CONF_MEDIA_PLAYERS, [])
                ): EntitySelector(
                    EntitySelectorConfig(domain="media_player", multiple=True)
                ),
                vol.Required(
                    CONF_PLAYLISTS,
                    default=current_data.get(CONF_PLAYLISTS, [])
                ): TextSelector(
                    TextSelectorConfig(multiline=False, multiple=True)
                ),
            }),
            errors=errors,
        )

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
                "media_players": "Core settings (media players)",
                "add_playlist": "Add playlist",
                "manage_playlists": "Manage playlists (edit/remove)",
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
            elif name in playlist_map:
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
                description_placeholders={"msg": "No playlists configured yet."},
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
            new_name = str(user_input["name"]).strip()
            raw = str(user_input[CONF_SPOTIFY_ID]).strip()
            sid = _extract_spotify_id(raw)

            errors = {}
            if not new_name:
                errors["name"] = "required"
            elif new_name != old_name and new_name in playlist_map:
                errors["name"] = "already_configured"
            if not sid:
                errors[CONF_SPOTIFY_ID] = "invalid_spotify_id"

            if errors:
                return self.async_show_form(
                    step_id="edit_playlist",
                    data_schema=_add_schema(default_name=new_name or old_name, default_sid=raw),
                    errors=errors,
                )

            if new_name != old_name:
                playlist_map.pop(old_name, None)
            playlist_map[new_name] = sid

            options = {
                CONF_MEDIA_PLAYERS: players,
                CONF_PLAYLISTS: playlist_map,
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="edit_playlist",
            data_schema=_add_schema(default_name=old_name, default_sid=old_id),
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
