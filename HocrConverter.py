from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import inch
from xml.etree.ElementTree import ElementTree
import Image, re, sys

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
    out = (0,0,0,0)
    if 'title' in element.attrib:
      matches = self.boxPattern.search(element.attrib['title'])
      if matches:
        coords = matches.group(1).split()
        out = (int(coords[0]),int(coords[1]),int(coords[2]),int(coords[3]))
    return out
    
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
      
  def to_pdf(self, imageFileName, outFileName, fontname="Courier", fontsize=8, withVisibleOCRText=False, withVisibleImage=True, withVisibleBoundingBoxes=False, takePictureFromHocr=True, multiplePages=False):
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
    
      for div in self.hocr.findall(".//%sdiv"%(self.xmlns)):
        print div
        if div.attrib['class'] == 'ocr_page':
          parse_result = self.parse_element_title(div)
          if parse_result.has_key("file"):
            imageFileName=parse_result["file"] 
            print "hocr-File image", imageFileName
    
    if imageFileName:
      im, width, height = self._setup_image(imageFileName)
    else:
      im = width = height = None 
      
    ocr_dpi = (300, 300) # a default, in case we can't find it
    
    # get dimensions of the OCR, which may not match the image
    if self.hocr is not None:
      page_count = 0
      for div in self.hocr.findall(".//%sdiv"%(self.xmlns)):
        print "-div" 
        if div.attrib['class'] == 'ocr_page':
          if page_count >= 1:
            if not multiplePages:
              print "Only processing one page."
              break # there shouldn't be more than one, and if there is, we don't want it
          
          print div
          coords = self.element_coordinates(div)
          parse_result = self.parse_element_title(div)
          print "Parse Results:",parse_result
          
          if parse_result.has_key("file"):
            if takePictureFromHocr:
              imageFileName_ocr_page = parse_result["file"] 
              print "ocr_page file", imageFileName_ocr_page
            
              im, width, height = self._setup_image(imageFileName_ocr_page)
              print "width, heigth:", width, height
          
          ocrwidth = coords[2]-coords[0]
          ocrheight = coords[3]-coords[1]
          
          if not ocrwidth:
            ocrwidth = im.size[0]

          if not ocrheight:
            ocrheight = im.size[1]
         
          print "ocrwidth, ocrheight :", ocrwidth, ocrheight
          
          if width is None:
            # no dpi info with the image
            # assume OCR was done at 300 dpi
            width = ocrwidth/300
            height = ocrheight/300
          ocr_dpi = (ocrwidth/width, ocrheight/height)
         
          print "ocr_dpi :", ocr_dpi
          
          page = div
          page_count += 1
            
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
            pdf.drawInlineImage(im, 0, 0, width=width*inch, height=height*inch)
          
          if self.hocr is not None:
            for line in page.findall(".//%sspan"%(self.xmlns)):
              if line.attrib['class'] == 'ocr_line':
                coords = self.element_coordinates(line)
                parse_result = self.parse_element_title(line)
                
                text = pdf.beginText()
                text.setFont(fontname, fontsize)
                
                text_corner1a = (float(coords[0])/ocr_dpi[0])*inch
                text_corner1b = (height*inch)-(float(coords[3])/ocr_dpi[1])*inch
                text_corner1b = (float(coords[1])/ocr_dpi[1])*inch

                text_corner2a = (float(coords[2])/ocr_dpi[0])*inch
                text_corner2b = (float(coords[3])/ocr_dpi[1])*inch
                
                text_width = text_corner2a - text_corner1a
                text_height = text_corner2b - text_corner1b
                
                # set cursor to bottom left corner of line bbox (adjust for dpi)
                text.setTextOrigin( text_corner1a, text_corner1b )
             
                # The content of the text to write  
                textContent = line.text
                if ( textContent == None ):
                  textContent = u""
                textContent = textContent.rstrip()

                # scale the width of the text to fill the width of the line's bbox
                if len(textContent) != 0:
                  text.setHorizScale( ((( float(coords[2])/ocr_dpi[0]*inch ) - ( float(coords[0])/ocr_dpi[0]*inch )) / pdf.stringWidth( textContent.rstrip(), fontname, fontsize))*100)

                if not withVisibleOCRText:
                  #text.setTextRenderMode(0) # visible
                #else:
                  text.setTextRenderMode(3) # invisible
               
                # Text color
                text.setFillColorRGB(255,0,0)
                
                # write the text to the page
                text.textLine( textContent )

                print "processing", coords,"->", text_corner1a, text_corner1b, text_corner2a, text_corner2b, ":", textContent
                pdf.drawText(text)

                pdf.setLineWidth(0.1)
                pdf.setStrokeColorRGB(0,255,0.3)
         
                # Draw a box around the text object
                if withVisibleBoundingBoxes: 
                  pdf.rect( text_corner1a, text_corner1b, text_width, text_height);
         
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

if __name__ == "__main__":
  
  # Taking care of command line Arguments
  if len(sys.argv) < 4:
    print 'Usage: python HocrConverter.py [-t] [-I] [-b] [-f] [-m] inputHocrFile inputImageFile outputPdfFile'
    sys.exit(1)
  withVisibleOCRText = False;
  withVisibleImage = True;
  withVisibleBoundingBoxes = False;
  takePictureFromHocr = True
  multiplePages = False

  # Only single Arguments possible, not combinations like -tIbf
  while sys.argv[1][0] == "-":
    arg = sys.argv.pop(1)
    if arg == "-t":
      withVisibleOCRText = True;
    elif arg == "-I":
      withVisibleImage = False;
    elif arg == "-b":
      withVisibleBoundingBoxes = True; 
    elif arg == "-n":
      takePictureFromHocr = False
    elif arg == "-m":
      multiplePages = True
  
  if takePictureFromHocr:
    inputImageFileName = None
    outputPdfFileName = sys.argv[2]
  else:
    inputImageFileName = sys.argv[2]
    outputPdfFileName = sys.argv[3]

  hocr = HocrConverter(sys.argv[1])
  hocr.to_pdf( inputImageFileName, outputPdfFileName, withVisibleOCRText=withVisibleOCRText, withVisibleImage=withVisibleImage, withVisibleBoundingBoxes=withVisibleBoundingBoxes, takePictureFromHocr=takePictureFromHocr, multiplePages=multiplePages )
