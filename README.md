# OSM Industrial Filter

A Python tool for extracting and filtering industrial land use areas from OpenStreetMap data by size, with support for country-based queries and JOSM integration.

## Features

- **Country-based queries**: Specify a country name instead of manual bounding box coordinates
- **Area-based filtering**: Filter industrial areas by minimum size (default: 10,000 sqm = 1 hectare)
- **Accurate area calculation**: Uses UTM projection for precise area measurements
- **GeoJSON export**: Exports filtered results with comprehensive metadata
- **JOSM integration**: Direct integration with JOSM editor via remote control
- **Flexible input**: Supports both country names and custom bounding boxes
- **Comprehensive output**: Includes OSM IDs, area calculations, and original tags

## Installation

### Requirements

```bash
pip install overpy geojson shapely pyproj requests
```

### Dependencies

- `overpy`: OpenStreetMap Overpass API client
- `geojson`: GeoJSON format handling
- `shapely`: Geometric operations and area calculations
- `pyproj`: Coordinate system transformations
- `requests`: HTTP requests for geocoding and JOSM integration

## Usage

### Basic Examples

```bash
# Filter industrial areas in the Netherlands (>= 10,000 sqm)
python osm_industrial_filter.py --country "Netherlands"

# Filter large industrial areas in Germany (>= 50,000 sqm)
python osm_industrial_filter.py --country "Germany" --min-area 50000

# Export to custom filename and open in JOSM
python osm_industrial_filter.py --country "Belgium" --output "belgium_industrial.geojson" --josm

# Use custom bounding box instead of country
python osm_industrial_filter.py --bbox "52.3,4.7,52.5,5.1" --min-area 25000
```

### Testing Connectivity

If you're experiencing network issues, start with a small area to test:

```bash
# Tiny test area in Morocco (Casablanca)
python osm_industrial_filter.py --bbox "33.55,-7.63,33.57,-7.61" --josm

```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--country` | Country name for automatic bounding box lookup | None |
| `--bbox` | Manual bounding box as "south,west,north,east" | None |
| `--min-area` | Minimum area in square meters | 10000 |
| `--output` | Output GeoJSON filename | `large_industrial_areas.geojson` |
| `--josm` | Open results in JOSM editor after export | False |

## How It Works

1. **Country Lookup**: Uses OpenStreetMap's Nominatim service to convert country names to bounding boxes
2. **Data Extraction**: Queries the Overpass API for `landuse=industrial` ways and relations
3. **Area Calculation**: Converts coordinates to appropriate UTM projection for accurate area measurement
4. **Filtering**: Removes industrial areas smaller than the specified threshold
5. **Export**: Saves filtered results as GeoJSON with comprehensive metadata
6. **JOSM Integration**: Optionally opens the data in JOSM via remote control API, not suitable when querying at country level

## Output Format

The script exports GeoJSON with the following structure:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "osm_id": 12345,
        "osm_type": "way",
        "landuse": "industrial",
        "area_sqm": 25000.50,
        "area_hectares": 2.50,
        "name": "Industrial Complex Name"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[lon, lat], ...]]
      }
    }
  ],
  "properties": {
    "description": "Industrial areas >= 10000 sqm",
    "count": 42,
    "min_area_sqm": 10000,
    "country": "Netherlands",
    "bounding_box": {
      "south": 50.7,
      "west": 3.2,
      "north": 53.6,
      "east": 7.2
    }
  }
}
```

## JOSM Integration

To use JOSM integration:

1. **Enable Remote Control** in JOSM:
   - Go to `Preferences → Remote Control`
   - Check "Enable remote control"
   - Optionally enable "Load data from API" for better functionality

2. **Run with JOSM flag**:
   ```bash
   python osm_industrial_filter.py --country "Netherlands" --josm
   ```

3. **JOSM will automatically**:
   - Load the specified geographic area
   - Display the filtered industrial areas
   - Allow immediate editing and validation

## Country Name Examples

The tool accepts various country name formats:

- Full names: "Netherlands", "United Kingdom", "Czech Republic"
- Common names: "UK", "USA", "Germany"
- Alternative names: "Holland" (for Netherlands), "Britain" (for UK)

## Area Thresholds

Common area thresholds for different use cases:

- **Small industrial areas**: 5,000 sqm (0.5 hectares)
- **Medium industrial areas**: 10,000 sqm (1 hectare) - default
- **Large industrial complexes**: 50,000 sqm (5 hectares)
- **Major industrial zones**: 100,000 sqm (10 hectares)
- **Industrial megasites**: 1,000,000 sqm (100 hectares)

## Error Handling

The script handles various error conditions:

- **Invalid country names**: Shows suggestions and exits gracefully
- **Network timeouts**: Provides clear error messages for API failures
- **Malformed geometries**: Skips invalid polygons with warnings
- **JOSM connection issues**: Falls back to URL display if JOSM unavailable

## Performance Considerations

- **Large countries**: Queries for large countries (USA, Russia, China) may take several minutes
- **Dense areas**: Urban regions with many industrial areas will take longer to process
- **Network dependency**: Requires stable internet connection for OSM and geocoding APIs
- **Memory usage**: Large result sets may require significant RAM for processing
- **Server reliability**: Uses alternative Overpass server (overpass.kumi.systems) for better uptime

## Alternative Overpass Servers

The script uses `overpass.kumi.systems` by default for better reliability. If you experience network issues, you can manually edit the script to use different servers:

```python
# In OSMIndustrialFilter.__init__, replace the Overpass() line:

# Default (current)
self.api = overpy.Overpass(url="https://overpass.kumi.systems/api/interpreter")

# Original OSM server
self.api = overpy.Overpass()

# French server
self.api = overpy.Overpass(url="https://overpass.openstreetmap.fr/api/interpreter")

# Russian server
self.api = overpy.Overpass(url="https://maps.mail.ru/osm/tools/overpass/api/interpreter")
```

## License

OpenStreetMap data is available under the Open Database License (ODbL).

## Troubleshooting

### Common Issues

**"No results found for country"**
- Check spelling of country name
- Try alternative names (e.g., "UK" instead of "United Kingdom")
- Verify internet connection

**"Could not connect to JOSM remote control"**
- Ensure JOSM is running
- Enable remote control in JOSM preferences
- Check if port 8111 is available

**Network Exception / "Error querying Overpass API"**
- **Most common issue**: Overpass servers are frequently overloaded
- The script now uses `overpass.kumi.systems` for better reliability
- Try reducing query area size:
  ```bash
  # Instead of large area
  python osm_industrial_filter.py --bbox "33.4,-7.7,33.6,-7.5" --josm
  
  # Try smaller area
  python osm_industrial_filter.py --bbox "33.55,-7.63,33.57,-7.61" --josm
  ```
- Wait a few minutes and retry
- Check Overpass API status: https://overpass-api.de/api/status

**Testing Overpass Server Connectivity**
```bash
# Test if servers are responding
curl "https://overpass.kumi.systems/api/status"
curl "https://overpass-api.de/api/status"

# Test with minimal query
curl "https://overpass.kumi.systems/api/interpreter" -d "[out:json];way[landuse=industrial](33.5,-7.6,33.6,-7.5);out geom;"
```

**Very slow performance**
- Use smaller areas or higher minimum area thresholds
- Consider splitting large countries into regions
- Check if Overpass API is experiencing high load
- Try different Overpass servers (see Alternative Overpass Servers section)

### Network Issue Solutions

1. **Start small**: Use tiny bounding boxes (0.05° x 0.05°) to test connectivity
2. **Try different servers**: Edit script to use alternative Overpass endpoints
3. **Wait and retry**: Overpass servers often recover after a few minutes
4. **Check server status**: Visit https://overpass-api.de/ for service announcements
