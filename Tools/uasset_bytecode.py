"""List the Blueprint bytecode of a cooked UE 4.27 class as readable statements. Read-only.

Used to see what an installed mod really does (which engine calls, with which values), so a new mod
can live next to it. Jump targets are in-memory offsets and are printed as numbers only.

Usage: python uasset_bytecode.py <file.uasset> [function name filter]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uasset_dump import Package, Reader
from uasset_funcs import read_field


class Script:
    def __init__(self, pkg, data):
        self.pkg, self.r = pkg, Reader(data, pkg.names)

    def obj(self):
        ref = self.pkg.ref(self.r.i32())
        return ref.split(".")[-1].replace("export:", "")

    def field(self):
        names = [self.r.fname() for _ in range(self.r.i32())]
        self.r.i32()
        return ".".join(names) if names else "<none>"

    def cstr(self, wide=False):
        out = []
        while True:
            c = self.r.fmt("<H")[0] if wide else self.r.u8()
            if c == 0:
                return "".join(out)
            out.append(chr(c))

    def params(self):
        out = []
        while self.r.d[self.r.p] != 0x16:
            out.append(self.expr())
        self.r.p += 1
        return ", ".join(out)

    def expr(self):
        r = self.r
        op = r.u8()
        if op in (0x00, 0x01, 0x02, 0x48, 0x6C): return self.field()
        if op == 0x04: return "return " + self.expr()
        if op == 0x06: return "jump %d" % r.u32()
        if op == 0x07: target = r.u32(); return "if not (%s) jump %d" % (self.expr(), target)
        if op == 0x09: r.fmt("<HB"); return "assert " + self.expr()
        if op == 0x0B: return "nop"
        if op == 0x0F: self.field(); a = self.expr(); return "%s = %s" % (a, self.expr())
        if op in (0x14, 0x5F, 0x60, 0x43, 0x44): a = self.expr(); return "%s = %s" % (a, self.expr())
        if op == 0x12 or op in (0x19, 0x1A):
            target = self.expr(); r.u32(); self.field()
            return "%s.%s" % (target, self.expr())
        if op in (0x13, 0x2E, 0x52, 0x54, 0x55): cls = self.obj(); return "cast<%s>(%s)" % (cls, self.expr())
        if op == 0x15: return "<endparm>"
        if op == 0x17: return "self"
        if op == 0x18: r.u32(); return self.expr()
        if op in (0x1B, 0x45): name = r.fname(); return "%s(%s)" % (name, self.params())
        if op in (0x1C, 0x46, 0x68, 0x63): name = self.obj(); return "%s(%s)" % (name, self.params())
        if op == 0x1D: return str(r.i32())
        if op == 0x1E: return "%g" % r.f32()
        if op == 0x1F: return repr(self.cstr())
        if op == 0x34: return repr(self.cstr(True))
        if op == 0x20: return "obj:" + self.obj()
        if op == 0x21: return "name:" + r.fname()
        if op in (0x22, 0x23): return "(%g, %g, %g)" % r.fmt("<3f")
        if op == 0x2B: return "transform%s" % (r.fmt("<10f"),)
        if op in (0x24, 0x2C): return str(r.u8())
        if op == 0x25: return "0"
        if op == 0x26: return "1"
        if op == 0x27: return "true"
        if op == 0x28: return "false"
        if op in (0x2A, 0x2D): return "null"
        if op == 0x29:
            kind = r.u8()
            if kind == 1: a = self.expr(); self.expr(); self.expr(); return "text " + a
            if kind in (2, 3): return "text " + self.expr()
            if kind == 4: self.obj(); self.expr(); return "text " + self.expr()
            return "text ''"
        if op == 0x2F:
            name = self.obj(); r.i32(); parts = []
            while r.d[r.p] != 0x30: parts.append(self.expr())
            r.p += 1
            return "%s{%s}" % (name, ", ".join(parts))
        if op == 0x31:
            target = self.expr(); parts = []
            while r.d[r.p] != 0x32: parts.append(self.expr())
            r.p += 1
            return "%s = [%s]" % (target, ", ".join(parts))
        if op == 0x65:
            self.field(); r.i32(); parts = []
            while r.d[r.p] != 0x66: parts.append(self.expr())
            r.p += 1
            return "[%s]" % ", ".join(parts)
        if op in (0x33, 0x6D): return "prop:" + self.field()
        if op == 0x35: return str(r.i64())
        if op == 0x36: return str(r.fmt("<Q")[0])
        if op == 0x38: r.u8(); return self.expr()
        if op == 0x42: member = self.field(); return "%s.%s" % (self.expr(), member)
        if op == 0x4B: return "delegate:" + r.fname()
        if op == 0x4C: return "push %d" % r.u32()
        if op == 0x4D: return "pop"
        if op == 0x4E: return "goto " + self.expr()
        if op == 0x4F: return "if not (%s) pop" % self.expr()
        if op in (0x50, 0x5A, 0x5E): return "nop"
        if op == 0x51: return self.expr()
        if op == 0x53: return "<end>"
        if op == 0x5B: return str(r.u32())
        if op in (0x5C, 0x62): a = self.expr(); return "%s %s %s" % (a, "+=" if op == 0x5C else "-=", self.expr())
        if op == 0x5D: return "clear " + self.expr()
        if op == 0x61: name = r.fname(); a = self.expr(); return "%s = bind(%s, %s)" % (a, name, self.expr())
        if op == 0x64: name = self.field(); return "%s = %s" % (name, self.expr())
        if op == 0x67: return "soft " + self.expr()
        if op == 0x69:
            cases = r.fmt("<H")[0]; r.u32(); index = self.expr(); parts = []
            for _ in range(cases):
                key = self.expr(); r.u32(); parts.append("%s: %s" % (key, self.expr()))
            return "switch(%s){%s; default: %s}" % (index, "; ".join(parts), self.expr())
        if op == 0x6A: r.u8(); return "nop"
        if op == 0x6B: a = self.expr(); return "%s[%s]" % (a, self.expr())
        raise ValueError("opcode 0x%02X at %d" % (op, r.p - 1))


def listing(pkg, export):
    r = Reader(pkg.body, pkg.names)
    r.p = export["off"] - pkg.body_base
    pkg.read_props(r)
    r.i32(); r.i32()
    children = r.i32()
    r.p += 4 * children
    for _ in range(r.i32()):
        read_field(pkg, r)
    r.i32()
    size = r.i32()
    script = Script(pkg, pkg.body[r.p:r.p + size])
    lines = []
    try:
        while script.r.p < size:
            at = script.r.p
            text = script.expr()
            if text not in ("nop", "<end>"):
                lines.append("%5d  %s" % (at, text))
    except Exception as error:  # show what was decoded so far
        lines.append("       <stopped: %s>" % error)
    return lines


def main():
    pkg = Package(sys.argv[1])
    wanted = sys.argv[2].lower() if len(sys.argv) > 2 else ""
    for export in pkg.exports:
        if pkg.ref(export["cls"]).endswith(".Function") and wanted in export["name"].lower():
            print("== " + export["name"])
            for line in listing(pkg, export):
                print(line)


if __name__ == "__main__":
    main()
