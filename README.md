HocrConverter
=============

Create PDFs and plain text from hOCR documents

Originally from jbrinley
See https://github.com/jbrinley/HocrConverter
and http://xplus3.net/2009/04/02/convert-hocr-to-pdf/

Changes by C.Holtermann

Original script didn't work for me so I made some changes to make it work for me

My configuration is ocropus 0.7

The script is more verbose. It respects the use of filenames in ocropus hocr files.
The calculation of the text positions was inversed in height.

I made the skript draw the bounding boxes and made the text visible.

Multiple pages in ocropus hocr respected.

Included some aspects from the fork of https://github.com/zw/HocrConverter:
 - some more command line arguments
 -- draw bounding boxes
 -- draw text
 -- include image

He seems to use tesseract hocr files. I haven't tested that. I didn't include the "word"-object interpretation.


Like this the script is rather something to understand the concept.

Maybe it's useful for others trying to understand OCR.

Work in progress.
