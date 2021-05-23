HocrConverter
=============

Create PDFs and plain text from hOCR documents

Originally from jbrinley
See https://github.com/jbrinley/HocrConverter
and http://xplus3.net/2009/04/02/convert-hocr-to-pdf/

Changes by C.Holtermann

Original script didn't work for me so I made some changes to make it work for me

My configuration is ocropus 0.7 and tesseract 3.02.02

Included some aspects from the fork of https://github.com/zw/HocrConverter:

Some command line arguments:
 - draw bounding boxes
 - draw text
 - inverse height ( tesseract and ocropus count differently )
 - multiple pages
 - include Images ( from hOCR or via command line )
 - verbosity

Like this the script is rather something to understand the concept.

Maybe it's useful for others trying to understand OCR.

Changes by tristelune1

- this script is for python3
- text is search recursively in span tags 

Work in progress.

# Install
For command line parsing and validation I use some external libraries:
- docopt
- schema

```
python -m pip install reportlab pdfgen schema image docopt
```
