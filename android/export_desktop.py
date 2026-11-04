"""Convert the PC snippet YAML to the phone's safe JSON interchange format. No history."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import Store, data_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=data_dir() / 'snippets.yaml')
    parser.add_argument('--output', type=Path, default=ROOT / 'release' / 'Android' / 'TwistType-PC-snippets.json')
    args = parser.parse_args()
    if not args.source.is_file():
        raise SystemExit('No existing PC library was found. Launch the PC app or pass --source to an existing snippets.yaml.')
    data = Store(args.source).load()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'version': 1, 'snippets': data['snippets']}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Exported {len(data["snippets"])} snippets to {args.output}. Clipboard history was not exported.')


if __name__ == '__main__':
    main()
