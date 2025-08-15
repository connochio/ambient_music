[![Static Badge](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://github.com/hacs/integration) 

# Ambient Music

A Home Assistant integration for playing ambient music on supported players via Music Assistant.

> [!IMPORTANT]
> This integration is currently in the alpha stage, awaiting further script and automation implementation.  
> It is not yet a fully automated ambient music integration.

> [!NOTE]
> This integration is intended to be used alongside Music Assistant and Spotify.  
> Future updates may include further providers and players, but this is not currently in the roadmap.

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=connochio&repository=ambient_music&category=integration)

Install this integration via HACS with the link above.

## Description

This integration will create user-configurable helpers to set various aspects of the ambient music system, including:

- The amount of time to fade music in.
- The amount of time to fade music out.
- The default volume for player entities.

<details>
  <summary>Planned future helpers, switches and/or user-configurable settings</summary>
  <br />
  
  - Blocker entities.
    - These entities will block or stop ambient music from playing based on an entity state or custom template.
  - Configurable sleep mode.
    - Sleep mode will play a user-selected playlist at night, based on user-set time of day binary sensors.
  - Configurable hours
    - Ambient music will play only during set hours, based on user-set time of day binary sensors.
</details>

## Setup

When adding this integration, you will be asked to specify a player or player group to play the ambient music from. 

In addition to this, you will asked to add the names of the playlists that will be available for selection within the integration
