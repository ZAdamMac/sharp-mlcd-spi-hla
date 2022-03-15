# High Level Analyzer
# For more information and documentation, please go to https://support.saleae.com/extensions/high-level-analyzer-extensions

import sys
MY_ADDITIONAL_PACKAGES_PATH = '/usr/lib/python3/dist-packages'
if MY_ADDITIONAL_PACKAGES_PATH not in sys.path:
    sys.path.append(MY_ADDITIONAL_PACKAGES_PATH)

from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame, StringSetting, NumberSetting, ChoicesSetting
from saleae.data import GraphTimeDelta
from PIL import Image

# State Object for the HLA to track the display. Effecitvely just emulates a display
class SharpDisplayEMU(object):
    '''The easiest way, conceptually, was to emulate the behaviour of the display family as a stateful object.'''

    def __init__(self, x, y, output_path, frame_delay):
        '''
        :param x: coerced-to-int x scale of display in pixels
        :param y: coerced-to-int y scale of display in pixels
        :param output_path: absolute path to the output file
        :param frame_delay: integer number of milliseconds between frame refreshes for rate limiting
        '''
        self.x = int(x)  # Bounds the x dimension of the display
        self.y = int(y)  # Bounds the y dimension of the display
        self.output_path = output_path
        self.enabled = False
        self.current_command = "static"
        self.address_set = False
        self.active_address = 0x00
        self.active_y_pos = 0x00
        self.lines = [[] for i in range(self.x)]
        self.next_write_time = None
        self.frame_delay = frame_delay
        for i in range(self.x):  # Initialize y since declarative list lengths are C, not python
            self.lines[i] = [0] * self.y
        self.linebreak_entered = False

    def clear_display(self):
        '''Sets all "cells" of the display high, which is the transparent state.'''
        for i in range(0, self.x):
            for ib in range(0, self.y):
                self.lines[i][ib] = 1
                ib += 1
            i += 1

        self.current_command = "static"

    def parse(self, input_byte):
        '''Parse an incoming byte of SPI traffic other than individual commands'''
        if "write" in self.current_command:  # we are writing to the display
            if self.address_set and self.active_y_pos < (self.y - 1):  # we got an address and are inside the box.
                bits_placed = 7
                for bit in bits_from_byte(input_byte):
                    try:
                        self.lines[self.active_address][int(self.active_y_pos+bits_placed)] = int(bit)
                    except IndexError:
                        pass
                    bits_placed -= 1
                self.active_y_pos += 8
            elif self.active_y_pos >= self.y:  # We are now outside the box, reached EOL. Next byte will determine
                                               # If we are in a multi-line regime or not.
                if input_byte == b'\x00':
                    self.linebreak_entered = True
                    self.address_set = False
                if self.linebreak_entered and input_byte == b'\x00':  # Double-naught at EOL == end write mode
                    self.linebreak_entered = False
                    self.address_set = False
                    self.active_y_pos = 0
                    self.current_command = 'static'
            else:
                self.active_address = ord(input_byte)
                self.address_set = True
                self.active_y_pos = 0

    def flush(self, this_frame_time):
        '''Expects a GraphTime object from the frame under analysis in order to write image state to disk.

        :param this_frame_time:
        :return:
        '''
        if self.next_write_time is None:  # This technically means we never write the first chunk of data
            self.next_write_time = this_frame_time

        if this_frame_time > self.next_write_time:  # We've passed delay and can go on.
            self.next_write_time = this_frame_time + GraphTimeDelta(millisecond=self.frame_delay)  # Update delay
            image = Image.new('1', (self.x, self.y))
            for ia in range(len(self.lines)):  # Since self.lines is a bitmap we can just pass it straight in.
                line = self.lines[ia]
                for i in range(0, len(line)):
                    image.putpixel((i, ia), line[i])

            image.save(self.output_path)  # Finally, write to disk.

# High level analyzers must subclass the HighLevelAnalyzer class.
class Hla(HighLevelAnalyzer):
    # List of settings that a user can set for this High Level Analyzer.
    display_x_size = NumberSetting(min_value=0, max_value=2048)
    display_y_size = NumberSetting(min_value=0, max_value=2048)
    output_file_path = StringSetting()
    frame_delay = NumberSetting(min_value=0, max_value=2048)

    result_types = {
        'datatype': {
            'format': 'UpdatedFile: {{data.updated}}, Path: {{data.output_path}}'
        }
    }

    def __init__(self):
        '''
        Initialize HLA.

        Settings can be accessed using the same name used above.
        '''

        print("Settings:", self.display_x_size, self.display_y_size,
              self.output_file_path)
        self.emulator = SharpDisplayEMU(self.display_x_size, self.display_y_size,
                                        self.output_file_path, self.frame_delay)


    def decode(self, frame: AnalyzerFrame):
        '''
        Process a frame from the input analyzer, and optionally return a single `AnalyzerFrame` or a list of `AnalyzerFrame`s.

        The type and data values in `frame` will depend on the input analyzer.
        '''

        if frame.type == "enable":
            self.emulator.enabled = True
        if frame.type == "disable":
            self.emulator.enabled = False
            self.emulator.flush(frame.end_time)
            return AnalyzerFrame('datatype', frame.start_time, frame.end_time, {'output_path': self.output_file_path})
        if self.emulator.enabled:
            if frame.type == "result":  # We have data, only need the MOSI line
                if 'write' not in self.emulator.current_command:  # In other words, we need a command.
                    if frame.data['mosi'] == b'\x01' or frame.data['mosi'] == b'\x03':  # Correct value would depend on VCOM in hardware
                        self.emulator.current_command = "write"
                        self.address_set = False
                    elif (frame.data['mosi'] == b'\x02' or frame.data['mosi'] == b'0x00') and self.emulator.current_command == "static":
                        # "Toggle VCOM", which doesn't need an action here.
                        pass
                    elif frame.data['mosi'] == b'\x04' or frame.data['mosi'] == b'\x06':  # Just need to blank the screen
                        self.emulator.clear_display()
                else:
                    self.emulator.parse(frame.data['mosi'])

# I thought this would get used more so I broke it out as a function, but in reality it only gets called in one spot
def bits_from_byte(input_byte):
    byte = ord(input_byte)
    byte = bin(byte)[2:].rjust(8, '0')
    return byte























