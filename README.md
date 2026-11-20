# Umbra Shadows

[![Latest release](https://img.shields.io/github/v/release/byrodi/umbra-shadows-drg)](https://github.com/byrodi/umbra-shadows-drg/releases/latest)
[![License](https://img.shields.io/github/license/byrodi/umbra-shadows-drg?cacheSeconds=3600)](LICENSE)

Deep Rock Galactic mod: every flare casts round, soft shadows in its class colour, and headlamps cast shadows too.

![A Driller's yellow flare on the cave floor; a bug, a rock and a mushroom cast shadows on the wall](.github/images/cover.jpg)

## Features

- Every flare lights all round and casts shadows of rocks, walls and bugs.
- Hand flares glow in the thrower's class colour.
- The flare gun keeps its own light and casts the same shadows.
- Your headlamp and your team mates' headlamps cast shadows.
- Far shadows fade out smoothly, so a cave full of flares stays playable.
- Client-side only: other players in the lobby do not need it.

![A bug between two flares, with shadows on the floor and the wall](.github/images/bug-between-flares.jpg)

## Before and after

The same spot with the mod off and on.

![Left: the game's flare lights the rock white with no shadow. Right: Umbra Shadows lights it in the Driller's yellow and the bug casts a large shadow on it](.github/images/compare-spider.jpg)

![Left: the game's flare lights a narrow cone. Right: Umbra Shadows lights the floor all round and the rocks cast shadows](.github/images/compare-floor.jpg)

![Left: a flat cave wall. Right: the plants in front of the flare cast a large shadow on the wall](.github/images/compare-mushrooms.jpg)

## Installation

1. Download `umbra-shadows.pak` from the [latest release](https://github.com/byrodi/umbra-shadows-drg/releases/latest).
2. Add it to [mint](https://github.com/trumank/mint) as a local mod and install the profile.
3. Start the game. With [Mod Hub](https://mod.io/g/drg/m/mod-hub) installed, the settings are on the "Umbra Shadows" page.

Do not use it together with [Shadows!](https://mod.io/g/drg/m/shadows): that mod replaces the flares Umbra Shadows works on.

## Settings

All settings apply at once in a mission. Without Mod Hub the mod runs with the defaults.

| Setting | Default | What it does |
| --- | --- | --- |
| Shadow distance | 25 m | Flare shadows fade out beyond this. Lower it for more FPS. |
| Flare shadow range | 14 m | How far a hand flare's shadow light reaches. |
| Flare gun shadow range | 20 m | The same for flare gun flares. |
| Class colour | 1 | 0 keeps the game's colours, 1 is the full class colour, up to 2 is brighter. |
| Flare brightness | 1 | Flare light compared with the game. |
| Flare shadow strength | 0.75 | Share of the light that casts shadows. Lower lifts the shadows. |
| Light shafts in fog | off | Shadows in volumetric fog. Looks good, costs GPU time. |

Headlamp shadows, team headlamp shadows, soft penumbra and cave wall shadows can be switched off on the same page.

## Performance

Tested on Ryzen 9 7900X, RTX 5070, 32 GB RAM, 3840×2160 with DLSS Quality.
Frame rates read from the in-game FPS counter.

| Scene | Mod off (avg) | Mod on (avg / low) |
| --- | --- | --- |
| Normal play in a cave | 210 | 185 / 152 |
| Large crystal cave lit by flare gun flares | 178 | 155 / 133 |
| 50 bugs around flares | 144 | 125 / 115 |

## Compatibility

- Made to run next to [Advanced Darkness](https://mod.io/g/drg/m/advanced-darkness-reloaded), [Pretty Flashlights](https://mod.io/g/drg/m/pretty-flashlights), [Better Post Processing](https://mod.io/g/drg/m/better-post-processing-reloaded) and Mod Hub.
- Turns cave wall shadows back on, which Mod Hub hides by default.
- In a lobby, each player sees the shadows only when they run the mod themselves.

## How it works

The mod changes the game's own flare and headlamp lights; it adds no lights of its own and no per-frame code.

1. A flare's fill light becomes one shadow light that reaches all round.
2. The flare's three spot lights stop casting shadows and only lift the darkness.
3. The engine's own shadow fade turns off the shadows of far flares.

## Building from source

You need Unreal Engine 4.27, Python 3.11 or newer and a project made from [FSD-Template](https://github.com/DRG-Modding/FSD-Template).

1. Copy `Content/_Umbra`, `Plugins/BPForge` and `Tools` into the template project.
2. Build the BPForge editor plugin (it writes Blueprints from a spec):
   ```
   <UE_4.27>\Engine\Build\BatchFiles\Build.bat FSDEditor Win64 Development -Project=<project>\FSD.uproject -Module=BPForge
   ```
   A module-only build writes no `UE4Editor.modules` file. If the editor does not load the plugin, copy that file from another plugin's `Binaries/Win64` and change the module name to BPForge.
3. In the template's `DRGModdingAutomationScripts/Configs`, set `ModName=umbra-shadows` in `GlobalConfig.ini` and put `_Umbra` and `..\AssetRegistry.bin` in `PakWhiteList.ini`. `UtilityBats\MakeDefaultConfigFiles.bat` creates `LocalConfig.ini` for the engine and game paths.
4. Generate and test the assets:
   ```
   python Tools/build_assets.py
   python Tools/umbra_test.py
   ```
5. Cook and pack with the template's scripts. The pak lands in `DRGModdingAutomationScripts/Temp/umbra-shadows.pak`.

The Blueprints live as code in `Tools/umbra_spec.py`; edit them there, not in the editor.

## Credits

The idea of shadow-casting flares comes from [Shadows!](https://mod.io/g/drg/m/shadows) by zombieseatflesh7.

## License

[MIT](LICENSE)
