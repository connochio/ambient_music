import asyncio
from typing import Iterable
import time

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.const import ATTR_ENTITY_ID
from async_timeout import timeout
import logging
_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN, CONF_MEDIA_PLAYERS
from .watchers import async_setup_watchers

PLATFORMS = [
    "number", 
    "select", 
    "binary_sensor",
    "switch"
]

class _ServiceDebouncer:
    def __init__(self, cooldown_seconds: float = 2.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_trigger_time = {}
    
    def should_execute(self, service_name: str) -> bool:
        current_time = time.time()
        last_time = self.last_trigger_time.get(service_name, 0)
        
        if current_time - last_time >= self.cooldown_seconds:
            self.last_trigger_time[service_name] = current_time
            return True
        
        _LOGGER.debug(f"Service '{service_name}' debounced, called too recently")
        return False

class _OperationTaskManager:
    
    def __init__(self):
        self.active_tasks: dict[str, asyncio.Task] = {}
    
    def cancel_for_targets(self, target_ids: list[str]) -> None:
        for entity_id in target_ids:
            if entity_id in self.active_tasks:
                task = self.active_tasks[entity_id]
                if not task.done():
                    task.cancel()
                del self.active_tasks[entity_id]
    
    async def run_operation(self, target_ids: list[str], coro, *, description: str, timeout_seconds: float) -> None:
        self.cancel_for_targets(target_ids)
        
        async def _wrapped_operation():
            try:
                async with timeout(timeout_seconds):
                    await coro
            except asyncio.CancelledError:
                _LOGGER.debug(f"Operation cancelled: {description}")
                raise
            except asyncio.TimeoutError:
                _LOGGER.warning(
                    "Timeout (%.1fs) while executing '%s' in ambient_music",
                    timeout_seconds,
                    description,
                )
            except Exception:
                _LOGGER.exception(
                    "Unexpected error while executing '%s' in ambient_music", description
                )
            finally:
                for entity_id in target_ids:
                    if entity_id in self.active_tasks and self.active_tasks[entity_id].done():
                        del self.active_tasks[entity_id]
        
        task = asyncio.create_task(_wrapped_operation())
        for entity_id in target_ids:
            self.active_tasks[entity_id] = task
        
        try:
            await task
        except asyncio.CancelledError:
            pass

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    service_debouncer = _ServiceDebouncer()
    task_manager = _OperationTaskManager()
    
    async def _options_updated(hass: HomeAssistant, updated_entry: ConfigEntry):
        await hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_options_updated))

    async def _cleanup_orphan_entity(_now=None):
            ent_reg = er.async_get(hass)
            old_entity_id = "number.ambient_music_previous_volume"

            if ent_reg.async_get(old_entity_id):
                _LOGGER.warning("Removing orphaned entity registry entry: %s", old_entity_id)
                ent_reg.async_remove(old_entity_id)

    hass.bus.async_listen_once("homeassistant_started", _cleanup_orphan_entity)

    def _configured_players() -> list[str]:
        opts = entry.options or {}
        players = opts.get(CONF_MEDIA_PLAYERS, []) or []
        return list(players)

    async def _resolve_targets(call: ServiceCall) -> list[str]:
        try:
            ids_from_target = await async_extract_entity_ids(call)
        except Exception:
            ids_from_target = set()
        ids = list(ids_from_target)

        data_ids = call.data.get("entity_id")
        if data_ids:
            if isinstance(data_ids, str):
                ids.append(data_ids)
            elif isinstance(data_ids, (list, tuple)):
                ids.extend(x for x in data_ids if isinstance(x, str))

        ids = [i for i in ids if isinstance(i, str) and i.startswith("media_player.")]
        ids = sorted(set(ids))

        if not ids:
            fallback = _configured_players()
            if not fallback:
                _LOGGER.warning(
                    "Ambient Music service called without any target, and/or no media players are configured in options"
                )
            return fallback
        return ids

    def _get_state_float(entity_id: str, default: float) -> float:
        st = hass.states.get(entity_id)
        try:
            return float(st.state)
        except Exception:
            return default

    def _get_state_attr_float(entity_id: str, attr: str, default: float) -> float:
        st = hass.states.get(entity_id)
        try:
            return float(st.attributes.get(attr, default))
        except Exception:
            return default

    async def _volume_set(entity_ids: Iterable[str], vol_level: float):
        if not entity_ids:
            return
        await hass.services.async_call(
            "media_player",
            "volume_set",
            {"entity_id": list(entity_ids), "volume_level": float(vol_level)},
            blocking=True,
        )

    async def _pause(entity_ids: Iterable[str]):
        if not entity_ids:
            _LOGGER.warning(
                "Ambient Music service called without any target, and/or no media players are configured in options"
            )
            return
        await hass.services.async_call(
            "media_player",
            "media_pause",
            {"entity_id": list(entity_ids)},
            blocking=True,
        )

    async def _play_playlist(entity_ids: Iterable[str], uri: str, radio_mode: bool = False):
        if not entity_ids or not uri:
            _LOGGER.warning(
                "Ambient Music service called without any target, no media players are configured in options, or a playlist uri was not given"
            )
            return
        if hass.services.has_service("music_assistant", "play_media"):
            await hass.services.async_call(
                "music_assistant",
                "play_media",
                {
                    "entity_id": list(entity_ids),
                    "media_type": "playlist",
                    "enqueue": "replace",
                    "media_id": uri,
                    "radio_mode": radio_mode,
                },
                blocking=True,
            )
            return
        if hass.services.has_service("mass", "play_media"):
            await hass.services.async_call(
                "mass",
                "play_media",
                {
                    "entity_id": list(entity_ids),
                    "media_type": "playlist",
                    "enqueue": "replace",
                    "media_id": uri,
                    "radio_mode": radio_mode,
                },
                blocking=True,
            )
            return
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": list(entity_ids),
                "media_content_id": uri,
                "media_content_type": "playlist",
            },
            blocking=True,
        )

    async def _fade_volume(entity_ids: list[str], target: float, duration: float, curve: str):
        if not entity_ids or duration <= 0:
            await _volume_set(entity_ids, target)
            return

        steps_per_second = 4
        total_steps = max(int(steps_per_second * duration), 1)
        start_volume = _get_state_attr_float(entity_ids[0], "volume_level", 0.0)
        start_diff = (target - start_volume)

        for idx in range(total_steps):
            t = (idx + 1) / total_steps
            if curve == "logarithmic":
                factor = (t / (1 + (1 - t)))
            elif curve == "bezier":
                factor = (t * t * (3 - 2 * t))
            else:
                factor = t
            vol_level = float(start_volume + factor * start_diff)
            await _volume_set(entity_ids, vol_level)
            await asyncio.sleep(0.25)

        await _volume_set(entity_ids, target)

    def _blockers_clear() -> bool:
        st = hass.states.get("binary_sensor.ambient_music_blockers_clear")
        return bool(st and st.state == "on")

    fade_schema = vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Required("target_volume"): vol.Coerce(float),
            vol.Required("duration"): vol.Coerce(float),
            vol.Optional("curve", default="logarithmic"): vol.In(["logarithmic", "bezier", "linear"]),
        }
    )

    async def _set_repeat(entity_ids: Iterable[str], mode: str):
        if not entity_ids:
            _LOGGER.warning(
                "Ambient Music service called without any target, and/or no media players are configured in options"
            )
            return
        if hass.services.has_service("media_player", "repeat_set"):
            try:
                await hass.services.async_call(
                    "media_player",
                    "repeat_set",
                    {"entity_id": list(entity_ids), "repeat": str(mode)},
                    blocking=True,
                )
            except Exception as err:
                _LOGGER.debug("repeat_set failed for %s: %s", entity_ids, err)
        else:
            _LOGGER.debug("media_player.repeat_set service not available; skipping")

    async def _set_shuffle(entity_ids: Iterable[str], shuffle: bool = True):
        if not entity_ids:
            _LOGGER.warning(
                "Ambient Music service called without any target, and/or no media players are configured in options"
            )
            return
        try:
            await hass.services.async_call(
                "media_player",
                "shuffle_set",
                {"entity_id": list(entity_ids), "shuffle": bool(shuffle)},
                blocking=True,
            )
        except Exception as err:
            _LOGGER.debug("shuffle_set failed for %s: %s", entity_ids, err)

    async def svc_fade_volume(call: ServiceCall):
        targets = await _resolve_targets(call)
        target_volume = float(call.data["target_volume"])
        duration = float(call.data["duration"])
        curve = call.data.get("curve", "logarithmic")

        fade_timeout = duration + 10.0
        
        async def _fade() -> None:
            await _fade_volume(targets, target_volume, duration, curve)

        await task_manager.run_operation(
            targets,
            _fade(),
            description=(
                f"svc_fade_volume to {target_volume} over {duration}s for {targets}"
            ),
            timeout_seconds=fade_timeout
        )

    hass.services.async_register(DOMAIN, "fade_volume", svc_fade_volume, schema=fade_schema)

    pause_schema = vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional("blockers_cleared", default=True): cv.boolean,
        }
    )

    async def svc_pause_for_switchover(call: ServiceCall):
        if not service_debouncer.should_execute("pause_for_switchover"):
            return
        if call.data.get("blockers_cleared", True) and not _blockers_clear():
            return
        targets = await _resolve_targets(call)
        fade_down = _get_state_float("number.ambient_music_volume_fade_down_seconds", 5.0)

        switchover_timeout = fade_down + 10.0

        async def _switchover() ->None:
            await _fade_volume(targets, 0.0, fade_down, "logarithmic")
            await _volume_set(targets, 0.0)
            await _pause(targets)

        await task_manager.run_operation(
            targets,
            _switchover(),
            description=(
                f"svc_pause_for_switchover playlist to volume 0 over {fade_down}s for {targets}"
            ),
            timeout_seconds=switchover_timeout
        )

    hass.services.async_register(DOMAIN, "pause_for_switchover", svc_pause_for_switchover, schema=pause_schema)

    play_schema = vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional("blockers_cleared", default=True): cv.boolean,
            vol.Optional("fade_up_duration"): vol.Coerce(float),
            vol.Optional("target_volume"): vol.Coerce(float),
            vol.Optional("curve", default="logarithmic"): vol.In(["logarithmic", "bezier", "linear"]),
        }
    )

    async def svc_play_current_playlist(call: ServiceCall):
        if not service_debouncer.should_execute("play_current_playlist"):
            return
        if call.data.get("blockers_cleared", True) and not _blockers_clear():
            return
        targets = await _resolve_targets(call)
        if not targets:
            _LOGGER.warning(
                "Ambient Music service called without any target, and/or no media players are configured in options"
            )
            return

        sel = hass.states.get("select.ambient_music_playlists")
        uri = sel and sel.attributes.get("current_playlist_uri")
        radio_mode = sel and sel.attributes.get("current_playlist_radio_mode", False)
        if not uri:
            _LOGGER.warning(
                "Ambient Music service called without any playlist ID"
            )
            return

        target_vol = call.data.get("target_volume")
        if target_vol is None:
            target_vol = _get_state_float("number.ambient_music_default_volume", 0.35)

        fade_up = call.data.get("fade_up_duration")
        if fade_up is None:
            fade_up = _get_state_float("number.ambient_music_volume_fade_up_seconds", 5.0)

        curve = call.data.get("curve", "logarithmic")

        play_timeout = fade_up + 20.0

        async def _start_playing() -> None:
            await _volume_set(targets, 0.0)
            await _play_playlist(targets, uri, radio_mode=bool(radio_mode))
            await _set_repeat(targets, "all")
            await _set_shuffle(targets, True)
            await _fade_volume(targets, float(target_vol), float(fade_up), curve)

        await task_manager.run_operation(
            targets,
            _start_playing(),
            description=(
                f"svc_play_current_playlist (uri={uri}) to volume {target_vol} over {fade_up}s for {targets}"
            ),
            timeout_seconds=play_timeout
        )

    hass.services.async_register(DOMAIN, "play_current_playlist", svc_play_current_playlist, schema=play_schema)

    stop_schema = vol.Schema(
        {
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        }
    )

    async def svc_stop_playing(call: ServiceCall):
        if not service_debouncer.should_execute("stop_playing"):
            return
        targets = await _resolve_targets(call)
        if not targets:
            _LOGGER.warning(
                "Ambient Music service called without any target, and/or no media players are configured in options"
            )
            return
        fade_down = _get_state_float("number.ambient_music_volume_fade_down_seconds", 5.0)

        stop_timeout = fade_down + 10.0

        async def _stop() -> None:
            await _fade_volume(targets, 0.0, fade_down, "logarithmic")
            await _pause(targets)

        await task_manager.run_operation(
            targets,
            _stop(),
            description=(
                f"svc_stop_playing playlist to volume 0 over {fade_down}s for {targets}"
            ),
            timeout_seconds=stop_timeout
        )

    hass.services.async_register(DOMAIN, "stop_playing", svc_stop_playing, schema=stop_schema)

    cleanup_watchers = await async_setup_watchers(
        hass,
        entry.entry_id,
        svc_play_current_playlist,
        svc_pause_for_switchover,
        svc_stop_playing,
        service_debouncer
    )
    entry.async_on_unload(cleanup_watchers)

    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "fade_volume"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "pause_for_switchover"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "play_current_playlist"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "stop_playing"))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
