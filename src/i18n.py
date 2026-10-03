import gettext
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "locales"

_translation = gettext.translation("noot", LOCALE_DIR, fallback=True)
tr = _translation.gettext
ngettext = _translation.ngettext