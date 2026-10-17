"""Portable plan files contain inputs and provenance, never trusted forecasts."""

from datetime import datetime, timezone
from hashlib import sha256

from .seasons import SEASONS, load_season, season_path
from .temporal_model import ARTIFACT

FORMAT = 'schedule-lab-plan'
VERSION = 1


def data_fingerprint(config):
    season = config['season']
    return {'reference_season': season,
            'sources': {year: {'cutoff': load_season(year)[0]['source']['cutoff'],
                              'sha256': sha256(season_path(year).read_bytes()).hexdigest()}
                        for year in SEASONS if year <= season},
            'probability_model_sha256': sha256(ARTIFACT.read_bytes()).hexdigest()
            if config['probability_model'] == 'historical' else None}


def plan_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80:
        raise ValueError('Plan names must contain 1–80 characters')
    return value.strip()


def export_plan(raw, validate):
    if not isinstance(raw, dict) or set(raw) != {'name', 'config'}:
        raise ValueError('Plan export needs a name and a configuration')
    name = plan_name(raw['name'])
    config, _ = validate(raw['config'])
    return {'format': FORMAT, 'version': VERSION, 'name': name,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'config': config, 'data': data_fingerprint(config)}


def import_plan(raw, validate):
    if not isinstance(raw, dict) or raw.get('format') != FORMAT:
        raise ValueError('Choose a plan JSON file exported by Schedule Lab')
    if type(raw.get('version')) is not int or raw['version'] != VERSION:
        raise ValueError('This plan file version is not supported')
    if set(raw) != {'format', 'version', 'name', 'exported_at', 'config', 'data'}:
        raise ValueError('The plan file is incomplete or has unsupported fields')
    name = plan_name(raw['name'])
    try:
        if not isinstance(raw['exported_at'], str) or datetime.fromisoformat(raw['exported_at'].replace('Z', '+00:00')).tzinfo is None:
            raise ValueError()
    except ValueError as error:
        raise ValueError('The plan export timestamp must include a time zone') from error
    if not isinstance(raw['data'], dict):
        raise ValueError('The plan file needs dataset provenance')
    config, _ = validate(raw['config'])
    matching = raw['data'] == data_fingerprint(config)
    return {'name': name, 'config': config, 'data_matches': matching,
            'notices': ([] if matching else ['This file used a different data version. Recalculation will use the data currently installed.'])
            + ['Setup imported; recalculate to obtain results. Existing saved plans are kept.']}
