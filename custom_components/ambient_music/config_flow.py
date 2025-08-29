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
)


def _clean_playlists(playlists):
    if isinstance(playlists, str):
        playlists = [line.strip() for line in playlists.splitlines()]
    elif not isinstance(playlists, list):
        playlists = []

    cleaned = [p.strip() for p in playlists if p and p.strip()]
    seen = set()
    result = []
    for p in cleaned:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def _get_current(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    opts = entry.options or {}
    data = entry.data or {}
    players = opts.get(CONF_MEDIA_PLAYERS, data.get(CONF_MEDIA_PLAYERS, []))
    playlists = opts.get(CONF_PLAYLISTS, data.get(CONF_PLAYLISTS, []))
    return players, _clean_playlists(playlists)


class AmbientMusicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            user_input[CONF_PLAYLISTS] = _clean_playlists(user_input[CONF_PLAYLISTS])
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
            user_input[CONF_PLAYLISTS] = _clean_playlists(user_input[CONF_PLAYLISTS])
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

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "core": "Core settings",
                "add_playlists": "Add playlists",
                "remove_playlists": "Remove playlists",
            },
        )

    async def async_step_core(self, user_input=None):
        current_players, current_playlists = _get_current(self.hass, self.config_entry)

        if user_input is not None:
            options = {
                CONF_MEDIA_PLAYERS: user_input[CONF_MEDIA_PLAYERS],
                CONF_PLAYLISTS: _clean_playlists(user_input[CONF_PLAYLISTS]),
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="core",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_MEDIA_PLAYERS,
                    default=current_players
                ): EntitySelector(
                    EntitySelectorConfig(domain="media_player", multiple=True)
                ),
                vol.Required(
                    CONF_PLAYLISTS,
                    default=current_playlists
                ): TextSelector(
                    TextSelectorConfig(multiline=False, multiple=True)
                ),
            }),
        )

    async def async_step_add_playlists(self, user_input=None):
        _, current_playlists = _get_current(self.hass, self.config_entry)

        if user_input is not None:
            to_add = _clean_playlists(user_input[CONF_PLAYLISTS])
            merged = _clean_playlists(current_playlists + to_add)
            options = {
                CONF_MEDIA_PLAYERS: _get_current(self.hass, self.config_entry)[0],
                CONF_PLAYLISTS: merged,
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="add_playlists",
            data_schema=vol.Schema({
                vol.Required(CONF_PLAYLISTS): TextSelector(
                    TextSelectorConfig(
                        multiline=False,
                        multiple=True,
                    )
                ),
            }),
            description_placeholders={
                "count": str(len(current_playlists)),
            },
        )

    async def async_step_remove_playlists(self, user_input=None):
        _, current_playlists = _get_current(self.hass, self.config_entry)

        if user_input is not None:
            to_remove = set(user_input.get(CONF_PLAYLISTS, []))
            new_list = [p for p in current_playlists if p not in to_remove]
            options = {
                CONF_MEDIA_PLAYERS: _get_current(self.hass, self.config_entry)[0],
                CONF_PLAYLISTS: new_list,
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="remove_playlists",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_PLAYLISTS,
                    default=[]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=current_playlists,
                        multiple=True,
                        custom_value=False,
                    )
                ),
            }),
        )
