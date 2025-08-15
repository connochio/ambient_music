import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_MEDIA_PLAYERS,
    CONF_PLAYLISTS,
)

def _clean_playlists(playlists):
    if isinstance(playlists, str):
        # Could happen in older entries, split on newlines
        playlists = [line.strip() for line in playlists.splitlines()]
    elif not isinstance(playlists, list):
        playlists = []

    # Strip whitespace, remove blanks
    return [p.strip() for p in playlists if p and p.strip()]


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
