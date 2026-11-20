"""Print the properties of an Unreal SaveGame file (.sav, UE 4.27). Read-only.

Usage: python sav_dump.py <file.sav> ...
"""
import struct
import sys


class R:
    def __init__(self, d):
        self.d, self.p = d, 0

    def fmt(self, f):
        v = struct.unpack_from(f, self.d, self.p)
        self.p += struct.calcsize(f)
        return v

    def s(self):
        n = self.fmt("<i")[0]
        if n == 0:
            return ""
        if n < 0:
            v = self.d[self.p:self.p - 2 * n].decode("utf-16-le")
            self.p -= 2 * n
        else:
            v = self.d[self.p:self.p + n].decode("latin-1")
            self.p += n
        return v.rstrip("\0")


def props(r, depth=0):
    while r.p < len(r.d):
        name = r.s()
        if name in ("None", ""):
            return
        typ = r.s()
        size, _ = r.fmt("<ii")
        extra = ""
        if typ == "StructProperty":
            extra = r.s(); r.p += 16
        elif typ == "BoolProperty":
            extra = bool(r.fmt("<B")[0])
        elif typ in ("ByteProperty", "EnumProperty", "ArrayProperty", "SetProperty"):
            extra = r.s()
        elif typ == "MapProperty":
            extra = r.s() + "," + r.s()
        r.p += 1
        end = r.p + size
        if typ == "FloatProperty":
            value = round(r.fmt("<f")[0], 5)
        elif typ == "IntProperty":
            value = r.fmt("<i")[0]
        elif typ == "BoolProperty":
            value = extra
        elif typ in ("StrProperty", "NameProperty", "EnumProperty"):
            value = r.s()
        elif typ == "StructProperty" and extra in ("LinearColor", "Vector", "Rotator", "Vector2D"):
            value = tuple(round(x, 4) for x in r.fmt("<%df" % (size // 4)))
        elif typ == "StructProperty":
            print("%s%s (%s):" % ("  " * depth, name, extra))
            props(r, depth + 1)
            r.p = end
            continue
        else:
            value = "<%s %s, %d bytes>" % (typ, extra, size)
        r.p = end
        print("%s%s = %s" % ("  " * depth, name, value))


def main():
    for path in sys.argv[1:]:
        with open(path, "rb") as f:
            r = R(f.read())
        assert r.d[:4] == b"GVAS", "not a SaveGame file"
        r.p = 4
        r.fmt("<ii")
        r.fmt("<HHHI"); r.s()
        r.fmt("<i")
        for _ in range(r.fmt("<i")[0]):
            r.p += 20
        print("== %s  (%s)" % (path, r.s()))
        props(r, 1)


if __name__ == "__main__":
    main()
