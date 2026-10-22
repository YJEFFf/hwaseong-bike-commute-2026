import pytest

from analysis.figures import (
    ACCESS_DISTRICTS,
    ACCESS_GROUP_ORDER,
    ACCESS_VERSIONS,
    load_access_by_network,
    load_detached_share,
    plot_access_by_network,
)


def _full_numbers():
    numbers = {"pop_total_hwaseong": "1000000"}
    base_by_version = {"osm": 0.20, "official": 0.30, "union": 0.45, "lowstress": 0.55}
    for version in ACCESS_VERSIONS:
        base = base_by_version[version]
        numbers[f"access_{version}_school_c2500_popshare"] = str(base)
        for i, district in enumerate(ACCESS_DISTRICTS):
            numbers[f"access_{version}_school_c2500_popshare_{district}"] = str(base + 0.01 * (i + 1))
    numbers["access_union_school_c2500_pop_detached"] = "250000.0"
    return numbers


def test_load_access_by_network_happy_path():
    numbers = _full_numbers()

    values = load_access_by_network(numbers)

    assert set(values.keys()) == set(ACCESS_VERSIONS)
    for version in ACCESS_VERSIONS:
        assert set(values[version].keys()) == set(ACCESS_GROUP_ORDER)
    # osm total = 0.20 -> 20.0%
    assert values["osm"]["total"] == pytest.approx(20.0)
    # osm dongtan = 0.20 + 0.01*1 = 0.21 -> 21.0%
    assert values["osm"]["dongtan"] == pytest.approx(21.0)


def test_load_access_by_network_missing_total_key_raises():
    numbers = _full_numbers()
    del numbers["access_union_school_c2500_popshare"]

    with pytest.raises(KeyError, match="access_union_school_c2500_popshare"):
        load_access_by_network(numbers)


def test_load_access_by_network_missing_district_key_raises():
    numbers = _full_numbers()
    del numbers["access_lowstress_school_c2500_popshare_manse"]

    with pytest.raises(KeyError, match="access_lowstress_school_c2500_popshare_manse"):
        load_access_by_network(numbers)


def test_load_detached_share_happy_path():
    numbers = _full_numbers()

    share = load_detached_share(numbers)

    # 250000 / 1000000 * 100 = 25.0
    assert share == pytest.approx(25.0)


def test_load_detached_share_missing_detached_key_raises():
    numbers = _full_numbers()
    del numbers["access_union_school_c2500_pop_detached"]

    with pytest.raises(KeyError, match="access_union_school_c2500_pop_detached"):
        load_detached_share(numbers)


def test_load_detached_share_missing_pop_total_key_raises():
    numbers = _full_numbers()
    del numbers["pop_total_hwaseong"]

    with pytest.raises(KeyError, match="pop_total_hwaseong"):
        load_detached_share(numbers)


def test_plot_access_by_network_creates_nonempty_png(tmp_path):
    numbers = _full_numbers()
    values = load_access_by_network(numbers)
    detached_share = load_detached_share(numbers)
    out_path = tmp_path / "fig2_access_by_network.png"

    result = plot_access_by_network(values, detached_share, out_path)

    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert str(result) == str(out_path)
