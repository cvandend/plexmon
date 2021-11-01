# Plex / NiceHash Monitor

PlexMon is a Python script that will monitor a Plex server, and when it detects a new 
transcoding stream, it will pause the configured NiceHash GPU for a given time
to let the transcoder start up more smoothly.

This script assumes that you are using the NiceHash QuickMiner on a Windows system.

Using a tweaked version of `nicehash.py` from:

https://github.com/nicehash/rest-clients-demo
    

## Required Python Modules

- Plex API Python module

    https://pypi.org/project/PlexAPI/

Install running: `pip install plexapi`


## Configuration

All the configuration items are stored in the `config.json` file.

- Find out the URL of your Plex server
- Read the following instructions on how to find your Plex server token:
    https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
- Create a NiceHash API key with both mining permissions selected:
    https://www.nicehash.com/my/settings/keys
- Look up the exact name of the miner you want to pause from your rig page:
    https://www.nicehash.com/my/mining/rigs/


## Tweaking

You can tweak the following settings at the top of `plexmon.py`:

- TIME_SLEEP : how often to check the Plex server for a new stream
- TIME_RIGPAUSE : how long to pause the NiceHash rig
- TIME_RIGCHECK : how often to check if NiceHash has crashed
