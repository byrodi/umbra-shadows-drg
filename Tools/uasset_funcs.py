"""Print function signatures of a cooked UE 4.27 Blueprint class (.uasset + .uexp).

Usage: python uasset_funcs.py <file.uasset> ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uasset_dump import Package, Reader

CPF = {0x2: "const", 0x80: "parm", 0x100: "out", 0x400: "return", 0x08000000: "ref"}


def read_field(pkg, r):
    typ = r.fname()
    if typ == "None":
        return None
    name = r.fname()
    r.u32()
    r.i32(); r.i32()
    flags = r.fmt("<Q")[0]
    r.fmt("<H"); r.fname(); r.u8()
    extra = ""
    if typ == "BoolProperty":
        r.p += 6
    elif typ in ("ObjectProperty", "WeakObjectProperty", "SoftObjectProperty", "LazyObjectProperty"):
        extra = pkg.ref(r.i32())
    elif typ in ("ClassProperty", "SoftClassProperty"):
        r.i32(); extra = pkg.ref(r.i32())
    elif typ == "InterfaceProperty":
        extra = pkg.ref(r.i32())
    elif typ == "StructProperty":
        extra = pkg.ref(r.i32())
    elif typ == "ByteProperty":
        extra = pkg.ref(r.i32())
    elif typ == "EnumProperty":
        extra = pkg.ref(r.i32()); read_field(pkg, r)
    elif typ in ("DelegateProperty", "MulticastDelegateProperty", "MulticastInlineDelegateProperty"):
        extra = pkg.ref(r.i32())
    elif typ in ("ArrayProperty", "SetProperty"):
        inner = read_field(pkg, r)
        extra = "of " + inner[1] + (" " + inner[2] if inner[2] else "")
    elif typ == "MapProperty":
        k = read_field(pkg, r); v = read_field(pkg, r)
        extra = "%s -> %s" % (k[1:3], v[1:3])
    fl = [n for b, n in CPF.items() if flags & b]
    return (name, typ, extra, fl)


def functions(pkg):
    out = []
    for e in pkg.exports:
        if not pkg.ref(e["cls"]).endswith(".Function"):
            continue
        r = Reader(pkg.body, pkg.names)
        r.p = e["off"] - pkg.body_base
        pkg.read_props(r)
        r.i32()            # no guid
        r.i32()            # super struct
        n_children = r.i32()
        r.p += 4 * n_children
        params = [read_field(pkg, r) for _ in range(r.i32())]
        out.append((e["name"], params))
    return out


if __name__ == "__main__":
    for path in sys.argv[1:]:
        pkg = Package(path)
        print("=== " + path)
        for name, params in functions(pkg):
            print("  %s(" % name)
            for p in params:
                if "parm" in p[3]:
                    print("      %-22s %s %s  [%s]" % (p[0], p[1], p[2], ",".join(p[3])))
            print("  )")
