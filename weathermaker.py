# Copyright (C) 2011, 2013, 2017, 2021 Ben Elliston
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
import pandas as pd
# PyEphem provides scientific-grade astronomical computations
import ephem

import epw
import tmy3
from latlong import LatLong

ghi_trace, dni_trace = None, None


def compute_dhi(hour, ghr, dnr):
    """Compute direct horizontal irradiance.

    DHI = GHI - DNI cos (zenith)
    """
    if dnr == -999 or ghr == -999:
        return -999

    observer.date = hour + datetime.timedelta(minutes=50)
    sun.compute(observer)
    zenith = (math.pi / 2.) - sun.alt
    dhr = ghr - dnr * math.cos(zenith)
    if dhr < 10:
        # Don't worry about diffuse levels below 10 W/m2.
        dhr = 0
    return dhr


def disk_irradiances(hour, location):
    """Return the GHI and DNI for a given location and time."""
    xcoord, ycoord = location.cartesian()

    # Compute a solar data filename from the hour
    filename = hour.strftime(args.grids + '/GHI/%Y/solar_ghi_%Y%m%d_%HUT.txt')
    try:
        with open(filename, 'r', encoding='utf-8') as filehandle:
            line = filehandle.readlines()[xcoord + 6]
        ghr = int(line.split()[ycoord])
    except IOError:
        logging.error('grid file %s missing', filename)
        ghr = 0

    filename = hour.strftime(args.grids + '/DNI/%Y/solar_dni_%Y%m%d_%HUT.txt')
    try:
        with open(filename, 'r', encoding='utf-8') as filehandle:
            line = filehandle.readlines()[xcoord + 6]
        dnr = int(line.split()[ycoord])
    except IOError:
        logging.error('grid file %s missing', filename)
        dnr = 0

    return ghr, dnr


class Station:
    """A simple struct to describe a BoM weather station."""

    def __init__(self):
        """Create a Station object."""
        self.number = 0
        self.name = None
        self.state = None
        self.altitude = 0
        self.location = None


def station_details():
    """Read station details file."""
    stn = Station()
    with open(args.hm_details, 'r', encoding='ascii') as filehandle:
        details = [ln for ln in filehandle if 'st,' + args.st in ln][0]
    # .. st = details[0:3]
    stn.number = details[3:9].strip()
    stn.name = details[15:55].strip()
    stn.state = details[107:110]
    log.info('Processing station number %s (%s)', stn.number, stn.name)

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

    stn.location = location
    stn.altitude = altitude
    return stn


def process_options():
    """Process command line options."""
    parser = argparse.ArgumentParser(description='Please file bug reports at '
                                     'https://github.com/bje-/weather-maker/')
    parser.add_argument('--version', action='version', version='1.1')
    parser.add_argument("--grids", type=str, help='top of gridded data tree',
                        required=True)
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

station = station_details()

# User overrides
if args.latlong is not None:
    station.location = LatLong(*args.latlong)
    station.name = '(%.2f, %.2f)' % tuple(args.latlong)
if args.name is not None:
    station.name = args.name

sun = ephem.Sun()
observer = ephem.Observer()
observer.elevation = station.altitude
observer.lat = str(station.location.lat)
observer.long = str(station.location.lon)

missing_values = {'Air Temperature in degrees C': 99.9,
                  'Wet bulb temperature in degrees C': 99.9,
                  'Dew point temperature in degrees C': 99.9,
                  'Relative humidity in percentage %': 999.,
                  'Wind speed in km/h': 999.,
                  'Wind speed in m/s': 999.,
                  'Wind direction in degrees true': 999.,
                  'Station level pressure in hPa': 999999.}


def _parse(year, month, date, hour, minute):
    dt = datetime.datetime(int(year), int(month), int(date),
                           int(hour), int(minute))
    return pd.to_datetime(dt)


def process_grids():
    """Process every grid in the DataFrame."""
    log.info("Processing grids")
    for i, (_, row) in enumerate(df.iterrows()):

        offset = datetime.timedelta(hours=i)
        tzoffset = datetime.timedelta(hours=args.tz)
        hour = datetime.datetime(args.year, 1, 1) + offset - tzoffset

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

        ghi, dni = disk_irradiances(hour, station.location)
        record['ghi'] = ghi
        record['dni'] = dni
        record['dhi'] = compute_dhi(hour, ghi, dni)

        if args.format.lower() == 'tmy3':
            tmy3.record(outfile, args, record)
        elif args.format.lower() == 'epw':
            epw.record(outfile, args, record)


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

# Interpolate missing data (limit to args.i hours or 2*args.i half-hours)
df.interpolate(inplace=True, limit=args.i * 2)

# Reindex the data to hourly
rng = pd.date_range(datetime.datetime(args.year, 1, 1),
                    datetime.datetime(args.year, 12, 31, 23),
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

with open(args.out, 'w', encoding='ascii') as outfile:
    if args.format.upper() == 'TMY3':
        log.info('Generating a TMY3 file')
        tmy3.preamble(outfile, args, station)
    elif args.format.upper() == 'EPW':
        log.info('Generating an EPW file')
        epw.preamble(outfile, args, station)
    else:
        raise ValueError("unknown format %s" % args.format)
    process_grids()
