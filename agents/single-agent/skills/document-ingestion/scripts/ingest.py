from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[5]
EXTRACT = ROOT / 'skills' / 'multi-agent-grader' / 'scripts' / 'extract_text.py'

spec = importlib.util.spec_from_file_location('paper_extract_text', EXTRACT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore
extract_text = mod.extract_text


def ingest(path: str) -> str:
    return extract_text(Path(path))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    args = ap.parse_args()
    print(ingest(args.path))
