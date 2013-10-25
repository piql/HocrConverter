"""HocrConverter

Convert Files from hOCR to pdf

Usage:
  HocrConverter.py [-tIbmnrV] [-i <inputHocrFile>] (-o <outputPdfFile>) <inputImageFile>...  
  HocrConverter.py (-h | --help)

Options:
  -h --help             Show this screen.
  -t                    Make ocr-text visible
  -i <inputHocrFile>    hOCR input file
  -o <outputPdfFile>    pdf output
  -I                    include images
  -b                    draw bounding boxes around ocr-text
  -n                    don't read images supplied in hocr-file
  -m                    do multiple pages in hocr and output pdf
  -r                    take hOCR-image sizes as reference for size of page
  -V                    vertical Inversion ( for ocropus: false, for tesseract: true )

"""

from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import inch
from xml.etree.ElementTree import ElementTree
import Image
import re
import sys
try:
  from docopt import docopt
except ImportError:
  exit('This program requires that `docopt` command line parsing library'
       ' is installed: \n pip install docopt\n'
       'https://github.com/docopt/docopt')
try:
  from schema import Schema, And, Or, Use, SchemaError, Optional
except ImportError:
  exit('This program requires that `schema` data-validation library'
       ' is installed: \n pip install schema\n'
       'https://github.com/halst/schema')

class HocrConverter():
  """
  A class for converting documents to/from the hOCR format.
  
  For details of the hOCR format, see:
  
    http://docs.google.com/View?docid=dfxcv4vc_67g844kf
    
  See also:
  
    http://code.google.com/p/hocr-tools/
  
  Basic usage:
  
  Create a PDF from an hOCR file and an image:
    
    hocr = HocrConverter("path/to/hOCR/file")
    hocr.to_pdf("path/to/image/file", "path/to/output/file")
  
  """
  def __init__(self, hocrFileName = None):
    self.hocr = None
    self.xmlns = ''
    self.boxPattern = re.compile('bbox((\s+\d+){4})')
    self.filenamePattern = re.compile('file\s+(.*)')
    if hocrFileName is not None:
      self.parse_hocr(hocrFileName)
      
  def __str__(self):
    """
    Return the textual content of the HTML body
    """
    if self.hocr is None:
      return ''
    body =  self.hocr.find(".//%sbody"%(self.xmlns))
    if body:
      return self._get_element_text(body).encode('utf-8') # XML gives unicode
    else:
      return ''
  
  def _get_element_text(self, element):
    """
    Return the textual content of the element and its children
    """
    text = ''
    if element.text is not None:
      text = text + element.text
    for child in element.getchildren():
      text = text + self._get_element_text(child)
    if element.tail is not None:
      text = text + element.tail
    return text
  
  def parse_element_title(self, element):
    
    if 'title' in element.attrib:
      matches = self.boxPattern.search(element.attrib['title'])
      if matches:
        coords = matches.group(1).split()
        out = (int(coords[0]),int(coords[1]),int(coords[2]),int(coords[3]))
        return {"bbox":out}
   
      matches = self.filenamePattern.search(element.attrib['title'])
      if matches:
        return {"file":matches.groups()[0]}
    
    return None
    
  def element_coordinates(self, element):
    """
    Returns a tuple containing the coordinates of the bounding box around
    an element
    """
    text_coords = (0,0,0,0)
    parse_result = self.parse_element_title( element )
    if parse_result.has_key("bbox"):
          text_coords = parse_result["bbox"]

    return text_coords
    
  def parse_hocr(self, hocrFileName):
    """
    Reads an XML/XHTML file into an ElementTree object
    """
    self.hocr = ElementTree()
    self.hocr.parse(hocrFileName)
    
    # if the hOCR file has a namespace, ElementTree requires its use to find elements
    matches = re.match('({.*})html', self.hocr.getroot().tag)
    if matches:
      self.xmlns = matches.group(1)
    else:
      self.xmlns = ''

  def _setup_image(self, imageFileName):
    
    print "Image File:", imageFileName
      
    im = Image.open(imageFileName)
    imwidthpx, imheightpx = im.size
    
    print "Image Dimensions:", im.size
    
    if 'dpi' in im.info:
      width = float(im.size[0])/im.info['dpi'][0]
      height = float(im.size[1])/im.info['dpi'][1]
    else:
      # we have to make a reasonable guess
      # set to None for now and try again using info from hOCR file
      width = height = None
    
    return (im, width, height)

  def get_ocr_text_extension( self, page ):
    """
    Get the maximum extension of the area covered by text
    """
    if not self.hocr:
      print "No hOCR."
      return None

    x_min = x_max = y_min = y_max = 0

    for line in page.findall(".//%sspan"%(self.xmlns)):
      if line.attrib['class'] == 'ocr_line':
        text_coords = self.element_coordinates(line)
      
        for coord_x in [ text_coords[0], text_coords[2] ]:
          if coord_x > x_max:
            x_max = coord_x
          if coord_x < x_min:
            x_min = coord_x
        for coord_y in [ text_coords[1], text_coords[3] ]:
          if coord_y > y_max:
            y_max = coord_y
          if coord_y < y_min:
            y_min = coord_y

    return (x_min,y_min,x_max,y_max)


  def to_pdf(self, imageFileNames, outFileName, fontname="Courier", fontsize=8, withVisibleOCRText=False, withVisibleImage=True, withVisibleBoundingBoxes=False, noPictureFromHocr=False, multiplePages=False, hocrImageReference=False, verticalInversion=False ):
    """
    Creates a PDF file with an image superimposed on top of the text.
    
    Text is positioned according to the bounding box of the lines in
    the hOCR file.
    
    The image need not be identical to the image used to create the hOCR file.
    It can be scaled, have a lower resolution, different color mode, etc.
    """
   
    # create the PDF file 
    pdf = Canvas(outFileName, pageCompression=1)
    
    if self.hocr is None:
      # warn that no text will be embedded in the output PDF
      print "Warning: No hOCR file specified. PDF will be image-only."
    
    # Collect pages from hOCR
    pages = []
    if self.hocr is not None:
      divs = self.hocr.findall(".//%sdiv"%(self.xmlns))
      for div in divs:
        if div.attrib['class'] == 'ocr_page':
          pages.append(div)
    
    page_count = 0
    # loop pages
    while True:
      page_count += 1
      
      if len(pages) >= page_count:
        page = pages[page_count-1] 
      else:
        page = None

      if page_count > 1:
        if not multiplePages:
          print "Only processing one page."
          break # there shouldn't be more than one, and if there is, we don't want it
     
      imageFileName = None
      
      # Check for image from command line 
      if imageFileNames:
        # distinct file
        if len(imageFileNames) >= page_count:
          imageFileName = imageFileNames[page_count-1]
        # repeat the last file
        else:
          imageFileName = imageFileNames[-1]
          # stop if no more ocr date
          if not page:
            break
      else:
        print "No Images supplied by command line."

      print "Image file name:", imageFileName
      
      print "page:",page
      # Dimensions of ocr-page
      if page is not None:
        coords = self.element_coordinates( page )
      else:
        coords = (0,0,0,0)

      ocrwidth = coords[2]-coords[0]
      ocrheight = coords[3]-coords[1]
      
      # Load command line image
      if imageFileName:
        im, width, height = self._setup_image(imageFileName)
        print "width, heigth:", width, height
      else:
        im = width = height = None
        
      # Image from hOCR
      # get dimensions, which may not match the image
      im_ocr = None
      if page is not None:
        parse_result = self.parse_element_title( page )
        print "Parse Results:",parse_result
        if parse_result.has_key( "file" ):
          imageFileName_ocr_page = parse_result["file"] 
          print "ocr_page file", imageFileName_ocr_page,
        
          if noPictureFromHocr:
            print "- ignored.",
          if imageFileName:
            print "- ignored (overwritten by command line).",

          print

          if ( ( not noPictureFromHocr ) and ( not imageFileName) ) or hocrImageReference:
            im_ocr, width_ocr, height_ocr = self._setup_image(imageFileName_ocr_page)
            print "hOCR width, heigth:", width, height
          if ( not noPictureFromHocr ) and ( not imageFileName):
            im = im_ocr
            width = width_ocr
            heigth = heigth_ocr

        # Get size of text area in hOCR-file
        ocr_text_x_min, ocr_text_y_min, ocr_text_x_max, ocr_text_y_max = self.get_ocr_text_extension( page )
        ocr_text_width = ocr_text_x_max
        ocr_text_height = ocr_text_y_max

        if not ocrwidth:
          if im_ocr:
            ocrwidth = im_ocr.size[0]
          else:
            ocrwidth = ocr_text_width 

        if not ocrheight:
          if im_ocr:
            ocrheight = im_ocr.size[1]
          else:
            ocrheight = ocr_text_height
     
        print "ocrwidth, ocrheight :", ocrwidth, ocrheight
     
      if ( ( not ocrwidth ) and ( ( not width ) or ( not withVisibleImage ) ) ) or ( ( not ocrheight) and ( ( not height ) or ( not withVisibleImage ) ) ):
        print "Page with extension 0 or without content. Skipping."
      else:

        if page is not None:
          ocr_dpi = (300, 300) # a default, in case we can't find it
        
          if width is None:
            # no dpi info with the image
            # assume OCR was done at 300 dpi
            width = ocrwidth / 300.0
            height = ocrheight / 300.0
            print "Assuming width, height:",width,height
        
          ocr_dpi = (ocrwidth/width, ocrheight/height)
       
          print "ocr_dpi :", ocr_dpi
        
        if width is None:
          # no dpi info with the image, and no help from the hOCR file either
          # this will probably end up looking awful, so issue a warning
          print "Warning: DPI unavailable for image %s. Assuming 96 DPI."%(imageFileName)
          width = float(im.size[0])/96
          height = float(im.size[1])/96
          
        # PDF page size
        pdf.setPageSize((width*inch, height*inch)) # page size in points (1/72 in.)
        
        # put the image on the page, scaled to fill the page
        if withVisibleImage:
          if im:
            pdf.drawInlineImage(im, 0, 0, width=width*inch, height=height*inch)
          else:
            print "No inline image file supplied."
        
        if self.hocr is not None:
          text_elements = page.findall(".//%sspan"%(self.xmlns))
          text_elements.extend( page.findall(".//%sp"%(self.xmlns)) )
          for line in text_elements:
            text_class = line.attrib['class']
            if text_class in [ 'ocr_line', 'ocrx_word', 'ocr_carea', 'ocr_par' ]:
              
              if text_class == 'ocr_line':
                textColor = (255,0,0)
                bboxColor = (0,255,0)
              elif text_class == 'ocrx_word' :
                textColor = (255,0,0)
                bboxColor = (0,255,255)
              elif text_class == 'ocr_carea' :
                textColor = (255,0,0)
                bboxColor = (255,255,0)
              elif text_class == 'ocr_par' :
                textColor = (255,0,0)
                bboxColor = (255,0,0)
              
              coords = self.element_coordinates( line )
              parse_result = self.parse_element_title( line )
              
              text = pdf.beginText()
              text.setFont(fontname, fontsize)
              
              text_corner1x = (float(coords[0])/ocr_dpi[0])*inch
              text_corner1y = (float(coords[1])/ocr_dpi[1])*inch

              text_corner2x = (float(coords[2])/ocr_dpi[0])*inch
              text_corner2y = (float(coords[3])/ocr_dpi[1])*inch
              
              text_width = text_corner2x - text_corner1x
              text_height = text_corner2y - text_corner1y
              
              if verticalInversion:
                text_corner2y_inv = (height*inch) - text_corner1y
                text_corner1y_inv = (height*inch) - text_corner2y
                
                text_corner1y = text_corner1y_inv
                text_corner2y = text_corner2y_inv

              # set cursor to bottom left corner of line bbox (adjust for dpi)
              text.setTextOrigin( text_corner1x, text_corner1y )
           
              # The content of the text to write  
              textContent = line.text
              if ( textContent == None ):
                textContent = u""
              textContent = textContent.rstrip()

              # scale the width of the text to fill the width of the line's bbox
              if len(textContent) != 0:
                text.setHorizScale( ((( float(coords[2])/ocr_dpi[0]*inch ) - ( float(coords[0])/ocr_dpi[0]*inch )) / pdf.stringWidth( textContent, fontname, fontsize))*100)

              if not withVisibleOCRText:
                text.setTextRenderMode(3) # invisible
             
              # Text color
              text.setFillColorRGB(textColor[0],textColor[1],textColor[2])

              # write the text to the page
              text.textLine( textContent )

              print "processing", text_class, coords,"->", text_corner1x, text_corner1y, text_corner2x, text_corner2y, ":", textContent
              pdf.drawText(text)

              pdf.setLineWidth(0.1)
              pdf.setStrokeColorRGB(bboxColor[0],bboxColor[1],bboxColor[2])
       
              # Draw a box around the text object
              if withVisibleBoundingBoxes: 
                pdf.rect( text_corner1x, text_corner1y, text_width, text_height);
     
      # finish up the page. A blank new one is initialized as well.
      pdf.showPage()
    
    # save the pdf file
    print "Writing pdf."
    pdf.save()
  
  def to_text(self, outFileName):
    """
    Writes the textual content of the hOCR body to a file.
    """
    f = open(outFileName, "w")
    f.write(self.__str__())
    f.close()

def setGlobal( varName ):
  def setValue( value ):
    print varName, "=", value
    globals()[varName] = value;
    return True
  return setValue

def appendGlobal( varName ):
  def appendValue( value ):
    globals()[varName].append(value)
    print varName,"=",globals()[varName]
    return True
  return appendValue

if __name__ == "__main__":
  # Variables to control program function
  withVisibleOCRText = False;
  withVisibleImage = True;
  withVisibleBoundingBoxes = False;
  noPictureFromHocr = False
  multiplePages = False
  inputImageFileNames = []
  inputImageFileName = None
  inputHocrFileName = None
  hocrImageReference = False
  verticalInversion=False

  # Taking care of command line arguments
  arguments = docopt(__doc__)
  print(arguments)
  
  # Validation of arguments and setting of global variables
  schema = Schema({
        '-i': And( setGlobal( "inputHocrFileName" ), lambda n: Use(open, error="Can't open <inputHocrFile>") if n else True ) ,
        '--help': bool,
        '-I': setGlobal( "withVisibleImage" ),
        '-b': setGlobal( "withVisibleBoundingBoxes" ),
        '-m': setGlobal( "multiplePages" ),
        '-n': setGlobal( "noPictureFromHocr" ),
        '-t': setGlobal( "withVisibleOCRText" ),
        '-r': setGlobal( "hocrImageReference" ),
        '-V': setGlobal( "verticalInversion" ),
        '<inputImageFile>': [ And( appendGlobal( "inputImageFileNames" ), Use(open, error="Can't open <inputImageFile>") ) ],
        '-o': setGlobal( "outputPdfFileName" ) })
  try:
    args = schema.validate(arguments)
  except SchemaError as e:
    print "Error:"
    print " ",e
    print "Error Details:"
    print " ", e.autos
    exit(1) 

  hocr = HocrConverter( inputHocrFileName )
  hocr.to_pdf( inputImageFileNames, outputPdfFileName, withVisibleOCRText=withVisibleOCRText, withVisibleImage=withVisibleImage, withVisibleBoundingBoxes=withVisibleBoundingBoxes, noPictureFromHocr=noPictureFromHocr, multiplePages=multiplePages, hocrImageReference=hocrImageReference, verticalInversion=verticalInversion )
