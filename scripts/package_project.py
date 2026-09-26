from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

root=Path(__file__).resolve().parents[1]
output=root/'artifacts/SwarmShield.zip'
output.parent.mkdir(exist_ok=True)
excluded={'node_modules','.venv','__pycache__','.pytest_cache','.git','artifacts','test-results','playwright-report'}
with ZipFile(output,'w',compression=ZIP_DEFLATED,compresslevel=9) as archive:
    for path in sorted(root.rglob('*')):
        relative=path.relative_to(root)
        if path.is_file() and not excluded.intersection(relative.parts) and path.suffix not in {'.log','.pyc','.tsbuildinfo'}:
            archive.write(path,Path('SwarmShield')/relative)
print(f'{output} ({output.stat().st_size/1024/1024:.2f} MB)')
