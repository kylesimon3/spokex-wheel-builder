"""Pull the small rounded-rectangle rim tag off the photographed decal sheet.

Both tags on a sheet are the same artwork -- "SX30" in red at each end, the
SPOKEX mountain mark in the middle, the whole layout MIRRORED about the centre
line -- and one of the two has a hole punched dead centre. That mirroring is
what tells you how it is fitted: the fold runs along the centre line, sits on
the rim's inner circumference, and the two halves wrap up onto the two
sidewalls so each reads the right way round. The hole is on the fold because
that is where the rim's valve hole is.

The tag is a rectangle seen in mild perspective, so it is located as a
connected component, fitted with a minimum-area rectangle, and resampled
through that quad. Output is a MASK so the app can recolour it:
  R = greyscale of the non-red artwork (keeps the black mark darker than the
      grey body -- that content is genuinely greyscale, so this is lossless)
  G = red coverage, which the decal colour drives
  A = total coverage
"""
from png import read_png
import zlib, struct, math, os

SRC = 'decal_src.png'
REGION = (244, 62, 356, 142)     # the clean back-sheet tag, no hole
OUT_W = 320

w, h, px = read_png(SRC)
def at(x, y): return px[y*w + x][:3]
def lum(p): return 0.2126*p[0] + 0.7152*p[1] + 0.0722*p[2]
def is_red(p):
    r, g, b = p
    return r > 70 and r > g + 35 and r > b + 35
def is_ink(p): return lum(p) < 120 or is_red(p)

X0, Y0, X1, Y1 = REGION
seen, best = set(), None
for sy in range(Y0, Y1):
    for sx in range(X0, X1):
        if (sx, sy) in seen or not is_ink(at(sx, sy)): continue
        stack, pts = [(sx, sy)], []
        seen.add((sx, sy))
        while stack:
            x, y = stack.pop(); pts.append((x, y))
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = x+dx, y+dy
                if X0 <= nx < X1 and Y0 <= ny < Y1 and (nx,ny) not in seen and is_ink(at(nx,ny)):
                    seen.add((nx,ny)); stack.append((nx,ny))
        if best is None or len(pts) > len(best): best = pts
assert best and len(best) > 1500, f"tag not found (largest component {len(best or [])}px)"

# The tag is a mild trapezoid, not a rotated rectangle -- the sheet is
# photographed at an angle, so the left and right edges converge. A minimum-area
# rectangle cannot express that and ends up swallowing the sheet edge alongside
# it, so each of the four sides is fitted as a line instead and the corners come
# from their intersections. Rounded corners make the extreme rows and columns
# unreliable, so only the middle of each side is fitted and the lines are then
# extended.
xs = [q[0] for q in best]; ys = [q[1] for q in best]
bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
rowmin, rowmax, colmin, colmax = {}, {}, {}, {}
for x, y in best:
    if y not in rowmin or x < rowmin[y]: rowmin[y] = x
    if y not in rowmax or x > rowmax[y]: rowmax[y] = x
    if x not in colmin or y < colmin[x]: colmin[x] = y
    if x not in colmax or y > colmax[x]: colmax[x] = y

def fit(pairs):
    """least squares b -> a of a list of (b, a); returns a = m*b + c"""
    n = len(pairs)
    sb = sum(b for b, _ in pairs); sa = sum(a for _, a in pairs)
    sbb = sum(b*b for b, _ in pairs); sba = sum(b*a for b, a in pairs)
    den = n*sbb - sb*sb
    if abs(den) < 1e-9: return (0.0, sa/n)
    m = (n*sba - sb*sa) / den
    return (m, (sa - m*sb)/n)

def trim(lo, hi, frac=0.22):
    d = (hi - lo) * frac
    return lo + d, hi - d
ry0, ry1 = trim(by0, by1)
cx0, cx1 = trim(bx0, bx1)
mL, cL = fit([(y, x) for y, x in rowmin.items() if ry0 <= y <= ry1])   # x = mL*y + cL
mR, cR = fit([(y, x) for y, x in rowmax.items() if ry0 <= y <= ry1])
mT, cT = fit([(x, y) for x, y in colmin.items() if cx0 <= x <= cx1])   # y = mT*x + cT
mB, cB = fit([(x, y) for x, y in colmax.items() if cx0 <= x <= cx1])

def meet(m1, c1, m2, c2):
    """x = m1*y + c1 with y = m2*x + c2"""
    x = (m1*c2 + c1) / (1 - m1*m2)
    return (x, m2*x + c2)
TL = meet(mL, cL, mT, cT); TR = meet(mR, cR, mT, cT)
BR = meet(mR, cR, mB, cB); BL = meet(mL, cL, mB, cB)
import math
def dist(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])
long_  = (dist(TL, TR) + dist(BL, BR)) / 2
short_ = (dist(TL, BL) + dist(TR, BR)) / 2
if long_ >= short_: quad = [TL, TR, BR, BL]
else:               quad = [BL, TL, TR, BR]; long_, short_ = short_, long_
print(f"tag {len(best)}px  quad {[(round(x),round(y)) for x,y in (TL,TR,BR,BL)]}")
print(f"  {long_:.1f} x {short_:.1f}  aspect={long_/short_:.2f}  "
      f"edge slopes L={mL:+.3f} R={mR:+.3f} T={mT:+.3f} B={mB:+.3f}")

OUT_H = max(8, int(round(OUT_W * short_ / long_)))
SS = 3
rows = []
for oy in range(OUT_H):
    row = bytearray([0])
    for ox in range(OUT_W):
        ng = nr = n = 0; gsum = 0
        for jy in range(SS):
            for jx in range(SS):
                u = (ox + (jx+.5)/SS) / OUT_W
                v = (oy + (jy+.5)/SS) / OUT_H
                ax = (1-v)*((1-u)*quad[0][0] + u*quad[1][0]) + v*((1-u)*quad[3][0] + u*quad[2][0])
                ay = (1-v)*((1-u)*quad[0][1] + u*quad[1][1]) + v*((1-u)*quad[3][1] + u*quad[2][1])
                xi, yi = int(round(ax)), int(round(ay))
                if not (0 <= xi < w and 0 <= yi < h): continue
                p = at(xi, yi); n += 1
                if is_red(p): nr += 1
                elif lum(p) < 175: ng += 1; gsum += lum(p)
        if not n: row += bytes((0,0,0,0)); continue
        g = int(255*ng/n); r = int(255*nr/n)
        grey = int(min(255, gsum/ng)) if ng else 0
        row += bytes((grey, r, 0, min(255, g + r)))
    rows.append(bytes(row))
def chunk(t_, d):
    c_ = t_ + d
    return struct.pack('>I', len(d)) + c_ + struct.pack('>I', zlib.crc32(c_) & 0xffffffff)
open('tag_mask.png','wb').write(
    b'\x89PNG\r\n\x1a\n'
    + chunk(b'IHDR', struct.pack('>IIBBBBB', OUT_W, OUT_H, 8, 6, 0, 0, 0))
    + chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + chunk(b'IEND', b''))
print(f"wrote tag_mask.png {OUT_W}x{OUT_H} ({os.path.getsize('tag_mask.png'):,} bytes)")
