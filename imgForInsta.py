# -*- coding: utf-8 -*-
import os
import cv2
import sys
import math
import argparse
import concurrent.futures
import multiprocessing
import numpy as np
import io
from tqdm import tqdm
from typing import Optional, List, Tuple, Union

"""
imgForInsta.py

Usage:
    python imgForInsta.py [<directory_or_file_path>] [-m MARGIN] [--ratio W:H] [--bg COLOR|blur] [--no-metadata]

If a directory path is given, all JPG/JPEG/HEIF/HEIC files in the directory are processed.
If a file path is given and it's an image, only that file will be processed.
If no path is given, a folder selection dialog is shown.
"""

SUPPORTED_EXTS = ('.jpg', '.jpeg', '.heif', '.heic')

# ラベル内の項目区切り（描画時は細い縦線に置き換える）
LABEL_SEP = ' | '
# 行ごとのスタイル (フォントの太さ, 文字色RGB)。行数がこれを超える場合は最後のスタイルを使う
_LABEL_STYLES = [('semibold', (40, 40, 40)), ('light', (125, 125, 125))]
_LABEL_SEP_COLOR = (200, 200, 200)
# 暗い背景（黒・暗いぼかし背景など）用のスタイル
_LABEL_STYLES_DARK = [('semibold', (235, 235, 235)), ('light', (170, 170, 170))]
_LABEL_SEP_COLOR_DARK = (95, 95, 95)
_LABEL_TRACKING = 0.06  # 字間（フォントサイズ比）
_LABEL_SEP_GAP = 0.8    # 区切り線の左右の間隔（フォントサイズ比）

# 背景指定: 'blur' または BGR タプル
Background = Union[str, Tuple[int, int, int]]
_NAMED_COLORS = {'white': (255, 255, 255), 'black': (0, 0, 0)}

# EXIF タグ
_TAG_ORIENTATION = 274
_TAG_EXIF_IFD = 34665
_TAG_GPS_IFD = 34853
_TAG_MAKER_NOTE = 37500


def _open_pil(input_file: str):
    """Pillow で画像を開く。HEIF/HEIC の場合は pillow_heif のオープナーを登録する。"""
    from PIL import Image
    ext = os.path.splitext(input_file)[1].lower()
    if ext in ('.heif', '.heic'):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except Exception:
            pass
    return Image.open(input_file)


def parse_ratio(text: str) -> float:
    """'4:5' / '1.91:1' / '0.8' 形式のアスペクト比（幅/高さ）を float にする。"""
    try:
        if ':' in text:
            w_s, h_s = text.split(':', 1)
            value = float(w_s) / float(h_s)
        else:
            value = float(text)
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError(f"invalid ratio '{text}' (e.g. 1:1, 4:5, 1.91:1)")
    if not (value > 0 and math.isfinite(value)):
        raise argparse.ArgumentTypeError(f"ratio must be positive: '{text}'")
    return value


def output_dir_name(ratio_text: str) -> str:
    """比率指定から出力ディレクトリ名を返す。1:1 は 'square_resized'、それ以外は '4_5_resized' のように比率を名前にする。"""
    if abs(parse_ratio(ratio_text) - 1.0) < 1e-9:
        return 'square_resized'
    safe = ratio_text.strip().replace(':', '_')
    safe = ''.join(c for c in safe if c.isalnum() or c in '._-')
    return f'{safe}_resized'


def parse_background(text: str) -> Background:
    """'white' / 'black' / '#RRGGBB' / 'blur' を解釈し、'blur' または BGR タプルを返す。"""
    t = text.strip().lower()
    if t == 'blur':
        return 'blur'
    if t in _NAMED_COLORS:
        return _NAMED_COLORS[t]
    hex_s = t[1:] if t.startswith('#') else t
    if len(hex_s) == 6:
        try:
            r, g, b = (int(hex_s[i:i + 2], 16) for i in (0, 2, 4))
            return (b, g, r)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"invalid background '{text}' (use white, black, #RRGGBB or blur)")


def get_exif_label(input_file: str) -> Optional[List[str]]:
    """EXIFからラベル行のリストを返す。
    1行目: カメラメーカー+モデル と レンズモデル
    2行目: F値・シャッタースピード・ISO感度
    取得できない場合はNone。
    """
    try:
        with _open_pil(input_file) as img:
            exif = img.getexif()
            ifd_exif = exif.get_ifd(_TAG_EXIF_IFD)

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


def get_output_exif(input_file: str) -> Optional[bytes]:
    """出力JPEGに埋め込むEXIFバイト列を返す。
    GPS情報は除去し、Orientation は 1（回転済み）にする。
    サイズ超過などで書き出せない場合は MakerNote を落として再試行し、それでも駄目なら None。
    """
    try:
        with _open_pil(input_file) as img:
            exif = img.getexif()
            if not exif:
                return None
            exif.get_ifd(_TAG_EXIF_IFD)  # サブIFDを読み込んでおく
            exif.pop(_TAG_GPS_IFD, None)
            if _TAG_ORIENTATION in exif:
                exif[_TAG_ORIENTATION] = 1
            try:
                data = exif.tobytes()
            except Exception:
                data = b''
            if not data or len(data) > 65000:
                # MakerNote は巨大/壊れていることが多いので落として再試行
                exif.get_ifd(_TAG_EXIF_IFD).pop(_TAG_MAKER_NOTE, None)
                data = exif.tobytes()
            return data if len(data) <= 65000 else None
    except Exception:
        return None


def _srgb_icc_bytes() -> Optional[bytes]:
    try:
        from PIL import ImageCms
        return ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
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


def _line_style(index: int, dark: bool = False) -> Tuple[str, Tuple[int, int, int]]:
    styles = _LABEL_STYLES_DARK if dark else _LABEL_STYLES
    return styles[min(index, len(styles) - 1)]


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


def _is_dark(region: np.ndarray) -> bool:
    """BGR領域の平均輝度が中間より暗いか。"""
    if region.size == 0:
        return False
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    return float(gray.mean()) < 128


def draw_label(image: np.ndarray, lines: List[str], bottom_area: int, font_size: int = 0) -> np.ndarray:
    """画像下部のbottom_area領域に複数行linesを中央揃え描画して返す。
    1行目はセミボールド、2行目以降はセミライトで、字間を少し空ける。
    文字色は bottom_area 領域の平均輝度で切り替える（明るい背景→濃いグレー、暗い背景→明るいグレー）。
    LABEL_SEP で区切られた項目の間には細い縦線を描く。
    font_size が指定された場合はそのサイズを使用し、0の場合は最長行が画像幅の2/3に収まるよう自動計算する。"""
    from PIL import Image, ImageDraw
    h, w = image.shape[:2]
    dark = _is_dark(image[max(0, h - bottom_area):, :])
    sep_color = _LABEL_SEP_COLOR_DARK if dark else _LABEL_SEP_COLOR
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
        weight, color = _line_style(i, dark)
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
                draw.line([(sx, y), (sx, y + bottom - top)], fill=sep_color, width=sep_width)
                x += 2 * sep_gap
            for ch in seg:
                draw.text((x, y - top), ch, fill=color, font=font)
                x += draw.textlength(ch, font=font) + tracking
            x -= tracking if seg else 0
        y += bottom - top + line_gap
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def canvas_size(height: int, width: int, ratio: float = 1.0, extra_margin: int = 100) -> Tuple[int, int]:
    """写真の四辺に最低 extra_margin を確保し、幅/高さ = ratio となる最小キャンバス (W, H) を返す。"""
    H = max(height + 2 * extra_margin, math.ceil((width + 2 * extra_margin) / ratio))
    W = max(width + 2 * extra_margin, round(H * ratio))
    return W, H


def compute_padding(height: int, width: int, ratio: float = 1.0, extra_margin: int = 100,
                    bottom_area: int = 0) -> Tuple[int, int, int, int]:
    """キャンバス比率 ratio に合わせた (top, bottom, left, right) のパディング量を返す。
    bottom_area: ラベル用に必要な下余白。元の下余白で足りなければ、まず上余白を削って写真を上へシフトし
    （上余白は最低 extra_margin を残す）、それでも足りない分は下余白を拡張する。
    拡張時は比率を保つため左右にも余白を追加する。
    """
    W, H = canvas_size(height, width, ratio, extra_margin)
    pad_v, pad_h = H - height, W - width
    top = pad_v // 2
    bot = pad_v - top
    left = pad_h // 2
    right = pad_h - left

    needed = bottom_area - bot
    if needed > 0:
        shift = min(needed, top - extra_margin)
        top -= shift
        bot += shift
        extra = needed - shift
        if extra > 0:
            add = round((H + extra) * ratio) - W
            if add % 2:
                # 左右で1px差が出ないよう、下余白を1px増やして偶数化を試みる
                extra += 1
                add = round((H + extra) * ratio) - W
            bot += extra
            left += add // 2
            right += add - add // 2
    return top, bot, left, right


def _blur_background(image: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    """写真をキャンバス全体を覆うよう拡大・中央クロップし、強くぼかした背景を作る。"""
    h, w = image.shape[:2]
    # 縮小してからぼかすことで大きな画像でも高速に処理する
    small_w = max(8, out_w // 8)
    small_h = max(8, out_h // 8)
    scale = max(small_w / w, small_h / h)
    rw, rh = max(small_w, math.ceil(w * scale)), max(small_h, math.ceil(h * scale))
    resized = cv2.resize(image, (rw, rh), interpolation=cv2.INTER_AREA)
    x0, y0 = (rw - small_w) // 2, (rh - small_h) // 2
    cropped = resized[y0:y0 + small_h, x0:x0 + small_w]
    sigma = max(small_w, small_h) * 0.04
    blurred = cv2.GaussianBlur(cropped, (0, 0), sigmaX=sigma, sigmaY=sigma, borderType=cv2.BORDER_REFLECT)
    return cv2.resize(blurred, (out_w, out_h), interpolation=cv2.INTER_LINEAR)


def make_padded(image: np.ndarray, padding: Tuple[int, int, int, int],
                background: Background = (255, 255, 255)) -> np.ndarray:
    """(top, bottom, left, right) のパディングを付けたキャンバスを返す。
    background: BGR タプルで単色塗り、'blur' でぼかした写真を背景に敷く。"""
    top, bot, left, right = padding
    if isinstance(background, str):  # 'blur'
        h, w = image.shape[:2]
        canvas = _blur_background(image, w + left + right, h + top + bot)
        canvas[top:top + h, left:left + w] = image
        return canvas
    return cv2.copyMakeBorder(image, top, bot, left, right, cv2.BORDER_CONSTANT, value=background)


def _pil_to_srgb(im):
    """ICC プロファイルが sRGB 以外なら sRGB に変換し、RGB モードの画像を返す。"""
    icc = im.info.get('icc_profile')
    if icc:
        try:
            from PIL import ImageCms
            src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            desc = (ImageCms.getProfileDescription(src_profile) or '').lower()
            if 'srgb' not in desc:
                dst_profile = ImageCms.createProfile('sRGB')
                return ImageCms.profileToProfile(im, src_profile, dst_profile, outputMode='RGB')
        except Exception:
            # ImageCms が利用できない、またはプロファイル変換に失敗した場合はそのまま変換
            pass
    return im.convert('RGB')


def load_image_as_bgr(input_file: str) -> Optional[np.ndarray]:
    """Load image file into a BGR numpy array suitable for OpenCV.

    JPEG/JPG と HEIF/HEIC を Pillow で読み込む（HEIF は pillow_heif が必要）。
    JPEG は EXIF の Orientation に従って回転し、ICC プロファイルが sRGB 以外（Display P3 / AdobeRGB 等）なら sRGB に変換する。
    Returns None on failure.
    """
    ext = os.path.splitext(input_file)[1].lower()
    if ext not in SUPPORTED_EXTS:
        print(f"Error: Unsupported file extension for '{input_file}'. Supported: .jpg/.jpeg/.heif/.heic")
        return None

    try:
        from PIL import ImageOps
        with _open_pil(input_file) as im:
            if ext in ('.jpg', '.jpeg'):
                # HEIF は pillow_heif が回転を適用済みのため JPEG のみ
                im = ImageOps.exif_transpose(im)
            arr = np.array(_pil_to_srgb(im))  # RGB
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception as e:
        if ext in ('.heif', '.heic'):
            print(f"Error: Cannot read HEIF file '{input_file}'. Install 'pillow-heif' or 'pyheif' (error: {e}).")
        return None


def save_square_image(input_file: str, output_dir: str, extra_margin: int = 100, max_size_mb: float = 9.0,
                      quality_start: int = 95, quality_min: int = 10, show_label: bool = True,
                      ratio: float = 1.0, background: Background = (255, 255, 255),
                      keep_metadata: bool = True) -> None:
    image: Optional[np.ndarray] = load_image_as_bgr(input_file)

    if image is None:
        print(f"Error: Failed to load image '{input_file}'. Skipping.")
        return

    h, w = image.shape[:2]
    exif_lines: Optional[List[str]] = get_exif_label(input_file) if show_label else None
    bottom_area: int = 0
    font_size: int = 0

    if exif_lines:
        canvas_w, _ = canvas_size(h, w, ratio, extra_margin)
        font_size = _measure_font_size(exif_lines, int(canvas_w * 2 / 3))
        # キャンバス幅の 2% を上限として最終比率を決める
        font_size = max(8, min(font_size, int(canvas_w * 0.02)))
        # 行数に応じた bottom_area (n行 + line_gap(0.4) + 上下パディング(1.2))
        n = len(exif_lines)
        bottom_area = int(font_size * (n + 0.4 * (n - 1) + 1.2))

    padding = compute_padding(h, w, ratio, extra_margin, bottom_area)
    out_image: np.ndarray = make_padded(image, padding, background)

    if exif_lines:
        out_image = draw_label(out_image, exif_lines, bottom_area, font_size)

    # 出力先のファイル名を設定（出力は常に JPEG）
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    in_ext = os.path.splitext(input_file)[1].lower()
    name_suffix = '' if show_label else '_no-label'
    out_ext = '.jpg' if in_ext in ('.heif', '.heic') else in_ext
    output_path = os.path.join(output_dir, base_name + name_suffix + out_ext)

    # Pillow でメモリ上にエンコードし、サイズが収まった時点で1回だけ書き出す（open() は日本語パス対応）
    from PIL import Image
    pil_out = Image.fromarray(cv2.cvtColor(out_image, cv2.COLOR_BGR2RGB))
    save_kwargs = {}
    if keep_metadata:
        exif_bytes = get_output_exif(input_file)
        if exif_bytes:
            save_kwargs['exif'] = exif_bytes
        icc = _srgb_icc_bytes()
        if icc:
            save_kwargs['icc_profile'] = icc

    def _encode(q: int) -> bytes:
        buf = io.BytesIO()
        pil_out.save(buf, format='JPEG', quality=q, **save_kwargs)
        return buf.getvalue()

    max_bytes = max_size_mb * 1024 * 1024
    quality = quality_start
    data = _encode(quality)
    # サイズが収まるまで品質を下げて再エンコード（品質に下限を設定して無限ループを防ぐ）
    while len(data) > max_bytes:
        if quality - 3 < quality_min:
            print(f"Warning: Reached minimum quality for '{output_path}', file may still be larger than {max_size_mb}MB.")
            break
        quality -= 3
        data = _encode(quality)

    with open(output_path, 'wb') as f:
        f.write(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pad images to a fixed aspect ratio (square by default) for Instagram-like posts. Supports JPG/JPEG and HEIF/HEIC (HEIF requires additional libraries).")
    parser.add_argument('path', nargs='?', default=None, help='Directory or image file path. 省略時はフォルダ選択ダイアログを表示。')
    parser.add_argument('-m', '--margin', type=int, default=100, help='Extra margin to add around the image (default: 100)')
    parser.add_argument('-w', '--workers', type=int, default=max(1, multiprocessing.cpu_count() - 1), help='Number of parallel worker processes (default: cpu_count-1)')
    parser.add_argument('--max-size', type=float, default=9.0, help='Maximum output file size in MB (default: 9)')
    parser.add_argument('--quality-min', type=int, default=10, help='Minimum JPEG quality when shrinking (default: 10)')
    parser.add_argument('--no-label', action='store_true', default=False, help='カメラ/レンズ情報をラベル表示しない（デフォルト: 表示する）')
    parser.add_argument('--ratio', type=str, default='1:1', help='出力のアスペクト比 幅:高さ（例: 1:1, 4:5, 1.91:1。デフォルト: 1:1）')
    parser.add_argument('--bg', type=parse_background, default=(255, 255, 255), help='背景: white / black / #RRGGBB / blur（デフォルト: white）')
    parser.add_argument('--no-metadata', action='store_true', default=False, help='EXIFとICCプロファイルを出力に残さない（デフォルト: GPSを除くEXIFとsRGBのICCを残す）')
    args = parser.parse_args()
    try:
        ratio_value = parse_ratio(args.ratio)
        out_dir_name = output_dir_name(args.ratio)
    except argparse.ArgumentTypeError as e:
        parser.error(f'argument --ratio: {e}')

    path_arg: Optional[str] = args.path
    workers: int = args.workers
    options = dict(
        extra_margin=args.margin,
        max_size_mb=args.max_size,
        quality_start=95,
        quality_min=args.quality_min,
        show_label=not args.no_label,
        ratio=ratio_value,
        background=args.bg,
        keep_metadata=not args.no_metadata,
    )

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
        if ext not in SUPPORTED_EXTS:
            print(f"Error: The specified file '{path_arg}' is not a supported image (jpg/jpeg/heif/heic).")
            sys.exit(1)

        input_files: List[str] = [path_arg]
        output_dir: str = os.path.join(os.path.dirname(path_arg), out_dir_name)
        os.makedirs(output_dir, exist_ok=True)

    elif os.path.isdir(path_arg):
        input_dir = path_arg
        input_files: List[str] = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith(SUPPORTED_EXTS)]
        if not input_files:
            print(f"No supported files (jpg/jpeg/heif/heic) found in the directory '{input_dir}'.")
            sys.exit(1)

        output_dir: str = os.path.join(input_dir, out_dir_name)
        os.makedirs(output_dir, exist_ok=True)

    else:
        print(f"Error: The specified path '{path_arg}' does not exist.")
        sys.exit(1)

    print(f"Found {len(input_files)} files. Using {workers} worker(s). Output dir: {output_dir}")

    # 並列処理
    if workers <= 1 or len(input_files) == 1:
        for input_file in tqdm(input_files, desc="Processing", unit="file"):
            tqdm.write(f"Processing file: {input_file}")
            save_square_image(input_file, output_dir, **options)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            futures: List[concurrent.futures.Future] = [ex.submit(save_square_image, f, output_dir, **options) for f in input_files]
            for fut in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing", unit="file"):
                try:
                    fut.result()
                except Exception as e:
                    tqdm.write(f"Error processing file in worker: {e}")

    print(f"Processing completed. Resized images are saved in '{output_dir}'.")
