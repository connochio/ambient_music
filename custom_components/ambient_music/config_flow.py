import re
import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from copy import deepcopy
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    BooleanSelector,
    BooleanSelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_MEDIA_PLAYERS,
    CONF_PLAYLISTS,
    CONF_BLOCKERS,
    BLOCKER_ID,
    BLOCKER_NAME,
    BLOCKER_TYPE,
    BLOCKER_INVERT,
    BLOCKER_ENTITY_ID,
    BLOCKER_STATE,
    BLOCKER_TEMPLATE,
)

try:
    from .const import CONF_PLAYLIST_ID as CONF_ID
except ImportError:
    from .const import CONF_SPOTIFY_ID as CONF_ID

_SPOTIFY_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")
_YTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{34}$")
_LOCAL_ID_RE = re.compile(r"[0-9]{1,3}$")
_TIDAL_ID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

def _extract_spotify_id(text: str) -> str:
    if not text:
        return ""
    s = text.strip()
    if _SPOTIFY_ID_RE.fullmatch(s):
        return s
    m = re.search(r"(?:spotify:playlist:|open\.spotify\.com/playlist/|spotify://playlist/)([A-Za-z0-9]{22})", s, flags=re.IGNORECASE,)
    return m.group(1) if m else ""

def _extract_ytm_id(text: str) -> str:
    if not text:
        return ""
    s = text.strip()
    m = re.search(r"(?:list=|youtube:playlist:|ytmusic://playlist/)([A-Za-z0-9_-]{34})", s, flags=re.IGNORECASE,)
    if m:
        s = m.group(1)
    return s if _YTUBE_ID_RE.fullmatch(s) else ""
    
def _extract_local_id(text: str) -> str:
    if not text:
        return ""
    s = text.strip()
    m = re.search(r"(?:media-source://mass/playlists/|library://playlist/)([0-9]{1,3})", s, flags=re.IGNORECASE,)
    if m:
        s = m.group(1)
    return s if _LOCAL_ID_RE.fullmatch(s) else ""

def _extract_tidal_id(text: str) -> str:
    if not text:
        return ""
    s = text.strip()
    if _TIDAL_ID_RE.fullmatch(s):
        return s
    m = re.search(r"(?:tidal://playlist/|(?:https?://)?(?:www\.)?tidal\.com/playlist/)([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", s, flags=re.IGNORECASE,)
    return m.group(1) if (m and _TIDAL_ID_RE.fullmatch(m.group(1))) else ""

def _parse_playlist_input(text: str) -> tuple[str, str] | None:
    if not text:
        return None
    s = text.strip()

    if "spotify" in s or "spotify://" in s:
        sid = _extract_spotify_id(s)
        return ("spotify", sid) if sid else None
    if "youtube" in s or "music.youtube.com" in s or "ytmusic://" in s or "list=" in s:
        yid = _extract_ytm_id(s)
        return ("youtube", yid) if yid else None
    if "library" in s or "media-source" in s:
        lid = _extract_local_id(s)
        return ("local", lid) if lid else None
    if "tidal" in s or "tidal://" in s:
        sid = _extract_tidal_id(s)
        return ("tidal", sid) if sid else None

    if _SPOTIFY_ID_RE.fullmatch(s):
        return ("spotify", s)
    if _YTUBE_ID_RE.fullmatch(s):
        return ("youtube", s)
    if _LOCAL_ID_RE.fullmatch(s):
        return ("local", s)
    if _TIDAL_ID_RE.fullmatch(s):
        return ("tidal", s)

    return None

def _get_players_and_map(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    opts = entry.options or {}
    players = list(opts.get(CONF_MEDIA_PLAYERS, []) or [])
    playlist_map = dict(opts.get(CONF_PLAYLISTS, {}) or {})
    playlist_map = {str(k): str(v) for k, v in playlist_map.items()}
    return players, playlist_map

def _get_blockers(entry: config_entries.ConfigEntry) -> list[dict]:
    ls = entry.options.get(CONF_BLOCKERS, [])
    return deepcopy(ls) if isinstance(ls, list) else []

def _add_schema(default_name: str = "", default_sid: str = "") -> vol.Schema:
    return vol.Schema({
        vol.Required("name", default=default_name): TextSelector(
            TextSelectorConfig(multiline=False)
        ),
        vol.Required(CONF_ID, default=default_sid): TextSelector(
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

def _readonly_name_and_id_schema(name: str, default_sid: str) -> vol.Schema:
    return vol.Schema({
        vol.Required("playlist_name", default=name): SelectSelector(
            SelectSelectorConfig(options=[name], multiple=False, custom_value=False)
        ),
        vol.Required(CONF_ID, default=default_sid): TextSelector(
            TextSelectorConfig(multiline=False)
        ),
    })

def _blocker_names(blockers: list[dict]) -> list[str]:
    return [b.get(BLOCKER_NAME, "") for b in blockers if b.get(BLOCKER_NAME)]

def _find_blocker(blockers: list[dict], name: str) -> dict | None:
    for b in blockers:
        if b.get(BLOCKER_NAME, "") == name:
            return b
    return None

def _blocker_type_schema(default_type: str | None = None) -> vol.Schema:
    return vol.Schema({
        vol.Required(BLOCKER_TYPE, default=default_type or "state"): SelectSelector(
            SelectSelectorConfig(
                options=["state", "template"],
                multiple=False,
                custom_value=False,
            )
        )
    })

def _add_blocker_state_schema(name: str = "", entity_id: str = "", state_val: str = "", invert: bool = False) -> vol.Schema:
    return vol.Schema({
        vol.Required(BLOCKER_NAME, default=name): TextSelector(TextSelectorConfig(multiline=False)),
        vol.Required(BLOCKER_ENTITY_ID, default=entity_id): EntitySelector(
            EntitySelectorConfig(multiple=False)
        ),
        vol.Required(BLOCKER_STATE, default=state_val): TextSelector(TextSelectorConfig(multiline=False)),
        vol.Required(BLOCKER_INVERT, default=invert): BooleanSelector(BooleanSelectorConfig()),
    })

def _add_blocker_template_schema(name: str = "", template_text: str = "", invert: bool = False) -> vol.Schema:
    return vol.Schema({
        vol.Required(BLOCKER_NAME, default=name): TextSelector(TextSelectorConfig(multiline=False)),
        vol.Required(BLOCKER_TEMPLATE, default=template_text): TextSelector(
            TextSelectorConfig(multiline=True)
        ),
        vol.Required(BLOCKER_INVERT, default=invert): BooleanSelector(BooleanSelectorConfig()),
    })

class AmbientMusicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Ambient Music", data={})

    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler()

class OptionsFlowHandler(config_entries.OptionsFlow):

    def __init__(self) -> None:
        self._edit_target = None
        self._pending_blocker_type = None
        self._edit_blocker_name = None

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "add_playlist": "Add Playlist",
                "manage_blockers": "Manage Blockers",
                "manage_playlists": "Manage Playlists",
                "media_players": "Media Players",
            },
        )

    async def async_step_media_players(self, user_input=None):
        current_players, playlist_map = _get_players_and_map(self.hass, self.config_entry)

        if user_input is not None:
            options = {
                CONF_MEDIA_PLAYERS: list(user_input[CONF_MEDIA_PLAYERS]),
                CONF_PLAYLISTS: dict(playlist_map),
                CONF_BLOCKERS: _get_blockers(self.config_entry),
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="media_players",
            data_schema=vol.Schema({
                vol.Required(CONF_MEDIA_PLAYERS, default=current_players): EntitySelector(
                    EntitySelectorConfig(domain="media_player", multiple=True)
                ),
            }),
        )

    async def async_step_add_playlist(self, user_input=None):
        players, playlist_map = _get_players_and_map(self.hass, self.config_entry)
        blockers = _get_blockers(self.config_entry)

        if user_input is not None:
            name = str(user_input.get("name", "")).strip()
            raw = str(user_input.get(CONF_ID, "")).strip()

            errors = {}
            if not name:
                errors["name"] = "required"
            else:
                existing_lower = {n.lower() for n in playlist_map}
                if name.lower() in existing_lower:
                    errors["name"] = "already_configured"
    
            parsed = _parse_playlist_input(raw)
            if not parsed or not parsed[1]:
                errors[CONF_ID] = "invalid_playlist_id"

            if errors:
                return self.async_show_form(
                    step_id="add_playlist",
                    data_schema=_add_schema(default_name=name, default_sid=raw),
                    errors=errors,
                )

            _, canonical_id = parsed
            new_map = dict(playlist_map)
            new_map[name] = canonical_id

            options = {
                CONF_MEDIA_PLAYERS: players,
                CONF_PLAYLISTS: new_map,
                CONF_BLOCKERS: blockers,
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
            raw = str(user_input.get(CONF_ID, "")).strip()
            sid = _extract_spotify_id(raw)

            errors = {}
            if not sid:
                errors[CONF_ID] = "invalid_playlist_id"

            if errors:
                return self.async_show_form(
                    step_id="edit_playlist",
                    data_schema=_readonly_name_and_id_schema(old_name, raw),
                    errors=errors,
                )

            new_map = dict(playlist_map)
            new_map[old_name] = sid
            options = {
                CONF_MEDIA_PLAYERS: list(players),
                CONF_PLAYLISTS: new_map,
                CONF_BLOCKERS: _get_blockers(self.config_entry),
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="edit_playlist",
            data_schema=_readonly_name_and_id_schema(old_name, old_id),
        )

    async def async_step_remove_playlists(self, user_input=None):
        players, playlist_map = _get_players_and_map(self.hass, self.config_entry)
        names = list(playlist_map.keys())

        if user_input is not None:
            to_remove = set(user_input.get(CONF_PLAYLISTS, []))
            new_map = {k: v for k, v in playlist_map.items() if k not in to_remove}

            options = {
                CONF_MEDIA_PLAYERS: list(players),
                CONF_PLAYLISTS: new_map,
                CONF_BLOCKERS: _get_blockers(self.config_entry),
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

    async def async_step_manage_blockers(self, user_input=None):
        blockers = _get_blockers(self.config_entry)
        names = _blocker_names(blockers)

        return self.async_show_menu(
            step_id="manage_blockers",
            menu_options={
                "add_blocker": "Add Blocker",
                "edit_blocker_choose": "Edit Blocker",
                "remove_blockers": "Remove Blockers",
            } if names else {
                "add_blocker": "Add Blocker",
            },
        )

    async def async_step_add_blocker(self, user_input=None):
        if user_input is not None:
            self._pending_blocker_type = user_input[BLOCKER_TYPE]
            return await self.async_step_add_blocker_details()
        return self.async_show_form(step_id="add_blocker", data_schema=_blocker_type_schema())

    async def async_step_add_blocker_details(self, user_input=None):
        blockers = _get_blockers(self.config_entry)
        btype = self._pending_blocker_type or "state"

        if user_input is not None:
            errors = {}

            if btype == "state":
                name = str(user_input[BLOCKER_NAME]).strip()
                entity_id = str(user_input[BLOCKER_ENTITY_ID]).strip()
                state_val = str(user_input[BLOCKER_STATE]).strip()
                invert = bool(user_input[BLOCKER_INVERT])

                if not name:
                    errors[BLOCKER_NAME] = "required"
                elif name.lower() in {n.lower() for n in _blocker_names(blockers)}:
                    errors[BLOCKER_NAME] = "already_configured"
                if not entity_id:
                    errors[BLOCKER_ENTITY_ID] = "required"
                if not state_val:
                    errors[BLOCKER_STATE] = "required"

                if errors:
                    return self.async_show_form(
                        step_id="add_blocker_details",
                        data_schema=_add_blocker_state_schema(name, entity_id, state_val, invert),
                        errors=errors,
                    )

                new_blocker = {
                    BLOCKER_ID: str(uuid.uuid4()),
                    BLOCKER_NAME: name,
                    BLOCKER_TYPE: "state",
                    BLOCKER_ENTITY_ID: entity_id,
                    BLOCKER_STATE: state_val,
                    BLOCKER_INVERT: invert,
                }

            else:
                name = str(user_input[BLOCKER_NAME]).strip()
                template_text = str(user_input[BLOCKER_TEMPLATE]).strip()
                invert = bool(user_input[BLOCKER_INVERT])

                if not name:
                    errors[BLOCKER_NAME] = "required"
                elif name.lower() in {n.lower() for n in _blocker_names(blockers)}:
                    errors[BLOCKER_NAME] = "already_configured"
                if not template_text:
                    errors[BLOCKER_TEMPLATE] = "required"

                if errors:
                    return self.async_show_form(
                        step_id="add_blocker_details",
                        data_schema=_add_blocker_template_schema(name, template_text, invert),
                        errors=errors,
                    )

                new_blocker = {
                    BLOCKER_ID: str(uuid.uuid4()),
                    BLOCKER_NAME: name,
                    BLOCKER_TYPE: "template",
                    BLOCKER_TEMPLATE: template_text,
                    BLOCKER_INVERT: invert,
                }

            new_blockers = blockers + [new_blocker]
            players, playlist_map = _get_players_and_map(self.hass, self.config_entry)
            options = {
                CONF_MEDIA_PLAYERS: list(players),
                CONF_PLAYLISTS: dict(playlist_map),
                CONF_BLOCKERS: new_blockers,
            }
            return self.async_create_entry(title="", data=options)

        if btype == "state":
            return self.async_show_form(step_id="add_blocker_details", data_schema=_add_blocker_state_schema())
        return self.async_show_form(step_id="add_blocker_details", data_schema=_add_blocker_template_schema())

    async def async_step_edit_blocker_choose(self, user_input=None):
        blockers = _get_blockers(self.config_entry)
        names = _blocker_names(blockers)

        if not names:
            return self.async_show_form(
                step_id="edit_blocker_choose",
                data_schema=vol.Schema({}),
                errors={"base": "no_blockers"},
            )

        schema = vol.Schema({
            vol.Required("name"): SelectSelector(
                SelectSelectorConfig(options=names, multiple=False, custom_value=False)
            )
        })

        if user_input is not None:
            self._edit_blocker_name = user_input["name"]
            return await self.async_step_edit_blocker()

        return self.async_show_form(step_id="edit_blocker_choose", data_schema=schema)

    async def async_step_edit_blocker(self, user_input=None):
        players, playlist_map = _get_players_and_map(self.hass, self.config_entry)
        blockers = _get_blockers(self.config_entry)
        old_name = self._edit_blocker_name or ""
        blk = _find_blocker(blockers, old_name)

        if not blk:
            return self.async_abort(reason="unknown_blocker")

        btype = blk[BLOCKER_TYPE]

        if btype == "state":
            schema = _add_blocker_state_schema(
                name=blk.get(BLOCKER_NAME, ""),
                entity_id=blk.get(BLOCKER_ENTITY_ID, ""),
                state_val=blk.get(BLOCKER_STATE, ""),
                invert=bool(blk.get(BLOCKER_INVERT, False)),
            )
        else:
            schema = _add_blocker_template_schema(
                name=blk.get(BLOCKER_NAME, ""),
                template_text=blk.get(BLOCKER_TEMPLATE, ""),
                invert=bool(blk.get(BLOCKER_INVERT, False)),
            )

        if user_input is not None:
            errors = {}

            new_name = str(user_input[BLOCKER_NAME]).strip()
            if not new_name:
                errors[BLOCKER_NAME] = "required"
            elif new_name.lower() != blk.get(BLOCKER_NAME, "").lower() and new_name.lower() in {
                n.lower() for n in _blocker_names(blockers)
            }:
                errors[BLOCKER_NAME] = "already_configured"

            if btype == "state":
                entity_id = str(user_input[BLOCKER_ENTITY_ID]).strip()
                state_val = str(user_input[BLOCKER_STATE]).strip()
                invert = bool(user_input[BLOCKER_INVERT])
                if not entity_id:
                    errors[BLOCKER_ENTITY_ID] = "required"
                if not state_val:
                    errors[BLOCKER_STATE] = "required"
                if errors:
                    return self.async_show_form(step_id="edit_blocker", data_schema=schema, errors=errors)

                updated = dict(blk)
                updated.update({
                    BLOCKER_NAME: new_name,
                    BLOCKER_ENTITY_ID: entity_id,
                    BLOCKER_STATE: state_val,
                    BLOCKER_INVERT: invert,
                })

            else:
                template_text = str(user_input[BLOCKER_TEMPLATE]).strip()
                invert = bool(user_input[BLOCKER_INVERT])
                if not template_text:
                    errors[BLOCKER_TEMPLATE] = "required"
                if errors:
                    return self.async_show_form(step_id="edit_blocker", data_schema=schema, errors=errors)

                updated = dict(blk)
                updated.update({
                    BLOCKER_NAME: new_name,
                    BLOCKER_TEMPLATE: template_text,
                    BLOCKER_INVERT: invert,
                })

            idx = next((i for i, b in enumerate(blockers) if b.get(BLOCKER_NAME, "") == old_name), -1)
            if idx < 0:
                return self.async_abort(reason="unknown_blocker")

            new_blockers = blockers.copy()
            new_blockers[idx] = updated

            options = {
                CONF_MEDIA_PLAYERS: list(players),
                CONF_PLAYLISTS: dict(playlist_map),
                CONF_BLOCKERS: new_blockers,
            }
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(step_id="edit_blocker", data_schema=schema)

    async def async_step_remove_blockers(self, user_input=None):
        players, playlist_map = _get_players_and_map(self.hass, self.config_entry)
        blockers = _get_blockers(self.config_entry)
        names = _blocker_names(blockers)

        if not names:
            return self.async_show_form(
                step_id="remove_blockers",
                data_schema=vol.Schema({}),
                errors={"base": "no_blockers"},
            )

        if user_input is not None:
            to_remove = set(user_input.get("names", []))
            new_blockers = [b for b in blockers if b.get(BLOCKER_NAME, "") not in to_remove]

            options = {
                CONF_MEDIA_PLAYERS: list(players),
                CONF_PLAYLISTS: dict(playlist_map),
                CONF_BLOCKERS: new_blockers,
            }
            return self.async_create_entry(title="", data=options)

        schema = vol.Schema({
            vol.Required("names", default=[]): SelectSelector(
                SelectSelectorConfig(options=names, multiple=True, custom_value=False)
            )
        })
        return self.async_show_form(step_id="remove_blockers", data_schema=schema)
