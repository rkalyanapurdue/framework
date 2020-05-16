# this script is the primary job execution script used by the workflow engine
# arguments to the script include the workflow filename, workflow stage to be executed,
# a set of variable bindings encoded as a JSON string, a set of stage reference bindings
# encoded as a JSON string, the target path for the current stage, the name of the file
# that stores the names of outputs generated by filter plugins, and overrides for
# arguments that refer to local files on submit host

from geoedfframework.GeoEDFExecutor import GeoEDFExecutor

import sys
import os
import json
import base64

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

arg_count = len(sys.argv)

# extract command line arguments

# make sure the required arguments have been provided
if arg_count < 9:
    raise Exception("Incorrect number of arguments provided")

workflow_fname = str(sys.argv[1])
workflow_stage = '$%s' % str(sys.argv[2])
output_path = str(sys.argv[4])
var_bindings_str = str(sys.argv[6])
stage_refs_str = str(sys.argv[7])
encrypted_args_str = str(sys.argv[8])
args_overridden_str = str(sys.argv[9])

# arg overrides are meant to provide input file paths corresponding to files
# on the submit host. Since these file paths are only determined during
# execution, we cannot pass this in as a json k-v pair
# instead these files will be provided as the argument tail to the job
# in addition, a comma separated set of args being overriden is provided
# need to construct the JSON here before invoking the executor

# parse comma separated args_overridden_str
if args_overridden_str != 'None':
    overridden_args = args_overridden_str.split(',')

    # validate
    if len(overridden_args) != (arg_count - 10):
        raise Exception('overridden args and override values do not match')

    # create json str
    overrides = dict()
    for indx in range(0,arg_count - 10):
        overrides[overridden_args[indx]] = str(sys.argv[10 + indx])

    arg_overrides_str = json.dumps(overrides)
else:
    arg_overrides_str = 'None'

# decrypt the encrypted args and create a new dictionary
if encrypted_args_str != 'None':
    encrypted_args = json.loads(encrypted_args_str)
    decrypted_args = dict()
    # get the top level job directory, private key is stored here
    job_dir = os.path.dirname(output_path)
    private_key_filename = '%s/private.pem' % job_dir
    with open(private_key_filename,'rb') as key_file:
        private_key = serialization.load_pem_private_key(
                        key_file.read(),
                        password=None,
                        backend=default_backend())

        for arg in encrypted_args:

            # first decode the base64 encoding
            encrypted_val = base64.decodestring(bytes(encrypted_args[arg],'ascii'))
            
            decrypted_val = private_key.decrypt(
                encrypted_val,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None))
            decrypted_args[arg] = decrypted_val.decode('utf-8')
    decrypted_args_str = json.dumps(decrypted_args)
else:
    decrypted_args_str = 'None'
            
# create instance of executor
executor = GeoEDFExecutor(workflow_fname, workflow_stage, output_path, var_bindings_str, stage_refs_str, decrypted_args_str, arg_overrides_str)

# execute this workflow stage
executor.bind_and_execute()

# check if we need to return anything (status etc.)
