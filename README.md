
# imgForInsta

Resize and pad images to square (1:1) for posting on the PC version of Instagram.

- Adds a margin of 100 pixels (default) to each side, making the image square with white padding.
- Output JPEG files are kept under 9MB by default (Instagram's upload limit is around 10MB).
- Margin size can be changed with an argument (default: 100).
- Reads camera/lens info plus shooting parameters (F-number, shutter speed, ISO) from EXIF metadata and overlays them as two lines in the bottom margin (enabled by default, disable with `--no-label`).

## Usage

### run.bat (recommended)

After setting up the venv, use `run.bat` for quick execution without manually activating the venv.

```batch
run.bat [<directory_or_file_path>] [-m MARGIN] [-w WORKERS] [--max-size MB] [--quality-min N] [--no-label]
```

**Examples:**

- Process a single file:

  ```batch
  run.bat "C:\path\to\photo.jpg"
  ```

- Process a directory with a custom margin:

  ```batch
  run.bat "C:\path\to\images" -m 150
  ```

### Direct Python execution

```powershell
python imgForInsta.py [<directory_or_file_path>] [-m MARGIN] [-w WORKERS] [--max-size MB] [--quality-min N] [--no-label]
```

**Arguments and Defaults:**

- `path` (optional): Directory or image file path. **Default:** when omitted, a folder selection dialog is shown.
- `-m`, `--margin`: Extra margin to add (pixels). **Default:** 100
- `-w`, `--workers`: Number of parallel worker processes. **Default:** CPU count - 1
- `--max-size`: Maximum output file size in MB. **Default:** 9
- `--quality-min`: Minimum JPEG quality. **Default:** 10
- `--no-label`: Disable camera/lens EXIF label in the bottom margin. Output filename gets a `_no-label` suffix. **Default:** label is shown

**Examples:**

- Process a directory (default margin):

 ```powershell
 python imgForInsta.py "C:\path\to\images"
 ```

- Process a single image file:

 ```powershell
 python imgForInsta.py "C:\path\to\images\photo.jpg"
 ```

- Use a custom margin and 4 workers:

 ```powershell
 python imgForInsta.py "C:\path\to\images" -m 150 -w 4
 ```

- Set maximum output size to 6 MB and minimum JPEG quality to 20:

 ```powershell
 python imgForInsta.py "C:\path\to\images" --max-size 6 --quality-min 20
 ```

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Features

- `run.bat` for easy launch without manual venv activation
- CLI with argparse (see Usage above)
- Parallel processing (set workers with `-w`)
- Progress bar with `tqdm`
- Supports JPEG/JPG and HEIF/HEIC input (HEIF requires extra packages; see Requirements)
- EXIF label: two lines drawn in the bottom white margin (disable with `--no-label`)
  - Line 1: camera make + model and lens model
  - Line 2: F-number, shutter speed, and ISO (e.g. `F2.8  1/250s  ISO400`)
  - Font is auto-sized to fit the longest line within 2/3 of the image width, capped at 2% of the square width
  - The original photo is only shifted up / the canvas is only expanded when the existing bottom margin is too small for the label; otherwise the photo stays centered at the same size. The top margin is always kept at least `--margin` pixels
- Folder selection dialog (Tkinter) when `path` is omitted
- Handles non-ASCII (e.g. Japanese) paths on Windows by routing through `np.fromfile` / `cv2.imencode` instead of `cv2.imread` / `cv2.imwrite`

## Requirements

Python 3.6+ (tested with Python 3.13). Use a virtual environment for best results.

Install dependencies:

```powershell
pip install opencv-python pillow pillow-heif tqdm
```

`pillow-heif` provides HEIF/HEIC support. If unavailable, try `pyheif` + `pillow` (platform dependent).

### Recommended venv setup

```powershell
# Create Python 3.12 venv (uses `.venv` by convention)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

**To update requirements after changes:**

```powershell
python -m pip freeze > requirements.txt
```

This repository includes a `requirements.txt` generated from the project venv. Use it to reproduce the tested environment.

## Notes

- Output files are saved in a `square_resized` folder next to the input directory or file.
- HEIF/HEIC inputs are always converted to JPEG for output.
- Use `py -3` or your Python 3 interpreter if `python` is not Python 3 on your system.
- When `--no-label` is specified, the output filename gets a `_no-label` suffix to distinguish it from the labeled version.
- The EXIF label reads the following EXIF tags:
  - Line 1: Make (271), Model (272), LensModel (42036)
  - Line 2: FNumber (33437), ExposureTime (33434), PhotographicSensitivity (34855)
  - If any tag is missing, only the available information is shown. If no EXIF data is found at all, the image is centered as usual with no label. When line 2 has no fields, only line 1 is rendered (and vice versa).
- Shutter speed shorter than 1 second is formatted as `1/N s`; 1 second or longer is formatted as `Ns` (e.g. `1.3s`).
