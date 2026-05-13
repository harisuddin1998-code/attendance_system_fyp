from flask import Flask

test_app = Flask(__name__)

@test_app.route('/basic', methods=['POST'])
def basic():
    return "BASIC_WORKS"

@test_app.route('/start-gate', methods=['POST'])
def start_gate():
    return "GATE_WORKS"

@test_app.route('/start_session', methods=['POST'])
def start_session():
    return "SESSION_WORKS"

if __name__ == '__main__':
    print("Routes in test app:")
    for rule in test_app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
        print(f"  {rule.rule:40} {methods:20} {rule.endpoint}")
    
    test_app.run(debug=False, port=5001)
