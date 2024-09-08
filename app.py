import logging
from logging.config import dictConfig
from flask import Flask, request, jsonify, Response, g, abort
import requests
from schema import init_db  # Absolute import
from db import get_db  # Absolute import
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask.logging import default_handler
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

REQUEST_COUNT = Counter('flask_http_request_total', 'Total HTTP Requests', 
                        ['method', 'endpoint'])
ERROR_COUNT = Counter('flask_http_error_total', 'Total HTTP Errors')

def create_app():
    app = Flask(__name__)

    dictConfig({
        'version': 1,
        'formatters': {
            'default': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            }
        },
        'handlers': {
            'default': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'stream': 'ext://sys.stdout',
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['default'],
        },
        'loggers': {
            'werkzeug': {
                'level': 'INFO',
                'handlers': ['default'],
                'propagate': False,
            },
        },
    })

    app.logger.setLevel(logging.INFO)
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s'))
        app.logger.addHandler(handler)

    with app.app_context():
        init_db()

    return app

app = create_app()

app = create_app()
app.logger.removeHandler(default_handler)
print("Application starting", flush=True)

@app.before_request
def before_request():
    endpoint = request.endpoint or 'unknown'
    REQUEST_COUNT.labels(method=request.method, endpoint=endpoint).inc()

@app.after_request
def after_request(response):
    if 400 <= response.status_code < 600:
        ERROR_COUNT.inc()
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    ERROR_COUNT.inc()
    app.logger.error(f"An unexpected error occurred: {str(e)}")
    return "Internal Server Error", 500

@app.route('/metrics')
def metrics():
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)

def authenticate(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not auth.username or not auth.password:
            app.logger.warning("Authentication required but not provided")
            abort(401, description="Authentication required")

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT id, password FROM users WHERE username=%s", (auth.username,))
        user = cursor.fetchone()
        cursor.close()

        if user is None or not check_password_hash(user[1], auth.password):
            app.logger.warning(f"Invalid credentials for user '{auth.username}'.")
            abort(403, description="Invalid credentials")

        g.user_id = user[0]  # Store the user's ID in the Flask global object
        app.logger.info(f"User '{auth.username}' authenticated successfully")

        return f(*args, **kwargs)
    
    return decorated_function

@app.route('/authenticate', methods=['GET'])
@authenticate
def authenticate_endpoint():
    return jsonify({"message": "Authenticated successfully"}), 200

@app.route('/create_user', methods=['POST'])
def create_user():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        hashed_password = generate_password_hash(password)

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id",
            (username, hashed_password)
        )
        user_id = cursor.fetchone()[0]
        db.commit()
        cursor.close()

        app.logger.info(f"User '{username}' created successfully with user ID: {user_id}")
        return jsonify({"message": "User created successfully", "user_id": user_id}), 201

    except Exception as e:
        app.logger.error(f"Error creating user: {e}")
        return jsonify({"error": "Failed to create user"}), 500

@app.route('/create_bucket/<bucket>', methods=['POST'])
@authenticate
def create_bucket(bucket):
    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT 1 FROM buckets WHERE bucket_name=%s", (bucket,))
        bucket_exists = cursor.fetchone()

        if bucket_exists:
            app.logger.warning(f"Bucket '{bucket}' already exists")
            cursor.close()
            return jsonify({"error": "Bucket already exists"}), 200

        # Insert the new bucket into db
        cursor.execute("INSERT INTO buckets (bucket_name, user_id) VALUES (%s, %s)", (bucket, g.user_id))
        db.commit()

        app.logger.info(f"Bucket '{bucket}' created successfully")
        return jsonify({"message": f"Bucket '{bucket}' created successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error creating bucket '{bucket}': {e}")
        return jsonify({"error": "Failed to create bucket"}), 500

@app.route('/delete_bucket/<bucket>', methods=['DELETE'])
@authenticate
def delete_bucket(bucket):
    try:
        db = get_db()
        cursor = db.cursor()

        # Check if the bucket belongs to the authenticated user
        cursor.execute("SELECT 1 FROM buckets WHERE bucket_name=%s AND user_id=%s", (bucket, g.user_id))
        bucket_exists = cursor.fetchone()

        if not bucket_exists:
            cursor.close()
            return jsonify({"error": "Bucket does not exist or you do not have permission to delete it"}), 403

        # Delete the bucket from the buckets table
        cursor.execute("DELETE FROM buckets WHERE bucket_name=%s", (bucket,))
        db.commit()

        # Fetch all nodes from the database
        cursor.execute("SELECT node_name FROM nodes")
        nodes = cursor.fetchall()
        cursor.close()

        # Send delete bucket request to all nodes
        for node in nodes:
            node_name = node[0]
            service_url = f"http://{node_name}.s3.svc.cluster.local:8080/delete_bucket/{bucket}"
            response = requests.delete(service_url)
            if response.status_code != 200:
                app.logger.error(f"Failed to delete bucket '{bucket}' on node '{node_name}'.")
                return jsonify({"error": f"Failed to delete bucket on node {node_name}"}), 500

        app.logger.info(f"Bucket '{bucket}' deleted from all nodes successfully")
        return jsonify({"message": f"Bucket '{bucket}' deleted from all nodes successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error deleting bucket '{bucket}': {e}")
        return jsonify({"error": "Failed to delete bucket"}), 500

@app.route('/upload/<bucket>/<path:key>', methods=['PUT'])
@authenticate
def handle_upload(bucket, key):
    try:
        key = key.rstrip('/')
        db = get_db()
        cursor = db.cursor()


        cursor.execute(
            "SELECT 1 FROM buckets WHERE bucket_name=%s AND user_id=%s", 
            (bucket, g.user_id)
        )
        bucket_exists = cursor.fetchone()

        if not bucket_exists:
            cursor.close()
            app.logger.warning(f"Bucket '{bucket}' does not exist or you do not have permission to access it")
            return jsonify({"error": "Bucket does not exist or you do not have permission to access it"}), 403

        # 3. Check if the key (file) already exists
        cursor.execute(
            "SELECT node_name FROM objects WHERE bucket=%s AND key=%s", 
            (bucket, key)
        )
        existing_record = cursor.fetchone()

        if existing_record:
            node_name = existing_record[0]
            service_url = f"http://{node_name}.s3.svc.cluster.local:8080/upload/{bucket}/{key}"
        else:
            service_url = f"http://s3worker.s3.svc.cluster.local:8080/upload/{bucket}/{key}"

        cursor.close()

        files = {'file': (key, request.files['file'].read())}
        response = requests.put(service_url, files=files) 

        if response.status_code == 200:
            app.logger.info(f"File '{key}' in bucket '{bucket}' uploaded successfully")
            return "Upload successful", 200
        else:
            return jsonify({"error": "Failed to process file"}), response.status_code

    except Exception as e:
        app.logger.error(f"Error handling upload request for '{key}' in bucket '{bucket}': {e}")
        return jsonify({"error": "Failed to handle upload request"}), 500

@app.route('/<bucket>/<path:key>', methods=['GET', 'HEAD', 'DELETE'])
@authenticate
def handle_request(bucket, key):
    try:
        key = key.rstrip('/')
        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT 1 FROM buckets WHERE bucket_name=%s AND user_id=%s", (bucket, g.user_id))
        bucket_exists = cursor.fetchone()

        if not bucket_exists:
            cursor.close()
            app.logger.warning(f"Bucket '{bucket}' does not exist or you do not have permission to access it")
            return jsonify({"error": "Bucket does not exist or you do not have permission to access it"}), 403

        cursor.execute(
            "SELECT node_name FROM objects WHERE bucket=%s AND key=%s",
            (bucket, key)
        )
        existing_record = cursor.fetchone()
        cursor.close()

        if not existing_record:
            app.logger.warning(f"File '{key}' in bucket '{bucket}' not found")
            return jsonify({"error": "File not found"}), 404

        node_name = existing_record[0]
        service_url = f"http://{node_name}.s3.svc.cluster.local:8080/{bucket}/{key}"

        if request.method == 'GET':
            response = requests.get(service_url, stream=True)
            if response.status_code == 200:
                return Response(response.iter_content(chunk_size=10*1024),
                                content_type=response.headers['Content-Type'],
                                status=response.status_code)
            else:
                return jsonify({"error": "Failed to retrieve file"}), response.status_code

        elif request.method == 'HEAD':
            response = requests.head(service_url)
            if response.status_code == 200:
                return jsonify({"message": "File exists", "size": response.headers.get('Content-Length')}), 200
            else:
                return jsonify({"error": "File not found"}), response.status_code

        elif request.method == 'DELETE':
            response = requests.delete(service_url)
            if response.status_code == 200:
                return jsonify({"message": "File deleted successfully"}), 200
            else:
                return jsonify({"error": "Failed to delete file"}), response.status_code

    except Exception as e:
        app.logger.error(f"Error handling request for '{key}' in bucket '{bucket}': {e}")
        return jsonify({"error": "Failed to handle request"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
