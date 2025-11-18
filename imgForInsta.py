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

def make_square(image: np.ndarray, margin_color: Tuple[int, int, int] = (255, 255, 255), extra_margin: int = 100) -> np.ndarray:
    # 画像のサイズを取得
    height, width = image.shape[:2]
    
    # 余白を追加する必要がある場合の処理
    if height != width:
        # 長辺の長さを取得
        max_dim = max(height, width)
        
        # 上下または左右に追加する余白のサイズを計算
        vertical_margin = (max_dim - height) // 2 + extra_margin
        horizontal_margin = (max_dim - width) // 2 + extra_margin
        
        # 余白を追加
        padded_image = cv2.copyMakeBorder(image, vertical_margin, vertical_margin, horizontal_margin, horizontal_margin, cv2.BORDER_CONSTANT, value=margin_color)
    else:
        # 既に正方形の場合は変更しない
        padded_image = cv2.copyMakeBorder(image, extra_margin, extra_margin, extra_margin, extra_margin, cv2.BORDER_CONSTANT, value=margin_color)
    
    return padded_image

def load_image_as_bgr(input_file: str) -> Optional[np.ndarray]:
    """Load image file into a BGR numpy array suitable for OpenCV.

    Supports JPEG/JPG via OpenCV. Supports HEIF/HEIC via Pillow + pillow_heif if available.
    Returns None on failure.
    """
    ext = os.path.splitext(input_file)[1].lower()
    if ext in ('.jpg', '.jpeg'):
        return cv2.imread(input_file)

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


def save_square_image(input_file: str, output_dir: str, extra_margin: int = 100, max_size_mb: float = 9.0, quality_start: int = 95, quality_min: int = 10) -> None:
    # 画像を読み込む
    image: Optional[np.ndarray] = load_image_as_bgr(input_file)

    # 画像が正しく読み込まれたか確認
    if image is None:
        print(f"Error: Failed to load image '{input_file}'. Skipping.")
        return

    # 正方形に加工した画像を取得
    # image はここで None でないことが保証される
    square_image: np.ndarray = make_square(image, extra_margin=extra_margin)

    # 出力先のファイル名を設定
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    in_ext = os.path.splitext(input_file)[1].lower()
    # HEIF を JPEG に変換して保存する（OpenCV の書き出しで HEIF を扱うのは環境依存）
    if in_ext in ('.heif', '.heic'):
        out_name = base_name + '.jpg'
    else:
        out_name = base_name + in_ext

    output_path = os.path.join(output_dir, out_name)

    # 最初は高めの品質から保存
    quality = quality_start
    # OpenCV は JPEG のみ品質オプションを受け取るため、常に JPEG で保存する
    # もし拡張子が .jpg/.jpeg 以外でも .jpg にして保存
    cv2.imwrite(output_path, square_image, [cv2.IMWRITE_JPEG_QUALITY, quality])

    # サイズが収まるまで繰り返し（品質に下限を設定して無限ループを防ぐ）
    while os.path.getsize(output_path) / (1024*1024) > max_size_mb:
        quality -= 3
        if quality < quality_min:
            # これ以上品質を下げられないのでループを抜ける
            print(f"Warning: Reached minimum quality for '{output_path}', file may still be larger than {max_size_mb}MB.")
            break
        cv2.imwrite(output_path, square_image, [cv2.IMWRITE_JPEG_QUALITY, quality])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make square images for Instagram-like posts. Supports JPG/JPEG and HEIF/HEIC (HEIF requires additional libraries).")
    parser.add_argument('path', nargs='?', default=os.path.dirname(os.path.abspath(__file__)), help='Directory or image file path. Defaults to script directory.')
    parser.add_argument('-m', '--margin', type=int, default=100, help='Extra margin to add around the image (default: 100)')
    parser.add_argument('-w', '--workers', type=int, default=max(1, multiprocessing.cpu_count() - 1), help='Number of parallel worker processes (default: cpu_count-1)')
    parser.add_argument('--max-size', type=float, default=9.0, help='Maximum output file size in MB (default: 9)')
    parser.add_argument('--quality-min', type=int, default=10, help='Minimum JPEG quality when shrinking (default: 10)')
    args = parser.parse_args()

    path_arg: str = args.path
    margin_size: int = args.margin
    workers: int = args.workers
    max_size: float = args.max_size
    quality_min: int = args.quality_min

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
            save_square_image(input_file, output_dir, extra_margin=margin_size, max_size_mb=max_size, quality_start=95, quality_min=quality_min)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as ex:
            futures: List[concurrent.futures.Future] = [ex.submit(save_square_image, f, output_dir, margin_size, max_size, 95, quality_min) for f in input_files]
            for fut in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing", unit="file"):
                try:
                    fut.result()
                except Exception as e:
                    tqdm.write(f"Error processing file in worker: {e}")

    print(f"Processing completed. Resized images are saved in '{output_dir}'.")
