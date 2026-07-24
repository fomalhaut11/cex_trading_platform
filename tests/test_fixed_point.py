from decimal import Decimal
from unittest import TestCase

from cex_quant.core import Price, Quantity


class FixedPointTest(TestCase):
    def test_parses_decimal_without_float(self) -> None:
        price = Price.from_str("67432.1500")

        self.assertEqual(price.raw, 674_321_500)
        self.assertEqual(price.scale, 4)
        self.assertEqual(price.as_decimal(), Decimal("67432.1500"))
        self.assertEqual(str(price), "67432.1500")

    def test_exact_rescale_preserves_nominal_type(self) -> None:
        quantity = Quantity.from_str("1.25")

        result = quantity.rescale_exact(4)

        self.assertIsInstance(result, Quantity)
        self.assertEqual(result, Quantity(raw=12_500, scale=4))

    def test_rescale_rejects_precision_loss(self) -> None:
        with self.assertRaisesRegex(ValueError, "lose precision"):
            Price.from_str("1.25").rescale_exact(1)

    def test_non_finite_and_negative_scale_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            Price.from_str("NaN")
        with self.assertRaisesRegex(ValueError, "non-negative"):
            Price(raw=1, scale=-1)


if __name__ == "__main__":
    import unittest

    unittest.main()

