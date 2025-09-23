# NetCDF to CKAN Upload Tool

This tool automatically uploads NetCDF climate data to CKAN, organizing files hierarchically by model, scenario, frequency, and variable.

## Features

- **Hierarchical Organization**: Groups NetCDF files by climate model, scenario, frequency, and variable into logical datasets
- **Filename-based Parsing**: Extracts metadata from standardized climate filenames (e.g., `EC-Earth3_ssp245_rsds_1km_2018.nc`)
- **Rich Metadata Extraction**: Automatically extracts spatial/temporal coverage, variables, and global attributes from NetCDF files
- **Flexible Configuration**: Support for both hierarchical datasets and individual file datasets
- **CKAN Integration**: Creates datasets with resources, handles updates, and manages metadata

## Prerequisites

### Python Dependencies
```bash
pip install xarray numpy shapely requests tapipy pathlib
```

### Required Python Packages
- `xarray` - NetCDF file reading
- `numpy` - Numerical operations
- `shapely` - Spatial geometry handling
- `requests` - HTTP API calls
- `tapipy` - Tapis authentication
- `pathlib` - File path handling

## Quick Start

### 1. Configure Your Settings

Copy the example config and update with your credentials:
```bash
cp config_netcdf_example.json config.json
```

Edit `config.json`:
```json
{
  "username": "your_tapis_username",
  "password": "your_tapis_password",
  "owner_org": "your_ckan_organization",
  "netcdf_directory": "./EC-Earth3",
  "dataset_name_prefix": "setx_climate",
  "use_hierarchical_datasets": true
}
```

### 2. Run the Script

```bash
python netcdf_ckan.py config.json
```

## Configuration Options

| Parameter | Description | Example |
|-----------|-------------|---------|
| `username` | Tapis username | `"your_username"` |
| `password` | Tapis password | `"your_password"` |
| `owner_org` | CKAN organization ID | `"your-org"` |
| `netcdf_directory` | Path to NetCDF files | `"./EC-Earth3"` |
| `dataset_name_prefix` | Prefix for dataset names | `"setx_climate"` |
| `use_hierarchical_datasets` | Group files into datasets | `true` |
| `tags` | Additional tags | `["climate", "texas"]` |
| `license_id` | Dataset license | `"cc-by"` |
| `private` | Make datasets private | `false` |

## Expected File Structure

The tool supports multiple filename patterns:

### Pattern 1: Standard Climate Model Format
```
EC-Earth3_ssp245_rsds_1km_2018.nc
{model}_{scenario}_{variable}_{resolution}_{year}.nc
```

### Pattern 2: Directory-based Structure
```
EC-Earth3/ssp245/day/rsds/EC-Earth3_ssp245_rsds_1km_2018.nc
{model}/{scenario}/{frequency}/{variable}/{filename}.nc
```

## What It Does

### With `use_hierarchical_datasets: true` (Recommended)

For your EC-Earth3 data structure, the script will create **2 datasets**:

1. **`setx_climate_ec_earth3_ssp245_day_rsds`**
   - Title: "EC-Earth3 SSP245 Surface Downwelling Shortwave Radiation (day) - 2015-2100"
   - Contains: 86 NetCDF resources (one per year)
   - Tags: `["netcdf", "climate", "scientific-data", "ec-earth3", "ssp245", "rsds", "geospatial", "texas"]`

2. **`setx_climate_ec_earth3_ssp245_day_tasmin`**
   - Title: "EC-Earth3 SSP245 Daily Minimum Near-Surface Air Temperature (day) - 2015-2100"
   - Contains: 86 NetCDF resources (one per year)
   - Tags: `["netcdf", "climate", "scientific-data", "ec-earth3", "ssp245", "tasmin", "geospatial", "texas"]`

### With `use_hierarchical_datasets: false`

Creates individual datasets for each NetCDF file (172 datasets total).

## Metadata Extraction

The script automatically extracts:

- **Spatial Coverage**: Bounding box from lat/lon coordinates
- **Temporal Coverage**: Start/end dates from time dimension
- **Variables**: Data variables and their attributes
- **Global Attributes**: NetCDF global metadata
- **File Information**: Size, format, number of files
- **Climate Metadata**: Model, scenario, variable, temporal range

## Example Output

```
🔍 Searching for NetCDF files in ./EC-Earth3
📁 Found 172 NetCDF files
🏗️ Organizing files by model/scenario/frequency/variable hierarchy...
📊 Found 2 dataset groups:
   • EC-Earth3/ssp245/day/rsds: 86 files
   • EC-Earth3/ssp245/day/tasmin: 86 files

📊 Processing dataset group: EC-Earth3/ssp245/day/rsds (86 files)
📦 Creating dataset: setx_climate_ec_earth3_ssp245_day_rsds
✅ Dataset ready with ID: abc123
📤 Adding 86 NetCDF resource references...
✅ All NetCDF files processed!
```

## Troubleshooting

### Authentication Issues
- Verify your Tapis username/password in config.json
- Check that your organization exists in CKAN

### File Parsing Issues
- The script will show warnings for unparseable filenames
- Check that filenames follow expected patterns
- Use directory structure as fallback if filename parsing fails

### Memory Issues
- The script reads NetCDF metadata but not full data arrays
- Large numbers of files are processed sequentially to manage memory

### CKAN API Errors
- Check dataset names don't conflict with existing datasets
- Verify organization permissions
- Review CKAN logs for detailed error messages

## Advanced Usage

### Custom Filename Patterns
Edit the `organize_netcdf_by_hierarchy()` function to add support for your specific filename patterns.

### Additional Metadata
Modify the `create_dataset_from_netcdf_collection()` function to extract additional metadata from NetCDF global attributes.

### Different CKAN Instance
Update the `CKAN_URL` constant to point to your CKAN instance.

## Files

- `netcdf_ckan.py` - Main script
- `config_netcdf_example.json` - Example configuration
- `odm_ckan.py` - Alternative script for ODM data
- `environment.yml` - Conda environment specification

## Support

For issues with the script, check:
1. Python package dependencies are installed
2. Configuration file is valid JSON
3. CKAN API credentials and permissions
4. NetCDF file accessibility and format