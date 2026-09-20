"""婚宴照片精修 v3。

思路（按人物特点微调，不做等比缩放）：
- 方脸不做整体瘦脸（会变嘬腮），只收下颌角 / 咬肌，保留颧骨与下巴宽度
- 压肩线拉长颈部（新娘本人建议），配合轻微收窄颈部
- 眼睛向外推并极轻微放大，平衡方脸比例
- 质感用频率分离：只压中低频色块，毛孔级细节完整保留并回补锐度
- 变形采样用 Catmull-Rom 三次卷积，避免双线性造成的发虚

坐标均为原图 7008x4672 实测，换照片必须重新标定。
"""

import numpy as np
from PIL import Image, ImageFilter

SRC = "微信图片_20260728185148_2671_11.jpg"
DST = "微信图片_20260728185148_2671_11_retouched.jpg"
PORTRAIT = "新娘竖构图_retouched.jpg"

# ---------------- 人物标定 ----------------
FACE = (3065, 1600, 300, 380)          # cx, cy, rx, ry
BODY = (3080, 2150, 1150, 1900)
EYE_A = (2827, 1540, 53, 27)           # 远侧眼（画面左）
EYE_B = (3048, 1517, 63, 31)           # 近侧眼（画面右）

# ---------------- 几何微调 ----------------
# 局部定向推移：(cx, cy, rx, ry, feather, dx, dy)  dx>0 内容左移，dy>0 内容上移
WARP_PUSH = [
    (2915, 1885, 115, 85, 0.60, -6.0, 0.0),     # 远侧下颌角内收（贴近下巴，力度更小）
    (3245, 1875, 130, 95, 0.60, 10.0, 0.0),     # 近侧下颌角 / 咬肌内收（方脸主要来源）
    (2827, 1540, 88, 62, 0.85, 5.0, 0.0),       # 远侧眼外扩
    (3048, 1517, 98, 68, 0.85, -5.0, 0.0),      # 近侧眼外扩
]
# 横向收窄：x 方向平顶 falloff × y 方向梯形门控，避免波及其他部位
# (cx, hx, fx, (y1, y2, y3, y4), amp)
WARP_PINCH_X = [
    (3060, 190, 130, (1920, 1985, 2045, 2125), 0.045),   # 颈部
    (3060, 620, 260, (2120, 2400, 4400, 4672), 0.030),   # 身体轮廓
]
# 等比缩放：(cx, cy, rx, ry, feather, amp)  amp<0 放大
WARP_SCALE = [
    (2827, 1540, 80, 55, 0.80, -0.015),         # 远侧眼微放大
    (3048, 1517, 90, 60, 0.80, -0.018),         # 近侧眼微放大
]
# 压肩线：x 方向梯形权重 × y 方向梯形权重，内容整体下移 → 颈部拉长
SHOULDER = dict(cx=3050, hx=470, fx=230, y=(1958, 2115, 2650, 3420), amount=18.0)

# ---------------- 显白 ----------------
SKIN_AREAS = [
    (3020, 1620, 400, 430, 0.55, 1.00),
    (3050, 1960, 310, 175, 0.80, 1.00),
    (2650, 3000, 340, 390, 0.70, 0.42),
    (3180, 3170, 200, 200, 0.80, 0.42),
]
SKIN_LIFT = np.array([0.110, 0.122, 0.155], dtype=np.float32)
SKIN_DESAT = 0.05

# ---------------- 质感 ----------------
BAND_KEEP = dict(fine=1.06, mid=0.58, tone=0.74)   # 毛孔保留 / 瑕疵压低 / 色块压低
# 法令纹弱化：(cx, cy, 长半轴, 短半轴, 角度°, 强度)
NASOLABIAL = [
    (3026, 1668, 78, 24, 40.0, 0.50),
]
CLARITY = 0.13
SHARPEN = 0.38


def to_arr(img):
    return np.asarray(img, dtype=np.float32)


def to_img(arr):
    a8 = np.clip(arr, 0, 255).astype(np.uint8)
    if a8.ndim == 3 and a8.shape[2] == 1:
        a8 = a8[..., 0]
    return Image.fromarray(a8)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def gauss(arr, sigma):
    """小半径走 PIL，大半径先降采样，兼顾质量与速度。"""
    if sigma <= 10:
        return to_arr(to_img(arr).filter(ImageFilter.GaussianBlur(sigma)))
    h, w = arr.shape[:2]
    s = max(2, int(sigma / 6))
    small = to_img(arr).resize((max(1, w // s), max(1, h // s)), Image.LANCZOS)
    small = small.filter(ImageFilter.GaussianBlur(sigma / s))
    return to_arr(small.resize((w, h), Image.BICUBIC))


def ellipse_mask(shape, cx, cy, rx, ry, feather=0.45, xs=None, ys=None):
    h, w = shape
    if ys is None:
        ys = np.arange(h, dtype=np.float32)
    if xs is None:
        xs = np.arange(w, dtype=np.float32)
    d = np.sqrt(((xs[None, :] - cx) / rx) ** 2 + ((ys[:, None] - cy) / ry) ** 2)
    return smoothstep((1.0 + feather - d) / feather)


def rot_ellipse_mask(shape, cx, cy, ra, rb, deg, feather=0.6):
    h, w = shape
    th = np.deg2rad(deg)
    co, si = np.cos(th), np.sin(th)
    X = np.arange(w, dtype=np.float32)[None, :] - cx
    Y = np.arange(h, dtype=np.float32)[:, None] - cy
    u = X * co + Y * si
    v = -X * si + Y * co
    return smoothstep((1.0 + feather - np.sqrt((u / ra) ** 2 + (v / rb) ** 2)) / feather)


def luma(arr):
    return arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114


def srgb_to_lin(a):
    n = np.clip(a / 255.0, 0, 1)
    return np.where(n <= 0.04045, n / 12.92, ((n + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055) * 255.0


def catmull_weights(t):
    t2, t3 = t * t, t * t * t
    return (
        -0.5 * t3 + t2 - 0.5 * t,
        1.5 * t3 - 2.5 * t2 + 1.0,
        -1.5 * t3 + 2.0 * t2 + 0.5 * t,
        0.5 * t3 - 0.5 * t2,
    )


def remap_cubic(a, xs, ys, dx, dy, strip=320):
    """Catmull-Rom 三次卷积重采样，按行分块控制内存。"""
    H, W = a.shape[:2]
    out = np.empty((len(ys), len(xs), 3), dtype=np.float32)
    for s in range(0, len(ys), strip):
        e = min(s + strip, len(ys))
        X = np.clip(xs[None, :] + dx[s:e], 1.0, W - 3.0)
        Y = np.clip(ys[s:e, None] + dy[s:e], 1.0, H - 3.0)
        X0 = np.floor(X).astype(np.int32)
        Y0 = np.floor(Y).astype(np.int32)
        wx = catmull_weights((X - X0)[..., None])
        wy = catmull_weights((Y - Y0)[..., None])
        acc = np.zeros((e - s, len(xs), 3), dtype=np.float32)
        for j in range(4):
            row = np.zeros_like(acc)
            for i in range(4):
                row += a[Y0 + j - 1, X0 + i - 1] * wx[i]
            acc += row * wy[j]
        out[s:e] = acc
    return out


def trapezoid(v, y1, y2, y3, y4):
    return smoothstep((v - y1) / (y2 - y1)) * (1.0 - smoothstep((v - y3) / (y4 - y3)))


def liquify(a):
    H, W = a.shape[:2]
    x0, x1, y0, y1 = W, 0, H, 0
    for cx, cy, rx, ry, f, *_ in WARP_PUSH + WARP_SCALE:
        x0 = min(x0, cx - (1 + f) * rx)
        x1 = max(x1, cx + (1 + f) * rx)
        y0 = min(y0, cy - (1 + f) * ry)
        y1 = max(y1, cy + (1 + f) * ry)
    for cx, hx, fx, yt, _ in WARP_PINCH_X:
        x0 = min(x0, cx - hx - fx)
        x1 = max(x1, cx + hx + fx)
        y0 = min(y0, yt[0])
        y1 = max(y1, yt[3])
    sh = SHOULDER
    x0 = min(x0, sh["cx"] - sh["hx"] - sh["fx"])
    x1 = max(x1, sh["cx"] + sh["hx"] + sh["fx"])
    y0 = min(y0, sh["y"][0])
    y1 = max(y1, sh["y"][3])
    x0, x1 = max(0, int(x0) - 6), min(W, int(x1) + 6)
    y0, y1 = max(0, int(y0) - 6), min(H, int(y1) + 6)

    xs = np.arange(x0, x1, dtype=np.float32)
    ys = np.arange(y0, y1, dtype=np.float32)
    shape = (len(ys), len(xs))
    dx = np.zeros(shape, dtype=np.float32)
    dy = np.zeros(shape, dtype=np.float32)

    for cx, cy, rx, ry, f, ax, ay in WARP_PUSH:
        m = ellipse_mask(shape, cx, cy, rx, ry, f, xs, ys)
        dx += ax * m
        dy += ay * m

    for cx, hx, fx, yt, amp in WARP_PINCH_X:
        wx = smoothstep((hx + fx - np.abs(xs - cx)) / fx)
        wy = trapezoid(ys, *yt)
        dx += amp * (wy[:, None] * wx[None, :]) * (xs[None, :] - cx)

    for cx, cy, rx, ry, f, amp in WARP_SCALE:
        m = ellipse_mask(shape, cx, cy, rx, ry, f, xs, ys)
        dx += amp * m * (xs[None, :] - cx)
        dy += amp * m * (ys[:, None] - cy)

    # 压肩：x 用平顶梯形，y 用四段梯形，避免把下巴一起拉下来
    wx = smoothstep((sh["hx"] + sh["fx"] - np.abs(xs - sh["cx"])) / sh["fx"])
    wy = trapezoid(ys, *sh["y"])
    dy -= sh["amount"] * wy[:, None] * wx[None, :]

    a[y0:y1, x0:x1] = remap_cubic(a, xs, ys, dx, dy)
    return a


def skin_color_mask(a):
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    Cb = 128 - 0.168736 * R - 0.331264 * G + 0.5 * B
    Cr = 128 + 0.5 * R - 0.418688 * G - 0.081312 * B

    def band(v, lo, hi, f):
        return np.clip((v - (lo - f)) / f, 0, 1) * np.clip(((hi + f) - v) / f, 0, 1)

    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = (mx - mn) / (mx + 1e-3)
    lip_guard = 1.0 - smoothstep((Cr - 158.0) / 16.0) * smoothstep((sat - 0.34) / 0.14)
    return (
        band(Cb, 80, 132, 10)
        * band(Cr, 132, 176, 10)
        * np.clip((luma(a) - 35) / 25, 0, 1)
        * lip_guard
    )


img = Image.open(SRC)
exif = img.info.get("exif")
img = img.convert("RGB")
W, H = img.size
a = to_arr(img)

# 1) 几何微调
a = liquify(a)

spot = ellipse_mask((H, W), *BODY, feather=0.85)

# 2) 暗部提亮：集中在新娘，背景保留深色氛围；黑场下压避免发灰
l = luma(a) / 255.0
a += ((1.0 - smoothstep(l / 0.55)) ** 1.5 * 12.0 * (0.20 + 0.80 * spot))[..., None]
a = (a - 7.0) * (255.0 / 248.0)

# 3) 暖色调 + 轻 S 曲线
a *= np.array([1.026, 1.002, 0.974], dtype=np.float32)
n = np.clip(a / 255.0, 0, 1)
a = (n + 0.10 * (n - 0.5) * (1.0 - np.abs(n - 0.5) * 2.0) * 2.0) * 255.0

# 4) 背景灯光光晕：在线性光下叠加，避免中间调发灰失质感
lin = srgb_to_lin(a)
hl = np.clip((luma(a) - 182.0) / 73.0, 0, 1) ** 1.5
glow = gauss(hl[..., None] * lin * 255.0, 60.0) / 255.0
lin += glow * np.array([0.20, 0.15, 0.09], dtype=np.float32)
a = lin_to_srgb(lin)

# 5) 新娘柔光 + 周边压暗
a *= (1.0 + 0.14 * spot)[..., None]
a += (spot[..., None] * np.array([4.0, 3.0, 2.0], dtype=np.float32))
a *= (1.0 - 0.20 * (1.0 - spot))[..., None]
a = np.clip(a, 0, 255)

# 6) 显白：肤色识别 + 区域遮罩 + 唇色/高光保护
area = np.zeros((H, W), dtype=np.float32)
for cx, cy, rx, ry, f, wgt in SKIN_AREAS:
    area = np.maximum(area, wgt * ellipse_mask((H, W), cx, cy, rx, ry, f))
L = luma(a)
dark_guard = smoothstep((L - (gauss(L, 60.0) - 48.0)) / 34.0)
w_skin = (
    area
    * skin_color_mask(a)
    * (1.0 - smoothstep((L - 198.0) / 57.0))
    * dark_guard
)
a += w_skin[..., None] * SKIN_LIFT * (255.0 - a)
g = luma(a)[..., None]
a = g + (a - g) * (1.0 - SKIN_DESAT * w_skin)[..., None]

# 7) 自然饱和度：红裙几乎不动，避免溢色
mx, mn = a.max(axis=2), a.min(axis=2)
sat = (mx - mn) / (mx + 1e-3)
g = luma(a)[..., None]
a = g + (a - g) * (1.0 + 0.20 * (1.0 - smoothstep(sat / 0.55)))[..., None]

# 8) 全局清晰度：提升布料与绣线质感；面部降权，避免加深法令纹与眼下细纹
face_soft = ellipse_mask((H, W), FACE[0], FACE[1], FACE[2] * 1.15, FACE[3] * 1.15, 0.55)
a += (a - gauss(a, 55.0)) * (CLARITY * (1.0 - 0.72 * face_soft))[..., None]
a = np.clip(a, 0, 255)

# 9) 面部频率分离：压中低频色块，毛孔级细节原样保留
fcx, fcy, frx, fry = FACE
pad = 260
cx0, cx1 = int(fcx - frx - pad), int(fcx + frx + pad)
cy0, cy1 = int(fcy - fry - pad), int(fcy + fry + pad)
crop = a[cy0:cy1, cx0:cx1].copy()
ch, cw = crop.shape[:2]
fmask = ellipse_mask((ch, cw), fcx - cx0, fcy - cy0, frx, fry, feather=0.5)
# 明显暗于局部肤色基准的像素（眉毛、睫毛、鼻孔、唇线）排除在磨皮之外
cl = luma(crop)
hair_guard = smoothstep((cl - (gauss(cl, 40.0) - 38.0)) / 28.0)
skin_w = fmask * skin_color_mask(crop) * hair_guard

b1 = gauss(crop, 3.0)
b2 = gauss(crop, 14.0)
b3 = gauss(crop, 55.0)
fine, mid, tone = crop - b1, b1 - b2, b2 - b3

k = BAND_KEEP
w3 = skin_w[..., None]
crop = (
    b3
    + tone * (1.0 + (k["tone"] - 1.0) * w3)
    + mid * (1.0 + (k["mid"] - 1.0) * w3)
    + fine * (1.0 + (k["fine"] - 1.0) * w3)
)
crop *= (1.0 + 0.035 * fmask)[..., None]

# 眼部：提升局部对比与锐度，让眼神更透
for ecx, ecy, erx, ery in (EYE_A, EYE_B):
    em = ellipse_mask((ch, cw), ecx - cx0, ecy - cy0, erx * 1.5, ery * 1.9, feather=0.6)
    crop += (crop - gauss(crop, 6.0)) * (em * 0.20)[..., None]
    crop += (crop - gauss(crop, 1.4)) * (em * 0.35)[..., None]

a[cy0:cy1, cx0:cx1] = np.clip(crop, 0, 255)

# 10) 输出锐化：暗部降权避免放大噪点；面部皮肤降权，五官与布料保持锐利
det = a - gauss(a, 1.2)
w_sharp = smoothstep((luma(a) - 28.0) / 62.0) * (0.62 + 0.38 * spot)
w_sharp *= 1.0 - 0.45 * face_soft * skin_color_mask(a)
a += det * (SHARPEN * w_sharp)[..., None]

# 11) 法令纹弱化：沿纹路向局部均值回归，保留走向但降低生硬感
target = gauss(a, 30.0)
for fcx_, fcy_, ra_, rb_, deg_, k_ in NASOLABIAL:
    m = rot_ellipse_mask((H, W), fcx_, fcy_, ra_, rb_, deg_, 0.7)
    a += (target - a) * (m * k_)[..., None]
a = np.clip(a, 0, 255)

out = to_img(a)
save_kw = dict(quality=98, subsampling=0, optimize=True)
if exif:
    save_kw["exif"] = exif
out.save(DST, **save_kw)
print("saved", DST, out.size)

pcx, ptop, pw = 3090, 780, 2050
ph = int(pw * 4 / 3)
out.crop((pcx - pw // 2, ptop, pcx + pw // 2, ptop + ph)).save(
    PORTRAIT, quality=98, subsampling=0
)
print("saved", PORTRAIT)


def side_by_side(before, after, path, box=None, width=1400):
    b, af = (before, after) if not box else (before.crop(box), after.crop(box))
    h = int(width / 2 * b.size[1] / b.size[0])
    canvas = Image.new("RGB", (width, h), "black")
    canvas.paste(b.resize((width // 2, h), Image.LANCZOS), (0, 0))
    canvas.paste(af.resize((width // 2, h), Image.LANCZOS), (width // 2, 0))
    canvas.save(path, quality=93)
    print("saved", path)


side_by_side(img, out, "compare_full.jpg")
side_by_side(img, out, "compare_face.jpg", box=(2500, 950, 3750, 2500))
side_by_side(img, out, "compare_neck.jpg", box=(2620, 1550, 3420, 2150), width=1600)
side_by_side(img, out, "compare_texture.jpg", box=(2760, 1380, 3260, 1780), width=1600)
