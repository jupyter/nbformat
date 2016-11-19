"""Utilities for signing notebooks"""

# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.

import base64
from contextlib import contextmanager
import hashlib
from hmac import HMAC
import io
import os
import sys
import time
import warnings

import errno

try:
    import sqlite3
except ImportError:
    try:
        from pysqlite2 import dbapi2 as sqlite3
    except ImportError:
        sqlite3 = None

from ipython_genutils.py3compat import unicode_type, cast_bytes, cast_unicode
from traitlets import (
    Instance, Bytes, Enum, Any, Unicode, Bool, Integer,
    default, observe,
)
from traitlets.config import LoggingConfigurable, MultipleInstanceError
from jupyter_core.application import JupyterApp, base_flags

from . import read, reads, NO_CONVERT, __version__

try:
    # Python 3
    algorithms = hashlib.algorithms_guaranteed
    # shake algorithms in py36 are not compatible with hmac
    # due to required length argument in digests
    algorithms = [ a for a in algorithms if not a.startswith('shake_') ]
except AttributeError:
    algorithms = hashlib.algorithms


def yield_everything(obj):
    """Yield every item in a container as bytes
    
    Allows any JSONable object to be passed to an HMAC digester
    without having to serialize the whole thing.
    """
    if isinstance(obj, dict):
        for key in sorted(obj):
            value = obj[key]
            yield cast_bytes(key)
            for b in yield_everything(value):
                yield b
    elif isinstance(obj, (list, tuple)):
        for element in obj:
            for b in yield_everything(element):
                yield b
    elif isinstance(obj, unicode_type):
        yield obj.encode('utf8')
    else:
        yield unicode_type(obj).encode('utf8')

def yield_code_cells(nb):
    """Iterator that yields all cells in a notebook
    
    nbformat version independent
    """
    if nb.nbformat >= 4:
        for cell in nb['cells']:
            if cell['cell_type'] == 'code':
                yield cell
    elif nb.nbformat == 3:
        for ws in nb['worksheets']:
            for cell in ws['cells']:
                if cell['cell_type'] == 'code':
                    yield cell

@contextmanager
def signature_removed(nb):
    """Context manager for operating on a notebook with its signature removed
    
    Used for excluding the previous signature when computing a notebook's signature.
    """
    save_signature = nb['metadata'].pop('signature', None)
    try:
        yield
    finally:
        if save_signature is not None:
            nb['metadata']['signature'] = save_signature


class FilenamesHashSet(object):
    def __init__(self, directory):
        self.directory = directory

    def _dir_and_file(self, hexdigest):
        return os.path.join(self.directory, hexdigest[0:2]), hexdigest[2:]

    def add(self, hexdigest):
        """Add a hash to the set if it's not already present."""
        dir, file_name = self._dir_and_file(hexdigest)
        try:
            os.makedirs(dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        with open(os.path.join(dir, file_name), 'wb'): pass

    def discard(self, hexdigest):
        """Discard a hash from the set; ignore if it's not included."""
        dir, file_name = self._dir_and_file(hexdigest)
        try:
            os.unlink(os.path.join(dir, file_name))
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    def __contains__(self, hexdigest):
        dir, file_name = self._dir_and_file(hexdigest)
        return os.path.isfile(os.path.join(dir, file_name))

    def check_and_update(self, hexdigest):
        """If a hash is in the set, return True and update its mtime."""
        dir, file_name = self._dir_and_file(hexdigest)
        if os.path.isfile(os.path.join(dir, file_name)):
            os.utime(os.path.join(dir, file_name), None)
            return True
        return False


class NotebookNotary(LoggingConfigurable):
    """A class for computing and verifying notebook signatures."""

    def __init__(self, **kwargs):
        super(NotebookNotary, self).__init__(**kwargs)
        d = os.path.join(self.data_dir, self.algorithm+'_hashes')
        self.hash_store = FilenamesHashSet(d)

        self.migrate_sqlite_to_filenames()
        self.cull_db()
    
    data_dir = Unicode()
    @default('data_dir')
    def _data_dir_default(self):
        app = None
        try:
            if JupyterApp.initialized():
                app = JupyterApp.instance()
        except MultipleInstanceError:
            pass
        if app is None:
            # create an app, without the global instance
            app = JupyterApp()
            app.initialize(argv=[])
        return app.data_dir

    @property
    def cull_marker(self):
        return os.path.join(self.data_dir, 'signatures_cull_time_marker')
    
    db_file = Unicode(
        help="""DEPRECATED: Path to an SQLite file to store notebook signatures.
        The signature mechanism no longer uses SQLite.
        """).tag(config=True)

    @default('db_file')
    def _db_file_default(self):
        if not self.data_dir:
            return ':memory:'
        return os.path.join(self.data_dir, u'nbsignatures.db')

    cache_size = Integer(256**2,
        help="""The number of notebook signatures to cache.
        When the number of signatures exceeds this value,
        the oldest 25% of signatures will be culled.
        """
    ).tag(config=True)

    cull_interval = Integer(60 * 60 * 24 * 30,
        help="""Time in seconds to wait before culling old signatures.
        The default is 30 days.
        """
    ).tag(config=True)

    def _connect_sqlite_database(self):
        if sqlite3 is None:
            self.log.warn("Missing SQLite3, all notebooks will be untrusted!")
            return
        kwargs = dict(detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        try:
            db = sqlite3.connect(self.db_file, **kwargs)
            self.init_db(db)
        except (sqlite3.DatabaseError, sqlite3.OperationalError):
            return None
        return db

    def init_db(self, db):
        db.execute("""
        CREATE TABLE IF NOT EXISTS nbsignatures
        (
            id integer PRIMARY KEY AUTOINCREMENT,
            algorithm text,
            signature text,
            path text,
            last_seen timestamp
        )""")
        db.execute("""
        CREATE INDEX IF NOT EXISTS algosig ON nbsignatures(algorithm, signature)
        """)
        db.commit()
    
    algorithm = Enum(algorithms, default_value='sha256',
        help="""The hashing algorithm used to sign notebooks."""
    ).tag(config=True)
    @observe('algorithm')
    def _algorithm_changed(self, change):
        self.digestmod = getattr(hashlib, change.new)
    
    digestmod = Any()
    @default('digestmod')
    def _digestmod_default(self):
        return getattr(hashlib, self.algorithm)
    
    secret_file = Unicode(
        help="""The file where the secret key is stored."""
    ).tag(config=True)
    @default('secret_file')
    def _secret_file_default(self):
        if not self.data_dir:
            return ''
        return os.path.join(self.data_dir, 'notebook_secret')
    
    secret = Bytes(
        help="""The secret key with which notebooks are signed."""
    ).tag(config=True)
    @default('secret')
    def _secret_default(self):
        # note : this assumes an Application is running
        if os.path.exists(self.secret_file):
            with io.open(self.secret_file, 'rb') as f:
                return f.read()
        else:
            secret = base64.encodestring(os.urandom(1024))
            self._write_secret_file(secret)
            return secret
    
    def _write_secret_file(self, secret):
        """write my secret to my secret_file"""
        self.log.info("Writing notebook-signing key to %s", self.secret_file)
        with io.open(self.secret_file, 'wb') as f:
            f.write(secret)
        try:
            os.chmod(self.secret_file, 0o600)
        except OSError:
            self.log.warn(
                "Could not set permissions on %s",
                self.secret_file
            )
        return secret
    
    def compute_signature(self, nb):
        """Compute a notebook's signature
        
        by hashing the entire contents of the notebook via HMAC digest.
        """
        hmac = HMAC(self.secret, digestmod=self.digestmod)
        # don't include the previous hash in the content to hash
        with signature_removed(nb):
            # sign the whole thing
            for b in yield_everything(nb):
                hmac.update(b)
        
        return hmac.hexdigest()
    
    def check_signature(self, nb):
        """Check a notebook's stored signature
        
        If a signature is stored in the notebook's metadata,
        a new signature is computed and compared with the stored value.
        
        Returns True if the signature is found and matches, False otherwise.
        
        The following conditions must all be met for a notebook to be trusted:
        - a signature is stored in the form 'scheme:hexdigest'
        - the stored scheme matches the requested scheme
        - the requested scheme is available from hashlib
        - the computed hash from notebook_signature matches the stored hash
        """
        if nb.nbformat < 3:
            return False
        signature = self.compute_signature(nb)

        return self.hash_store.check_and_update(signature)
    
    def sign(self, nb):
        """Sign a notebook, indicating that its output is trusted on this machine
        
        Stores hash algorithm and hmac digest in a local database of trusted notebooks.
        """
        if nb.nbformat < 3:
            return
        signature = self.compute_signature(nb)
        self.store_signature(signature, nb)

    def store_signature(self, signature, nb):
        self.hash_store.add(signature)
    
    def unsign(self, nb):
        """Ensure that a notebook is untrusted
        
        by removing its signature from the trusted database, if present.
        """
        signature = self.compute_signature(nb)
        self.hash_store.discard(signature)

    def cull_db(self):
        try:
            last_cull = os.path.getmtime(self.cull_marker)
        except OSError as e:
            if e.errno == errno.ENOENT:
                # Create the cull marker, don't do any cull now
                with open(self.cull_marker, 'wb'): pass
                return
            else:
                raise

        if time.time() - last_cull < self.cull_interval:
            # Wait until a month has elapsed since we last considered culling.
            return

        self.log.info('Counting notebook signature hashes to decide on cull...')
        hash_files = []
        for dirpath, dirnames, filenames in os.walk(self.hash_store.directory):
            for f in filenames:
                full_path = os.path.join(dirpath, f)
                hash_files.append(full_path)

        if len(hash_files) > self.cache_size:
            self.log.info('Culling notebook signature hashes...')
            mtimes_files = []
            for path in hash_files:
                mtimes_files.append((os.path.getmtime(path), path))
            mtimes_files.sort()
            n_cull = len(mtimes_files) // 4
            for _, path in mtimes_files[:n_cull]:
                os.unlink(path)

        # Update the mtime on the cull marker, so we don't check again for
        # another month
        os.utime(self.cull_marker, None)

    
    def mark_cells(self, nb, trusted):
        """Mark cells as trusted if the notebook's signature can be verified
        
        Sets ``cell.metadata.trusted = True | False`` on all code cells,
        depending on whether the stored signature can be verified.
        
        This function is the inverse of check_cells
        """
        if nb.nbformat < 3:
            return
        
        for cell in yield_code_cells(nb):
            cell['metadata']['trusted'] = trusted
    
    def _check_cell(self, cell, nbformat_version):
        """Do we trust an individual cell?
        
        Return True if:
        
        - cell is explicitly trusted
        - cell has no potentially unsafe rich output
        
        If a cell has no output, or only simple print statements,
        it will always be trusted.
        """
        # explicitly trusted
        if cell['metadata'].pop("trusted", False):
            return True
        
        # explicitly safe output
        if nbformat_version >= 4:
            unsafe_output_types = ['execute_result', 'display_data']
            safe_keys = {"output_type", "execution_count", "metadata"}
        else: # v3
            unsafe_output_types = ['pyout', 'display_data']
            safe_keys = {"output_type", "prompt_number", "metadata"}
        
        for output in cell['outputs']:
            output_type = output['output_type']
            if output_type in unsafe_output_types:
                # if there are any data keys not in the safe whitelist
                output_keys = set(output)
                if output_keys.difference(safe_keys):
                    return False
        
        return True
    
    def check_cells(self, nb):
        """Return whether all code cells are trusted
        
        If there are no code cells, return True.
        
        This function is the inverse of mark_cells.
        """
        if nb.nbformat < 3:
            return False
        trusted = True
        for cell in yield_code_cells(nb):
            # only distrust a cell if it actually has some output to distrust
            if not self._check_cell(cell, nb.nbformat):
                trusted = False

        return trusted

    def migrate_sqlite_to_filenames(self):
        marker_file = os.path.join(self.data_dir, 'signatures_migrated_from_sqlite')
        if os.path.isfile(marker_file):
            # Skip if the marker already exists
            return

        db = None
        if os.path.isfile(self.db_file):
            db = self._connect_sqlite_database()
        if db is None:
            # Skip if the sqlite database doesn't exist or can't be read
            with open(marker_file, 'wb'): pass
            return

        self.log.info('Migrating sqlite signatures database to filenames...')
        cur = db.execute("SELECT signature FROM nbsignatures WHERE algorithm = ?",
                         (self.algorithm,))
        for signature, in cur:
            self.store_signature(signature, None)

        # Create the marker file to say that migration is complete
        with open(marker_file, 'wb'):
            pass


trust_flags = {
    'reset' : (
        {'TrustNotebookApp' : { 'reset' : True}},
        """Delete the trusted notebook cache.
        All previously signed notebooks will become untrusted.
        """
    ),
}
trust_flags.update(base_flags)


class TrustNotebookApp(JupyterApp):
    version = __version__
    description="""Sign one or more Jupyter notebooks with your key,
    to trust their dynamic (HTML, Javascript) output.
    
    Otherwise, you will have to re-execute the notebook to see output.
    """
    
    examples = """
    jupyter trust mynotebook.ipynb and_this_one.ipynb
    """
    
    flags = trust_flags
    
    reset = Bool(False,
        help="""If True, delete the trusted signature cache.
        After reset, all previously signed notebooks will become untrusted.
        """
    ).tag(config=True)
    
    notary = Instance(NotebookNotary)
    @default('notary')
    def _notary_default(self):
        return NotebookNotary(parent=self, data_dir=self.data_dir)
    
    def sign_notebook_file(self, notebook_path):
        """Sign a notebook from the filesystem"""
        if not os.path.exists(notebook_path):
            self.log.error("Notebook missing: %s" % notebook_path)
            self.exit(1)
        with io.open(notebook_path, encoding='utf8') as f:
            nb = read(f, NO_CONVERT)
        self.sign_notebook(nb, notebook_path)
    
    def sign_notebook(self, nb, notebook_path='<stdin>'):
        """Sign a notebook that's been loaded"""
        if self.notary.check_signature(nb):
            print("Notebook already signed: %s" % notebook_path)
        else:
            print("Signing notebook: %s" % notebook_path)
            self.notary.sign(nb)
    
    def generate_new_key(self):
        """Generate a new notebook signature key"""
        print("Generating new notebook key: %s" % self.notary.secret_file)
        self.notary._write_secret_file(os.urandom(1024))
    
    def start(self):
        if self.reset:
            if os.path.exists(self.notary.db_file):
                print("Removing trusted signature cache: %s" % self.notary.db_file)
                os.remove(self.notary.db_file)
            self.generate_new_key()
            return
        if not self.extra_args:
            self.log.debug("Reading notebook from stdin")
            nb_s = cast_unicode(sys.stdin.read())
            nb = reads(nb_s, NO_CONVERT)
            self.sign_notebook(nb, '<stdin>')
        else:
            for notebook_path in self.extra_args:
                self.sign_notebook_file(notebook_path)


main = TrustNotebookApp.launch_instance

if __name__ == '__main__':
    main()
