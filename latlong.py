# Copyright (C) 2010, 2011, 2014 Ben Elliston
#
# Latitude/longitude spherical geodesy formulae and scripts are
# (C) Chris Veness 2002-2011
# (www.movable-type.co.uk/scripts/latlong.html)
#
# This file is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

"""Latitude and longitude support for the BoM solar irradiance grids."""
import math


CELLSIZE = 0.05
XLLCORNER = 112.025
YLLCORNER = -43.925
MAXCOLS = 839
MAXROWS = 679


class LatLong:
    """A point of latitude and logitude."""

    def __init__(self, arg1, arg2, is_xy=False):
        """Initialise a lat/long object.

        >>> obj = LatLong(-35, 149)
        >>> obj = LatLong(1, 10, True)
        >>> obj = LatLong(1, 2, True)
        >>> obj = LatLong(679, 839, True)
        >>> obj = LatLong(839, 679, True)
        Traceback (most recent call last):
          ...
        ValueError
        >>> obj = LatLong (499, 739, True)
        >>> round(obj.lat, 3)  # round for test safety
        -34.925
        >>> round(obj.lon, 3)  # round for test safety
        148.975
        """
        if is_xy:
            if arg1 > MAXROWS or arg2 > MAXCOLS:
                raise ValueError
            self.lat = YLLCORNER + CELLSIZE * (MAXROWS - arg1)
            self.lon = XLLCORNER + CELLSIZE * arg2
        else:
            self.lat = arg1
            self.lon = arg2

    def cartesian(self):
        """
        Return the Cartesian coordinate.

        >>> obj = LatLong(-35, 149)
        >>> obj.cartesian()
        (499, 739)
        >>> obj = LatLong(0, 0, True)
        >>> round(obj.lat, 3)  # round for test safety
        -9.975
        >>> round(obj.lon, 3)  # round for test safety
        112.025
        """
        col = int((self.lon - XLLCORNER) / CELLSIZE)
        assert col < MAXCOLS
        row = int(MAXROWS - ((self.lat - YLLCORNER) / CELLSIZE)) - 1
        assert row >= 0
        return row, col

    def __repr__(self):
        """
        Print object representation.

        >>> obj = LatLong(-35, 149)
        >>> repr(obj)
        '(-35, 149)'
        """
        return self.__str__()

    def __str__(self):
        """
        Return string representation of the object.

        >>> obj = LatLong(-35, 149)
        >>> str(obj)
        '(-35, 149)'
        """
        return '(' + str(self.lat) + ', ' + str(self.lon) + ')'
