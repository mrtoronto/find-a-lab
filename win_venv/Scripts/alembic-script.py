#!"c:\users\matt\documents\stuff\02 - programming\00 - projects\find-a-lab\win_venv\scripts\python.exe"
# EASY-INSTALL-ENTRY-SCRIPT: 'alembic==0.9.6','console_scripts','alembic'
__requires__ = 'alembic==0.9.6'
import re
import sys
from pkg_resources import load_entry_point

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(
        load_entry_point('alembic==0.9.6', 'console_scripts', 'alembic')()
    )
