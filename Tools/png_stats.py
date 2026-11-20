"""Brightness statistics of the test renders (no extra packages needed).

Usage: python png_stats.py <file.png> ...
Prints the mean sRGB value (0-255) of a 16 x 9 grid of cells, so a render can be checked as numbers.
"""
import struct
import sys
import zlib


def read_png(path):
    with open(path, "rb") as f:
        data = f.read()
    pos, chunks, width, height, channels = 8, [], 0, 0, 4
    while pos + 8 <= len(data):
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"IEND":
            break
        body = data[pos + 8:pos + 8 + size]
        if kind == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", body[:10])
            channels = {2: 3, 6: 4}[colour]
        elif kind == b"IDAT":
            chunks.append(body)
        pos += 12 + size
    raw = zlib.decompress(b"".join(chunks))
    stride = width * channels
    rows, prev = [], bytearray(stride)
    for y in range(height):
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        kind = raw[y * (stride + 1)]
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return width, height, channels, rows


def main():
    for path in sys.argv[1:]:
        width, height, channels, rows = read_png(path)
        print(path)
        for gy in range(9):
            cells = []
            for gx in range(16):
                total = count = 0
                for y in range(gy * height // 9, (gy + 1) * height // 9, 4):
                    row = rows[y]
                    for x in range(gx * width // 16, (gx + 1) * width // 16, 4):
                        i = x * channels
                        total += row[i] + row[i + 1] + row[i + 2]
                        count += 3
                cells.append("%3d" % (total // count))
            print("  " + " ".join(cells))


if __name__ == "__main__":
    main()
