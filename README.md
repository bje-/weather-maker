# weather-maker
TMY3/EPW weather data file creation tool

This utility takes publicly available Bureau of Meteorology weather
and solar radiation data and processes it into a TMY3 or EPW format
file suitable for tools such as SAM and EnergyPlus. In addition, it
attempts to clean up the data to produce a high quality weather data
file.

Command line usage:

usage: weather-maker.py [-h] [--version] [--grids GRIDS] [-l LATLONG LATLONG]
                        [-i I] -y YEAR --st ST [--name NAME] --hm-data HM_DATA
                        --hm-details HM_DETAILS [--tz TZ] -o OUT
                        [--format FORMAT] [-v]

Please file bug reports at https://github.com/bje-/weather-maker/issues

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --grids GRIDS         top of gridded data tree
  -l LATLONG LATLONG, --latlong LATLONG LATLONG
                        latitude and longitude of location
  -i I                  maximum length of interpolation (hours)
  -y YEAR, --year YEAR  year to generate
  --st ST               nearest BoM station code (required)
  --name NAME           Override station name
  --hm-data HM_DATA     BoM station data file
  --hm-details HM_DETAILS
                        BoM station details file
  --tz TZ               Time zone [default +10]
  -o OUT, --out OUT     output filename
  --format FORMAT       output format: EPW [default] or TMY3
  -v, --verbose         verbose run output
