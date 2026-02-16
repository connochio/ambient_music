import logging
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

class _WatcherServiceCall:
    def __init__(self):
        self.data = {}

async def async_setup_watchers(
    hass: HomeAssistant,
    entry_id: str,
    play_handler: callable,
    pause_handler: callable,
    stop_handler: callable
):
    unsubscribe_blockers = async_track_state_change_event(
        hass,
        "binary_sensor.ambient_music_blockers_clear",
        lambda event: _handle_blockers_change(hass, event, stop_handler)
    )

    unsubscribe_playlist = async_track_state_change_event(
        hass,
        "select.ambient_music_playlists",
        lambda event: _handle_playlist_change(hass, event, pause_handler, play_handler)
    )

    def cleanup():
        unsubscribe_blockers()
        unsubscribe_playlist()

    return cleanup

@callback
def _handle_blockers_change(hass: HomeAssistant, event, stop_handler: callable):
    new_state = event.data.get("new_state")
    old_state = event.data.get("old_state")

    if not new_state or not old_state:
        return

    if old_state.state == "on" and new_state.state == "off":
        _LOGGER.debug("Blockers activated, triggering stop via watcher")
        call = _WatcherServiceCall()
        hass.loop.create_task(stop_handler(call))

@callback
def _handle_playlist_change(hass: HomeAssistant, event, pause_handler: callable, play_handler: callable):
    new_state = event.data.get("new_state")
    old_state = event.data.get("old_state")

    if not new_state:
        return

    if old_state and new_state.state == old_state.state:
        return

    if new_state.state not in ("unknown", "unavailable"):
        _LOGGER.debug(f"Playlist changed to {new_state.state}, triggering switchover via watcher")
        call = _WatcherServiceCall()
        
        async def _switchover():
            await pause_handler(call)
            await play_handler(call)
        
        hass.loop.create_task(_switchover())
