"""Tests for LocalTuya number scaling."""

import unittest

from custom_components.localtuya.number import (
    _scale_number_value,
    _unscale_number_value,
)


class NumberScalingTests(unittest.TestCase):
    """Test raw/native number conversion."""

    def test_scale_tenths(self):
        self.assertEqual(
            _scale_number_value(
                225,
                0.1,
            ),
            22.5,
        )

    def test_unscale_tenths(self):
        self.assertEqual(
            _unscale_number_value(
                22.5,
                0.1,
            ),
            225,
        )

    def test_negative_roundtrip(self):
        native = _scale_number_value(
            -30,
            0.1,
        )

        self.assertEqual(
            native,
            -3.0,
        )

        self.assertEqual(
            _unscale_number_value(
                native,
                0.1,
            ),
            -30,
        )

    def test_unscaled_integer(self):
        self.assertEqual(
            _unscale_number_value(
                42,
                1.0,
            ),
            42,
        )


if __name__ == "__main__":
    unittest.main()
