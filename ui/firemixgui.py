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

import time
import os

from PySide import QtGui, QtCore

from ui.ui_firemix import Ui_FireMixMain
from ui.dlg_add_preset import DlgAddPreset
from ui.dlg_settings import DlgSettings

class FireMixGUI(QtGui.QMainWindow, Ui_FireMixMain):

    def __init__(self, parent=None, app=None):
        super(FireMixGUI, self).__init__(parent)
        self._app = app
        self._mixer = app.mixer
        self.setupUi(self)

        self.icon_blank = QtGui.QIcon("./res/icons/blank.png")
        self.icon_disabled = QtGui.QIcon("./res/icons/ic_do_not_disturb_black_24dp_1x.png")
        self.icon_playing = QtGui.QIcon("./res/icons/ic_play_circle_filled_black_24dp_1x.png")
        self.icon_next = QtGui.QIcon("./res/icons/ic_play_circle_outline_black_24dp_1x.png")

        # Control
        self.btn_blackout.clicked.connect(self.on_btn_blackout)
        self.btn_runfreeze.clicked.connect(self.on_btn_runfreeze)
        self.btn_playpause.clicked.connect(self.on_btn_playpause)
        self.btn_next_preset.clicked.connect(self.on_btn_next_preset)
        self.btn_prev_preset.clicked.connect(self.on_btn_prev_preset)
        self.btn_reset_preset.clicked.connect(self.on_btn_reset_preset)
        self.btn_add_preset.clicked.connect(self.on_btn_add_preset)
        self.btn_remove_preset.clicked.connect(self.on_btn_remove_preset)
        self.btn_clone_preset.clicked.connect(self.on_btn_clone_preset)
        self.btn_clear_playlist.clicked.connect(self.on_btn_clear_playlist)
        self.slider_global_dimmer.valueChanged.connect(self.on_slider_dimmer)
        self.slider_speed.valueChanged.connect(self.on_slider_speed)
        self.btn_shuffle_playlist.clicked.connect(self.on_btn_shuffle_playlist)
        self.btn_trigger_onset.clicked.connect(self.on_btn_trigger_onset)

        def slider_double_click_event(e):
            self.on_slider_speed_double_click()

        self.slider_speed.mouseDoubleClickEvent = slider_double_click_event

        # File menu
        self.action_file_load_scene.triggered.connect(self.on_file_load_scene)
        self.action_file_open_playlist.triggered.connect(self.on_file_open_playlist)
        self.action_file_save_playlist_as.triggered.connect(self.on_file_save_playlist_as)
        self.action_file_save_playlist.triggered.connect(self.on_file_save_playlist)
        self.action_file_quit.triggered.connect(self.close)


        # Edit menu
        self.action_file_reload_presets.triggered.connect(self.on_file_reload_presets)
        self.action_edit_settings.triggered.connect(self.on_edit_settings)
        #self.action_settings_networking.triggered.connect(self.on_settings_networking)

        # Tools menu
        self.action_file_generate_default_playlist.triggered.connect(self.on_file_generate_default_playlist)

        # Preset list
        self.lst_presets.itemDoubleClicked.connect(self.on_preset_double_clicked)
        self.lst_presets.itemChanged.connect(self.on_preset_name_changed)
        self.lst_presets.layout_changed.connect(self.on_playlist_reorder)
        self.lst_presets.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.lst_presets.customContextMenuRequested.connect(self.preset_list_context_menu)
        self.lst_presets.setEditTriggers(QtGui.QAbstractItemView.EditKeyPressed | QtGui.QAbstractItemView.SelectedClicked)

        # Settings
        self.edit_preset_duration.valueChanged.connect(self.on_preset_duration_changed)
        self.edit_transition_duration.valueChanged.connect(self.on_transition_duration_changed)
        self.cb_transition_mode.currentIndexChanged.connect(self.on_transition_mode_changed)

        # Preset Parameters
        self.tbl_preset_parameters.itemChanged.connect(self.on_preset_parameter_changed)

        self.update_playlist()
        self.load_preset_parameters_table()
        self.tbl_preset_parameters.setDisabled(True)
        self._app.playlist_changed.connect(self.on_playlist_changed)

        if self._app.aubio_connector is not None:
            self._app.aubio_connector.onset_detected.connect(self.onset_detected)

        # Mixer FPS update
        self._update_interval = 250
        self._mixer_frame_counts = []
        self.last_frames = 0
        self.last_time = time.time()
        self.mixer_update_timer = QtCore.QTimer()
        self.mixer_update_timer.setInterval(self._update_interval)
        self.mixer_update_timer.timeout.connect(self.update_mixer)
        self.mixer_update_timer.start()

        self.transition_update_toggle = False
        self.transition_update_timer = QtCore.QTimer()
        self.transition_update_timer.setInterval(300)
        self.transition_update_timer.timeout.connect(self.on_transition_update_timer)
        self._mixer.transition_starting.connect(self.transition_update_start)

        self.btn_prev_preset.setDisabled(True)
        self.btn_blackout.setDisabled(False)

        self.update_mixer_settings()

    def closeEvent(self, event):
        self._app.stop()
        event.accept()

    def on_btn_blackout(self):
        self._app.mixer.on_tick_timer(force_tick=True)

    @QtCore.Slot()
    def onset_detected(self):
        self.btn_onset_detected.setChecked(QtCore.Qt.Checked)
        QtCore.QTimer.singleShot(50, self.clear_onset_detected)

    @QtCore.Slot()
    def clear_onset_detected(self):
        self.btn_onset_detected.setChecked(QtCore.Qt.Unchecked)

    def on_btn_trigger_onset(self):
        self._app.mixer.onset_detected()
        self.onset_detected()

    def transition_update_start(self):
        self.progress_transition.setValue(0)
        self.lbl_transition_progress.setStyleSheet("QLabel { color: #22f; }")
        self.transition_update_timer.start()

    def on_transition_update_timer(self):
        p = self._mixer.transition_progress

        if self.transition_update_toggle and not self._mixer.is_paused:
            self.lbl_transition_progress.setStyleSheet("QLabel { color: #000; }")
            self.transition_update_toggle = False
        else:
            self.lbl_transition_progress.setStyleSheet("QLabel { color: #22f; }")
            self.transition_update_toggle = True

        if p >= 1.0:
            self.lbl_transition_progress.setStyleSheet("QLabel { color: #000; }")
            self.progress_transition.setValue(0)
            self.transition_update_timer.stop()
        else:
            self.progress_transition.setValue(p * 100)

    def update_mixer(self):
        if len(self._mixer_frame_counts) < 4:
            self._mixer_frame_counts.append(self._mixer._num_frames)
            fps = 0.0
        else:
            self._mixer_frame_counts.append(self._mixer._num_frames)
            self._mixer_frame_counts.pop(0)
            frames = self._mixer_frame_counts[3] - self._mixer_frame_counts[0]
            dt = (3 * self._update_interval) / 1000.0
            fps = float(frames) / dt

        self.setWindowTitle("FireMix - %s - %0.2f FPS" % (self._app.playlist.name, fps))

        # Update wibblers
        # TODO (jon) this is kinda inefficient
        for name, parameter in self._app.playlist.get_active_preset().get_parameters().iteritems():
            pval = parameter.get()
            for i in range(self.tbl_preset_parameters.rowCount()):
                if self.tbl_preset_parameters.item(i, 0).text() == name:
                    # TODO: For now, all wibblers are float values.  Maybe they should be allowed to be others?
                    if parameter._wibbler is not None:
                        self.tbl_preset_parameters.item(i, 2).setText("= %0.2f" % pval)
                        self.tbl_preset_parameters.item(i, 2).setBackground(QtGui.QColor(200, 255, 255))
                    else:
                        self.tbl_preset_parameters.item(i, 2).setText("")
                        self.tbl_preset_parameters.item(i, 2).setBackground(QtGui.QColor(255, 255, 255))

        for name, watch in self._app.playlist.get_active_preset().get_watches().iteritems():
            val = watch.get()
            for i in range(self.tbl_preset_parameters.rowCount()):
                if self.tbl_preset_parameters.item(i, 0).text() == ("watch(%s)" % name):
                    self.tbl_preset_parameters.item(i, 1).setText(str(val))

    def on_btn_playpause(self):
        if self._mixer.is_paused():
            self._mixer.pause(False)
            self.btn_next_preset.setDisabled(False)
        else:
            self._mixer.pause()
            self.btn_next_preset.setDisabled(True)
        self.update_mixer_settings()

    def on_btn_runfreeze(self):
        if self._mixer.is_frozen():
            self._mixer.freeze(False)
            self.btn_runfreeze.setText("Freeze")
        else:
            self._mixer.freeze()
            self.btn_runfreeze.setText("Unfreeze")

    def on_btn_next_preset(self):
        self._mixer.next()
        self.update_playlist()

    # Disabling this button, we don't use it and it complicates implementation
    def on_btn_prev_preset(self):
        pass

    def on_btn_reset_preset(self):
        paused = self._app.mixer.is_paused()
        self._app.mixer.pause()
        self._app.playlist.get_active_preset()._reset()
        self._app.mixer.pause(paused)

    def on_btn_add_preset(self):
        dlg = DlgAddPreset(self)
        dlg.exec_()
        if dlg.result() == QtGui.QDialog.Accepted:
            classname = dlg.cb_preset_type.currentText()
            name = dlg.edit_preset_name.text()
            self._app.playlist.add_preset(classname, name)

    def on_btn_remove_preset(self):
        ci = self.lst_presets.currentItem()
        if ci is not None:
            self._app.playlist.remove_preset(ci.text())

    def on_btn_clone_preset(self):
        if self.lst_presets.currentItem() is None:
            return

        old_name = self.lst_presets.currentItem().text()

        self._app.playlist.clone_preset(old_name)
        self.update_playlist()

    def on_btn_clear_playlist(self):
        dlg = QtGui.QMessageBox()
        dlg.setWindowTitle("FireMix - Clear Playlist")
        dlg.setText("Are you sure you want to clear the playlist?")
        dlg.setInformativeText("This action cannot be undone.")
        dlg.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        dlg.setDefaultButton(QtGui.QMessageBox.No)
        ret = dlg.exec_()
        if ret == QtGui.QMessageBox.Yes:
            self._app.playlist.clear_playlist()
            self.update_playlist()

    def update_mixer_settings(self):
        self.edit_preset_duration.setValue(self._mixer.get_preset_duration())
        self.edit_transition_duration.setValue(self._mixer.get_transition_duration())
        # Populate transition list
        current_transition = self._app.settings.get('mixer')['transition']
        transition_list = [str(t(None)) for t in self._app.plugins.get('Transition')]
        transition_list.insert(0, "Cut")
        transition_list.insert(1, "Random")
        self.cb_transition_mode.clear()
        self.cb_transition_mode.insertItems(0, transition_list)
        self.cb_transition_mode.setCurrentIndex(self.cb_transition_mode.findText(current_transition))

        shuffle_state = QtCore.Qt.Checked if self._app.settings['mixer']['shuffle'] else QtCore.Qt.Unchecked
        self.btn_shuffle_playlist.setChecked(shuffle_state)

        preset = self._app.playlist.get_active_preset().name()

        if not self._mixer.is_paused():
            self.tbl_preset_parameters.setDisabled(True)
            self.lbl_preset_parameters.setTitle("%s Parameters (Pause to Edit)" % preset)
            self.btn_playpause.setText("Pause")
            self.btn_next_preset.setDisabled(False)
        else:
            self.lbl_preset_parameters.setTitle("%s Parameters" % preset)
            self.tbl_preset_parameters.setDisabled(False)
            self.btn_next_preset.setDisabled(True)
            self.btn_playpause.setText("Play")

    def on_slider_dimmer(self):
        dval = self.slider_global_dimmer.value() / 100.0
        self._app.mixer.set_global_dimmer(dval)
        self.lbl_dimmer.setText("Dimmer [%0.2f]" % dval)

    def on_slider_speed(self):
        sval = round(self.slider_speed.value() / 1000.0, 2)
        self._app.mixer.set_global_speed(sval)
        self.lbl_speed.setText("Speed [%0.2fx]" % sval)

    def on_slider_speed_double_click(self):
        self.slider_speed.setValue(1000.0)
        self.on_slider_speed()

    def update_playlist(self):
        self.lst_presets.clear()
        presets = self._app.playlist.get()
        current = self._app.playlist.get_active_preset()
        next = self._app.playlist.get_next_preset()
        for preset in presets:
            item = QtGui.QListWidgetItem(preset.name())

            #TODO: Enable renaming in the list when we have a real delegate
            #item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
            if not preset.parameter('allow-playback').get():
                item.setIcon(self.icon_disabled)
            else:
                if preset == current:
                    item.setIcon(self.icon_playing)
                elif preset == next:
                    item.setIcon(self.icon_next)
                else:
                    item.setIcon(self.icon_blank)

            self.lst_presets.addItem(item)

    def on_playlist_changed(self):
        self.update_playlist()
        self.update_mixer_settings()
        self.load_preset_parameters_table()

    def on_playlist_reorder(self):
        names = [self.lst_presets.item(i).text() for i in range(self.lst_presets.count())]
        self._app.playlist.reorder_playlist_by_names(names)

    def on_file_load_scene(self):
        pass

    def on_file_reload_presets(self):
        self._app.mixer.freeze(True)
        self._app.playlist.reload_presets()
        self._app.mixer.freeze(False)

    def preset_list_context_menu(self, point):
        ctx = QtGui.QMenu("test")
        action_rename = QtGui.QAction("Rename" ,self)
        action_rename.triggered.connect(self.start_rename)
        ctx.addAction(action_rename)
        ctx.exec_(self.lst_presets.pos() + self.mapToParent(point))

    def start_rename(self):
        #TODO: Enable renaming in the list when we have a real delegate
        #self.lst_presets.editItem(self.lst_presets.currentItem())
        old_name = self.lst_presets.currentItem().text()
        new_name, ok = QtGui.QInputDialog.getText(self, 'Rename Preset', 'New name', text=old_name)
        if ok and new_name:
            if not self._app.playlist.preset_name_exists(new_name):
                self._app.playlist.rename_preset(old_name, new_name)

    def on_preset_name_changed(self, item):
        pass

    def on_preset_double_clicked(self, preset_item):
        self._app.mixer.cancel_transition()
        self._app.playlist.set_active_preset_by_name(preset_item.text())

    def on_preset_duration_changed(self):
        nd = self.edit_preset_duration.value()
        if self._mixer.set_preset_duration(nd):
            self._app.settings['mixer']['preset-duration'] = nd
        self.edit_preset_duration.setValue(self._mixer.get_preset_duration())

    def on_transition_duration_changed(self):
        nd = self.edit_transition_duration.value()
        if self._mixer.set_transition_duration(nd):
            self._app.settings['mixer']['transition-duration'] = nd
        self.edit_transition_duration.setValue(self._mixer.get_transition_duration())

    def on_transition_mode_changed(self):
        if self._app.mixer.set_transition_mode(self.cb_transition_mode.currentText()):
            self._app.settings['mixer']['transition'] = self.cb_transition_mode.currentText()

    def load_preset_parameters_table(self):
        self.tbl_preset_parameters.itemChanged.disconnect(self.on_preset_parameter_changed)
        self.tbl_preset_parameters.clear()
        if self._app.playlist.get_active_preset() == None:
            return

        parameters = self._app.playlist.get_active_preset().get_parameters()
        watches = self._app.playlist.get_active_preset().get_watches()
        self.tbl_preset_parameters.setColumnCount(3)
        self.tbl_preset_parameters.setRowCount(len(parameters) + len(watches))
        i = 0
        for name in sorted(parameters, key=lambda x: x):
            parameter = parameters[name]
            key_item = QtGui.QTableWidgetItem(name)
            key_item.setFlags(QtCore.Qt.ItemIsEnabled)
            value_item = QtGui.QTableWidgetItem(parameter.get_as_str())
            current_state_item = QtGui.QTableWidgetItem("")
            current_state_item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.tbl_preset_parameters.setItem(i, 0, key_item)
            self.tbl_preset_parameters.setItem(i, 1, value_item)
            self.tbl_preset_parameters.setItem(i, 2, current_state_item)
            i += 1

        for name in sorted(watches, key=lambda x: x):
            watch = watches[name]
            key_item = QtGui.QTableWidgetItem("watch(%s)" % name)
            key_item.setFlags(QtCore.Qt.ItemIsEnabled)
            value_item = QtGui.QTableWidgetItem(watch.get_as_str())
            current_state_item = QtGui.QTableWidgetItem("")
            current_state_item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.tbl_preset_parameters.setItem(i, 0, key_item)
            self.tbl_preset_parameters.setItem(i, 1, value_item)
            self.tbl_preset_parameters.setItem(i, 2, current_state_item)
            i += 1

        self.tbl_preset_parameters.horizontalHeader().resizeSection(1, 400)
        self.tbl_preset_parameters.setHorizontalHeaderLabels(('Parameter', 'Value', 'Current'))
        self.tbl_preset_parameters.itemChanged.connect(self.on_preset_parameter_changed)

    # Unused?
    @QtCore.Slot()
    def update_preset_parameters(self):
        """
        Called from main app when presets programmatically change parameter values
        """
        parameters = self._app.playlist.get_active_preset().get_parameters()
        for item in self.tbl_preset_parameters.items():
            print item

    def on_preset_parameter_changed(self, item):
        if item.column() != 1:
            return

        key = self.tbl_preset_parameters.item(item.row(), 0)
        if key.text()[:6] == "watch(":
            return

        par = self._app.playlist.get_active_preset().parameter(key.text())
        try:
            par.set_from_str(item.text())
            item.setText(par.get_as_str())
        except ValueError:
            item.setText(par.get_as_str())

    def on_file_open_playlist(self):
        paused = self._app.mixer.is_paused()
        self._app.mixer.stop()
        old_name = self._app.playlist.filename
        filename, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open playlist file', os.path.join(os.getcwd(), "data", "playlists"), filter="Playlists (*.json)")
        name = os.path.split(filename)[1].replace(".json", "")

        self._app.playlist.set_filename(filename)
        if not self._app.playlist.open():
            self._app.playlist.set_filename(old_name)
            QtGui.QMessageBox.warning(self, "Error", "Could not open file")
        self._app.mixer.run()
        self._app.mixer.pause(paused)

    def on_file_save_playlist(self):
        self._app.playlist.save()

    def on_file_save_playlist_as(self):
        paused = self._app.mixer.is_paused()
        self._app.mixer.pause()
        filename = self._app.playlist.filename
        filename, _ = QtGui.QFileDialog.getSaveFileName(self, 'Save playlist file as', os.path.join(os.getcwd(), "data", "playlists"), filter="Playlists (*.json)")

        if len(filename) > 0:
            self._app.playlist.set_filename(filename)
            self._app.playlist.save()
        self._app.mixer.pause(paused)

    def on_file_generate_default_playlist(self):
        dlg = QtGui.QMessageBox()
        dlg.setWindowTitle("FireMix - Generate Default Playlist")
        dlg.setText("Are you sure you want to generate the default playlist?")
        dlg.setInformativeText("All existing playlist entries will be removed.  This action cannot be undone.")
        dlg.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        dlg.setDefaultButton(QtGui.QMessageBox.No)
        ret = dlg.exec_()
        if ret == QtGui.QMessageBox.Yes:
            self._app.playlist.generate_default_playlist()
            self.update_playlist()

    def on_edit_settings(self):
        DlgSettings(self).exec_()

    def on_btn_shuffle_playlist(self):
        shuffle = self.btn_shuffle_playlist.isChecked()
        self._app.settings['mixer']['shuffle'] = shuffle
        self._app.playlist.shuffle_mode(shuffle)

