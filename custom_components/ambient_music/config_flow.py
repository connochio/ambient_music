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

class AmbientMusicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
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
