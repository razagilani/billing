TIFF images must be uncompressed to be processed with tesseract

convert -quiet original.tif -compress None -density 600 -strip -depth 8 -monochrome -endian MSB output.tif

This seems to work:

convert -compress None -depth 8 -monochrome [filein].tif [fileout].tif

split a multipage tiff

convert [multipagefile].tif page-%d.png



IM Geometry

"<width>x<height>{+-}<xoffset>{+-}<yoffset>"

+xoffset	

The left edge of the object is to be placed xoffset pixels in from the left edge of the image.

-xoffset	

The left edge of the object is to be placed outside the image, xoffset pixels out from the left edge of the image.

The Y offset has similar meanings:

+yoffset	

The top edge of the object is to be yoffset pixels below the top edge of the image.

-yoffset	

The top edge of the object is to be yoffset pixels above the top edge of the image.