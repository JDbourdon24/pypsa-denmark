from pathlib import Path

import yaml

CONFIG_FILE = Path(__file__).with_name("config.yaml")


def load_config(path: Path | str = CONFIG_FILE) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)
