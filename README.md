[![Static Badge](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://github.com/hacs/integration) 
![Dynamic JSON Badge](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.ambient_music.total&style=for-the-badge&label=Installs&color=brightgreen)
![GitHub Release](https://img.shields.io/github/v/release/connochio/ambient_music?style=for-the-badge&label=Current%20Release&color=41BDF5&cacheSeconds=15600)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/connochio/ambient_music?style=for-the-badge)

# Ambient Music

A Home Assistant integration for playing ambient music on supported players via Music Assistant.

> [!IMPORTANT]
> This integration is intended to be used alongside Music Assistant, and may not work correctly without it.

> [!TIP]
> Whilst this integration is quite new, only some providers are currently supported.  
> These are:
> - Spotify
> - Youtube Music
> - Local Files via Music Assistant
> - Plex Media Server (via MASS)
> - Tidal
> - Apple Music
>
> We are working on adding more with each release, but if you would like to request a specific provider please log a GitHub Issue and tag it as a feature request.

<br />

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=connochio&repository=ambient_music&category=Integration)

Install this integration via HACS with the link above.

<br />

## Description

### An integration that enables automatic playback of music via Home Assistant

The currently supported music providers are:
- Spotify
- Youtube Music
- Music Assistant Local Files
- Plex Media Server (via MASS)
- Tidal
- Apple Music

When configured, playlists will fade out and back in from each-other seamlessly when changed, and fade in and out when Ambient Music is turned on or off.  

User configurable options include:
- Default volume
- Music fade in time
- Music fade out time
- Time to wait between swapping playlists
- Playlist names and spotify IDs
- Blockers to prevent Ambient Music from running
  - available via either entity selection or template 


<details>
  <summary>Planned future helpers, switches and/or user-configurable settings</summary>
  <br />
  
  - Configurable sleep mode.
    - Sleep mode will play a user-selected playlist at night, based on user-set time of day binary sensors.  
      This will override any currently selected playlist.
  - Configurable hours
    - Ambient music will play only during set hours, based on user-set time of day binary sensors.
</details>

> [!IMPORTANT]
> This integration requires the use of automations to function.  
> These are available in the documentation below.

<br />

## Setup and Documentation

To get this integration fully up and running, a small amount of setup is needed.  
Setup instructions and automation blueprints can be found within the documentation guthub page below:

[Setup and Documentation Information](https://github.com/connochio/ambient_music_documentation#readme)

<br />

## Credits and Thanks

Special thanks to Lauren Peploe for her design and creation of the Ambient Music logo
