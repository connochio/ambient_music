import asyncio
from typing import Iterable

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_entity_ids
import logging
_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN, CONF_MEDIA_PLAYERS

PLATFORMS = [
    "number", 
    "select", 
    "binary_sensor",
    "switch"
]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    async def _options_updated(hass: HomeAssistant, updated_entry: ConfigEntry):
        await hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_options_updated))

    def _configured_players() -> list[str]:
        opts = entry.options or {}
        players = opts.get(CONF_MEDIA_PLAYERS, []) or []
        return list(players)

    async def _resolve_targets(call: ServiceCall) -> list[str]:
        try:
            ids_from_target = await async_extract_entity_ids(hass, call)
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
                    "Ambient Music service call without targets and no speakers configured in options"
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
            return
        await hass.services.async_call(
            "media_player",
            "media_pause",
            {"entity_id": list(entity_ids)},
            blocking=True,
        )

    async def _play_playlist(entity_ids: Iterable[str], uri: str):
        if not entity_ids or not uri:
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
            vol.Required("target_volume"): vol.Coerce(float),
            vol.Required("duration"): vol.Coerce(float),
            vol.Optional("curve", default="logarithmic"): vol.In(["logarithmic", "bezier", "linear"]),
        }
    )

    async def svc_fade_volume(call: ServiceCall):
        targets = await _resolve_targets(call)
        target_volume = float(call.data["target_volume"])
        duration = float(call.data["duration"])
        curve = call.data.get("curve", "logarithmic")
        await _fade_volume(targets, target_volume, duration, curve)

    hass.services.async_register(DOMAIN, "fade_volume", svc_fade_volume, schema=fade_schema)

    pause_schema = vol.Schema({vol.Optional("blockers_cleared", default=True): cv.boolean})

    async def svc_pause_for_switchover(call: ServiceCall):
        if call.data.get("blockers_cleared", True) and not _blockers_clear():
            return
        targets = await _resolve_targets(call)
        fade_down = _get_state_float("number.ambient_music_volume_fade_down_seconds", 5.0)
        await _fade_volume(targets, 0.0, fade_down, "logarithmic")
        await _volume_set(targets, 0.0)
        await _pause(targets)

    hass.services.async_register(DOMAIN, "pause_for_switchover", svc_pause_for_switchover, schema=pause_schema)

    play_schema = vol.Schema(
        {
            vol.Optional("blockers_cleared", default=True): cv.boolean,
            vol.Optional("fade_up_duration"): vol.Coerce(float),
            vol.Optional("target_volume"): vol.Coerce(float),
            vol.Optional("curve", default="logarithmic"): vol.In(["logarithmic", "bezier", "linear"]),
        }
    )

    async def svc_play_current_playlist(call: ServiceCall):
        if call.data.get("blockers_cleared", True) and not _blockers_clear():
            return
        targets = await _resolve_targets(call)
        if not targets:
            return

        sel = hass.states.get("select.ambient_music_playlists")
        uri = sel and sel.attributes.get("current_playlist_uri")
        if not uri:
            return

        await _volume_set(targets, 0.0)

        await _play_playlist(targets, uri)

        target_vol = call.data.get("target_volume")
        if target_vol is None:
            target_vol = _get_state_float("number.ambient_music_default_volume", 0.35)

        fade_up = call.data.get("fade_up_duration")
        if fade_up is None:
            fade_up = _get_state_float("number.ambient_music_volume_fade_up_seconds", 5.0)

        curve = call.data.get("curve", "logarithmic")

        await _fade_volume(targets, float(target_vol), float(fade_up), curve)

    hass.services.async_register(DOMAIN, "play_current_playlist", svc_play_current_playlist, schema=play_schema)

    stop_schema = vol.Schema({})

    async def svc_stop_playing(call: ServiceCall):
        targets = await _resolve_targets(call)
        if not targets:
            return
        fade_down = _get_state_float("number.ambient_music_volume_fade_down_seconds", 5.0)
        await _fade_volume(targets, 0.0, fade_down, "logarithmic")
        await _pause(targets)

    hass.services.async_register(DOMAIN, "stop_playing", svc_stop_playing, schema=stop_schema)

    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "fade_volume"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "pause_for_switchover"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "play_current_playlist"))
    entry.async_on_unload(lambda: hass.services.async_remove(DOMAIN, "stop_playing"))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
