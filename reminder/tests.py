#from django.test import TestCase
#
#
#class SimpleTest(TestCase):
#    def test_basic_addition(self):
#        """
#        Tests that 1 + 1 always equals 2.
#        """
#        self.assertEqual(1 + 1, 2)


import unittest
from rapidsms.tests.scripted import TestScript

class TestRegister(TestScript):

    def testRegister(self):
        self.assertInteraction("""
            0266688209 > 
            0266688209 < Thank you for registering!
        """)