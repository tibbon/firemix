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

import os
import gc
import logging
import random

from PySide import QtCore

from lib.json_dict import JSONDict
from lib.preset_loader import PresetLoader

log = logging.getLogger("firemix.lib.playlist")


# TODO: Metaclass hell when trying to subclass QObject here.  Maybe don't need to subclass JSONDict?
class Playlist(JSONDict):
    """
    Manages the available presets and the current playlist of presets.
    """

    def changed(self):
        # Ugh. At boot-up the emit() method isn't present on Qt signals. This is
        # a hack around that.
        emit = getattr(self._app.playlist_changed, 'emit', None)
        if emit is not None:
            emit()

    def __init__(self, app):
        self._app = app
        self.name = app.args.playlist
        if self.name is None:
            self.name = self._app.settings.get("mixer").get("last_playlist", "default")
        filepath = os.path.join(os.getcwd(), "data", "playlists", "".join([self.name, ".json"]))
        JSONDict.__init__(self, 'playlist', filepath, True)

        self.open()

    def set_filename(self, filename):
        self.name = os.path.split(filename)[1].replace(".json", "")
        self.filename = filename

    def open(self):
        try:
            self.load(False)
        except ValueError:
            print "Error loading %s" % self.filename
            return False

        self._loader = PresetLoader(self)
        self._preset_classes = self._loader.load()
        self._playlist_data = self.data.get('playlist', [])
        self._playlist = []

        self.active_preset = None
        self.next_preset = None
        self._shuffle = self._app.settings['mixer']['shuffle']
        self._shuffle_list = []

        self.generate_playlist()

        self.changed()
        return True

    def generate_playlist(self):
        log.info("Populating playlist...")
        if len(self._playlist_data) == 0:
            self._playlist = []

        for entry in self._playlist_data:
            if entry['classname'] in self._loader.all_presets():

                inst = self._loader.all_presets()[entry['classname']][1](self._app.mixer, name=entry['name'])
                inst._reset()

                for _, key in enumerate(entry.get('params', {})):
                    try:
                        inst.parameter(key).set_from_str(str(entry['params'][key]))
                    except AttributeError:
                        log.warn("Parameter %s called out in playlist but not found in plugin.  Perhaps it was renamed?" % key)

                # This is a total hack and indicates that the initialization
                # model for presets isn't quite right.
                self.initialized = True
                inst.parameter_changed(None)
                self._playlist.append(inst)
            else:
                self._playlist_data.remove(entry)

        self.playlist_mutated()

        log.info("Done")
        return self._playlist

    @QtCore.Slot()
    def playlist_mutated(self):
        """
        This should get called when the playlist is mutated in some way
        (presets dragged around, dis/enabled, deleted, duplicated, added, etc)
        It also gets called from advance() at the end of a transition, etc
        """

        if self.active_preset is None:
            if len(self._playlist) > 0:
                self.active_preset = self._playlist[0]
            else:
                # Nothing going on here!
                self.next_preset = None
                return

        # Check if we just deleted the active preset
        if self.active_preset not in self._playlist:
            self.active_preset = self.next_preset
            self.update_next_preset()

        # Generate the shuffle list
        if self._shuffle:
            self.generate_shuffle()

        if self.next_preset is None:
            # Initialize _next.  We probably went from a playlist of length 0 to 1.
            if self._shuffle and len(self._playlist) > 1:
                self.next_preset = self._playlist[self._shuffle_list.pop()]
            elif len(self._playlist) == 0:
                self.next_preset = None
            elif len(self._playlist) == 1:
                self.next_preset = self.active_preset
            else:
                self.next_preset = self._playlist[1]
        else:
            # Update the next pointer
            self.update_next_preset()

    def update_next_preset(self):
        if len(self._playlist) == 1:
            self.next_preset = self.active_preset
        else:
            active_idx = self._playlist.index(self.active_preset)
            candidate = (active_idx + 1) % len(self._playlist)
            while not self._playlist[candidate].parameter('allow-playback').get():
                candidate = (candidate + 1) % len(self._playlist)
                # This should never happen but I don't like infinite loops
                if candidate == active_idx:
                    break
            self.next_preset = self._playlist[candidate]
        self.changed()

    def shuffle_mode(self, shuffle=True):
        """
        Enables or disables playlist shuffle
        """
        self._shuffle = shuffle
        self.update_next_preset()

    def generate_shuffle(self):
        """
        Creates a shuffle list
        """
        self._shuffle_list = range(len(self._playlist))

        # Remove disallowed presets from the shuffle list
        self._shuffle_list = [idx for idx in self._shuffle_list if self._playlist[idx].parameter('allow-playback').get()]

        random.shuffle(self._shuffle_list)
        active_idx = self._playlist.index(self.active_preset)
        if active_idx in self._shuffle_list:
            self._shuffle_list.remove(active_idx)

    def reload_presets(self):
        """Attempts to reload all preset classes in the playlist"""
        self._preset_classes = self._loader.reload()
        while len(self._playlist) > 0:
            inst = self._playlist.pop(0)
            inst.clear_parameters()
            del inst

        gc.collect()
        self.generate_playlist()
        self.changed()

    def disable_presets_by_class(self, class_name):
        for p in self._playlist:
            if p.__class__.__name__ == class_name:
                p.disabled = True
                log.error("Disabling %s because the preset is crashing." % p.name())

    def module_reloaded(self, module):
        for p in self._playlist:
            if p.__module__ == module:
                p.reset()
                p.disabled = False

    def save(self):
        log.info("Saving playlist")
        # Pack the current state into self.data
        self.data = {'file-type': 'playlist'}
        playlist = []
        for preset in self._playlist:
            playlist_entry = {'classname': preset.__class__.__name__,
                              'name': preset.name()}
            param_dict = {}
            for name, param in preset.get_parameters().iteritems():
                param_dict[name] = param.get_as_str()
            playlist_entry['params'] = param_dict
            playlist.append(playlist_entry)
        self.data['playlist'] = playlist
        # Superclass write to file
        self._app.settings.get("mixer")["last_playlist"] = self.name
        JSONDict.save(self)

    def get(self):
        return self._playlist

    def advance(self):
        """
        Advances the playlist
        """
        self.active_preset = self.next_preset

        if self._shuffle:
            if len(self._shuffle_list) == 0:
                self.generate_shuffle()
            self.next_preset = self._playlist[self._shuffle_list.pop()]
        else:
            self.update_next_preset()

        self.changed()

    def __len__(self):
        return len(self._playlist)

    def get_active_preset(self):
        if len(self._playlist) == 0:
            return None
        else:
            return self.active_preset

    def get_next_preset(self):
        if len(self._playlist) == 0:
            return None
        else:
            return self.next_preset

    def get_preset_by_index(self, idx):
        if len(self._playlist) == 0:
            return None
        else:
            return self._playlist[idx]

    def get_preset_by_name(self, name):
        for preset in self._playlist:
            if preset.name() == name:
                return preset
        return None

    def set_active_preset_by_name(self, name):
        #TODO: Support transitions other than jump cut
        for i, preset in enumerate(self._playlist):
            if preset.name() == name:
                preset._reset()
                self.active_preset = preset
                self._app.mixer._elapsed = 0.0  # Hack
                self.update_next_preset()
                return

    def set_next_preset_by_name(self, name):
        for i, preset in enumerate(self._playlist):
            if preset.name() == name:
                self._next = preset
                self.changed()
                return

    def reorder_playlist_by_names(self, names):
        """
        Pass in a list of preset names to reorder.
        """
        current = dict([(preset.name(), preset) for preset in self._playlist])

        new = []
        for name in names:
            new.append(current[name])

        self._playlist = new
        self.playlist_mutated()
        self.changed()

    def get_available_presets(self):
        return self._preset_classes.keys()

    def preset_name_exists(self, name):
        return True if name in [p.name() for p in self._playlist] else False

    def add_preset(self, classname, name, idx=None):
        """
        Adds a new preset instance to the playlist.  Classname must be a currently loaded
        preset class.  Name must be unique.  If idx is specified, the preset will be inserted
        at the position idx, else it will be appended to the end of the playlist.
        """
        if classname not in self._preset_classes:
            log.error("Tried to add nonexistent preset class %s" % classname)
            return False

        if self.preset_name_exists(name):
            return False

        inst = self._preset_classes[classname](self._app.mixer, name=name)
        inst._reset()

        if idx is not None:
            self._playlist.insert(idx, inst)
        else:
            self._playlist.append(inst)

        if self.active_preset == self.next_preset:
            self.update_next_preset()

        self.changed()
        return True

    def remove_preset(self, name):
        """
        Removes an existing instance from the playlist
        """
        if not self.preset_name_exists(name):
            return False

        pl = [(i, p) for i, p in enumerate(self._playlist) if p.name() == name]
        assert len(pl) == 1

        self._playlist.remove(pl[0][1])

        self.playlist_mutated()
        self.changed()
        return True

    def clone_preset(self, old_name):
        old = self.get_preset_by_name(old_name)
        classname = old.__class__.__name__
        new_name = old_name
        candidate = new_name
        i = 2
        while self.get_preset_by_name(candidate):
            candidate = new_name + " (" + str(i) + ")"
            i += 1
        new_name = candidate
        self.add_preset(classname, new_name, self._playlist.index(old) + 1)
        new = self.get_preset_by_name(new_name)

        for name, param in old.get_parameters().iteritems():
            new.parameter(name).set_from_str(param.get_as_str())

        self.playlist_mutated()
        self.changed()

    def clear_playlist(self):
        self._playlist = []
        self.playlist_mutated()
        self.changed()

    def rename_preset(self, old_name, new_name):
        pl = [i for i, p in enumerate(self._playlist) if p.name() == old_name]
        if len(pl) != 1:
            return False
        self._playlist[pl[0]].set_name(new_name)
        self.changed()

    def generate_default_playlist(self):
        """
        Wipes out the existing playlist and adds one instance of each preset
        """
        self.clear_playlist()
        for cn in self._preset_classes:
            name = cn + "-1"
            inst = self._preset_classes[cn](self._app.mixer, name=name)
            inst.setup()
            self._playlist.append(inst)
        self.playlist_mutated()
        self.changed()

    def suggest_preset_name(self, classname):
        """
        Returns an unused preset name based on the classname, in the form "Classname-N",
        where N is an integer.
        """
        i = 1
        name = classname + "-" + str(i)
        while self.preset_name_exists(name):
            i += 1
            name = classname + "-" + str(i)
        return name
