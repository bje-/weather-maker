# weather-maker
TMY3/EPW weather data file creation tool

This utility processes publicly available Bureau of Meteorology
weather and solar radiation data into a TMY3 or EPW format file
suitable for tools such as SAM and EnergyPlus. In addition, it
attempts to clean up the data to produce a high quality weather data
file.

Usage: `weather-maker.py [-h] [--version] [--grids GRIDS] [-l LATLONG LATLONG]
                        [-i I] -y YEAR --st ST [--name NAME] --hm-data HM_DATA
                        --hm-details HM_DETAILS [--tz TZ] -o OUT
                        [--format FORMAT] [-v]`

This script now requires Python 3.

Please file bug reports at https://github.com/bje-/weather-maker/issues
