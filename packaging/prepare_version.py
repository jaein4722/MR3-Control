"""Generate Windows version resources from VERSION; reject mismatched release tags."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent


def validate_version(value, tag=None):
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value):
        raise ValueError('VERSION must contain a stable major.minor.patch version')
    if any(int(part) > 65535 for part in value.split('.')):
        raise ValueError('Windows version components must be at most 65535')
    if tag is not None and tag != f'v{value}':
        raise ValueError(f'Tag {tag!r} does not match VERSION ({value})')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag')
    args = parser.parse_args()
    version = validate_version((ROOT / 'VERSION').read_text().strip(), args.tag)
    output = ROOT / 'build'
    output.mkdir(exist_ok=True)
    for name in ('version-info.txt', 'app.manifest'):
        template = (ROOT / 'packaging' / name).read_text(encoding='utf-8')
        rendered = template.replace('@VERSION_TUPLE@', version.replace('.', ',') + ',0')
        rendered = rendered.replace('@VERSION@', version)
        (output / name).write_text(rendered, encoding='utf-8')
    print(version)


if __name__ == '__main__':
    main()
