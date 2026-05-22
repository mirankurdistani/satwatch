import math
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Test edilecek fonksiyonlar
def mm_to_alt(mm):
    mu = 398600.4418
    n = mm * 2 * math.pi / 86400
    a = (mu / n**2) ** (1/3)
    return round(a - 6371, 2)

def calc_dv(mm1, mm2):
    mu = 398600.4418
    def v(mm):
        n = mm * 2 * math.pi / 86400
        a = (mu / n**2) ** (1/3)
        return math.sqrt(mu / a)
    return round(abs(v(mm2) - v(mm1)) * 1000, 4)

def risk_label(d):
    if d < 1:  return "CRITICAL"
    if d < 5:  return "HIGH"
    if d < 20: return "MEDIUM"
    return "LOW"

def distance_km(p1, p2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(p1, p2)))

# ── TESTLER ──

class TestAltitudeCalculation:
    def test_iss_altitude(self):
        """ISS ~420 km civarında olmalı"""
        iss_mm = 15.49
        alt = mm_to_alt(iss_mm)
        assert 400 < alt < 450, f"ISS irtifası beklenen aralıkta değil: {alt}"

    def test_starlink_altitude(self):
        """Starlink ~550 km civarında olmalı"""
        starlink_mm = 15.09
        alt = mm_to_alt(starlink_mm)
        assert 530 < alt < 580, f"Starlink irtifası beklenen aralıkta değil: {alt}"

    def test_deorbit_candidate(self):
        """Deorbit adayı 300 km altında olmalı"""
        deorbit_mm = 16.58
        alt = mm_to_alt(deorbit_mm)
        assert alt < 300, f"Deorbit adayı 300 km üzerinde: {alt}"

    def test_higher_mm_lower_altitude(self):
        """Daha yüksek mean motion = daha düşük irtifa"""
        alt1 = mm_to_alt(15.0)
        alt2 = mm_to_alt(16.0)
        assert alt1 > alt2, "Yüksek MM düşük irtifa vermeli"

    def test_altitude_positive(self):
        """İrtifa her zaman pozitif olmalı"""
        for mm in [14.0, 15.0, 15.5, 16.0, 16.5]:
            assert mm_to_alt(mm) > 0


class TestDeltaV:
    def test_no_maneuver(self):
        """Aynı MM = sıfır delta-v"""
        dv = calc_dv(15.0, 15.0)
        assert dv == 0.0

    def test_positive_delta_v(self):
        """Farklı MM = pozitif delta-v"""
        dv = calc_dv(15.0, 15.1)
        assert dv > 0

    def test_symmetric(self):
        """Delta-v yön bağımsız olmalı"""
        dv1 = calc_dv(15.0, 15.1)
        dv2 = calc_dv(15.1, 15.0)
        assert abs(dv1 - dv2) < 0.0001

    def test_larger_change_larger_dv(self):
        """Büyük MM farkı = büyük delta-v"""
        dv_small = calc_dv(15.0, 15.01)
        dv_large = calc_dv(15.0, 15.1)
        assert dv_large > dv_small


class TestRiskLabel:
    def test_critical(self):
        assert risk_label(0.5) == "CRITICAL"

    def test_critical_boundary(self):
        assert risk_label(0.999) == "CRITICAL"

    def test_high(self):
        assert risk_label(1.0) == "HIGH"
        assert risk_label(4.9) == "HIGH"

    def test_medium(self):
        assert risk_label(5.0) == "MEDIUM"
        assert risk_label(19.9) == "MEDIUM"

    def test_low(self):
        assert risk_label(20.0) == "LOW"
        assert risk_label(1000.0) == "LOW"


class TestDistanceCalculation:
    def test_same_point(self):
        """Aynı nokta = sıfır mesafe"""
        p = (100.0, 200.0, 300.0)
        assert distance_km(p, p) == 0.0

    def test_known_distance(self):
        """Bilinen mesafe: (3,4,0) → (0,0,0) = 5"""
        d = distance_km((3.0, 4.0, 0.0), (0.0, 0.0, 0.0))
        assert abs(d - 5.0) < 0.0001

    def test_positive_distance(self):
        """Mesafe her zaman pozitif"""
        d = distance_km((100.0, 200.0, 300.0), (150.0, 250.0, 350.0))
        assert d > 0
