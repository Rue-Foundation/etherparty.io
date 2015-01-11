#etherparty.io v1
#GPLv3
import apsw, re, random, binascii, logging, subprocess, os, time, json, hashlib
from flask import Flask, request, Response, redirect
app = Flask(__name__)

log_file = './access.log'
db_file = '/home/ubuntu/.etherparty/users.db'
logger = logging.getLogger('werkzeug')
logger.setLevel(666)
logger.addHandler(logging.FileHandler(log_file))

def log__():
   _env = request.environ
   keys = ['HTTP_CF_CONNECTING_IP','QUERY_STRING', 'REQUEST_METHOD', 'REMOTE_ADDR', 
           'HTTP_USER_AGENT','HTTP_ACCEPT_LANGUAGE', 'HTTP_COOKIE', 'PATH_INFO' ]
   result = []

   for key in keys:
      result.append('None' if key not in _env else _env[key])

   result.append(request.form if len(request.form) > 0 else 'None' )

   logger.log(666,"[ %s ] - IP %s - QS %s - METHOD %s - REMOTEIP %s - UAGENT %s - LANG %s - PATH %s - FORM %s", time.strftime("%Y-%m-%d %H:%M:%S"),  result[0], result[1], result[2], result[3], result[4], result[5], result[7], result[8])

@app.after_request
def req_hand(res):
  log__()
  return res

filetypes = { 'js': 'application/json', 'css': 'text/css', 'html': 'text/html', 'png': 'image/png', 
   'jpg': 'image/jpg', 'php': 'text/html', 'woff': 'application/font-woff', 'ttf': 'application/x-font-ttf', 'mp4': 'video/mp4', 'ogg': 'video/ogg', 'webm': 'video/webm' }
binaryprefixes = ['ttf','woff','mp4','ogg','webm', 'jpg', 'png']
@app.route("/")
@app.route("/<path:ex>")
def extra(ex='index.html'):

   if request.headers.has_key("Range"):
     sts = 206
   else:
     sts = 200

   print(ex)

   try:
    prefix = ex.split('.')[-1]
    filetype = filetypes[ prefix ] 
    if prefix in binaryprefixes:
      ret = open('' +ex, mode="rb").read()
    else:
      ret = ''.join(open('' +ex, encoding='utf8').readlines())

    resp = Response(response=ret, status=sts, mimetype=filetype)

    if sts == 206: 
      resp.headers.add('Accept-Ranges','bytes')
      resp.headers.add('Content-Transfer-Encoding','binary')
      resp.headers.add('Content-Range','bytes %s-%s/%s' % (str(0),str(len(ret) - 1),str(len(ret))) )

    return resp 
   except Exception as e:
    print('err', ex, e)
    return ''

def sanitize(s):
  print([type(s), s])
  return binascii.hexlify( s.encode('ascii',errors='ignore') ).decode('ascii') #.zfill(128)[:128] #max 64 bytes of data allowed

@app.route("/execute", methods=['POST'])
def execute():

   print(["form", request.form])

   blob = { 
    'timestamp': sanitize( str( int( time.time() ) ) ),
    'email': sanitize( request.form['email'] ),
    'name': sanitize( request.form['name'] ),
    'alias': sanitize( request.form['alias'] )
   }

   blobhex = hashlib.sha256( json.dumps(blob).encode('ascii') ).hexdigest()

   blobkey = str( int( blobhex[:16], 16 ) ).zfill(64)

   #TODO need to put character limit on input field, 32byte word max 

   print(["post-sanitize", blob, blobhex, blobkey])
   try:

        source = "mvMqLp7NhrPcUkMznrBA6TkJAzHoVKqvif" #hardcode for now
        contract = "d12e2000ea15ff18333d062fce82be53ef2f82e3" #hardcode for now
        gasprice = "1"
        startgas = "200000"
        value = "0"
        xcp_dir= "/home/ubuntu/counterpartyd_build/dist/counterpartyd/"
        data_dir= "/home/ubuntu/.config/counterpartyd/"
        payload_hex = blobkey + blobhex 

        print(["pre-submission", payload_hex])

        hexdata = subprocess.check_output([xcp_dir + "counterpartyd.py","--testnet", "--unconfirmed", "--data-dir=" + data_dir,"execute", "--source=" + source ,"--contract=" + contract, "--gasprice=" + gasprice , "--startgas=" + startgas, "--value=" + value, "--payload-hex=" + payload_hex], stderr=subprocess.STDOUT).decode('utf-8').replace('\n', '').split(';')

        print(hexdata)

        blob['txid'] = hexdata[-1]

        #TODO store in sqlite blobhex, blobkey, txid, timestamp, email, name, alias

        db = apsw.Connection(db_file)
        cursor = db.cursor()
        retval = cursor.execute('''INSERT into users(blobhex,blobkey,txid,timestamp,email,name,alias) VALUES (?,?,?,?,?,?,?);''', [blobhex, blobkey, blob['txid'], blob['timestamp'], blob['email'], blob['name'], blob['alias'] ] )
        print(retval, 'a')
        cursor.close()

   except Exception as e:
        print(e, e.__dict__)

   return blobkey; 

def decoderow(tup):
  each = tup
  return (each[0], each[1], int(each[2]), each[3], binascii.unhexlify(each[4]).decode('ascii'), binascii.unhexlify(each[5]).decode('ascii'), binascii.unhexlify(each[6]).decode('ascii'),binascii.unhexlify(each[7]).decode('ascii') if each[7] is not None else None )

@app.route("/users")
def getusers():
    try:
      db = apsw.Connection(db_file)
      cursor = db.cursor()
      rows = list(cursor.execute('''SELECT * FROM users;'''))
      print(rows, 'a')
      rows = [ decoderow(each) for each in rows ]
      cursor.close()
    except Exception as e:
      print(e, e.__dict__)

    return json.dumps(rows); 

if __name__ == "__main__":
    app.run(host="127.0.0.1",port=6666, debug=True, use_reloader=True)
