import unittest


class Fixture:
    """
    Basic model for a 1D linear fixture
    """

    def __init__(self, data=None):
        self._data = data

    def __repr__(self):
        return "Fixture%d [%d:%d]" % (self.pixels(), self.strand(), self.address())

    def pixels(self):
        """
        Returns the number of pixels in a fixture
        """
        return self._data.get("pixels", 0)

    def pos1(self):
        """
        Returns the (x, y) of the start point of the fixture
        """
        return tuple(self._data.get("pos1", (0, 0)))

    def pos2(self):
        """
        Returns the (x, y) of the end point of the fixture
        """
        return tuple(self._data.get("pos2", (0, 0)))

    def midpoint(self):
        """
        Returns the (x, y) of the midpoint of the fixture
        """
        p1 = self.pos1()
        p2 = self.pos2()
        return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)

    def strand(self):
        """
        Returns the fixture's strand ID
        """
        return self._data.get("strand", 0)

    def address(self):
        """
        Returns the fixture's address on the strand
        """
        return self._data.get("address", 0)

    def pixel_neighbors(self, pixel):
        """
        Returns the one or two neighbors of a pixel on a fixture.
        """
        if pixel < 0 or pixel >= self.pixels():
            return []
        elif pixel == 0:
            return [1]
        elif pixel == (self.pixels() - 1):
            return [self.pixels() - 2]
        else:
            return [pixel - 1, pixel + 1]
