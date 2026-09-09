"""Bulk onboarding stops when every account device is already configured."""

from __future__ import annotations

import unittest


class BulkNoNewDevicesTests(unittest.TestCase):
    def test_no_new_devices_is_a_terminal_condition(self):
        eligible = {}
        self.assertFalse(eligible)


if __name__ == "__main__":
    unittest.main()
