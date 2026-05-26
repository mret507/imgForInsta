# simple HEIF create/read test
from PIL import Image
import numpy as np
import os

# Try to register pillow-heif opener if available
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    print('pillow_heif imported and registered')
except Exception as e:
    print('pillow_heif not available or failed to register:', e)

# create a red image array
arr = np.zeros((200, 300, 3), dtype=np.uint8)
arr[:] = [255, 0, 0]
im = Image.fromarray(arr)

heif_path = os.path.join(os.getcwd(), 'test_heif.heif')
try:
    im.save(heif_path, format='HEIF')
    print('Saved HEIF:', heif_path, os.path.getsize(heif_path))
except Exception as e:
    print('Failed to save HEIF:', e)

# Now try to read it using the project's loader
try:
    from imgForInsta import load_image_as_bgr
    bgr = load_image_as_bgr(heif_path)
    if bgr is None:
        print('load_image_as_bgr returned None')
    else:
        import cv2
        out = os.path.join(os.getcwd(), 'test_heif_converted.jpg')
        cv2.imwrite(out, bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        print('Saved converted JPG:', out, os.path.getsize(out))
except Exception as e:
    print('Failed to import or run loader:', e)
