import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('package_project',ROOT/'scripts/package_project.py')
package_project=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_project)

def test_submission_package_excludes_agent_and_generated_files():
    rejected=['CLAUDE.md','AGENTS.md','CODEX.md','PLAN.md','notes_plan.md','frontend/tsconfig.app.tsbuildinfo','node_modules/a.js','backend/.venv/a.py','x/__pycache__/a.pyc','.git/config']
    assert all(not package_project.should_include(Path(path)) for path in rejected)
    assert package_project.should_include(Path('frontend/dist/index.html'))
    assert package_project.should_include(Path('evidence/backend_tests.txt'))
