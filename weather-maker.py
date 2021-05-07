# Copyright (C) 2011, 2013, 2017 Ben Elliston
#
# This file is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# If you find a bug or implement an enhancement, please send a patch
# to the author in the form of a unified context diff (diff -u).

"""A tool to generate TMY3 or EPW weather data files."""

import os
import math
import sys
import argparse
import datetime
import logging
import urllib.request
import urllib.parse
import urllib.error
import pandas as pd
# PyEphem provides scientific-grade astronomical computations
import ephem

from latlong import LatLong

ghi_trace, dni_trace = None, None


def tmy3_preamble(f):
    """Emit the required headers for a TMY3 file.

    eg. 722287,"ANNISTON METROPOLITAN AP",AL,-6.0,33.583,-85.850,186
    """
    print('%s in %s,\"%s\",%s,%.1f,%.3f,%.3f,%d' %
          (stnumber, stname, args.year, ststate[0:2], args.tz,
           locn.lat, locn.lon, elevation), file=f)
    print('Date (MM/DD/YYYY),Time (HH:MM),ETR (W/m^2),ETRN (W/m^2),GHI (W/m^2),GHI source,GHI uncert (%),DNI (W/m^2),DNI source,DNI uncert (%),DHI (W/m^2),DHI source,DHI uncert (%),GH illum (lx),GH illum source,Global illum uncert (%),DN illum (lx),DN illum source,DN illum uncert (%),DH illum (lx),DH illum source,DH illum uncert (%),Zenith lum (cd/m^2),Zenith lum source,Zenith lum uncert (%),TotCld (tenths),TotCld source,TotCld uncert (code),OpqCld (tenths),OpqCld source,OpqCld uncert (code),Dry-bulb (C),Dry-bulb source,Dry-bulb uncert (code),Dew-point (C),Dew-point source,Dew-point uncert (code),RHum (%),RHum source,RHum uncert (code),Pressure (mbar),Pressure source,Pressure uncert (code),Wdir (degrees),Wdir source,Wdir uncert (code),Wspd (m/s),Wspd source,Wspd uncert (code),Hvis (m),Hvis source,Hvis uncert (code),CeilHgt (m),CeilHgt source,CeilHgt uncert (code),Pwat (cm),Pwat source,Pwat uncert (code),AOD (unitless),AOD source,AOD uncert (code),Alb (unitless),Alb source,Alb uncert (code),Lprecip depth (mm),Lprecip quantity (hr),Lprecip source,Lprecip uncert (code)', file=f)  # noqa: E501


def epw_preamble(f):
    """Emit the required headers for an EPW file."""
    print('LOCATION,%s in %s,%s,AUS,BoM,%s,%.2f,%.2f,%.1f,%.1f' %
          (stname, args.year, ststate, stnumber, locn.lat, locn.lon,
           args.tz, elevation), file=f)

    print('DESIGN CONDITIONS,0', file=f)
    print('TYPICAL/EXTREME PERIODS,,', file=f)
    print('GROUND TEMPERATURES,,,,,,', file=f)
    print('HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0', file=f)
    print('COMMENTS 1,Generated by weather-maker.py from Bureau of '
          'Meteorology solar and weather data (%d)' % args.year, file=f)
    print('COMMENTS 2,Please report weather-maker bugs to bje@air.net.au',
          file=f)
    print('DATA PERIODS,1,1,Data,Sunday,1/ 1,12/31', file=f)


def tmy3_record(f, rec):
    """Emit a record in TMY3 format."""
    t = datetime.datetime(args.year, 1, 1)
    t += datetime.timedelta(hours=rec['hour'])
    if t.month == 2 and t.day == 29:
        # Skip leap day
        return

    text = '%02d/%02d/%d,%02d:50,-9900,-9900,%d,1,5,%d,1,5,%d,1,0,-9900,1,0,-9900,1,0,-9900,1,0,-9900,1,0,-9900,?,9,-9900,?,9,%.1f,A,7,%.1f,A,7,%.1f,A,7,%d,A,7,%d,A,7,%.1f,A,7,-9900,?,9,-9900,?,9,-9900,?,9,-9900,?,9,-9900,?,9,-9900,-9900,?,9' \
        % (t.month, t.day, t.year, t.hour + 1, rec['ghi'], rec['dni'],  # noqa: E501
           rec['dhi'], rec['dry-bulb'], rec['dew-point'],
           rec['rel-humidity'], rec['atm-pressure'] / 100,
           rec['wind-direction'], rec['wind-speed'])
    print(text, file=f)


def epw_record(f, rec):
    """Emit a record in EPW format."""
    t = datetime.datetime(args.year, 1, 1)
    t += datetime.timedelta(hours=rec['hour'])
    if t.month == 2 and t.day == 29:
        # Skip leap day
        return

    text = '%d,%d,%d,%d,50,%s,%.1f,%.1f,%d,%d,9999,9999,9999,%d,%d,%d,999999,999999,999999,999999,%d,%.1f,99,99,9999,99999,9,999999999,99999,0.999,999,99,999,0,99' \
        % (t.year, t.month, t.day, t.hour + 1, '_' * 39,  # noqa: E501
           rec['dry-bulb'],
           rec['dew-point'], rec['rel-humidity'], rec['atm-pressure'],
           rec['ghi'], rec['dni'], rec['dhi'], rec['wind-direction'],
           rec['wind-speed'])
    print(text, file=f)


def compute_dhi(hour, ghr, dnr):
    """
    Compute direct horizontal irradiance:
    DHI = GHI - DNI cos (zenith)
    """
    if dnr == -999 or ghr == -999:
        return -999

    # pylint: disable=assigning-non-slot
    observer.date = hour + datetime.timedelta(minutes=50)
    sun.compute(observer)
    zenith = (math.pi / 2.) - sun.alt
    dhr = ghr - dnr * math.cos(zenith)
    if dhr < 10:
        # Don't worry about diffuse levels below 10 W/m2.
        dhr = 0
    return dhr


def http_irradiances(hour, location):
    """Return the GHI and DNI for a given location and time via AREMI."""
    global dni_trace, ghi_trace  # pylint: disable=global-statement

    tzmin, tzhour = math.modf(args.tz)
    tzmin *= 60
    assert tzmin in (0, 30)
    params = {'start': '%d-01-01T00:00:00+%02d%02d' %
                       (args.year, tzhour, tzmin),
              'end': '%d-01-01T00:00:00+%02d%02d' %
                     (args.year + 1, tzhour, tzmin)}
    prefix = 'http://services.aremi.data61.io/solar-satellite/v1'

    if dni_trace is None:
        dni_trace = pd.read_csv('%s/DNI/%s/%s?%s' %
                                (prefix, location.lat, location.lon,
                                 urllib.parse.urlencode(params)),
                                parse_dates=True,
                                index_col='UTC time',
                                na_values='-')
        dni_trace.interpolate(inplace=True, limit=args.i)
        dni_null_count = dni_trace.isnull().sum().sum()
        if dni_null_count > 0:
            log.warning('missing values in DNI data: %d', dni_null_count)
        dni_trace.fillna(-999, inplace=True)

    if ghi_trace is None:
        ghi_trace = pd.read_csv('%s/GHI/%s/%s?%s' %
                                (prefix, location.lat, location.lon,
                                 urllib.parse.urlencode(params)),
                                parse_dates=True,
                                index_col='UTC time',
                                na_values='-')
        ghi_trace.interpolate(inplace=True, limit=args.i)
        ghi_null_count = ghi_trace.isnull().sum().sum()
        if ghi_null_count > 0:
            log.warning('missing values in GHI data: %d', ghi_null_count)
        ghi_trace.fillna(-999, inplace=True)

    ghr = ghi_trace.loc[hour, 'Value']
    dnr = dni_trace.loc[hour, 'Value']
    return ghr, dnr


def disk_irradiances(hour, location):
    """Return the GHI and DNI for a given location and time."""
    x, y = location.xy()

    # Compute a solar data filename from the hour
    filename = hour.strftime(args.grids + '/GHI/%Y/solar_ghi_%Y%m%d_%HUT.txt')
    try:
        with open(filename, 'r') as filehandle:
            line = filehandle.readlines()[x + 6]
        ghr = int(line.split()[y])
    except IOError:
        logging.error('grid file %s missing', filename)
        ghr = 0

    filename = hour.strftime(args.grids + '/DNI/%Y/solar_dni_%Y%m%d_%HUT.txt')
    try:
        with open(filename, 'r') as filehandle:
            line = filehandle.readlines()[x + 6]
        dnr = int(line.split()[y])
    except IOError:
        logging.error('grid file %s missing', filename)
        dnr = 0

    return ghr, dnr


def station_details():
    """Read station details file."""
    details = [ln for ln in open(args.hm_details) if 'st,' + args.st in ln][0]
    # .. st = details[0:3]
    st_number = details[3:9].strip()
    st_name = details[15:55].strip()
    st_state = details[107:110]
    log.info('Processing station number %s (%s)', stnumber, stname)

    latitude = float(details[72:80])
    longitude = float(details[81:90])
    location = LatLong(latitude, longitude)
    altitude = int(float(details[111:117]))
    wflags = details[153:156]
    sflags = details[157:160]
    iflags = details[161:164]
    if int(wflags) or int(sflags) or int(iflags):
        log.warning('%% wrong = %s, %% suspect = %s, %% inconsistent = %s',
                    wflags, sflags, iflags)

    return location, altitude, st_number, st_name, st_state


def process_options():
    """Process command line options."""
    parser = argparse.ArgumentParser(description='Please file bug reports at '
                                     'https://github.com/bje-/weather-maker/')
    parser.add_argument('--version', action='version', version='1.1')
    parser.add_argument("--grids", type=str, help='top of gridded data tree')
    parser.add_argument("-l", "--latlong", type=float, nargs=2,
                        help='latitude and longitude of location')
    parser.add_argument("-i", type=int, default=2,
                        help='maximum length of interpolation (hours)')
    parser.add_argument("-y", "--year", type=int, help='year to generate',
                        required=True)
    parser.add_argument("--st", type=str,
                        help='nearest BoM station code (required)',
                        required=True)
    parser.add_argument("--name", type=str, help='Override station name')
    parser.add_argument("--hm-data", type=str, help='BoM station data file',
                        required=True)
    parser.add_argument("--hm-details", type=str,
                        help='BoM station details file', required=True)
    parser.add_argument("--tz", type=float, default=10.0,
                        help='Time zone [default +10]')
    parser.add_argument("-o", "--out", type=str, help='output filename',
                        required=True)
    parser.add_argument("--format", type=str, default="epw",
                        help="output format: EPW [default] or TMY3")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose",
                        help="verbose run output")
    return parser.parse_args()


args = process_options()

logging.basicConfig(format='%(levelname)s: %(message)s')
log = logging.getLogger()
if args.verbose:
    log.setLevel(logging.INFO)

# Check that the grid directory exists
if args.grids is not None and not os.path.isdir(args.grids):
    log.critical('%s is not a directory', args.grids)
    sys.exit(1)

outfile = open(args.out, 'w')

locn, elevation, stnumber, stname, ststate = station_details()

# User overrides
if args.latlong is not None:
    locn = LatLong(*args.latlong)
    stname = '(%.2f, %.2f)' % tuple(args.latlong)
if args.name is not None:
    stname = args.name

sun = ephem.Sun()
observer = ephem.Observer()
observer.elevation = elevation  # pylint: disable=assigning-non-slot
observer.lat = str(locn.lat)    # pylint: disable=assigning-non-slot
observer.long = str(locn.lon)   # pylint: disable=assigning-non-slot

if args.format.lower() == 'tmy3':
    log.info('Generating a TMY3 file')
    tmy3_preamble(outfile)
elif args.format.lower() == 'epw':
    log.info('Generating an EPW file')
    epw_preamble(outfile)
else:
    raise ValueError("unknown format %s" % args.format)

missing_values = {'Air Temperature in degrees C': 99.9,
                  'Wet bulb temperature in degrees C': 99.9,
                  'Dew point temperature in degrees C': 99.9,
                  'Relative humidity in percentage %': 999.,
                  'Wind speed in km/h': 999.,
                  'Wind speed in m/s': 999.,
                  'Wind direction in degrees true': 999.,
                  'Station level pressure in hPa': 999999.}


def _parse(y, m, d, hh, mm):
    return pd.datetime(int(y), int(m), int(d), int(hh), int(mm))


df = pd.read_csv(args.hm_data,
                 sep=',',
                 skipinitialspace=True,
                 low_memory=False,
                 date_parser=_parse,
                 index_col='datetime',
                 parse_dates={'datetime':
                              ['Year Month Day Hour Minutes in YYYY.1',
                               'MM.1', 'DD.1', 'HH24.1',
                               'MI format in Local standard time']})

# Interpolate missing data (limit to args.i hours aka 2*args.i half-hours)
df.interpolate(inplace=True, limit=args.i * 2)

# Reindex the data to hourly
rng = pd.date_range(pd.datetime(args.year, 1, 1),
                    pd.datetime(args.year, 12, 31, 23),
                    freq='H')
df = df.reindex(rng)

# Basic integrity check on the dataframe
assert len(df) == 8784 if args.year % 4 == 0 else 8760

# Count missing values
subset = df.loc[:, ['Air Temperature in degrees C',
                    'Wet bulb temperature in degrees C',
                    'Dew point temperature in degrees C',
                    'Relative humidity in percentage %',
                    'Wind speed in km/h', 'Wind direction in degrees true',
                    'Station level pressure in hPa']]
if subset.isnull().sum().sum() > 0:
    log.warning('missing values in weather data:\n%s', subset.isnull().sum())

# Handle missing values
df.fillna(value=missing_values, inplace=True)

log.info("Processing grids")

for i, (_, row) in enumerate(df.iterrows()):

    offset = datetime.timedelta(hours=i)
    tzoffset = datetime.timedelta(hours=args.tz)
    hr = datetime.datetime(args.year, 1, 1) + offset - tzoffset

    record = {}
    record['hour'] = i
    record['dry-bulb'] = row['Air Temperature in degrees C']
    record['wet-bulb'] = row['Wet bulb temperature in degrees C']
    record['dew-point'] = row['Dew point temperature in degrees C']
    record['rel-humidity'] = row['Relative humidity in percentage %']
    record['wind-speed'] = row['Wind speed in km/h']
    if record['wind-speed'] != 999:
        record['wind-speed'] /= 3.6

    record['wind-direction'] = row['Wind direction in degrees true']
    record['atm-pressure'] = row['Station level pressure in hPa']
    if record['atm-pressure'] != 999999:
        record['atm-pressure'] *= 100.

    if args.grids is not None:
        ghi, dni = disk_irradiances(hr, locn)
    else:
        ghi, dni = http_irradiances(hr, locn)

    record['ghi'] = ghi
    record['dni'] = dni
    record['dhi'] = compute_dhi(hr, ghi, dni)

    if args.format.lower() == 'tmy3':
        tmy3_record(outfile, record)
    elif args.format.lower() == 'epw':
        epw_record(outfile, record)

outfile.close()
