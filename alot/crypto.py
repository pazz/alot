from helper import call_cmd
import tempfile
import os


#field descriptors for output of `gpg --with-colons`
keys = [
    'type', 'trust', 'length', 'algorithm', 'key_id', 'creation_date',
    'expiration_date', 'serial_number', 'ownertrust', 'user_id',
    'signature_class', 'capabilities', 'cfingerprint', 'flag',
    'token_serial_number'
]


def get_gpg_output(arglist):
    out, err, rval = call_cmd(['gpg', '--with-colons'] + arglist)
    keydicts = []
    for line in out.strip().split('\n'):
        keydicts.append(dict(zip(keys, line.split(':'))))
    return keydicts


def get_private_keys():
    entries = get_gpg_output(['--list-secret-keys'])
    return [e for e in entries if e['type'] == 'sec']


def get_public_keys():
    entries = get_gpg_output(['--list-keys'])
    return [e for e in entries if e['type'] == 'pub']


def verify(blob, sig):
    """call gnupg to verify content string blob agains signature string sig"""
    sigfile = tempfile.NamedTemporaryFile(delete=False, suffix='.sig')
    sigfile.write(sig)
    sigfile.close()

    out, err, rval = call_cmd(['gpg', '--verify', sigfile.name, '-'],
                              stdin=blob)

    os.unlink(sigfile.name)
    return err, rval
