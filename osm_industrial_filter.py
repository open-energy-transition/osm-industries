#!/usr/bin/env python3

import overpy
import geojson
import json
import requests
import urllib.parse
from shapely.geometry import Polygon, Point
from shapely.ops import transform
import pyproj
from functools import partial
import argparse
import sys
import time
from typing import List, Dict, Tuple, Optional

class OSMIndustrialFilter:
    def __init__(self, min_area_sqm: float = 10000, bbox: Optional[Tuple[float, float, float, float]] = None, country: Optional[str] = None):
        self.api = overpy.Overpass(url="https://overpass.kumi.systems/api/interpreter")
        self.min_area_sqm = min_area_sqm
        self.bbox = bbox
        self.country = country
        self.filtered_features = []
        
        if country and not bbox:
            self.bbox = self.get_country_bbox(country)
        
    def get_country_bbox(self, country_name: str) -> Optional[Tuple[float, float, float, float]]:
        print(f"Looking up bounding box for country: {country_name}")
        
        nominatim_url = "https://nominatim.openstreetmap.org/search"
        
        params = {
            'q': country_name,
            'format': 'json',
            'limit': 1,
            'addressdetails': 1,
            'extratags': 1,
            'namedetails': 1
        }
        
        headers = {
            'User-Agent': 'OSM-Industrial-Filter/1.0 (https://github.com/user/repo)'
        }
        
        try:
            response = requests.get(nominatim_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            results = response.json()
            
            if not results:
                print(f"No results found for country: {country_name}")
                return None
            
            result = results[0]
            
            if 'address' in result:
                address = result['address']
                if 'country' not in address:
                    print(f"Warning: Result for '{country_name}' doesn't appear to be a country")
            
            if 'boundingbox' in result:
                bbox_str = result['boundingbox']
                south, north, west, east = map(float, bbox_str)
                bbox = (south, west, north, east)
                
                print(f"Found bounding box for {result.get('display_name', country_name)}")
                print(f"Bounding box: South={south}, West={west}, North={north}, East={east}")
                
                return bbox
            else:
                print(f"No bounding box found for: {country_name}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching country data: {e}")
            return None
        except (ValueError, KeyError, IndexError) as e:
            print(f"Error parsing country data: {e}")
            return None
        
        time.sleep(1)
        
    def build_query(self) -> str:
        bbox_filter = ""
        if self.bbox:
            south, west, north, east = self.bbox
            bbox_filter = f"({south},{west},{north},{east})"
            if self.country:
                print(f"Querying industrial areas in {self.country}")
            else:
                print(f"Querying industrial areas in bounding box: {bbox_filter}")
        
        query = f"""
        [out:json][timeout:3000];
        (
          way["landuse"="industrial"]{bbox_filter};
          relation["landuse"="industrial"]{bbox_filter};
        );
        (._;>;);
        out geom;
        """
        return query
    
    def calculate_area(self, geometry: List[Tuple[float, float]]) -> float:
        if len(geometry) < 3:
            return 0
        
        polygon = Polygon(geometry)
        
        centroid = polygon.centroid
        lon, lat = centroid.x, centroid.y
        
        utm_zone = int((lon + 180) / 6) + 1
        utm_epsg = 32600 + utm_zone if lat >= 0 else 32700 + utm_zone
        
        wgs84 = pyproj.CRS('EPSG:4326')
        utm = pyproj.CRS(f'EPSG:{utm_epsg}')
        project = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
        
        utm_polygon = transform(project, polygon)
        return utm_polygon.area
    
    def way_to_coordinates(self, way) -> List[Tuple[float, float]]:
        return [(float(node.lon), float(node.lat)) for node in way.nodes]
    
    def relation_to_coordinates(self, relation) -> List[List[Tuple[float, float]]]:
        outer_rings = []
        inner_rings = []
        
        for member in relation.members:
            if member.role == "outer" and hasattr(member, 'nodes'):
                coords = [(float(node.lon), float(node.lat)) for node in member.nodes]
                if len(coords) >= 3:
                    outer_rings.append(coords)
            elif member.role == "inner" and hasattr(member, 'nodes'):
                coords = [(float(node.lon), float(node.lat)) for node in member.nodes]
                if len(coords) >= 3:
                    inner_rings.append(coords)
        
        return outer_rings + inner_rings
    
    def create_geojson_feature(self, element, coordinates: List[Tuple[float, float]], area: float) -> Dict:
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        
        properties = {
            'osm_id': element.id,
            'osm_type': 'way' if hasattr(element, 'nodes') else 'relation',
            'landuse': 'industrial',
            'area_sqm': round(area, 2),
            'area_hectares': round(area / 10000, 2)
        }
        
        for key, value in element.tags.items():
            if key not in properties:
                properties[key] = value
        
        feature = {
            'type': 'Feature',
            'properties': properties,
            'geometry': {
                'type': 'Polygon',
                'coordinates': [coordinates]
            }
        }
        
        return feature
    
    def fetch_and_filter(self) -> List[Dict]:
        print("Fetching industrial land use data from OpenStreetMap...")
        
        query = self.build_query()
        print(f"Query: {query}")
        
        try:
            result = self.api.query(query)
            print(f"Found {len(result.ways)} ways and {len(result.relations)} relations")
        except Exception as e:
            print(f"Error querying Overpass API: {e}")
            return []
        
        features = []
        processed_count = 0
        kept_count = 0
        
        for way in result.ways:
            processed_count += 1
            try:
                coordinates = self.way_to_coordinates(way)
                if len(coordinates) < 3:
                    continue
                
                area = self.calculate_area(coordinates)
                
                if area >= self.min_area_sqm:
                    feature = self.create_geojson_feature(way, coordinates, area)
                    features.append(feature)
                    kept_count += 1
                    print(f"Kept way {way.id}: {area:.0f} sqm ({area/10000:.2f} ha)")
                else:
                    print(f"Filtered out way {way.id}: {area:.0f} sqm (too small)")
                    
            except Exception as e:
                print(f"Error processing way {way.id}: {e}")
        
        for relation in result.relations:
            processed_count += 1
            try:
                coord_rings = self.relation_to_coordinates(relation)
                if not coord_rings:
                    continue
                
                largest_ring = max(coord_rings, key=len) if coord_rings else []
                if len(largest_ring) < 3:
                    continue
                
                area = self.calculate_area(largest_ring)
                
                if area >= self.min_area_sqm:
                    feature = self.create_geojson_feature(relation, largest_ring, area)
                    features.append(feature)
                    kept_count += 1
                    print(f"Kept relation {relation.id}: {area:.0f} sqm ({area/10000:.2f} ha)")
                else:
                    print(f"Filtered out relation {relation.id}: {area:.0f} sqm (too small)")
                    
            except Exception as e:
                print(f"Error processing relation {relation.id}: {e}")
        
        print(f"\nProcessed {processed_count} elements, kept {kept_count} large industrial areas")
        self.filtered_features = features
        return features
    
    def export_geojson(self, filename: str = "large_industrial_areas.geojson") -> str:
        if not self.filtered_features:
            print("No features to export. Run fetch_and_filter() first.")
            return ""
        
        properties = {
            'description': f'Industrial areas >= {self.min_area_sqm} sqm',
            'count': len(self.filtered_features),
            'min_area_sqm': self.min_area_sqm
        }
        
        if self.country:
            properties['country'] = self.country
        if self.bbox:
            south, west, north, east = self.bbox
            properties['bounding_box'] = {
                'south': south,
                'west': west, 
                'north': north,
                'east': east
            }
        
        feature_collection = {
            'type': 'FeatureCollection',
            'features': self.filtered_features,
            'properties': properties
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(feature_collection, f, indent=2, ensure_ascii=False)
        
        country_info = f" in {self.country}" if self.country else ""
        print(f"Exported {len(self.filtered_features)} features{country_info} to {filename}")
        return filename
    
    def create_josm_link(self, geojson_file: str) -> str:
        if self.bbox:
            south, west, north, east = self.bbox
            bbox_param = f"{west},{south},{east},{north}"
            josm_url = f"http://127.0.0.1:8111/load_and_zoom?left={west}&bottom={south}&right={east}&top={north}"
        else:
            josm_url = "http://127.0.0.1:8111/import?url=" + urllib.parse.quote(f"file://{geojson_file}")
        
        print(f"JOSM Remote Control URL: {josm_url}")
        print("Note: Make sure JOSM is running with remote control enabled")
        print("(Preferences → Remote Control → Enable remote control)")
        
        return josm_url
    
    def open_in_josm(self, geojson_file: str) -> bool:
        josm_url = self.create_josm_link(geojson_file)
        
        try:
            response = requests.get(josm_url, timeout=10)
            if response.status_code == 200:
                print("Successfully sent data to JOSM")
                return True
            else:
                print(f"JOSM responded with status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Could not connect to JOSM remote control: {e}")
            print("Make sure JOSM is running with remote control enabled")
            return False

def main():
    parser = argparse.ArgumentParser(description='Filter OSM industrial areas by size')
    parser.add_argument('--min-area', type=float, default=10000,
                       help='Minimum area in square meters (default: 10000)')
    parser.add_argument('--bbox', type=str,
                       help='Bounding box as "south,west,north,east"')
    parser.add_argument('--country', type=str,
                       help='Country name (e.g., "Netherlands", "Germany", "United States")')
    parser.add_argument('--output', type=str, default='large_industrial_areas.geojson',
                       help='Output GeoJSON filename')
    parser.add_argument('--josm', action='store_true',
                       help='Attempt to open in JOSM after export')
    
    args = parser.parse_args()
    
    if args.country and args.bbox:
        print("Error: Please specify either --country OR --bbox, not both")
        sys.exit(1)
    
    if not args.country and not args.bbox:
        print("Warning: No geographic filter specified. This will query globally and may be very slow.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    bbox = None
    if args.bbox:
        try:
            bbox = tuple(map(float, args.bbox.split(',')))
            if len(bbox) != 4:
                raise ValueError("Bounding box must have 4 coordinates")
        except ValueError as e:
            print(f"Invalid bounding box format: {e}")
            sys.exit(1)
    
    filter_tool = OSMIndustrialFilter(
        min_area_sqm=args.min_area, 
        bbox=bbox, 
        country=args.country
    )
    
    if not filter_tool.bbox:
        if args.country:
            print(f"Could not find bounding box for country: {args.country}")
            sys.exit(1)
    
    features = filter_tool.fetch_and_filter()
    
    if not features:
        print("No industrial areas found or all were too small")
        sys.exit(1)
    
    geojson_file = filter_tool.export_geojson(args.output)
    
    if args.josm:
        filter_tool.open_in_josm(geojson_file)

if __name__ == "__main__":
    main()