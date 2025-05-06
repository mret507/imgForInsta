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

def save_square_image(input_file, output_dir, max_size_mb=8):
    # 画像を読み込む
    image = cv2.imread(input_file)
    
    # 画像が正しく読み込まれたか確認
    if image is None:
        print(f"Error: Failed to load image '{input_file}'. Please check the file path or format.")
        return
    
    # 正方形に加工した画像を取得
    square_image = make_square(image)
    
    # 出力先のファイル名を設定
    file_name = os.path.basename(input_file)
    output_path = os.path.join(output_dir, file_name)
    
    # 加工した画像を一時保存
    temp_output_path = output_path + ".temp.jpg"
    cv2.imwrite(temp_output_path, square_image)
    
    # 画像サイズをチェックし、8MBを超える場合は圧縮
    file_size_mb = os.path.getsize(temp_output_path) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        compression_quality = int(100 * max_size_mb / file_size_mb)
        cv2.imwrite(output_path, square_image, [cv2.IMWRITE_JPEG_QUALITY, compression_quality])
        os.remove(temp_output_path)
    else:
        os.rename(temp_output_path, output_path)

if __name__ == "__main__":
    if len(sys.argv) > 2:
        print("Usage: python3 imgForInsta.py [<directory_path>]")
        sys.exit(1)

    # 指定されたディレクトリを取得
    if len(sys.argv) == 2:
        input_dir = sys.argv[1]
    else:
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
        save_square_image(input_file, output_dir)

    print(f"Processing completed. Resized images are saved in '{output_dir}'.")
