import sys
import json
import os
from pathlib import Path
import xarray as xr
import numpy as np
from shapely.geometry import box, mapping
import requests
from tapipy.tapis import Tapis
from datetime import datetime

CKAN_URL = "https://ckan.tacc.utexas.edu"
TACC_BASE_URL = "https://ptdatax.tacc.utexas.edu/workbench/data/tapis/projects/ptdatax.project.PTDATAX-207/SETx_Climate_Datasets/"

def authenticate_upstream():
    # Placeholder or external auth, no-op here
    print("✅ Upstream authentication skipped or done externally.")

def get_tapis_token(credentials):
    t = Tapis(base_url="https://portals.tapis.io",
              username=credentials['username'],
              password=credentials['password'])
    t.get_tokens()
    print("✅ Tapis authentication successful!")
    return t.access_token.access_token

def get_headers(jwt_token):
    return {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }

def dataset_exists(jwt_token, dataset_name, ckan_url=CKAN_URL):
    url = f"{ckan_url}/api/3/action/package_show?id={dataset_name}"
    headers = get_headers(jwt_token)
    response = requests.get(url, headers=headers)
    print(f"   🔍 Dataset check status: {response.status_code}")
    if response.status_code == 200:
        return True, response.json()['result']
    elif response.status_code == 404:
        return False, None
    elif response.status_code == 403:
        print(f"   ⚠️ Access denied (403) - you may not have permission to view this dataset")
        return False, None
    else:
        print(f"   ⚠️ Unexpected status code {response.status_code}: {response.text}")
        return False, None

def create_dataset(jwt_token, dataset_dict, ckan_url=CKAN_URL):
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    url = f"{ckan_url}/api/3/action/package_create"
    print("Dataset data:", dataset_dict)

    try:
        response = requests.post(url, json=dataset_dict, headers=headers)
        print(f"   📡 Create dataset status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"   ✅ Dataset created: {result['result']['id']}")
                return result["result"]
            else:
                print(f"   ❌ CKAN API returned success=False: {result}")
                return None
        else:
            response.raise_for_status()

    except requests.HTTPError as e:
        print(f"   ❌ HTTP Error {e.response.status_code}")
        print(f"   📄 Response text: {e.response.text}")

        if e.response.status_code == 409:
            print(f"   ⚠️ Checking if dataset actually exists...")
            exists, existing_dataset = dataset_exists(jwt_token, dataset_dict['name'], ckan_url)
            if exists and existing_dataset:
                print(f"   ✅ Retrieved existing dataset: {existing_dataset['id']}")
                return existing_dataset
            print(f"   ❌ Could not retrieve existing dataset after 409 error")
            return None
        else:
            raise

def create_resource_by_url(jwt_token, dataset_id, resource_dict, ckan_url=CKAN_URL):
    """Create a resource that references a file by URL (no upload)."""
    api_url = f"{ckan_url}/api/3/action/resource_create"

    resource_data = {
        "package_id": dataset_id,
        "url": resource_dict["url"],
        "name": resource_dict.get("name", "NetCDF Resource"),
        "format": resource_dict.get("format", "NetCDF"),
        "description": resource_dict.get("description", "")
    }

    print(f"📎 Adding resource by URL: {resource_dict.get('name')} ({resource_dict['url']})")
    try:
        response = requests.post(api_url, json=resource_data, headers=get_headers(jwt_token))
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            print(f"   ✅ Resource added by URL: {result['result']['id']}")
            return result["result"]
        else:
            print(f"   ❌ Failed to add resource by URL: {result}")
            return None
    except Exception as e:
        print(f"   ❌ Error adding resource by URL: {e}")
        return None

def find_netcdf_files(directory):
    """Recursively find all NetCDF files in directory and subdirectories."""
    netcdf_extensions = ['.nc', '.netcdf', '.nc4']
    netcdf_files = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in netcdf_extensions):
                netcdf_files.append(Path(root) / file)

    return netcdf_files

def organize_netcdf_by_hierarchy(netcdf_files):
    """Organize NetCDF files by model/scenario/frequency/variable hierarchy using filename patterns."""
    hierarchy = {}
    import re

    for file_path in netcdf_files:
        filename = file_path.stem  # filename without extension

        # Try multiple filename patterns
        hierarchy_info = None

        # Pattern 1: EC-Earth3_ssp245_rsds_1km_2018 or BCC-CSM2-MR_ssp126_huss_1km_2015
        # Handle model names with hyphens by being more flexible
        pattern1 = re.match(r'^([^_]+(?:-[^_]+)*)_([^_]+)_([^_]+)_([^_]+)_(\d{4})$', filename)
        if pattern1:
            model, scenario, variable, resolution, year = pattern1.groups()
            # Infer frequency from directory or assume 'day' for climate data
            frequency = 'day'  # Default assumption for climate model data
            if 'day' in str(file_path):
                frequency = 'day'
            elif 'mon' in str(file_path):
                frequency = 'mon'
            elif 'year' in str(file_path):
                frequency = 'year'

            hierarchy_info = (model, scenario, frequency, variable)

        # Pattern 2: Try directory-based parsing as fallback
        if not hierarchy_info:
            parts = file_path.parts
            if len(parts) >= 4:
                # Work backwards: .../model/scenario/frequency/variable/file.nc
                variable = parts[-2]  # directory containing the file
                frequency = parts[-3]
                scenario = parts[-4]
                model = parts[-5]
                hierarchy_info = (model, scenario, frequency, variable)

        # Pattern 3: More flexible filename pattern (handle variations)
        if not hierarchy_info:
            # Try to extract components from filename using common separators
            parts = re.split(r'[_\-\.]', filename)
            if len(parts) >= 4:
                # Look for known patterns in the parts
                model = parts[0] if parts[0] else 'unknown'
                scenario = next((p for p in parts if p.lower() in ['ssp245', 'ssp126', 'ssp370', 'ssp585', 'rcp26', 'rcp45', 'rcp85']), 'unknown')
                variable = next((p for p in parts if p.lower() in ['rsds', 'tasmin', 'tasmax', 'tas', 'pr', 'huss', 'sfcwind']), 'unknown')
                frequency = 'day'  # Default
                hierarchy_info = (model, scenario, frequency, variable)

        # Use filename as fallback if no pattern matches
        if not hierarchy_info:
            hierarchy_info = ('unknown', 'unknown', 'unknown', filename)
            print(f"⚠️ Could not parse hierarchy from {filename}, using filename as variable")

        # Create hierarchical key
        if hierarchy_info not in hierarchy:
            hierarchy[hierarchy_info] = []
        hierarchy[hierarchy_info].append(file_path)

    return hierarchy

def extract_netcdf_metadata(netcdf_path):
    """Extract metadata from a NetCDF file."""
    try:
        with xr.open_dataset(netcdf_path) as ds:
            metadata = {}

            # Global attributes
            global_attrs = dict(ds.attrs)
            metadata['global_attributes'] = global_attrs

            # Title and description
            metadata['title'] = global_attrs.get('title', f"NetCDF: {netcdf_path.name}")
            metadata['description'] = global_attrs.get('description',
                                                     global_attrs.get('abstract',
                                                     global_attrs.get('summary',
                                                     f"NetCDF dataset from {netcdf_path.name}")))

            # Author information
            metadata['author'] = global_attrs.get('creator_name', global_attrs.get('author', ''))
            metadata['author_email'] = global_attrs.get('creator_email', global_attrs.get('contact', ''))
            metadata['institution'] = global_attrs.get('institution', '')

            # Version and source
            metadata['version'] = global_attrs.get('version', global_attrs.get('source_version', ''))
            metadata['source'] = global_attrs.get('source', f"NetCDF file: {netcdf_path.name}")

            # Variables information
            variables = {}
            for var_name, var in ds.data_vars.items():
                variables[var_name] = {
                    'dimensions': list(var.dims),
                    'shape': list(var.shape),
                    'dtype': str(var.dtype),
                    'attributes': dict(var.attrs)
                }
            metadata['variables'] = variables

            # Coordinate information
            coordinates = {}
            for coord_name, coord in ds.coords.items():
                coordinates[coord_name] = {
                    'dimensions': list(coord.dims),
                    'shape': list(coord.shape),
                    'dtype': str(coord.dtype),
                    'attributes': dict(coord.attrs)
                }
            metadata['coordinates'] = coordinates

            # Spatial coverage
            spatial_coverage = extract_spatial_coverage(ds)
            if spatial_coverage:
                metadata['spatial_coverage'] = spatial_coverage

            # Temporal coverage
            temporal_coverage = extract_temporal_coverage(ds)
            if temporal_coverage:
                metadata['temporal_coverage_start'] = temporal_coverage.get('start')
                metadata['temporal_coverage_end'] = temporal_coverage.get('end')

            # File information
            metadata['file_size'] = os.path.getsize(netcdf_path)
            metadata['file_path'] = str(netcdf_path)

            return metadata

    except Exception as e:
        print(f"⚠️ Error extracting metadata from {netcdf_path}: {e}")
        return None

def extract_spatial_coverage(dataset):
    """Extract spatial coverage from NetCDF dataset."""
    try:
        # Look for common coordinate names
        lat_names = ['lat', 'latitude', 'y', 'Y', 'XLAT']
        lon_names = ['lon', 'longitude', 'x', 'X', 'XLONG']

        lat_coord = None
        lon_coord = None

        # Find latitude coordinate
        for name in lat_names:
            if name in dataset.coords:
                lat_coord = dataset.coords[name]
                break

        # Find longitude coordinate
        for name in lon_names:
            if name in dataset.coords:
                lon_coord = dataset.coords[name]
                break

        if lat_coord is not None and lon_coord is not None:
            # Get bounds
            lat_min = float(lat_coord.min().values)
            lat_max = float(lat_coord.max().values)
            lon_min = float(lon_coord.min().values)
            lon_max = float(lon_coord.max().values)

            # Create bounding box
            bbox_geom = box(lon_min, lat_min, lon_max, lat_max)
            geojson_geom = mapping(bbox_geom)

            return json.dumps(geojson_geom)
        else:
            return None

    except Exception as e:
        print(f"⚠️ Error extracting spatial coverage: {e}")
        return None

def extract_temporal_coverage(dataset):
    """Extract temporal coverage from NetCDF dataset."""
    try:
        # Look for common time coordinate names
        time_names = ['time', 'Time', 'TIME', 't', 'T']

        time_coord = None
        for name in time_names:
            if name in dataset.coords:
                time_coord = dataset.coords[name]
                break

        if time_coord is not None:
            try:
                # Check if we have cftime objects
                first_time = time_coord.values[0]
                if hasattr(first_time, 'strftime'):
                    # cftime objects - convert directly
                    start_time = time_coord.values[0]
                    end_time = time_coord.values[-1]
                    start_str = start_time.strftime('%Y-%m-%d')
                    end_str = end_time.strftime('%Y-%m-%d')
                else:
                    # Try pandas conversion for standard datetime
                    import pandas as pd
                    times = pd.to_datetime(time_coord.values)
                    start_time = times.min()
                    end_time = times.max()

                    # Convert to ISO format strings
                    if hasattr(start_time, 'isoformat'):
                        start_str = start_time.isoformat()
                        end_str = end_time.isoformat()
                    else:
                        start_str = str(start_time)
                        end_str = str(end_time)

            except Exception as e:
                print(f"   ⚠️ Datetime conversion failed: {e}, trying alternative method")
                try:
                    # Fallback: use xarray's native datetime handling
                    times = time_coord
                    start_time = times.min().values
                    end_time = times.max().values

                    # Handle different datetime types
                    if hasattr(start_time, 'strftime'):
                        # cftime object
                        start_str = start_time.strftime('%Y-%m-%d')
                        end_str = end_time.strftime('%Y-%m-%d')
                    elif hasattr(start_time, 'astype'):
                        # numpy datetime64
                        start_str = str(start_time.astype('datetime64[D]'))
                        end_str = str(end_time.astype('datetime64[D]'))
                    else:
                        start_str = str(start_time)
                        end_str = str(end_time)

                except Exception as e2:
                    print(f"   ⚠️ Alternative datetime conversion also failed: {e2}")
                    # Last resort: use raw values
                    start_str = str(time_coord.values[0])
                    end_str = str(time_coord.values[-1])

            return {
                'start': start_str,
                'end': end_str
            }
        else:
            return None

    except Exception as e:
        print(f"⚠️ Error extracting temporal coverage: {e}")
        return None

def create_dataset_from_netcdf_collection(hierarchy_key, netcdf_files, config_data):
    """Create CKAN dataset dictionary from a collection of NetCDF files organized by hierarchy."""

    model, scenario, frequency, variable = hierarchy_key

    # Generate dataset name from hierarchy
    dataset_name = f"{config_data.get('dataset_name_prefix', 'climate')}_{model.lower()}_{scenario}_{frequency}_{variable}"
    dataset_name = dataset_name.replace('-', '_').replace(' ', '_')

    # Extract metadata from the first file to get common attributes
    first_file_metadata = extract_netcdf_metadata(netcdf_files[0])
    if not first_file_metadata:
        return None

    # Get years from all files in the collection (from filenames, not file content)
    years = []
    total_file_size = 0
    temporal_start = None
    temporal_end = None

    import re
    for file_path in netcdf_files:
        # Extract year from filename (assumes format like *_YYYY.nc)
        filename = file_path.stem

        # Debug: print what we're trying to parse
        print(f"   🔍 Extracting year from: {filename}")

        # Try the same pattern as in hierarchy organization
        pattern1 = re.match(r'^([^_]+(?:-[^_]+)*)_([^_]+)_([^_]+)_([^_]+)_(\d{4})$', filename)
        if pattern1:
            year = int(pattern1.group(5))
            years.append(year)
            print(f"   ✅ Extracted year: {year}")
        else:
            # Fallback: Look for 4-digit year in filename
            year_matches = re.findall(r'\b(19|20)\d{2}\b', filename)
            if year_matches:
                year = int(year_matches[-1])
                years.append(year)
                print(f"   ✅ Found year (fallback): {year}")
            else:
                print(f"   ❌ No year found in: {filename}")

        # Accumulate file sizes
        if file_path.exists():
            total_file_size += os.path.getsize(file_path)

    # Only read temporal coverage from first and last files (by year) for efficiency
    if years:
        years.sort()
        min_year = min(years)
        max_year = max(years)

        # Find files corresponding to min and max years
        first_file = None
        last_file = None

        for file_path in netcdf_files:
            filename = file_path.stem
            year_matches = re.findall(r'\b(19|20)\d{2}\b', filename)
            if year_matches:
                year = int(year_matches[-1])
                if year == min_year and not first_file:
                    first_file = file_path
                if year == max_year:
                    last_file = file_path

        # Extract temporal coverage from first file
        first_metadata = None
        if first_file:
            print(f"   📅 Reading temporal coverage from first file: {first_file.name}")
            first_metadata = extract_netcdf_metadata(first_file)
            if first_metadata and first_metadata.get('temporal_coverage_start'):
                temporal_start = first_metadata['temporal_coverage_start']

        # Extract temporal coverage from last file (if different from first)
        if last_file and last_file != first_file:
            print(f"   📅 Reading temporal coverage from last file: {last_file.name}")
            last_metadata = extract_netcdf_metadata(last_file)
            if last_metadata and last_metadata.get('temporal_coverage_end'):
                temporal_end = last_metadata['temporal_coverage_end']
        elif last_file == first_file and first_metadata:
            # Same file, use end time from first file
            temporal_end = first_metadata.get('temporal_coverage_end')

    years.sort()
    year_range = f"{min(years)}-{max(years)}" if years else "unknown"

    # Create extras from metadata
    extras = []

    # Add hierarchy information
    extras.append({"key": "climate_model", "value": model})
    extras.append({"key": "scenario", "value": scenario})
    extras.append({"key": "frequency", "value": frequency})
    extras.append({"key": "variable", "value": variable})
    extras.append({"key": "temporal_range", "value": year_range})
    extras.append({"key": "number_of_files", "value": str(len(netcdf_files))})
    extras.append({"key": "total_size_bytes", "value": str(total_file_size)})
    extras.append({"key": "file_format", "value": "NetCDF"})

    if years:
        extras.append({"key": "years_available", "value": ", ".join(map(str, sorted(years)))})

    # Get global attributes early
    global_attrs = first_file_metadata.get('global_attributes', {})

    # Add important global attributes as structured extras
    important_attrs = {
        'activity': 'Activity',
        'institution': 'Institution',
        'cmip6_source_id': 'CMIP6 Source ID',
        'cmip6_institution_id': 'CMIP6 Institution ID',
        'cmip6_license': 'CMIP6 License',
        'variant_label': 'Variant Label',
        'resolution_id': 'Resolution',
        'realm': 'Realm',
        'tracking_id': 'Tracking ID',
        'creation_date': 'Creation Date',
        'external_variables': 'External Variables',
        'Conventions': 'CF Conventions'
    }

    for attr_key, display_name in important_attrs.items():
        if global_attrs.get(attr_key):
            extras.append({"key": display_name.lower().replace(' ', '_'), "value": str(global_attrs[attr_key])})

    # Add other global attributes with netcdf_ prefix (for less important ones)
    skip_attrs = set(important_attrs.keys()) | {'contact', 'doi', 'version', 'disclaimer', 'references', 'history', 'title', 'source'}
    for key, value in global_attrs.items():
        if key not in skip_attrs and key and value and isinstance(value, (str, int, float)):
            extras.append({"key": f"netcdf_{key}", "value": str(value)})

    # Add variables information from first file
    if first_file_metadata.get('variables'):
        var_names = list(first_file_metadata['variables'].keys())
        extras.append({"key": "data_variables", "value": ", ".join(var_names)})

    # Create human-readable variable name
    variable_display_names = {
        'rsds': 'Surface Downwelling Shortwave Radiation',
        'tasmin': 'Daily Minimum Near-Surface Air Temperature',
        'tasmax': 'Daily Maximum Near-Surface Air Temperature',
        'tas': 'Near-Surface Air Temperature',
        'pr': 'Precipitation',
        'huss': 'Near-Surface Specific Humidity',
        'sfcwind': 'Near-Surface Wind Speed',
        'rsus': 'Surface Upwelling Shortwave Radiation',
        'rlds': 'Surface Downwelling Longwave Radiation',
        'rlus': 'Surface Upwelling Longwave Radiation'
    }

    variable_display = variable_display_names.get(variable, variable.upper())

    # Create human-readable frequency name
    frequency_display_names = {
        'day': 'daily',
        'mon': 'monthly',
        'year': 'yearly',
        'daily': 'daily',
        'monthly': 'monthly',
        'yearly': 'yearly'
    }
    frequency_display = frequency_display_names.get(frequency, frequency)

    # Build comprehensive description
    description_parts = []

    # Basic description
    description_parts.append(f"{variable_display} data from {model} climate model under {scenario.upper()} scenario. {frequency_display.title()} frequency data covering years {year_range}. This dataset contains {len(netcdf_files)} NetCDF files, one for each year.")

    # Add variable details from NetCDF metadata
    if first_file_metadata.get('variables', {}).get(variable, {}).get('attributes', {}).get('comment'):
        var_comment = first_file_metadata['variables'][variable]['attributes']['comment']
        description_parts.append(f"\n\nVariable Details: {var_comment}")
    elif first_file_metadata.get('variables', {}).get(variable, {}).get('attributes', {}).get('long_name'):
        var_long_name = first_file_metadata['variables'][variable]['attributes']['long_name']
        description_parts.append(f"\n\nVariable: {var_long_name}")

    # Add disclaimer if present
    if global_attrs.get('disclaimer'):
        description_parts.append(f"\n\nDisclaimer: {global_attrs['disclaimer']}")

    # Add references if present
    if global_attrs.get('references'):
        description_parts.append(f"\n\nReferences: {global_attrs['references']}")

    # Add processing history if present
    if global_attrs.get('history'):
        description_parts.append(f"\n\nProcessing History: {global_attrs['history']}")

    dataset = {
        "name": dataset_name,
        "title": f"{model} {scenario.upper()} {variable_display} ({frequency_display}) - {year_range}",
        "notes": "".join(description_parts),
        "owner_org": config_data.get("owner_org"),
        "extras": extras
    }

    # global_attrs already defined above

    # Parse contact field for author and maintainer
    contact = global_attrs.get('contact', '')
    if contact:
        # Parse contact like "Dr. Geeta Persad: geeta.persad@jsg.utexas.edu, Dr. Ifeanyichukwu Nduka: icnduka@jsg.utexas.edu"
        import re
        contact_parts = contact.split(',')
        if len(contact_parts) >= 1:
            # Extract first contact as author
            first_contact = contact_parts[0].strip()
            author_match = re.match(r'^([^:]+):\s*(.+)$', first_contact)
            if author_match:
                dataset["author"] = author_match.group(1).strip()
                dataset["author_email"] = author_match.group(2).strip()
        if len(contact_parts) >= 2:
            # Extract second contact as maintainer
            second_contact = contact_parts[1].strip()
            maintainer_match = re.match(r'^([^:]+):\s*(.+)$', second_contact)
            if maintainer_match:
                dataset["maintainer"] = maintainer_match.group(1).strip()
                dataset["maintainer_email"] = maintainer_match.group(2).strip()

    # Use DOI as source if available
    if global_attrs.get('doi'):
        dataset["source"] = global_attrs['doi']
    elif first_file_metadata.get('source'):
        dataset["source"] = first_file_metadata['source']

    # Use version from global attributes
    if global_attrs.get('version'):
        dataset["version"] = global_attrs['version']
    elif first_file_metadata.get('version'):
        dataset["version"] = first_file_metadata['version']

    # Add spatial coverage from first file if available
    if first_file_metadata.get('spatial_coverage'):
        dataset["spatial"] = first_file_metadata['spatial_coverage']

    # Add temporal coverage from aggregated data
    if temporal_start:
        dataset["temporal_coverage_start"] = temporal_start
    if temporal_end:
        dataset["temporal_coverage_end"] = temporal_end

    # Add any additional fields from config
    for field in ['license_id', 'private', 'url']:
        if config_data.get(field):
            dataset[field] = config_data[field]

    # Handle tags - add climate-specific tags
    climate_tags = ["netcdf", "climate", "scientific-data", model.lower(), scenario, variable]
    user_tags = config_data.get("tags", [])
    all_tags = list(set(climate_tags + user_tags))

    if isinstance(all_tags[0], str):
        dataset["tags"] = [{"name": tag} for tag in all_tags]
    else:
        dataset["tags"] = all_tags

    return dataset

def create_dataset_from_netcdf(netcdf_metadata, config_data):
    """Create CKAN dataset dictionary from NetCDF metadata (legacy function for single files)."""

    # Generate dataset name from file path
    file_path = Path(netcdf_metadata['file_path'])
    dataset_name = config_data.get('dataset_name_prefix', 'netcdf') + '_' + file_path.stem.lower().replace(' ', '_')

    # Create extras from metadata
    extras = []

    # Add global attributes as extras
    for key, value in netcdf_metadata.get('global_attributes', {}).items():
        if key and value and isinstance(value, (str, int, float)):
            extras.append({"key": f"netcdf_{key}", "value": str(value)})

    # Add variables information
    if netcdf_metadata.get('variables'):
        var_names = list(netcdf_metadata['variables'].keys())
        extras.append({"key": "variables", "value": ", ".join(var_names)})

    # Add file information
    extras.append({"key": "file_size_bytes", "value": str(netcdf_metadata['file_size'])})
    extras.append({"key": "file_format", "value": "NetCDF"})

    # Filter out core fields that should go in main dataset dict
    core_fields = {
        'author', 'author_email', 'maintainer', 'maintainer_email',
        'version', 'source', 'institution'
    }

    dataset = {
        "name": dataset_name,
        "title": netcdf_metadata.get('title', f"NetCDF Dataset: {file_path.name}"),
        "notes": netcdf_metadata.get('description', "NetCDF dataset uploaded via automated script"),
        "owner_org": config_data.get("owner_org"),
        "extras": extras
    }

    # Add core fields from metadata
    if netcdf_metadata.get('author'):
        dataset["author"] = netcdf_metadata['author']
    if netcdf_metadata.get('author_email'):
        dataset["author_email"] = netcdf_metadata['author_email']
    if netcdf_metadata.get('version'):
        dataset["version"] = netcdf_metadata['version']
    if netcdf_metadata.get('source'):
        dataset["source"] = netcdf_metadata['source']

    # Add spatial coverage if available
    if netcdf_metadata.get('spatial_coverage'):
        dataset["spatial"] = netcdf_metadata['spatial_coverage']

    # Add temporal coverage if available
    if netcdf_metadata.get('temporal_coverage_start'):
        dataset["temporal_coverage_start"] = netcdf_metadata['temporal_coverage_start']
    if netcdf_metadata.get('temporal_coverage_end'):
        dataset["temporal_coverage_end"] = netcdf_metadata['temporal_coverage_end']

    # Add any additional fields from config
    for field in ['license_id', 'private', 'url']:
        if config_data.get(field):
            dataset[field] = config_data[field]

    # Handle tags
    tags = config_data.get("tags", ["netcdf", "scientific-data"])
    if tags:
        if isinstance(tags[0], str):
            dataset["tags"] = [{"name": tag} for tag in tags]
        else:
            dataset["tags"] = tags

    return dataset

def main(config_path):
    with open(config_path) as f:
        data = json.load(f)

    credentials = {
        "username": data.get("username"),
        "password": data.get("password")
    }
    if not credentials["username"] or not credentials["password"]:
        print("❌ Missing username or password in config.json")
        sys.exit(1)

    authenticate_upstream()
    jwt_token = get_tapis_token(credentials)

    # Get directory to search for NetCDF files
    search_directory = data.get("netcdf_directory", ".")
    if not os.path.exists(search_directory):
        print(f"❌ Directory {search_directory} does not exist")
        sys.exit(1)

    print(f"🔍 Searching for NetCDF files in {search_directory}")
    netcdf_files = find_netcdf_files(search_directory)

    if not netcdf_files:
        print(f"⚠️ No NetCDF files found in {search_directory}")
        return

    print(f"📁 Found {len(netcdf_files)} NetCDF files")

    # Organize files by hierarchy
    print("🏗️ Organizing files by model/scenario/frequency/variable hierarchy...")
    hierarchy = organize_netcdf_by_hierarchy(netcdf_files)

    print(f"📊 Found {len(hierarchy)} dataset groups:")
    for (model, scenario, frequency, variable), files in hierarchy.items():
        print(f"   • {model}/{scenario}/{frequency}/{variable}: {len(files)} files")

    # Check if user wants hierarchical organization
    use_hierarchical = data.get("use_hierarchical_datasets", True)

    if use_hierarchical and hierarchy:
        # Process each group as a single dataset
        for hierarchy_key, file_group in hierarchy.items():
            model, scenario, frequency, variable = hierarchy_key
            print(f"\n📊 Processing dataset group: {model}/{scenario}/{frequency}/{variable} ({len(file_group)} files)")

            # Create dataset from collection
            dataset = create_dataset_from_netcdf_collection(hierarchy_key, file_group, data)
            if not dataset:
                print(f"   ⚠️ Skipping group due to metadata extraction error")
                continue

            print(f"📦 Checking if dataset '{dataset['name']}' exists...")
            exists, existing_dataset = dataset_exists(jwt_token, dataset['name'], CKAN_URL)

            if exists:
                print(f"⚠️ Dataset '{dataset['name']}' already exists, updating...")
                # Update existing dataset
                update_data = dataset.copy()
                update_data['id'] = existing_dataset['id']

                update_url = f"{CKAN_URL}/api/3/action/package_update"
                try:
                    response = requests.post(update_url, json=update_data, headers=get_headers(jwt_token))
                    response.raise_for_status()
                    result = response.json()
                    if result.get("success"):
                        print(f"   ✅ Dataset updated: {result['result']['id']}")
                        pkg = result["result"]
                    else:
                        print(f"   ❌ Dataset update failed: {result}")
                        continue
                except Exception as e:
                    print(f"   ❌ Error updating dataset: {e}")
                    continue
            else:
                print(f"📦 Creating dataset: {dataset['name']}")
                pkg = create_dataset(jwt_token, dataset, CKAN_URL)
                if not pkg:
                    print(f"   ❌ Dataset creation failed for group {hierarchy_key}")
                    continue

            print(f"✅ Dataset ready with ID: {pkg['id']}")

            # Create resources for each file in the group
            print(f"📤 Adding {len(file_group)} NetCDF resource references...")
            for netcdf_path in file_group:
                # Construct URL using hierarchical structure: model/scenario/frequency/variable/filename
                filename = netcdf_path.name
                resource_url = f"{TACC_BASE_URL}{model}/{scenario}/{frequency}/{variable}/{filename}"

                # Extract year from filename for resource naming
                import re
                filename = netcdf_path.stem

                # Try multiple patterns to extract year
                year = "unknown"

                # Debug: print the filename we're trying to parse
                print(f"   🔍 Parsing filename: {filename}")

                # Pattern 1: Standard climate format (model_scenario_variable_resolution_year)
                pattern1 = re.match(r'^([^_]+(?:-[^_]+)*)_([^_]+)_([^_]+)_([^_]+)_(\d{4})$', filename)
                if pattern1:
                    year = pattern1.group(5)  # The year is the 5th group
                    print(f"   ✅ Pattern 1 matched, year: {year}")
                else:
                    print(f"   ❌ Pattern 1 failed")
                    # Pattern 2: Look for any 4-digit year in the filename
                    year_matches = re.findall(r'\b(19|20)\d{2}\b', filename)
                    if year_matches:
                        year = year_matches[-1]  # Take the last found year
                        print(f"   ✅ Pattern 2 found year: {year}")
                    else:
                        print(f"   ❌ No year found in filename")

                # Get display name for variable
                variable_display_names = {
                    'rsds': 'Surface Downwelling Shortwave Radiation',
                    'tasmin': 'Daily Minimum Near-Surface Air Temperature',
                    'tasmax': 'Daily Maximum Near-Surface Air Temperature',
                    'tas': 'Near-Surface Air Temperature',
                    'pr': 'Precipitation'
                }

                resource = {
                    "url": resource_url,
                    "name": f"{variable.upper()} {year} - NetCDF",
                    "format": "NetCDF",
                    "description": f"{variable_display_names.get(variable, variable)} data for year {year} from {model} model under {scenario} scenario"
                }

                create_resource_by_url(jwt_token, pkg["id"], resource, CKAN_URL)

    else:
        # Process each NetCDF file individually (original behavior)
        print("📊 Processing files individually...")
        for netcdf_path in netcdf_files:
            print(f"\n📊 Processing {netcdf_path}")

            # Extract metadata
            metadata = extract_netcdf_metadata(netcdf_path)
            if not metadata:
                print(f"   ⚠️ Skipping {netcdf_path} due to metadata extraction error")
                continue

            # Create dataset
            dataset = create_dataset_from_netcdf(metadata, data)

            print(f"📦 Checking if dataset '{dataset['name']}' exists...")
            exists, existing_dataset = dataset_exists(jwt_token, dataset['name'], CKAN_URL)

            if exists:
                print(f"⚠️ Dataset '{dataset['name']}' already exists, updating...")
                # Update existing dataset
                update_data = dataset.copy()
                update_data['id'] = existing_dataset['id']

                update_url = f"{CKAN_URL}/api/3/action/package_update"
                try:
                    response = requests.post(update_url, json=update_data, headers=get_headers(jwt_token))
                    response.raise_for_status()
                    result = response.json()
                    if result.get("success"):
                        print(f"   ✅ Dataset updated: {result['result']['id']}")
                        pkg = result["result"]
                    else:
                        print(f"   ❌ Dataset update failed: {result}")
                        continue
                except Exception as e:
                    print(f"   ❌ Error updating dataset: {e}")
                    continue
            else:
                print(f"📦 Creating dataset: {dataset['name']}")
                pkg = create_dataset(jwt_token, dataset, CKAN_URL)
                if not pkg:
                    print(f"   ❌ Dataset creation failed for {netcdf_path}")
                    continue

            print(f"✅ Dataset ready with ID: {pkg['id']}")

            # Create resource reference to the NetCDF file
            # Try to extract hierarchy from path for URL construction
            filename = netcdf_path.name
            relative_path = netcdf_path.relative_to(search_directory)

            # Try to construct hierarchical URL if possible
            path_parts = relative_path.parts
            if len(path_parts) >= 4:
                # Assume structure: model/scenario/frequency/variable/filename
                model_dir, scenario_dir, freq_dir, var_dir = path_parts[-5:-1] if len(path_parts) >= 5 else path_parts[-4:]
                resource_url = f"{TACC_BASE_URL}{model_dir}/{scenario_dir}/{freq_dir}/{var_dir}/{filename}"
            else:
                # Fallback to simple concatenation
                resource_url = TACC_BASE_URL + str(relative_path).replace('\\', '/')

            resource = {
                "url": resource_url,
                "name": f"NetCDF Data: {netcdf_path.name}",
                "format": "NetCDF",
                "description": f"NetCDF dataset from {relative_path}"
            }

            print(f"📤 Adding NetCDF resource reference...")
            create_resource_by_url(jwt_token, pkg["id"], resource, CKAN_URL)

    print("✅ All NetCDF files processed!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python netcdf_ckan.py <config.json>")
        sys.exit(1)
    main(sys.argv[1])