from app import app
import json

routes = []
for rule in app.url_map.iter_rules():
    if 'start' in str(rule.rule):
        routes.append({
            'rule': str(rule.rule),
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'endpoint_func': app.view_functions.get(rule.endpoint).__name__
        })

print(json.dumps(routes, indent=2))

# Also test the routes directly
print("\n" + "="*80)
print("Direct test of routes using Flask test client:")
print("="*80)

with app.test_client() as client:
    test_routes = [
        ('/start_session', {'camera_id': '1', 'classroom_id': '1'}),
        ('/start-gate', {'classroom_id': '1'}),
        ('/start-class', {'classroom_id': '1'}),
    ]
    
    for route, data in test_routes:
        resp = client.post(route, data=data)
        print(f"{route:30} -> Status {resp.status_code}")
