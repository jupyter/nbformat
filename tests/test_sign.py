"""Test Notebook signing"""

# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.
from __future__ import annotations

import codecs
import copy
import os
import shutil
import sys
import tempfile
import time
import unittest
import warnings
from subprocess import PIPE, Popen

import pytest
import testpath
from traitlets.config import Config

from nbformat import read, sign, write

from .base import TestsBase


class TestNotary(TestsBase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()
        self.notary = sign.NotebookNotary(
            db_file=":memory:",
            secret=b"secret",
            data_dir=self.data_dir,
        )
        self.notary.__enter__()
        with self.fopen("test3.ipynb", "r") as f:
            self.nb = read(f, as_version=4)
        with self.fopen("test3.ipynb", "r") as f:
            self.nb3 = read(f, as_version=3)

    def tearDown(self):
        self.notary.__exit__(None, None, None)
        shutil.rmtree(self.data_dir)

    def test_invalid_db_file(self):
        invalid_sql_file = os.path.join(self.data_dir, "invalid_db_file.db")
        with open(invalid_sql_file, "w", encoding="utf-8") as tempfile:
            tempfile.write("[invalid data]")

        invalid_notary = sign.NotebookNotary(
            db_file=invalid_sql_file,
            secret=b"secret",
        )
        with invalid_notary.open_session() as session:
            session.sign(self.nb)
        invalid_notary.close()

        testpath.assert_isfile(os.path.join(self.data_dir, invalid_sql_file))
        testpath.assert_isfile(os.path.join(self.data_dir, invalid_sql_file + ".bak"))

    def test_not_using_context_manager_warns(self):
        """Using the store without entering the notary as a context manager warns once."""
        notary = sign.NotebookNotary(
            db_file=":memory:",
            secret=b"secret",
            data_dir=self.data_dir,
        )
        try:
            with pytest.warns(PendingDeprecationWarning, match="context manager"):
                notary.sign(self.nb)
            # only warns once per instance
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                notary.check_signature(self.nb)
        finally:
            notary.close()

    def test_using_context_manager_does_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with sign.NotebookNotary(
                db_file=":memory:",
                secret=b"secret",
                data_dir=self.data_dir,
            ) as notary:
                notary.sign(self.nb)
                self.assertTrue(notary.check_signature(self.nb))

    def test_open_session(self):
        db_file = os.path.join(self.data_dir, "sessions.db")
        notary = sign.NotebookNotary(db_file=db_file, secret=b"secret", data_dir=self.data_dir)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with notary.open_session() as session:
                self.assertFalse(session.check_signature(self.nb))
                session.sign(self.nb)
                self.assertTrue(session.check_signature(self.nb))
            # the notary is reusable: a later session sees the persisted signature
            with notary.open_session() as session:
                self.assertTrue(session.check_signature(self.nb))
        notary.close()

    def test_sessions_are_independent(self):
        """Each session owns its own store; closing one leaves the others alone."""
        db_file = os.path.join(self.data_dir, "nested.db")
        notary = sign.NotebookNotary(db_file=db_file, secret=b"secret", data_dir=self.data_dir)
        with notary.open_session() as outer:
            outer.sign(self.nb)
            with notary.open_session() as inner:
                self.assertIsNot(inner._store, outer._store)
                self.assertTrue(inner.check_signature(self.nb))
            # closing the inner session must not disturb the outer one
            self.assertTrue(outer.check_signature(self.nb))
        notary.close()

    def test_session_public_api(self):
        """A session exposes its operations and nothing else: no store, no close."""
        notary = sign.NotebookNotary(db_file=":memory:", secret=b"secret", data_dir=self.data_dir)
        with notary.open_session() as session:
            self.assertEqual(
                sorted(name for name in dir(session) if not name.startswith("_")),
                [
                    "check_cells",
                    "check_signature",
                    "compute_signature",
                    "mark_cells",
                    "sign",
                    "unsign",
                ],
            )
        notary.close()

    def test_session_snapshots_secret(self):
        """A session keeps the secret it was opened with; the notary can change under it."""
        notary = sign.NotebookNotary(db_file=":memory:", secret=b"secret", data_dir=self.data_dir)
        with notary.open_session() as session:
            before = session.compute_signature(self.nb)
            notary.secret = b"different"
            self.assertEqual(session.compute_signature(self.nb), before)
        # a later session picks the new secret up
        with notary.open_session() as session:
            self.assertNotEqual(session.compute_signature(self.nb), before)
        notary.close()

    def test_session_snapshots_algorithm(self):
        """The algorithm a session was opened with drives its digest."""
        notary = sign.NotebookNotary(db_file=":memory:", secret=b"secret", data_dir=self.data_dir)
        with notary.open_session() as session:
            sha256 = session.compute_signature(self.nb)
            notary.algorithm = "sha512"
            self.assertEqual(session.compute_signature(self.nb), sha256)
        with notary.open_session() as session:
            sha512 = session.compute_signature(self.nb)
        self.assertEqual(len(sha256), 64)
        self.assertEqual(len(sha512), 128)
        notary.close()

    def test_session_cell_helpers(self):
        """mark_cells/check_cells are available on the session and actually work."""
        notary = sign.NotebookNotary(db_file=":memory:", secret=b"secret", data_dir=self.data_dir)
        with notary.open_session() as session:
            session.mark_cells(self.nb, False)
            self.assertFalse(session.check_cells(self.nb))
            session.mark_cells(self.nb, True)
            self.assertTrue(session.check_cells(self.nb))
        notary.close()

    def test_direct_calls_share_one_store(self):
        """The non-session API keeps using a single store across calls."""
        stores = []

        def factory():
            stores.append(sign.MemorySignatureStore())
            return stores[-1]

        notary = sign.NotebookNotary(
            secret=b"secret", data_dir=self.data_dir, store_factory=factory
        )
        with notary:
            notary.sign(self.nb)
            self.assertTrue(notary.check_signature(self.nb))
            notary.unsign(self.nb)
        self.assertEqual(len(stores), 1)

    def test_subclass_hooks_are_honoured(self):
        """Subclasses overriding compute_signature/_check_cell still take effect."""
        calls = []

        class Sub(sign.NotebookNotary):
            def compute_signature(self, nb):
                calls.append("compute_signature")
                return super().compute_signature(nb)

            def _check_cell(self, cell, nbformat_version):
                calls.append("_check_cell")
                return super()._check_cell(cell, nbformat_version)

        notary = Sub(db_file=":memory:", secret=b"secret", data_dir=self.data_dir)
        with notary:
            notary.sign(self.nb)
            self.assertTrue(notary.check_signature(self.nb))
            notary.unsign(self.nb)
            notary.check_cells(self.nb)
        self.assertEqual(calls.count("compute_signature"), 3)
        self.assertIn("_check_cell", calls)

    def test_assigned_store_is_not_closed(self):
        """A store assigned by the caller is owned by the caller."""
        # a real store, whose close() is observable (unlike MemorySignatureStore's)
        store = sign.SQLiteSignatureStore(":memory:")
        notary = sign.NotebookNotary(
            db_file=":memory:",
            secret=b"secret",
            data_dir=self.data_dir,
        )
        notary.store = store
        with notary:
            notary.sign(self.nb)
        notary.close()
        # even an explicit close leaves a caller-owned store alone
        self.assertTrue(store.check_signature(notary.compute_signature(self.nb), "sha256"))
        store.close()

    def test_reusable_after_internal_close(self):
        """Leaving a `with` block closes the store but leaves the notary working."""
        notary = sign.NotebookNotary(
            db_file=":memory:",
            secret=b"secret",
            data_dir=self.data_dir,
        )
        with notary:
            notary.sign(self.nb)
        self.assertIsNone(notary._store)
        # code that goes on using the notary keeps working: a fresh store is
        # created on demand
        with notary:
            self.assertFalse(notary.check_signature(self.nb))
            notary.sign(self.nb)
            self.assertTrue(notary.check_signature(self.nb))

    def test_explicit_close_is_final(self):
        """An explicit close() means done: the store is not re-created."""
        notary = sign.NotebookNotary(
            db_file=":memory:",
            secret=b"secret",
            data_dir=self.data_dir,
        )
        with notary:
            notary.sign(self.nb)
        notary.close()
        with pytest.raises(RuntimeError, match="has been closed"):
            notary.check_signature(self.nb)
        with pytest.raises(RuntimeError, match="has been closed"):
            _ = notary.store
        # closing twice is harmless, and sessions are unaffected
        notary.close()
        with notary.open_session() as session:
            self.assertFalse(session.check_signature(self.nb))

    def test_store_free_methods_open_no_store(self):
        """compute_signature/mark_cells/check_cells need no store at all."""
        notary = sign.NotebookNotary(db_file=":memory:", secret=b"secret", data_dir=self.data_dir)
        notary.compute_signature(self.nb)
        notary.mark_cells(self.nb, True)
        notary.check_cells(self.nb)
        self.assertIsNone(notary._store)

    def test_algorithms(self):
        last_sig = ""
        for algo in sign.algorithms:
            self.notary.algorithm = algo
            sig = self.notary.compute_signature(self.nb)
            self.assertNotEqual(last_sig, sig)
            last_sig = sig

    def test_sign_same(self):
        """Multiple signatures of the same notebook are the same"""
        sig1 = self.notary.compute_signature(self.nb)
        sig2 = self.notary.compute_signature(self.nb)
        self.assertEqual(sig1, sig2)

    def test_change_secret(self):
        """Changing the secret changes the signature"""
        sig1 = self.notary.compute_signature(self.nb)
        self.notary.secret = b"different"
        sig2 = self.notary.compute_signature(self.nb)
        self.assertNotEqual(sig1, sig2)

    def test_sign(self):
        self.assertFalse(self.notary.check_signature(self.nb))
        self.notary.sign(self.nb)
        self.assertTrue(self.notary.check_signature(self.nb))

    def test_unsign(self):
        self.notary.sign(self.nb)
        self.assertTrue(self.notary.check_signature(self.nb))
        self.notary.unsign(self.nb)
        self.assertFalse(self.notary.check_signature(self.nb))
        self.notary.unsign(self.nb)
        self.assertFalse(self.notary.check_signature(self.nb))

    def test_cull_db(self):
        # this test has various sleeps of 2ms
        # to ensure low resolution timestamps compare as expected
        dt = 2e-3
        nbs = [copy.deepcopy(self.nb) for i in range(10)]
        for row in self.notary.store.db.execute("SELECT * FROM nbsignatures"):
            print(row)
        self.notary.store.cache_size = 8
        for i, nb in enumerate(nbs[:8]):
            nb.metadata.dirty = i
            self.notary.sign(nb)

        for i, nb in enumerate(nbs[:8]):
            time.sleep(dt)
            self.assertTrue(self.notary.check_signature(nb), "nb %i is trusted" % i)

        # signing the 9th triggers culling of first 3
        # (75% of 8 = 6, 9 - 6 = 3 culled)
        self.notary.sign(nbs[8])
        self.assertFalse(self.notary.check_signature(nbs[0]))
        self.assertFalse(self.notary.check_signature(nbs[1]))
        self.assertFalse(self.notary.check_signature(nbs[2]))
        self.assertTrue(self.notary.check_signature(nbs[3]))
        # checking nb3 should keep it from being culled:
        self.notary.sign(nbs[0])
        self.notary.sign(nbs[1])
        self.notary.sign(nbs[2])
        self.assertTrue(self.notary.check_signature(nbs[3]))
        self.assertFalse(self.notary.check_signature(nbs[4]))

    def test_check_signature(self):
        nb = self.nb
        md = nb.metadata
        notary = self.notary
        check_signature = notary.check_signature
        # no signature:
        md.pop("signature", None)
        self.assertFalse(check_signature(nb))
        # hash only, no algo
        md.signature = notary.compute_signature(nb)
        self.assertFalse(check_signature(nb))
        # proper signature, algo mismatch
        notary.algorithm = "sha224"
        notary.sign(nb)
        notary.algorithm = "sha256"
        self.assertFalse(check_signature(nb))
        # check correctly signed notebook
        notary.sign(nb)
        self.assertTrue(check_signature(nb))

    def test_mark_cells_untrusted(self):
        cells = self.nb.cells
        self.notary.mark_cells(self.nb, False)
        for cell in cells:
            self.assertNotIn("trusted", cell)
            if cell.cell_type == "code":
                self.assertIn("trusted", cell.metadata)
                self.assertFalse(cell.metadata.trusted)
            else:
                self.assertNotIn("trusted", cell.metadata)

    def test_mark_cells_trusted(self):
        cells = self.nb.cells
        self.notary.mark_cells(self.nb, True)
        for cell in cells:
            self.assertNotIn("trusted", cell)
            if cell.cell_type == "code":
                self.assertIn("trusted", cell.metadata)
                self.assertTrue(cell.metadata.trusted)
            else:
                self.assertNotIn("trusted", cell.metadata)

    def test_check_cells(self):
        nb = self.nb
        self.notary.mark_cells(nb, True)
        self.assertTrue(self.notary.check_cells(nb))
        for cell in nb.cells:
            self.assertNotIn("trusted", cell)
        self.notary.mark_cells(nb, False)
        self.assertFalse(self.notary.check_cells(nb))
        for cell in nb.cells:
            self.assertNotIn("trusted", cell)

    def test_trust_no_output(self):
        nb = self.nb
        self.notary.mark_cells(nb, False)
        for cell in nb.cells:
            if cell.cell_type == "code":
                cell.outputs = []
        self.assertTrue(self.notary.check_cells(nb))

    def test_mark_cells_untrusted_v3(self):
        nb = self.nb3
        cells = nb.worksheets[0].cells
        self.notary.mark_cells(nb, False)
        for cell in cells:
            self.assertNotIn("trusted", cell)
            if cell.cell_type == "code":
                self.assertIn("trusted", cell.metadata)
                self.assertFalse(cell.metadata.trusted)
            else:
                self.assertNotIn("trusted", cell.metadata)

    def test_mark_cells_trusted_v3(self):
        nb = self.nb3
        cells = nb.worksheets[0].cells
        self.notary.mark_cells(nb, True)
        for cell in cells:
            self.assertNotIn("trusted", cell)
            if cell.cell_type == "code":
                self.assertIn("trusted", cell.metadata)
                self.assertTrue(cell.metadata.trusted)
            else:
                self.assertNotIn("trusted", cell.metadata)

    def test_check_cells_v3(self):
        nb = self.nb3
        cells = nb.worksheets[0].cells
        self.notary.mark_cells(nb, True)
        self.assertTrue(self.notary.check_cells(nb))
        for cell in cells:
            self.assertNotIn("trusted", cell)
        self.notary.mark_cells(nb, False)
        self.assertFalse(self.notary.check_cells(nb))
        for cell in cells:
            self.assertNotIn("trusted", cell)

    def test_sign_stdin(self):
        def sign_stdin(nb):
            env = os.environ.copy()
            env["JUPYTER_DATA_DIR"] = self.data_dir
            p = Popen(
                [sys.executable, "-m", "nbformat.sign", "--log-level=0"],
                stdin=PIPE,
                stdout=PIPE,
                env=env,
            )
            assert p.stdin is not None
            write(nb, codecs.getwriter("utf8")(p.stdin))
            p.stdin.close()
            p.wait()
            self.assertEqual(p.returncode, 0)
            assert p.stdout is not None
            out = p.stdout.read().decode("utf8", "replace")
            p.stdout.close()
            return out

        out = sign_stdin(self.nb3)
        self.assertIn("Signing notebook: <stdin>", out)
        out = sign_stdin(self.nb3)
        self.assertIn("already signed: <stdin>", out)

    def test_trust_reset(self):
        """`jupyter trust --reset` deletes the cache without reopening it."""
        app = sign.TrustNotebookApp(data_dir=self.data_dir)
        app.notary = sign.NotebookNotary(
            db_file=os.path.join(self.data_dir, "reset.db"),
            secret_file=os.path.join(self.data_dir, "reset_secret"),
            data_dir=self.data_dir,
        )
        with app.notary.open_session() as session:
            session.sign(self.nb)
        testpath.assert_isfile(app.notary.db_file)

        app.reset = True
        app.start()

        testpath.assert_not_path_exists(app.notary.db_file)
        # the store must not have been reopened, which would recreate the file
        self.assertIsNone(app.notary._store)


def test_config_store():
    store = sign.MemorySignatureStore()

    c = Config()
    c.NotebookNotary.store_factory = lambda: store
    notary = sign.NotebookNotary(config=c)
    assert notary.store is store


class SignatureStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = sign.MemorySignatureStore()

    def tearDown(self):
        # SQLiteSignatureStore (the subclass below) holds a real connection.
        # Leaving it for the garbage collector means Python 3.13+ reports the
        # finalization as an unraisable exception, which surfaces as a
        # PytestUnraisableExceptionWarning inside whichever unrelated test
        # happens to be running when the collection occurs -- and
        # `filterwarnings = ["error"]` turns that into a failure.
        self.store.close()

    def test_basics(self):
        digest = "0123457689abcef"
        algo = "fake_sha"
        assert not self.store.check_signature(digest, algo)
        self.store.store_signature(digest, algo)
        assert self.store.check_signature(digest, algo)
        self.store.remove_signature(digest, algo)
        assert not self.store.check_signature(digest, algo)


class SQLiteSignatureStoreTests(SignatureStoreTests):
    def setUp(self):
        self.store = sign.SQLiteSignatureStore(":memory:")  # type:ignore[assignment]
