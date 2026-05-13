import sys
sys.path.insert(0, '.')

from app import app

print("Routes registered in app object:")
print("="*80)

for rule in app.url_map.iter_rules():
    methods = ','.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
    print(f"{rule.rule:40} {methods:25} {rule.endpoint}")

print("\n" + "="*80)
print("Checking specific routes:")
for rule in app.url_map.iter_rules():
    if 'start' in str(rule.rule):
        print(f"✅ {rule.rule:40} {rule.endpoint}")
