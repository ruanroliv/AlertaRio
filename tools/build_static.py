"""Build output for static presentation hosting; Python source stays in frontend/."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parent.parent
output=root/'dist'
output.mkdir(exist_ok=True)
for path in (root/'frontend').iterdir():
    if path.is_file():shutil.copy2(path,output/path.name)
print('Static presentation copied to dist/. Real authentication runs only with the Python backend.')
