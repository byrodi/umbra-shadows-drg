"""Headless test of the Umbra Blueprints (no game needed).

Builds a small dark room in a throwaway world with the light values of the game and of the mods it
must live with (Pretty Flashlights headlamp, the game's flare), runs the mod's logic and prints the
results as "TEST ..." lines. Also renders pictures to ue/Saved/Test/umbra (or env DRG_TEST_OUT).

Usage: drg test umbra   (runs: python Tools/umbra_test.py <out.json>; needs the assets of drg build umbra --save)
Writes the test spec to <out.json> and the expected TEST values to <out.json>.expect.json.
This checks logic and look. It does not measure in-game performance.
"""
import json
import os
import sys

from drgkit import config

import umbra_spec as spec

OUT = os.environ.get("DRG_TEST_OUT") or str(config.UE_SAVED / "Test" / "umbra")

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
SETTINGS_FIELDS = ["Enabled", "Level", "FlareColour", "OwnLamp", "TeamLamps", "SoftShadows", "TerrainShadows", "LightShafts",
                   "ShadowDistance", "FlareRange", "HandFlares", "GunFlareRange", "GunFlares", "Quality", "FlareBrightness",
                   "ShadowStrength", "Penumbra"]


def box(name, loc, scale, mesh=CUBE):
    return [
        {"spawn": "/Script/Engine.StaticMeshActor", "as": name, "loc": loc, "scale": scale},
        {"props": name, "component": MESH, "values": {"Mobility": "Movable", "StaticMesh": mesh}},
    ]


CLASSES = ["Driller", "Engineer", "Gunner", "Scout"]
# The game's flare gun flare (PRJ_FlareGun_Projectile01).
GUN_FILL = dict(bUseInverseSquaredFalloff="False", AttenuationRadius="3500.0", Intensity="3.5",
                LightColor="(R=222,G=253,B=255,A=255)", CastShadows="False", CastStaticShadows="False",
                CastDynamicShadows="False", IndirectLightingIntensity="6.0", Mobility="Movable")
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
    out = {name: default for name, _, _, _, _, _, default in spec.SLIDERS}
    out.update({name: default for name, _, default in spec.LEVEL_SETTINGS})
    return out


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
        # The flare gun puts its own intensities back when its light timeline starts, 2.5 s after it is fired.
        # Without a fresh timeline Watch leaves the variables alone (3.5 stays); with one it applies the mod's again.
        {"props": "gunA", "values": {"LightIntensity_Point": "3.5", "LightIntensity_Spot": "35.0"}},
        {"call": "mod.Watch"},
        {"print": "gunA", "fields": ["LightIntensity_Point"]},
        {"addcomp": "gunA", "class": "/Script/Engine.TimelineComponent", "as": "gunAAnim"},
        {"call": "gunAAnim.SetTimelineLengthMode", "args": {"NewLengthMode": "TL_TimelineLength"}},
        {"call": "gunAAnim.SetTimelineLength", "args": {"NewLength": "90.0"}},
        {"call": "gunAAnim.SetPlaybackPosition", "args": {"NewPosition": "0.2", "bFireEvents": "False", "bFireUpdate": "False"}},
        {"call": "gunAAnim.SetPlayRate", "args": {"NewRate": "1.17"}},
        {"call": "gunAAnim.Play"},
        {"call": "mod.Watch"},
        {"print": "gunA", "fields": ["LightIntensity_Point", "LightIntensity_Spot"]},
        # The test world runs no component ticks, so the timeline would stay fresh: stop it.
        {"call": "gunAAnim.Stop"},
    ]

    def flare_report(fields_spot, fields_fill):
        report = []
        for name in list(flares) + list(guns):
            if fields_spot:
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
        {"get": "mod.Settings", "as": "settings"},
        # An old save with hand-set values: the level puts its own values back (ApplyLevel, also run on load).
        {"props": "settings", "values": {"Level": "1.0", "LightShafts": "True", "ShadowDistance": "55.0", "TeamLamps": "False"}},
        {"call": "mod.ApplyLevel"},
        {"call": "mod.SaveSettings"},
        {"print": "settings", "fields": SETTINGS_FIELDS},
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
                        ["CastShadows", "CastDynamicShadows", "AttenuationRadius", "LightFalloffExponent",
                         "ShadowResolutionScale", "LightColor", "bCastVolumetricShadow", "RelativeLocation"])
    for name in flares:
        out.append({"print": name, "fields": ["BaseIntensity"]})
    for name in guns:
        out.append({"print": name, "fields": ["LightIntensity_Point", "LightIntensity_Spot"]})
    out.append({"print": "flareAMesh", "fields": ["CastShadow"]})
    # A flare that turns (flies, rolls) turns the lift of its shadow light with it. Watch puts the light back
    # above the flare: RelativeLocation stays after the turn and changes after Watch. Then the flare turns back.
    out += [{"print": "flareAFill", "fields": ["RelativeLocation"]},
            {"call": "flareA.K2_SetActorRotation", "args": {"NewRotation": "(Pitch=90,Yaw=90,Roll=0)", "bTeleportPhysics": "True"}},
            {"print": "flareAFill", "fields": ["RelativeLocation"]},
            {"call": "mod.Watch"},
            {"print": "flareAFill", "fields": ["RelativeLocation"]},
            {"call": "flareA.K2_SetActorRotation", "args": {"NewRotation": "(Pitch=0,Yaw=90,Roll=0)", "bTeleportPhysics": "True"}},
            {"call": "mod.Watch"},
            {"print": "flareAFill", "fields": ["RelativeLocation"]}]
    out += animate(flares, guns, set(flares) | set(guns))
    out += [
        {"call": "mod.ApplyTerrain"},
        {"print": "terrainMesh", "fields": ["CastShadow"]},
    ]
    out += scenery_shadows(True)
    out.append(dict(CAMERA, capture=os.path.join(OUT, "umbra_1_default.png")))
    out += fade_steps()

    # Settings page through the Mod Hub adapter: the quality slider writes the level's settings.
    out += [
        {"find": MOD + "UI/Umbra_Hub.Umbra_Hub_C", "as": "hub"},
        {"call": "hub.GetModPages"},
        {"get": "hub.Page", "as": "page"},
        {"get": "page.ValLevel", "as": "valLevel"},
        {"print": "page", "fields": ["Mod"]},
        {"print": "valLevel", "fields": ["Text"]},
        # Low: no team lamps, hard edges, 2 hand flares and no flare gun flare with shadows.
        {"call": "page.SldLevel_K2Node", "args": {"Value": "0.0"}},
        {"print": "valLevel", "fields": ["Text"]},
        {"print": "settings", "fields": SETTINGS_FIELDS},
        {"cvar": "r.Shadow.FilterMethod"}, {"cvar": "r.Shadow.MaxResolution"},
        {"cvar": "r.Shadow.FadeResolution"}, {"cvar": "r.Shadow.MinResolution"},
    ]
    out += camera(2)
    out.append({"print": "mateLamp", "fields": ["CastShadows"]})
    out += flare_report(None, ["CastShadows", "AttenuationRadius"])
    out.append(dict(CAMERA, capture=os.path.join(OUT, "umbra_2_low.png")))
    # Ultra: every hand flare, 4 flare gun flares, fog shadows. The map size stays the game's.
    out += [
        {"call": "page.SldLevel_K2Node", "args": {"Value": "3.0"}},
        {"print": "valLevel", "fields": ["Text"]},
        {"print": "settings", "fields": SETTINGS_FIELDS},
        {"cvar": "r.Shadow.FilterMethod"}, {"cvar": "r.Shadow.MaxResolution"},
    ]
    out += camera(4)
    out += flare_report(None, ["CastShadows", "bCastVolumetricShadow"])
    out.append(dict(CAMERA, capture=os.path.join(OUT, "umbra_3_ultra.png")))
    # Reset: Medium again.
    out += [
        {"call": "page.BtnReset_K2Node", "args": {}},
        {"print": "valLevel", "fields": ["Text"]},
        {"print": "settings", "fields": ["Level", "TeamLamps", "HandFlares", "GunFlares", "Quality"]},
    ]

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
        {"print": "gunAFill", "fields": ["AttenuationRadius", "LightColor", "CastShadows"]},
    ]
    # Space Rig after a mission: the mod is on with soft shadows, but the rig gets the game's filter (0).
    out += [
        {"call": "page.ChkEnabled_K2Node", "args": {"bIsChecked": "True"}},
        {"cvar": "r.Shadow.FilterMethod"},
        {"spawn": MOD + "InitSpacerig.InitSpacerig_C", "as": "rig"},
        {"cvar": "r.Shadow.FilterMethod"},
    ]
    return out


def flag(value):
    return {"equals": "True" if value else "False"}


def num(value, tol=0.001):
    return {"approx": value, "tol": tol}


def expectations():
    """What the TEST lines must say. drg test checks the LAST line with each prefix, so a value printed in
    several steps is checked as the last step leaves it (see steps())."""
    def level(name, index):
        return spec.LEVELS[name][index]
    gun_point, gun_spot = game_intensities("Scout", True, True)
    medium = spec.DEFAULT_LEVEL
    checks = [
        # Watch: a reset spot and a new flare get the mod's light at once.
        ("flareFSpot.AttenuationRadius", num(level("FlareRange", medium) * 100)),
        ("flareFSpot.OuterConeAngle", num(spec.FLARE_OUTER_UPGRADED)),
        ("flareFSpot.CastShadows", flag(False)),
        ("flareFFill.CastShadows", flag(True)),
        # Headlamps at the default level (myLamp is checked again with the mod off, below).
        ("myLamp.SourceRadius", num(spec.LAMP_SOURCE_RADIUS)),
        ("myWide.CastShadows", flag(False)),
        ("myBody.CastShadow", flag(False)),
        ("mateLamp.SourceRadius", num(spec.LAMP_SOURCE_RADIUS)),
        # Default level: chosen flares shadow with their fill light; the spots do not.
        ("flareBSpot.CastShadows", flag(False)),
        ("flareBSpot.OuterConeAngle", num(spec.FLARE_OUTER_UPGRADED)),
        ("flareBFill.LightFalloffExponent", num(spec.SHADOW_FALLOFF)),
        ("flareBFill.ShadowResolutionScale", num(spec.SHADOW_RESOLUTION_SCALE)),
        ("flareBFill.RelativeLocation", {"contains": "Z=%f" % spec.SHADOW_LIGHT_LIFT}),
        ("gunB.LightIntensity_Point", num(gun_point)),
        ("gunB.LightIntensity_Spot", num(gun_spot)),
        ("flareAMesh.CastShadow", flag(False)),
        ("terrainMesh.CastShadow", flag(True)),
        # Fade: the slots empty and the Tick stops; the start levels are kept in IESBrightnessScale.
        ("mod.PrimaryActorTick", {"contains": spec.TICK_GROUP}),
        ("flareGFill.IESBrightnessScale", num(4.0)),
        ("flareGSpot.IESBrightnessScale", num(4.0 * spec.HAND_SPOT_SHARE)),
        ("gunCFill.IESBrightnessScale", num(spec.GUN_POINT_BASE)),
        ("flareGFill.Intensity", num(0.0)),
        ("flareGSpot.Intensity", num(0.0)),
        ("gunCFill.Intensity", num(0.0)),
        ("mod.Fading", flag(False)),
        ("mod.FadeBusy", flag(False)),
        ("mod.FadeFlare0", {"equals": "None"}),
        ("mod.FadeFlare1", {"equals": "None"}),
        ("mod.FadeFlare2", {"equals": "None"}),
        # Settings page through the Mod Hub adapter.
        ("page.Mod", {"contains": "InitCave_C"}),
        # Low (last printed there): no team lamps, 2 hand flares at 10 m, no flare gun flare with shadows.
        ("mateLamp.CastShadows", flag(level("TeamLamps", 0))),
        ("flareBFill.AttenuationRadius", num(level("FlareRange", 0) * 100)),
        ("flareDFill.AttenuationRadius", num(level("FlareRange", 0) * 100)),
        ("gunBFill.AttenuationRadius", num(level("GunFlareRange", 0) * 100)),
        # Ultra (last printed there): every flare shadows, also the fog.
        ("settings.Enabled", flag(True)),
        ("settings.SoftShadows", flag(level("SoftShadows", 3))),
        ("settings.LightShafts", flag(level("LightShafts", 3))),
        ("settings.ShadowDistance", num(level("ShadowDistance", 3))),
        ("settings.FlareRange", num(level("FlareRange", 3))),
        ("settings.GunFlareRange", num(level("GunFlareRange", 3))),
        ("flareEFill.CastShadows", flag(True)),
        ("flareDFill.bCastVolumetricShadow", flag(level("LightShafts", 3))),
        ("gunBFill.CastShadows", flag(True)),
        ("gunBFill.bCastVolumetricShadow", flag(level("LightShafts", 3))),
        # Reset: the default level again.
        ("valLevel.Text", {"contains": spec.LEVEL_NAMES[medium]}),
        ("settings.Level", num(float(medium))),
        ("settings.TeamLamps", flag(level("TeamLamps", medium))),
        ("settings.HandFlares", num(level("HandFlares", medium))),
        ("settings.GunFlares", num(level("GunFlares", medium))),
        ("settings.Quality", num(0.0)),
        # Enabled off: the game's own values come back.
        ("cvar r.Shadow.FadeResolution", {"equals": str(spec.FADE_RES_GAME)}),
        ("cvar r.Shadow.MinResolution", {"equals": str(spec.MIN_RES_GAME)}),
        ("myLamp.CastShadows", flag(False)),
        ("flareASpot.CastShadows", flag(True)),
        ("flareASpot.SourceRadius", num(0.0)),
        ("flareASpot.ShadowBias", num(spec.FLARE_BIAS_GAME)),
        ("flareASpot.InnerConeAngle", num(spec.FLARE_INNER_GAME)),
        ("flareASpot.OuterConeAngle", num(spec.FLARE_OUTER_GAME)),
        ("flareAFill.AttenuationRadius", num(2000.0)),
        ("flareAFill.CastShadows", flag(False)),
        ("flareAFill.LightFalloffExponent", num(spec.FILL_FALLOFF_GAME)),
        ("flareAFill.RelativeLocation", {"contains": "Z=%f" % spec.HAND_FILL_Z}),
        ("flareAFill.LightColor", {"equals": "(B=255,G=160,R=160,A=255)"}),
        ("flareA.BaseIntensity", num(4.0)),
        ("gunA.LightIntensity_Point", num(spec.GUN_POINT_BASE)),
        ("gunA.LightIntensity_Spot", num(spec.GUN_SPOT_BASE)),
        ("flareCSpot.LightColor", {"equals": "(B=84,G=199,R=255,A=255)"}),
        ("flareCFill.AttenuationRadius", num(2000.0)),
        ("flareEFill.AttenuationRadius", num(2000.0)),
        ("gunASpot.CastShadows", flag(True)),
        ("gunASpot.ShadowBias", num(spec.GUN_BIAS_GAME)),
        ("gunASpot.InnerConeAngle", num(spec.FLARE_INNER_GAME)),
        ("gunASpot.OuterConeAngle", num(spec.FLARE_OUTER_GAME)),
        ("gunASpot.RelativeRotation", {"contains": "Yaw=90.000000"}),
        ("gunAFill.AttenuationRadius", num(3500.0)),
        ("gunAFill.CastShadows", flag(False)),
        # Space Rig: the mod is on, but the rig keeps the game's shadow filter.
        ("cvar r.Shadow.FilterMethod", {"equals": "0"}),
    ]
    out = [dict(value, line="TEST %s = " % key) for key, value in checks]
    out.append({"line": "TEST find %sUI/Umbra_Hub.Umbra_Hub_C -> " % MOD, "contains": "Umbra_Hub_C"})
    return out


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python umbra_test.py <out.json>")
    os.makedirs(OUT, exist_ok=True)
    assets = test_assets() + [{"kind": "worldtest", "steps": steps()}]
    with open(sys.argv[1], "w", encoding="utf-8") as out:
        json.dump({"assets": assets}, out, indent=1)
    with open(sys.argv[1] + ".expect.json", "w", encoding="utf-8") as out:
        json.dump(expectations(), out, indent=1)
    print("wrote %s (%d assets), captures in %s" % (sys.argv[1], len(assets), OUT))

if __name__ == "__main__":
    main()
