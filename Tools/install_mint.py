"""Installs the packed mod for local testing with mint (the mod loader that builds mods_P.pak).

Usage: python Tools/install_mint.py <path to mint .exe> [--replace OldModName] [--pak PakName]
--pak installs DRGModdingAutomationScripts/Temp/<PakName>.pak (a mod packed with Tools/pack_mod.py)
instead of the GlobalConfig.ini ModName.

Steps: copies DRGModdingAutomationScripts/Temp/<ModName>.pak into mint's mods folder, adds it to the
active mint profile (once), then asks mint to integrate that profile. Close mint and the game first.
--replace removes an earlier local mod of this project (its profile entry and its pak in mint's folder).
Backups (*.bak-install): mod_data.json next to the original, mods_P.pak in mint's data folder.
Without mint, use DRGModdingAutomationScripts/QuickTestMod.bat instead.
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "DRGModdingAutomationScripts")


def config_value(name, key):
    with open(os.path.join(SCRIPTS, "Configs", name), encoding="utf-8") as lines:
        for line in lines:
            left, _, right = line.strip().partition("=")
            if left == key:
                return right
    sys.exit("%s not found in %s" % (key, name))


def same_file(a, b):
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def main():
    args = sys.argv[1:]
    replace = None
    if "--replace" in args:
        replace = args[args.index("--replace") + 1]
        del args[args.index("--replace"):args.index("--replace") + 2]
    mod_name = None
    if "--pak" in args:
        mod_name = args[args.index("--pak") + 1]
        del args[args.index("--pak"):args.index("--pak") + 2]
    if len(args) != 1 or not os.path.isfile(args[0]):
        sys.exit(__doc__)
    mint = args[0]
    mod_name = mod_name or config_value("GlobalConfig.ini", "ModName")
    pak = os.path.join(SCRIPTS, "Temp", mod_name + ".pak")
    if not os.path.isfile(pak):
        sys.exit("No pak at %s. Cook and pack first." % pak)

    mint_dir = os.path.join(os.environ["APPDATA"], "drg-mod-integration")
    mods_dir = os.path.join(mint_dir, "data", "mods")
    target = os.path.join(mods_dir, mod_name + ".pak")
    os.makedirs(mods_dir, exist_ok=True)
    shutil.copyfile(pak, target)
    print("copied pak to mint's mods folder")

    data_path = os.path.join(mint_dir, "config", "mod_data.json")
    with open(data_path, encoding="utf-8") as source:
        data = json.load(source)
    profile = data["active_profile"]
    mods = data["profiles"][profile]["mods"]
    changed = False
    if replace:
        old = os.path.join(mods_dir, replace + ".pak")
        kept = [mod for mod in mods if not same_file(mod["spec"]["url"], old)]
        if len(kept) != len(mods):
            mods[:] = kept
            changed = True
            print("removed %s from mint profile '%s'" % (replace, profile))
        if os.path.isfile(old):
            os.remove(old)
    if not any(same_file(mod["spec"]["url"], target) for mod in mods):
        mods.append({"spec": {"url": target}, "required": False, "enabled": True})
        changed = True
        print("added %s to mint profile '%s'" % (mod_name, profile))
    if changed:
        shutil.copyfile(data_path, data_path + ".bak-install")
        with open(data_path, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2)

    game_pak = os.path.join(config_value("LocalConfig.ini", "SteamInstall"), "FSD", "Content", "Paks", "mods_P.pak")
    if os.path.isfile(game_pak):
        # Keep the backup outside the game folder.
        shutil.copyfile(game_pak, os.path.join(mint_dir, "data", "mods_P.pak.bak-install"))
    code = subprocess.call([mint, "profile", profile])
    print("mint exit code", code)
    sys.exit(code)


if __name__ == "__main__":
    main()
