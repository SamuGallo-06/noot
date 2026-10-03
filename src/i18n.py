import gettext
import os
from pathlib import Path

LOCALE_DIR = Path(__file__).parent / "assets" / "locales"


def _language_candidates() -> list[str]:
	candidates = []
	variables = ("LANGUAGE",) if os.environ.get("LANGUAGE") else ("LC_ALL", "LC_MESSAGES", "LANG")
	for variable in variables:
		value = os.environ.get(variable, "")
		for language in value.split(":"):
			language = language.split(".", 1)[0].split("@", 1)[0]
			if language and language not in candidates and language not in ("C", "POSIX"):
				candidates.append(language)
	return candidates


def _load_translation() -> gettext.NullTranslations:
	languages = _language_candidates()
	if languages:
		try:
			return gettext.translation("noot", LOCALE_DIR, languages=languages)
		except FileNotFoundError:
			pass

		for language in languages:
			catalog = LOCALE_DIR / f"{language}.mo"
			if not catalog.exists() and "_" not in language:
				matches = sorted(LOCALE_DIR.glob(f"{language}_*.mo"))
				catalog = matches[0] if matches else catalog
			if catalog.exists():
				with catalog.open("rb") as catalog_file:
					return gettext.GNUTranslations(catalog_file)

	return gettext.NullTranslations()


_translation = _load_translation()
tr = _translation.gettext
ngettext = _translation.ngettext