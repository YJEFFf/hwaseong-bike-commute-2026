import pandas as pd
import pytest
from shapely.geometry import Polygon, box

from analysis.ledgers import (
    assert_no_sum_columns,
    energy_rows,
    get_scenario_value,
    load_params,
    s2_wide_existing_area,
    strip_width,
)

CSV_HEADER = "param,low,mid,high,unit,source,url,status,note\n"


def _write_params_csv(tmp_path, extra_rows=""):
    content = (
        CSV_HEADER
        + 'grid_ef,0.4173,0.4173,0.4541,tCO2eq/MWh,"GIR",https://example.com,SECONDARY,"note"\n'
        + 'pv_cf,0.132,0.1466,0.15,fraction,"src",https://example.com,SECONDARY,"note"\n'
        + 'canopy_density,100,109,150,Wp/m2,"src",https://example.com,SECONDARY,"note"\n'
        + 'pv_embodied,480,580,810,kgCO2e/kWp,"Fraunhofer",https://example.com,SECONDARY,"note"\n'
        + 'canopy_steel_mass,,,,kg/m2,,,NOT_FOUND,"1차 출처 없음"\n'
        + extra_rows
    )
    path = tmp_path / "carbon_params.csv"
    path.write_text(content, encoding="utf-8")
    return path


# --- load_params ---------------------------------------------------------

def test_load_params_numeric_parsing(tmp_path):
    path = _write_params_csv(tmp_path)
    params = load_params(path)
    assert params["grid_ef"]["low"] == pytest.approx(0.4173)
    assert params["grid_ef"]["mid"] == pytest.approx(0.4173)
    assert params["grid_ef"]["high"] == pytest.approx(0.4541)
    assert params["grid_ef"]["status"] == "SECONDARY"


def test_load_params_not_found_row_returns_none(tmp_path):
    path = _write_params_csv(tmp_path)
    params = load_params(path)
    row = params["canopy_steel_mass"]
    assert row["low"] is None
    assert row["mid"] is None
    assert row["high"] is None
    assert row["status"] == "NOT_FOUND"


def test_get_scenario_value_raises_naming_param(tmp_path):
    path = _write_params_csv(tmp_path)
    params = load_params(path)
    with pytest.raises(ValueError, match="canopy_steel_mass"):
        get_scenario_value(params, "canopy_steel_mass", "mid")


# --- strip_width -----------------------------------------------------------

def test_strip_width_rectangle():
    rect = box(0, 0, 100, 3)  # 100 m x 3 m
    w = strip_width(rect)
    assert abs(w - 3.0) / 3.0 < 0.03


# --- energy_rows -------------------------------------------------------------

def _synthetic_params():
    return {
        "canopy_density": {"low": 100.0, "mid": 160.0, "high": 150.0, "status": "SECONDARY"},
        "pv_cf": {"low": 0.132, "mid": 0.132, "high": 0.15, "status": "SECONDARY"},
        "grid_ef": {"low": 0.4173, "mid": 0.4173, "high": 0.4541, "status": "SECONDARY"},
        "pv_embodied": {"low": 480.0, "mid": 580.0, "high": 810.0, "status": "SECONDARY"},
    }


def test_energy_rows_mid_reproduces_carbon_test_values():
    params = _synthetic_params()
    row = energy_rows(2500.0, params, "mid")
    assert abs(row["capacity_kw"] - 400.0) < 1e-9
    assert abs(row["energy_mwh_yr"] - 462.53) < 0.1


def test_energy_rows_sanity_hours_relation():
    params = _synthetic_params()
    row = energy_rows(2500.0, params, "mid")
    # mid MWh per kW per year must equal 8.76 * pv_cf mid
    per_kw = row["energy_mwh_yr"] / row["capacity_kw"]
    assert abs(per_kw - 8.76 * params["pv_cf"]["mid"]) < 1e-6


def test_energy_rows_scenario_mapping_pessimistic_uses_high_embodied_low_density():
    params = _synthetic_params()
    row = energy_rows(2500.0, params, "low")
    expected_kw = 2500.0 * params["canopy_density"]["low"] / 1000.0
    assert abs(row["capacity_kw"] - expected_kw) < 1e-9
    expected_embodied_t = row["capacity_kw"] * params["pv_embodied"]["high"] / 1000.0
    assert abs(row["pv_module_embodied_t"] - expected_embodied_t) < 1e-9


def test_energy_rows_scenario_mapping_optimistic_uses_low_embodied_high_density():
    params = _synthetic_params()
    row = energy_rows(2500.0, params, "high")
    expected_kw = 2500.0 * params["canopy_density"]["high"] / 1000.0
    assert abs(row["capacity_kw"] - expected_kw) < 1e-9
    expected_embodied_t = row["capacity_kw"] * params["pv_embodied"]["low"] / 1000.0
    assert abs(row["pv_module_embodied_t"] - expected_embodied_t) < 1e-9


def test_energy_rows_low_mid_high_ordering():
    params = _synthetic_params()
    low = energy_rows(2500.0, params, "low")
    mid = energy_rows(2500.0, params, "mid")
    high = energy_rows(2500.0, params, "high")
    assert low["energy_mwh_yr"] <= mid["energy_mwh_yr"] <= high["energy_mwh_yr"]
    assert low["avoided_tco2_yr"] <= mid["avoided_tco2_yr"] <= high["avoided_tco2_yr"]


# --- s2_wide_existing_area ---------------------------------------------------

def test_s2_wide_existing_area_filters_by_width():
    region = box(0, 0, 200, 200)
    wide = box(10, 10, 110, 13)      # 100 x 3 -> width ~2.91 (>=3.0? just under)
    wide2 = box(10, 50, 110, 55)     # 100 x 5 -> width ~4.76 (kept)
    narrow = box(10, 100, 60, 101)   # 50 x 1 -> width ~0.98 (dropped)
    result = s2_wide_existing_area([wide2, narrow], region, min_width=3.0)
    assert result["kept"] == 1
    assert result["total"] == 2
    assert result["area_m2"] == pytest.approx(wide2.area)


def test_s2_wide_existing_area_clips_to_region():
    region = box(0, 0, 50, 200)
    poly = box(10, 10, 110, 15)  # extends past region on the right, width ~4.76
    result = s2_wide_existing_area([poly], region, min_width=3.0)
    assert result["kept"] == 1
    clipped = poly.intersection(region)
    assert result["area_m2"] == pytest.approx(clipped.area)


# --- no-sum guard --------------------------------------------------------

def test_assert_no_sum_columns_passes_on_clean_table():
    df = pd.DataFrame({"ledger": ["energy"], "area_m2": [100.0]})
    assert_no_sum_columns(df)  # no raise


def test_assert_no_sum_columns_rejects_hapgye_column():
    df = pd.DataFrame({"ledger": ["energy"], "합계": [100.0]})
    with pytest.raises(AssertionError):
        assert_no_sum_columns(df)


def test_assert_no_sum_columns_rejects_total_column():
    df = pd.DataFrame({"ledger": ["energy"], "total_kw": [100.0]})
    with pytest.raises(AssertionError):
        assert_no_sum_columns(df)
