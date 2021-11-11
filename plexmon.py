#   plexmon.py
#   Monitor Plex to see if there is a new stream that is transcoding, and then pause selected NiceHash 
#   rig for X seconds to let the transcoder start up more smoothly.
#
#   v0.6    Christian Vandendorpe
#
#   Plex Python module: 
#       https://pypi.org/project/PlexAPI/
#   How to get Plex token:
#       https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
#   NiceHash Python module:
#       https://github.com/nicehash/rest-clients-demo
#

import nicehash
from plexapi.server import PlexServer
import time
import psutil
import json
import argparse
import datetime

TIME_SLEEP = 20                 # How often to check Plex in seconds
TIME_RIGPAUSE = 180             # How long to pause rig in seconds
TIME_RIGCHECK = 300             # How often to check if rig is hung in seconds

parser = argparse.ArgumentParser(
    description="Monitor Plex to see if there \
        is a new stream that is transcoding, and then pause selected NiceHash \
        rig for X seconds to let the transcoder start up more smoothly."
)
parser.add_argument(
    '--config', 
    type=str, 
    dest="config", 
    help='Config file', 
    default="config.json"
)
args = parser.parse_args()

# Open the config file
try:
    with open(args.config, 'r') as f:
        config = json.load(f)
except Exception as e:
    print("Error: Cannot open config file!",e)
    exit(0)

# Initialise variables
g_current_streams = []

g_rig_id = ''
g_rig_deviceid = 0
g_rig_deviceidx = 0
g_rig_ismining = False
g_rig_shouldmine = True

g_rig_time_pause_until = 0

# Connect to Plex
try:
    plex = PlexServer(config['plex']['api_url'], config['plex']['token'])
except Exception as e:
    print("Error: Cannot get handle to Plex server: ",e)
    exit(0)

if not plex:
    print("Error: Cannot get handle to Plex server")
    exit(0)

# Get handle to NiceHash private API
nh_api = nicehash.private_api(config['nicehash']['api_url'], 
                              config['nicehash']['organisation_id'], 
                              config['nicehash']['api_key'], 
                              config['nicehash']['api_secret'])

# Helper function to find rig ID
def nh_find_rig(api):
    global g_rig_id
    global g_rig_deviceid
    global g_rig_deviceidx
    global g_rig_ismining

    try:
        rigs = nh_api.get_mining_rigs()
    except Exception as e:
        print(e)
        return False

    if (rigs):
        g_rig_id = rigs['miningRigs'][0]['rigId']
        for rig in rigs['miningRigs'][0]['devices']:
            if (rig['name'] == config['nicehash']['card_name']):
                g_rig_deviceid = rig['id']
                g_rig_ismining = (rig['status']['enumName'] == 'MINING')
                return True
            g_rig_deviceidx += 1

    return False

# Helper function to find rig status
def nh_get_rig_status(api):
    global g_rig_ismining

    try:
        rig = nh_api.get_mining_rig(g_rig_id)
    except Exception as e:
        print(e)
        return False

    if (rig):
        g_rig_ismining = (rig['minerStatus'] == 'MINING')
        return True
    return False

# Get rig details
if not nh_find_rig(nh_api):
    print("Error: Cannot find NiceHash rig info")
    exit(0)

g_nh_checked_rig = time.time()

firstLoop = True

if not g_rig_ismining:
    print(f"[{str(datetime.datetime.now())}] > Ready, rig is currently not mining")
    g_rig_shouldmine = False
else:
    print(f"[{str(datetime.datetime.now())}] > Ready, starting monitoring!")

while True:
    try:
        sessions = plex.sessions()
    except Exception as e:
        print(f"[{str(datetime.datetime.now())}] Warning: could not query Plex: ",e.__class__,e)
        time.sleep(TIME_SLEEP)
        continue

    new_stream = False
    current_streams = []
    time_now = time.time()

    for session in plex.sessions():
        if (session.listType == 'video' and session.transcodeSessions):
            name = session.usernames[0] + '@' + session.guid
            if (name not in g_current_streams):
                new_stream = True
            current_streams.append(name)
    g_current_streams = current_streams

    if g_rig_shouldmine and new_stream:
        print(g_current_streams)
        if not firstLoop:
            g_rig_time_pause_until = time_now + TIME_RIGPAUSE
            print(f"[{str(datetime.datetime.now())}] > New stream detected, pausing rig until: " + 
                  time.asctime(time.localtime(g_rig_time_pause_until)))
    
    if (g_rig_time_pause_until > 0):
        if time_now < g_rig_time_pause_until:
            if g_rig_ismining:
                print(f"[{str(datetime.datetime.now())}] !> Stopping rig")
                try:
                    nh_api.set_mining_rig(g_rig_id, g_rig_deviceid, "STOP")
                except Exception as e:
                    print(f"[{str(datetime.datetime.now())}] > Error: Unable to stop rig")
                else:
                    g_rig_ismining = False
        else:
            if not g_rig_ismining:
                print(f"[{str(datetime.datetime.now())}] !> Starting rig again")
                try:
                    nh_api.set_mining_rig(g_rig_id, g_rig_deviceid, "START")
                except Exception as e:
                    print(f"[{str(datetime.datetime.now())}] > Error: Unable to start rig")
                    # Will try to start again on the next loop
                else:
                    g_rig_ismining = True
                    g_rig_time_pause_until = 0

    # Check if rig is ok. Sometimes NiceHash crashes :/
    # So kill it. It will be restarted by the NiceHash watcher
    if (g_nh_checked_rig + TIME_RIGCHECK < time_now):
        g_nh_checked_rig = time_now

        try:
            rigs = nh_api.get_mining_rigs()
        except Exception as e:
            print(f"[{str(datetime.datetime.now())}] > Error: Unable to query rig status")
        else:
            if 'UNKNOWN' in rigs['minerStatuses']:
                # Mining rig state is unknown, usually means crashed
                print(f"[{str(datetime.datetime.now())}] Error: NiceHash rig seems to be hung!")
                for proc in psutil.process_iter():
                    if proc.name() == config['nicehash']['process_name']:
                        # Kill process and wait a bit until it is restarted                        
                        proc.kill()
                        time.sleep(TIME_SLEEP)
                        # This will get the rig started in the next loop if it's stopped now
                        g_rig_time_pause_until = 1
                        # Query rig status again
                        nh_get_rig_status(nh_api)
                        break
            # Check if rig was disabled and is back up now
            elif (not g_rig_shouldmine 
                  and rigs['miningRigs'][0]['devices'][g_rig_deviceidx]['status']['enumName'] == 'MINING'):
                # Rig was set offline and now it is enabled again, so restart monitoring
                g_rig_shouldmine = True
                g_rig_ismining = True
                print(f"[{str(datetime.datetime.now())}] > Rig is enabled again, starting monitoring!")
            elif (g_rig_shouldmine 
                  and g_rig_ismining 
                  and rigs['miningRigs'][0]['devices'][g_rig_deviceidx]['status']['enumName'] != 'MINING'):
                # Rig was supposed to be mining but seems to have been disabled, stop monitoring
                g_rig_shouldmine = False
                print(f"[{str(datetime.datetime.now())}] > Rig seems to have been disabled externally, stoping monitoring")


    # Sleep and loop again
    time.sleep(TIME_SLEEP)
    firstLoop = False

# Exit app
exit(0)
