"""Integration invariants for the shared completed run; no claims of field accuracy."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

OUT = Path(__file__).resolve().parents[1]/'outputs/auto_vector'
pytestmark = pytest.mark.skipif(not (OUT/'run_manifest.json').exists(), reason='run automatic scenarios first')


def test_same_population_and_scenarios():
    df = pd.read_csv(OUT/'access_city.csv')
    assert df.scenario.nunique() == 5
    assert len(df) == 5*3*3
    assert np.allclose(df.population, df.population.iloc[0])
    assert np.allclose(df.reaching_pop+df.detached_pop+df.attached_unreached_pop, df.population)
    assert df.reaching_share.between(0, 1).all()


def test_cutoff_and_nested_scenario_monotonicity():
    df = pd.read_csv(OUT/'access_city.csv')
    for _, group in df.groupby(['scenario', 'kind']):
        assert (np.diff(group.sort_values('cutoff_m').reaching_pop) >= -1e-7).all()
    transitions = pd.read_csv(OUT/'access_transitions.csv')
    nested = transitions[transitions.older.ne('source_union')]
    assert (nested.lost_pop <= 1e-7).all()


def test_dong_and_district_totals_match_city():
    df = pd.read_csv(OUT/'access_scenarios.csv')
    keys = ['scenario', 'kind', 'cutoff_m']
    cols = ['population', 'reaching_pop', 'detached_pop', 'attached_unreached_pop']
    city = df[df.level.eq('city')].set_index(keys)[cols].sort_index()
    for level in ('dong', 'district'):
        grouped = df[df.level.eq(level)].groupby(keys)[cols].sum().sort_index()
        assert np.allclose(grouped, city)


def test_priority_common_universe_and_budget():
    df = pd.read_csv(OUT/'priority_bundles.csv')
    assert len(df) == 54
    assert df.eligible_n.nunique() == 1
    assert (df.used_length_m <= df.length_budget_m+1e-7).all()
    assert (df.gained_pop >= 0).all()
    assert (df.bottom_group_gained_pop <= df.gained_pop+1e-7).all()
    assert (df.selected_n <= df.eligible_n).all()
    selected = pd.read_csv(OUT/'priority_selections.csv')
    assert not selected.duplicated().any()


def test_sample_not_expanded_to_fake_citywide_validation():
    manifest = json.loads((OUT/'run_manifest.json').read_text(encoding='utf-8'))
    assert manifest['unique_targets'] == 171
    assert manifest['original_sample_rows'] == 176
    assert manifest['origin_count'] == 52300
    assert manifest['destination_count'] == 2278
    assert manifest['human_validation'] is False
    assert manifest['imagery_inference'] is False
    assert manifest['raw_population_reproduced'] is False
    universe = pd.read_csv(OUT/'candidate_universe.csv')
    assert len(universe) == 51
    assert universe.pid.is_unique


def test_all_targets_accounted_for_and_no_unmatched_extent():
    df = pd.read_csv(OUT/'automatic_operations.csv')
    assert all(group.pid.nunique() == 171 for _, group in df.groupby('scenario'))
    assert not df.action.eq('no_exact_source_match_no_edit').any()
    assert df[df.action.eq('polygon_observation_only')].pid.nunique() == 5


def test_frequency_is_bounded_and_candidate_classes_retained():
    df = pd.read_csv(OUT/'priority_stability.csv')
    assert df.pid.is_unique
    for rule in ('short', 'reach', 'bottom20'):
        assert df['selection_frequency_'+rule].between(0, 1).all()
    assert 'intervention_type' in df
    assert df[df.auto_class.eq('supported')].intervention_type.eq('자료 연결 보정 가정').all()
