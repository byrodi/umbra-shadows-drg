"""Writes the BPForge spec (JSON) for the Umbra mod: real shadows with soft edges from headlamps and flares.

Usage: python umbra_spec.py <out.json>
The spec is the source of the mod's Blueprints. Edit here, then run Tools/build_assets.py.

How it fits the other mods (read from their cooked Blueprints, see README "Other mods"):
- Pretty Flashlights adds its own headlamp spot lights and never turns their shadows on by itself.
- Advanced Darkness changes light colour, range and fog, and leaves shadow settings alone.
- Mod Hub hides terrain shadows by default.
So this mod only sets shadow properties, on a fixed number of lights, and nothing the others reset.
"""
import json
import math
import sys

HUB = "/Game/_ModHub/"
MOD = "/Game/_Umbra/"

KSL = "/Script/Engine.KismetSystemLibrary"
KML = "/Script/Engine.KismetMathLibrary"
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
UMG = "/Script/UMG."
LIGHT = "/Script/Engine.LightComponent"
TIMELINE = "/Script/Engine.TimelineComponent"
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
MOD_NAME = "Umbra Shadows"  # shown in Mod Hub; internal paths and the save slot keep "Umbra"
MOD_AUTHOR = "rodionmasalov"
MOD_VERSION = "0.2.0"

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
HAND_FILL_Z, GUN_FILL_X = 20.0, 3.23457  # where the game puts the fill light on the flare
# Intensity variables of the game's flares (ITM_* BaseIntensity = the fill's template intensity per class;
# PRJ_FlareGun_Projectile01 LightIntensity_Point / LightIntensity_Spot).
HAND_BASE = {"Small_Engineer": 12.0, "Small_Driller": 5.0, "Flare_Small": 10.0, "default": 4.0}
HAND_SPOT_SHARE = 1.6        # hand flare: spots = 1.6 x fill
HAND_TOTAL = 1.0 + HAND_SPOT_SHARE
GUN_POINT_BASE, GUN_SPOT_BASE = 3.5, 35.0
GUN_TOTAL = GUN_POINT_BASE + GUN_SPOT_BASE
# Hue of each class: the colour the game gives the glowing flare model of that class
# (M_Flare_Glow_<Class>_inst, DynamicTint2), scaled so the brightest channel is 1. Scout also covers the flare gun.
# Light colour = lerp(white, hue, Class colour): pastel at the default. The light of the game's flares has
# other colours (Scout orange, Engineer and Driller blue, Gunner green); Class colour 0 keeps those.
CLASS_HUE = {
    "Driller": "(R=1.0,G=0.855,B=0.0,A=1.0)",
    "Engineer": "(R=1.0,G=0.0,B=0.0,A=1.0)",
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
GUN_FADE_FROM = 80.0         # flare gun: Light_Anim position (0 to 90) where the fade starts
GUN_LIGHT_END, GUN_TIMELINE_END = 88.0, 90.0  # the flare goes out at 88; the game plays 88 to 90 at rate 1, then hides
GUN_AFTER = 2.0              # s from 88 to 90 at play rate 1
FADE_MARGIN = 0.15           # s; a gun flare's fade ends this much before the game hides its lights
FADE_HOLD = 1.0              # s the mod keeps a faded light at zero, until the game has hidden it
FADE_POWER = 3.0
TICK_GROUP = "TG_PostUpdateWork"  # after actor, timeline, timer and subsystem ticks: the mod's value wins

# name, label, hint, default
CHECKS = [
    ("Enabled", "Enabled", "Off returns lights to the game's own shadow settings.", True),
    ("OwnLamp", "Own headlamp shadows", "Your headlamp casts shadows. They show as dark rims behind things.", True),
    ("TeamLamps", "Team headlamp shadows", "Other dwarves' headlamps cast shadows.", True),
    ("SoftShadows", "Soft penumbra", "Headlamp shadow edges are sharp at the contact and softer with distance.", True),
    ("TerrainShadows", "Cave walls cast shadows", "Overrides Mod Hub's 'hide shadows on terrain'. Needed for most shadows.", True),
    ("LightShafts", "Light shafts in fog", "Shadow flares also shadow the volumetric fog (Advanced Darkness). Costs GPU time.", False),
]
# name, label, hint, min, max, step, default
SLIDERS = [
    ("ShadowDistance", "Shadow distance", "Metres, about. Flare shadows fade out smoothly beyond this. Lower gives more FPS.", 10.0, 60.0, 5.0, 25.0),
    ("FlareRange", "Flare shadow range", "Metres. How far the shadow light of a flare reaches.", 8.0, 20.0, 1.0, 14.0),
    ("GunFlareRange", "Flare gun shadow range", "Metres. How far the shadow light of a flare gun flare reaches.", 10.0, 30.0, 1.0, 20.0),
    ("FlareColour", "Class colour", "Hand flares take the colour of the dwarf's class. 0 game colours, 1 full colour, up to 2 brighter colour. The flare gun keeps its own light.", 0.0, 2.0, 0.05, 1.0),
    ("FlareBrightness", "Flare brightness", "Flare light compared with the game. Coloured light is raised to the same brightness.", 0.5, 2.0, 0.05, 1.0),
    ("ShadowStrength", "Flare shadow strength", "Share of a shadow flare's light that casts shadows. Lower lifts the shadows.", 0.4, 1.0, 0.05, 0.75),
    ("Penumbra", "Penumbra size", "Size of the headlamp light source. Bigger gives wider soft edges.", 0.0, 3.0, 0.1, 1.0),
    ("Quality", "Shadow resolution", "0 game setting, 1 = 1024, 2 = 2048, 3 = 4096. Higher costs GPU time.", 0.0, 3.0, 1.0, 0.0),
]


def iface(name):
    return HUB + name + "." + name + "_C"


def t(name, typ, cls=None, **extra):
    out = {"name": name, "type": typ}
    if cls:
        out["class"] = cls
    out.update(extra)
    return out


class Graph:
    """Small helper to write nodes, links and pin defaults."""

    def __init__(self):
        self.nodes, self.links, self.defaults = [], [], {}
        self.settings = None

    def node(self, node_id, kind, **fields):
        self.nodes.append(dict(id=node_id, k=kind, **fields))
        return node_id

    def call(self, node_id, fn, **pins):
        """Function call. Pin values made with ref() are links, everything else is a pin default."""
        self.node(node_id, "call", fn=fn)
        for pin, value in pins.items():
            pin = "self" if pin == "target" else pin  # the object the function is called on
            if isinstance(value, str) and value.startswith("@"):
                self.link(value[1:], "%s.%s" % (node_id, pin))
            else:
                self.defaults["%s.%s" % (node_id, pin)] = value
        return node_id

    def get(self, node_id, var, cls=None, target=None):
        self.node(node_id, "get", var=var, **({"class": cls} if cls else {}))
        if target:
            self.link(target, node_id + ".self")
        return node_id + "." + var

    def set(self, node_id, var, cls=None, target=None, value=None, default=None):
        self.node(node_id, "set", var=var, **({"class": cls} if cls else {}))
        if target:
            self.link(target, node_id + ".self")
        if value:
            self.link(value, node_id + "." + var)
        if default is not None:
            self.defaults["%s.%s" % (node_id, var)] = default
        return node_id

    def setting(self, name):
        """Output pin with the value of a setting (reads Settings once per graph)."""
        if self.settings is None:
            self.settings = self.get("getSettings", "Settings")
        return self.get("setting" + name, name, SETTINGS_C, self.settings)

    def loop(self, node_id, array):
        self.node(node_id, "macro", name="ForEachLoop")
        self.link(array, node_id + ".Array")
        return node_id + ".Array Element"

    def branch(self, node_id, condition):
        self.node(node_id, "branch")
        self.link(condition, node_id + ".Condition")
        return node_id

    def link(self, a, b):
        self.links.append([a, b])

    def flow(self, *steps):
        """Chain execution: each step is a node id, or 'node.pin' for a non-default pin."""
        for a, b in zip(steps, steps[1:]):
            out_pin = a if "." in a else a + ".then"
            in_pin = b if "." in b else b + ".execute"
            self.link(out_pin, in_pin)

    def data(self):
        return {"nodes": self.nodes, "links": self.links, "defaults": self.defaults}


def ref(pin):
    """Marks a call argument as a link to another node's pin."""
    return "@" + pin


# --------------------------------------------------------------------------- settings object

def settings_asset():
    variables = [t(name, "bool", default=str(default).lower()) for name, _, _, default in CHECKS]
    variables += [t(name, "float", default=str(default)) for name, _, _, _, _, _, default in SLIDERS]
    return {"kind": "blueprint", "path": SETTINGS, "parent": "/Script/Engine.SaveGame", "variables": variables}


# --------------------------------------------------------------------------- mod actor

def g_load_settings():
    g = Graph()
    g.call("load", GS + ":LoadGameFromSlot", SlotName=SAVE_SLOT, UserIndex="0")
    g.node("castL", "cast", **{"class": SETTINGS_C})
    g.link("load.ReturnValue", "castL.Object")
    g.set("setL", "Settings", value="castL.$cast")
    g.call("create", GS + ":CreateSaveGameObject", SaveGameClass=SETTINGS_C)
    g.node("castC", "cast", **{"class": SETTINGS_C})
    g.link("create.ReturnValue", "castC.Object")
    g.set("setC", "Settings", value="castC.$cast")
    g.flow("entry", "load", "castL", "setL")
    g.flow("castL.CastFailed", "create", "castC", "setC")
    return g.data()


def g_save_settings():
    g = Graph()
    g.call("save", GS + ":SaveGameToSlot", SlotName=SAVE_SLOT, UserIndex="0", SaveGameObject=ref(g.get("getS", "Settings")))
    g.flow("entry", "save")
    return g.data()


def g_apply_settings():
    g = Graph()
    g.call("cvars", "ApplyCvars")
    g.call("refresh", "Refresh")
    g.call("terrain", "ApplyTerrain")
    g.flow("entry", "cvars", "refresh", "terrain")
    return g.data()


def g_apply_cvars():
    """Shadow filter and, if asked, shadow map size. Console variables stay until the game restarts."""
    g = Graph()
    g.call("soft", KML + ":BooleanAND", A=ref(g.setting("Enabled")), B=ref(g.setting("SoftShadows")))
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
    g.call("flares", "ApplyFlares", FlareClass=FLARE, Range=ref(g.setting("FlareRange")))
    g.call("gunFlares", "ApplyFlares", FlareClass=GUN_FLARE, Range=ref(g.setting("GunFlareRange")))
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


def g_apply_flares():
    """Every flare of one kind gets the same light and shadow. No picking: the cost is limited by the
    engine's shadow fade with distance (see ApplyCvars)."""
    g = Graph()
    g.call("all", GS + ":GetAllActorsOfClass", ActorClass=ref("entry.FlareClass"))
    g.set("keep", "Actors", value="all.OutActors")
    flare = g.loop("each", g.get("getActors", "Actors"))
    g.call("apply", "ApplyFlare", Flare=ref(flare), bUpgrade=ref(g.setting("Enabled")), bCast="true", Range=ref("entry.Range"))
    g.flow("entry", "all", "keep", "each.Exec")
    g.flow("each.LoopBody", "apply")
    return g.data()


def gun_spot_tilted(pitch, yaw):
    """Rotation of a flare gun spot light after tilting the ring GUN_TILT degrees back (towards -X, out of the wall)."""
    p, y, b = math.radians(pitch), math.radians(yaw), math.radians(GUN_TILT)
    d = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))
    n = (-math.sin(b), math.cos(b) * d[1], math.cos(b) * d[2])  # the game's ring is the YZ plane (d[0] = 0)
    return round(math.degrees(math.asin(n[2])), 3), round(math.degrees(math.atan2(n[1], n[0])), 3)


def g_watch():
    """Runs ten times a second: new flares, and flares the game has just reset, get the mod's light at once.
    Flares whose light is about to end start their fade-out."""
    g = Graph()
    g.call("on", KML + ":BooleanAND", A=ref(g.get("getActive", "ActiveInLevel")), B=ref(g.setting("Enabled")))
    g.branch("br", "on.ReturnValue")
    g.call("hand", "WatchFlares", FlareClass=FLARE, Range=ref(g.setting("FlareRange")))
    g.call("gun", "WatchFlares", FlareClass=GUN_FLARE, Range=ref(g.setting("GunFlareRange")))
    g.call("fadeHand", "StartFades", FlareClass=FLARE, bGun="false")
    g.call("fadeGun", "StartFades", FlareClass=GUN_FLARE, bGun="true")
    g.flow("entry", "br", "hand", "gun", "fadeHand", "fadeGun")
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
    """Flares of one kind whose light is about to end get a fade slot. Each of the mod's lights keeps its present
    level, the start of its fade, in IESBrightnessScale: a property used only with an IES light profile (flare
    lights have none)."""
    g = Graph()
    g.call("all", GS + ":GetAllActorsOfClass", ActorClass=ref("entry.FlareClass"))
    g.set("keep", "FadeActors", value="all.OutActors")
    flare = g.loop("each", g.get("getActors", "FadeActors"))
    g.call("due", "FlareDue", Flare=ref(flare), bGun=ref("entry.bGun"))
    g.branch("brDue", g.get("getDue", "DueNow"))
    g.call("known", "IsFading", Flare=ref(flare))
    g.branch("brKnown", "known.bFading")
    g.call("lights", ACTOR + ":K2_GetComponentsByClass", ComponentClass=POINT, target=ref(flare))
    g.set("keepLights", "FadePoints", value="lights.ReturnValue")
    light = g.loop("eachLight", g.get("getLights", "FadePoints"))
    g.branch("brMine", is_mod_light(g, "mine", light))
    g.call("store", KSL + ":SetFloatPropertyByName", Object=ref(light), PropertyName="IESBrightnessScale",
           Value=ref(g.get("level", "Intensity", LIGHT_BASE, light)))
    g.call("now", GS + ":GetTimeSeconds")
    g.call("add", "AddFade", Flare=ref(flare), Start=ref("now.ReturnValue"), End=ref(g.get("getEnd", "DueEnd")))
    g.flow("entry", "all", "keep", "each.Exec")
    g.flow("each.LoopBody", "due", "brDue", "known")
    g.flow("known", "brKnown")
    g.flow("brKnown.else", "keepLights", "eachLight.Exec")
    g.flow("eachLight.LoopBody", "brMine", "store")
    g.flow("eachLight.Completed", "add")
    return g.data()


def g_flare_due():
    """Is the light of this flare about to end? Sets DueNow, and DueEnd: the game time the fade reaches zero.

    Hand flare: its light runs for Duration from the throw (native code), so the fade starts HAND_FADE_LEAD
    before that and ends HAND_FADE_AFTER after it. Flare gun flare: read from its light timeline, whose
    play rate is 88 / Duration until the flare goes out at 88, and 1 for the last stretch to 90.
    """
    g = Graph()
    g.set("clear", "DueNow", default="false")
    g.branch("brKind", "entry.bGun")
    g.flow("entry", "clear", "brKind")
    g.call("now", GS + ":GetTimeSeconds")

    # --- flare gun flare
    g.call("timelines", ACTOR + ":K2_GetComponentsByClass", ComponentClass=TIMELINE, target=ref("entry.Flare"))
    g.set("keep", "Timelines", value="timelines.ReturnValue")
    timeline = g.loop("each", g.get("getTimelines", "Timelines"))
    g.call("pos", TIMELINE + ":GetPlaybackPosition", target=ref(timeline))
    g.call("rate", KML + ":FMax", A=ref(g.call("rateNow", TIMELINE + ":GetPlayRate", target=ref(timeline)) + ".ReturnValue"), B="0.1")
    g.call("playing", TIMELINE + ":IsPlaying", target=ref(timeline))
    g.call("length", TIMELINE + ":GetTimelineLength", target=ref(timeline))
    g.call("late", KML + ":GreaterEqual_FloatFloat", A=ref("pos.ReturnValue"), B=str(GUN_FADE_FROM))
    g.call("isLight", KML + ":GreaterEqual_FloatFloat", A=ref("length.ReturnValue"), B=str(GUN_TIMELINE_END - 1.0))
    g.call("gunOk1", KML + ":BooleanAND", A=ref("playing.ReturnValue"), B=ref("late.ReturnValue"))
    g.call("gunOk", KML + ":BooleanAND", A=ref("gunOk1.ReturnValue"), B=ref("isLight.ReturnValue"))
    g.branch("brGun", "gunOk.ReturnValue")
    # Still burning: to 88 at this rate, then 2 s at rate 1. Already out: to 90 at this rate.
    g.call("toOut", KML + ":Divide_FloatFloat", B=ref("rate.ReturnValue"),
           A=ref(g.call("toOutPos", KML + ":Subtract_FloatFloat", A=str(GUN_LIGHT_END), B=ref("pos.ReturnValue")) + ".ReturnValue"))
    g.call("burning", KML + ":Add_FloatFloat", A=ref("toOut.ReturnValue"), B=str(GUN_AFTER))
    g.call("toHide", KML + ":Divide_FloatFloat", B=ref("rate.ReturnValue"),
           A=ref(g.call("toHidePos", KML + ":Subtract_FloatFloat", A=str(GUN_TIMELINE_END), B=ref("pos.ReturnValue")) + ".ReturnValue"))
    g.call("isBurning", KML + ":Less_FloatFloat", A=ref("pos.ReturnValue"), B=str(GUN_LIGHT_END))
    g.call("left", KML + ":SelectFloat", A=ref("burning.ReturnValue"), B=ref("toHide.ReturnValue"), bPickA=ref("isBurning.ReturnValue"))
    g.call("gunEnd1", KML + ":Add_FloatFloat", A=ref("now.ReturnValue"), B=ref("left.ReturnValue"))
    g.call("gunEnd", KML + ":Subtract_FloatFloat", A=ref("gunEnd1.ReturnValue"), B=str(FADE_MARGIN))
    g.set("gunSetEnd", "DueEnd", value="gunEnd.ReturnValue")
    g.set("gunDue", "DueNow", default="true")
    g.flow("brKind", "keep", "each.Exec")
    g.flow("each.LoopBody", "brGun", "gunSetEnd", "gunDue")

    # --- hand flare
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
    g.flow("brKind.else", "asFlare", "brHand", "handSetEnd", "handDue")
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
    0 to 1 between FadeStart and FadeEnd. After the fade the lights are kept at zero for FADE_HOLD, then the slot
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
        g.flow(slot("each", i) + ".LoopBody", slot("brMine", i), slot("set", i))
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
    """Cheap check of one kind of flare: does a flare light not reach Range?

    With the mod on, the fill and the spot lights of every flare reach Range. One that does not belongs to a
    new flare, or the game has just set it (it does when a flare ignites or lands), so the whole kind is
    applied again at once.
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
    g.branch("brStale", g.get("getStale", "Stale"))
    g.call("apply", "ApplyFlares", FlareClass=ref("entry.FlareClass"), Range=ref("entry.Range"))
    g.flow("entry", "clear", "all", "keep", "each.Exec")
    g.flow("each.LoopBody", "keepLights", "eachLight.Exec")
    g.flow("eachLight.LoopBody", "brOff", "mark")
    g.flow("each.Completed", "brStale", "apply")
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
    variables: BaseIntensity (hand flare: fill and spots), LightIntensity_Point and LightIntensity_Spot
    (flare gun). The mod sets those variables, so the game's fade-in and flicker stay. The last seconds of
    the light are faded by the mod itself (see FADE_SLOTS).

    Chosen flare (bUpgrade and bCast): the fill becomes the one shadow light, all round, like a real flame:
    reach Range, steeper falloff, lifted 15 cm above the flare, the flare's own mesh casts no shadow.
    The three spot lights cast no shadows and only lift the shadows a little (ShadowStrength sets the share).
    Other flares with the mod on: the game's light without shadows. Both get the class colour, and the
    intensity is raised by 1 / luminance of that colour, so a coloured flare is as bright as a white one.
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
    g.call("big", KML + ":BooleanAND", A=ref("entry.bUpgrade"), B=ref("entry.bCast"))
    strength = g.setting("ShadowStrength")
    g.call("brightWanted", KML + ":Multiply_FloatFloat", A=ref(g.setting("FlareBrightness")), B=ref("extraPick.ReturnValue"))
    g.call("brightLum", KML + ":Divide_FloatFloat", A=ref("brightWanted.ReturnValue"), B=ref("lumSafe.ReturnValue"))
    # Mod on, not chosen: brightness / luminance. Chosen: also the split between shadow light and spots.
    # Hand flare: fill = Base*k, spots = Base*k*1.6 (in the game). Total in the game = 2.6 * Base.
    g.call("handBig", KML + ":Multiply_FloatFloat", A=ref("brightLum.ReturnValue"),
           B=ref(g.call("handBigS", KML + ":Multiply_FloatFloat", A=str(HAND_TOTAL), B=ref(strength)) + ".ReturnValue"))
    g.call("gunPointBig", KML + ":Multiply_FloatFloat", A=ref("brightLum.ReturnValue"),
           B=ref(g.call("gunPointS", KML + ":Multiply_FloatFloat", A=str(GUN_TOTAL / GUN_POINT_BASE), B=ref(strength)) + ".ReturnValue"))
    g.call("weak", KML + ":Subtract_FloatFloat", A="1.0", B=ref(strength))
    g.call("gunSpotBig", KML + ":Multiply_FloatFloat", A=ref("brightLum.ReturnValue"),
           B=ref(g.call("gunSpotS", KML + ":Multiply_FloatFloat", A=str(GUN_TOTAL / GUN_SPOT_BASE), B=ref("weak.ReturnValue")) + ".ReturnValue"))
    # Hand flare spots share the fill's BaseIntensity, so they are dimmed through their colour instead.
    g.call("handAmbient", KML + ":Divide_FloatFloat", A=ref(g.call("handWeak", KML + ":Multiply_FloatFloat", A=str(1.0 / HAND_SPOT_SHARE),
                                                                     B=ref("weak.ReturnValue")) + ".ReturnValue"),
           B=ref(strength))
    g.call("handAmbientClamp", KML + ":FClamp", Value=ref("handAmbient.ReturnValue"), Min="0.0", Max="1.0")

    def pick(node_id, big, upgraded):
        """big if chosen, upgraded if mod on, 1 if mod off."""
        g.call(node_id + "On", KML + ":SelectFloat", A=ref(big), B=ref(upgraded), bPickA=ref("big.ReturnValue"))
        g.call(node_id, KML + ":SelectFloat", A=ref(node_id + "On.ReturnValue"), B="1.0", bPickA=ref("entry.bUpgrade"))
        return node_id + ".ReturnValue"

    hand_boost = pick("handBoost", "handBig.ReturnValue", "brightLum.ReturnValue")
    point_boost = pick("pointBoost", "gunPointBig.ReturnValue", "brightLum.ReturnValue")
    spot_boost = pick("spotBoost", "gunSpotBig.ReturnValue", "brightLum.ReturnValue")
    g.call("ambientGain", KML + ":SelectFloat", A=ref("handAmbientClamp.ReturnValue"), B="1.0", bPickA=ref("big.ReturnValue"))
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
    g.call("pointI", KML + ":Multiply_FloatFloat", A=str(GUN_POINT_BASE), B=ref(point_boost))
    g.call("spotI", KML + ":Multiply_FloatFloat", A=str(GUN_SPOT_BASE), B=ref(spot_boost))
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
    g.branch("brUpgrade", "big.ReturnValue")
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
    g.call("fillCast", LIGHT_BASE + ":SetCastShadows", target=ref(fill), bNewValue="true")
    g.call("fillColour", "ColourLight", Light=ref(fill), Gain="1.0")
    # Lift the light above the flare in world space: its own place (20 cm off the flare's axis) may be in the floor.
    g.call("flareAt", ACTOR + ":K2_GetActorLocation", target=ref(flare))
    g.call("lifted", KML + ":Add_VectorVector", A=ref("flareAt.ReturnValue"), B="0.0,0.0,%s" % SHADOW_LIGHT_LIFT)
    g.call("fillLift", "/Script/Engine.SceneComponent:K2_SetWorldLocation", target=ref(fill),
           NewLocation=ref("lifted.ReturnValue"), bSweep="false", bTeleport="true")
    # Never move a light that is the flare's root: that would move the flare.
    g.call("root", ACTOR + ":K2_GetRootComponent", target=ref(flare))
    g.call("isRoot", KML + ":EqualEqual_ObjectObject", A=ref(fill), B=ref("root.ReturnValue"))
    g.branch("brRoot", "isRoot.ReturnValue")
    g.flow("brShadow", "fillRange", "fillFalloff", "fillRes", "fillBias", "fillSlope", "fillSetSource", "fillShafts",
           "fillCast", "fillColour", "brRoot")
    g.flow("brRoot.else", "fillLift")

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
    g.node("tick", "event", name="ReceiveTick", **{"class": ACTOR})
    g.call("fade", "FadeLights")
    g.flow("tick", "fade")

    # Settings page: only if Mod Hub is installed. The paths are built from strings at run time,
    # so this Blueprint has no import of Mod Hub and loads without it.
    def soft_load(node_id, path):
        g.call(node_id + "Path", KSL + ":MakeSoftClassPath", PathString=path)
        g.call(node_id + "Ref", KSL + ":Conv_SoftClassPathToSoftClassRef", SoftClassPath=ref(node_id + "Path.ReturnValue"))
        g.call(node_id, KSL + ":LoadClassAsset_Blocking", AssetClass=ref(node_id + "Ref.ReturnValue"))

    soft_load("hubApi", iface("IHubMod"))
    g.call("hubValid", KSL + ":IsValidClass", Class=ref("hubApi.ReturnValue"))
    g.branch("brHub", "hubValid.ReturnValue")
    soft_load("hubClass", HUBMOD_C)
    g.node("asActor", "classcast", **{"class": ACTOR})
    g.link("hubClass.ReturnValue", "asActor.Class")
    g.call("xform", KML + ":MakeTransform")
    g.call("spawn", GS + ":BeginDeferredActorSpawnFromClass", ActorClass=ref("asActor.$cast"),
           SpawnTransform=ref("xform.ReturnValue"), Owner=ref("me.self"))
    g.call("finish", GS + ":FinishSpawningActor", Actor=ref("spawn.ReturnValue"), SpawnTransform=ref("xform.ReturnValue"))
    g.flow("begin", "load", "cvars", "tickGroup", "tickOff", "timer", "watchTimer", "refresh", "hubApi", "brHub", "hubClass",
           "asActor", "spawn", "finish")
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
        ] + [var for i in range(FADE_SLOTS) for var in (
            t(slot("FadeFlare", i), "object", ACTOR),
            t(slot("FadeStart", i), "float", default="0.0"),
            t(slot("FadeEnd", i), "float", default="0.0"),
        )],
        "functions": [
            {"name": "LoadSettings"}, {"name": "SaveSettings"}, {"name": "ApplySettings"}, {"name": "ApplyCvars"},
            {"name": "Refresh"}, {"name": "ApplyTerrain"},
            {"name": "ApplyFlares", "inputs": [t("FlareClass", "class", ACTOR), t("Range", "float")]},
            {"name": "ApplyShadowFade"},
            {"name": "ApplyPawn", "inputs": [t("Pawn", "object", PAWN), t("bLocal", "bool")]},
            {"name": "ApplyFlare", "inputs": [t("Flare", "object", ACTOR), t("bUpgrade", "bool"), t("bCast", "bool"),
                                              t("Range", "float")]},
            {"name": "Watch"},
            {"name": "WatchFlares", "inputs": [t("FlareClass", "class", ACTOR), t("Range", "float")]},
            {"name": "ColourLight", "inputs": [t("Light", "object", "/Script/Engine.LightComponent"), t("Gain", "float")]},
            {"name": "AimSpot", "inputs": [t("Light", "object", SPOT), t("bUpgrade", "bool")]},
            {"name": "StartFades", "inputs": [t("FlareClass", "class", ACTOR), t("bGun", "bool")]},
            {"name": "FlareDue", "inputs": [t("Flare", "object", ACTOR), t("bGun", "bool")]},
            {"name": "IsFading", "inputs": [t("Flare", "object", ACTOR)], "outputs": [t("bFading", "bool")]},
            {"name": "AddFade", "inputs": [t("Flare", "object", ACTOR), t("Start", "float"), t("End", "float")]},
            {"name": "FadeLights"}, {"name": "StopFades"},
        ],
        "graphs": {
            "LoadSettings": g_load_settings(), "SaveSettings": g_save_settings(),
            "ApplySettings": g_apply_settings(), "ApplyCvars": g_apply_cvars(), "Refresh": g_refresh(),
            "ApplyFlares": g_apply_flares(), "ApplyShadowFade": g_apply_shadow_fade(), "ApplyFlare": g_apply_flare(), "ApplyTerrain": g_apply_terrain(),
            "ApplyPawn": g_apply_pawn(), "Watch": g_watch(), "WatchFlares": g_watch_flares(),
            "ColourLight": g_colour_light(), "AimSpot": g_aim_spot(), "EventGraph": g_mod_events(),
            "StartFades": g_start_fades(), "FlareDue": g_flare_due(), "IsFading": g_is_fading(), "AddFade": g_add_fade(),
            "FadeLights": g_fade_lights(), "StopFades": g_stop_fades(),
        },
    }


# --------------------------------------------------------------------------- Mod Hub adapter

def g_hub_events():
    g = Graph()
    g.node("begin", "event", name="ReceiveBeginPlay", **{"class": ACTOR})
    g.call("owner", ACTOR + ":GetOwner")
    g.node("asMod", "cast", **{"class": MOD_C})
    g.link("owner.ReturnValue", "asMod.Object")
    g.set("setCore", "Core", value="asMod.$cast")
    g.flow("begin", "asMod", "setCore")

    g.node("closed", "event", name="ModHubClosed", **{"class": iface("IHubMod")})
    g.call("save", MOD_C + ":SaveSettings", target=ref(g.get("getCore", "Core")))
    g.flow("closed", "save")
    return g.data()


def g_mod_info():
    g = Graph()
    g.flow("entry", "result")
    g.defaults.update({"result.ModName": MOD_NAME, "result.ModAuthor": MOD_AUTHOR, "result.ModVersion": MOD_VERSION})
    return g.data()


def g_mod_pages():
    """Creates the settings page on first request and hands it to the hub."""
    g = Graph()
    g.call("valid", KSL + ":IsValid", Object=ref(g.get("getPage", "Page")))
    g.branch("br", "valid.ReturnValue")
    g.call("create", UMG + "WidgetBlueprintLibrary:Create", WidgetType=PAGE_C)
    g.set("setPage", "Page", value="create.ReturnValue")
    g.node("cast", "cast", **{"class": PAGE_C})
    g.link(g.get("getPage2", "Page"), "cast.Object")
    g.set("setMod", "Mod", PAGE_C, "cast.$cast", g.get("getCore", "Core"))
    g.call("sync", PAGE_C + ":Sync", target=ref("cast.$cast"))
    g.node("arr", "makearray", n=1)
    g.link("arr.Array", "result.HubPages")
    g.link("cast.$cast", "arr.[0]")
    g.flow("entry", "br", "cast", "setMod", "sync", "result")
    g.flow("br.else", "create", "setPage", "cast")
    g.flow("cast.CastFailed", "result")
    return g.data()


def hub_asset():
    """Registers the mod and its settings page with Mod Hub. Spawned by the mod only when Mod Hub exists."""
    return {
        "kind": "blueprint", "path": HUBMOD, "parent": ACTOR, "interfaces": [iface("IHubMod")],
        "variables": [t("Core", "object", MOD_C), t("Page", "object", UMG + "UserWidget")],
        "graphs": {"EventGraph": g_hub_events(), "GetModInfo": g_mod_info(), "GetModPages": g_mod_pages()},
    }


# --------------------------------------------------------------------------- settings page

WHITE = "(SpecifiedColor=(R=1.0,G=1.0,B=1.0,A=1.0))"
GREY = "(SpecifiedColor=(R=0.55,G=0.55,B=0.55,A=1.0))"
AMBER = "(SpecifiedColor=(R=1.0,G=0.62,B=0.1,A=1.0))"
LABEL_WIDTH = 260


def text(name, content, size, colour=WHITE, var=False, slot=None):
    return {"class": UMG + "TextBlock", "name": name, "var": var,
            "props": {"Text": content, "Font": "(Size=%d)" % size, "ColorAndOpacity": colour},
            "slot": slot or {}}


def sized(name, width, child):
    return {"class": UMG + "SizeBox", "name": name,
            "props": {"WidthOverride": str(width), "bOverride_WidthOverride": "True"},
            "slot": {"VerticalAlignment": "VAlign_Center"}, "children": [child]}


def page_tree():
    pad = {"Padding": "(Left=0,Top=4,Right=0,Bottom=4)"}
    hint_pad = {"Padding": "(Left=0,Top=0,Right=0,Bottom=10)"}
    rows = [
        text("Title", "UMBRA SHADOWS", 26, AMBER, slot=pad),
        text("Subtitle", "Real shadows with soft edges from headlamps and flares. Changes apply at once in a mission.",
             13, GREY, slot={"Padding": "(Left=0,Top=0,Right=0,Bottom=14)"}),
    ]
    for name, label, hint, _ in CHECKS:
        rows.append({"class": UMG + "HorizontalBox", "name": "Row" + name, "slot": pad, "children": [
            sized("Box" + name, LABEL_WIDTH, text("Lbl" + name, label, 16)),
            {"class": UMG + "CheckBox", "name": "Chk" + name, "var": True, "slot": {"VerticalAlignment": "VAlign_Center"}},
        ]})
        rows.append(text("Hint" + name, hint, 12, GREY, slot=hint_pad))
    for name, label, hint, low, high, step, default in SLIDERS:
        rows.append({"class": UMG + "HorizontalBox", "name": "Row" + name, "slot": pad, "children": [
            sized("Box" + name, LABEL_WIDTH, text("Lbl" + name, label, 16)),
            {"class": UMG + "Slider", "name": "Sld" + name, "var": True,
             "props": {"MinValue": str(low), "MaxValue": str(high), "StepSize": str(step), "MouseUsesStep": "True",
                       "Value": str(default)},
             "slot": {"Size": "(Value=1.0,SizeRule=Fill)", "VerticalAlignment": "VAlign_Center",
                      "Padding": "(Left=12,Top=0,Right=12,Bottom=0)"}},
            sized("BoxVal" + name, 70, text("Val" + name, str(default), 16, AMBER, var=True)),
        ]})
        rows.append(text("Hint" + name, hint, 12, GREY, slot=hint_pad))
    rows.append({"class": UMG + "Button", "name": "BtnReset", "var": True,
                 "slot": {"HorizontalAlignment": "HAlign_Left", "Padding": "(Left=0,Top=10,Right=0,Bottom=0)"},
                 "children": [text("LblReset", "Reset to defaults", 14, "(SpecifiedColor=(R=0.02,G=0.02,B=0.02,A=1.0))")]})
    return {"class": UMG + "ScrollBox", "name": "Root",
            "children": [{"class": UMG + "VerticalBox", "name": "Rows", "children": rows}]}


def g_page_sync():
    g = Graph()
    settings = g.get("getSet", "Settings", MOD_C, g.get("getMod", "Mod"))
    g.call("valid", KSL + ":IsValid", Object=ref(settings))
    g.branch("br", "valid.ReturnValue")
    chain = ["entry", "br"]
    for name, *_ in SLIDERS:
        value = g.get("get" + name, name, SETTINGS_C, settings)
        g.call("setV" + name, UMG + "Slider:SetValue", target=ref(g.get("sld" + name, "Sld" + name)), InValue=ref(value))
        g.call("txt" + name, KTXT + ":Conv_FloatToText", MaximumFractionalDigits="2", Value=ref(value))
        g.call("setT" + name, UMG + "TextBlock:SetText", target=ref(g.get("val" + name, "Val" + name)),
               InText=ref("txt%s.ReturnValue" % name))
        chain += ["setV" + name, "setT" + name]
    for name, *_ in CHECKS:
        g.call("setC" + name, UMG + "CheckBox:SetIsChecked", target=ref(g.get("chk" + name, "Chk" + name)),
               InIsChecked=ref(g.get("get" + name, name, SETTINGS_C, settings)))
        chain.append("setC" + name)
    g.flow(*chain)
    return g.data()


def g_page_events():
    g = Graph()
    mod = g.get("getMod", "Mod")
    settings = g.get("getSet", "Settings", MOD_C, mod)

    def apply(node_id):
        return g.call(node_id, MOD_C + ":ApplySettings", target=ref(mod))

    for name, *_ in SLIDERS:
        g.node("ev" + name, "boundevent", widget="Sld" + name, name="OnValueChanged")
        g.set("set" + name, name, SETTINGS_C, settings, "ev%s.Value" % name)
        g.call("txt" + name, KTXT + ":Conv_FloatToText", MaximumFractionalDigits="2", Value=ref("ev%s.Value" % name))
        g.call("setT" + name, UMG + "TextBlock:SetText", target=ref(g.get("val" + name, "Val" + name)),
               InText=ref("txt%s.ReturnValue" % name))
        g.flow("ev" + name, "set" + name, "setT" + name, apply("apply" + name))

    for name, *_ in CHECKS:
        g.node("ev" + name, "boundevent", widget="Chk" + name, name="OnCheckStateChanged")
        g.set("set" + name, name, SETTINGS_C, settings, "ev%s.bIsChecked" % name)
        g.flow("ev" + name, "set" + name, apply("apply" + name))

    g.node("evReset", "boundevent", widget="BtnReset", name="OnClicked")
    chain = ["evReset"]
    for name, _, _, default in CHECKS:
        g.set("rst" + name, name, SETTINGS_C, settings, default=str(default).lower())
        chain.append("rst" + name)
    for name, _, _, _, _, _, default in SLIDERS:
        g.set("rst" + name, name, SETTINGS_C, settings, default=str(default))
        chain.append("rst" + name)
    g.call("syncReset", "Sync")
    g.flow(*chain, "syncReset", apply("applyReset"))

    g.node("opened", "event", name="HubPageOpened", **{"class": iface("IHubPageWidget")})
    g.call("syncOpen", "Sync")
    g.flow("opened", "syncOpen")

    g.node("closed", "event", name="HubPageClosed", **{"class": iface("IHubPageWidget")})
    g.call("save", MOD_C + ":SaveSettings", target=ref(mod))
    g.flow("closed", "save")
    return g.data()


def page_asset():
    info = Graph()
    info.flow("entry", "result")
    info.defaults["result.PageName"] = MOD_NAME
    mode = Graph()
    mode.flow("entry", "result")
    mode.defaults["result.bStretchToContainer"] = "true"
    return {
        "kind": "widget", "path": PAGE, "parent": UMG + "UserWidget", "interfaces": [iface("IHubPageWidget")],
        "variables": [t("Mod", "object", MOD_C)],
        "functions": [{"name": "Sync"}],
        "tree": page_tree(),
        "graphs": {"Sync": g_page_sync(), "EventGraph": g_page_events(),
                   "GetPageInfo": info.data(), "GetContainerMode": mode.data()},
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
