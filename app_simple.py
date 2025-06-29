from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello World! Flask is working!"

@app.route('/test')
def test():
    return "Test page is working!"

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000) 