"""State-change watchers that trigger play/pause/stop in response to blocker or playlist changes."""

import logging
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)


class _WatcherServiceCall:
    """Minimal stand-in for ServiceCall so watcher-triggered handlers get a valid call object."""

    def __init__(self):
        self.data = {}

async def async_setup_watchers(
    hass: HomeAssistant,
    entry_id: str,
    play_handler: callable,
    pause_handler: callable,
    stop_handler: callable,
    debouncer
):
    """
    Subscribe to blocker and playlist state changes and wire them to service handlers.

    :param hass: Home Assistant instance.
    :param entry_id: Config entry ID (reserved for future per-entry scoping).
    :param play_handler: Coroutine called when playback should start.
    :param pause_handler: Coroutine called when playback should pause (switchover).
    :param stop_handler: Coroutine called when playback should stop.
    :param debouncer: Service debouncer shared with the service layer.
    :return: Cleanup callable that removes all subscriptions.
    """
    unsubscribe_blockers = async_track_state_change_event(
        hass,
        "binary_sensor.ambient_music_blockers_clear",
        lambda event: _handle_blockers_change(hass, event, stop_handler, play_handler, debouncer)
    )

    unsubscribe_playlist = async_track_state_change_event(
        hass,
        "select.ambient_music_playlists",
        lambda event: _handle_playlist_change(hass, event, pause_handler, play_handler, debouncer)
    )

    def cleanup():
        unsubscribe_blockers()
        unsubscribe_playlist()

    return cleanup

@callback
def _handle_blockers_change(hass: HomeAssistant, event, stop_handler: callable, play_handler: callable, debouncer):
    """Stop playback when blockers activate; resume when they clear."""
    if hass.state is not CoreState.running:
        _LOGGER.debug(
            "Blockers watcher: HA not yet running (state=%s); ignoring event",
            hass.state,
        )
        return

    new_state = event.data.get("new_state")
    old_state = event.data.get("old_state")

    if not new_state or not old_state:
        return

    if old_state.state in ("unknown", "unavailable") or new_state.state in ("unknown", "unavailable"):
        _LOGGER.debug(
            "Blockers watcher: ignoring transition %s -> %s (initial-populate, not a real change)",
            old_state.state,
            new_state.state,
        )
        return

    if old_state.state == "on" and new_state.state == "off":
        _LOGGER.debug("Blockers activated, triggering stop via watcher")
        call = _WatcherServiceCall()
        hass.loop.create_task(stop_handler(call))
    elif old_state.state == "off" and new_state.state == "on":
        _LOGGER.debug("Blockers cleared, triggering play via watcher")
        call = _WatcherServiceCall()
        hass.loop.create_task(play_handler(call))

@callback
def _handle_playlist_change(hass: HomeAssistant, event, pause_handler: callable, play_handler: callable, debouncer):
    """Fade-down then start the new playlist when the active playlist select changes."""
    if hass.state is not CoreState.running:
        _LOGGER.debug(
            "Playlist watcher: HA not yet running (state=%s); ignoring event",
            hass.state,
        )
        return

    new_state = event.data.get("new_state")
    old_state = event.data.get("old_state")

    if not new_state:
        return

    if old_state and old_state.state in ("unknown", "unavailable"):
        _LOGGER.debug(
            "Playlist watcher: ignoring transition out of %s — initial state populate, not a user-driven change",
            old_state.state,
        )
        return

    if old_state and new_state.state == old_state.state:
        return

    if new_state.state not in ("unknown", "unavailable"):
        _LOGGER.debug(f"Playlist changed to {new_state.state}, triggering switchover via watcher")
        call = _WatcherServiceCall()
        
        async def _switchover():
            pause_debouncer_state_before = dict(debouncer.last_trigger_time)
            await pause_handler(call)
            pause_executed = debouncer.last_trigger_time.get("pause_for_switchover", 0) > pause_debouncer_state_before.get("pause_for_switchover", 0)
            
            if pause_executed:
                await play_handler(call)
            else:
                _LOGGER.debug("Pause was debounced (automation likely already paused), skipping immediate play")
        
        hass.loop.create_task(_switchover())
