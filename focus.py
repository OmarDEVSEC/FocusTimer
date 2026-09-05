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
import subprocess           #This runs other programs adn commands fro within python and capture outputs
import signal
import atexit
import platform
import sys
import time
from datetime import datetime, timedelta


parser = argparse.ArgumentParser(description='Starts focus timer')
parser.add_argument('timed_start', metavar='timed_start', type=str, help='How many minutes would you like to focus: ')
args = parser.parse_args()

timed_start = time.time()
clean_time = datetime.now()
print(f"Timer started at {timed_start}")
print(f"Cleaner time starts at {clean_time}")




START_MARKER  = "# START Focus Timer - do not edit; managed by focus.py"
END_MARKER  = "#END Focus Timer"   

# Default list of all the blocked sites for this project

blocked_sites = [
#Anime Site:
"https://9anime.me.uk/",
#Youtube:
"https://youtube.com",
#SocialMedia:
"https://instagram.com",
"https://twitter.com",
"https://titok.com",
"https://facebook.com"
]

# ANSI colors codes for terminal
class C:
    RESET       ="\033[0m"
    BOLD        ="\033[1m"
    DIM         ="\033[2m"
    RED         ="\033[31m"
    GREEN       ="\033[32m" 
    YELLOW      ="\033[33m"
    CYAN        ="\033[36m"
    BRIGHT_CYAN ="\033[96m"
    BRIGHT_YEL  ="\033[96m"
    HIDE_CURSOR ="\033[?25L"
    SHOW_CURSOR ="\033[?25h]"
    CLEAR_LINE  ="\033[K"

def get_hosts_file() -> Path:
    """Path to the system host files"""
    if platform.system() =="Windows":
        return Path(r"C:\Windows\System32\drivers\etc\hosts")
    return Path("/etc/hosts")

"""What the hosts file actually does, for context: it's a plain text file the OS checks before doing a DNS lookup. 
Each line maps a domain name to an IP address. Adding a line like 127.0.0.1 twitter.com makes your computer think twitter.com 
resolves to your own machine (127.0.0.1, "localhost") instead of the real site — so any attempt to visit it just fails to load. 
That's the classic technique focus/blocker apps use to lock out distracting sites during a session, and it requires admin/root privileges 
to edit (on Mac you'd need sudo to write to /etc/hosts)."""