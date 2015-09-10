File specifications

./db/[resco]/utilitybills/[account]/incoming/[raw bill file]
./db/[resco]/utilitybills/[account]/[service]/[billperiodbegin]-[billperiodend].[pdf] (multipage document)
./db/[resco]/utilitybills/[account]/[service]/[billperiodbegin]-[billperiodend]/[p].pdf (single page document)
./db/[resco]/utilitybills/[account]/[service]/[billperiodbegin]-[billperiodend]/[p]-thumb.png
./db/[resco]/utilitybills/[account]/[service]/[billperiodbegin]-[billperiodend]/[p]-crop-[partid].tif




Converting pdf files to tiff files

    convert -density 600 Delano_WAGas_123009.pdf  Delano_WAGas_123009.tif
    for file in *; do convert -density 600 $file $file.tif; done

Splitting multipage tiff to individual pages

    for file in *.tif; do convert $file $file-%d.tif; done

split a multipage tiff into thumbnails

    convert [multipagefile].tif page-%d.png





TIFF images must be uncompressed to be processed with tesseract

convert -quiet [p].pdf -compress None -density 600 -strip -depth 8 -monochrome -endian MSB [p].tif

for file in * do convert -quiet $file -compress None -density 600 -strip -depth 8 -monochrome -endian MSB $file-converted.tif; done



This seems to work:

convert -compress None -depth 8 -monochrome [filein].tif [fileout].tif




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
