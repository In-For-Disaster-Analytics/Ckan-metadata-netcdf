#!/usr/bin/env python3
"""
NetCDF Metadata Inspector

Simple script to extract and display all metadata from a NetCDF file.
Usage: python inspect_netcdf.py <path_to_netcdf_file>
"""

import sys
import json
from pathlib import Path
import os

def inspect_netcdf_file(netcdf_path):
    """Extract and display comprehensive metadata from a NetCDF file."""
    try:
        import xarray as xr
        import numpy as np

        print(f"🔍 Inspecting NetCDF file: {netcdf_path}")
        print("=" * 80)

        with xr.open_dataset(netcdf_path) as ds:
            metadata = {}

            # Basic file info
            print("\n📁 FILE INFORMATION:")
            file_size = os.path.getsize(netcdf_path)
            print(f"   File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
            print(f"   File path: {netcdf_path}")

            # Global attributes
            print("\n🌍 GLOBAL ATTRIBUTES:")
            global_attrs = dict(ds.attrs)
            metadata['global_attributes'] = global_attrs

            if global_attrs:
                for key, value in global_attrs.items():
                    print(f"   {key}: {value}")
            else:
                print("   No global attributes found")

            # Dimensions
            print("\n📏 DIMENSIONS:")
            for dim_name, dim_size in ds.dims.items():
                print(f"   {dim_name}: {dim_size}")

            # Coordinates
            print("\n🗺️ COORDINATES:")
            for coord_name, coord in ds.coords.items():
                print(f"   {coord_name}:")
                print(f"      Shape: {coord.shape}")
                print(f"      Dtype: {coord.dtype}")
                print(f"      Dims: {coord.dims}")

                # Show coordinate attributes
                if coord.attrs:
                    print(f"      Attributes:")
                    for attr_key, attr_val in coord.attrs.items():
                        print(f"         {attr_key}: {attr_val}")

                # Show sample values for small coordinates, or min/max for large ones
                if coord.size <= 10:
                    print(f"      Values: {coord.values}")
                else:
                    try:
                        min_val = float(coord.min().values)
                        max_val = float(coord.max().values)
                        print(f"      Range: {min_val} to {max_val}")
                        print(f"      First few: {coord.values[:3]}")
                        print(f"      Last few: {coord.values[-3:]}")
                    except:
                        print(f"      First value: {coord.values[0]}")
                        print(f"      Last value: {coord.values[-1]}")
                print()

            # Data variables
            print("\n📊 DATA VARIABLES:")
            for var_name, var in ds.data_vars.items():
                print(f"   {var_name}:")
                print(f"      Shape: {var.shape}")
                print(f"      Dtype: {var.dtype}")
                print(f"      Dims: {var.dims}")

                # Show variable attributes
                if var.attrs:
                    print(f"      Attributes:")
                    for attr_key, attr_val in var.attrs.items():
                        print(f"         {attr_key}: {attr_val}")

                # Show data statistics if possible
                try:
                    if var.size > 0:
                        min_val = float(var.min().values)
                        max_val = float(var.max().values)
                        mean_val = float(var.mean().values)
                        print(f"      Data range: {min_val:.4f} to {max_val:.4f}")
                        print(f"      Mean: {mean_val:.4f}")
                except Exception as e:
                    print(f"      Could not compute statistics: {e}")
                print()

            # Try to extract spatial coverage
            print("\n🌐 SPATIAL COVERAGE:")
            lat_names = ['lat', 'latitude', 'y', 'Y', 'XLAT']
            lon_names = ['lon', 'longitude', 'x', 'X', 'XLONG']

            lat_coord = None
            lon_coord = None

            for name in lat_names:
                if name in ds.coords:
                    lat_coord = ds.coords[name]
                    break

            for name in lon_names:
                if name in ds.coords:
                    lon_coord = ds.coords[name]
                    break

            if lat_coord is not None and lon_coord is not None:
                try:
                    lat_min = float(lat_coord.min().values)
                    lat_max = float(lat_coord.max().values)
                    lon_min = float(lon_coord.min().values)
                    lon_max = float(lon_coord.max().values)

                    print(f"   Latitude range: {lat_min} to {lat_max}")
                    print(f"   Longitude range: {lon_min} to {lon_max}")
                    print(f"   Bounding box: [{lon_min}, {lat_min}, {lon_max}, {lat_max}]")
                except Exception as e:
                    print(f"   Could not extract spatial bounds: {e}")
            else:
                print("   No recognizable spatial coordinates found")
                print(f"   Available coordinates: {list(ds.coords.keys())}")

            # Try to extract temporal coverage
            print("\n⏰ TEMPORAL COVERAGE:")
            time_names = ['time', 'Time', 'TIME', 't', 'T']

            time_coord = None
            for name in time_names:
                if name in ds.coords:
                    time_coord = ds.coords[name]
                    break

            if time_coord is not None:
                try:
                    print(f"   Time coordinate: {time_coord.name}")
                    print(f"   Time shape: {time_coord.shape}")
                    print(f"   Time dtype: {time_coord.dtype}")

                    if time_coord.attrs:
                        print(f"   Time attributes:")
                        for attr_key, attr_val in time_coord.attrs.items():
                            print(f"      {attr_key}: {attr_val}")

                    # Try different datetime conversion methods
                    try:
                        import pandas as pd
                        times = pd.to_datetime(time_coord.values)
                        start_time = times.min()
                        end_time = times.max()
                        print(f"   Time range (pandas): {start_time} to {end_time}")
                    except Exception as e1:
                        print(f"   Pandas conversion failed: {e1}")
                        try:
                            start_time = time_coord.values[0]
                            end_time = time_coord.values[-1]
                            print(f"   Time range (raw): {start_time} to {end_time}")
                        except Exception as e2:
                            print(f"   Could not extract time range: {e2}")

                    # Show some sample time values
                    if time_coord.size <= 10:
                        print(f"   Time values: {time_coord.values}")
                    else:
                        print(f"   First time: {time_coord.values[0]}")
                        print(f"   Last time: {time_coord.values[-1]}")
                        print(f"   Total time steps: {time_coord.size}")

                except Exception as e:
                    print(f"   Error processing time coordinate: {e}")
            else:
                print("   No recognizable time coordinate found")
                print(f"   Available coordinates: {list(ds.coords.keys())}")

            # Filename parsing test
            print("\n🏷️ FILENAME PARSING TEST:")
            filename = Path(netcdf_path).stem
            print(f"   Filename (no extension): {filename}")

            import re

            # Test the regex patterns
            print("   Testing regex patterns:")

            # Pattern 1: Standard climate model format
            pattern1 = re.match(r'^([^_]+(?:-[^_]+)*)_([^_]+)_([^_]+)_([^_]+)_(\d{4})$', filename)
            if pattern1:
                model, scenario, variable, resolution, year = pattern1.groups()
                print(f"   ✅ Pattern 1 matched:")
                print(f"      Model: {model}")
                print(f"      Scenario: {scenario}")
                print(f"      Variable: {variable}")
                print(f"      Resolution: {resolution}")
                print(f"      Year: {year}")
            else:
                print(f"   ❌ Pattern 1 did not match")

            # Pattern 2: Try splitting on underscores
            parts = filename.split('_')
            print(f"   Filename parts (split by '_'): {parts}")

            # Look for year patterns
            year_matches = re.findall(r'\b(19|20)\d{2}\b', filename)
            print(f"   Found years in filename: {year_matches}")

            # Look for known scenarios
            scenarios = ['ssp126', 'ssp245', 'ssp370', 'ssp585', 'rcp26', 'rcp45', 'rcp85']
            found_scenarios = [s for s in scenarios if s.lower() in filename.lower()]
            print(f"   Found scenarios: {found_scenarios}")

            # Look for known variables
            variables = ['rsds', 'tasmin', 'tasmax', 'tas', 'pr', 'huss', 'sfcwind']
            found_variables = [v for v in variables if v.lower() in filename.lower()]
            print(f"   Found variables: {found_variables}")

            print("\n" + "=" * 80)
            print("✅ Inspection complete!")

    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("Please install required packages:")
        print("pip install xarray netcdf4 pandas numpy")
    except Exception as e:
        print(f"❌ Error inspecting file: {e}")
        import traceback
        traceback.print_exc()

def main():
    if len(sys.argv) != 2:
        print("Usage: python inspect_netcdf.py <path_to_netcdf_file>")
        print("Example: python inspect_netcdf.py ./EC-Earth3/ssp245/day/rsds/EC-Earth3_ssp245_rsds_1km_2018.nc")
        sys.exit(1)

    netcdf_path = Path(sys.argv[1])

    if not netcdf_path.exists():
        print(f"❌ File not found: {netcdf_path}")
        sys.exit(1)

    if not netcdf_path.suffix.lower() in ['.nc', '.netcdf', '.nc4']:
        print(f"⚠️ Warning: File doesn't have a typical NetCDF extension: {netcdf_path.suffix}")

    inspect_netcdf_file(netcdf_path)

if __name__ == "__main__":
    main()