
# imgForInsta
Resize and pad images to square (1:1) for posting on the PC version of Instagram. 
- Adds a margin of 100 pixels (default) to each side, making the image square with white padding.
- Output JPEG files are kept under 9MB by default (Instagram's upload limit is around 10MB).
- Margin size can be changed with an argument (default: 100).


## Usage

```powershell
python imgForInsta.py [<directory_or_file_path>] [-m MARGIN] [-w WORKERS] [--max-size MB] [--quality-min N]
```

**Arguments and Defaults:**
- `path` (optional): Directory or image file path. **Default:** script directory.
- `-m`, `--margin`: Extra margin to add (pixels). **Default:** 100
- `-w`, `--workers`: Number of parallel worker processes. **Default:** CPU count - 1
- `--max-size`: Maximum output file size in MB. **Default:** 9
- `--quality-min`: Minimum JPEG quality. **Default:** 10

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
- CLI with argparse (see Usage above)
- Parallel processing (set workers with `-w`)
- Progress bar with `tqdm`
- Supports JPEG/JPG and HEIF/HEIC input (HEIF requires extra packages; see Requirements)

## Requirements

Python 3.6+ (tested with Python 3.12). Use a virtual environment for best results.

Install dependencies:
```powershell
pip install opencv-python pillow pillow-heif tqdm
```

`pillow-heif` provides HEIF/HEIC support. If unavailable, try `pyheif` + `pillow` (platform dependent).

### Recommended venv setup:
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

