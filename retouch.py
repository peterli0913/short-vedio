"""婚宴照片修图：整体调色 + 新娘柔光 + 背景灯光光晕 + 保边柔肤。

新娘面部/身体位置为该张照片实测坐标，换图需重新标定 BRIDE_* 常量。
"""

import numpy as np
from PIL import Image, ImageFilter

SRC = "微信图片_20260728185148_2671_11.jpg"
DST = "微信图片_20260728185148_2671_11_retouched.jpg"

# 全图坐标（7008x4672）
BRIDE_FACE = (3065, 1600, 300, 380)   # cx, cy, rx, ry
BRIDE_BODY = (3080, 2150, 1150, 1900)


def to_arr(img):
    return np.asarray(img, dtype=np.float32)


def blur_big(arr, sigma, scale=8):
    """大半径模糊：先降采样再模糊，速度快且视觉等效。"""
    h, w = arr.shape[:2]
    small = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize(
        (w // scale, h // scale), Image.LANCZOS
    )
    small = small.filter(ImageFilter.GaussianBlur(sigma / scale))
    return to_arr(small.resize((w, h), Image.BICUBIC))


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def ellipse_mask(shape, cx, cy, rx, ry, feather=0.45):
    h, w = shape
    ys = np.arange(h, dtype=np.float32)[:, None]
    xs = np.arange(w, dtype=np.float32)[None, :]
    d = np.sqrt(((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2)
    return smoothstep((1.0 + feather - d) / feather)


def luma(arr):
    return arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114


img = Image.open(SRC).convert("RGB")
W, H = img.size
a = to_arr(img)

bcx, bcy, brx, bry = BRIDE_BODY
spot = ellipse_mask((H, W), bcx, bcy, brx, bry, feather=0.85)

# 1) 阴影提亮：暗部权重曲线，且主要作用于新娘，背景保留深色氛围
l = luma(a) / 255.0
shadow_w = (1.0 - smoothstep(l / 0.55)) ** 1.5
a += (shadow_w * 13.0 * (0.22 + 0.78 * spot))[..., None]

# 黑场下压，避免整体发灰
a = (a - 7.0) * (255.0 / 248.0)

# 2) 暖色调 + 轻微 S 曲线对比
a *= np.array([1.028, 1.002, 0.972], dtype=np.float32)
n = np.clip(a / 255.0, 0, 1)
a = (n + 0.10 * (n - 0.5) * (1.0 - np.abs(n - 0.5) * 2.0) * 2.0) * 255.0

# 3) 背景灯光光晕：提取高光做大半径模糊叠加，暖色调
hl = np.clip((luma(a) - 176.0) / 79.0, 0, 1) ** 1.4
glow = blur_big((hl[..., None] * a), 70.0)
a += glow * np.array([0.22, 0.17, 0.10], dtype=np.float32)

# 4) 新娘柔光：椭圆范围内提亮，外围压暗形成视觉引导
a *= (1.0 + 0.15 * spot)[..., None]
a += (spot[..., None] * np.array([6.0, 3.5, 1.0], dtype=np.float32))
a *= (1.0 - 0.22 * (1.0 - spot))[..., None]

# 5) 自然饱和度：低饱和区多加，高饱和区（红裙）几乎不动，避免溢色
mx = a.max(axis=2)
mn = a.min(axis=2)
sat = (mx - mn) / (mx + 1e-3)
gray = luma(a)[..., None]
a = gray + (a - gray) * (1.0 + 0.22 * (1.0 - smoothstep(sat / 0.55)))[..., None]

a = np.clip(a, 0, 255)

# 6) 面部保边柔肤：仅在低频区域（肤质）混合模糊，边缘（眼睛/唇/发丝）保留
fcx, fcy, frx, fry = BRIDE_FACE
pad = 260
x0, x1 = int(fcx - frx - pad), int(fcx + frx + pad)
y0, y1 = int(fcy - fry - pad), int(fcy + fry + pad)
crop = a[y0:y1, x0:x1].copy()
ch, cw = crop.shape[:2]

fmask = ellipse_mask((ch, cw), fcx - x0, fcy - y0, frx, fry, feather=0.5)

crop_img = Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8))
soft = to_arr(crop_img.filter(ImageFilter.GaussianBlur(9)))

edge = np.abs(luma(crop) - luma(soft))
keep = smoothstep((edge - 2.0) / 8.0)            # 边缘越强越保留原图
w_soft = fmask * 0.55 * (1.0 - keep)
crop = crop * (1 - w_soft[..., None]) + soft * w_soft[..., None]

# 色度柔化：减轻肤色不匀，不动亮度细节
y = luma(crop)[..., None]
chroma = crop - y
chroma_s = to_arr(
    Image.fromarray(np.clip(chroma + 128, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(16)
    )
) - 128
wc = (fmask * 0.6)[..., None]
crop = y + chroma * (1 - wc) + chroma_s * wc

# 柔肤后回补清晰度，让眼睛与唇部不发糊
sharp_base = to_arr(
    Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(2)
    )
)
crop += (crop - sharp_base) * (fmask * 0.55)[..., None]

# 面部轻提亮 + 一点暖光
crop *= (1.0 + 0.05 * fmask)[..., None]
crop += (fmask[..., None] * np.array([4.0, 2.0, 0.0], dtype=np.float32))

a[y0:y1, x0:x1] = crop
a = np.clip(a, 0, 255)

out = Image.fromarray(a.astype(np.uint8))
out.save(DST, quality=97, subsampling=0, optimize=True)
print("saved", DST, out.size)

# 对比图与面部特写，便于快速检查效果
def side_by_side(before, after, path, box=None, width=1400):
    b, af = before, after
    if box:
        b, af = b.crop(box), af.crop(box)
    h = int(width / 2 * b.size[1] / b.size[0])
    canvas = Image.new("RGB", (width, h), "black")
    canvas.paste(b.resize((width // 2, h), Image.LANCZOS), (0, 0))
    canvas.paste(af.resize((width // 2, h), Image.LANCZOS), (width // 2, 0))
    canvas.save(path, quality=92)
    print("saved", path)


side_by_side(img, out, "compare_full.jpg")
side_by_side(img, out, "compare_face.jpg", box=(2500, 950, 3750, 2500))
