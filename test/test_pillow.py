#unit test to check if PIL works after replacing PIL with Pillow from requirements
from PIL import Image
import unittest

class PillowTest(unittest.TestCase):

    def test_PIL_works(self):
        im = Image.open("test0.png")
        self.assertEqual(im.__class__.__bases__[0].__module__,'PIL.ImageFile' )


if __name__ == '__main__':
    #unittest.main(failfast=True)
    unittest.main()

