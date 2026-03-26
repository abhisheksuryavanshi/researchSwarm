"""Unit tests for search logic (T024)."""

from registry.search import _cosine_distance


def test_cosine_distance_identical():
    v = [1.0, 0.0, 0.5]
    assert abs(_cosine_distance(v, v)) < 1e-6


def test_cosine_distance_orthogonal():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert abs(_cosine_distance(a, b) - 1.0) < 1e-6


def test_cosine_distance_opposite():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(_cosine_distance(a, b) - 2.0) < 1e-6


def test_cosine_distance_zero_vector():
    a = [0.0, 0.0]
    b = [1.0, 1.0]
    assert _cosine_distance(a, b) == 1.0
