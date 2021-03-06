# This file is part of Firemix.
#
# Copyright 2013-2015 Jonathan Evans <jon@craftyjon.com>
#
# Firemix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Firemix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Firemix.  If not, see <http://www.gnu.org/licenses/>.

import unittest
import time
import logging
import numpy as np

from lib.commands import SetAll, SetStrand, SetFixture, SetPixel, render_command_list
from lib.parameters import BoolParameter

log = logging.getLogger("firemix.lib.preset")


class Preset:
    """Base Preset.  Does nothing."""

    def __init__(self, mixer, name=""):
        self._mixer = mixer
        self._commands = []
        self._tickers = []
        self._ticks = 0
        self._elapsed_time = 0
        self._parameters = {}
        self._watches = {}
        self._instance_name = name
        self.initialized = False
        self.disabled = False
        self.add_parameter(BoolParameter('allow-playback', True))
        self.setup()

    def __repr__(self):
        return "%s (%s)" % (self._instance_name, self.__class__.__name__)

    def set_name(self, name):
        self._instance_name = name

    def name(self):
        return self._instance_name

    def reset(self):
        """
        Override this method to perform any initialization that will be triggered
        each time the preset is about to start playing.  Note that code that should
        only run once (e.g. creating parameters) should go in the setup() method instead.
        """
        pass

    def _reset(self):
        self._commands = []
        self.reset()

    def setup(self):
        """
        Override this method to initialize your tickers.
        """
        pass

    def parameter_changed(self, parameter):
        """
        This callback will be called when any parameters are updated.
        """
        pass

    def can_transition(self):
        """
        Override this method to define clear points at which the mixer can
        transition to or from the preset.  By default, the mixer can
        transition at any time.
        """
        return True

    def add_parameter(self, parameter):
        """
        Adds a parameter to the preset (see ./lib/parameters.py)
        """
        parameter.set_parent(self)
        self._parameters[str(parameter)] = parameter

    def get_parameters(self):
        return self._parameters

    def clear_parameters(self):
        self._parameters = []

    def parameter(self, key):
        return self._parameters.get(key, None)

    def set_parameter(self, key, value):
        """
        Attempts to change the value of a parameter. Returns False if the parameter does not
        exist or the new value is invalid.
        """
        try:
            self._parameters[key].set(value)
            return True
        except KeyError:
            return False

    def add_watch(self, watch):
        self._watches[str(watch)] = watch

    def get_watches(self):
        return self._watches

    def clear_watches(self):
        self._watches = []

    def watch(self, key):
        return self._watches.get(key, None)

    def add_ticker(self, ticker, priority=0):
        """
        Adds a ticker. Tickers are run every tick and can yield any number of
        (lights, color) tuples.

        lights is one of:
            an empty tuple                    (to change all strands)
            a (strand) tuple                  (to change all addresses on the strand)
            a (strand, address) tuple         (to change all pixels on the strand)
            a (strand, address, pixel) tuple  (to change a single pixel)
            a list of any of the above tuples

        color is an (r, g, b) tuple where r, g, and b are either:
            integers between 0 and 255
            floats between 0 and 1

        Tickers get a two arguments: the number of ticks that have
        passed since this preset started, and the approximate amount of time
        this preset has been running for, in seconds.

        The optional priority arguments is used to determine the order in which
        tickers are run. High priorities are run after lower priorities, allowing
        them to override the lower-priority tickers.
        """
        self._tickers.append((ticker, priority))
        # Resort the list here rather than at each tick
        self._tickers = sorted(self._tickers, key=lambda x: x[1])
        return ticker

    def remove_ticker(self, ticker):
        for (t, p) in self._tickers:
            if t == ticker:
                self._tickers.remove((t, p))

    def clear_tickers(self):
        self._tickers = []

    def tick(self, dt):  
        if self._mixer._enable_profiling:
            start = time.time()

        for parameter in self._parameters.values():
            parameter.tick(dt)
        
        # Assume that self._tickers is already sorted via add_ticker()
        for ticker, priority in self._tickers:

            for lights, color in ticker(self._ticks, self._elapsed_time):

                if lights is not None:

                    if type(lights) == tuple:
                        lights = [lights]

                    for light in lights:
                        if len(light) == 0:
                            self.add_command(SetAll(color, priority))
                        elif len(light) == 1:
                            self.add_command(SetStrand(light[0], color, priority))
                        elif len(light) == 2:
                            self.add_command(SetFixture(light[0], light[1], color, priority))
                        elif len(light) == 3:
                            self.add_command(SetPixel(light[0], light[1], light[2], color, priority))

        self._ticks += 1
        self._elapsed_time += dt
        if self._mixer._enable_profiling:
            tick_time = 1000.0 * (time.time() - start)
            if tick_time > 30.0:
                log.info("%s slow frame: %d ms" % (self.__class__, tick_time))

    def draw_to_buffer(self, buffer):
        commands = self.get_commands()
        render_command_list(self.scene(), commands, buffer)
        return buffer

    def tick_rate(self):
        return self._mixer.get_tick_rate()

    def clear_commands(self):
        self._commands = []

    def get_commands(self):
        return self._commands

    def get_commands_packed(self):
        return [cmd.pack() for cmd in self._commands]

    def add_command(self, cmd):
        self._commands.append(cmd)

    def _convert_color(self, color):
        if (type(color[0]) == float) or (type(color[1]) == float) or (type(color[2]) == float) or (type(color[1]) ==np.float32):
            return tuple([int(c*255) for c in color])
        else:
            return color

    def scene(self):
        return self._mixer.scene()


class TestPreset(unittest.TestCase):

    pass
