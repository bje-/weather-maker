# Copyright (C) 2021 Ben Elliston
#
# This file is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

"""Backend routines for the Typical Meteorological Year (TMY3) file format."""

import datetime


def preamble(filehandle, args, station):
    """Emit the required headers for a TMY3 file.

    eg. 722287,"ANNISTON METROPOLITAN AP",AL,-6.0,33.583,-85.850,186
    """
    print(f'{station.number}, \"{station.name} in {args.year}\",'
          f'{station.state[:2]},{args.tz:.1f},'
          f'{station.location.lat:.3f},{station.location.lon:.3f},'
          f'{station.elevation}', file=filehandle)

    print("""Date (MM/DD/YYYY),Time (HH:MM),ETR (W/m^2),ETRN (W/m^2),
GHI (W/m^2),GHI source,GHI uncert (%),DNI (W/m^2),DNI source,DNI uncert (%),
DHI (W/m^2),DHI source,DHI uncert (%),GH illum (lx),GH illum source,
Global illum uncert (%),DN illum (lx),DN illum source,DN illum uncert (%),
DH illum (lx),DH illum source,DH illum uncert (%),Zenith lum (cd/m^2),
Zenith lum source,Zenith lum uncert (%),TotCld (tenths),TotCld source,
TotCld uncert (code),OpqCld (tenths),OpqCld source,OpqCld uncert (code),
Dry-bulb (C),Dry-bulb source,Dry-bulb uncert (code),Dew-point (C),
Dew-point source,Dew-point uncert (code),RHum (%),RHum source,
RHum uncert (code),Pressure (mbar),Pressure source,Pressure uncert (code),
Wdir (degrees),Wdir source,Wdir uncert (code),Wspd (m/s),Wspd source,
Wspd uncert (code),Hvis (m),Hvis source,Hvis uncert (code),CeilHgt (m),
CeilHgt source,CeilHgt uncert (code),Pwat (cm),Pwat source,Pwat uncert (code),
AOD (unitless),AOD source,AOD uncert (code),Alb (unitless),Alb source,
Alb uncert (code),Lprecip depth (mm),Lprecip quantity (hr),Lprecip source,
Lprecip uncert (code)""", file=filehandle)  # noqa: E501


def record(filehandle, args, rec):
    """Emit a record in TMY3 format."""
    time = datetime.datetime(args.year, 1, 1)
    time += datetime.timedelta(hours=rec['hour'])
    if time.month == 2 and time.day == 29:
        # Skip leap day
        return

    text = f"{time.month:02}/{time.day:02}/{time.year}," \
        f"{time.hour + 1:02}:50,-9900,-9900,{rec['ghi']},1,5,{rec['dni']}," \
        f"1,5,{rec['dhi']},1,0,-9900,1,0,-9900,1,0,-9900,1,0,-9900,1,0," \
        f"-9900,?,9,-9900,?,9,{rec['dry-bulb']:.1f},A,7," \
        f"{rec['dew-point']:.1f},A,7,{rec['rel-humidity']:.1f},A,7," \
        f"{rec['atm-pressure'] / 100:.1f},A,7,{rec['wind-direction']}," \
        f"A,7,{rec['wind-speed']:.1f},A,7,-9900,?,9,-9900,?,9,-9900,?,9," \
        f"-9900,?,9,-9900,?,9,-9900,-9900,?,9"
    print(text, file=filehandle)
