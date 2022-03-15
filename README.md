
  # SHARP mLCD SPI Interpreter
  
This is a simplistic interpreter built around the SHARP Memory LCD (mLCD) family of displays, in particular tested for the LS013B7DH03. It was developed as a helper utility under the [PETI](https://www.arcanalabs.ca/hardware/PETI.html) project and tested on the same hardware, but is widely licensed and freely available for you to use in your own project! Curious about contributing? Just open a PR!
  
## Getting started

1. Pull this module into your copy of Logic.
2. Configure SPI with at least MOSI, CLK, and the LCD-CS lines measured.
3. Adjust SPI settings as needed for your device (usually CS High, Clock Inactive Low, LSB, and Trailing Edge)
4. Run the HLA on top of the SPI analyzer after specifying:
    - A reasonable frame delay in milliseconds
    - The X and Y dimensions of the screen in pixels
    - An output filepath.
    
Your mileage may vary but I've been able to use this tool to capture relatively smooth "video", using the output image as an "image source" in my broadcaster software, when the native framerate of the display was roughly 2 Hz.

  