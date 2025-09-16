[![Static Badge](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://github.com/hacs/integration)  

# Ambient Music

A Home Assistant integration for playing ambient music on supported players via Music Assistant.

> [!IMPORTANT]
> This integration is currently in the beta stage, awaiting feedback and improvements.
>   
> Bugs may be present and some functionality may be missing.  

> [!NOTE]
> This integration is intended to be used alongside Music Assistant and Spotify.
>   
> Future updates may include further providers and players, but this is not currently in the roadmap.

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=connochio&repository=ambient_music&category=Integration)

Install this integration via HACS with the link above.

## Description

This integration allows for users to create playlist selections that will play automatically on supported players via music assistant.  

Playlists will fade out and back in from each-other seamlessly when changed, and fade in and out when Ambient Music is turned on or off.  

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

## Setup and Documentation

To get this integration fully up and running, a small amount of setup is needed.  
Setup instructions and automation blueprints can be found within the documentation guthub page below:

[Setup and Documentation Information](https://github.com/connochio/ambient_music_documentation#readme)

## Credits and Thanks

Special thanks to Lauren Peploe for her design and creation of the Ambient Music logo
