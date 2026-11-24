"""Writes the BPForge spec (JSON) for the Umbra mod: real shadows with soft edges from headlamps and flares.

Usage: python umbra_spec.py <out.json>   (normally run by drg-toolkit: drg build umbra)
The spec is the source of the mod's Blueprints. Edit here, then run drg build umbra (check) or
drg build umbra --save (writes the assets). Name, author and version come from drgmod.toml.

How it fits the other mods (read from their cooked Blueprints, see README "Other mods"):
- Pretty Flashlights adds its own headlamp spot lights and never turns their shadows on by itself.
- Advanced Darkness changes light colour, range and fog, and leaves shadow settings alone.
- Mod Hub hides terrain shadows by default.
So this mod only sets shadow properties, on a fixed number of lights, and nothing the others reset.
"""
import json
import math
import sys

from drgkit import mod as drgmod
from drgkit.bp import dsl, modhub, ui
from drgkit.bp.dsl import ref, t
from drgkit.bp.modhub import iface

MOD = "/Game/_Umbra/"

KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
KARR = "/Script/Engine.KismetArrayLibrary"
KSTR = "/Script/Engine.KismetStringLibrary"
KTXT = "/Script/Engine.KismetTextLibrary"
GS = "/Script/Engine.GameplayStatics"
ACTOR = "/Script/Engine.Actor"
PAWN = "/Script/Engine.Pawn"
SPOT = "/Script/Engine.SpotLightComponent"
LOCAL_LIGHT = "/Script/Engine.LocalLightComponent"
LIGHT_BASE = "/Script/Engine.LightComponentBase"
POINT = "/Script/Engine.PointLightComponent"
MESH = "/Script/Engine.MeshComponent"
PRIMITIVE = "/Script/Engine.PrimitiveComponent"
SCENE = "/Script/Engine.SceneComponent"
UMG = "/Script/UMG."
LIGHT = "/Script/Engine.LightComponent"
TIMELINE = "/Script/Engine.TimelineComponent"
PARTICLES = "/Script/Engine.ParticleSystemComponent"
FLARE = "/Script/FSD.Flare"
GUN_FLARE = "/Script/FSD.FlareGunProjectile"
PLAYER = "/Script/FSD.PlayerCharacter"
TERRAIN = "/Script/FSDEngine.DeepCSGSection"

SETTINGS = MOD + "Umbra_Settings"
SETTINGS_C = SETTINGS + ".Umbra_Settings_C"
MODBP = MOD + "Umbra_Mod"
MOD_C = MODBP + ".Umbra_Mod_C"
PAGE = MOD + "UI/Umbra_Page"
PAGE_C = PAGE + ".Umbra_Page_C"
HUBMOD = MOD + "UI/Umbra_Hub"
HUBMOD_C = HUBMOD + ".Umbra_Hub_C"

SAVE_SLOT = "Umbra"
# From drgmod.toml. MOD_NAME is shown in Mod Hub; internal paths and the save slot keep "Umbra".
_MOD = drgmod.current()
MOD_NAME, MOD_AUTHOR, MOD_VERSION = _MOD.name, _MOD.author, _MOD.full_version

# A spot light on a player is the headlamp beam when it reaches at least this far and is at most this wide.
# Matches the game's own headlamp and the Pretty Flashlights one, also after Advanced Darkness shortens them;
# leaves out the wide fill lights.
BEAM_MIN_RADIUS = 700.0
BEAM_MAX_CONE = 45.0
LAMP_SOURCE_RADIUS = 6.0     # cm at Penumbra = 1
FLARE_SOURCE_RADIUS = 10.0   # cm at Penumbra = 1
# Shadow fade: the engine fades a light's shadow out when its shadow map would be small on screen
# (r.Shadow.FadeResolution, r.Shadow.MinResolution; ShadowSetup.cpp, CalculateShadowFadeAlpha), and does
# not render it at all once faded. Shadow resolution = TexelsPerPixelPointlight * screen scale * radius /
# distance, so the two console variables are set from the wanted distance. Engine defaults: 64 and 32.
TEXELS_PER_PIXEL_POINT = 1.27324
SHADOW_FADE_END = 1.5        # gone at 1.5 x Shadow distance
FADE_RES_GAME, MIN_RES_GAME = 64, 32
FILL_MIN_RADIUS = 500.0      # cm; a flare's point light at least this big is its fill light
FILL_CUT = 0.65              # share of the fill radius removed at ShadowStrength = 1
STORED_MIN = 50.0            # see g_apply_flare: values from here up are a stored radius
# Values of the flare's spot lights in the game (ITM_BaseFlare and PRJ_FlareGun_Projectile01; the subclasses only
# change radius, intensity and colour), and what an upgraded flare gets instead.
FLARE_BIAS_GAME, FLARE_BIAS_UPGRADED = 0.25, 0.8
FLARE_SLOPE_GAME, FLARE_SLOPE_UPGRADED = 0.5, 1.0
# The three spot lights of a flare point 120 degrees apart, in one ring around the flare's long axis.
# Game cones (inner 40, outer 65) leave dark wedges between them and at both ends of the flare; upgraded cones
# are as wide as the engine allows, with a long soft edge, so the ring is even and the ends fade out gently.
FLARE_INNER_GAME, FLARE_INNER_UPGRADED = 40.0, 50.0
FLARE_OUTER_GAME, FLARE_OUTER_UPGRADED = 65.0, 80.0
GUN_BIAS_GAME = 0.5          # ShadowBias of the flare gun flare's spot lights in the game (engine default)
# A flare gun flare sticks in a wall or ceiling nose first; its ring of spot lights then lies flat along the
# wall, so the shadowed light only grazes the wall. Upgraded, the ring is tilted back out of the wall by this.
GUN_TILT = 30.0
GUN_SPOTS_GAME = {"Shadow_1": (0.0, 90.0, 90.0), "Shadow_2": (60.0, -90.0, -90.0), "Shadow_3": (-60.0, -90.0, -90.0)}
STORED_COLOUR_MAX = 100.0    # see g_colour_light: LightFunctionScale below this holds a stored colour
# The shadow light of a chosen flare (the flare's own fill point light, see g_apply_flare).
SHADOW_FALLOFF = 4.0         # falloff exponent at Range (the game's fill: 8 at 20 m; about the same shape)
FILL_FALLOFF_GAME = 8.0      # engine default for point lights; the flare fills do not change it
SHADOW_RESOLUTION_SCALE = 0.5  # half-size shadow maps: a quarter of the texels, softer edges
SHADOW_BIAS, SHADOW_SLOPE_BIAS = 0.5, 0.5
SHADOW_LIGHT_LIFT = 15.0     # cm above the flare
PLACE_TOLERANCE = 1.0        # cm; the shadow light moves only when it is further off (see g_place_shadow_light)
MOVING_SPEED = 30.0          # cm/s; a flare faster than this (flying, rolling) gets its shadow light at its centre
# Flare gun flare: its light timeline (Light_Anim) plays only when a cheat manager exists (PRJ_FlareGun_Projectile01,
# ExecuteUbergraph 1059-1882), so not in a normal game: the lights keep their own intensities (GUN_POINT_BASE,
# GUN_SPOT_BASE) while it burns. With a cheat manager the game copies those into LightIntensity_Point and
# LightIntensity_Spot and plays the timeline; while it is below this position Watch applies the mod's values again.
GUN_ANIM_FRESH = 0.5
HAND_FILL_Z, GUN_FILL_X = 20.0, 3.23457  # where the game puts the fill light on the flare
# Intensity variables of the game's flares (ITM_* BaseIntensity = the fill's template intensity per class;
# PRJ_FlareGun_Projectile01 LightIntensity_Point / LightIntensity_Spot).
HAND_BASE = {"Small_Engineer": 12.0, "Small_Driller": 5.0, "Flare_Small": 10.0, "default": 4.0}
HAND_SPOT_SHARE = 1.6        # hand flare: spots = 1.6 x fill
HAND_TOTAL = 1.0 + HAND_SPOT_SHARE
GUN_POINT_BASE, GUN_SPOT_BASE = 3.5, 35.0
GUN_SPOT_VAR_GAME = 50.0     # the game's own LightIntensity_Spot (LightIntensity_Point is GUN_POINT_BASE)
# When the flare goes out the game sets Light_Anim to 86 and so writes into the lights: point = LightIntensity_Point *
# NewTrack_0(86), spots = LightIntensity_Spot * NewTrack_0(86) * ShadowMultiplier(86). Curve keys from the game
# asset: NewTrack_0 (85.840, 0.42769) to (90, 0), cubic; ShadowMultiplier 1.005125 from 1.52 on. In game the point
# light went to 12.302254 with the variable at 28.875 (2026-11-24). The mod sets the variables so that this write
# repeats what the lights already have: the light does not jump when the flare goes out.
GUN_END_POINT = 12.302254 / 28.875
GUN_END_SPOT = GUN_END_POINT * 1.005125
# Hue of each class: the colour the game gives the glowing flare model of that class
# (M_Flare_Glow_<Class>_inst, DynamicTint2), scaled so the brightest channel is 1. Scout also covers the flare gun.
# Engineer: the game's hue is pure red, which washed the scene red; the mod uses it 30% toward white.
# Light colour = lerp(white, hue, Class colour): pastel at the default. The light of the game's flares has
# other colours (Scout orange, Engineer and Driller blue, Gunner green); Class colour 0 keeps those.
CLASS_HUE = {
    "Driller": "(R=1.0,G=0.855,B=0.0,A=1.0)",
    "Engineer": "(R=1.0,G=0.3,B=0.3,A=1.0)",  # the game's pure red, 30% toward white (player feedback: too red)
    "Gunner": "(R=0.0,G=1.0,B=0.11,A=1.0)",
    "Scout": "(R=0.0,G=0.52,B=1.0,A=1.0)",
}
TERRAIN_EVERY = 15           # seconds between terrain passes
TERRAIN_AT = 7               # first pass, after Mod Hub's own pass at 5 s

# End of a flare's light. The game ends it with a short straight ramp to zero (hand flare: native code,
# CRV_Flare_Brightness; flare gun: its Light_Anim timeline) and hides the lights 2 s later. With the mod's
# bright all-round shadow light that looks like the light is switched off. For the last seconds the mod sets
# the intensity itself, every frame after the game's own light update: from the level the light had when the
# fade started down to zero along (1 - u)^3, an even fade to the eye (lightness is about the cube root of
# luminance). The Tick runs only while a light fades.
FADE_SLOTS = 8               # flares that can fade at once; more keep the game's own ending
HAND_FADE_LEAD = 4.0         # s before a hand flare's light ends (Duration after it is thrown)
HAND_FADE_AFTER = 1.8        # s after it ends; the game hides the lights 2 s after the end
GUN_TIMELINE_END = 90.0      # length of the flare gun flare's light timeline (Light_Anim)
# Flare gun flare: when it goes out the game sets its light timeline to 86 without playing it (the light jumps to
# the track's value there) and hides the lights up to 4 s later, right before ParticleSystem.SetActive(false)
# (PRJ_FlareGun_Projectile01, ExecuteUbergraph 131-267). The mod binds that component's OnComponentDeactivated
# (BindGunEnd) and then shows the lights again for GUN_TAIL seconds while they fade (GunTail): no polling.
# The jump at 86 changes nothing, see GUN_END_POINT, so the light is steady until the tail starts.
GUN_TAIL = 3.0
FADE_HOLD = 1.0              # s the mod keeps a faded light at zero, until the game has hidden it
FADE_POWER = 3.0
TICK_GROUP = "TG_PostUpdateWork"  # after actor, timeline, timer and subsystem ticks: the mod's value wins

# Settings. The page shows Enabled, the quality level and the class colour, and below them a list of detailed
# settings that is closed until the player opens it. A level writes all the detailed settings (ApplyLevel, from
# LEVELS) whenever it is chosen and when the settings are loaded. Changing a detailed setting by hand sets the
# level to Custom (the slider's right end): ApplyLevel then keeps the player's values. So a save from 0.2.0 or
# 0.3.0 (level 0 to 3) gets its level's values; the save slot and the variable names stay.
LEVEL_NAMES = ["Low", "Medium", "High", "Ultra"]
CUSTOM = len(LEVEL_NAMES)    # Level value of Custom
PRESET_NAMES = LEVEL_NAMES + ["Custom"]
DEFAULT_LEVEL = 1
ALL_FLARES = 99.0            # "every flare" as a count
CUT_ALL = 1.0e9              # cm; a distance cut that lets every flare cast (ApplyFlares)
# Value of each setting at Low, Medium, High, Ultra.
# OwnLamp, TeamLamps: headlamp shadows (own, other dwarves'). SoftShadows: PCSS penumbra (r.Shadow.FilterMethod).
# TerrainShadows: cave walls cast shadows (Mod Hub hides them by default). LightShafts: shadow flares also shadow
# the volumetric fog. ShadowDistance: metres, flare shadows fade out beyond it (ApplyShadowFade).
# FlareRange, GunFlareRange: metres the shadow light of a flare reaches. HandFlares, GunFlares: how many flares of
# each kind, the nearest to the camera, cast shadows (the others light the same, without shadows).
# Quality: shadow map size, 0 game setting, 1 = 1024, 2 = 2048, 3 = 4096.
LEVELS = {
    "OwnLamp": (True, True, True, True),
    "TeamLamps": (False, True, True, True),
    "SoftShadows": (False, True, True, True),
    "TerrainShadows": (True, True, True, True),
    "LightShafts": (False, False, False, True),
    "ShadowDistance": (15.0, 20.0, 25.0, 40.0),
    "FlareRange": (10.0, 12.0, 14.0, 16.0),
    "HandFlares": (2.0, 4.0, 6.0, ALL_FLARES),
    "GunFlareRange": (14.0, 14.0, 16.0, 20.0),
    "GunFlares": (0.0, 1.0, 2.0, 4.0),
    # The game's own shadow quality option sets the map size. A size set by the mod would stay until the game
    # restarts (nothing restores the console variable when the level goes down again), so no level sets one.
    "Quality": (0.0, 0.0, 0.0, 0.0),
}
# name, label, hint, default
CHECKS = [
    ("Enabled", "Enabled", "Off returns lights to the game's own shadow settings.", True),
]
# name, label, hint, min, max, step, default
SLIDERS = [
    ("Level", "Shadow quality", "Low gives the most FPS. Higher levels add team headlamp shadows, soft edges, more and "
              "longer flare shadows; Ultra also shadows the fog. Custom keeps your own detailed settings.",
     0.0, float(CUSTOM), 1.0, float(DEFAULT_LEVEL)),
]
# Kept in the save, set by the level: (name, type, default = the default level's value).
LEVEL_SETTINGS = [(name, "bool" if isinstance(values[0], bool) else "float", values[DEFAULT_LEVEL])
                  for name, values in LEVELS.items()]


class Detail:
    """A detailed setting on the page: a check box when low is None, else a slider. all_at: the slider's top stop
    means every flare (ALL_FLARES is stored), shown as ALL. look: not part of a level (default given here); Shadow
    quality never changes it, and changing it keeps the level."""

    def __init__(self, name, label, hint, low=None, high=None, step=None, digits=0, all_at=None, look=False,
                 default=None):
        self.name, self.label, self.hint = name, label, hint
        self.low, self.high, self.step, self.digits, self.all_at = low, high, step, digits, all_at
        self.check = low is None
        self.look = look
        self.default = default if look else LEVELS[name][DEFAULT_LEVEL]


# The list under DETAILED SETTINGS, in two groups. QUALITY: every level setting but Quality (a shadow map size set by
# the mod would stay until the game restarts, see LEVELS); a change sets the level to Custom. LOOK: the colour and
# brightness of flares, how dark the shadows are, the headlamp's soft edge.
DETAILS = [
    Detail("OwnLamp", "Own headlamp", "Your headlamp casts shadows."),
    Detail("TeamLamps", "Team headlamps", "Other dwarves' headlamps cast shadows."),
    Detail("SoftShadows", "Soft edges", "Shadow edges are sharp at the contact and softer with distance."),
    Detail("TerrainShadows", "Cave wall shadows", "Cave walls cast shadows. Most shadows need it."),
    Detail("LightShafts", "Shadows in fog", "Shadow flares also shadow the fog. Costs the most GPU time."),
    Detail("ShadowDistance", "Shadow distance", "Metres. Flare shadows fade out beyond it. Lower gives more FPS.",
           10.0, 60.0, 5.0),
    Detail("HandFlares", "Hand flares", "How many hand flares cast shadows: the nearest to you. The others still light "
           "the cave. Fewer gives more FPS in big fights.", 0.0, 11.0, 1.0, all_at=11.0),
    Detail("FlareRange", "Hand flare range", "Metres. How far the shadow light of a hand flare reaches.",
           8.0, 20.0, 1.0),
    Detail("GunFlares", "Flare gun flares", "How many flare gun flares cast shadows: the nearest to you.",
           0.0, 7.0, 1.0, all_at=7.0),
    Detail("GunFlareRange", "Flare gun range", "Metres. How far the shadow light of a flare gun flare reaches.",
           10.0, 30.0, 1.0),
    Detail("FlareColour", "Class colour", "Hand flares take the colour of the dwarf's class. 0 game colours, 1 full "
           "colour, up to 2 brighter colour. The flare gun keeps its own light.", 0.0, 2.0, 0.05, digits=2,
           look=True, default=1.0),
    Detail("FlareBrightness", "Flare brightness", "Flare light compared with the game. Coloured light is raised to the "
           "same brightness.", 0.5, 2.0, 0.05, digits=2, look=True, default=1.0),
    Detail("ShadowStrength", "Shadow strength", "Share of a shadow flare's light that casts shadows. Lower lifts the "
           "shadows.", 0.4, 1.0, 0.05, digits=2, look=True, default=0.75),
    Detail("Penumbra", "Penumbra size", "Size of the headlamp light source. Bigger gives wider soft edges.",
           0.0, 3.0, 0.1, digits=1, look=True, default=1.0),
]
# Kept in the save, not part of a level: (name, default). All floats.
LOOK_SETTINGS = [(d.name, d.default) for d in DETAILS if d.look]
for _d in DETAILS:  # every level's value must fit its control
    if _d.look:
        assert _d.name not in LEVELS and _d.low <= _d.default <= _d.high, _d.name
        continue
    for _v in LEVELS[_d.name]:
        assert _d.check == isinstance(_v, bool), _d.name
        assert _d.check or _d.low <= _v <= _d.high or (_d.all_at is not None and _v >= ALL_FLARES), (_d.name, _v)


class Graph(dsl.Graph):
    """drgkit Graph as Umbra uses it: None pin values are written as null, setting() reads Umbra_Settings."""
    keep_none = True
    settings_class = SETTINGS_C


# --------------------------------------------------------------------------- settings object

def settings_asset():
    variables = [t(name, "bool", default=str(default).lower()) for name, _, _, default in CHECKS]
    variables += [t(name, "float", default=str(default)) for name, _, _, _, _, _, default in SLIDERS]
    variables += [t(name, typ, default=str(default).lower() if typ == "bool" else str(default))
                  for name, typ, default in LEVEL_SETTINGS]
    variables += [t(name, "float", default=str(default)) for name, default in LOOK_SETTINGS]
    return {"kind": "blueprint", "path": SETTINGS, "parent": "/Script/Engine.SaveGame", "variables": variables}


# --------------------------------------------------------------------------- mod actor

def g_load_settings():
    return modhub.g_load_settings(SETTINGS_C, SAVE_SLOT, then=[("level", "ApplyLevel")], check_exists=False)


def level_index(g, prefix, level_pin, names=LEVEL_NAMES):
    """Output pins: is the level (a float, rounded and clamped to names) each of names but the last? The last name is
    none of them. Also makes prefix + "Round" (the rounded level, not clamped)."""
    g.call(prefix + "Round", KML + ":Round", A=ref(level_pin))
    g.call(prefix + "Int", KML + ":Clamp", Value=ref(prefix + "Round.ReturnValue"), Min="0", Max=str(len(names) - 1))
    level = prefix + "Int.ReturnValue"
    picks = []
    for i in range(len(names) - 1):
        g.call("%sIs%d" % (prefix, i), KML + ":EqualEqual_IntInt", A=ref(level), B=str(i))
        picks.append("%sIs%d.ReturnValue" % (prefix, i))
    return level, picks


def g_apply_level():
    """Writes the settings of the chosen level (LEVELS) into Settings. Does not apply them (ApplySettings does).
    Custom (or above): writes nothing, the player's own values stay."""
    g = Graph()
    settings = g.get("getSettings", "Settings")
    g.call("valid", KSL + ":IsValid", Object=ref(settings))
    level, picks = level_index(g, "lv", g.get("getLevel", "Level", SETTINGS_C, settings))
    g.call("isPreset", KML + ":Less_IntInt", A=ref("lvRound.ReturnValue"), B=str(CUSTOM))
    g.call("doWrite", KML + ":BooleanAND", A=ref("valid.ReturnValue"), B=ref("isPreset.ReturnValue"))
    g.branch("br", "doWrite.ReturnValue")
    chain = ["entry", "br"]
    for name, values in LEVELS.items():
        if isinstance(values[0], bool):
            # True from some level up: level >= the first level where it is on.
            first = values.index(True) if True in values else len(values)
            assert all(values[i] == (i >= first) for i in range(len(values))), name
            g.call("on" + name, KML + ":GreaterEqual_IntInt", A=ref(level), B=str(first))
            value = "on%s.ReturnValue" % name
        else:
            # Nested picks: Low ? v0 : (Medium ? v1 : (High ? v2 : v3)).
            value = str(values[-1])
            for i in reversed(range(len(values) - 1)):
                node = "%sPick%d" % (name, i)
                g.call(node, KML + ":SelectFloat", A=str(values[i]), bPickA=ref(picks[i]),
                       B=ref(value) if value.endswith(".ReturnValue") else value)
                value = node + ".ReturnValue"
        g.set("set" + name, name, SETTINGS_C, settings, value)
        chain.append("set" + name)
    g.flow(*chain)
    return g.data()


def g_save_settings():
    return modhub.g_save_settings(SAVE_SLOT, check_valid=False)


def g_apply_settings():
    g = Graph()
    g.call("cvars", "ApplyCvars")
    g.call("refresh", "Refresh")
    g.call("terrain", "ApplyTerrain")
    g.flow("entry", "cvars", "refresh", "terrain")
    return g.data()


def g_apply_cvars():
    """Shadow filter and, if asked, shadow map size. Console variables stay until the game restarts.

    Soft shadows (PCSS) only in missions: the filter is global, and on the Space Rig the sun's and the big
    lights' shadows get stripes (shadow acne) on floors and machines with it. The Space Rig gets the game's
    filter back, also after a mission.
    """
    g = Graph()
    g.call("softWanted", KML + ":BooleanAND", A=ref(g.setting("Enabled")), B=ref(g.setting("SoftShadows")))
    g.call("soft", KML + ":BooleanAND", A=ref("softWanted.ReturnValue"), B=ref(g.get("getActive", "ActiveInLevel")))
    g.branch("brSoft", "soft.ReturnValue")
    g.call("pcss", KSL + ":ExecuteConsoleCommand", Command="r.Shadow.FilterMethod 1")
    g.call("pcf", KSL + ":ExecuteConsoleCommand", Command="r.Shadow.FilterMethod 0")
    g.call("qRound", KML + ":Round", A=ref(g.setting("Quality")))
    g.call("qSet", KML + ":Greater_IntInt", A=ref("qRound.ReturnValue"), B="0")
    g.call("qOn", KML + ":BooleanAND", A=ref(g.setting("Enabled")), B=ref("qSet.ReturnValue"))
    g.branch("brRes", "qOn.ReturnValue")
    # 1 -> 1024, 2 -> 2048, 3 -> 4096
    g.call("qFloat", KML + ":Conv_IntToFloat", InInt=ref("qRound.ReturnValue"))
    g.call("pow", KML + ":MultiplyMultiply_FloatFloat", Base="2.0", Exp=ref("qFloat.ReturnValue"))
    g.call("size", KML + ":Multiply_FloatFloat", A="512.0", B=ref("pow.ReturnValue"))
    g.call("sizeInt", KML + ":Round", A=ref("size.ReturnValue"))
    g.call("sizeStr", KSTR + ":Conv_IntToString", InInt=ref("sizeInt.ReturnValue"))
    g.call("cmd", KSTR + ":Concat_StrStr", A="r.Shadow.MaxResolution ", B=ref("sizeStr.ReturnValue"))
    g.call("res", KSL + ":ExecuteConsoleCommand", Command=ref("cmd.ReturnValue"))
    g.flow("entry", "brSoft", "pcss", "brRes", "res", "fade")
    g.flow("brSoft.else", "pcf", "brRes")
    g.flow("brRes.else", "fade")
    g.call("fade", "ApplyShadowFade")
    return g.data()


def g_apply_shadow_fade():
    """r.Shadow.FadeResolution / MinResolution from Shadow distance, for a hand flare's shadow range.

    screen scale = (viewport width / 2) / tan(horizontal FOV / 2). With upscaling (DLSS) the engine uses the
    smaller render size, so shadows fade a little closer than set. Never below the engine defaults.
    Mod off, or on the Space Rig: the engine defaults.
    """
    g = Graph()
    g.call("pc", GS + ":GetPlayerController", PlayerIndex="0")
    g.call("pcValid", KSL + ":IsValid", Object=ref("pc.ReturnValue"))
    g.call("size", "/Script/Engine.PlayerController:GetViewportSize", target=ref("pc.ReturnValue"))
    g.call("width", KML + ":Conv_IntToFloat", InInt=ref("size.SizeX"))
    g.call("widthOk", KML + ":Greater_FloatFloat", A=ref("width.ReturnValue"), B="100.0")
    g.call("useWidth", KML + ":BooleanAND", A=ref("pcValid.ReturnValue"), B=ref("widthOk.ReturnValue"))
    g.call("w", KML + ":SelectFloat", A=ref("width.ReturnValue"), B="1920.0", bPickA=ref("useWidth.ReturnValue"))
    g.call("cam", GS + ":GetPlayerCameraManager", PlayerIndex="0")
    g.call("camValid", KSL + ":IsValid", Object=ref("cam.ReturnValue"))
    g.call("fovNow", "/Script/Engine.PlayerCameraManager:GetFOVAngle", target=ref("cam.ReturnValue"))
    g.call("fov", KML + ":SelectFloat", A=ref("fovNow.ReturnValue"), B="90.0", bPickA=ref("camValid.ReturnValue"))
    g.call("halfFov", KML + ":Multiply_FloatFloat", A=ref("fov.ReturnValue"), B="0.5")
    g.call("tan", KML + ":DegTan", A=ref("halfFov.ReturnValue"))
    g.call("halfW", KML + ":Multiply_FloatFloat", A=ref("w.ReturnValue"), B="0.5")
    g.call("scale", KML + ":Divide_FloatFloat", A=ref("halfW.ReturnValue"), B=ref("tan.ReturnValue"))
    # resolution at the fade start = texels per pixel * scale * radius / distance (radius and distance in m)
    g.call("ratio", KML + ":Divide_FloatFloat", A=ref(g.setting("FlareRange")), B=ref(g.setting("ShadowDistance")))
    g.call("res1", KML + ":Multiply_FloatFloat", A=ref("scale.ReturnValue"), B=ref("ratio.ReturnValue"))
    g.call("res", KML + ":Multiply_FloatFloat", A=ref("res1.ReturnValue"), B=str(TEXELS_PER_PIXEL_POINT))
    g.call("minRes", KML + ":Divide_FloatFloat", A=ref("res.ReturnValue"), B=str(SHADOW_FADE_END))
    g.call("fadeI", KML + ":Round", A=ref(g.call("fadeMax", KML + ":FMax", A=ref("res.ReturnValue"), B=str(FADE_RES_GAME)) + ".ReturnValue"))
    g.call("minI", KML + ":Round", A=ref(g.call("minMax", KML + ":FMax", A=ref("minRes.ReturnValue"), B=str(MIN_RES_GAME)) + ".ReturnValue"))
    # Only in missions with the mod on; the Space Rig keeps the engine defaults.
    g.call("fadeWanted", KML + ":BooleanAND", A=ref(g.setting("Enabled")), B=ref(g.get("getActive", "ActiveInLevel")))
    g.call("fadeOn", KML + ":SelectInt", A=ref("fadeI.ReturnValue"), B=str(FADE_RES_GAME), bPickA=ref("fadeWanted.ReturnValue"))
    g.call("minOn", KML + ":SelectInt", A=ref("minI.ReturnValue"), B=str(MIN_RES_GAME), bPickA=ref("fadeWanted.ReturnValue"))
    g.call("fadeStr", KSTR + ":Conv_IntToString", InInt=ref("fadeOn.ReturnValue"))
    g.call("minStr", KSTR + ":Conv_IntToString", InInt=ref("minOn.ReturnValue"))
    g.call("fadeCmd", KSTR + ":Concat_StrStr", A="r.Shadow.FadeResolution ", B=ref("fadeStr.ReturnValue"))
    g.call("minCmd", KSTR + ":Concat_StrStr", A="r.Shadow.MinResolution ", B=ref("minStr.ReturnValue"))
    g.call("setFade", KSL + ":ExecuteConsoleCommand", Command=ref("fadeCmd.ReturnValue"))
    g.call("setMin", KSL + ":ExecuteConsoleCommand", Command=ref("minCmd.ReturnValue"))
    g.flow("entry", "setFade", "setMin")  # GetViewportSize is const, so a pure node
    return g.data()


def g_refresh():
    """Runs once a second. Touches only player characters (4 at most), flares and, rarely, terrain sections."""
    g = Graph()
    g.branch("brActive", g.get("getActive", "ActiveInLevel"))
    g.call("tick", KML + ":Add_IntInt", A=ref(g.get("getTicks", "Ticks")), B="1")
    g.set("setTicks", "Ticks", value="tick.ReturnValue")
    g.node("seq", "seq", n=4)
    g.flow("entry", "brActive", "setTicks", "seq")
    g.call("isThree", KML + ":EqualEqual_IntInt", A=ref(g.get("getTicks3", "Ticks")), B="3")
    g.branch("brThree", "isThree.ReturnValue")
    g.call("fadeAgain", "ApplyShadowFade")
    g.flow("seq.then_3", "brThree", "fadeAgain")

    # 1. Headlamps of the player characters. Stateless: setters do nothing when the value is unchanged,
    #    so late joiners and respawns need no special handling.
    g.call("players", GS + ":GetAllActorsOfClass", ActorClass=PLAYER)
    element = g.loop("each", "players.OutActors")
    g.node("asPawn", "cast", **{"class": PAWN})
    g.link(element, "asPawn.Object")
    g.call("localPawn", GS + ":GetPlayerPawn", PlayerIndex="0")
    g.call("isLocal", KML + ":EqualEqual_ObjectObject", A=ref(element), B=ref("localPawn.ReturnValue"))
    g.call("applyPawn", "ApplyPawn", Pawn=ref("asPawn.$cast"), bLocal=ref("isLocal.ReturnValue"))
    g.flow("seq.then_0", "players", "each.Exec")
    g.flow("each.LoopBody", "asPawn", "applyPawn")

    # 2. Flares.
    g.call("flares", "ApplyFlares", FlareClass=FLARE, Range=ref(g.setting("FlareRange")), Count=ref(g.setting("HandFlares")))
    g.call("gunFlares", "ApplyFlares", FlareClass=GUN_FLARE, Range=ref(g.setting("GunFlareRange")),
           Count=ref(g.setting("GunFlares")))
    g.flow("seq.then_1", "flares", "gunFlares")

    # 3. Terrain sections: every TERRAIN_EVERY seconds.
    g.call("mod", KML + ":Percent_IntInt", A=ref(g.get("getTicks2", "Ticks")), B=str(TERRAIN_EVERY))
    g.call("isTime", KML + ":EqualEqual_IntInt", A=ref("mod.ReturnValue"), B=str(TERRAIN_AT))
    g.branch("brTerrain", "isTime.ReturnValue")
    g.call("terrain", "ApplyTerrain")
    g.flow("seq.then_2", "brTerrain", "terrain")
    return g.data()


def g_apply_pawn():
    """Headlamp beam of one player: shadows on or off. With shadows on, the dwarf's own meshes stop casting.

    The lamp sits inside the head and next to the weapon. If the dwarf's own meshes cast shadows, they block
    the beam. Pretty Flashlights does the same in its shadow mode.
    """
    g = Graph()
    pawn = "entry.Pawn"
    g.call("mine", KML + ":BooleanAND", A=ref("entry.bLocal"), B=ref(g.setting("OwnLamp")))
    g.call("notLocal", KML + ":Not_PreBool", A=ref("entry.bLocal"))
    g.call("theirs", KML + ":BooleanAND", A=ref("notLocal.ReturnValue"), B=ref(g.setting("TeamLamps")))
    g.call("either", KML + ":BooleanOR", A=ref("mine.ReturnValue"), B=ref("theirs.ReturnValue"))
    g.call("want", KML + ":BooleanAND", A=ref(g.setting("Enabled")), B=ref("either.ReturnValue"))
    want = "want.ReturnValue"

    g.call("spots", ACTOR + ":K2_GetComponentsByClass", ComponentClass=SPOT, target=ref(pawn))
    g.set("keepSpots", "Lights", value="spots.ReturnValue")
    light = g.loop("eachLight", g.get("getLights", "Lights"))
    g.call("farEnough", KML + ":GreaterEqual_FloatFloat", B=str(BEAM_MIN_RADIUS),
           A=ref(g.get("radius", "AttenuationRadius", LOCAL_LIGHT, light)))
    g.call("narrow", KML + ":LessEqual_FloatFloat", B=str(BEAM_MAX_CONE),
           A=ref(g.get("cone", "OuterConeAngle", SPOT, light)))
    g.call("isBeam", KML + ":BooleanAND", A=ref("farEnough.ReturnValue"), B=ref("narrow.ReturnValue"))
    g.branch("brBeam", "isBeam.ReturnValue")
    g.call("cast", LIGHT_BASE + ":SetCastShadows", target=ref(light), bNewValue=ref(want))
    g.branch("brSource", want)
    g.call("source", KML + ":Multiply_FloatFloat", A=str(LAMP_SOURCE_RADIUS), B=ref(g.setting("Penumbra")))
    g.call("setSource", POINT + ":SetSourceRadius", target=ref(light), bNewValue=ref("source.ReturnValue"))
    g.flow("entry", "keepSpots", "eachLight.Exec")
    g.flow("eachLight.LoopBody", "brBeam", "cast", "brSource", "setSource")

    # The dwarf's own meshes, and the meshes of what it holds.
    g.branch("brMeshes", want)
    g.call("meshes", ACTOR + ":K2_GetComponentsByClass", ComponentClass=MESH, target=ref(pawn))
    g.set("keepMeshes", "Meshes", value="meshes.ReturnValue")
    mesh = g.loop("eachMesh", g.get("getMeshes", "Meshes"))
    g.call("bodyOff", PRIMITIVE + ":SetCastShadow", target=ref(mesh), NewCastShadow="false")
    g.call("attached", ACTOR + ":GetAttachedActors", target=ref(pawn))
    g.set("keepActors", "Actors", value="attached.OutActors")
    item = g.loop("eachItem", g.get("getActors", "Actors"))
    g.call("itemMeshes", ACTOR + ":K2_GetComponentsByClass", ComponentClass=MESH, target=ref(item))
    g.set("keepItemMeshes", "Meshes", value="itemMeshes.ReturnValue")
    item_mesh = g.loop("eachItemMesh", g.get("getItemMeshes", "Meshes"))
    g.call("itemOff", PRIMITIVE + ":SetCastShadow", target=ref(item_mesh), NewCastShadow="false")
    g.flow("eachLight.Completed", "brMeshes", "keepMeshes", "eachMesh.Exec")
    g.flow("eachMesh.LoopBody", "bodyOff")
    g.flow("eachMesh.Completed", "keepActors", "eachItem.Exec")
    g.flow("eachItem.LoopBody", "keepItemMeshes", "eachItemMesh.Exec")
    g.flow("eachItemMesh.LoopBody", "itemOff")
    return g.data()


def g_is_lit():
    """Is this flare burning? The game's own flag, IsFlareOn (replicated, so clients have it too): set when the
    flare ignites, cleared when it goes out. A hand flare's light ends then; a flare gun flare keeps a last light
    for up to 4 s and then hides its lights (see GUN_TAIL). A burnt-out flare stays in the level
    until the mission ends, so a long mission holds hundreds of them, and none needs the mod. Any other actor
    counts as burning."""
    g = Graph()
    hand = g.cast("asHand", FLARE, "entry.Flare")
    g.set("handOn", "LitNow", value=g.get("handFlag", "IsFlareOn", FLARE, hand))
    gun = g.cast("asGun", GUN_FLARE, "entry.Flare")
    g.set("gunOn", "LitNow", value=g.get("gunFlag", "IsFlareOn", GUN_FLARE, gun))
    g.set("other", "LitNow", default="true")
    g.link(g.get("getLit", "LitNow"), "result.bLit")
    g.flow("entry", "asHand", "handOn", "result")
    g.flow("asHand.CastFailed", "asGun", "gunOn", "result")
    g.flow("asGun.CastFailed", "other", "result")
    return g.data()


def g_apply_flares():
    """Every burning flare of one kind gets the mod's light; only the Count flares nearest to the camera cast shadows.

    Burnt-out flares are skipped (IsLit): they also take no shadow from a burning one. The distances of the burning
    flares go into Dists; the cut is the Count-th smallest of them (Count passes of a minimum search over a copy,
    about Count x N steps), and a flare casts when its distance is at most the cut. That is the same choice as
    "fewer than Count flares are closer", without comparing each flare with each other one: a long mission has
    hundreds of flares, and that comparison cost 15 to 20 ms once a second at 200 flares (2026-11-23 capture).
    Count ALL_FLARES or more, no camera, or no more burning flares than Count: every one casts. Count 0: none.
    Each shadow light costs a shadow map that every moving thing in its reach (bugs) is drawn into each frame,
    so in a fight the count, not the distance fade (ApplyShadowFade), is what keeps the cost down.
    """
    g = Graph()
    g.call("all", GS + ":GetAllActorsOfClass", ActorClass=ref("entry.FlareClass"))
    g.set("keep", "Actors", value="all.OutActors")
    g.call("clearLit", KARR + ":Array_Clear", TargetArray=ref(g.get("lit0", "Lit")))
    g.call("clearDists", KARR + ":Array_Clear", TargetArray=ref(g.get("dists0", "Dists")))
    g.call("cam", GS + ":GetPlayerCameraManager", PlayerIndex="0")
    g.call("camValid", KSL + ":IsValid", Object=ref("cam.ReturnValue"))
    g.branch("brCam", "camValid.ReturnValue")
    g.set("setCam", "CamAt", value=g.call("camAt", "/Script/Engine.PlayerCameraManager:GetCameraLocation",
                                          target=ref("cam.ReturnValue")) + ".ReturnValue")
    g.call("noCam", KML + ":Not_PreBool", A=ref("camValid.ReturnValue"))
    g.call("countAll", KML + ":GreaterEqual_FloatFloat", A=ref("entry.Count"), B=str(ALL_FLARES))
    g.call("castAll", KML + ":BooleanOR", A=ref("noCam.ReturnValue"), B=ref("countAll.ReturnValue"))
    g.set("keepAll", "CastAll", value="castAll.ReturnValue")
    g.flow("entry", "all", "keep", "clearLit", "clearDists", "keepAll", "brCam", "setCam", "each.Exec")
    g.flow("brCam.else", "each.Exec")

    # 1. The burning flares, and their distances to the camera in the same order.
    flare = g.loop("each", g.get("getActors", "Actors"))
    g.call("lit", "IsLit", Flare=ref(flare))
    g.branch("brLit", "lit.bLit")
    g.call("addLit", KARR + ":Array_Add", TargetArray=ref(g.get("lit1", "Lit")), NewItem=ref(flare))
    g.call("dist", KML + ":VSize", A=ref(g.call("off", KML + ":Subtract_VectorVector", B=ref(g.get("getCam", "CamAt")),
                                                 A=ref(g.call("at", ACTOR + ":K2_GetActorLocation", target=ref(flare)) + ".ReturnValue"))
                                          + ".ReturnValue"))
    g.call("addDist", KARR + ":Array_Add", TargetArray=ref(g.get("dists1", "Dists")), NewItem=ref("dist.ReturnValue"))
    g.flow("each.LoopBody", "lit", "brLit", "addLit", "addDist")

    # 2. The cut: the Count-th smallest distance. Count is a whole number kept as a float (2, 4, 6).
    g.call("k", KML + ":FCeil", A=ref("entry.Count"))
    g.call("nLit", KARR + ":Array_Length", TargetArray=ref(g.get("lit2", "Lit")))
    g.call("more", KML + ":Greater_IntInt", A=ref("nLit.ReturnValue"), B=ref("k.ReturnValue"))
    g.call("notAll", KML + ":Not_PreBool", A=ref(g.get("getAll", "CastAll")))
    g.call("needCut", KML + ":BooleanAND", A=ref("notAll.ReturnValue"), B=ref("more.ReturnValue"))
    g.branch("brCut", "needCut.ReturnValue")
    g.set("cutAll", "Cut", default=str(CUT_ALL))
    g.set("copy", "Nearest", value=g.get("dists2", "Dists"))
    g.set("cutNone", "Cut", default="-1.0")  # Count 0: the passes below do not run, and no flare casts
    g.for_range("pass", "1", ref("k.ReturnValue"))
    g.set("minAt0", "MinAt", default="0")
    g.set("minDist0", "MinDist", value=g.call("first", KARR + ":Array_Get", TargetArray=ref(g.get("nearest0", "Nearest")),
                                              Index="0") + ".Item")
    near = g.loop("eachNear", g.get("nearest1", "Nearest"))
    g.call("smaller", KML + ":Less_FloatFloat", A=ref(near), B=ref(g.get("getMin", "MinDist")))
    g.branch("brSmaller", "smaller.ReturnValue")
    g.set("setMinDist", "MinDist", value=near)
    g.set("setMinAt", "MinAt", value="eachNear.Array Index")
    g.set("setCut", "Cut", value=g.get("getMin2", "MinDist"))
    g.call("drop", KARR + ":Array_Remove", TargetArray=ref(g.get("nearest2", "Nearest")),
           IndexToRemove=ref(g.get("getMinAt", "MinAt")))
    g.flow("each.Completed", "brCut", "copy", "cutNone", "pass.execute")
    g.flow("pass.LoopBody", "minAt0", "minDist0", "eachNear.Exec")
    g.flow("eachNear.LoopBody", "brSmaller", "setMinDist", "setMinAt")
    g.flow("eachNear.Completed", "setCut", "drop")
    g.flow("brCut.else", "cutAll", "eachLit.Exec")
    g.flow("pass.Completed", "eachLit.Exec")

    # 3. The light of each burning flare.
    lit_flare = g.loop("eachLit", g.get("lit3", "Lit"))
    g.call("itsDist", KARR + ":Array_Get", TargetArray=ref(g.get("dists3", "Dists")), Index=ref("eachLit.Array Index"))
    g.call("inCut", KML + ":LessEqual_FloatFloat", A=ref("itsDist.Item"), B=ref(g.get("getCut", "Cut")))
    g.call("apply", "ApplyFlare", Flare=ref(lit_flare), bUpgrade=ref(g.setting("Enabled")), bCast=ref("inCut.ReturnValue"),
           Range=ref("entry.Range"))
    g.call("bindEnd", "BindGunEnd", Flare=ref(lit_flare))
    g.flow("eachLit.LoopBody", "apply", "bindEnd")
    return g.data()


def gun_spot_tilted(pitch, yaw):
    """Rotation of a flare gun spot light after tilting the ring GUN_TILT degrees back (towards -X, out of the wall)."""
    p, y, b = math.radians(pitch), math.radians(yaw), math.radians(GUN_TILT)
    d = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))
    n = (-math.sin(b), math.cos(b) * d[1], math.cos(b) * d[2])  # the game's ring is the YZ plane (d[0] = 0)
    return round(math.degrees(math.asin(n[2])), 3), round(math.degrees(math.atan2(n[1], n[0])), 3)


def g_watch():
    """Runs ten times a second: new flares, and flares the game has just reset, get the mod's light at once.
    Hand flares whose light is about to end start their fade-out (flare gun flares: GunTail, from an event)."""
    g = Graph()
    g.call("on", KML + ":BooleanAND", A=ref(g.get("getActive", "ActiveInLevel")), B=ref(g.setting("Enabled")))
    g.branch("br", "on.ReturnValue")
    g.call("hand", "WatchFlares", FlareClass=FLARE, Range=ref(g.setting("FlareRange")), Count=ref(g.setting("HandFlares")),
           bGun="false")
    g.call("gun", "WatchFlares", FlareClass=GUN_FLARE, Range=ref(g.setting("GunFlareRange")),
           Count=ref(g.setting("GunFlares")), bGun="true")
    g.call("fadeHand", "StartFades", FlareClass=FLARE, bGun="false")
    g.flow("entry", "br", "hand", "gun", "fadeHand")
    # Mod off: the game drives the lights of fading flares again.
    g.branch("brFading", g.get("getFading", "Fading"))
    g.call("stop", "StopFades")
    g.flow("br.else", "brFading", "stop")
    return g.data()


def is_mod_light(g, node_id, light):
    """Output pin: does this light belong to the mod (fill or spot, reaching Range)? The flare's small glow
    lights (75 to 250 cm) do not; see g_watch_flares."""
    g.call(node_id, KML + ":GreaterEqual_FloatFloat", A=ref(g.get(node_id + "Radius", "AttenuationRadius", LOCAL_LIGHT, light)),
           B="290.0")
    return node_id + ".ReturnValue"


def g_start_fades():
    """Hand flares whose light is about to end get a fade slot. Each of the mod's lights keeps its present level, the
    start of its fade, in IESBrightnessScale: a property used only with an IES light profile (flare lights have
    none). Burnt-out flares are skipped (IsLit): a hand flare's fade starts while it still burns.
    Flare gun flares do not come here: GunTail fades them from an event."""
    g = Graph()
    g.call("all", GS + ":GetAllActorsOfClass", ActorClass=ref("entry.FlareClass"))
    g.set("keep", "FadeActors", value="all.OutActors")
    flare = g.loop("each", g.get("getActors", "FadeActors"))
    g.call("lit", "IsLit", Flare=ref(flare))
    g.branch("brLit", "lit.bLit")
    g.call("due", "FlareDue", Flare=ref(flare), bGun=ref("entry.bGun"))
    g.branch("brDue", g.get("getDue", "DueNow"))
    g.call("known", "IsFading", Flare=ref(flare))
    g.branch("brKnown", "known.bFading")
    add_fade_here(g, flare, g.get("getEnd", "DueEnd"))
    g.flow("entry", "all", "keep", "each.Exec")
    g.flow("each.LoopBody", "lit", "brLit", "due", "brDue", "known")
    g.flow("known", "brKnown")
    g.flow("brKnown.else", "keepLights", "eachLight.Exec")
    return g.data()


def add_fade_here(g, flare, end_pin, show=False):
    """Nodes that store the level of each of the mod's lights of a flare and give the flare a fade slot ending at
    end_pin. Exec in: "keepLights"; out: "add". show: the lights are made visible again first (GunTail)."""
    g.call("lights", ACTOR + ":K2_GetComponentsByClass", ComponentClass=POINT, target=ref(flare))
    g.set("keepLights", "FadePoints", value="lights.ReturnValue")
    light = g.loop("eachLight", g.get("getLights", "FadePoints"))
    g.branch("brMine", is_mod_light(g, "mine", light))
    g.call("store", KSL + ":SetFloatPropertyByName", Object=ref(light), PropertyName="IESBrightnessScale",
           Value=ref(g.get("level", "Intensity", LIGHT_BASE, light)))
    g.call("now", GS + ":GetTimeSeconds")
    g.call("add", "AddFade", Flare=ref(flare), Start=ref("now.ReturnValue"), End=ref(end_pin))
    if show:
        g.call("show", SCENE + ":SetVisibility", target=ref(light), bNewVisibility="true", bPropagateToChildren="false")
        g.flow("eachLight.LoopBody", "brMine", "show", "store")
    else:
        g.flow("eachLight.LoopBody", "brMine", "store")
    g.flow("eachLight.Completed", "add")


def g_flare_due():
    """Is the light of this hand flare about to end? Sets DueNow, and DueEnd: the game time the fade reaches zero.
    Its light runs for Duration from the throw (native code), so the fade starts HAND_FADE_LEAD before that and
    ends HAND_FADE_AFTER after it. bGun: unused (flare gun flares fade from an event, see GunTail)."""
    g = Graph()
    g.set("clear", "DueNow", default="false")
    g.call("now", GS + ":GetTimeSeconds")
    g.node("asFlare", "cast", **{"class": FLARE})
    g.link("entry.Flare", "asFlare.Object")
    g.call("age", ACTOR + ":GetGameTimeSinceCreation", target=ref("entry.Flare"))
    duration = g.get("duration", "Duration", FLARE, "asFlare.$cast")
    g.call("from", KML + ":Subtract_FloatFloat", A=ref(duration), B=str(HAND_FADE_LEAD))
    g.call("started", KML + ":GreaterEqual_FloatFloat", A=ref("age.ReturnValue"), B=ref("from.ReturnValue"))
    g.call("lit", KML + ":Less_FloatFloat", A=ref("age.ReturnValue"), B=ref(duration))
    g.call("handOk", KML + ":BooleanAND", A=ref("started.ReturnValue"), B=ref("lit.ReturnValue"))
    g.branch("brHand", "handOk.ReturnValue")
    g.call("handLeft", KML + ":Subtract_FloatFloat", A=ref(duration), B=ref("age.ReturnValue"))
    g.call("handEnd1", KML + ":Add_FloatFloat", A=ref("now.ReturnValue"), B=ref("handLeft.ReturnValue"))
    g.call("handEnd", KML + ":Add_FloatFloat", A=ref("handEnd1.ReturnValue"), B=str(HAND_FADE_AFTER))
    g.set("handSetEnd", "DueEnd", value="handEnd.ReturnValue")
    g.set("handDue", "DueNow", default="true")
    g.flow("entry", "clear", "asFlare", "brHand", "handSetEnd", "handDue")
    return g.data()


def g_bind_gun_end():
    """BindGunEnd: a burning flare gun flare reports when the game hides its lights. Its particle systems'
    OnComponentDeactivated goes to GunFlareOut (the game turns ParticleSystem off right after it hides the lights).
    Called from ApplyFlares; a bind that is already there is not added again (AddUnique). Hand flares: nothing."""
    g = Graph()
    g.cast("asGun", GUN_FLARE, "entry.Flare")
    g.call("parts", ACTOR + ":K2_GetComponentsByClass", ComponentClass=PARTICLES, target=ref("entry.Flare"))
    g.set("keepParts", "Parts", value="parts.ReturnValue")
    part = g.loop("eachPart", g.get("getParts", "Parts"))
    g.node("handler", "createdelegate", fn="GunFlareOut")
    g.node("bind", "adddelegate", name="OnComponentDeactivated", **{"class": "/Script/Engine.ActorComponent"})
    g.link(part, "bind.self")
    g.link("handler.OutputDelegate", "bind.Delegate")
    g.flow("entry", "asGun", "keepParts", "eachPart.Exec")
    g.flow("eachPart.LoopBody", "bind")
    return g.data()


def g_gun_tail():
    """GunTail: the game has just hidden the lights of a flare gun flare (Component is its particle system). With
    the mod on, the mod's lights are shown again and faded out over GUN_TAIL seconds from the level they had;
    FadeLights hides them again at the end. Ignored while the flare still burns (another particle system went off)."""
    g = Graph()
    g.call("on", KML + ":BooleanAND", A=ref(g.get("getActive", "ActiveInLevel")), B=ref(g.setting("Enabled")))
    g.branch("brOn", "on.ReturnValue")
    g.call("owner", "/Script/Engine.ActorComponent:GetOwner", target=ref("entry.Component"))
    gun = g.cast("asGun", GUN_FLARE, "owner.ReturnValue")
    g.call("out", KML + ":Not_PreBool", A=ref(g.get("flag", "IsFlareOn", GUN_FLARE, gun)))
    g.branch("brOut", "out.ReturnValue")
    g.call("known", "IsFading", Flare=ref("owner.ReturnValue"))
    g.branch("brKnown", "known.bFading")
    g.call("tailEnd", KML + ":Add_FloatFloat", A=ref(g.call("nowEnd", GS + ":GetTimeSeconds") + ".ReturnValue"), B=str(GUN_TAIL))
    add_fade_here(g, "owner.ReturnValue", "tailEnd.ReturnValue", show=True)
    g.flow("entry", "brOn", "asGun", "brOut", "known", "brKnown")
    g.flow("brKnown.else", "keepLights", "eachLight.Exec")
    return g.data()


def slot(name, i):
    return "%s%d" % (name, i)


def g_is_fading():
    """Has this flare a fade slot already?"""
    g = Graph()
    found = None
    for i in range(FADE_SLOTS):
        g.call(slot("same", i), KML + ":EqualEqual_ObjectObject", A=ref("entry.Flare"), B=ref(g.get(slot("get", i), slot("FadeFlare", i))))
        same = slot("same", i) + ".ReturnValue"
        if found is None:
            found = same
        else:
            found = g.call(slot("or", i), KML + ":BooleanOR", A=ref(found), B=ref(same)) + ".ReturnValue"
    g.link(found, "result.bFading")
    g.flow("entry", "result")
    return g.data()


def g_add_fade():
    """Puts a flare in the first free fade slot and starts the Tick. No free slot: the game's own ending."""
    g = Graph()
    g.set("mark", "Fading", default="true")
    g.call("tickOn", ACTOR + ":SetActorTickEnabled", bEnabled="true")
    g.flow("mark", "tickOn")
    previous = "entry"
    for i in range(FADE_SLOTS):
        g.call(slot("valid", i), KSL + ":IsValid", Object=ref(g.get(slot("get", i), slot("FadeFlare", i))))
        g.branch(slot("br", i), slot("valid", i) + ".ReturnValue")
        g.set(slot("flare", i), slot("FadeFlare", i), value="entry.Flare")
        g.set(slot("start", i), slot("FadeStart", i), value="entry.Start")
        g.set(slot("end", i), slot("FadeEnd", i), value="entry.End")
        g.flow(previous, slot("br", i))
        g.flow(slot("br", i) + ".else", slot("flare", i), slot("start", i), slot("end", i), "mark")
        previous = slot("br", i)
    return g.data()


def g_fade_lights():
    """Every frame while flares fade (Tick, after the game's own light update). Each of the mod's lights of a
    fading flare: intensity = its level at the start of the fade (IESBrightnessScale) * (1 - u)^3, u going from
    0 to 1 between FadeStart and FadeEnd. After the fade the lights are kept at zero for FADE_HOLD, then they are
    hidden (the game has hidden a hand flare's already; GunTail showed a flare gun flare's again) and the slot
    is freed. No slot in use: the Tick stops."""
    g = Graph()
    g.call("on", KML + ":BooleanAND", A=ref(g.get("getActive", "ActiveInLevel")), B=ref(g.setting("Enabled")))
    g.branch("brOn", "on.ReturnValue")
    g.call("off", "StopFades")
    g.flow("entry", "brOn")
    g.flow("brOn.else", "off")
    g.set("idle", "FadeBusy", default="false")
    g.call("now", GS + ":GetTimeSeconds")
    now = "now.ReturnValue"
    g.flow("brOn", "idle")
    exits = ["idle.then"]  # exec outputs that lead on to the next slot
    for i in range(FADE_SLOTS):
        flare = g.get(slot("flare", i), slot("FadeFlare", i))
        start = g.get(slot("start", i), slot("FadeStart", i))
        end = g.get(slot("end", i), slot("FadeEnd", i))
        g.call(slot("valid", i), KSL + ":IsValid", Object=ref(flare))
        g.branch(slot("br", i), slot("valid", i) + ".ReturnValue")
        g.call(slot("t", i), KML + ":Subtract_FloatFloat", A=ref(now), B=ref(start))
        g.call(slot("len", i), KML + ":FMax", B="0.05",
               A=ref(g.call(slot("span", i), KML + ":Subtract_FloatFloat", A=ref(end), B=ref(start)) + ".ReturnValue"))
        g.call(slot("u", i), KML + ":FClamp", Min="0.0", Max="1.0",
               Value=ref(g.call(slot("ratio", i), KML + ":Divide_FloatFloat", A=ref(slot("t", i) + ".ReturnValue"),
                                B=ref(slot("len", i) + ".ReturnValue")) + ".ReturnValue"))
        g.call(slot("left", i), KML + ":Subtract_FloatFloat", A="1.0", B=ref(slot("u", i) + ".ReturnValue"))
        g.call(slot("k", i), KML + ":MultiplyMultiply_FloatFloat", Base=ref(slot("left", i) + ".ReturnValue"), Exp=str(FADE_POWER))
        g.set(slot("keepK", i), "FadeLevel", value=slot("k", i) + ".ReturnValue")  # once per frame, not per light
        g.call(slot("lights", i), ACTOR + ":K2_GetComponentsByClass", ComponentClass=POINT, target=ref(flare))
        g.set(slot("keepLights", i), "FadePoints", value=slot("lights", i) + ".ReturnValue")
        light = g.loop(slot("each", i), g.get(slot("getLights", i), "FadePoints"))
        g.branch(slot("brMine", i), is_mod_light(g, slot("mine", i), light))
        g.call(slot("level", i), KML + ":Multiply_FloatFloat", A=ref(g.get(slot("from", i), "IESBrightnessScale", LIGHT, light)),
               B=ref(g.get(slot("getK", i), "FadeLevel")))
        g.call(slot("set", i), LIGHT + ":SetIntensity", target=ref(light), NewIntensity=ref(slot("level", i) + ".ReturnValue"))
        g.call(slot("over", i), KML + ":Greater_FloatFloat", A=ref(now),
               B=ref(g.call(slot("until", i), KML + ":Add_FloatFloat", A=ref(end), B=str(FADE_HOLD)) + ".ReturnValue"))
        g.branch(slot("brOver", i), slot("over", i) + ".ReturnValue")
        g.set(slot("free", i), slot("FadeFlare", i))
        g.set(slot("busy", i), "FadeBusy", default="true")
        for out_pin in exits:
            g.link(out_pin, slot("br", i) + ".execute")
        g.flow(slot("br", i), slot("keepK", i), slot("keepLights", i), slot("each", i) + ".Exec")
        g.branch(slot("brHide", i), slot("over", i) + ".ReturnValue")
        g.call(slot("hide", i), SCENE + ":SetVisibility", target=ref(light), bNewVisibility="false",
               bPropagateToChildren="false")
        g.flow(slot("each", i) + ".LoopBody", slot("brMine", i), slot("set", i), slot("brHide", i), slot("hide", i))
        g.flow(slot("each", i) + ".Completed", slot("brOver", i), slot("free", i))
        g.flow(slot("brOver", i) + ".else", slot("busy", i))
        exits = [slot("br", i) + ".else", slot("free", i) + ".then", slot("busy", i) + ".then"]
    g.branch("brBusy", g.get("getBusy", "FadeBusy"))
    g.call("done", "StopFades")
    for out_pin in exits:
        g.link(out_pin, "brBusy.execute")
    g.flow("brBusy.else", "done")
    return g.data()


def g_stop_fades():
    """Frees every fade slot and stops the Tick. The game drives those lights again."""
    g = Graph()
    chain = ["entry"]
    for i in range(FADE_SLOTS):
        chain.append(g.set(slot("free", i), slot("FadeFlare", i)))
    g.set("clear", "Fading", default="false")
    g.call("tickOff", ACTOR + ":SetActorTickEnabled", bEnabled="false")
    g.flow(*chain, "clear", "tickOff")
    return g.data()


def g_watch_flares():
    """Cheap check of one kind of flare, ten times a second. Burnt-out flares are skipped (IsLit).

    With the mod on, the fill and the spot lights of every flare reach Range. One that does not belongs to a
    new flare, or the game has just set it (it does when a flare ignites or lands), so the whole kind is
    applied again at once. A flare gun flare whose light timeline has just started is applied again too:
    the game has just put its own intensities back (see GUN_ANIM_FRESH).
    The shadow light of every flare is put back above it (PlaceShadowLight): a flying or rolling flare turns it.
    """
    g = Graph()
    g.set("clear", "Stale", default="false")
    g.call("all", GS + ":GetAllActorsOfClass", ActorClass=ref("entry.FlareClass"))
    g.set("keep", "Actors", value="all.OutActors")
    g.call("wanted", KML + ":Multiply_FloatFloat", A="100.0", B=ref("entry.Range"))
    flare = g.loop("each", g.get("getActors", "Actors"))
    g.call("lights", ACTOR + ":K2_GetComponentsByClass", ComponentClass=POINT, target=ref(flare))
    g.set("keepLights", "Points", value="lights.ReturnValue")
    light = g.loop("eachLight", g.get("getLights", "Points"))
    g.call("diff", KML + ":Subtract_FloatFloat", A=ref(g.get("radius", "AttenuationRadius", LOCAL_LIGHT, light)),
           B=ref("wanted.ReturnValue"))
    g.call("abs", KML + ":Abs", A=ref("diff.ReturnValue"))
    g.call("short", KML + ":Greater_FloatFloat", A=ref("abs.ReturnValue"), B="1.0")
    # The flare's small glow lights (75 to 250 cm) are not the mod's; the game's spot radius is 300 cm or more.
    g.call("big", KML + ":GreaterEqual_FloatFloat", A=ref(g.get("radius2", "AttenuationRadius", LOCAL_LIGHT, light)), B="290.0")
    g.call("off", KML + ":BooleanAND", A=ref("short.ReturnValue"), B=ref("big.ReturnValue"))
    g.branch("brOff", "off.ReturnValue")
    g.set("mark", "Stale", default="true")
    # The shadow light: the fill with a stored radius (see g_apply_flare). Spots and glow lights have none.
    g.call("isShadow", KML + ":GreaterEqual_FloatFloat", B=str(STORED_MIN),
           A=ref(g.get("stored", "IndirectLightingIntensity", LIGHT_BASE, light)))
    g.branch("brShadow", "isShadow.ReturnValue")
    g.call("place", "PlaceShadowLight", Flare=ref(flare), Light=ref(light))
    g.call("lit", "IsLit", Flare=ref(flare))
    g.branch("brLit", "lit.bLit")
    g.flow("entry", "clear", "all", "keep", "each.Exec")
    g.flow("each.LoopBody", "lit", "brLit", "keepLights", "eachLight.Exec")
    g.flow("eachLight.LoopBody", "brOff", "mark", "brShadow", "place")
    g.flow("brOff.else", "brShadow")

    # Flare gun flare: its light timeline (Light_Anim, 90 long; the hand flare's unused one is 15) just started.
    g.branch("brGun", "entry.bGun")
    g.call("timelines", ACTOR + ":K2_GetComponentsByClass", ComponentClass=TIMELINE, target=ref(flare))
    g.set("keepTimelines", "Timelines", value="timelines.ReturnValue")
    timeline = g.loop("eachTimeline", g.get("getTimelines", "Timelines"))
    g.call("pos", TIMELINE + ":GetPlaybackPosition", target=ref(timeline))
    g.call("early", KML + ":Less_FloatFloat", A=ref("pos.ReturnValue"), B=str(GUN_ANIM_FRESH))
    g.call("playing", TIMELINE + ":IsPlaying", target=ref(timeline))
    g.call("length", TIMELINE + ":GetTimelineLength", target=ref(timeline))
    g.call("isLight", KML + ":GreaterEqual_FloatFloat", A=ref("length.ReturnValue"), B=str(GUN_TIMELINE_END - 1.0))
    g.call("fresh1", KML + ":BooleanAND", A=ref("early.ReturnValue"), B=ref("playing.ReturnValue"))
    g.call("fresh", KML + ":BooleanAND", A=ref("fresh1.ReturnValue"), B=ref("isLight.ReturnValue"))
    g.branch("brFresh", "fresh.ReturnValue")
    g.set("markFresh", "Stale", default="true")
    g.flow("eachLight.Completed", "brGun", "keepTimelines", "eachTimeline.Exec")
    g.flow("eachTimeline.LoopBody", "brFresh", "markFresh")

    g.branch("brStale", g.get("getStale", "Stale"))
    g.call("apply", "ApplyFlares", FlareClass=ref("entry.FlareClass"), Range=ref("entry.Range"), Count=ref("entry.Count"))
    g.flow("each.Completed", "brStale", "apply")
    return g.data()


def g_place_shadow_light():
    """Puts the shadow light of a flare SHADOW_LIGHT_LIFT above the part of the flare it hangs on, in world space.

    That part is the light's parent: the hand flare's box (its root), or the box of the flare gun's dart (its
    shaft, 30 cm behind the tip that sticks in the wall; the actor's own place is that tip). The light's own
    place on the flare may be in the floor or the wall. The lift is kept relative to the flare, so it would turn
    with a tumbling flare between two Watch calls and the shadows would jump (in game: lift -13 to +15 cm at
    4 samples a second, 2026-11-24). So while the flare moves faster than MOVING_SPEED the light sits at the
    centre of that part, where turning does not move it, and gets its lift once the flare is at rest.
    The light moves only when it is more than PLACE_TOLERANCE off: a light that moves renders its shadow map
    again instead of the cached one.
    A light that is the flare's root is never moved: that would move the flare.
    """
    g = Graph()
    light = "entry.Light"
    g.call("root", ACTOR + ":K2_GetRootComponent", target=ref("entry.Flare"))
    g.call("isRoot", KML + ":EqualEqual_ObjectObject", A=ref(light), B=ref("root.ReturnValue"))
    g.branch("brRoot", "isRoot.ReturnValue")
    g.call("parent", SCENE + ":GetAttachParent", target=ref(light))
    g.call("hasParent", KSL + ":IsValid", Object=ref("parent.ReturnValue"))
    g.branch("brParent", "hasParent.ReturnValue")
    g.set("fromParent", "LiftFrom", value=g.call("parentAt", SCENE + ":K2_GetComponentLocation",
                                                   target=ref("parent.ReturnValue")) + ".ReturnValue")
    g.set("fromFlare", "LiftFrom", value=g.call("flareAt", ACTOR + ":K2_GetActorLocation",
                                                  target=ref("entry.Flare")) + ".ReturnValue")
    g.call("speed", KML + ":VSize", A=ref(g.call("velocity", ACTOR + ":GetVelocity", target=ref("entry.Flare")) + ".ReturnValue"))
    g.call("moving", KML + ":Greater_FloatFloat", A=ref("speed.ReturnValue"), B=str(MOVING_SPEED))
    g.call("liftZ", KML + ":SelectFloat", A="0.0", B=str(SHADOW_LIGHT_LIFT), bPickA=ref("moving.ReturnValue"))
    g.call("lift", KML + ":MakeVector", X="0.0", Y="0.0", Z=ref("liftZ.ReturnValue"))
    g.call("lifted", KML + ":Add_VectorVector", A=ref(g.get("getFrom", "LiftFrom")), B=ref("lift.ReturnValue"))
    g.call("lightAt", SCENE + ":K2_GetComponentLocation", target=ref(light))
    g.call("offset", KML + ":Subtract_VectorVector", A=ref("lifted.ReturnValue"), B=ref("lightAt.ReturnValue"))
    g.call("far", KML + ":Greater_FloatFloat", A=ref(g.call("dist", KML + ":VSize", A=ref("offset.ReturnValue")) + ".ReturnValue"),
           B=str(PLACE_TOLERANCE))
    g.branch("brFar", "far.ReturnValue")
    g.call("move", SCENE + ":K2_SetWorldLocation", target=ref(light), NewLocation=ref("lifted.ReturnValue"),
           bSweep="false", bTeleport="true")
    g.flow("entry", "brRoot")
    g.flow("brRoot.else", "brParent", "fromParent", "brFar", "move")
    g.flow("brParent.else", "fromFlare", "brFar")
    return g.data()


def g_colour_light():
    """Light colour of one flare light: the pastel class colour, or its own colour from the game.

    The light's first colour is kept on the light itself, in LightFunctionScale: a property that does
    nothing without a light function material (flares have none). The engine default is 1024; a value below
    STORED_COLOUR_MAX means "stored colour".
    colour = lerp(white, Hue, TintAmount) * brightness of own colour * Gain. TintAmount 0 gives the own colour
    (the step from own to class colour happens between 0 and 0.1).
    """
    g = Graph()
    light = "entry.Light"
    light_class = "/Script/Engine.LightComponent"
    g.call("brk", KML + ":BreakVector", InVec=ref(g.get("stored", "LightFunctionScale", light_class, light)))
    g.call("hasStored", KML + ":Less_FloatFloat", A=ref("brk.X"), B=str(STORED_COLOUR_MAX))
    g.branch("br", "hasStored.ReturnValue")
    g.call("now", LIGHT_BASE + ":GetLightColor", target=ref(light))
    g.call("asVec", KML + ":Conv_LinearColorToVector", InLinearColor=ref("now.ReturnValue"))
    g.call("store", light_class + ":SetLightFunctionScale", target=ref(light), NewLightFunctionScale=ref("asVec.ReturnValue"))
    # Read again here, after the store.
    g.call("own", KML + ":Conv_VectorToLinearColor", InVec=ref(g.get("stored2", "LightFunctionScale", light_class, light)))
    g.call("hsv", KML + ":RGBToHSV", InColor=ref("own.ReturnValue"))
    tint = g.get("tint", "TintAmount")
    g.call("pastel", KML + ":LinearColorLerp", A="(R=1.0,G=1.0,B=1.0,A=1.0)", B=ref(g.get("hue", "Hue")), Alpha=ref(tint))
    g.call("target", KML + ":Multiply_LinearColorFloat", A=ref("pastel.ReturnValue"), B=ref("hsv.V"))
    g.call("step", KML + ":Multiply_FloatFloat", A=ref(tint), B="10.0")
    g.call("stepClamp", KML + ":FClamp", Value=ref("step.ReturnValue"), Min="0.0", Max="1.0")
    g.call("mixed", KML + ":LinearColorLerp", A=ref("own.ReturnValue"), B=ref("target.ReturnValue"), Alpha=ref("stepClamp.ReturnValue"))
    # Gain scales red, green and blue only; alpha stays 1.
    g.call("gain", KML + ":MakeColor", R=ref("entry.Gain"), G=ref("entry.Gain"), B=ref("entry.Gain"), A="1.0")
    g.call("final", KML + ":Multiply_LinearColorLinearColor", A=ref("mixed.ReturnValue"), B=ref("gain.ReturnValue"))
    g.call("set", light_class + ":SetLightColor", target=ref(light), NewLightColor=ref("final.ReturnValue"))
    g.flow("entry", "br", "set")
    g.flow("br.else", "store", "set")
    return g.data()


def g_aim_spot():
    """Rotation of one spot light of a flare gun flare: the game's, or tilted back out of the wall."""
    g = Graph()
    g.call("name", KSL + ":GetObjectName", Object=ref("entry.Light"))
    rotators = {}
    for part, (pitch, yaw, roll) in GUN_SPOTS_GAME.items():
        up_pitch, up_yaw = gun_spot_tilted(pitch, yaw)
        g.call("game" + part, KML + ":MakeRotator", Roll=str(roll), Pitch=str(pitch), Yaw=str(yaw))
        g.call("up" + part, KML + ":MakeRotator", Roll=str(roll), Pitch=str(up_pitch), Yaw=str(up_yaw))
        g.call("pick" + part, KML + ":SelectRotator", A=ref("up%s.ReturnValue" % part), B=ref("game%s.ReturnValue" % part),
               bPickA=ref("entry.bUpgrade"))
        rotators[part] = "pick%s.ReturnValue" % part
    g.call("is2", KSTR + ":Contains", SearchIn=ref("name.ReturnValue"), Substring="Shadow_2")
    g.call("is3", KSTR + ":Contains", SearchIn=ref("name.ReturnValue"), Substring="Shadow_3")
    g.call("pick23", KML + ":SelectRotator", A=ref(rotators["Shadow_2"]), B=ref(rotators["Shadow_3"]), bPickA=ref("is2.ReturnValue"))
    g.call("not1", KML + ":BooleanOR", A=ref("is2.ReturnValue"), B=ref("is3.ReturnValue"))
    g.call("pick", KML + ":SelectRotator", A=ref("pick23.ReturnValue"), B=ref(rotators["Shadow_1"]), bPickA=ref("not1.ReturnValue"))
    g.call("aim", "/Script/Engine.SceneComponent:K2_SetRelativeRotation", target=ref("entry.Light"),
           NewRotation=ref("pick.ReturnValue"), bSweep="false", bTeleport="true")
    g.flow("entry", "aim")
    return g.data()


def g_apply_flare():
    """One flare: a hand flare or a flare from the Scout's flare gun. Both are built the same way.

    The game's flare has three spot lights in a ring (shadows, a few metres) and one fill point light
    (no shadows, 20 m; flare gun 35 m). Their intensity is animated by the flare every frame from its own
    variable BaseIntensity (hand flare: fill and spots). The mod sets that variable, so the game's fade-in and
    flicker stay. A flare gun flare keeps its lights' own intensities; its variables LightIntensity_Point and
    LightIntensity_Spot are only used when it goes out (see GUN_END_POINT). The last seconds of the light are
    faded by the mod itself (see FADE_SLOTS).

    Mod on (bUpgrade): the fill becomes the one shadow light, all round, like a real flame: reach Range,
    steeper falloff, lifted 15 cm above the flare, the flare's own mesh casts no shadow. The three spot lights
    cast no shadows and only lift the shadows a little (ShadowStrength sets the share). The fill casts shadows
    only if bCast (one of the nearest flares, see ApplyFlares); the light is the same either way, so a flare
    that gains or loses its shadow does not change its light. Lights get the class colour, and the intensity
    is raised by 1 / luminance of that colour, so a coloured flare is as bright as a white one.
    Mod off: the game's own values.

    The fill's own radius is kept on the light in IndirectLightingIntensity (unused by movable lights in this
    game); values of 50 and up mean "stored radius". Colours are kept the same way, see g_colour_light.
    """
    g = Graph()
    flare = "entry.Flare"
    light_class = "/Script/Engine.LightComponent"

    # --- what kind of flare, and whose. The class is in the actor's name (ITM_Flare_Large_Gunner_C_3).
    g.call("name", KSL + ":GetObjectName", Object=ref(flare))

    def named(node_id, part):
        g.call(node_id, KSTR + ":Contains", SearchIn=ref("name.ReturnValue"), Substring=part)
        return node_id + ".ReturnValue"

    is_gun = named("isGun", "FlareGun")
    is_driller, is_engineer, is_gunner, is_scout = (named("is" + c, c) for c in ("Driller", "Engineer", "Gunner", "Scout"))
    g.call("hueC", KML + ":SelectColor", A=CLASS_HUE["Gunner"], B=CLASS_HUE["Scout"], bPickA=ref(is_gunner))
    g.call("hueB", KML + ":SelectColor", A=CLASS_HUE["Engineer"], B=ref("hueC.ReturnValue"), bPickA=ref(is_engineer))
    g.call("hue", KML + ":SelectColor", A=CLASS_HUE["Driller"], B=ref("hueB.ReturnValue"), bPickA=ref(is_driller))
    g.call("known1", KML + ":BooleanOR", A=ref(is_driller), B=ref(is_engineer))
    g.call("known2", KML + ":BooleanOR", A=ref(is_gunner), B=ref(is_scout))
    g.call("known3", KML + ":BooleanOR", A=ref("known1.ReturnValue"), B=ref("known2.ReturnValue"))
    g.call("known", KML + ":BooleanOR", A=ref("known3.ReturnValue"), B=ref(is_gun))
    # Only hand flares of a known class take the class colour. The flare gun keeps the game's own light.
    g.call("useTint", KML + ":BooleanAND", A=ref("known3.ReturnValue"), B=ref("entry.bUpgrade"))
    colour = g.setting("FlareColour")
    # Class colour 0..1 is the colour itself (white to full hue); 1..2 makes the coloured light brighter.
    g.call("colourSat", KML + ":FMin", A=ref(colour), B="1.0")
    g.call("tintPick", KML + ":SelectFloat", A=ref("colourSat.ReturnValue"), B="0.0", bPickA=ref("useTint.ReturnValue"))
    g.call("colourExtra", KML + ":FMax", A=ref(colour), B="1.0")
    g.call("extraPick", KML + ":SelectFloat", A=ref("colourExtra.ReturnValue"), B="1.0", bPickA=ref("useTint.ReturnValue"))
    # Luminance of the class colour: intensity is divided by it, so colour does not darken the light.
    g.call("pastel", KML + ":LinearColorLerp", A="(R=1.0,G=1.0,B=1.0,A=1.0)", B=ref("hue.ReturnValue"),
           Alpha=ref("tintPick.ReturnValue"))
    g.call("lum", KML + ":LinearColor_GetLuminance", InColor=ref("pastel.ReturnValue"))
    # A pure colour has low luminance (red 0.21); compensate at most about 2.9 times, or it blows out.
    g.call("lumSafe", KML + ":FMax", A=ref("lum.ReturnValue"), B="0.35")
    strength = g.setting("ShadowStrength")
    g.call("brightWanted", KML + ":Multiply_FloatFloat", A=ref(g.setting("FlareBrightness")), B=ref("extraPick.ReturnValue"))
    g.call("brightLum", KML + ":Divide_FloatFloat", A=ref("brightWanted.ReturnValue"), B=ref("lumSafe.ReturnValue"))
    # Mod on: brightness / luminance, and the split between shadow light and spots.
    # Hand flare: fill = Base*k, spots = Base*k*1.6 (in the game). Total in the game = 2.6 * Base.
    g.call("handBig", KML + ":Multiply_FloatFloat", A=ref("brightLum.ReturnValue"),
           B=ref(g.call("handBigS", KML + ":Multiply_FloatFloat", A=str(HAND_TOTAL), B=ref(strength)) + ".ReturnValue"))
    g.call("weak", KML + ":Subtract_FloatFloat", A="1.0", B=ref(strength))
    # Hand flare spots share the fill's BaseIntensity, so they are dimmed through their colour instead.
    g.call("handAmbient", KML + ":Divide_FloatFloat", A=ref(g.call("handWeak", KML + ":Multiply_FloatFloat", A=str(1.0 / HAND_SPOT_SHARE),
                                                                     B=ref("weak.ReturnValue")) + ".ReturnValue"),
           B=ref(strength))
    g.call("handAmbientClamp", KML + ":FClamp", Value=ref("handAmbient.ReturnValue"), Min="0.0", Max="1.0")

    def pick(node_id, big):
        """big if mod on, 1 if mod off."""
        g.call(node_id, KML + ":SelectFloat", A=ref(big), B="1.0", bPickA=ref("entry.bUpgrade"))
        return node_id + ".ReturnValue"

    hand_boost = pick("handBoost", "handBig.ReturnValue")
    g.call("ambientGain", KML + ":SelectFloat", A=ref("handAmbientClamp.ReturnValue"), B="1.0", bPickA=ref("entry.bUpgrade"))
    g.call("gainPick", KML + ":SelectFloat", A="1.0", B=ref("ambientGain.ReturnValue"), bPickA=ref(is_gun))
    g.call("biasPick", KML + ":SelectFloat", A=str(GUN_BIAS_GAME), B=str(FLARE_BIAS_GAME), bPickA=ref(is_gun))

    # Intensity variables of the flare. Hand flares: the game's BaseIntensity differs per class.
    g.call("isSmallEng", KSTR + ":Contains", SearchIn=ref("name.ReturnValue"), Substring="Small_Engineer")
    g.call("isSmallDrill", KSTR + ":Contains", SearchIn=ref("name.ReturnValue"), Substring="Small_Driller")
    g.call("isSmall", KSTR + ":Contains", SearchIn=ref("name.ReturnValue"), Substring="Flare_Small")
    g.call("base2", KML + ":SelectFloat", A=str(HAND_BASE["Flare_Small"]), B=str(HAND_BASE["default"]), bPickA=ref("isSmall.ReturnValue"))
    g.call("base1", KML + ":SelectFloat", A=str(HAND_BASE["Small_Driller"]), B=ref("base2.ReturnValue"), bPickA=ref("isSmallDrill.ReturnValue"))
    g.call("base", KML + ":SelectFloat", A=str(HAND_BASE["Small_Engineer"]), B=ref("base1.ReturnValue"), bPickA=ref("isSmallEng.ReturnValue"))
    g.call("handI", KML + ":Multiply_FloatFloat", A=ref("base.ReturnValue"), B=ref(hand_boost))
    # Flare gun: with the mod on, what the game writes when the flare goes out is the lights' own level.
    g.call("pointI", KML + ":SelectFloat", A=str(GUN_POINT_BASE / GUN_END_POINT), B=str(GUN_POINT_BASE), bPickA=ref("entry.bUpgrade"))
    g.call("spotI", KML + ":SelectFloat", A=str(GUN_SPOT_BASE / GUN_END_SPOT), B=str(GUN_SPOT_VAR_GAME), bPickA=ref("entry.bUpgrade"))
    g.call("setHandI", KSL + ":SetFloatPropertyByName", Object=ref(flare), PropertyName="BaseIntensity", Value=ref("handI.ReturnValue"))
    g.call("setPointI", KSL + ":SetFloatPropertyByName", Object=ref(flare), PropertyName="LightIntensity_Point", Value=ref("pointI.ReturnValue"))
    g.call("setSpotI", KSL + ":SetFloatPropertyByName", Object=ref(flare), PropertyName="LightIntensity_Spot", Value=ref("spotI.ReturnValue"))
    g.branch("brKindI", is_gun)

    # Kept in variables: the loops below would otherwise run the name checks again for every light.
    g.set("keepHue", "Hue", value="hue.ReturnValue")
    g.set("keepTint", "TintAmount", value="tintPick.ReturnValue")
    g.set("keepGain", "SpotGain", value="gainPick.ReturnValue")
    g.set("keepBias", "GameBias", value="biasPick.ReturnValue")
    g.set("keepGun", "IsGun", value=is_gun)
    g.call("spots", ACTOR + ":K2_GetComponentsByClass", ComponentClass=SPOT, target=ref(flare))
    g.set("keep", "Lights", value="spots.ReturnValue")
    g.call("points", ACTOR + ":K2_GetComponentsByClass", ComponentClass=POINT, target=ref(flare))
    g.set("keepPoints", "Points", value="points.ReturnValue")
    # The flare's own meshes never cast shadows with the mod on: the shadow light sits next to them.
    g.branch("brMeshes", "entry.bUpgrade")
    g.call("meshes", ACTOR + ":K2_GetComponentsByClass", ComponentClass=MESH, target=ref(flare))
    g.set("keepMeshes", "Meshes", value="meshes.ReturnValue")
    mesh = g.loop("eachMesh", g.get("getMeshes", "Meshes"))
    g.call("meshOff", PRIMITIVE + ":SetCastShadow", target=ref(mesh), NewCastShadow="false")
    g.branch("brUpgrade", "entry.bUpgrade")
    g.flow("entry", "brKindI")
    g.flow("brKindI", "setPointI", "setSpotI", "keepHue")
    g.flow("brKindI.else", "setHandI", "keepHue")
    g.flow("keepHue", "keepTint", "keepGain", "keepBias", "keepGun", "keep", "keepPoints", "brMeshes", "keepMeshes", "eachMesh.Exec")
    g.flow("eachMesh.LoopBody", "meshOff")
    g.flow("eachMesh.Completed", "brUpgrade")
    g.flow("brMeshes.else", "brUpgrade")

    # --- chosen: spots are soft fill without shadows
    light = g.loop("eachUp", g.get("getLights", "Lights"))
    g.call("range", KML + ":Multiply_FloatFloat", A="100.0", B=ref("entry.Range"))
    g.call("setRange", LOCAL_LIGHT + ":SetAttenuationRadius", target=ref(light), NewRadius=ref("range.ReturnValue"))
    g.call("castUp", LIGHT_BASE + ":SetCastShadows", target=ref(light), bNewValue="false")
    g.call("outerUp", SPOT + ":SetOuterConeAngle", target=ref(light), NewOuterConeAngle=str(FLARE_OUTER_UPGRADED))
    g.call("coneUp", SPOT + ":SetInnerConeAngle", target=ref(light), NewInnerConeAngle=str(FLARE_INNER_UPGRADED))
    g.call("colourUp", "ColourLight", Light=ref(light), Gain=ref(g.get("gain", "SpotGain")))
    g.branch("brGunUp", g.get("gunUp", "IsGun"))
    g.call("aimUp", "AimSpot", Light=ref(light), bUpgrade="true")
    g.flow("brUpgrade", "eachUp.Exec")
    g.flow("eachUp.LoopBody", "setRange", "outerUp", "coneUp", "colourUp", "castUp", "brGunUp", "aimUp")

    # --- chosen: the fill is the shadow light
    fill = g.loop("eachFill", g.get("getPoints", "Points"))
    g.node("fillIsSpot", "cast", **{"class": SPOT})
    g.link(fill, "fillIsSpot.Object")
    stored = g.get("stored", "IndirectLightingIntensity", LIGHT_BASE, fill)
    radius = g.get("fillRadius", "AttenuationRadius", LOCAL_LIGHT, fill)
    g.call("hasStored", KML + ":GreaterEqual_FloatFloat", A=ref(stored), B=str(STORED_MIN))
    g.call("isFill", KML + ":GreaterEqual_FloatFloat", A=ref(radius), B=str(FILL_MIN_RADIUS))
    g.call("needStore", KML + ":Not_PreBool", A=ref("hasStored.ReturnValue"))
    g.call("storeNow", KML + ":BooleanAND", A=ref("needStore.ReturnValue"), B=ref("isFill.ReturnValue"))
    g.branch("brStore", "storeNow.ReturnValue")
    g.call("store", light_class + ":SetIndirectLightingIntensity", target=ref(fill), NewIntensity=ref(radius))
    g.branch("brShadow", "hasStored.ReturnValue")  # read again here, after the store
    g.flow("eachUp.Completed", "eachFill.Exec")
    g.flow("eachFill.LoopBody", "fillIsSpot")
    g.flow("fillIsSpot.CastFailed", "brStore", "store", "brShadow")
    g.flow("brStore.else", "brShadow")
    g.call("fillRange", LOCAL_LIGHT + ":SetAttenuationRadius", target=ref(fill), NewRadius=ref("range.ReturnValue"))
    g.call("fillFalloff", POINT + ":SetLightFalloffExponent", target=ref(fill), NewLightFalloffExponent=str(SHADOW_FALLOFF))
    g.call("fillRes", KSL + ":SetFloatPropertyByName", Object=ref(fill), PropertyName="ShadowResolutionScale",
           Value=str(SHADOW_RESOLUTION_SCALE))
    g.call("fillBias", light_class + ":SetShadowBias", target=ref(fill), NewValue=str(SHADOW_BIAS))
    g.call("fillSlope", light_class + ":SetShadowSlopeBias", target=ref(fill), NewValue=str(SHADOW_SLOPE_BIAS))
    g.call("fillSource", KML + ":Multiply_FloatFloat", A=str(FLARE_SOURCE_RADIUS), B=ref(g.setting("Penumbra")))
    g.call("fillSetSource", POINT + ":SetSourceRadius", target=ref(fill), bNewValue=ref("fillSource.ReturnValue"))
    g.call("fillShafts", LIGHT_BASE + ":SetCastVolumetricShadow", target=ref(fill), bNewValue=ref(g.setting("LightShafts")))
    # The flare gun's fill (PointLight_NoShadow) also has CastDynamicShadows off, and a movable light casts shadows
    # only with both on. There is no setter; SetCastShadows below then rebuilds the light (CastShadows changes).
    g.call("fillDynamic", KSL + ":SetBoolPropertyByName", Object=ref(fill), PropertyName="CastDynamicShadows", Value="true")
    g.call("fillCast", LIGHT_BASE + ":SetCastShadows", target=ref(fill), bNewValue=ref("entry.bCast"))
    g.call("fillColour", "ColourLight", Light=ref(fill), Gain="1.0")
    g.call("fillPlace", "PlaceShadowLight", Flare=ref(flare), Light=ref(fill))
    g.flow("brShadow", "fillRange", "fillFalloff", "fillRes", "fillBias", "fillSlope", "fillSetSource", "fillShafts",
           "fillDynamic", "fillCast", "fillColour", "fillPlace")

    # --- not chosen, or mod off: the flare sets its own spot radius again (the game picks it from the shadow quality)
    g.node("asFlare", "cast", **{"class": FLARE})
    g.link(flare, "asFlare.Object")
    g.call("ownRadius", FLARE + ":OnUpdateShadowRadius", target=ref("asFlare.$cast"))
    g.node("asGunFlare", "cast", **{"class": GUN_FLARE})
    g.link(flare, "asGunFlare.Object")
    g.call("ownGunRadius", GUN_FLARE + ":OnUpdateShadowRadius", target=ref("asGunFlare.$cast"))
    plain = g.loop("eachPlain", g.get("getLights2", "Lights"))
    g.call("noSource", POINT + ":SetSourceRadius", target=ref(plain), bNewValue="0.0")
    g.call("gameCast", KML + ":Not_PreBool", A=ref("entry.bUpgrade"))  # the game: every flare casts shadows
    g.call("castAs", LIGHT_BASE + ":SetCastShadows", target=ref(plain), bNewValue=ref("gameCast.ReturnValue"))
    g.call("biasBack", light_class + ":SetShadowBias", target=ref(plain), NewValue=ref(g.get("gameBias", "GameBias")))
    g.call("slopeBack", light_class + ":SetShadowSlopeBias", target=ref(plain), NewValue=str(FLARE_SLOPE_GAME))
    g.call("outerBack", SPOT + ":SetOuterConeAngle", target=ref(plain), NewOuterConeAngle=str(FLARE_OUTER_GAME))
    g.call("coneBack", SPOT + ":SetInnerConeAngle", target=ref(plain), NewInnerConeAngle=str(FLARE_INNER_GAME))
    g.call("colourBack", "ColourLight", Light=ref(plain), Gain="1.0")
    g.branch("brGunBack", g.get("gunBack", "IsGun"))
    g.call("aimBack", "AimSpot", Light=ref(plain), bUpgrade="false")
    g.flow("brUpgrade.else", "asFlare", "ownRadius", "eachPlain.Exec")
    g.flow("asFlare.CastFailed", "asGunFlare", "ownGunRadius", "eachPlain.Exec")
    g.flow("asGunFlare.CastFailed", "eachPlain.Exec")
    g.flow("eachPlain.LoopBody", "noSource", "biasBack", "slopeBack", "outerBack", "coneBack", "colourBack", "castAs",
           "brGunBack", "aimBack")

    back = g.loop("eachBack", g.get("getPoints2", "Points"))
    back_stored = g.get("backStored", "IndirectLightingIntensity", LIGHT_BASE, back)
    g.call("backHas", KML + ":GreaterEqual_FloatFloat", A=ref(back_stored), B=str(STORED_MIN))
    g.branch("brBack", "backHas.ReturnValue")
    g.call("restore", LOCAL_LIGHT + ":SetAttenuationRadius", target=ref(back), NewRadius=ref(back_stored))
    g.call("falloffBack", POINT + ":SetLightFalloffExponent", target=ref(back), NewLightFalloffExponent=str(FILL_FALLOFF_GAME))
    g.call("castBack", LIGHT_BASE + ":SetCastShadows", target=ref(back), bNewValue="false")
    g.call("fillColourBack", "ColourLight", Light=ref(back), Gain="1.0")
    # Back to the game's place on the flare: hand flare (0, 0, 20), flare gun (3.2, 0, 0).
    g.call("placeBack", KML + ":SelectVector", A="%s,0.0,0.0" % GUN_FILL_X, B="0.0,0.0,%s" % HAND_FILL_Z,
           bPickA=ref(g.get("gunBack2", "IsGun")))
    g.call("moveBack", "/Script/Engine.SceneComponent:K2_SetRelativeLocation", target=ref(back),
           NewLocation=ref("placeBack.ReturnValue"), bSweep="false", bTeleport="true")
    g.call("backRoot", ACTOR + ":K2_GetRootComponent", target=ref(flare))
    g.call("backIsRoot", KML + ":EqualEqual_ObjectObject", A=ref(back), B=ref("backRoot.ReturnValue"))
    g.branch("brBackRoot", "backIsRoot.ReturnValue")
    # Colour: every fill light, also of flares that were never chosen (radius test as in the store step).
    g.call("backIsFill", KML + ":GreaterEqual_FloatFloat", A=ref(g.get("backRadius", "AttenuationRadius", LOCAL_LIGHT, back)),
           B=str(FILL_MIN_RADIUS))
    g.call("backColourIt", KML + ":BooleanOR", A=ref("backHas.ReturnValue"), B=ref("backIsFill.ReturnValue"))
    g.branch("brBackColour", "backColourIt.ReturnValue")
    g.node("backIsSpot", "cast", **{"class": SPOT})
    g.link(back, "backIsSpot.Object")
    g.flow("eachPlain.Completed", "eachBack.Exec")
    g.flow("eachBack.LoopBody", "backIsSpot")
    g.flow("backIsSpot.CastFailed", "brBack", "restore", "falloffBack", "castBack", "brBackRoot")
    g.flow("brBackRoot.else", "moveBack", "brBackColour")
    g.flow("brBackRoot", "brBackColour")
    g.flow("brBack.else", "brBackColour")
    g.flow("brBackColour", "fillColourBack")
    return g.data()


def g_apply_terrain():
    """Cave walls cast shadows. Mod Hub turns this off by default, 5 seconds into a level."""
    g = Graph()
    g.call("on", KML + ":BooleanAND", A=ref(g.setting("Enabled")), B=ref(g.setting("TerrainShadows")))
    g.call("active", KML + ":BooleanAND", A=ref("on.ReturnValue"), B=ref(g.get("getActive", "ActiveInLevel")))
    g.branch("br", "active.ReturnValue")
    g.call("all", GS + ":GetAllActorsOfClass", ActorClass=TERRAIN)
    g.set("keep", "Actors", value="all.OutActors")
    section = g.loop("each", g.get("getActors", "Actors"))
    g.node("asSection", "cast", **{"class": TERRAIN})
    g.link(section, "asSection.Object")
    g.call("setCast", PRIMITIVE + ":SetCastShadow", NewCastShadow="true",
           target=ref(g.get("mesh", "DeepMesh", TERRAIN, "asSection.$cast")))
    g.flow("entry", "br", "all", "keep", "each.Exec")
    g.flow("each.LoopBody", "asSection", "setCast")
    return g.data()


def g_mod_events():
    g = Graph()
    g.node("begin", "event", name="ReceiveBeginPlay", **{"class": ACTOR})
    g.call("load", "LoadSettings")
    g.call("cvars", "ApplyCvars")
    g.node("me", "self")
    g.call("timer", KSL + ":K2_SetTimer", FunctionName="Refresh", Time="1.0", bLooping="true", Object=ref("me.self"))
    g.call("watchTimer", KSL + ":K2_SetTimer", FunctionName="Watch", Time="0.1", bLooping="true", Object=ref("me.self"))
    g.call("refresh", "Refresh")
    # The Tick only fades flare lights: after the game's own updates, and off until a light fades.
    g.call("tickGroup", ACTOR + ":SetTickGroup", NewTickGroup=TICK_GROUP)
    g.call("tickOff", ACTOR + ":SetActorTickEnabled", bEnabled="false")
    # A flare gun flare's particle system went off (BindGunEnd): its lights were just hidden.
    g.node("gunOut", "customevent", name="GunFlareOut", signature="/Script/Engine.ActorComponent:OnComponentDeactivated")
    g.call("gunTail", "GunTail", Component=ref("gunOut.Component"))
    g.flow("gunOut", "gunTail")
    g.node("tick", "event", name="ReceiveTick", **{"class": ACTOR})
    g.call("fade", "FadeLights")
    g.flow("tick", "fade")

    # Settings page: only if Mod Hub is installed. The paths are built from strings at run time,
    # so this Blueprint has no import of Mod Hub and loads without it.
    steps = modhub.spawn_hub(g, HUBMOD_C, "me.self")
    g.flow("begin", "load", "cvars", "tickGroup", "tickOff", "timer", "watchTimer", "refresh", *steps)
    return g.data()


def mod_asset():
    """The mod itself. It has no reference to Mod Hub, so it also loads when Mod Hub is not installed."""
    return {
        "kind": "blueprint", "path": MODBP, "parent": ACTOR,
        "variables": [
            t("Settings", "object", SETTINGS_C),
            t("ActiveInLevel", "bool", default="true"),
            t("Ticks", "int", default="0"),
            # Scratch arrays: results of pure calls are kept here so loops do not repeat the calls.
            t("Lights", "object", SPOT, array=True),
            t("Points", "object", POINT, array=True),
            t("Hue", "struct", "/Script/CoreUObject.LinearColor"),
            t("TintAmount", "float", default="0.0"),
            t("SpotGain", "float", default="1.0"),
            t("GameBias", "float", default="0.25"),
            t("IsGun", "bool", default="false"),
            t("Stale", "bool", default="false"),
            t("LiftFrom", "struct", "/Script/CoreUObject.Vector"),
            # Nearest flares (ApplyFlares): burning flares, their distances, the copy the cut is found in.
            t("CamAt", "struct", "/Script/CoreUObject.Vector"),
            t("CastAll", "bool", default="true"),
            t("Lit", "object", ACTOR, array=True),
            t("Dists", "float", array=True),
            t("Nearest", "float", array=True),
            t("Cut", "float", default="0.0"),
            t("MinDist", "float", default="0.0"),
            t("MinAt", "int", default="0"),
            t("LitNow", "bool", default="true"),
            t("Meshes", "object", MESH, array=True),
            t("Actors", "object", ACTOR, array=True),
            # Fade-out of flare lights (see FADE_SLOTS).
            t("Fading", "bool", default="false"),
            t("FadeBusy", "bool", default="false"),
            t("DueNow", "bool", default="false"),
            t("DueEnd", "float", default="0.0"),
            t("FadeLevel", "float", default="1.0"),
            t("FadeActors", "object", ACTOR, array=True),
            t("FadePoints", "object", POINT, array=True),
            t("Timelines", "object", TIMELINE, array=True),
            t("Parts", "object", PARTICLES, array=True),
        ] + [var for i in range(FADE_SLOTS) for var in (
            t(slot("FadeFlare", i), "object", ACTOR),
            t(slot("FadeStart", i), "float", default="0.0"),
            t(slot("FadeEnd", i), "float", default="0.0"),
        )],
        "functions": [
            {"name": "LoadSettings"}, {"name": "SaveSettings"}, {"name": "ApplySettings"}, {"name": "ApplyCvars"},
            {"name": "Refresh"}, {"name": "ApplyTerrain"},
            {"name": "ApplyFlares", "inputs": [t("FlareClass", "class", ACTOR), t("Range", "float"), t("Count", "float")]},
            {"name": "ApplyLevel"},
            {"name": "ApplyShadowFade"},
            {"name": "ApplyPawn", "inputs": [t("Pawn", "object", PAWN), t("bLocal", "bool")]},
            {"name": "ApplyFlare", "inputs": [t("Flare", "object", ACTOR), t("bUpgrade", "bool"), t("bCast", "bool"),
                                              t("Range", "float")]},
            {"name": "Watch"},
            {"name": "WatchFlares", "inputs": [t("FlareClass", "class", ACTOR), t("Range", "float"), t("Count", "float"),
                                               t("bGun", "bool")]},
            {"name": "PlaceShadowLight", "inputs": [t("Flare", "object", ACTOR), t("Light", "object", POINT)]},
            {"name": "ColourLight", "inputs": [t("Light", "object", "/Script/Engine.LightComponent"), t("Gain", "float")]},
            {"name": "AimSpot", "inputs": [t("Light", "object", SPOT), t("bUpgrade", "bool")]},
            {"name": "StartFades", "inputs": [t("FlareClass", "class", ACTOR), t("bGun", "bool")]},
            {"name": "FlareDue", "inputs": [t("Flare", "object", ACTOR), t("bGun", "bool")]},
            {"name": "IsFading", "inputs": [t("Flare", "object", ACTOR)], "outputs": [t("bFading", "bool")]},
            {"name": "IsLit", "inputs": [t("Flare", "object", ACTOR)], "outputs": [t("bLit", "bool")]},
            {"name": "AddFade", "inputs": [t("Flare", "object", ACTOR), t("Start", "float"), t("End", "float")]},
            {"name": "FadeLights"}, {"name": "StopFades"},
            {"name": "BindGunEnd", "inputs": [t("Flare", "object", ACTOR)]},
            {"name": "GunTail", "inputs": [t("Component", "object", "/Script/Engine.ActorComponent")]},
        ],
        "graphs": {
            "LoadSettings": g_load_settings(), "SaveSettings": g_save_settings(),
            "ApplySettings": g_apply_settings(), "ApplyCvars": g_apply_cvars(), "Refresh": g_refresh(),
            "ApplyFlares": g_apply_flares(), "ApplyShadowFade": g_apply_shadow_fade(), "ApplyFlare": g_apply_flare(), "ApplyTerrain": g_apply_terrain(),
            "ApplyPawn": g_apply_pawn(), "Watch": g_watch(), "WatchFlares": g_watch_flares(),
            "PlaceShadowLight": g_place_shadow_light(), "ApplyLevel": g_apply_level(),
            "ColourLight": g_colour_light(), "AimSpot": g_aim_spot(), "EventGraph": g_mod_events(),
            "StartFades": g_start_fades(), "FlareDue": g_flare_due(), "IsFading": g_is_fading(), "IsLit": g_is_lit(), "AddFade": g_add_fade(),
            "FadeLights": g_fade_lights(), "StopFades": g_stop_fades(),
            "BindGunEnd": g_bind_gun_end(), "GunTail": g_gun_tail(),
        },
    }


# --------------------------------------------------------------------------- Mod Hub adapter

def hub_asset():
    """Registers the mod and its settings page with Mod Hub. Spawned by the mod only when Mod Hub exists."""
    return modhub.hub_asset(HUBMOD, MOD_C, PAGE_C, MOD_NAME, MOD_AUTHOR, MOD_VERSION)


# --------------------------------------------------------------------------- settings page
# The game's look (drgkit.bp.ui, skill drg-design): title, Enabled and Shadow quality, then DETAILED SETTINGS, a bar
# that opens and closes the list of detailed settings (closed when the page is made; two groups, QUALITY and LOOK),
# RESET TO DEFAULTS and an answer line. Widget names: Chk<Name>, Sld<Name> + Val<Name>, BtnReset, BtnDetails,
# DetailRows, Note.

SUBTITLE = "Real shadows with soft edges from headlamps and flares in missions. Every change shows right away."
NOTE = "Settings are saved when Mod Hub closes."
GROUPS = [
    ("Quality", "QUALITY", "Shadow quality sets these. Changing one switches it to Custom.", False),
    ("Look", "LOOK", "Shadow quality does not change these.", True),
]
VISIBILITY = "/Script/UMG.ESlateVisibility"


def label_box(name, label):
    return ui.box("Box" + name, ui.LABEL_WIDTH, slot=ui.hslot(),
                  child=ui.text("Lbl" + name, label.upper(), ui.CARBON, ui.F_LABEL, ui.LIGHT_TEXT))


def check_row(name, label, checked, top):
    return ui.hbox("Row" + name, [label_box(name, label), ui.check_box("Chk" + name, checked, slot=ui.hslot())],
                   slot=ui.vslot(pad=(0, top, 0, 0)))


def slider_row(name, label, low, high, step, value, shown, top):
    return ui.hbox("Row" + name, [
        label_box(name, label),
        ui.slider("Sld" + name, low, high, step, value, slot=ui.hslot(fill=True, pad=(0, 0, 16, 0))),
        ui.box("BoxVal" + name, ui.VALUE_WIDTH, slot=ui.hslot(),
               child=ui.text("Val" + name, shown, ui.CARBON, ui.F_LABEL, ui.ORANGE, var=True, justify="Right",
                             upper=True)),
    ], slot=ui.vslot(pad=(0, top, 0, 0)))


def hint(name, content):
    return ui.text("Hint" + name, content, ui.BODY, ui.F_HINT, ui.LABEL, wrap=True,
                   slot=ui.vslot(pad=(ui.LABEL_WIDTH, 2, 0, 0)))


def shown(d, value):
    """Text next to a detailed slider at build time."""
    if d.all_at is not None and value >= d.all_at:
        return "All"
    return ("%." + str(d.digits) + "f") % value


def group_head(name, title, content, top):
    """A group in the detailed list: its name in orange capitals and one sentence."""
    return [ui.text("Group" + name, title, ui.CARBON, ui.F_LABEL, ui.ORANGE, slot=ui.vslot(pad=(0, top, 0, 0))),
            ui.text("GroupHint" + name, content, ui.BODY, ui.F_HINT, ui.LABEL, wrap=True,
                    slot=ui.vslot(pad=(0, 2, 0, 0)))]


def details_bar():
    """DETAILED SETTINGS: a full-width bar with an orange rule; a click opens or closes the list (SHOW / HIDE)."""
    pad = ui.margin(16, 0, 16, 0)
    style = "(Normal=%s,Hovered=%s,Pressed=%s,Disabled=%s,NormalPadding=%s,PressedPadding=%s)" % (
        ui.btn_brush(ui.HEAD_BG), ui.btn_brush(ui.DARK), ui.btn_brush(ui.DARK_HOVER), ui.btn_brush(ui.HEAD_BG),
        pad, pad)
    head = ui.hbox("DetailsHead", [
        # Rift Soft's capitals sit a little low in its line (see ui.game_button): lift them by 0.08 em.
        ui.text("LblDetails", "DETAILED SETTINGS", ui.RIFT, ui.F_BUTTON, ui.LIGHT_TEXT,
                slot=ui.hslot(fill=True, pad=(0, 0, 0, round(ui.F_BUTTON * 0.08)))),
        ui.text("SignDetails", "SHOW", ui.CARBON, ui.F_LABEL, ui.ORANGE, var=True, slot=ui.hslot()),
    ])
    head["slot"] = {"HorizontalAlignment": "HAlign_Fill", "VerticalAlignment": "VAlign_Center", "Padding": ui.margin()}
    button = ui.w("Button", "BtnDetails", True, {"WidgetStyle": style, "IsFocusable": "False"}, children=[head])
    return ui.vbox("Details", [ui.rule("DetailsRule"), ui.box("DetailsSize", height=ui.BTN_HEIGHT, slot=ui.vslot(),
                                                               child=button)],
                   slot=ui.vslot(pad=(0, 28, 0, 0)))


def page_tree():
    rows = [
        ui.text("Title", MOD_NAME.upper(), ui.RIFT, ui.F_PAGE_TITLE, ui.ORANGE, slot=ui.vslot()),
        ui.text("Subtitle", SUBTITLE, ui.BODY, ui.F_SUBTITLE, ui.LIGHT_TEXT, wrap=True, slot=ui.vslot(pad=(0, 2, 0, 6))),
    ]
    for name, label, text, default in CHECKS:
        rows += [check_row(name, label, default, 18), hint(name, text)]
    for name, label, text, low, high, step, default in SLIDERS:
        value = PRESET_NAMES[int(default)] if name == "Level" else "%.2f" % default
        rows += [slider_row(name, label, low, high, step, default, value, 18), hint(name, text)]
    rows.append(details_bar())
    details = []
    for i, (group, title, content, look) in enumerate(GROUPS):
        details += group_head(group, title, content, 14 if i == 0 else 30)
        for d in DETAILS:
            if d.look != look:
                continue
            if d.check:
                details.append(check_row(d.name, d.label, d.default, 14))
            else:
                details.append(slider_row(d.name, d.label, d.low, d.high, d.step,
                                          min(d.default, d.all_at or d.default), shown(d, d.default), 14))
            details.append(hint(d.name, d.hint))
    rows.append(ui.w("VerticalBox", "DetailRows", True, {"Visibility": "Collapsed"}, ui.vslot(pad=(0, 4, 0, 0)),
                     details))
    rows.append(ui.hbox("ResetRow", [
        ui.game_button("BtnReset", "RESET TO DEFAULTS", ui.F_BUTTON, primary=False, height=ui.BTN_HEIGHT,
                       slot=ui.hslot()),
        ui.text("Note", NOTE, ui.BODY, ui.F_SUBTITLE, ui.LABEL, var=True, slot=ui.hslot(fill=True, pad=(16, 0, 0, 0))),
    ], slot=ui.vslot(pad=(0, 28, 0, 0))))
    return ui.w("ScrollBox", "Root", children=[
        ui.w("VerticalBox", "Rows", slot={"Padding": ui.margin(*ui.PAGE_PAD)}, children=rows)])


def preset_text(g, prefix, value_pin):
    """Output pin: the name of the level (Low ... Ultra, Custom) for a Level value."""
    _, picks = level_index(g, prefix, value_pin, PRESET_NAMES)
    value = None
    for i in reversed(range(len(PRESET_NAMES) - 1)):
        node = "%sPick%d" % (prefix, i)
        g.call(node, KML + ":SelectString", A=PRESET_NAMES[i], bPickA=ref(picks[i]),
               B=ref(value) if value else PRESET_NAMES[-1])
        value = node + ".ReturnValue"
    g.call(prefix + "Txt", KTXT + ":Conv_StringToText", InString=ref(value))
    return prefix + "Txt.ReturnValue"


def number_text(g, prefix, value_pin, digits, all_at=None):
    """Output pin: a slider's value as text; "All" from all_at up."""
    g.call(prefix + "Num", KTXT + ":Conv_FloatToText", Value=ref(value_pin),
           MinimumFractionalDigits=str(digits), MaximumFractionalDigits=str(digits))
    if all_at is None:
        return prefix + "Num.ReturnValue"
    g.call(prefix + "IsAll", KML + ":GreaterEqual_FloatFloat", A=ref(value_pin), B=str(all_at))
    g.call(prefix + "Str", KTXT + ":Conv_TextToString", InText=ref(prefix + "Num.ReturnValue"))
    g.call(prefix + "Pick", KML + ":SelectString", A="All", B=ref(prefix + "Str.ReturnValue"),
           bPickA=ref(prefix + "IsAll.ReturnValue"))
    g.call(prefix + "Txt", KTXT + ":Conv_StringToText", InString=ref(prefix + "Pick.ReturnValue"))
    return prefix + "Txt.ReturnValue"


def value_text(g, prefix, name, value_pin):
    """Output pin: the text next to slider `name` for a value pin."""
    if name == "Level":
        return preset_text(g, prefix, value_pin)
    detail = next((d for d in DETAILS if d.name == name), None)
    if detail is None:
        return number_text(g, prefix, value_pin, 2)
    return number_text(g, prefix, value_pin, detail.digits, detail.all_at)


def widget_call(g, node_id, widget, fn, **pins):
    return g.call(node_id, UMG + fn, target=ref(g.get(node_id + "W", widget)), **pins)


def g_page_sync():
    """Sync: every control shows the mod's settings (SetValue and SetIsChecked fire no events)."""
    g = Graph()
    settings = g.get("getSet", "Settings", MOD_C, g.get("getMod", "Mod"))
    g.call("valid", KSL + ":IsValid", Object=ref(settings))
    g.branch("br", "valid.ReturnValue")
    chain = ["entry", "br"]
    checks = [name for name, *_ in CHECKS] + [d.name for d in DETAILS if d.check]
    sliders = [(name, None) for name, *_ in SLIDERS] + [(d.name, d.all_at) for d in DETAILS if not d.check]
    for name, all_at in sliders:
        value = g.get("get" + name, name, SETTINGS_C, settings)
        shown_value = value
        if all_at is not None:  # ALL_FLARES puts the handle on the top stop
            shown_value = g.call("top" + name, KML + ":FMin", A=ref(value), B=str(all_at)) + ".ReturnValue"
        widget_call(g, "setV" + name, "Sld" + name, "Slider:SetValue", InValue=ref(shown_value))
        widget_call(g, "setT" + name, "Val" + name, "TextBlock:SetText", InText=ref(value_text(g, "sync" + name, name, value)))
        chain += ["setV" + name, "setT" + name]
    for name in checks:
        widget_call(g, "setC" + name, "Chk" + name, "CheckBox:SetIsChecked",
                    InIsChecked=ref(g.get("get" + name, name, SETTINGS_C, settings)))
        chain.append("setC" + name)
    g.flow(*chain)
    return g.data()


def g_set_custom():
    """SetCustom: the player changed a detailed setting; the level becomes Custom (only the slider and its text
    change, the detailed settings stay)."""
    g = Graph()
    settings = g.get("getSet", "Settings", MOD_C, g.get("getMod", "Mod"))
    g.set("setLevel", "Level", SETTINGS_C, settings, default=str(float(CUSTOM)))
    widget_call(g, "setV", "SldLevel", "Slider:SetValue", InValue=str(float(CUSTOM)))
    g.call("txt", KTXT + ":Conv_StringToText", InString=PRESET_NAMES[CUSTOM])
    widget_call(g, "setT", "ValLevel", "TextBlock:SetText", InText=ref("txt.ReturnValue"))
    g.flow("entry", "setLevel", "setV", "setT")
    return g.data()


def g_reset_defaults():
    """ResetDefaults: Enabled, the default level (and so its detailed settings) and the look settings."""
    g = Graph()
    mod = g.get("getMod", "Mod")
    settings = g.get("getSet", "Settings", MOD_C, mod)
    chain = ["entry"]
    for name, _, _, default in CHECKS:
        chain.append(g.set("rst" + name, name, SETTINGS_C, settings, default=str(default).lower()))
    for name, _, _, _, _, _, default in SLIDERS:
        chain.append(g.set("rst" + name, name, SETTINGS_C, settings, default=str(default)))
    for name, default in LOOK_SETTINGS:
        chain.append(g.set("rst" + name, name, SETTINGS_C, settings, default=str(default)))
    g.call("level", MOD_C + ":ApplyLevel", target=ref(mod))
    g.call("sync", "Sync")
    g.call("apply", MOD_C + ":ApplySettings", target=ref(mod))
    g.flow(*chain, "level", "sync", "apply", *modhub.note(g, "note", "Defaults restored.", ui.GOOD))
    return g.data()


def g_toggle_details():
    """ToggleDetails: opens or closes the list of detailed settings."""
    g = Graph()
    g.call("flip", KML + ":Not_PreBool", A=ref(g.get("getOpen", "DetailsOpen")))
    g.set("setOpen", "DetailsOpen", value="flip.ReturnValue")
    open_now = g.get("getOpen2", "DetailsOpen")
    g.node("vis", "select", index="bool", type={"type": "enum", "class": VISIBILITY})
    g.link(open_now, "vis.Index")
    g.defaults["vis.Option 0"] = "Collapsed"
    g.defaults["vis.Option 1"] = "Visible"
    widget_call(g, "show", "DetailRows", "Widget:SetVisibility", InVisibility=ref("vis.ReturnValue"))
    g.call("sign", KML + ":SelectString", A="HIDE", B="SHOW", bPickA=ref(open_now))
    g.call("signTxt", KTXT + ":Conv_StringToText", InString=ref("sign.ReturnValue"))
    widget_call(g, "setSign", "SignDetails", "TextBlock:SetText", InText=ref("signTxt.ReturnValue"))
    g.flow("entry", "setOpen", "show", "setSign")
    return g.data()


def g_page_events():
    g = Graph()
    mod = g.get("getMod", "Mod")
    settings = g.get("getSet", "Settings", MOD_C, mod)

    def apply(node_id):
        return g.call(node_id, MOD_C + ":ApplySettings", target=ref(mod))

    # Main settings. A level writes its detailed settings, and the list shows them.
    for name, *_ in SLIDERS:
        ev = "ev" + name
        g.node(ev, "boundevent", widget="Sld" + name, name="OnValueChanged")
        g.set("set" + name, name, SETTINGS_C, settings, ev + ".Value")
        widget_call(g, "setT" + name, "Val" + name, "TextBlock:SetText", InText=ref(value_text(g, ev, name, ev + ".Value")))
        steps = [ev, "set" + name, "setT" + name]
        if name == "Level":
            steps += [g.call("level" + name, MOD_C + ":ApplyLevel", target=ref(mod)), g.call("sync" + name, "Sync")]
        g.flow(*steps, apply("apply" + name))
    for name, *_ in CHECKS:
        ev = "ev" + name
        g.node(ev, "boundevent", widget="Chk" + name, name="OnCheckStateChanged")
        g.set("set" + name, name, SETTINGS_C, settings, ev + ".bIsChecked")
        g.flow(ev, "set" + name, apply("apply" + name))

    # Detailed settings: the value, then Custom (not for the look settings).
    for d in DETAILS:
        ev = "ev" + d.name
        if d.check:
            g.node(ev, "boundevent", widget="Chk" + d.name, name="OnCheckStateChanged")
            g.set("set" + d.name, d.name, SETTINGS_C, settings, ev + ".bIsChecked")
            steps = [ev, "set" + d.name]
        else:
            g.node(ev, "boundevent", widget="Sld" + d.name, name="OnValueChanged")
            value = ev + ".Value"
            if d.all_at is not None:
                g.call(ev + "IsAll", KML + ":GreaterEqual_FloatFloat", A=ref(value), B=str(d.all_at))
                value = g.call(ev + "Stored", KML + ":SelectFloat", A=str(ALL_FLARES), B=ref(value),
                               bPickA=ref(ev + "IsAll.ReturnValue")) + ".ReturnValue"
            g.set("set" + d.name, d.name, SETTINGS_C, settings, value)
            widget_call(g, "setT" + d.name, "Val" + d.name, "TextBlock:SetText",
                        InText=ref(number_text(g, ev + "T", ev + ".Value", d.digits, d.all_at)))
            steps = [ev, "set" + d.name, "setT" + d.name]
        if not d.look:
            steps.append(g.call("custom" + d.name, "SetCustom"))
        g.flow(*steps, apply("apply" + d.name))

    g.node("evReset", "boundevent", widget="BtnReset", name="OnClicked")
    g.call("reset", "ResetDefaults")
    g.flow("evReset", "reset")
    ui.press_feedback(g, "BtnReset")

    g.node("evDetails", "boundevent", widget="BtnDetails", name="OnClicked")
    g.call("toggle", "ToggleDetails")
    g.flow("evDetails", "toggle")

    g.node("opened", "event", name="HubPageOpened", **{"class": iface("IHubPageWidget")})
    g.call("syncOpen", "Sync")
    g.flow("opened", "syncOpen", *modhub.note(g, "noteOpen", NOTE, ui.LABEL))

    g.node("closed", "event", name="HubPageClosed", **{"class": iface("IHubPageWidget")})
    g.call("save", MOD_C + ":SaveSettings", target=ref(mod))
    g.flow("closed", "save")
    return g.data()


def page_asset():
    graphs = {"Sync": g_page_sync(), "SetCustom": g_set_custom(), "ResetDefaults": g_reset_defaults(),
              "ToggleDetails": g_toggle_details(), "EventGraph": g_page_events(),
              "GetPageInfo": modhub.g_page_info(MOD_NAME), "GetContainerMode": modhub.g_container_mode()}
    for graph in graphs.values():
        problems = dsl.lint(graph)
        assert not problems, problems
    return {
        "kind": "widget", "path": PAGE, "parent": UMG + "UserWidget", "interfaces": [iface("IHubPageWidget")],
        "variables": [t("Mod", "object", MOD_C), t("DetailsOpen", "bool", default="false")],
        "functions": [{"name": "Sync"}, {"name": "SetCustom"}, {"name": "ResetDefaults"}, {"name": "ToggleDetails"}],
        "tree": page_tree(),
        "graphs": graphs,
    }


def spawn_assets():
    # The mod loader spawns actors with these names: InitCave in missions, InitSpacerig on the Space Rig.
    return [
        {"kind": "blueprint", "path": MOD + "InitCave", "parent": MOD_C},
        {"kind": "blueprint", "path": MOD + "InitSpacerig", "parent": MOD_C,
         "class_defaults": {"ActiveInLevel": "False"}},
    ]


def main():
    assets = [settings_asset(), mod_asset(), page_asset(), hub_asset()] + spawn_assets()
    with open(sys.argv[1], "w", encoding="utf-8") as out:
        json.dump({"assets": assets}, out, indent=1)
    print("wrote %s (%d assets)" % (sys.argv[1], len(assets)))


if __name__ == "__main__":
    main()
