"""婚宴照片修图：几何微调 + 调色打光 + 显白 + 保边柔肤。

坐标均为原图 7008x4672 下实测，换照片必须重新标定 BRIDE_*/WARP_*/SKIN_* 常量。
"""

import numpy as np
from PIL import Image, ImageFilter

SRC = "微信图片_20260728185148_2671_11.jpg"
DST = "微信图片_20260728185148_2671_11_retouched.jpg"
PORTRAIT = "新娘竖构图_retouched.jpg"

BRIDE_FACE = (3065, 1600, 300, 380)   # cx, cy, rx, ry
BRIDE_BODY = (3080, 2150, 1150, 1900)

# 液化瘦身：横向收窄（pinch）。amp 为最大收窄比例
WARP_PINCH = [
    (2990, 1800, 400, 330, 0.60, 0.032),   # 下半脸 / 下颌线
    (3060, 1950, 270, 150, 0.80, 0.090),   # 颈部（重点）
    (3060, 3100, 800, 1600, 0.60, 0.035),  # 身体轮廓
]
# 下颌收紧：颏下内容上移，让下颌线更利落
WARP_LIFT = (2990, 1935, 230, 110, 0.70, 8.0)

# 显白：spatial 遮罩 + 肤色识别 + 高光保护
SKIN_AREAS = [
    (3020, 1620, 400, 430, 0.55, 1.00),   # 面部
    (3050, 1935, 310, 165, 0.80, 1.00),   # 颈部
    (2650, 3000, 340, 390, 0.70, 0.42),   # 右臂 / 手
    (3180, 3170, 200, 200, 0.80, 0.42),   # 左手
]
SKIN_LIFT = np.array([0.105, 0.115, 0.142], dtype=np.float32)  # 偏冷一点＝显白
SKIN_DESAT = 0.05


def to_arr(img):
    return np.asarray(img, dtype=np.float32)


def to_img(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def blur_big(arr, sigma, scale=8):
    """大半径模糊：降采样后模糊再放大，视觉等效且快得多。"""
    h, w = arr.shape[:2]
    small = to_img(arr).resize((w // scale, h // scale), Image.LANCZOS)
    small = small.filter(ImageFilter.GaussianBlur(sigma / scale))
    return to_arr(small.resize((w, h), Image.BICUBIC))


def ellipse_mask(shape, cx, cy, rx, ry, feather=0.45, xs=None, ys=None):
    h, w = shape
    if ys is None:
        ys = np.arange(h, dtype=np.float32)
    if xs is None:
        xs = np.arange(w, dtype=np.float32)
    d = np.sqrt(((xs[None, :] - cx) / rx) ** 2 + ((ys[:, None] - cy) / ry) ** 2)
    return smoothstep((1.0 + feather - d) / feather)


def luma(arr):
    return arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114


def liquify(a):
    """按 WARP_PINCH / WARP_LIFT 做局部变形，只在受影响的包围盒内重采样。"""
    H, W = a.shape[:2]

    xs_all = [c[0] - (1 + c[4]) * c[2] for c in WARP_PINCH] + [
        WARP_LIFT[0] - (1 + WARP_LIFT[4]) * WARP_LIFT[2]
    ]
    xe_all = [c[0] + (1 + c[4]) * c[2] for c in WARP_PINCH] + [
        WARP_LIFT[0] + (1 + WARP_LIFT[4]) * WARP_LIFT[2]
    ]
    ys_all = [c[1] - (1 + c[4]) * c[3] for c in WARP_PINCH] + [
        WARP_LIFT[1] - (1 + WARP_LIFT[4]) * WARP_LIFT[3]
    ]
    ye_all = [c[1] + (1 + c[4]) * c[3] for c in WARP_PINCH] + [
        WARP_LIFT[1] + (1 + WARP_LIFT[4]) * WARP_LIFT[3]
    ]
    x0 = max(0, int(min(xs_all)) - 4)
    x1 = min(W, int(max(xe_all)) + 4)
    y0 = max(0, int(min(ys_all)) - 4)
    y1 = min(H, int(max(ye_all)) + 4)

    xs = np.arange(x0, x1, dtype=np.float32)
    ys = np.arange(y0, y1, dtype=np.float32)
    shape = (len(ys), len(xs))

    dx = np.zeros(shape, dtype=np.float32)
    dy = np.zeros(shape, dtype=np.float32)

    for cx, cy, rx, ry, f, amp in WARP_PINCH:
        m = ellipse_mask(shape, cx, cy, rx, ry, f, xs, ys)
        dx += amp * m * (xs[None, :] - cx)

    cx, cy, rx, ry, f, amt = WARP_LIFT
    dy += amt * ellipse_mask(shape, cx, cy, rx, ry, f, xs, ys)

    X = np.clip(xs[None, :] + dx, 0, W - 1.001)
    Y = np.clip(ys[:, None] + dy, 0, H - 1.001)
    X0 = X.astype(np.int32)
    Y0 = Y.astype(np.int32)
    fx = (X - X0)[..., None]
    fy = (Y - Y0)[..., None]
    X1 = X0 + 1
    Y1 = Y0 + 1

    out = (
        a[Y0, X0] * (1 - fx) * (1 - fy)
        + a[Y0, X1] * fx * (1 - fy)
        + a[Y1, X0] * (1 - fx) * fy
        + a[Y1, X1] * fx * fy
    )
    a[y0:y1, x0:x1] = out
    return a


def skin_color_mask(a):
    """YCbCr 肤色识别，避开红裙与深色背景。"""
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


img = Image.open(SRC).convert("RGB")
W, H = img.size
a = to_arr(img)

# 1) 几何微调（先做变形，后续遮罩基于成形后的位置）
a = liquify(a)

bcx, bcy, brx, bry = BRIDE_BODY
spot = ellipse_mask((H, W), bcx, bcy, brx, bry, feather=0.85)

# 2) 阴影提亮：主要作用于新娘，背景保留深色氛围
l = luma(a) / 255.0
shadow_w = (1.0 - smoothstep(l / 0.55)) ** 1.5
a += (shadow_w * 13.0 * (0.22 + 0.78 * spot))[..., None]
a = (a - 7.0) * (255.0 / 248.0)          # 黑场下压，避免整体发灰

# 3) 暖色调 + 轻 S 曲线对比
a *= np.array([1.028, 1.002, 0.972], dtype=np.float32)
n = np.clip(a / 255.0, 0, 1)
a = (n + 0.10 * (n - 0.5) * (1.0 - np.abs(n - 0.5) * 2.0) * 2.0) * 255.0

# 4) 背景灯光光晕
hl = np.clip((luma(a) - 176.0) / 79.0, 0, 1) ** 1.4
glow = blur_big((hl[..., None] * a), 70.0)
a += glow * np.array([0.22, 0.17, 0.10], dtype=np.float32)

# 5) 新娘柔光 + 周边压暗
a *= (1.0 + 0.15 * spot)[..., None]
a += (spot[..., None] * np.array([6.0, 3.5, 1.0], dtype=np.float32))
a *= (1.0 - 0.22 * (1.0 - spot))[..., None]
a = np.clip(a, 0, 255)

# 6) 显白：提亮 + 轻微降饱和，高光区不再推白以免过曝
area = np.zeros((H, W), dtype=np.float32)
for cx, cy, rx, ry, f, wgt in SKIN_AREAS:
    area = np.maximum(area, wgt * ellipse_mask((H, W), cx, cy, rx, ry, f))
w_skin = area * skin_color_mask(a) * (1.0 - smoothstep((luma(a) - 198.0) / 57.0))
a += w_skin[..., None] * SKIN_LIFT * (255.0 - a)
gray = luma(a)[..., None]
a = gray + (a - gray) * (1.0 - SKIN_DESAT * w_skin)[..., None]

# 7) 自然饱和度：低饱和区多加，红裙几乎不动，避免溢色
mx, mn = a.max(axis=2), a.min(axis=2)
sat = (mx - mn) / (mx + 1e-3)
gray = luma(a)[..., None]
a = gray + (a - gray) * (1.0 + 0.22 * (1.0 - smoothstep(sat / 0.55)))[..., None]
a = np.clip(a, 0, 255)

# 8) 面部保边柔肤：低频（肤质）柔化，边缘（眼睛/唇/发丝）保留
fcx, fcy, frx, fry = BRIDE_FACE
pad = 260
x0, x1 = int(fcx - frx - pad), int(fcx + frx + pad)
y0, y1 = int(fcy - fry - pad), int(fcy + fry + pad)
crop = a[y0:y1, x0:x1].copy()
ch, cw = crop.shape[:2]
fmask = ellipse_mask((ch, cw), fcx - x0, fcy - y0, frx, fry, feather=0.5)

soft = to_arr(to_img(crop).filter(ImageFilter.GaussianBlur(9)))
keep = smoothstep((np.abs(luma(crop) - luma(soft)) - 2.0) / 8.0)
w_soft = fmask * 0.55 * (1.0 - keep)
crop = crop * (1 - w_soft[..., None]) + soft * w_soft[..., None]

# 色度柔化：减轻肤色不匀，不动亮度细节
y = luma(crop)[..., None]
chroma = crop - y
chroma_s = to_arr(to_img(chroma + 128).filter(ImageFilter.GaussianBlur(16))) - 128
wc = (fmask * 0.6)[..., None]
crop = y + chroma * (1 - wc) + chroma_s * wc

# 柔肤后回补清晰度，避免眼唇发糊
crop += (crop - to_arr(to_img(crop).filter(ImageFilter.GaussianBlur(2)))) * (fmask * 0.55)[..., None]
crop *= (1.0 + 0.04 * fmask)[..., None]

a[y0:y1, x0:x1] = crop
a = np.clip(a, 0, 255)

out = to_img(a)
out.save(DST, quality=97, subsampling=0, optimize=True)
print("saved", DST, out.size)

# 3:4 竖构图，去掉前景遮挡人物
pcx, ptop, pw = 3090, 780, 2050
ph = int(pw * 4 / 3)
out.crop((pcx - pw // 2, ptop, pcx + pw // 2, ptop + ph)).save(
    PORTRAIT, quality=97, subsampling=0
)
print("saved", PORTRAIT)


def side_by_side(before, after, path, box=None, width=1400):
    b, af = (before, after) if not box else (before.crop(box), after.crop(box))
    h = int(width / 2 * b.size[1] / b.size[0])
    canvas = Image.new("RGB", (width, h), "black")
    canvas.paste(b.resize((width // 2, h), Image.LANCZOS), (0, 0))
    canvas.paste(af.resize((width // 2, h), Image.LANCZOS), (width // 2, 0))
    canvas.save(path, quality=92)
    print("saved", path)


side_by_side(img, out, "compare_full.jpg")
side_by_side(img, out, "compare_face.jpg", box=(2500, 950, 3750, 2500))
side_by_side(img, out, "compare_neck.jpg", box=(2620, 1550, 3420, 2150), width=1600)
