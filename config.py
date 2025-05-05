import os
from queue import Queue

# Hostname or IP of the Grand Server
GRAND_HOST = "10.0.0.3"
GRAND_PORT = 9000

BIND_HOST = "0.0.0.0"

basedir = os.path.abspath(os.path.dirname(__file__))  #The location of the system.
certfile = os.path.join(basedir, 'server.crt') #The location of the certificate.
keyfile = os.path.join(basedir, 'server.key') #The location of the public key
secret_key = "dfcc0ab22a9913f9f19c758feabe1c2c56d0e5be670647ef4f131666c36f0572" #The secret key of the project.


db_file = os.path.join(basedir, 'database.db')
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')

changes_queue = Queue()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}