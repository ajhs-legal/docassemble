import yaml
import os
import re
import sys
import httplib2
import socket
from docassemble.base.generate_key import random_string

dbtableprefix = None
daconfig = dict()
s3_config = dict()
S3_ENABLED = False
gc_config = dict()
GC_ENABLED = False
hostname = None
loaded = False
in_celery = False

def load(**kwargs):
    global daconfig
    global s3_config
    global S3_ENABLED
    global gc_config
    global GC_ENABLED
    global dbtableprefix
    global hostname
    global loaded
    global in_celery
    if 'arguments' in kwargs and kwargs['arguments'] and len(kwargs['arguments']) > 1:
        filename = kwargs['arguments'][1]
    else:
        filename = kwargs.get('filename', os.getenv('DA_CONFIG_FILE', '/usr/share/docassemble/config/config.yml'))
    if 'in_celery' in kwargs and kwargs['in_celery']:
        in_celery = True
    if not os.path.isfile(filename):
        if not os.access(os.path.dirname(filename), os.W_OK):
            sys.stderr.write("Configuration file " + str(filename) + " does not exist and cannot be created\n")
            sys.exit(1)
        with open(filename, 'w') as config_file:
            config_file.write(default_config())
            sys.stderr.write("Wrote configuration file to " + str(filename) + "\n")
    if not os.path.isfile(filename):
        sys.stderr.write("Configuration file " + str(filename) + " does not exist\n")
    with open(filename, 'rU') as stream:
        raw_daconfig = yaml.load(stream)
    if raw_daconfig is None:
        sys.stderr.write("Could not open configuration file from " + str(filename) + "\n")
        with open(filename, 'rU') as fp:
            sys.stderr.write(fp.read().decode('utf8') + "\n")
        sys.exit(1)
    daconfig = dict()
    for key, val in raw_daconfig.iteritems():
        if re.search(r'_', key):
            sys.stderr.write("WARNING!  Configuration keys should not contain underscores.  Your configuration key " + str(key) + " has been converted.\n")
            daconfig[re.sub(r'_', r' ', key)] = val
        else:
            daconfig[key] = val
    daconfig['config file'] = filename
    if 'keymap' in daconfig and daconfig['keymap'] not in ['vim', 'emacs', 'sublime']:
        sys.stderr.write("WARNING!  You used a keymap that is not supported.  Available values are vim, emacs, and sublime.\n")
        del daconfig['keymap']
    if 'vim' in daconfig:
        sys.stderr.write("WARNING!  The configuration directive vim is deprecated.  Please use keymap instead.\n")
        if daconfig['vim'] and 'keymap' not in daconfig:
            daconfig['keymap'] = 'vim'
    s3_config = daconfig.get('s3', None)
    if not s3_config or ('enable' in s3_config and not s3_config['enable']): # or not ('access key id' in s3_config and s3_config['access key id']) or not ('secret access key' in s3_config and s3_config['secret access key']):
        S3_ENABLED = False
    else:
        S3_ENABLED = True
    gc_config = daconfig.get('google cloud', None)
    if not gc_config or ('enable' in gc_config and not gc_config['enable']) or not ('access key id' in gc_config and gc_config['access key id']) or not ('secret access key' in gc_config and gc_config['secret access key']):
        GC_ENABLED = False
    else:
        GC_ENABLED = True
    if 'db' not in daconfig:
        daconfig['db'] = dict(name="docassemble", user="docassemble", password="abc123")
    dbtableprefix = daconfig['db'].get('table prefix', None)
    if not dbtableprefix:
        dbtableprefix = ''
    if daconfig.get('ec2', False):
        h = httplib2.Http()
        resp, content = h.request(daconfig.get('ec2 ip url', "http://169.254.169.254/latest/meta-data/local-hostname"), "GET")
        if resp['status'] and int(resp['status']) == 200:
            hostname = content
        else:
            sys.stderr.write("Could not get hostname from ec2\n")
            sys.exit(1)
    else:
        hostname = os.getenv('SERVERHOSTNAME', socket.gethostname())
    if S3_ENABLED:
        import docassemble.webapp.amazon
        s3 = docassemble.webapp.amazon.s3object(s3_config)
        if 'host' not in daconfig['db'] or daconfig['db']['host'] is None:
            key = s3.get_key('hostname-sql')
            if key.exists():
                the_host = key.get_contents_as_string()
                if the_host == hostname:
                    daconfig['db']['host'] = 'localhost'
                else:
                    daconfig['db']['host'] = the_host
        if 'log server' not in daconfig or daconfig['log server'] is None:
            key = s3.get_key('hostname-log')
            if key.exists():
                the_host = key.get_contents_as_string()
                if the_host == hostname:
                    daconfig['log server'] = 'localhost'
                else:
                    daconfig['log server'] = the_host
        if 'redis' not in daconfig or daconfig['redis'] is None:
            key = s3.get_key('hostname-redis')
            if key.exists():
                the_host = key.get_contents_as_string()
                if the_host == hostname:
                    the_host = 'localhost'
                daconfig['redis'] = 'redis://' + the_host
        if 'rabbitmq' not in daconfig or daconfig['rabbitmq'] is None:
            key = s3.get_key('hostname-rabbitmq')
            if key.exists():
                the_host = key.get_contents_as_string()
                daconfig['rabbitmq'] = 'pyamqp://guest@' + str(the_host) + '//'
    if daconfig['db'].get('host', None) is None or daconfig['db'].get('host', '') == '':
        daconfig['db']['host'] = 'localhost'
    if daconfig['db'].get('name', None) is None or daconfig['db'].get('name', '') == '':
        daconfig['db']['name'] = 'docassemble'
    if daconfig['db'].get('user', None) is None or daconfig['db'].get('user', '') == '':
        daconfig['db']['user'] = 'docassemble'
    if daconfig['db'].get('password', None) is None or daconfig['db'].get('password', '') == '':
        daconfig['db']['password'] = 'abc123'
    if daconfig['db'].get('port', None) is None or daconfig['db'].get('port', '') == '':
        daconfig['db']['port'] = '5432'
    if 'ocr languages' not in daconfig or type(daconfig['ocr languages']) is not dict:
        daconfig['ocr languages'] = dict()
    if 'en' not in daconfig['ocr languages']:
        daconfig['ocr languages']['en'] = 'eng'
    if 'es' not in daconfig['ocr languages']:
        daconfig['ocr languages']['es'] = 'spa'
    loaded = True
    return

def default_config():
    config = """\
secretkey: """ + random_string(32) + """
mail:
  default sender: '"Administrator" <no-reply@example.com>'
"""
    return config