"""
.. autoclass:: server.tests.processor.base.BaseProcessorTestCase
   :members:

"""
from __future__ import print_function

import hashlib
import gzip
import os
import shutil

from django.conf import settings
from django.core import management
from django.test import TestCase

from genesis.models import GenUser
from server.models import Data, Storage, Processor, dict_dot
from ..unit.utils import create_admin, create_test_case


PROCESSORS_FIXTURE_CACHE = None


def _register_processors():
    """Register processors.

    Processor definitions are red when the first test is callled and cached
    into the PROCESSORS_FIXTURE_CACHE global variable.

    """
    Processor.objects.delete()

    global PROCESSORS_FIXTURE_CACHE  # pylint: disable=global-statement
    if PROCESSORS_FIXTURE_CACHE:
        Processor.objects.insert(PROCESSORS_FIXTURE_CACHE)
    else:
        if len(GenUser.objects.filter(is_superuser=True)) == 0:
            GenUser.objects.create_superuser(email='admin@genialis.com')

        management.call_command('register', force=True, verbosity='0')
        PROCESSORS_FIXTURE_CACHE = Processor.objects.all()
        for p in PROCESSORS_FIXTURE_CACHE:
            # Trick Mongoengine not to fail the insert
            p._created = True  # pylint: disable=protected-access


class BaseProcessorTestCase(TestCase):

    """Base class for writing processor tests.

    This class is subclass of Django's ``TestCase`` with some specific
    functions used for testing processors.

    To write a processor test use standard Django's syntax for writing
    tests and follow next steps:

    #. Put input files (if any) in ``server/tests/processor/inputs``
       folder.
    #. Run test with :func:`run_processor`.
    #. Check if processor has finished successfully with
       :func:`assertDone` function.
    #. Assert processor's output with :func:`assertFiles`,
       :func:`assertFields` and :func:`assertJSON` functions.

    .. DANGER::
        If output files doesn't exists in
        ``server/tests/processor/outputs`` folder, they are created
        automatically. But you have to chack that they are correct
        before using them for further runs.

    """

    def setUp(self):
        super(BaseProcessorTestCase, self).setUp()
        self.admin = create_admin()
        _register_processors()

        self.case = create_test_case(self.admin.pk)['c1']
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self._keep_all = False
        self._keep_failed = False

    def tearDown(self):
        super(BaseProcessorTestCase, self).tearDown()

        # Delete Data objects and their files unless keep_failed
        for d in Data.objects.all():
            if self._keep_all or (self._keep_failed and d.status == "error"):
                print("KEEPING DATA: {}".format(d.pk))
            else:
                data_dir = os.path.join(settings.DATAFS['data_path'], str(d.pk))
                d.delete()
                shutil.rmtree(data_dir, ignore_errors=True)

    def keep_all(self):
        self._keep_all = True

    def keep_failed(self):
        self._keep_failed = True

    def assertStatus(self, obj, status):  # pylint: disable=invalid-name
        """Check if Data object's status is 'status'.

        :param obj: Data object for which to check status
        :type obj: :obj:`server.models.Data`
        :param status: Data status to check
        :type status: str

        """
        self.assertEqual(obj.status, status, msg="Data status != '{}'".format(status) + self._msg_stdout(obj))

    def assertFields(self, obj, path, value):  # pylint: disable=invalid-name
        """Compare Data object's field to given value.

        :param obj: Data object with field to compare
        :type obj: :obj:`server.models.Data`

        :param path: Path to field in Data object.
        :type path: :obj:`str`

        :param value: Desired value.
        :type value: :obj:`str`

        """
        field = self._get_field(obj['output'], path)
        self.assertEqual(field, str(value),
                         msg="Field 'output.{}' mismatch: {} != {}".format(path, field, str(value)) +
                         self._msg_stdout(obj))

    def assertFiles(self, obj, field_path, fn, gzipped=False):  # pylint: disable=invalid-name
        """Compare output file of a processor to the given correct file.

        :param obj: Data object which includes file that we want to
            compare.
        :type obj: :obj:`server.models.Data`

        :param field_path: Path to file name in Data object.
        :type field_path: :obj:`str`

        :param fn: File name (and relative path) of file to which we
            want to compare. Name/path is relative to
            'server/tests/processor/outputs'.
        :type fn: :obj:`str`

        :param gzipped: If true, file is unziped before comparison.
        :type gzipped: :obj:`bool`

        """
        field = self._get_field(obj['output'], field_path)
        output = os.path.join(settings.DATAFS['data_path'], str(obj.pk), field['file'])
        output_file = gzip.open(output, 'rb') if gzipped else open(output)
        output_hash = hashlib.sha256(output_file.read()).hexdigest()

        wanted = os.path.join(self.current_path, 'outputs', fn)

        if not os.path.isfile(wanted):
            shutil.copyfile(output, wanted)
            self.fail(msg="Output file {} missing so it was created.".format(fn))

        wanted_file = gzip.open(wanted, 'rb') if gzipped else open(wanted)
        wanted_hash = hashlib.sha256(wanted_file.read()).hexdigest()
        self.assertEqual(wanted_hash, output_hash,
                         msg="File hash mismatch: {} != {}".format(wanted_hash, output_hash) + self._msg_stdout(obj))

    def assertJSON(self, obj, storage, field_path, fn):  # pylint: disable=invalid-name
        """Compare JSON in Storage object to the given correct output.

        :param obj: Data object which includes file that we want to
            compare.
        :type obj: :obj:`server.models.Data`

        :param storage: Storage (or storage id) which contains JSON to
            compare.
        :type storage: :obj:`server.models.Storage` or :obj:`str`

        :param field_path: Path to JSON subset to compare in Storage
            object. If it is empty, entire Storage object will be
            compared.
        :type field_path: :obj:`str`

        :param fn: File name (and relative path) of file to which we
            want to compare. Name/path is relative to
            'server/tests/processor/outputs'.
        :type fn: :obj:`str`

        """
        if not isinstance(storage, Storage):
            storage = Storage.objects.get(pk=str(storage))

        field = str(self._get_field(storage['json'], field_path))
        field_hash = hashlib.sha256(field).hexdigest()

        wanted = os.path.join(self.current_path, 'outputs', fn)

        if not os.path.isfile(wanted):
            with open(wanted, 'w') as fn:
                fn.write(field)

            self.fail(msg="Output file {} missing so it was created.".format(fn))

        wanted_hash = hashlib.sha256(open(wanted).read()).hexdigest()
        self.assertEqual(wanted_hash, field_hash,
                         msg="JSON hash mismatch: {} != {}".format(wanted_hash, field_hash) + self._msg_stdout(obj))

    def _get_field(self, obj, path):
        """Get field value ``path`` in multilevel dict ``obj``."""
        return dict_dot(obj, path)

    def _msg_stdout(self, data):
        """Print stdout.txt content."""
        msg = "\n\nDump stdout.txt:\n\n"
        stdout = os.path.join(settings.DATAFS['data_path'], str(data.pk), 'stdout.txt')
        if os.path.isfile(stdout):
            with open(stdout, 'r') as fn:
                msg += fn.read()

        return msg
