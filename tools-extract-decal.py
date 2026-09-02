"""Pull one rim decal off the photographed sheet and straighten it.

Each decal prints as a SOLID dark band carrying red keyline artwork, and the
four on a sheet are separated by thin light slivers -- so a decal is one run of
ink per column, and can be followed across the sheet by continuity.

Resampling each column between that run's own top and bottom removes two things
at once: the curve the decal is manufactured with, and the vertical
foreshortening of the angled photograph (bands measure ~62px tall at the near
end and ~52px at the far end). What comes out is a straight strip the app can
bend onto any rim radius.

Output is a MASK, not a picture, so the app can recolour it:
  R = dark body coverage, G = red keyline coverage, A = either.
"""
from png import read_png
import zlib, struct

SRC, SEED_X, SEED_Y, OUT_W = 'decal_src.png', 500, 332, 1100
MARGIN = 0.06   # transparent padding so bending it onto the rim cannot clip

w, h, px = read_png(SRC)
def at(x, y): return px[y*w + x][:3]
def lum(p): return 0.2126*p[0] + 0.7152*p[1] + 0.0722*p[2]
def is_accent(p):
    r, g, b = p
    return r > 70 and r > g + 35 and r > b + 35
def is_ink(p): return lum(p) < 118 or is_accent(p)

def runs(x, lo=200, hi=560):
    out, start = [], None
    for y in range(lo, hi):
        if is_ink(at(x, y)):
            if start is None: start = y
        elif start is not None:
            out.append((start, y - 1)); start = None
    if start is not None: out.append((start, hi - 1))
    return out

def pick(x, centre, tol=14):
    best = None
    for a, b in runs(x):
        if b - a < 8: continue
        c = (a + b) / 2
        if abs(c - centre) > tol: continue
        if best is None or abs(c - centre) < abs((best[0]+best[1])/2 - centre): best = (a, b)
    return best

seed = pick(SEED_X, SEED_Y, 30)
assert seed, "no band at the seed"
band = {SEED_X: seed}
for step in (1, -1):
    x, c = SEED_X, (seed[0] + seed[1]) / 2
    while 0 <= x + step < w:
        x += step
        r = pick(x, c)
        if not r: break
        band[x] = r; c = (r[0] + r[1]) / 2
xs = sorted(band)
th = [band[x][1] - band[x][0] for x in xs]
print(f"band x {xs[0]}..{xs[-1]} ({len(xs)} cols), thickness {min(th)}..{max(th)} (mean {sum(th)/len(th):.1f})")

OUT_H = max(8, int(round(OUT_W * (sum(th)/len(th)) / len(xs) * (1 + 2*MARGIN))))
SS = 3
rows = []
for oy in range(OUT_H):
    row = bytearray([0])
    for ox in range(OUT_W):
        nb = na = n = 0
        for jy in range(SS):
            for jx in range(SS):
                u = (ox + (jx + .5)/SS) / OUT_W
                v = ((oy + (jy + .5)/SS) / OUT_H) * (1 + 2*MARGIN) - MARGIN
                xi = int(round(xs[0] + u * (xs[-1] - xs[0])))
                if xi not in band: continue
                t, b = band[xi]
                p = at(xi, int(round(t + v * (b - t))))
                n += 1
                if is_accent(p): na += 1
                elif lum(p) < 118: nb += 1
        bb = int(255*nb/n) if n else 0
        aa = int(255*na/n) if n else 0
        row += bytes((bb, aa, 0, min(255, bb + aa)))
    rows.append(bytes(row))
def chunk(t, d):
    c = t + d
    return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
open('decal_mask.png','wb').write(
    b'\x89PNG\r\n\x1a\n'
    + chunk(b'IHDR', struct.pack('>IIBBBBB', OUT_W, OUT_H, 8, 6, 0, 0, 0))
    + chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + chunk(b'IEND', b''))
import os
print(f"wrote decal_mask.png {OUT_W}x{OUT_H} ({os.path.getsize('decal_mask.png'):,} bytes), aspect {OUT_W/OUT_H:.2f}:1")
