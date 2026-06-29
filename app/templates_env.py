"""Shared Jinja2 environment with project filters."""
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def tojson_filter(value):
    return json.dumps(value, ensure_ascii=False)


def create_jinja_env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    env.filters["tojson"] = tojson_filter
    return env


jinja_env = create_jinja_env()
