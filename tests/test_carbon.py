import pytest

from analysis.carbon import (
    payback_years,
    pv_capacity_kw,
    pv_energy_mwh,
    required_avoided_vkm,
)


def test_required_vkm():
    assert abs(required_avoided_vkm(5.0, 0.163) - 30674.8) < 1.0     # 5 t ÷ 0.163 kg/vkm


def test_pv_units():
    kw = pv_capacity_kw(2500.0, 160.0)                                  # m² × Wp/m² → kW
    assert abs(kw - 400.0) < 1e-9
    assert abs(pv_energy_mwh(kw, 0.132) - 462.53) < 0.1                 # kW × CF × h → MWh


def test_payback():
    assert abs(payback_years(700.0, 192.0) - 3.6458) < 1e-3


# --- input validation ---

def test_required_vkm_rejects_non_positive_ef():
    with pytest.raises(ValueError):
        required_avoided_vkm(5.0, 0.0)
    with pytest.raises(ValueError):
        required_avoided_vkm(5.0, -0.163)


def test_required_vkm_rejects_negative_extra_emission():
    with pytest.raises(ValueError):
        required_avoided_vkm(-5.0, 0.163)


def test_pv_capacity_kw_rejects_negative_area():
    with pytest.raises(ValueError):
        pv_capacity_kw(-2500.0, 160.0)


def test_pv_capacity_kw_rejects_negative_density():
    with pytest.raises(ValueError):
        pv_capacity_kw(2500.0, -160.0)


def test_pv_energy_mwh_rejects_negative_p_rated():
    with pytest.raises(ValueError):
        pv_energy_mwh(-400.0, 0.132)


def test_pv_energy_mwh_rejects_cf_outside_0_1():
    with pytest.raises(ValueError):
        pv_energy_mwh(400.0, -0.1)
    with pytest.raises(ValueError):
        pv_energy_mwh(400.0, 1.1)


def test_pv_energy_mwh_rejects_non_positive_hours():
    with pytest.raises(ValueError):
        pv_energy_mwh(400.0, 0.132, hours=0.0)
    with pytest.raises(ValueError):
        pv_energy_mwh(400.0, 0.132, hours=-8760.0)


def test_payback_years_rejects_negative_embodied():
    with pytest.raises(ValueError):
        payback_years(-700.0, 192.0)


def test_payback_years_rejects_non_positive_annual_saving():
    with pytest.raises(ValueError):
        payback_years(700.0, 0.0)
    with pytest.raises(ValueError):
        payback_years(700.0, -192.0)
