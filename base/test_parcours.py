from django.test import TestCase
from base.services import phone


class PhoneNormalizeTest(TestCase):
    def test_benin_local_number_normalizes_to_e164(self):
        # Bénin : numéros à 10 chiffres depuis 2023 (préfixe 01)
        self.assertEqual(phone.normalize("0197000000", "BJ"), "+2290197000000")

    def test_number_with_plus_prefix_is_accepted(self):
        self.assertEqual(phone.normalize("+2290197000000", "BJ"), "+2290197000000")

    def test_france_number(self):
        self.assertEqual(phone.normalize("0612345678", "FR"), "+33612345678")

    def test_invalid_number_raises(self):
        with self.assertRaises(ValueError):
            phone.normalize("123", "BJ")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            phone.normalize("", "BJ")

    def test_is_valid_wrapper(self):
        self.assertTrue(phone.is_valid("0197000000", "BJ"))
        self.assertFalse(phone.is_valid("123", "BJ"))

    def test_countries_benin_first(self):
        self.assertEqual(phone.COUNTRIES[0]["iso2"], "BJ")
        self.assertEqual(phone.COUNTRIES[0]["dial"], "+229")
