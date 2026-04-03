"""Ambient Music fade engine — async volume transitions with speaker availability awareness."""

import asyncio
import logging
from dataclasses import dataclass, field

from homeassistant.core import HomeAssistant

from .const import VOLUME_SET_CALL_TIMEOUT

_LOGGER = logging.getLogger(__name__)

_STEPS_PER_SECOND: int = 4
_STEP_INTERVAL: float = 0.25


@dataclass
class FadeResult:
    """Outcome metadata from a fade operation."""

    commanded_speakers: list[str] = field(default_factory=list)
    skipped_speakers: list[tuple[str, str]] = field(default_factory=list)
    call_timeouts: int = 0

    @property
    def all_unavailable(self) -> bool:
        """Return True when no speakers were successfully commanded."""
        return not self.commanded_speakers


async def fade_volume(
    hass: HomeAssistant,
    entity_ids: list[str],
    target_volume: float,
    duration: float,
    curve: str,
    volume_set_timeout: float = VOLUME_SET_CALL_TIMEOUT,
) -> FadeResult:
    """
    Fade volume for the given entity IDs to target_volume over duration seconds.

    Group members are resolved automatically — if an entity has a ``group_members``
    attribute, individual members are targeted instead.  Unavailable speakers are
    skipped (and re-evaluated each step) so a single offline speaker never blocks the fade.

    :param hass: Home Assistant instance.
    :param entity_ids: Media-player entity IDs (may include groups).
    :param target_volume: Desired end volume (0.0–1.0).
    :param duration: Fade duration in seconds; 0 or negative means jump immediately.
    :param curve: Easing curve — "logarithmic", "bezier", or "linear".
    :param volume_set_timeout: Per-call timeout for each volume_set service call.
    :return: FadeResult with details of commanded/skipped speakers and timeouts.
    """
    commanded: set[str] = set()
    skipped_by_entity: dict[str, str] = {}
    warned_skips: set[tuple[str, str]] = set()
    call_timeouts: int = 0

    def _record_skips(skipped: list[tuple[str, str]]) -> None:
        for entity_id, reason in skipped:
            skipped_by_entity[entity_id] = reason
            key = (entity_id, reason)
            if key in warned_skips:
                continue
            warned_skips.add(key)
            _LOGGER.warning(
                "Skipping unavailable speaker: entity_id=%s reason=%s",
                entity_id,
                reason,
            )

    if not entity_ids:
        return FadeResult()

    # Resolve group members and classify availability
    resolved = _resolve_group_members(hass, entity_ids)
    available, skipped = _classify_speakers(hass, resolved)
    _record_skips(skipped)

    if not available:
        _LOGGER.warning("All speakers unavailable; skipping fade")
        return FadeResult(skipped_speakers=list(skipped_by_entity.items()))

    # Duration ≤ 0: single immediate volume_set, no fade loop
    if duration <= 0:
        call_timeouts += await _guarded_volume_set(
            hass, available, target_volume, volume_set_timeout
        )
        commanded.update(available)
        return FadeResult(
            commanded_speakers=sorted(commanded),
            skipped_speakers=list(skipped_by_entity.items()),
            call_timeouts=call_timeouts,
        )

    start_volume = _get_current_volume(hass, available[0])
    total_steps = max(int(_STEPS_PER_SECOND * duration), 1)

    _LOGGER.debug(
        "Fade starting: entities=%s start_vol=%.3f target=%.3f duration=%.1fs steps=%d curve=%s",
        available,
        start_volume,
        target_volume,
        duration,
        total_steps,
        curve,
    )

    # Stepped fade loop — re-resolve and re-classify each step
    for idx in range(total_steps):
        step_resolved = _resolve_group_members(hass, entity_ids)
        step_available, step_skipped = _classify_speakers(hass, step_resolved)
        _record_skips(step_skipped)

        if not step_available:
            _LOGGER.warning("All speakers unavailable; stopping fade early")
            break

        t = (idx + 1) / total_steps
        factor = _compute_curve_factor(t, curve)
        vol_level = start_volume + factor * (target_volume - start_volume)

        call_timeouts += await _guarded_volume_set(
            hass, step_available, vol_level, volume_set_timeout
        )
        commanded.update(step_available)
        await asyncio.sleep(_STEP_INTERVAL)

    # Final pin to exact target (guards against floating-point drift)
    final_resolved = _resolve_group_members(hass, entity_ids)
    final_available, final_skipped = _classify_speakers(hass, final_resolved)
    _record_skips(final_skipped)

    if final_available:
        call_timeouts += await _guarded_volume_set(
            hass, final_available, target_volume, volume_set_timeout
        )
        commanded.update(final_available)
    else:
        _LOGGER.warning("All speakers unavailable; skipping final volume pin")

    _LOGGER.debug(
        "Fade complete: entities=%s final_vol=%.3f",
        sorted(commanded),
        target_volume,
    )

    return FadeResult(
        commanded_speakers=sorted(commanded),
        skipped_speakers=list(skipped_by_entity.items()),
        call_timeouts=call_timeouts,
    )


async def volume_set(
    hass: HomeAssistant,
    entity_ids: list[str],
    volume_level: float,
    volume_set_timeout: float = VOLUME_SET_CALL_TIMEOUT,
) -> FadeResult:
    """
    Availability-aware single volume_set — resolves groups, skips unavailable speakers.

    Drop-in replacement for the old _volume_set helper, but returns a FadeResult
    so the caller can inspect what happened.

    :param hass: Home Assistant instance.
    :param entity_ids: Media-player entity IDs (may include groups).
    :param volume_level: Target volume (0.0–1.0).
    :param volume_set_timeout: Per-call timeout for the volume_set service call.
    """
    if not entity_ids:
        return FadeResult()

    resolved = _resolve_group_members(hass, entity_ids)
    available, skipped = _classify_speakers(hass, resolved)

    if skipped:
        for entity_id, reason in skipped:
            _LOGGER.warning(
                "Skipping unavailable speaker: entity_id=%s reason=%s",
                entity_id,
                reason,
            )

    if not available:
        _LOGGER.warning("All speakers unavailable; skipping volume_set")
        return FadeResult(skipped_speakers=skipped)

    timeouts = await _guarded_volume_set(hass, available, volume_level, volume_set_timeout)
    return FadeResult(
        commanded_speakers=sorted(available),
        skipped_speakers=skipped,
        call_timeouts=timeouts,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_group_members(hass: HomeAssistant, entity_ids: list[str]) -> list[str]:
    """Expand grouped media players into their individual members for per-speaker volume control."""
    resolved: list[str] = []
    for eid in entity_ids:
        state = hass.states.get(eid)
        members = state and state.attributes.get("group_members")
        if members and isinstance(members, list):
            resolved.extend(m for m in members if isinstance(m, str))
        else:
            resolved.append(eid)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for eid in resolved:
        if eid not in seen:
            seen.add(eid)
            unique.append(eid)
    return unique


def _classify_speakers(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Split speakers into commandable and skipped groups with skip reasons."""
    available: list[str] = []
    skipped: list[tuple[str, str]] = []
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None:
            skipped.append((entity_id, "missing_state"))
            continue
        if state.state == "unavailable":
            skipped.append((entity_id, "state_unavailable"))
            continue
        if state.state == "unknown":
            skipped.append((entity_id, "state_unknown"))
            continue
        available.append(entity_id)
    return available, skipped


async def _guarded_volume_set(
    hass: HomeAssistant,
    entity_ids: list[str],
    volume_level: float,
    call_timeout: float,
) -> int:
    """
    Call media_player.volume_set with a timeout guard.

    :param hass: Home Assistant instance.
    :param entity_ids: Already-resolved, already-classified available entity IDs.
    :param volume_level: Target volume (0.0–1.0).
    :param call_timeout: Maximum seconds to wait for the service call.
    :return: 1 if the call timed out, 0 otherwise.
    """
    try:
        await asyncio.wait_for(
            hass.services.async_call(
                "media_player",
                "volume_set",
                {"entity_id": entity_ids, "volume_level": float(volume_level)},
                blocking=True,
            ),
            timeout=call_timeout,
        )
        return 0
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "volume_set call timed out: entities=%s timeout=%.1fs",
            entity_ids,
            call_timeout,
        )
        return 1


def _get_current_volume(hass: HomeAssistant, entity_id: str) -> float:
    """Return current volume_level from HA state, defaulting to 0.0 if unavailable."""
    state = hass.states.get(entity_id)
    if state is None:
        return 0.0
    try:
        return float(state.attributes.get("volume_level", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _compute_curve_factor(t: float, curve: str) -> float:
    """Return interpolation factor for position t in [0.0, 1.0] using the named curve."""
    if curve == "logarithmic":
        return t / (1 + (1 - t))
    if curve == "bezier":
        return t * t * (3 - 2 * t)
    return t
