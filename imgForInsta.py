# -*- coding: utf-8 -*-
import os
import cv2
import sys

def make_square(image, margin_color=(255, 255, 255), extra_margin=100):
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

def save_square_image(input_file, output_dir, extra_margin=100, max_size_mb=9):
    # 画像を読み込む
    image = cv2.imread(input_file)
    
    # 画像が正しく読み込まれたか確認
    if image is None:
        print(f"Error: Failed to load image '{input_file}'. Please check the file path or format.")
        return
    
    # 正方形に加工した画像を取得
    square_image = make_square(image, extra_margin=extra_margin)
    
    # 出力先のファイル名を設定
    file_name = os.path.basename(input_file)
    output_path = os.path.join(output_dir, file_name)
    
    # 最初は高めの品質から保存
    quality = 95
    cv2.imwrite(output_path, square_image, [cv2.IMWRITE_JPEG_QUALITY, quality])

    # サイズが収まるまで繰り返し
    while os.path.getsize(output_path) / (1024*1024) > max_size_mb:
        quality -= 3
        cv2.imwrite(output_path, square_image, [cv2.IMWRITE_JPEG_QUALITY, quality])

if __name__ == "__main__":
    if len(sys.argv) > 3:
        print("Usage: python3 imgForInsta.py [<directory_path>] [<margin_size>]")
        sys.exit(1)

    # 指定されたディレクトリとマージンサイズを取得
    input_dir = None
    margin_size = 100  # デフォルト値

    if len(sys.argv) >= 2:
        # 最後の引数が数値の場合はマージンサイズとして扱う
        if sys.argv[-1].isdigit():
            margin_size = int(sys.argv[-1])
            if len(sys.argv) == 3:
                input_dir = sys.argv[1]
        else:
            input_dir = sys.argv[1]

    if input_dir is None:
        # 引数がない場合はスクリプトのディレクトリを使用
        input_dir = os.path.dirname(os.path.abspath(__file__))

    # ディレクトリが存在するか確認
    if not os.path.isdir(input_dir):
        print(f"Error: The specified directory '{input_dir}' does not exist.")
        sys.exit(1)

    # 指定されたディレクトリ内のすべての JPG ファイルを取得
    input_path = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith('.jpg')]

    if not input_path:
        print(f"No JPG files found in the directory '{input_dir}'.")
        sys.exit(1)

    # 出力先のディレクトリを設定
    output_dir = os.path.join(input_dir, "square_resized")

    # 出力先ディレクトリを作成
    os.makedirs(output_dir, exist_ok=True)

    # 各画像に対して処理を実行
    for input_file in input_path:
        print(f"Processing file: {input_file}")
        save_square_image(input_file, output_dir, extra_margin=margin_size)

    print(f"Processing completed. Resized images are saved in '{output_dir}'.")
