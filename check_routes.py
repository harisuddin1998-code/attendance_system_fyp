import app
print([rule.rule for rule in app.app.url_map.iter_rules()])
