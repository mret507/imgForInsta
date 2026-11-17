
# imgForInsta

[English](README.md) | 日本語

PC版Instagramへの投稿用に、画像を指定したアスペクト比（デフォルトは正方形 1:1。4:5 や 1.91:1 なども可）へパディングするツールです。

- 四辺にデフォルト100ピクセルの余白を加え、指定したアスペクト比（`--ratio`、デフォルト 1:1）になるようパディングします。
- 背景は白（デフォルト）、黒、任意の `#RRGGBB` カラー、または写真をぼかしたもの（`--bg blur`）から選べます。
- 出力JPEGはデフォルトで9MB未満に収めます（Instagramのアップロード上限は約10MB）。
- 余白のサイズは引数で変更できます（デフォルト: 100）。
- EXIFメタデータからカメラ・レンズ情報と撮影パラメータ（F値・シャッタースピード・ISO）を読み取り、下部の余白に2行で描画します（デフォルトで有効。`--no-label` で無効化）。
  - カメラ/レンズの行はセミボールドの濃いグレー、露出の行はやや薄いグレーで描画し、わずかな字間と項目間の細い縦線で区切ります（例: `f/2.8 | 1/250s | ISO 400`）。

## 使い方

### run.bat（推奨）

venv をセットアップしておけば、`run.bat` を使うことで venv を手動で有効化せずにすぐ実行できます。

```batch
run.bat [<ディレクトリまたはファイルのパス>] [-m マージン] [-w ワーカー数] [--max-size MB] [--quality-min N] [--no-label] [--ratio W:H] [--bg COLOR|blur] [--no-metadata]
```

**例:**

- 単一ファイルを処理:

  ```batch
  run.bat "C:\path\to\photo.jpg"
  ```

- 余白を指定してディレクトリを処理:

  ```batch
  run.bat "C:\path\to\images" -m 150
  ```

- 縦長 4:5 でぼかし背景（`4_5_resized` に保存）:

  ```batch
  run.bat "C:\path\to\images" --ratio 4:5 --bg blur
  ```

### Python で直接実行

```powershell
python imgForInsta.py [<ディレクトリまたはファイルのパス>] [-m マージン] [-w ワーカー数] [--max-size MB] [--quality-min N] [--no-label] [--ratio W:H] [--bg COLOR|blur] [--no-metadata]
```

**引数とデフォルト値:**

- `path`（省略可）: ディレクトリまたは画像ファイルのパス。**デフォルト:** 省略時はフォルダ選択ダイアログを表示
- `-m`, `--margin`: 追加する余白（ピクセル）。**デフォルト:** 100
- `-w`, `--workers`: 並列ワーカープロセス数。**デフォルト:** CPU数 - 1
- `--max-size`: 出力ファイルの最大サイズ（MB）。**デフォルト:** 9
- `--quality-min`: JPEGの最低品質。**デフォルト:** 10
- `--no-label`: 下部余白へのカメラ/レンズのEXIFラベル描画を無効化。出力ファイル名の末尾に `_no-label` が付きます。**デフォルト:** ラベルを表示
- `--ratio`: 出力アスペクト比。`W:H` 形式（例: `1:1`, `4:5`, `1.91:1`）または単一の数値（幅 / 高さ）。出力フォルダ名は比率に応じて決まります（例: `4_5_resized`）。**デフォルト:** `1:1`（出力フォルダは `square_resized`）
- `--bg`: パディング部分の背景。`white`、`black`、`#RRGGBB`、または `blur`（写真を拡大して強くぼかしたもの）。**デフォルト:** `white`
- `--no-metadata`: 出力からすべてのメタデータ（EXIF と ICC プロファイル）を除去。**デフォルト:** EXIFメタデータ（カメラ、レンズ、露出、日時など）を保持し、sRGB ICC プロファイルを埋め込みます。GPS位置情報は常に除去されます

**例:**

- ディレクトリを処理（デフォルトの余白）:

  ```powershell
  python imgForInsta.py "C:\path\to\images"
  ```

- 単一の画像ファイルを処理:

  ```powershell
  python imgForInsta.py "C:\path\to\images\photo.jpg"
  ```

- 余白を指定し、ワーカー数を4にする:

  ```powershell
  python imgForInsta.py "C:\path\to\images" -m 150 -w 4
  ```

- 最大出力サイズを6MB、JPEGの最低品質を20にする:

  ```powershell
  python imgForInsta.py "C:\path\to\images" --max-size 6 --quality-min 20
  ```

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。詳細は LICENSE ファイルを参照してください。

## 機能

- venv を手動で有効化せずに起動できる `run.bat`
- argparse による CLI（上記「使い方」を参照）
- 並列処理（`-w` でワーカー数を指定）
- `tqdm` によるプログレスバー表示
- JPEG/JPG と HEIF/HEIC の入力に対応（HEIF には追加パッケージが必要。「必要環境」を参照）
- 出力アスペクト比（`--ratio`）と背景（`--bg`: 単色またはぼかした写真）を選択可能
- カラーマネジメント: sRGB 以外の ICC プロファイル（Display P3、Adobe RGB など）を持つ JPEG 入力は sRGB に変換し、EXIF の向き情報も適用するため、Instagram 上で色と回転が正しく表示されます
- デフォルトでメタデータ（EXIF + sRGB ICC）を保持し、プライバシー保護のため GPS は除去。`--no-metadata` で無効化
- EXIFラベル: 下部余白に2行で描画（`--no-label` で無効化）
  - 1行目: カメラのメーカー + モデル名とレンズのモデル名
  - 2行目: F値、シャッタースピード、ISO（例: `f/2.8 | 1/250s | ISO 400`）
  - フォントサイズは最長の行がキャンバス幅の2/3に収まるよう自動調整され、上限はキャンバス幅の2%
  - 文字色は背景に応じて切り替わります: 明るい背景では濃いグレー、暗い背景（例: `--bg black`）では明るいグレー
  - 既存の下余白がラベルに足りない場合のみ、写真を上にシフトするか、キャンバスを拡張します（下方向に加え、アスペクト比維持のため左右にも拡張）。足りている場合は写真を同じサイズのまま中央に配置します。上余白は常に `--margin` ピクセル以上確保されます
- `path` 省略時のフォルダ選択ダイアログ（Tkinter）
- Windows 上の非ASCII（日本語など）パスに対応（画像の読み書きは `cv2.imread` / `cv2.imwrite` ではなく Pillow / Python のファイルI/O を使用）

## 必要環境

Python 3.6 以上（Python 3.13 で動作確認済み）。仮想環境の使用を推奨します。

依存パッケージのインストール:

```powershell
pip install opencv-python pillow pillow-heif tqdm
```

`pillow-heif` が HEIF/HEIC 対応を提供します。利用できない場合は `pyheif` + `pillow` を試してください（プラットフォームに依存します）。

### 推奨する venv のセットアップ

```powershell
# Python 3.12 の venv を作成（慣例として `.venv` を使用）
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

**変更後に requirements を更新するには:**

```powershell
python -m pip freeze > requirements.txt
```

このリポジトリにはプロジェクトの venv から生成した `requirements.txt` が含まれています。動作確認済みの環境を再現する際に使用してください。

## 補足

- 出力ファイルは入力ディレクトリ（またはファイル）の隣のフォルダに保存されます。1:1 の場合は `square_resized`、それ以外は比率の `:` を `_` に置き換えた名前になります（例: `4_5_resized`、`1.91_1_resized`）。
- HEIF/HEIC 入力は常に JPEG に変換して出力されます。
- システムの `python` が Python 3 でない場合は、`py -3` などの Python 3 インタープリタを使用してください。
- `--no-label` を指定すると、ラベル付きの出力と区別できるよう出力ファイル名の末尾に `_no-label` が付きます。
- EXIFラベルは次のEXIFタグを読み取ります:
  - 1行目: Make (271), Model (272), LensModel (42036)
  - 2行目: FNumber (33437), ExposureTime (33434), PhotographicSensitivity (34855)
  - タグが欠けている場合は、取得できた情報のみを表示します。EXIFデータがまったくない場合は、ラベルなしで通常どおり中央に配置します。2行目の項目がない場合は1行目のみを描画します（逆も同様）。
- シャッタースピードは1秒未満なら `1/N s`、1秒以上なら `Ns`（例: `1.3s`）の形式で表示します。
