# -*- coding: utf-8 -*-
"""EXIFラベル機能のテスト。
1. EXIF（カメラ・レンズ・F値・SS・ISO）を持つテスト画像を生成
2. get_exif_label が想定行を返すか確認
3. save_square_image が出力ファイルを生成するか確認
"""
import os
import sys
from PIL import Image

from imgForInsta import get_exif_label, save_square_image


HERE = os.path.dirname(os.path.abspath(__file__))
TEST_INPUT = os.path.join(HERE, 'test_label_input.jpg')
OUTPUT_DIR = os.path.join(HERE, 'square_resized')


def make_test_image(path: str) -> None:
    img = Image.new('RGB', (1200, 900), (180, 200, 230))
    exif = img.getexif()
    exif[271] = 'SONY'             # Make
    exif[272] = 'ILCE-7M4'         # Model

    ifd = exif.get_ifd(34665)      # ExifIFD
    ifd[42036] = 'FE 24-70mm F2.8 GM II'  # LensModel
    ifd[33437] = 2.8               # FNumber
    ifd[33434] = 1 / 250           # ExposureTime
    ifd[34855] = 400               # PhotographicSensitivity (ISO)

    img.save(path, exif=exif, quality=95)


def main() -> int:
    failures = 0

    make_test_image(TEST_INPUT)
    assert os.path.exists(TEST_INPUT), 'test input image was not created'
    print(f'[OK] generated test image: {TEST_INPUT} ({os.path.getsize(TEST_INPUT)} bytes)')

    # 1) get_exif_label
    lines = get_exif_label(TEST_INPUT)
    print(f'[INFO] get_exif_label -> {lines}')

    if not lines:
        print('[FAIL] get_exif_label returned None/empty')
        return 1

    if len(lines) != 2:
        print(f'[FAIL] expected 2 lines, got {len(lines)}')
        failures += 1

    if 'SONY' not in lines[0] or 'ILCE-7M4' not in lines[0] or '24-70' not in lines[0]:
        print(f'[FAIL] line1 missing camera/lens: {lines[0]!r}')
        failures += 1
    else:
        print(f'[OK] line1 contains camera/lens: {lines[0]!r}')

    line2 = lines[1] if len(lines) > 1 else ''
    for needle in ('F2.8', '1/250s', 'ISO400'):
        if needle not in line2:
            print(f'[FAIL] line2 missing {needle!r}: {line2!r}')
            failures += 1
        else:
            print(f'[OK] line2 contains {needle!r}')

    # 2) save_square_image (label on)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    save_square_image(TEST_INPUT, OUTPUT_DIR, extra_margin=100, max_size_mb=9.0,
                      quality_start=95, quality_min=10, show_label=True)
    out_path = os.path.join(OUTPUT_DIR, 'test_label_input.jpg')
    if not os.path.exists(out_path):
        print(f'[FAIL] output not produced: {out_path}')
        failures += 1
    else:
        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        with Image.open(out_path) as im:
            w, h = im.size
        if w != h:
            print(f'[FAIL] output is not square: {w}x{h}')
            failures += 1
        else:
            print(f'[OK] labeled output: {out_path} ({size_mb:.2f} MB, {w}x{h})')

    # 3) save_square_image (label off)
    save_square_image(TEST_INPUT, OUTPUT_DIR, extra_margin=100, max_size_mb=9.0,
                      quality_start=95, quality_min=10, show_label=False)
    out_path_nl = os.path.join(OUTPUT_DIR, 'test_label_input_no-label.jpg')
    if not os.path.exists(out_path_nl):
        print(f'[FAIL] no-label output not produced: {out_path_nl}')
        failures += 1
    else:
        with Image.open(out_path_nl) as im:
            w, h = im.size
        if w != h:
            print(f'[FAIL] no-label output is not square: {w}x{h}')
            failures += 1
        else:
            print(f'[OK] no-label output: {out_path_nl} ({w}x{h})')

    print()
    if failures:
        print(f'[RESULT] {failures} failure(s)')
        return 1
    print('[RESULT] all assertions passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
