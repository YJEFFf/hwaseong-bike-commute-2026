from analysis.osm_filter import is_bike_facility, is_crossing, is_low_stress

def test_no_tags_are_not_facilities():
    assert not is_bike_facility({"highway": "secondary", "cycleway:both": "no"})
    assert not is_bike_facility({"highway": "tertiary", "cycleway:right": "no"})

def test_real_facilities():
    assert is_bike_facility({"highway": "cycleway"})
    assert is_bike_facility({"highway": "footway", "bicycle": "designated"})
    assert is_bike_facility({"highway": "primary", "cycleway:left": "lane"})

def test_separately_mapped_road_tag_not_double_counted():
    assert not is_bike_facility({"highway": "primary", "cycleway:both": "separate"})

def test_crossing():
    assert is_crossing({"highway": "cycleway", "cycleway": "crossing"})
    assert is_crossing({"highway": "footway", "footway": "crossing", "bicycle": "designated"})
    assert not is_crossing({"highway": "cycleway"})


def test_low_stress_residential_included():
    assert is_low_stress({"highway": "residential"})


def test_low_stress_primary_without_facility_excluded():
    assert not is_low_stress({"highway": "primary"})


def test_low_stress_primary_with_cycleway_facility_included():
    assert is_low_stress({"highway": "primary", "cycleway:right": "track"})


def test_low_stress_footway_without_bicycle_tag_excluded():
    assert not is_low_stress({"highway": "footway"})


def test_low_stress_footway_with_bicycle_yes_included():
    assert is_low_stress({"highway": "footway", "bicycle": "yes"})


def test_low_stress_service_with_private_access_excluded():
    assert not is_low_stress({"highway": "service", "access": "private"})


def test_low_stress_steps_excluded():
    assert not is_low_stress({"highway": "steps"})


def test_low_stress_cycleway_with_bicycle_no_excluded():
    assert not is_low_stress({"highway": "cycleway", "bicycle": "no"})
