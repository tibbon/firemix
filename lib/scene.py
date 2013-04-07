import unittest

from lib.fixture import Fixture


class Scene:
    """
    Basic model for a scene.
    """

    def __init__(self, data):
        self._data = data
        self._fixtures = None
        self._fixture_hierarchy = None

    def extents(self):
        return tuple(self._data.get("extents", (0, 0)))

    def name(self):
        return self._data.get("name", "")

    def fixtures(self):
        if self._fixtures is None:
            self._fixtures = [Fixture(fd) for fd in self._data["fixtures"]]
        return self._fixtures

    def fixture(self, strand, address):
        for f in self.fixtures():
            if f.strand() == strand and f.address() == address:
                return f
        return None

    def fixture_hierarchy(self):
        if self._fixture_hierarchy is None:
            self._fixture_hierarchy = dict()
            for f in self.fixtures():
                if not self._fixture_hierarchy.get(f.strand(), None):
                    self._fixture_hierarchy[f.strand()] = dict()
                self._fixture_hierarchy[f.strand()][f.address()] = f
        return self._fixture_hierarchy