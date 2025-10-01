#!/usr/bin/env python3
"""
Validate a specific conference entry or all conference data.
Usage: python validate-conference.py [conference_name]
"""

import sys
import yaml
from pathlib import Path
from datetime import datetime

def validate_conference(conf: dict, name: str = None) -> list[str]:
    """Validate a single conference entry."""
    errors = []
    
    # Required fields
    required = ['conference', 'year', 'link', 'cfp', 'place', 'start', 'end', 'sub']
    for field in required:
        if field not in conf:
            errors.append(f"Missing required field: {field}")
    
    # Year validation
    if 'year' in conf and conf['year'] < 1989:
        errors.append(f"Year {conf['year']} is before Python's birth (1989)")
    
    # URL validation
    if 'link' in conf and not conf['link'].startswith('https://'):
        errors.append(f"URL must use HTTPS: {conf['link']}")
    
    # Date validation
    date_fields = ['cfp', 'start', 'end', 'sub']
    for field in date_fields:
        if field in conf:
            try:
                datetime.strptime(conf[field], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                errors.append(f"Invalid date format for {field}: {conf[field]}")
    
    # Coordinate validation
    if 'lat' in conf and 'lon' in conf:
        lat_str = str(conf['lat'])
        lon_str = str(conf['lon'])
        if '.' in lat_str and len(lat_str.split('.')[1]) > 5:
            errors.append(f"Latitude precision too high: {conf['lat']}")
        if '.' in lon_str and len(lon_str.split('.')[1]) > 5:
            errors.append(f"Longitude precision too high: {conf['lon']}")
    
    return errors

def main():
    conf_file = Path('E:/Code/python-deadlines/_data/conferences.yml')
    
    if not conf_file.exists():
        print("❌ conferences.yml not found!")
        return 1
    
    with open(conf_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if not data:
        print("⚠️ No conference data found")
        return 1
    
    target_name = sys.argv[1] if len(sys.argv) > 1 else None
    total_errors = 0
    
    for conf in data:
        if target_name and conf.get('conference') != target_name:
            continue
        
        errors = validate_conference(conf)
        if errors:
            total_errors += len(errors)
            print(f"\n❌ {conf.get('conference', 'Unknown')} ({conf.get('year', '?')})")
            for error in errors:
                print(f"   - {error}")
    
    if total_errors == 0:
        print("✅ All conference data is valid!")
        return 0
    else:
        print(f"\n⚠️ Found {total_errors} validation errors")
        return 1

if __name__ == "__main__":
    sys.exit(main())