import re
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.template import Template

from .const import (
    CONF_PLAYLISTS, DEVICE_INFO,
    CONF_BLOCKERS, BLOCKER_NAME, BLOCKER_TYPE, BLOCKER_INVERT,
    BLOCKER_ENTITY_ID, BLOCKER_STATE, BLOCKER_TEMPLATE
)

SELECT_ENTITY_ID = "select.ambient_music_playlists"
MASTER_SWITCH_ENTITY_ID = "switch.ambient_music_master_enable"


def _slugify_playlist(playlist_name: str) -> str:
    slug = playlist_name.lower()
    slug = re.sub(r"\s+", "_", slug)
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug


def _get_playlist_names(entry: ConfigEntry) -> list[str]:
    raw = entry.options.get(CONF_PLAYLISTS, {})
    if not isinstance(raw, dict):
        return []
    return list(raw.keys())


def _to_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("1", "true", "on", "yes", "y", "enabled")


class PlaylistEnabledSensor(BinarySensorEntity, RestoreEntity):

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, playlist_name: str):
        self.hass = hass
        self._playlist_name = playlist_name
        self._attr_name = f"Ambient Music {playlist_name} Enabled"
        self._attr_unique_id = f"ambient_music_{_slugify_playlist(playlist_name)}_enabled"
        self._attr_is_on = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last = await self.async_get_last_state()
        if last and last.state in ("on", "off"):
            self._attr_is_on = (last.state == "on")

        async_track_state_change_event(self.hass, SELECT_ENTITY_ID, self._handle_select_change)

        self._evaluate_and_maybe_write()

    @callback
    def _handle_select_change(self, _event) -> None:
        self._evaluate_and_maybe_write()

    @callback
    def _evaluate_and_maybe_write(self) -> None:
        st = self.hass.states.get(SELECT_ENTITY_ID)
        new_on = bool(st and st.state == self._playlist_name)
        if new_on == self._attr_is_on:
            return
        self._attr_is_on = new_on
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return bool(self._attr_is_on)

    @property
    def device_info(self):
        return DEVICE_INFO


class BlockersClear(BinarySensorEntity, RestoreEntity):

    _attr_should_poll = False
    _attr_name = "Ambient Music Blockers Clear"
    _attr_unique_id = "ambient_music_blockers_clear"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._entry = entry
        self._blockers: list[dict] = []
        self._listened_entities: set[str] = set()
        self._unsubs: list = []
        self._interval_added = False
        self._attr_is_on = None
        self._attr_extra_state_attributes = None

    @property
    def device_info(self):
        return DEVICE_INFO

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last = await self.async_get_last_state()
        if last is not None:
            if last.state in ("on", "off"):
                self._attr_is_on = (last.state == "on")
            if last.attributes:
                self._attr_extra_state_attributes = dict(last.attributes)

        await self._refresh_blockers_and_listeners()
        self._evaluate_and_maybe_write()

    async def async_will_remove_from_hass(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        self._listened_entities.clear()
        await super().async_will_remove_from_hass()

    async def _refresh_blockers_and_listeners(self) -> None:
        blockers = self._entry.options.get(CONF_BLOCKERS, [])
        if not isinstance(blockers, list):
            blockers = []
        self._blockers = blockers

        new_entities: set[str] = set()
        for blk in blockers:
            if blk.get(BLOCKER_TYPE) == "state":
                ent = blk.get(BLOCKER_ENTITY_ID)
                if ent:
                    new_entities.add(str(ent))
        new_entities.add(MASTER_SWITCH_ENTITY_ID)

        if new_entities != self._listened_entities:
            for u in self._unsubs:
                u()
            self._unsubs.clear()
            self._listened_entities = set()

            for ent in new_entities:
                self._unsubs.append(
                    async_track_state_change_event(self.hass, ent, self._handle_change)
                )
            self._listened_entities = new_entities

            if not self._interval_added:
                self._unsubs.append(
                    async_track_time_interval(self.hass, self._handle_interval, timedelta(seconds=10))
                )
                self._interval_added = True

    @callback
    def _handle_change(self, _event) -> None:
        self.hass.async_create_task(self._async_refresh_and_eval())

    @callback
    def _handle_interval(self, _now) -> None:
        self.hass.async_create_task(self._async_refresh_and_eval())

    async def _async_refresh_and_eval(self) -> None:
        await self._refresh_blockers_and_listeners()
        self._evaluate_and_maybe_write()

    def _eval_blocker(self, blk: dict) -> bool:
        try:
            if blk.get(BLOCKER_TYPE) == "state":
                ent = blk.get(BLOCKER_ENTITY_ID)
                target = blk.get(BLOCKER_STATE, "")
                st = self.hass.states.get(ent)
                cond_ok = (st is not None) and (str(st.state) == str(target))
            else:
                tpl_text = blk.get(BLOCKER_TEMPLATE, "")
                tpl = Template(tpl_text, self.hass)
                res = tpl.async_render(variables={})
                cond_ok = _to_bool(res)

            invert = bool(blk.get(BLOCKER_INVERT, False))
            passed = cond_ok if invert else not cond_ok
            return passed
        except Exception:
            return False

    @callback
    def _evaluate_and_maybe_write(self) -> None:
        results = []

        ms = self.hass.states.get(MASTER_SWITCH_ENTITY_ID)
        master_ok = True if ms is None else (ms.state == "on")
        results.append({
            "name": "Master Enable",
            "type": "switch",
            "invert": False,
            "passed": master_ok,
        })

        all_ok = master_ok

        for blk in self._blockers:
            passed = self._eval_blocker(blk)
            results.append({
                "name": blk.get(BLOCKER_NAME, ""),
                "type": blk.get(BLOCKER_TYPE, ""),
                "invert": bool(blk.get(BLOCKER_INVERT, False)),
                "passed": passed,
            })
            all_ok = all_ok and passed

        new_attrs = {
            "blockers": results,
            "blocker_count": len(results),
            "failing_blockers": [r["name"] for r in results if not r["passed"]],
            "all_passed": all_ok,
        }

        state_changed = (all_ok != self._attr_is_on)
        attrs_changed = (new_attrs != self._attr_extra_state_attributes)

        if not state_changed and not attrs_changed:
            return

        self._attr_is_on = all_ok
        self._attr_extra_state_attributes = new_attrs
        self.async_write_ha_state()

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    playlists = _get_playlist_names(entry)

    ent_reg = er.async_get(hass)
    valid_slugs = {_slugify_playlist(p) for p in playlists}
    for entity_id, entity_entry in list(ent_reg.entities.items()):
        if (
            entity_entry.domain == "binary_sensor"
            and entity_entry.unique_id.startswith("ambient_music_")
            and entity_entry.unique_id.endswith("_enabled")
        ):
            slug = entity_entry.unique_id[len("ambient_music_"):-len("_enabled")]
            if slug not in valid_slugs:
                ent_reg.async_remove(entity_id)

    sensors = [PlaylistEnabledSensor(hass, name) for name in playlists]
    sensors.append(BlockersClear(hass, entry))
    async_add_entities(sensors, True)
