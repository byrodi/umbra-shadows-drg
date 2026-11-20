"""Tells, per game session, whether Umbra ran. Reads the game's logs only.

Umbra sets r.Shadow.FilterMethod, r.Shadow.FadeResolution and r.Shadow.MinResolution on every level load,
and the engine writes each console variable change to FSD.log. No other installed mod sets these, so a
session without those lines is a session in which Umbra did not run.

Usage: python Tools/umbra_check_logs.py [path to FSD/Saved/Logs]
Without an argument the path is taken from DRGModdingAutomationScripts/Configs/LocalConfig.ini (SteamInstall).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKERS = ("r.Shadow.FilterMethod", "r.Shadow.FadeResolution", "r.Shadow.MinResolution")


def logs_dir():
    if len(sys.argv) > 1:
        return sys.argv[1]
    ini = os.path.join(ROOT, "DRGModdingAutomationScripts", "Configs", "LocalConfig.ini")
    with open(ini, encoding="utf-8", errors="replace") as f:
        match = re.search(r"^SteamInstall=(.+)$", f.read(), re.M)
    if not match:
        sys.exit("SteamInstall not found in LocalConfig.ini; pass the Logs folder as an argument")
    return os.path.join(match.group(1).strip().strip('"'), "FSD", "Saved", "Logs")


def main():
    folder = logs_dir()
    names = sorted((n for n in os.listdir(folder) if n.startswith("FSD") and n.endswith(".log")),
                   key=lambda n: os.path.getmtime(os.path.join(folder, n)))
    for name in names:
        hits = 0
        with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as f:
            for line in f:
                if any(m in line for m in MARKERS):
                    hits += 1
        state = "Umbra RAN (%d shadow settings)" % hits if hits else "Umbra did not run"
        print("%-40s %s" % (name, state))
    print("\nFSD.log is the current or last session; FSD-backup-<date>.log are older ones (date in UTC).")


if __name__ == "__main__":
    main()
