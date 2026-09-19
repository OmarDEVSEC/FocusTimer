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


# parser = argparse.ArgumentParser(description='Starts focus timer')
# parser.add_argument('timed_start', metavar='timed_start', type=str, help='How many minutes would you like to focus: ')
# args = parser.parse_args()

# timed_start = time.time()
# clean_time = datetime.now()
# print(f"Timer started at {timed_start}")
# print(f"Cleaner time starts at {clean_time}")




MARKER = "focustimer"
START_MARKER  = f"# START {MARKER} - do not edit; managed by focus.py"
END_MARKER  = f"#END {MARKER} "   

# Default list of all the blocked sites for this project. Common subdomains and their variants
#Option to add more with --add on the command line

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


    """Platform Helpers"""

def get_hosts_file() -> Path:
    """Path to the system host files"""
    if platform.system() =="Windows":
        return Path(r"C:\Windows\System32\drivers\etc\hosts")
    return Path("/etc/hosts")


def is_admin() -> bool:
    """
    Check wether you can edit the hosts file.

    Not 100% reliable (permissions can be weird on some setups)
    Enough for a pre-flight warning. The real test is the actual write, which is wrapped in 
    try/except
    
    """
    try:
        if platform.system() == "Windows":
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


def flush_dns() -> None:
    """
    Flush the OS DNS cache so hosts change take effects immediately.

    Without this, sites you just blocked might still resolve for a few seconds via cached entries. 
    Different OSes have different commands. All commands run best-effore - if flushing fails, the block still works
    just with t a slught delay befor the browser cataches up.
    
    """
    system = platform.system()
    try:
        if system == "Darwin":    #macos
            # args as a list (not one string) avoids shell-parsing issues
            subprocess.run(["dscacheutil", "-flushcache"],
                           check = False,capture_output = True, timeout = 5)

            #also reset mDNSResponder, which caches DNS separately
            subprocess.run(["killall", "-HUP", "mDNSResponder"],
                           check = False, capture_output = True, timeout = 5)
        elif system == "Linux":
            # Try systemd-resolved (most modern distros)
            r = subprocess.run(["resolvectl", "flush-caches"],
                               check = False, capture_output = True, timeout = 5)
            if r.returncode != 0:
                # Fall back to older command name if needed
                subprocess.run(["systemd-resolve", "--flush-caches"],
                               check = False, capture_output = True, timeout = 5)
        elif system == "Windows": 
            #shell=True needed for ipconfig on windows machines
            subprocess.run(["ipconfig", "/flushdns"],
                           check = False, capture_output = True, timeout = 5, shell = True)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass #command not availabe - blocks still work, just delayed

"""
Libraries used above:
    * Platform: Detect the OS("Windows", "Darwin" for mac, "Linux") so the code can branch to the right command/API for each
    * Ctypes: Lets python call native OS level functions directly. Used here just for Windows' IsUserAnAdmin(), which Python has no built-in
    equivalent for
    *Os: Used for os.geteuid(), which returns the current process's effective user ID on Unix systems; 0 means root.
    * Subprocess: Runs external command-line progrmas (dscacheutil, killall, resolvectl, ipconfig) and captures their result, since
    flushing DN is something Python can do natively - it has to shell out to OS tools.
"""

# Hosts File Manipulations

def is_active(hosts_file: Path) -> bool:
    """Whether our block markers are currently present in the hosts file."""
    if not hosts_file.exists():
        return False
    return START_MARKER in hosts_file.read_text(0)

def add_block_entries(hosts_file: Path, sites: list[str]) -> None:
    """Add 127.0.0.1 entries for each site wrapped in BEGIN/END markers
    
        idempotent; if entries already exist (from a prior crashed session), they get removed first
        and rewritten fresh.
    """

    # Remove any prior section, so we don't stack duplicates,
    remove_block_entries(hosts_file)

    # Read existing content; create the file if it somehow does not exist
    # unlikely on real systems but keep things defensive.

    if hosts_file.exists():
        existing = hosts_file.read_text()
        if existing and not existing.endswith("\n"):
            existing += "\n"
    else: 
        existing = ""

    block_lines = [START_MARKER]
    for site in sites:
        # 127.0.0.1 is your own machine; nothing is listening there for HTTP,
        # So the brower will get connection refused, Simple and universal
        block_lines.append(f"127.0.0.1 {site}")
    block_lines.append(END_MARKER)
    block_lines.append("") #trailing new line

    hosts_file.write_text(existing + "\n".join(block_lines))

def remove_block_entries(hosts_file: Path) -> bool:
    """ Remove our Begin/End block form the host file. Idempotent.
    o
    nly removes lines between our markers. Everything else in the file
    (include any manual entries the user added) stay exactly as is.

    Returns True if anything was removed. False if the file was clean.
    """
    if not hosts_file.exists():
        return False
    content = hosts_file.read_text()
    if START_MARKER not in content:
        return False

    lines = content.splitlines(keepends=True)
    out_lines = []
    inside_block = False
    for line in lines:
        stripped = line.rstrip("\n\r")
        if stripped == START_MARKER:
            inside_block = True
            continue
        if stripped == END_MARKER:
            inside_block = False
            continue
        if not inside_block:
            out_lines.append(line)
    # Drop any trailing blank lines we left behind, then re-add a single \n
    new_content = "".join(out_lines).rstrip() + "\n"
    hosts_file.write_text(new_content)
    return True

 
#--------------------------------
# Time / Display Helpers Section
#--------------------------------

def format_duration(seconds: int) -> str:
    """Will format seconds as either 'M:SS' or 'H:MM:SS' for the countdown."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_pretty_duration(seconds: int) -> str:
    """Human-friendly duration for start/end messages ('25 minutes, 1H 30M')."""

    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} second" + ("s" if seconds != 1 else "")
    minutes, sec = divmod(seconds,60)
    hours, minutes = divmod(minutes,60)
    if hours == 0:
        base = f"{minutes} minute" + ("s" if minutes != 1 else "")
        return base + {f" {sec}s" if sec else ""}
    if minutes == 0 and sec == 0:
        return f"{hours} hour" + ("s" if hours != 1 else "")
    return f"{hours}h {minutes}m" + (f" {sec}s" if sec else "")


def format_end_time(end_dt: datetime) -> str:
    """Local time at which the session ends, e.g. '4:32 PM'."""
    return end_dt.strftime("%I:%M %p").lstrip("0")

class LiveDisplay:
    """
    This rewrites a fixed block of lines in-place using ANSI escapes.

    On each render() call, moves to the cursor up N lines (N = height of the previous
    render), clears each line, and writes the new content. The net effect is a smooth in-place update with
    no flicker.
    """


    def __init__(self):
        self.prev_line_count = 0
        # Hide the cursor while we're doing live redraws - looks cleaner.
        sys.stdout.write(C.HIDE_CURSOR)
        sys.stdout.flush()

    def render(self, lines:list[str]) -> None:
        if self.prev_line_count > 0:
            #Move cursor up to the top of the previous block.
            sys.stdout.write(f"\033[{self.prev_line_count}A")
        for line in lines:
            sys.stdout.write(C.CLEAR_LINE + line + "\n")
        sys.stdout.flush()
        self.prev_line_count = len(lines)

    def stop(self) -> None:
        sys.stdout.write(C.SHOW_CURSOR)
        sys.stdout.flush()


def build_countdown_view(remaining_seconds: int,
                         num_sites: int,
                         end_time_str: str) -> list[str]:
    """Return the lines up to disply for the countdown at this moment."""
    time_str = format_duration(remaining_seconds)
    #Big centered time, with a rule above and info below.

    return [
        f"{C.DIM}━━━━━━━━━━━━━━━━━━ FOCUS SESSION ━━━━━━━━━━━━━━━━━━{C.RESET}",
        "",
        f"{C.BOLD}{C.BRIGHT_CYAN}                            {time_str}{C.RESET}",
        "",
        f"{C.DIM}   Blocking {num_sites} sites * Ends at {end_time_str}{C.RESET}",
        f"{C.DIM}   Press Ctrl+C to end early{C.RESET}",
        f"{C.DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RESET}",
    ]

def show_countdown(duration_seconds: int, num_sites: int) -> None:
    """Run the visible countdown for the given duration.
    
    Uses time.monotonic() so a system clock adjustment during the session
    (NTP sync, etc.) doesn't skew the countdown.
    """
    display = LiveDisplay()
    start = time.monotonic()
    end_time = datetime.now() + timedelta(seconds=duration_seconds)
    end_str = format_end_time(end_time)

    try:
        while True:
            elapsed = time.monotonic() - start
            remaining = duration_seconds - elapsed
            if remaining <= 0:
                #final render at 00:00, then break.
                display.render(build_countdown_view(0, num_sites, end_str))
                break
            display.render(build_countdown_view(int(round(remaining)),
                                                num_sites, end_str))
            #sleep to the next whole-second boundary.
            time.sleep(max(0.05, 1 - (time.monotonic() - start % 1)))
    finally:
        display.stop()


# --------------------------------------
#       SESSION RUNNER
# --------------------------------------

def run_session(hosts_file: Path, sites: list[str],
                duration_seconds: int) -> None:
    """Add blocks, run timer, remove blocks. Cleanup always runs."""

    #Register cleanup before anything can fail. Runs on normal exit,
    #Unhandled exceptions, and after our signal handlers - call sys.exit

    def cleanup() -> None:
        if remove_block_entries(hosts_file):
            flush_dns()
    atexit.register(cleanup)

    #This function converts ctr+c into a clean sys.exit so that atexit runs

    def _sig_handler(signum, frame):
        print() #get off the countdown line.


# """What the hosts file actually does, for context: it's a plain text file the OS checks before doing a DNS lookup. 
# Each line maps a domain name to an IP address. Adding a line like 127.0.0.1 twitter.com makes your computer think twitter.com 
# resolves to your own machine (127.0.0.1, "localhost") instead of the real site — so any attempt to visit it just fails to load. 
# That's the classic technique focus/blocker apps use to lock out distracting sites during a session, and it requires admin/root privileges 
# to edit (on Mac you'd need sudo to write to /etc/hosts)."""