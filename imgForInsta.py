# -*- coding: utf-8 -*-
import os
import cv2
import sys
import argparse
import concurrent.futures
import multiprocessing
import numpy as np
import io
from tqdm import tqdm
from typing import Optional, List, Tuple

"""
imgForInsta.py

Usage:
    python imgForInsta.py [<directory_or_file_path>] [<margin_size>]

If a directory path is given, all JPG/JPEG/PNG files in the directory are processed.
If a file path is given and it's an image, only that file will be processed.
If no path is given, the script directory is used.
"""

# ラベル内の項目区切り（描画時は細い縦線に置き換える）
LABEL_SEP = ' | '
# 行ごとのスタイル (フォントの太さ, 文字色RGB)。行数がこれを超える場合は最後のスタイルを使う
_LABEL_STYLES = [('semibold', (40, 40, 40)), ('light', (125, 125, 125))]
_LABEL_SEP_COLOR = (200, 200, 200)
_LABEL_TRACKING = 0.06  # 字間（フォントサイズ比）
_LABEL_SEP_GAP = 0.8    # 区切り線の左右の間隔（フォントサイズ比）


def get_exif_label(input_file: str) -> Optional[List[str]]:
    """EXIFからラベル行のリストを返す。
    1行目: カメラメーカー+モデル と レンズモデル
    2行目: F値・シャッタースピード・ISO感度
    取得できない場合はNone。
    """
    try:
        from PIL import Image
        ext = os.path.splitext(input_file)[1].lower()
        if ext in ('.heif', '.heic'):
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except Exception:
                pass
        with Image.open(input_file) as img:
            exif = img.getexif()
            ifd_exif = exif.get_ifd(34665)

            make  = str(exif.get(271, '')).strip()
            model = str(exif.get(272, '')).strip()
            lens  = str(ifd_exif.get(42036, '')).strip()
            # Model にメーカー名が含まれる場合（例: "Canon EOS R5"）は Make を重ねない
            if make and not model.lower().startswith(make.split()[0].lower()):
                camera = f"{make} {model}".strip()
            else:
                camera = model or make
            line1_parts = [p for p in [camera, lens] if p]
            line1 = LABEL_SEP.join(line1_parts) if line1_parts else None

            # F値・シャッタースピード・ISO感度
            fnumber  = ifd_exif.get(33437)  # FNumber
            exposure = ifd_exif.get(33434)  # ExposureTime
            iso      = ifd_exif.get(34855)  # PhotographicSensitivity
            # ISO はリスト/タプルで入る場合があるので先頭を取得
            if isinstance(iso, (list, tuple)) and iso:
                iso = iso[0]

            line2_parts: List[str] = []
            if fnumber is not None:
                try:
                    line2_parts.append(f"f/{float(fnumber):g}")
                except Exception:
                    pass
            if exposure is not None:
                try:
                    et = float(exposure)
                    if et >= 1:
                        line2_parts.append(f"{et:g}s")
                    elif et > 0:
                        line2_parts.append(f"1/{round(1 / et)}s")
                except Exception:
                    pass
            if iso is not None:
                try:
                    line2_parts.append(f"ISO {int(iso)}")
                except Exception:
                    pass
            line2 = LABEL_SEP.join(line2_parts) if line2_parts else None

            lines = [l for l in [line1, line2] if l]
            return lines if lines else None
    except Exception:
        return None


def _load_font(size: int, weight: str = 'regular'):
    """指定サイズ・太さのTrueTypeフォントを返す。見つからない場合はPILデフォルトフォント。"""
    # TODO: 設定値管理にする？
    from PIL import ImageFont
    candidates = {
        'semibold': ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/calibrib.ttf"],
        'light':    ["C:/Windows/Fonts/segoeuisl.ttf", "C:/Windows/Fonts/calibril.ttf"],
    }.get(weight, [])
    for path in candidates + [
        # "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _line_style(index: int) -> Tuple[str, Tuple[int, int, int]]:
    return _LABEL_STYLES[min(index, len(_LABEL_STYLES) - 1)]


def _segment_width(draw, text: str, font, tracking: float) -> float:
    """字間 tracking(px) を加えたテキスト幅。"""
    if not text:
        return 0.0
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking * (len(text) - 1)


def _line_width(draw, line: str, font, font_size: int) -> float:
    """区切り線・字間込みで1行を描画したときの幅。"""
    segments = line.split(LABEL_SEP)
    tracking = font_size * _LABEL_TRACKING
    width = sum(_segment_width(draw, seg, font, tracking) for seg in segments)
    return width + (len(segments) - 1) * 2 * font_size * _LABEL_SEP_GAP


def _measure_font_size(lines: List[str], target_width: int) -> int:
    """最も幅の広い行が target_width になるフォントサイズを計算して返す（描画なし）。"""
    from PIL import Image, ImageDraw
    font_size = max(16, int(target_width * 0.08))
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    for _ in range(2):
        rw = max(_line_width(draw, line, _load_font(font_size, _line_style(i)[0]), font_size)
                 for i, line in enumerate(lines))
        if rw > 0:
            font_size = max(16, int(font_size * target_width / rw))
    return font_size


def draw_label(image: np.ndarray, lines: List[str], bottom_area: int, font_size: int = 0) -> np.ndarray:
    """画像下部のbottom_area領域に複数行linesを中央揃え描画して返す。
    1行目はセミボールドの濃いグレー、2行目以降はセミライトの淡いグレーで、字間を少し空ける。
    LABEL_SEP で区切られた項目の間には細い縦線を描く。
    font_size が指定された場合はそのサイズを使用し、0の場合は最長行が画像幅の2/3に収まるよう自動計算する。"""
    from PIL import Image, ImageDraw
    h, w = image.shape[:2]
    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    if font_size == 0:
        font_size = _measure_font_size(lines, int(w * 2 / 3))

    line_gap = int(font_size * 0.4)
    tracking = font_size * _LABEL_TRACKING
    sep_gap = font_size * _LABEL_SEP_GAP
    sep_width = max(1, round(font_size / 18))

    # 各行のフォント・インク上端/下端を求める（行ごとに太さが異なるため）
    metrics = []
    for i, line in enumerate(lines):
        weight, color = _line_style(i)
        font = _load_font(font_size, weight)
        _, top, _, bottom = draw.textbbox((0, 0), line.replace(LABEL_SEP, ' '), font=font)
        metrics.append((font, color, top, bottom))

    total_h = sum(m[3] - m[2] for m in metrics) + line_gap * max(0, len(lines) - 1)
    y = h - bottom_area + (bottom_area - total_h) // 2
    for line, (font, color, top, bottom) in zip(lines, metrics):
        x = max(0.0, (w - _line_width(draw, line, font, font_size)) / 2)
        for j, seg in enumerate(line.split(LABEL_SEP)):
            if j > 0:
                # 項目の区切りは文字の高さに合わせた細い縦線
                sx = round(x + sep_gap)
                draw.line([(sx, y), (sx, y + bottom - top)], fill=_LABEL_SEP_COLOR, width=sep_width)
                x += 2 * sep_gap
            for ch in seg:
                draw.text((x, y - top), ch, fill=color, font=font)
                x += draw.textlength(ch, font=font) + tracking
            x -= tracking if seg else 0
        y += bottom - top + line_gap
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def make_square(image: np.ndarray, margin_color: Tuple[int, int, int] = (255, 255, 255), extra_margin: int = 100, label_shift: int = 0, label_extra: int = 0) -> np.ndarray:
    """正方形にパディングする。
    label_shift: 画像を上方向にシフトするpx数（既存の上余白の範囲内でキャップ）
    label_extra: テキスト用に下余白へ追加するpx数。正方形を保つため左右にも label_extra//2 ずつ追加する。
    """
    height, width = image.shape[:2]

    if height != width:
        max_dim = max(height, width)
        sym_v = (max_dim - height) // 2 + extra_margin
        sym_h = (max_dim - width) // 2 + extra_margin
        cap = min(label_shift, sym_v)
        top  = sym_v - cap
        bot  = sym_v + cap + label_extra
        left = right = sym_h + label_extra // 2
    else:
        cap  = min(label_shift, extra_margin)
        top  = extra_margin - cap
        bot  = extra_margin + cap + label_extra
        left = right = extra_margin + label_extra // 2

    return cv2.copyMakeBorder(image, top, bot, left, right, cv2.BORDER_CONSTANT, value=margin_color)

def load_image_as_bgr(input_file: str) -> Optional[np.ndarray]:
    """Load image file into a BGR numpy array suitable for OpenCV.

    Supports JPEG/JPG via OpenCV. Supports HEIF/HEIC via Pillow + pillow_heif if available.
    Returns None on failure.
    """
    ext = os.path.splitext(input_file)[1].lower()
    if ext in ('.jpg', '.jpeg'):
        # cv2.imread は Windows で日本語パスを扱えないため fromfile + imdecode を使う
        try:
            data = np.fromfile(input_file, dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            return None

    if ext in ('.heif', '.heic'):
        try:
            from PIL import Image
            # pillow-heif は Pillow に HEIF オープナーを登録します
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except Exception:
                # pillow_heif がインストールされていない場合は pyheif を試す可能性があります
                pass

            im = Image.open(input_file)
            # ICC プロファイルが埋め込まれている場合は sRGB に変換して色ずれを抑える
            try:
                icc = im.info.get('icc_profile')
                if icc:
                    try:
                        from PIL import ImageCms
                        src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                        dst_profile = ImageCms.createProfile('sRGB')
                        im = ImageCms.profileToProfile(im, src_profile, dst_profile, outputMode='RGB')
                    except Exception:
                        # ImageCms が利用できない、またはプロファイル変換に失敗した場合はフォールバック
                        im = im.convert('RGB')
                else:
                    im = im.convert('RGB')
            except Exception:
                # 何らかの理由でプロファイル処理が失敗した場合でも画像をRGBに変換して続行
                im = im.convert('RGB')

            arr = np.array(im)  # RGB（赤・緑・青）
            # RGB を OpenCV の BGR に変換
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"Error: Cannot read HEIF file '{input_file}'. Install 'pillow-heif' or 'pyheif' (error: {e}).")
            return None

    # サポート外
    print(f"Error: Unsupported file extension for '{input_file}'. Supported: .jpg/.jpeg/.heif/.heic")
    return None


def save_square_image(input_file: str, output_dir: str, extra_margin: int = 100, max_size_mb: float = 9.0, quality_start: int = 95, quality_min: int = 10, show_label: bool = True) -> None:
    image: Optional[np.ndarray] = load_image_as_bgr(input_file)

    if image is None:
        print(f"Error: Failed to load image '{input_file}'. Skipping.")
        return

    exif_lines: Optional[List[str]] = get_exif_label(input_file) if show_label else None
    label_shift: int = 0
    label_extra: int = 0
    bottom_area: int = 0
    font_size: int = 0

    if exif_lines:
        h, w = image.shape[:2]
        max_dim = max(h, w)
        sq_width = max_dim + 2 * extra_margin
        font_size = _measure_font_size(exif_lines, int(sq_width * 2 / 3))
        # 画像幅の 2% を上限として最終比率を決める
        font_size = max(8, min(font_size, int(sq_width * 0.02)))
        # 行数に応じた bottom_area (n行 + line_gap(0.4) + 上下パディング(1.2))
        n = len(exif_lines)
        bottom_area = int(font_size * (n + 0.4 * (n - 1) + 1.2))

        # 元の下余白（パディング後・シフト前）で bottom_area を賄えるか判定
        base_bottom = (max_dim - h) // 2 + extra_margin
        needed = bottom_area - base_bottom
        if needed <= 0:
            # 下余白が既に十分: シフトも拡張も不要
            label_shift = 0
            label_extra = 0
        else:
            # 上余白は最低 extra_margin を残す（ラベルなし時と同等の間隔を確保）
            shift_budget = (max_dim - h) // 2
            label_shift = min(needed, shift_budget)
            # シフトで足りない分は余白拡張で対応（写真が相対的に小さくなる）
            label_extra = needed - label_shift
            label_extra += label_extra % 2  # 奇数だと左右で1px差が出るため偶数に揃える

    square_image: np.ndarray = make_square(image, extra_margin=extra_margin, label_shift=label_shift, label_extra=label_extra)

    if exif_lines:
        square_image = draw_label(square_image, exif_lines, bottom_area, font_size)

    # 出力先のファイル名を設定
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    in_ext = os.path.splitext(input_file)[1].lower()
    name_suffix = '' if show_label else '_no-label'
    # HEIF を JPEG に変換して保存する（OpenCV の書き出しで HEIF を扱うのは環境依存）
    if in_ext in ('.heif', '.heic'):
        out_name = base_name + name_suffix + '.jpg'
    else:
        out_name = base_name + name_suffix + in_ext

    output_path = os.path.join(output_dir, out_name)

    # cv2.imwrite は Windows で日本語パスを扱えないため imencode + tofile を使う
    def _write_jpeg(path: str, img: np.ndarray, q: int) -> None:
        ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, q])
        if not ok:
            raise IOError(f'Failed to encode JPEG for {path}')
        buf.tofile(path)

    # 最初は高めの品質から保存
    quality = quality_start
    _write_jpeg(output_path, square_image, quality)

    # サイズが収まるまで繰り返し（品質に下限を設定して無限ループを防ぐ）
    while os.path.getsize(output_path) / (1024*1024) > max_size_mb:
        quality -= 3
        if quality < quality_min:
            # これ以上品質を下げられないのでループを抜ける
            print(f"Warning: Reached minimum quality for '{output_path}', file may still be larger than {max_size_mb}MB.")
            break
        _write_jpeg(output_path, square_image, quality)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make square images for Instagram-like posts. Supports JPG/JPEG and HEIF/HEIC (HEIF requires additional libraries).")
    parser.add_argument('path', nargs='?', default=None, help='Directory or image file path. 省略時はフォルダ選択ダイアログを表示。')
    parser.add_argument('-m', '--margin', type=int, default=100, help='Extra margin to add around the image (default: 100)')
    parser.add_argument('-w', '--workers', type=int, default=max(1, multiprocessing.cpu_count() - 1), help='Number of parallel worker processes (default: cpu_count-1)')
    parser.add_argument('--max-size', type=float, default=9.0, help='Maximum output file size in MB (default: 9)')
    parser.add_argument('--quality-min', type=int, default=10, help='Minimum JPEG quality when shrinking (default: 10)')
    parser.add_argument('--no-label', action='store_true', default=False, help='カメラ/レンズ情報をラベル表示しない（デフォルト: 表示する）')
    args = parser.parse_args()

    path_arg: Optional[str] = args.path
    margin_size: int = args.margin
    workers: int = args.workers
    max_size: float = args.max_size
    quality_min: int = args.quality_min
    show_label: bool = not args.no_label

    # 引数省略時はフォルダ選択ダイアログを表示
    if path_arg is None:
        import tkinter
        from tkinter import filedialog
        root = tkinter.Tk()
        root.withdraw()
        path_arg = filedialog.askdirectory(title='処理するフォルダを選択')
        root.destroy()
        if not path_arg:
            print('キャンセルされました。')
            sys.exit(0)

    # 判定とファイルリスト作成（PNG は除外、HEIF を追加）
    if os.path.isfile(path_arg):
        ext = os.path.splitext(path_arg)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.heif', '.heic'):
            print(f"Error: The specified file '{path_arg}' is not a supported image (jpg/jpeg/heif/heic).")
            sys.exit(1)

        input_files: List[str] = [path_arg]
        output_dir: str = os.path.join(os.path.dirname(path_arg), "square_resized")
        os.makedirs(output_dir, exist_ok=True)

    elif os.path.isdir(path_arg):
        input_dir = path_arg
        exts = ('.jpg', '.jpeg', '.heif', '.heic')
        input_files: List[str] = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith(exts)]
        if not input_files:
            print(f"No supported files (jpg/jpeg/heif/heic) found in the directory '{input_dir}'.")
            sys.exit(1)

        output_dir: str = os.path.join(input_dir, "square_resized")
        os.makedirs(output_dir, exist_ok=True)

    else:
        print(f"Error: The specified path '{path_arg}' does not exist.")
        sys.exit(1)

    print(f"Found {len(input_files)} files. Using {workers} worker(s). Output dir: {output_dir}")

    # 並列処理
    if workers <= 1 or len(input_files) == 1:
        for input_file in tqdm(input_files, desc="Processing", unit="file"):
            tqdm.write(f"Processing file: {input_file}")
            save_square_image(input_file, output_dir, extra_margin=margin_size, max_size_mb=max_size, quality_start=95, quality_min=quality_min, show_label=show_label)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            futures: List[concurrent.futures.Future] = [ex.submit(save_square_image, f, output_dir, margin_size, max_size, 95, quality_min, show_label) for f in input_files]
            for fut in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing", unit="file"):
                try:
                    fut.result()
                except Exception as e:
                    tqdm.write(f"Error processing file in worker: {e}")

    print(f"Processing completed. Resized images are saved in '{output_dir}'.")
