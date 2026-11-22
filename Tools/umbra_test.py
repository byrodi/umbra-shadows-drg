"""Headless test of the Umbra Blueprints (no game needed).

Builds a small dark room in a throwaway world with the light values of the game and of the mods it
must live with (Pretty Flashlights headlamp, the game's flare), runs the mod's logic and prints the
results as "TEST ..." lines. Also renders pictures to Saved/Test/.

Usage: python Tools/umbra_test.py            (needs the assets from build_assets.py)
This checks logic and look. It does not measure in-game performance.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import umbra_spec as spec  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Saved", "Test")

MESH = "/Script/Engine.StaticMeshComponent"
SPOT = "/Script/Engine.SpotLightComponent"
POINT = "/Script/Engine.PointLightComponent"
MOD = "/Game/_Umbra/"
TEST = "/Game/_UmbraTest/"
CUBE = "/Engine/BasicShapes/Cube.Cube"
SPHERE = "/Engine/BasicShapes/Sphere.Sphere"

# Pretty Flashlights headlamp (FlashlightComponent) and its wide fill light, as shipped by that mod.
BEAM = dict(InnerConeAngle="21.0", OuterConeAngle="30.0", AttenuationRadius="1600.0", Intensity="6000.0",
            SourceRadius="10.0", ShadowBias="1.0", LightColor="(R=188,G=218,B=255,A=255)",
            CastShadows="False", Mobility="Movable")
WIDE = dict(InnerConeAngle="30.0", OuterConeAngle="60.0", AttenuationRadius="600.0", Intensity="160.0",
            CastShadows="False", Mobility="Movable")
# The game's flare (ITM_BaseFlare) at shadow quality 3.
FLARE_FILL = dict(bUseInverseSquaredFalloff="False", AttenuationRadius="2000.0", Intensity="4.0",
                  LightColor="(R=185,G=255,B=176,A=255)", CastShadows="False", Mobility="Movable",
                  RelativeLocation="(X=0,Y=0,Z=20)")
FLARE_SPOT = dict(bUseInverseSquaredFalloff="False", InnerConeAngle="40.0", OuterConeAngle="65.0",
                  LightFalloffExponent="4.0", AttenuationRadius="800.0", Intensity="6.4", ShadowBias="0.25",
                  LightColor="(R=185,G=255,B=176,A=255)", Mobility="Movable")
FLARE_SPOT_ROTATIONS = ["(Pitch=-0.00038,Yaw=92.88731,Roll=-90.00046)", "(Pitch=59.99612,Yaw=-87.11185,Roll=90.00113)",
                        "(Pitch=-59.99501,Yaw=-87.11845,Roll=90.00085)"]
CAMERA = dict(loc=[-40, 0, 170], rot=[-6, 0, 0], exposure=2.5)  # brightened: the scene is a dark cave


def box(name, loc, scale, mesh=CUBE):
    return [
        {"spawn": "/Script/Engine.StaticMeshActor", "as": name, "loc": loc, "scale": scale},
        {"props": name, "component": MESH, "values": {"Mobility": "Movable", "StaticMesh": mesh}},
    ]


CLASSES = ["Driller", "Engineer", "Gunner", "Scout"]
# The game's flare gun flare (PRJ_FlareGun_Projectile01).
GUN_FILL = dict(bUseInverseSquaredFalloff="False", AttenuationRadius="3500.0", Intensity="3.5",
                LightColor="(R=222,G=253,B=255,A=255)", CastShadows="False", IndirectLightingIntensity="6.0",
                Mobility="Movable")
GUN_SPOT = dict(FLARE_SPOT, AttenuationRadius="900.0", Intensity="35.0", ShadowBias="0.5",
                LightColor="(R=255,G=223,B=106,A=255)")
GUN_SPOT_ROTATIONS = ["(Pitch=0,Yaw=90,Roll=90)", "(Pitch=60,Yaw=-90,Roll=-90)", "(Pitch=-60,Yaw=-90,Roll=-90)"]
# Light colours of the game's hand flares per class (spot, fill): ITM_Flare_Small_Driller, ITM_Flare_Small_Engineer,
# ITM_Flare_Large_Gunner, ITM_Flare_Large_Scout.
CLASS_LIGHT = {
    "Driller": ("(R=76,G=240,B=255,A=255)", "(R=160,G=245,B=255,A=255)"),
    "Engineer": ("(R=91,G=91,B=255,A=255)", "(R=160,G=160,B=255,A=255)"),
    "Gunner": ("(R=127,G=255,B=95,A=255)", "(R=174,G=255,B=160,A=255)"),
    "Scout": ("(R=255,G=199,B=84,A=255)", "(R=255,G=226,B=188,A=255)"),
}


def flare_parts(fill_name, fill, spot, rotations=FLARE_SPOT_ROTATIONS):
    # The flare's own mesh casts shadows, as the game's hand flare does (SM_Shape_Pipe, default CastShadow).
    # The mesh comes first, so it is the root, as in the game; the lights are attached to it.
    parts = [{"name": "StaticMesh", "class": MESH, "props": {"StaticMesh": CUBE, "RelativeScale3D": "(X=0.15,Y=0.03,Z=0.03)",
                                                             "Mobility": "Movable"}},
             {"name": fill_name, "class": POINT, "props": fill}]
    for index, rotation in enumerate(rotations):
        parts.append({"name": "SpotLight_Shadow_%d" % (index + 1), "class": SPOT,
                      "props": dict(spot, RelativeRotation=rotation)})
    return parts


def test_assets():
    assets = [
        {"kind": "blueprint", "transient": True, "path": TEST + "ITM_TestFlare_" + name, "parent": "/Script/FSD.Flare",
         "variables": [{"name": "BaseIntensity", "type": "float", "default": "4.0"}],
         "components": flare_parts("Light_NoShadow", dict(FLARE_FILL, LightColor=CLASS_LIGHT[name][1]),
                                   dict(FLARE_SPOT, LightColor=CLASS_LIGHT[name][0]))}
        for name in CLASSES
    ]
    assets += [
        {"kind": "blueprint", "transient": True, "path": TEST + "PRJ_TestFlareGun", "parent": "/Script/FSD.FlareGunProjectile",
         "variables": [{"name": "LightIntensity_Point", "type": "float", "default": "3.5"},
                       {"name": "LightIntensity_Spot", "type": "float", "default": "35.0"}],
         "components": flare_parts("PointLight_NoShadow", GUN_FILL, GUN_SPOT, GUN_SPOT_ROTATIONS)},
        # A dwarf: headlamp, wide fill, and a body mesh (behind the lamp, so it stays out of the pictures).
        {"kind": "blueprint", "transient": True, "path": TEST + "BP_TestDwarf", "parent": "/Script/Engine.Pawn",
         "components": [
             {"name": "Headlamp", "class": SPOT, "props": BEAM},
             {"name": "Wide", "class": SPOT, "props": WIDE},
             {"name": "Body", "class": MESH,
              "props": {"StaticMesh": CUBE, "RelativeLocation": "(X=-45,Y=0,Z=-40)", "RelativeScale3D": "(X=0.3,Y=0.5,Z=0.9)",
                        "Mobility": "Movable"}},
         ]},
    ]
    return assets


def luminance(owner, amount):
    hue = [float(x.split("=")[1]) for x in spec.CLASS_HUE[owner].strip("()").split(",")[:3]]
    pastel = [1.0 + (h - 1.0) * min(amount, 1.0) for h in hue]
    return max(0.35, 0.2126 * pastel[0] + 0.7152 * pastel[1] + 0.0722 * pastel[2])


def defaults():
    return {name: default for name, _, _, _, _, _, default in spec.SLIDERS}


def game_intensities(owner, chosen, gun):
    """What the game's flare sets on its lights each frame, after the mod set its variables (default settings)."""
    d = defaults()
    s, bright = d["ShadowStrength"], d["FlareBrightness"]
    if gun:  # the flare gun keeps the game's colour
        lum = 1.0
    else:
        lum = luminance(owner, d["FlareColour"])
        bright *= max(d["FlareColour"], 1.0)
    if gun:
        point = spec.GUN_POINT_BASE * (bright / lum * (spec.GUN_TOTAL / spec.GUN_POINT_BASE * s if chosen else 1.0))
        spot = spec.GUN_SPOT_BASE * (bright / lum * (spec.GUN_TOTAL / spec.GUN_SPOT_BASE * (1 - s) if chosen else 1.0))
        return point, spot
    base = 4.0 * bright / lum * (spec.HAND_TOTAL * s if chosen else 1.0)
    return base, base * spec.HAND_SPOT_SHARE


def animate(flares, guns, chosen):
    out = []
    for name, (_, owner) in flares.items():
        fill, spot = game_intensities(owner, name in chosen, False)
        out.append({"props": name + "Fill", "values": {"Intensity": "%.3f" % fill}})
        for i in (1, 2, 3):
            out.append({"props": "%sSpot%d" % (name, i), "values": {"Intensity": "%.3f" % spot}})
    for name in guns:
        fill, spot = game_intensities("Scout", name in chosen, True)
        out.append({"props": name + "Fill", "values": {"Intensity": "%.3f" % fill}})
        for i in (1, 2, 3):
            out.append({"props": "%sSpot%d" % (name, i), "values": {"Intensity": "%.3f" % spot}})
    return out


def fade_steps():
    """End of a flare's light: the mod fades it out itself (FadeLights, every frame).

    A hand flare with Duration 2 s is due at once (its light ends 2 s from now, the fade 1.8 s later). A flare gun
    flare gets a light timeline at 86 of 90, playing at rate 1: due, its light goes out at 88 (2 s), the game hides
    it 2 s later. Each capture ticks the world 0.8 s; the intensity must fall smoothly to 0, the slots must
    empty and the Tick stop. Expected hand fill (template 4.0): 4 * (1 - t / 3.8)^3.
    """
    out = [
        {"spawn": TEST + "ITM_TestFlare_Engineer.ITM_TestFlare_Engineer_C", "as": "flareG", "loc": [-2600, 1500, 30],
         "rot": [0, 90, 0]},
        {"props": "flareG", "values": {"Duration": "2.0"}},
        {"comp": "flareG", "name": "Light_NoShadow", "as": "flareGFill"},
        {"comp": "flareG", "name": "SpotLight_Shadow_1", "as": "flareGSpot"},
        {"spawn": TEST + "PRJ_TestFlareGun.PRJ_TestFlareGun_C", "as": "gunC", "loc": [-1500, 2200, 500], "rot": [0, 90, 0]},
        {"comp": "gunC", "name": "PointLight_NoShadow", "as": "gunCFill"},
        {"addcomp": "gunC", "class": "/Script/Engine.TimelineComponent", "as": "gunCAnim"},
        {"call": "gunCAnim.SetTimelineLengthMode", "args": {"NewLengthMode": "TL_TimelineLength"}},
        {"call": "gunCAnim.SetTimelineLength", "args": {"NewLength": "90.0"}},
        {"call": "gunCAnim.SetPlaybackPosition", "args": {"NewPosition": "86.0", "bFireEvents": "False", "bFireUpdate": "False"}},
        {"call": "gunCAnim.SetPlayRate", "args": {"NewRate": "1.0"}},
        {"call": "gunCAnim.Play"},
        {"print": "gunCAnim", "fields": ["TheTimeline"]},
        {"call": "mod.Watch"},
        {"print": "mod", "fields": ["Fading", "FadeFlare0", "FadeStart0", "FadeEnd0", "FadeFlare1", "FadeStart1", "FadeEnd1",
                                    "FadeFlare2", "PrimaryActorTick"]},
        {"print": "flareGFill", "fields": ["IESBrightnessScale"]}, {"print": "flareGSpot", "fields": ["IESBrightnessScale"]},
        {"print": "gunCFill", "fields": ["IESBrightnessScale"]},
        # Another Watch must not take a second slot for the same flares.
        {"call": "mod.Watch"},
        {"print": "mod", "fields": ["FadeFlare2"]},
    ]
    for frame in range(1, 8):
        # The test world advances time but runs no actor ticks or timers, so the Tick's function is called here.
        out.append(dict(CAMERA, capture=os.path.join(OUT, "umbra_fade_%d.png" % frame)))
        out += [{"call": "mod.FadeLights"},
                {"print": "flareGFill", "fields": ["Intensity"]}, {"print": "flareGSpot", "fields": ["Intensity"]},
                {"print": "gunCFill", "fields": ["Intensity"]}, {"print": "mod", "fields": ["Fading", "FadeBusy"]}]
    out.append({"print": "mod", "fields": ["Fading", "FadeFlare0", "FadeFlare1"]})
    return out


def steps():
    out = []
    out += box("floor", [1500, 0, -50], [60, 60, 1])
    out += box("wall", [1900, 0, 500], [1, 60, 12])
    out += box("pillar", [1000, 150, 250], [0.8, 0.8, 5])
    out += box("rock", [1150, -350, 70], [1.4, 1.4, 1.4], SPHERE)
    out += box("bug", [800, -80, 45], [0.9, 0.9, 0.9], SPHERE)
    flares = {"flareA": ([1250, 650, 30], "Engineer"), "flareB": ([650, -750, 30], "Gunner"),
              "flareC": ([2600, 2300, 30], "Scout"), "flareD": ([-2200, 1500, 30], "Driller"),
              "flareE": ([2600, -2500, 30], "Engineer")}
    for name, (loc, owner) in flares.items():
        # Turned so the ring of the three spot lights faces the scene (a flare has two unlit ends).
        out.append({"spawn": TEST + "ITM_TestFlare_%s.ITM_TestFlare_%s_C" % (owner, owner), "as": name, "loc": loc,
                    "rot": [0, 90, 0]})
    guns = {"gunA": [1500, -900, 500], "gunB": [-1500, -2200, 500]}
    for name, loc in guns.items():
        out.append({"spawn": TEST + "PRJ_TestFlareGun.PRJ_TestFlareGun_C", "as": name, "loc": loc, "rot": [0, 90, 0]})
    scenery = ["floor", "wall", "pillar", "rock"]

    def scenery_shadows(on):
        # Stand-in for cave terrain. Mod Hub hides terrain shadows by default; the mod turns them back on
        # for real terrain sections (checked below on a DeepCSGSection). Here the meshes are switched by hand.
        return [{"props": name, "component": MESH, "values": {"CastShadow": str(on)}} for name in scenery]

    def camera(index, extra=()):
        # A player controller gives the world a camera manager; flares are chosen by distance to it.
        # It has no player, and console commands sent through it are dropped, so it is removed again
        # before steps that set console variables. In the game the controller always has a player.
        return [{"spawn": "/Script/Engine.PlayerController", "as": "pc%d" % index, "loc": CAMERA["loc"]},
                {"call": "mod.Refresh"},
                {"call": "mod.ApplyPawn", "args": {"Pawn": "@me", "bLocal": "True"}},
                {"call": "mod.ApplyPawn", "args": {"Pawn": "@mate", "bLocal": "False"}}] + list(extra) + [
                {"destroy": "pc%d" % index}]

    # The fast check (Watch): the game resets one flare's spot radius, and a new flare appears.
    # Both must have the mod's light after one Watch call, without waiting for Refresh.
    watch = [
        {"props": "flareASpot", "values": {"AttenuationRadius": "800.0"}},
        {"spawn": TEST + "ITM_TestFlare_Driller.ITM_TestFlare_Driller_C", "as": "flareF", "loc": [-2600, -1500, 30],
         "rot": [0, 90, 0]},
        {"comp": "flareF", "name": "SpotLight_Shadow_1", "as": "flareFSpot"},
        {"print": "flareASpot", "fields": ["AttenuationRadius"]},
        {"print": "flareFSpot", "fields": ["AttenuationRadius", "LightColor"]},
        {"call": "mod.Watch"},
        {"print": "flareASpot", "fields": ["AttenuationRadius"]},
        {"print": "flareFSpot", "fields": ["AttenuationRadius", "LightColor", "OuterConeAngle", "CastShadows"]},
        {"comp": "flareF", "name": "Light_NoShadow", "as": "flareFFill"},
        {"print": "flareFFill", "fields": ["AttenuationRadius", "CastShadows"]},
    ]

    def flare_report(fields_spot, fields_fill):
        report = []
        for name in list(flares) + list(guns):
            report.append({"print": name + "Spot", "fields": fields_spot})
            if fields_fill:
                report.append({"print": name + "Fill", "fields": fields_fill})
        return report

    out += [
        {"spawn": TEST + "BP_TestDwarf.BP_TestDwarf_C", "as": "me", "loc": [0, 0, 160]},
        {"comp": "me", "name": "Headlamp", "as": "myLamp"},
        {"comp": "me", "name": "Wide", "as": "myWide"},
        {"comp": "me", "name": "Body", "as": "myBody"},
        {"spawn": TEST + "BP_TestDwarf.BP_TestDwarf_C", "as": "mate", "loc": [500, -800, 170], "rot": [-4, 60, 0]},
        {"comp": "mate", "name": "Headlamp", "as": "mateLamp"},
        # Terrain section with shadows hidden, as Mod Hub leaves it.
        {"spawn": "/Script/FSDEngine.DeepCSGSection", "as": "section", "loc": [0, 0, -2000]},
        {"get": "section.DeepMesh", "as": "terrainMesh"},
        {"props": "terrainMesh", "values": {"CastShadow": "False"}},
    ]
    for name in flares:
        out.append({"comp": name, "name": "SpotLight_Shadow_1", "as": name + "Spot"})
        out.append({"comp": name, "name": "Light_NoShadow", "as": name + "Fill"})
    for name in guns:
        out.append({"comp": name, "name": "SpotLight_Shadow_1", "as": name + "Spot"})
        out.append({"comp": name, "name": "PointLight_NoShadow", "as": name + "Fill"})
    for name in list(flares) + list(guns):
        for i in (1, 2, 3):
            out.append({"comp": name, "name": "SpotLight_Shadow_%d" % i, "as": "%sSpot%d" % (name, i)})
    out.append({"comp": "flareA", "name": "StaticMesh", "as": "flareAMesh"})
    out += scenery_shadows(False)
    out.append(dict(CAMERA, capture=os.path.join(OUT, "umbra_0_before.png")))

    # The mod. BeginPlay runs on spawn.
    out += [
        {"spawn": MOD + "InitCave.InitCave_C", "as": "mod"},
        {"call": "mod.SaveSettings"},
        {"get": "mod.Settings", "as": "settings"},
        {"print": "settings", "fields": ["Enabled", "OwnLamp", "TeamLamps", "SoftShadows", "TerrainShadows",
                                         "LightShafts", "ShadowDistance", "FlareRange", "GunFlareRange", "FlareColour", "FlareBrightness",
                                         "ShadowStrength", "Penumbra", "Quality"]},
        {"cvar": "r.Shadow.FilterMethod"}, {"cvar": "r.Shadow.MaxResolution"},
        {"cvar": "r.Shadow.FadeResolution"}, {"cvar": "r.Shadow.MinResolution"},
    ]
    out += camera(1, watch)
    out += [
        {"print": "myLamp", "fields": ["CastShadows", "SourceRadius"]},
        {"print": "myWide", "fields": ["CastShadows"]},
        {"print": "myBody", "fields": ["CastShadow"]},
        {"print": "mateLamp", "fields": ["CastShadows", "SourceRadius"]},
    ]
    out += flare_report(["CastShadows", "AttenuationRadius", "LightColor", "OuterConeAngle", "RelativeRotation"],
                        ["CastShadows", "AttenuationRadius", "LightFalloffExponent", "ShadowResolutionScale", "LightColor",
                         "bCastVolumetricShadow", "RelativeLocation"])
    for name in flares:
        out.append({"print": name, "fields": ["BaseIntensity"]})
    for name in guns:
        out.append({"print": name, "fields": ["LightIntensity_Point", "LightIntensity_Spot"]})
    out.append({"print": "flareAMesh", "fields": ["CastShadow"]})
    out += animate(flares, guns, set(flares) | set(guns))
    out += [
        {"call": "mod.ApplyTerrain"},
        {"print": "terrainMesh", "fields": ["CastShadow"]},
    ]
    out += scenery_shadows(True)
    out.append(dict(CAMERA, capture=os.path.join(OUT, "umbra_1_default.png")))
    out += fade_steps()

    # Settings page through the Mod Hub adapter: one shadow flare, team lamps off, hard edges, 1024 maps.
    out += [
        {"find": MOD + "UI/Umbra_Hub.Umbra_Hub_C", "as": "hub"},
        {"call": "hub.GetModPages"},
        {"get": "hub.Page", "as": "page"},
        {"print": "page", "fields": ["Mod"]},
        {"call": "page.SldShadowDistance_K2Node", "args": {"Value": "40.0"}},
        {"call": "page.ChkTeamLamps_K2Node", "args": {"bIsChecked": "False"}},
        {"call": "page.ChkSoftShadows_K2Node", "args": {"bIsChecked": "False"}},
        {"call": "page.SldQuality_K2Node", "args": {"Value": "1.0"}},
        {"print": "settings", "fields": ["ShadowDistance", "TeamLamps", "SoftShadows", "Quality"]},
        {"cvar": "r.Shadow.FilterMethod"}, {"cvar": "r.Shadow.MaxResolution"},
        {"cvar": "r.Shadow.FadeResolution"}, {"cvar": "r.Shadow.MinResolution"},
    ]
    out += camera(2)
    out.append({"print": "mateLamp", "fields": ["CastShadows"]})
    out += flare_report(["CastShadows"], None)
    out.append(dict(CAMERA, capture=os.path.join(OUT, "umbra_2_one_flare_hard.png")))

    # Enabled off: the game's own state.
    out.append({"call": "page.ChkEnabled_K2Node", "args": {"bIsChecked": "False"}})
    out.append({"cvar": "r.Shadow.FilterMethod"})
    out += [{"cvar": "r.Shadow.FadeResolution"}, {"cvar": "r.Shadow.MinResolution"}]
    out += camera(3)
    out += [
        {"print": "myLamp", "fields": ["CastShadows"]},
        {"print": "flareASpot", "fields": ["CastShadows", "SourceRadius", "LightColor", "ShadowBias",
                                           "InnerConeAngle", "OuterConeAngle"]},
        {"print": "flareAFill", "fields": ["AttenuationRadius", "LightColor", "CastShadows", "LightFalloffExponent",
                                           "RelativeLocation"]},
        {"print": "flareA", "fields": ["BaseIntensity"]},
        {"print": "gunA", "fields": ["LightIntensity_Point", "LightIntensity_Spot"]},
        {"print": "flareCSpot", "fields": ["LightColor"]},
        {"print": "flareCFill", "fields": ["AttenuationRadius", "LightColor"]},
        {"print": "flareEFill", "fields": ["AttenuationRadius"]},
        {"print": "gunASpot", "fields": ["CastShadows", "LightColor", "ShadowBias", "InnerConeAngle", "OuterConeAngle",
                                         "RelativeRotation"]},
        {"print": "gunAFill", "fields": ["AttenuationRadius", "LightColor"]},
    ]
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    assets = test_assets() + [{"kind": "worldtest", "steps": steps()}]
    spec = os.path.join(ROOT, "Saved", "umbra_test.json")
    with open(spec, "w", encoding="utf-8") as out:
        json.dump({"assets": assets}, out, indent=1)
    sys.exit(subprocess.call([sys.executable, os.path.join(ROOT, "Tools", "build_assets.py"), spec]))


if __name__ == "__main__":
    main()
