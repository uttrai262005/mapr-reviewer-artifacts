from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[5]
SRC = ROOT / 'skills' / 'multi-agent-grader' / 'skills' / 'structure-grader' / 'grader.py'

spec = importlib.util.spec_from_file_location('paper_structure_grader', SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore
grade = mod.grade
