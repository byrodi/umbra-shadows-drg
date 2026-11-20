"""Regenerates the mod's Blueprint assets from Tools/umbra_spec.py with the BPForge editor plugin.

Usage: python Tools/build_assets.py [other_spec.json]
Needs UnrealEngineLocation in DRGModdingAutomationScripts/Configs/LocalConfig.ini and a built BPForge plugin
(see README: "Rebuilding the assets").
"""
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATED = ["Content/_Umbra"]  # only the mod's own folder


def engine_dir():
    config = os.path.join(ROOT, "DRGModdingAutomationScripts", "Configs", "LocalConfig.ini")
    with open(config, encoding="utf-8") as lines:
        for line in lines:
            key, _, value = line.strip().partition("=")
            if key == "UnrealEngineLocation":
                return value
    sys.exit("UnrealEngineLocation not found in LocalConfig.ini")


def main():
    spec = os.path.join(ROOT, "Saved", "umbra_spec.json")
    if len(sys.argv) > 1:
        spec = os.path.abspath(sys.argv[1])  # run another spec as is, e.g. a read-only "dump"
        generated = []
    else:
        generated = GENERATED
        os.makedirs(os.path.dirname(spec), exist_ok=True)
        subprocess.check_call([sys.executable, os.path.join(ROOT, "Tools", "umbra_spec.py"), spec])

    # Generated assets are rebuilt from scratch every time.
    for folder in generated:
        for path in glob.glob(os.path.join(ROOT, folder, "**", "*.uasset"), recursive=True):
            os.remove(path)

    log = os.path.join(ROOT, "Saved", "Logs", "BPForge.log")
    editor = os.path.join(engine_dir(), "Engine", "Binaries", "Win64", "UE4Editor-Cmd.exe")
    code = subprocess.call([editor, os.path.join(ROOT, "FSD.uproject"), "-run=BPForge", "-Spec=" + spec,
                            "-unattended", "-nopause", "-nosplash", "-AllowCommandletRendering", "-abslog=" + log],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(log, encoding="utf-8", errors="replace") as lines:
        for line in lines:
            if "LogBPForge" in line:
                print(line.rstrip())
    print("BPForge exit code", code)
    sys.exit(code)


if __name__ == "__main__":
    main()
