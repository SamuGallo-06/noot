"""Risoluzione ProductType -> nome commerciale del device.

pymobiledevice3 espone ``ProductType`` (es. ``iPad2,5``), che e' l'identificatore
hardware interno di Apple, non il nome che un utente riconosce (``iPad mini``).
Questo modulo carica una mappa statica ProductType -> nome commerciale da
``assets/device_models.json`` e la espone tramite ``resolve_model_name``.

La mappa e' basata su https://github.com/ElfSundae/iOS-Model-List (MIT
License), integrata a mano con i modelli successivi al 2022 mancanti in
quella fonte. Va aggiornata quando Apple rilascia nuovi ProductType non
ancora presenti nel JSON.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def _load_model_map() -> dict[str, str]:
    """Carica il JSON una sola volta per processo (risultato messo in cache)."""
    data_path = files("noot.assets") / "device_models.json"
    with data_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    ## "_comment" e' un campo informativo nel JSON, non un ProductType reale.
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def resolve_model_name(product_type: str | None) -> str:
    """Ritorna il nome commerciale per un ProductType, o un fallback leggibile.

    :param product_type: es. ``"iPad2,5"``. Puo' essere ``None`` se il device
        non ha ancora fornito questa informazione (es. summary parziale).
    :return: es. ``"iPad mini"``. Se il ProductType non e' in mappa (modello
        troppo recente non ancora aggiunto), ritorna il ProductType stesso
        cosi' l'informazione non va persa, invece di mostrare "Unknown".
    """
    if not product_type:
        return "Unknown model"

    model_map = _load_model_map()
    return model_map.get(product_type, product_type)