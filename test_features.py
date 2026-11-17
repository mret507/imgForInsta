# -*- coding: utf-8 -*-
"""--ratio / --bg / メタデータ保持（--no-metadata） と読み込み時の向き補正のテスト。
中間生成物として test_features_*.jpg と square_resized/test_features_*.jpg を出力する。
"""
import os
import sys
from PIL import Image

from imgForInsta import compute_padding, save_square_image, parse_ratio, parse_background, output_dir_name


HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(HERE, 'square_resized')
COLOR = (180, 200, 230)

failures = 0


def check(cond: bool, msg: str) -> None:
    global failures
    if cond:
        print(f'[OK] {msg}')
    else:
        print(f'[FAIL] {msg}')
        failures += 1


def make_input(name: str, size=(1200, 900), with_exif=True, gps=False, orientation=None) -> str:
    path = os.path.join(HERE, name)
    img = Image.new('RGB', size, COLOR)
    exif = img.getexif()
    if with_exif:
        exif[271] = 'SONY'
        exif[272] = 'ILCE-7M4'
        ifd = exif.get_ifd(34665)
        ifd[42036] = 'FE 24-70mm F2.8 GM II'
        ifd[33437] = 2.8
        ifd[33434] = 1 / 250
        ifd[34855] = 400
    if gps:
        exif.get_ifd(34853)[1] = 'N'  # GPSLatitudeRef
    if orientation:
        exif[274] = orientation
    img.save(path, exif=exif, quality=95)
    return path


def run(path: str, out_name: str, **kw) -> Image.Image:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_square_image(path, OUTPUT_DIR, **kw)
    out = os.path.join(OUTPUT_DIR, out_name)
    im = Image.open(out)
    im.load()
    return im


def near(px, color, tol=12) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(px, color))


def main() -> int:
    # --- 引数パース ---
    check(abs(parse_ratio('4:5') - 0.8) < 1e-9, "parse_ratio('4:5') == 0.8")
    check(abs(parse_ratio('1.91:1') - 1.91) < 1e-9, "parse_ratio('1.91:1') == 1.91")
    check(output_dir_name('1:1') == 'square_resized', "output_dir_name('1:1') == 'square_resized'")
    check(output_dir_name('4:5') == '4_5_resized', "output_dir_name('4:5') == '4_5_resized'")
    check(output_dir_name('1.91:1') == '1.91_1_resized', "output_dir_name('1.91:1') == '1.91_1_resized'")
    check(parse_background('#FF0000') == (0, 0, 255), "parse_background('#FF0000') -> BGR (0,0,255)")
    check(parse_background('Blur') == 'blur', "parse_background('Blur') -> 'blur'")

    # --- compute_padding: 1:1 は従来どおり max_dim + 2*margin の正方形 ---
    t, b, l, r = compute_padding(900, 1200, 1.0, 100)
    check((1200 + l + r, 900 + t + b) == (1400, 1400), f'1:1 landscape canvas 1400x1400 (got {1200 + l + r}x{900 + t + b})')
    # ラベル領域が足りない縦長: 上余白は margin 以上残す
    t, b, l, r = compute_padding(1200, 900, 1.0, 100, bottom_area=300)
    check(t >= 100 and b >= 300, f'portrait label: top>=100, bottom>=300 (got top={t}, bottom={b})')
    W, H = 900 + l + r, 1200 + t + b
    check(abs(W - H) <= 1, f'portrait label keeps square ({W}x{H})')

    # --- --ratio 4:5 ---
    src = make_input('test_features_input.jpg')
    for label in (True, False):
        name = 'test_features_input.jpg' if label else 'test_features_input_no-label.jpg'
        im = run(src, name, ratio=0.8, show_label=label)
        w, h = im.size
        check(abs(w / h - 0.8) < 0.002, f'4:5 output (label={label}): {w}x{h} ratio={w / h:.4f}')

    # --- --bg black: 角が黒、ラベルは明るい色で描かれる ---
    im = run(src, 'test_features_input.jpg', background=(0, 0, 0))
    w, h = im.size
    check(near(im.getpixel((0, 0)), (0, 0, 0)), f'black bg corner = {im.getpixel((0, 0))}')
    label_region = im.convert('L').crop((0, h - int(h * 0.06), w, h))
    check(label_region.getextrema()[1] > 150, f'label is bright on black bg (max={label_region.getextrema()[1]})')

    # --- --bg blur: 単色写真ならぼかし背景も同じ色 ---
    im = run(src, 'test_features_input_no-label.jpg', background='blur', show_label=False)
    check(near(im.getpixel((5, 5)), COLOR), f'blur bg corner ~ photo color ({im.getpixel((5, 5))})')

    # --- デフォルト（メタデータ保持）: EXIF/ICC を保持し GPS を除去 ---
    gps_src = make_input('test_features_gps.jpg', gps=True)
    im = run(gps_src, 'test_features_gps.jpg')
    exif = im.getexif()
    check(exif.get(272) == 'ILCE-7M4', f"metadata: Model kept ({exif.get(272)!r})")
    check(exif.get_ifd(34665).get(42036) == 'FE 24-70mm F2.8 GM II', 'metadata: LensModel kept')
    check(34853 not in exif, 'metadata: GPS removed')
    check(bool(im.info.get('icc_profile')), 'metadata: sRGB ICC embedded')

    im = run(gps_src, 'test_features_gps.jpg', keep_metadata=False)
    check(len(im.getexif()) == 0 and not im.info.get('icc_profile'), 'no-metadata: metadata stripped')

    # --- EXIF Orientation=6（90度回転）は読み込み時に縦向きへ補正 ---
    rot_src = make_input('test_features_rot.jpg', size=(1200, 900), with_exif=False, orientation=6)
    im = run(rot_src, 'test_features_rot_no-label.jpg', ratio=0.8, show_label=False, extra_margin=0)
    w, h = im.size
    check((w, h) == (960, 1200), f'orientation applied: 900x1200 photo -> 4:5 canvas 960x1200 (got {w}x{h})')

    print()
    if failures:
        print(f'[RESULT] {failures} failure(s)')
        return 1
    print('[RESULT] all assertions passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
