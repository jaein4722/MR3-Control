"""Collect redistribution notices from the build environment."""
from importlib.metadata import distributions
from pathlib import Path
import shutil
import sys

destination = Path(__file__).resolve().parent.parent / 'build/third-party'
destination.mkdir(parents=True, exist_ok=True)
inventory = []
for dist in distributions():
    name = dist.metadata['Name']
    inventory.append(f'{name}=={dist.version}')
    for file in dist.files or ():
        if any(part.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')) for part in Path(str(file)).parts):
            source = Path(dist.locate_file(file))
            if source.is_file():
                target = destination / name / Path(str(file))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
for source in Path(sys.base_prefix).glob('LICENSE*'):
    if source.is_file():
        shutil.copy2(source, destination / ('Python-' + source.name))
for source in Path(__file__).parent.glob('*-LICENSE.txt'):
    shutil.copy2(source, destination / source.name)
tk_license = Path(sys.base_prefix) / 'tcl/tk8.6/license.terms'
if tk_license.is_file():
    shutil.copy2(tk_license, destination / 'Tk-LICENSE.txt')
(destination / 'DEPENDENCIES.txt').write_text('\n'.join(sorted(inventory)) + '\n', encoding='utf-8')
(destination / 'NOTICE.txt').write_text(
    'MR3 Control is an unofficial application, not an Edifier product.\n'
    'Edifier product photograph: copyright Edifier; see assets/SOURCES.md.\n'
    'Pretendard: SIL Open Font License; see assets/fonts/LICENSE.txt.\n'
    'Python, Tcl/Tk and third-party libraries retain their respective licenses.\n'
    'The inventory includes build tools; listing is not a statement that every tool is shipped.\n', encoding='utf-8')
print(f'License notices collected in {destination}')
