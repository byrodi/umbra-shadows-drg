"""Screenshot finishing for the mod.io page, with ffmpeg (no Python packages needed).

  python Tools/shots.py grade   <in> <out.jpg> [options]           16:9, 1920x1080, light grade
  python Tools/shots.py compare <game> <umbra> <out.jpg> [options]  before/after split, GAME / UMBRA
  python Tools/shots.py pair    <game> <umbra> <out.jpg> --crop X,Y,W [options]
                      the same box (W x W*9/8) from both shots, side by side: same place, mod off / on
  python Tools/shots.py cover   <in> <out.jpg> [options]           1920x1080 cover with the mod's name

Options:
  --zoom Z            keep the middle Z of the picture (0.85 drops the HUD in the corners)
  --crop X,Y,W        crop this 16:9 box instead (source pixels; height = W * 9 / 16)
  --hide X,Y,W,H      blur out a small HUD element (source pixels; repeat for more)
  --hide1 / --hide2   the same for the first or second shot only (compare, pair)
  --gamma G           brighten the mid tones (1.0 = as shot; dark caves look good at 1.1 to 1.25)
  --glow A            soft glow around bright light, 0 to 0.5 (0.2 is subtle)

compare needs two shots from the same place: Umbra's "Enabled" off, then on, without moving.
ffmpeg: Saved/Tools/ffmpeg/**/ffmpeg.exe, or set FFMPEG. Fonts: Windows' Bahnschrift and Segoe UI.
Keep the grade honest: mod.io screenshots must show what the mod looks like in the game.
"""
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1920, 1080
TITLE_FONT = "C\\:/Windows/Fonts/bahnschrift.ttf"
TEXT_FONT = "C\\:/Windows/Fonts/segoeuib.ttf"
OPT = {"zoom": 1.0, "crop": None, "hide": [], "hide1": [], "hide2": [], "gamma": 1.0, "glow": 0.0}


def ffmpeg():
    exe = os.environ.get("FFMPEG")
    if exe:
        return exe
    found = glob.glob(os.path.join(ROOT, "Saved", "Tools", "ffmpeg", "**", "ffmpeg.exe"), recursive=True)
    if not found:
        sys.exit("ffmpeg not found: set FFMPEG or unpack it to Saved/Tools/ffmpeg")
    return found[0]


def hide_hud(src, dst):
    """Each --hide box: a median filter over that patch. It removes thin lines (crosshair) and small text
    and keeps the colours around them. Returns graph text and the label to continue from."""
    graph, label_now = [], src
    own = OPT["hide2"] if src.startswith("1:") else OPT["hide1"]
    for i, (x, y, w, h) in enumerate(OPT["hide"] + own):
        m = 12  # margin, so the median sees the surroundings
        graph.append("[%s]split[k%s%d][p%s%d];[p%s%d]crop=%d:%d:%d:%d,median=radius=9,crop=%d:%d:%d:%d[q%s%d];"
                     "[k%s%d][q%s%d]overlay=%d:%d[h%s%d]"
                     % (label_now, dst, i, dst, i, dst, i, w + 2 * m, h + 2 * m, max(0, x - m), max(0, y - m),
                        w, h, m, m, dst, i, dst, i, dst, i, x, y, dst, i))
        label_now = "h%s%d" % (dst, i)
    return graph, label_now


def finish(src, dst, half=False):
    """Filter graph from input label src to output label dst: HUD removal, crop, scale, grade, glow.
    half: a W x W*9/8 box scaled to half the output width (for side by side pairs)."""
    graph, src = hide_hud(src, dst)
    prefix = ";".join(graph) + (";" if graph else "")
    steps = []
    if OPT["crop"]:
        x, y, w = OPT["crop"]
        steps.append("crop=%d:%d:%d:%d" % (w, w * 9 // 8 if half else w * 9 // 16, x, y))
    else:
        z = OPT["zoom"]
        steps.append("crop='min(iw,ih*16/9)*%s':'min(ih,iw*9/16)*%s'" % (z, z))
    steps += [
        "scale=%d:%d:flags=lanczos" % (W // 2 if half else W, H),
        # contrast and colour a little up, mid tones lifted for dark caves, then sharpen the upscale
        "eq=contrast=1.08:saturation=1.10:gamma=%s" % OPT["gamma"],
        "vibrance=intensity=0.15",
        "unsharp=5:5:0.5:5:5:0.0",
    ]
    chain = ",".join(steps)
    if OPT["glow"] <= 0:
        return prefix + "[%s]%s,vignette=angle=PI/5[%s]" % (src, chain, dst)
    # glow: only the bright parts, blurred wide, added back on top (screen blend). In RGB: a screen blend
    # on YUV planes would shift the colours.
    return prefix + ("[%(s)s]%(c)s,format=gbrp,split[base%(d)s][hi%(d)s];"
                     "[hi%(d)s]curves=all='0/0 0.55/0 1/1',gblur=sigma=28[blur%(d)s];"
                     "[base%(d)s][blur%(d)s]blend=all_mode=screen:all_opacity=%(a)s,vignette=angle=PI/5[%(d)s]"
                     % {"s": src, "c": chain, "d": dst, "a": OPT["glow"]})


def run(inputs, graph, out):
    cmd = [ffmpeg(), "-v", "error", "-y"]
    for path in inputs:
        cmd += ["-i", path]
    cmd += ["-filter_complex", graph, "-map", "[o]", "-frames:v", "1", "-q:v", "2", out]
    subprocess.check_call(cmd)
    print("wrote", out)


def label(text, x, y, size):
    """drawtext with a soft shadow; text in capitals reads well over busy cave walls."""
    return ("drawtext=fontfile='%s':text='%s':fontsize=%d:fontcolor=white:x=%s:y=%s:"
            "shadowcolor=black@0.7:shadowx=3:shadowy=3" % (TITLE_FONT, text, size, x, y))


def grade(src, out):
    run([src], finish("0:v", "o"), out)


def compare(game, umbra, out):
    half = W // 2
    graph = (finish("0:v", "a") + ";" + finish("1:v", "b") + ";"
             "[a]crop=%d:%d:0:0[l];[b]crop=%d:%d:%d:0[r];"
             "[l][r]hstack=inputs=2,drawbox=x=%d:y=0:w=4:h=%d:color=white@0.9:t=fill,%s,%s[o]"
             % (half, H, half, H, half, half - 2, H,
                label("GAME", "60", "h-120", 64), label("UMBRA", "w-tw-60", "h-120", 64)))
    run([game, umbra], graph, out)


def pair(game, umbra, out):
    """Same place, mod off and on, side by side. Both get exactly the same processing."""
    graph = (finish("0:v", "a", True) + ";" + finish("1:v", "b", True) + ";"
             "[a][b]hstack=inputs=2,drawbox=x=%d:y=0:w=4:h=%d:color=white@0.9:t=fill,%s,%s[o]"
             % (W // 2 - 2, H, label("GAME", "50", "h-110", 60), label("UMBRA", "w-tw-50", "h-110", 60)))
    run([game, umbra], graph, out)


def cover(src, out):
    graph = (finish("0:v", "g") + ";"
             "[g]drawbox=x=0:y=ih-300:w=iw:h=300:color=black@0.45:t=fill,%s,"
             "drawtext=fontfile='%s':text='Round soft shadows for every flare  ·  class colours  ·  headlamp shadows':"
             "fontsize=40:fontcolor=white@0.92:x=80:y=h-110:shadowcolor=black@0.7:shadowx=2:shadowy=2[o]"
             % (label("UMBRA", "80", "h-270", 150), TEXT_FONT))
    run([src], graph, out)


def parse(args):
    rest = []
    i = 0
    while i < len(args):
        key = args[i]
        if key in ("--zoom", "--gamma", "--glow"):
            OPT[key[2:]] = float(args[i + 1])
            i += 2
        elif key == "--crop":
            OPT["crop"] = [int(v) for v in args[i + 1].split(",")]
            i += 2
        elif key in ("--hide", "--hide1", "--hide2"):
            OPT[key[2:]].append([int(v) for v in args[i + 1].split(",")])
            i += 2
        else:
            rest.append(key)
            i += 1
    return rest


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    action, args = sys.argv[1], parse(sys.argv[2:])
    if action == "grade" and len(args) == 2:
        grade(*args)
    elif action == "compare" and len(args) == 3:
        compare(*args)
    elif action == "pair" and len(args) == 3 and OPT["crop"]:
        pair(*args)
    elif action == "cover" and len(args) == 2:
        cover(*args)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
