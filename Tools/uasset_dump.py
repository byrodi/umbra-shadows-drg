"""Dump a cooked UE 4.27 package (.uasset + .uexp): imports, exports, tagged properties.

Read-only helper to look at real game values (extract with UnrealPak first).
Usage: python uasset_dump.py <file.uasset> [--imports] [--filter text]
"""
import struct
import sys

NATIVE_STRUCTS = {
    "Vector": "<3f", "Rotator": "<3f", "Vector2D": "<2f", "Quat": "<4f", "Vector4": "<4f",
    "LinearColor": "<4f", "Color": "<4B", "IntPoint": "<2i", "Guid": "<4I", "IntVector": "<3i",
    "Box": "<6fB", "DateTime": "<q", "Timespan": "<q",
}


class Reader:
    def __init__(self, data, names=None):
        self.d = data
        self.p = 0
        self.names = names or []

    def fmt(self, f):
        v = struct.unpack_from(f, self.d, self.p)
        self.p += struct.calcsize(f)
        return v

    def i32(self): return self.fmt("<i")[0]
    def u32(self): return self.fmt("<I")[0]
    def i64(self): return self.fmt("<q")[0]
    def u8(self): return self.fmt("<B")[0]
    def f32(self): return self.fmt("<f")[0]

    def fstring(self):
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            s = self.d[self.p:self.p - 2 * n].decode("utf-16-le")
            self.p += -2 * n
        else:
            s = self.d[self.p:self.p + n].decode("latin-1")
            self.p += n
        return s.rstrip("\0")

    def fname(self):
        idx, num = self.fmt("<iI")
        s = self.names[idx]
        return s if num == 0 else "%s_%d" % (s, num - 1)


class Package:
    def __init__(self, path):
        with open(path, "rb") as f:
            head = f.read()
        r = Reader(head)
        assert r.u32() == 0x9E2A83C1, "not a package"
        legacy = r.i32()
        r.i32(); r.i32(); r.i32()
        for _ in range(r.i32()):
            r.p += 20
        self.header_size = r.i32()
        r.fstring()
        self.flags = r.u32()
        name_count, name_off = r.i32(), r.i32()
        if not self.flags & 0x80000000:
            r.fstring()
        r.i32(); r.i32()
        export_count, export_off = r.i32(), r.i32()
        import_count, import_off = r.i32(), r.i32()

        r.p = name_off
        self.names = []
        for _ in range(name_count):
            self.names.append(r.fstring())
            r.p += 4
        r.names = self.names

        r.p = import_off
        self.imports = []
        for _ in range(import_count):
            cpkg, cname, outer, oname = r.fname(), r.fname(), r.i32(), r.fname()
            self.imports.append((cpkg, cname, outer, oname))

        r.p = export_off
        self.exports = []
        for _ in range(export_count):
            cls, sup, tmpl, outer = r.i32(), r.i32(), r.i32(), r.i32()
            oname = r.fname()
            oflags = r.u32()
            size, off = r.i64(), r.i64()
            r.p += 12 + 16 + 4 + 4 + 4 + 20
            self.exports.append(dict(cls=cls, sup=sup, tmpl=tmpl, outer=outer, name=oname,
                                     flags=oflags, size=size, off=off))
        try:
            with open(path[:-7] + ".uexp", "rb") as f:
                self.body = f.read()
            self.body_base = self.header_size
        except IOError:
            self.body = head
            self.body_base = 0

    def ref(self, idx):
        if idx == 0:
            return "None"
        if idx < 0:
            imp = self.imports[-idx - 1]
            outer = self.ref(imp[2]) if imp[2] else ""
            return (outer + "." if outer else "") + imp[3]
        e = self.exports[idx - 1]
        return "export:" + e["name"]

    def read_value(self, r, typ, size, tag, depth):
        end = r.p + size
        try:
            if typ == "IntProperty": return r.i32()
            if typ == "UInt32Property": return r.u32()
            if typ == "Int64Property": return r.i64()
            if typ == "FloatProperty": return round(r.f32(), 6)
            if typ == "BoolProperty": return tag.get("bool")
            if typ in ("ObjectProperty", "WeakObjectProperty", "InterfaceProperty"): return self.ref(r.i32())
            if typ == "NameProperty": return r.fname()
            if typ == "StrProperty": return r.fstring()
            if typ == "EnumProperty": return r.fname()
            if typ == "ByteProperty":
                return r.u8() if size == 1 else r.fname()
            if typ in ("SoftObjectProperty", "SoftClassProperty"):
                n = r.fname(); sub = r.fstring()
                return n + (":" + sub if sub else "")
            if typ == "TextProperty":
                r.p = end
                return "<text>"
            if typ == "StructProperty":
                return self.read_struct(r, tag.get("struct"), end, depth)
            if typ in ("ArrayProperty", "SetProperty"):
                inner = tag["inner"]
                if typ == "SetProperty":
                    r.i32()
                n = r.i32()
                if inner == "StructProperty":
                    r.fname(); r.fname(); r.i32(); r.i32()
                    sname = r.fname(); r.p += 17
                    return [self.read_struct(r, sname, None, depth + 1) for _ in range(n)]
                if n == 0:
                    return []
                per = (end - r.p) // n
                return [self.read_value(r, inner, per, {}, depth + 1) for _ in range(n)]
            return "<%s %d bytes>" % (typ, size)
        finally:
            if typ != "BoolProperty":
                r.p = end

    def read_struct(self, r, sname, end, depth):
        if sname in NATIVE_STRUCTS:
            return tuple(round(x, 5) if isinstance(x, float) else x for x in r.fmt(NATIVE_STRUCTS[sname]))
        if sname in ("SoftObjectPath", "SoftClassPath"):
            n = r.fname(); sub = r.fstring()
            return n + (":" + sub if sub else "")
        return self.read_props(r, depth + 1)

    def read_props(self, r, depth=0):
        out = []
        while True:
            name = r.fname()
            if name == "None":
                break
            typ = r.fname()
            size, aidx = r.i32(), r.i32()
            tag = {}
            if typ == "StructProperty":
                tag["struct"] = r.fname(); r.p += 16
            elif typ == "BoolProperty":
                tag["bool"] = bool(r.u8())
            elif typ in ("ByteProperty", "EnumProperty"):
                tag["enum"] = r.fname()
            elif typ in ("ArrayProperty", "SetProperty"):
                tag["inner"] = r.fname()
            elif typ == "MapProperty":
                tag["inner"] = r.fname(); tag["value"] = r.fname()
            if r.u8():
                r.p += 16
            val = self.read_value(r, typ, size, tag, depth)
            key = name if aidx == 0 else "%s[%d]" % (name, aidx)
            out.append((key, val))
        return out

    def export_props(self, e):
        r = Reader(self.body, self.names)
        r.p = e["off"] - self.body_base
        return self.read_props(r)


def show(val, indent):
    pad = "  " * indent
    if isinstance(val, list) and val and isinstance(val[0], tuple) and len(val[0]) == 2 and isinstance(val[0][0], str):
        for k, v in val:
            if isinstance(v, list) and v and isinstance(v[0], (list, tuple)) and not (
                    isinstance(v[0], tuple) and not isinstance(v[0][0], str)):
                print("%s%s:" % (pad, k))
                if isinstance(v[0], tuple):
                    show(v, indent + 1)
                else:
                    for i, item in enumerate(v):
                        print("%s  [%d]" % (pad, i))
                        show(item, indent + 2)
            else:
                print("%s%s = %s" % (pad, k, v))
    else:
        print("%s%s" % (pad, val))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flt = None
    if "--filter" in sys.argv:
        flt = sys.argv[sys.argv.index("--filter") + 1].lower()
        args.remove(sys.argv[sys.argv.index("--filter") + 1])
    pkg = Package(args[0])
    if "--imports" in sys.argv:
        for i, imp in enumerate(pkg.imports):
            print("import %d: %s  (%s)" % (-i - 1, pkg.ref(-i - 1), imp[1]))
    for e in pkg.exports:
        if flt and flt not in e["name"].lower() and flt not in pkg.ref(e["cls"]).lower():
            continue
        print("== %s : %s  (outer %s, %d bytes)" % (e["name"], pkg.ref(e["cls"]), pkg.ref(e["outer"]), e["size"]))
        try:
            show(pkg.export_props(e), 1)
        except Exception as ex:  # class/function exports are not plain property lists
            print("  <unparsed: %s>" % ex)


if __name__ == "__main__":
    main()
