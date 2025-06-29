import sys
import os

# Proje dizinini Python path'e ekle
sys.path.insert(0, os.path.dirname(__file__))

def application(environ, start_response):
    status = '200 OK'
    output = b'Hello World! Passenger is working!'
    
    response_headers = [('Content-type', 'text/plain'),
                       ('Content-Length', str(len(output)))]
    start_response(status, response_headers)
    
    return [output] 