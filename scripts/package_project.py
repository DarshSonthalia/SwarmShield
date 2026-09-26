from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

root=Path(__file__).resolve().parents[1]
output=root/'artifacts/SwarmShield.zip'
excluded_parts={'node_modules','.venv','venv','env','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.git','artifacts','test-results','playwright-report'}
excluded_names={'CLAUDE.md','AGENTS.md','CODEX.md','PLAN.md','IMPLEMENTATION_PLAN.md','TODO.md','NOTES.md'}

def should_include(relative: Path) -> bool:
    name=relative.name
    lowered=name.lower()
    if excluded_parts.intersection(relative.parts) or name in excluded_names:
        return False
    if relative.parts[:2] in {('docs','ai'),('docs','agent')}:
        return False
    if lowered.endswith(('_plan.md','_agent.md')) or relative.suffix in {'.log','.pyc','.tsbuildinfo'}:
        return False
    return True

def main() -> None:
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output,'w',compression=ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(root.rglob('*')):
            relative=path.relative_to(root)
            if path.is_file() and should_include(relative):
                archive.write(path,Path('SwarmShield')/relative)
    print(f'{output} ({output.stat().st_size/1024/1024:.2f} MB)')

if __name__=='__main__':
    main()
