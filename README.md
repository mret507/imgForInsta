# imgForInsta
PC版Instagramアプリに投稿するためファイルサイズの大きい画像を縮小し、余白を追加して1:1にする  
- 長辺にマージンを100ずつ追加し、その長さに合わせて正方形になるよう短辺にマージンを追加する  
- Instagramアプリは恐らく10MB以上の画像に対応していないので~~余裕を見て8MB~~9MB以下に設定  
- 短辺のマージンは引数で指定可能 指定なしの場合100がセットされる

## Usage
python3 imgForInsta.py [<directory_path>] [<margin_size>]

## Lisence
This project is licensed under the MIT License, see the LICENSE.txt file for details
