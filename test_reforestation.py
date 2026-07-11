import sys
sys.path.insert(0, '.')
from reforestation_engine import get_batch_recommendations, SPECIES_INFO
print('Engine imported OK')
print('Species catalog:', list(SPECIES_INFO.keys()))

test_cells = [
    {'row': 10, 'col': 12, 'latitude': -2.1, 'longitude': -59.1,
     'risk_score': 0.8, 'vegetation_density': 0.3, 'fuel_load': 0.7,
     'soil_moisture': 0.3, 'elevation': 120.0, 'temperature': 30.0,
     'humidity': 70.0, 'wind_speed': 4.0, 'rainfall': 3.0, 'burn_duration': 5},
    {'row': 11, 'col': 13, 'latitude': -2.105, 'longitude': -59.09,
     'risk_score': 0.6, 'vegetation_density': 0.5, 'fuel_load': 0.5,
     'soil_moisture': 0.5, 'elevation': 110.0, 'temperature': 28.0,
     'humidity': 78.0, 'wind_speed': 3.0, 'rainfall': 8.0, 'burn_duration': 3},
]

result = get_batch_recommendations(test_cells)
print('Status:', result['status'])
print('Burned cells processed:', result['total_burned_cells'])
print('Dominant species:', result['summary']['dominant_recommended_species'])
print('Species distribution:', result['summary']['species_distribution'])
for r in result['recommendations']:
    row = r['row']
    col = r['col']
    sp = r['recommended_species']
    conf = int(r['confidence']*100)
    st = r['soil_type']
    dr = r['drainage']
    print(f'  Cell ({row},{col}): {sp} ({conf}%) - {st} / {dr}')
