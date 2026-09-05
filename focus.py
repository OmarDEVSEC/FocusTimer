"""# Creating a focus timer that blocks frquently visited sites
    And includes exceptions as well
    NO AI

        Run a focus session for N minutes. During that window, distracting sites
    (reddit, twitter, youtube, tiktok, etc.) become genuinely unreachable at
    the DNS level via your machine's hosts file. Not "muted", not "hidden" -
    they resolve to 127.0.0.1 and the browser gets connection refused. When
    the timer ends the block is lifted automatically.

    Zero external dependencies. Pure Python stdlib. Just save the file and run.

    WHY THIS WORKS:
    Your OS resolves domain names via a chain, and the hosts file at
    /etc/hosts (or C:\\Windows\\System32\\drivers\\etc\\hosts on Windows) is
    checked FIRST, before any DNS server. So `127.0.0.1 reddit.com` sends
    every attempt to reach reddit.com to your own machine, where nothing is
    listening. The browser shows "This site can't be reached" and gives up.



    Note:
    The moment the timer hits zero — or you Ctrl+C early, 
    or the script crashes, or your laptop shuts down and reboots 
    — the block is removed automatically. Sites come back. 
    No manual cleanup required.

    Zero external dependencies

    CLI:
    python focus.py 25          # 25 minutes of focus
    python focus.py 45          # 45 minutes of focus.. etc.

"""

import os               #Talks to the operating system: Environment variables and all
import argparse         #Used to build CLI arguements as shown in the above comments
from pathlib import Path    #Modern way to work with file paths (used to build a path to a log file)
import subprocess 
import signal
import atexit
import platform
import sys
import time
from datetime import datetime, timedelta




START_MARKER  = "# START Focus Timer - do not edit; managed by focus.py"

END_MARKER  = "#END Focus Timer"   

