"""Test the module `aws_orga_deployer.utils`."""

# COMPLETED
import unittest

from aws_orga_deployer import utils


class TestExecMultithread(unittest.TestCase):
    """Test the function `exec_multithread`."""

    def test_exec_multithread_ok(self):
        """Check that the function `exec_multithread` works as expected."""
        input_list = range(10)
        result = []

        def func(value):
            result.append(value)

        utils.exec_multithread(input_list, func, 5)
        self.assertCountEqual(input_list, result)

    def test_exec_multithread_exception(self):
        """Check that exception raised by the threads are propagated to the
        parent thread.
        """

        def func(value):
            raise RuntimeError()

        with self.assertRaises(RuntimeError):
            utils.exec_multithread(range(10), func, 5)
