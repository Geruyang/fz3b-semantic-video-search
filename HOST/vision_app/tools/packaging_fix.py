"""Avoid bundling an unrelated renamed ICU over Qt's Windows system ICU."""
import argparse
from pathlib import Path
import pefile
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('app')
args = parser.parse_args()
app = Path(args.app).resolve()
target = app / '_internal/icuuc.dll'
if target.exists():
    pe = pefile.PE(str(target))
    names = {s.name for s in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    if b'ucnv_open' not in names and any(n and n.startswith(b'ucnv_open_') for n in names):
        # Verify the Windows dependency has the exact API Qt imports.
        system = pefile.PE('C:/Windows/System32/icuuc.dll')
        assert b'ucnv_open' in {s.name for s in system.DIRECTORY_ENTRY_EXPORT.symbols}
        system.close()
        quarantine = app.parent / 'incompatible-icu78.dll'
        shutil.copy2(target, quarantine)
        pe.close()
        assert target.is_relative_to(app)
        target.unlink()
        print('Removed renamed ICU from bundle; Qt resolves Windows system ICU')
