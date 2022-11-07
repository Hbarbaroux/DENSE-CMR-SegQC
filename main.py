import utils

import os
import re
import sys
from pathlib import Path
import numpy as np
from scipy.io import loadmat

import matlab.engine as mtlb

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvas

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import * 



class HTMLDelegate(QStyledItemDelegate):
    '''Custom Item Delegate
    Used for ROI list to automatically change
    the color of slice indices in the list items text
    '''
    def paint(self, painter, option, index):
        '''Function overwrite
        Main style function for list items
        '''
        ### Standard ###
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options,index)
        #################

        # Converting item text to html with custom color management
        doc = self.text_to_html(options.text)

        ### Standard ####
        options.text = ""
        style = QApplication.style() if options.widget is None else options.widget.style()
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()
        if option.state & QStyle.State_Selected:
            ctx.palette.setColor(QPalette.Text, option.palette.color(QPalette.Active, QPalette.HighlightedText))

        # If item is disabled, set text color to gray
        if index.model().flags(index) == Qt.NoItemFlags:
            ctx.palette.setColor(QPalette.Text, QColor(Qt.gray))

        textRect = style.subElementRect(QStyle.SE_ItemViewItemText, options)
        painter.save()
        painter.translate(textRect.topLeft())
        painter.setClipRect(textRect.translated(-textRect.topLeft()))
        doc.documentLayout().draw(painter, ctx)
        painter.restore()
        #################


    def sizeHint(self, option, index):
        '''Function overwrite
        Used by paint() to estimate item dimensions for display
        '''
        ### Standard ###
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options,index)
        ################

        # Converting text to html like in paint()
        doc = self.text_to_html(options.text)

        # Estimating size
        doc.setTextWidth(options.rect.width())
        return QSize(int(doc.idealWidth()), int(doc.size().height()))


    def text_to_html(self, text, color='#32CD32'):
        '''
        Given a text of format 'XXXX [Y Y Y] [Z, Z, Z]', transforms it in a HTML format
        and changes the color of '[Z, Z, Z]'
        :param text: original string
        :param color: rgb string '#RRGGBB' for custom color
        :returns: QTextDocument containing HTML text
        '''
        doc = QTextDocument()
        text = text.split('\t')
        if len(text) > 2:
            text = ' '.join(text[:2]) + ' <span style="color:#32CD32;">' + text[2] + '</span>'
        else:
            text = ' '.join(text)
        doc.setHtml('<pre>' + text + '<\pre>')
        return doc



class DenseVisualizer(QMainWindow):
    '''
    Main application window
    '''

    def __init__(self):
        super().__init__()
        # Initialize menu options only
        # Wait for file opening before loading other UI elements (see open_file())
        self.init_menu()

        self.user_set_output = False
        self.input_folder = './'

        # Starting matlab engine (need Matlab for results export)
        # Needed as impossible to use scipy.io.savemat in append mode with .dns files from recent Matlab versions
        # and saving full file fails in Python due to 'seq' field of .dns file containing reference to Matlab functions
        self.eng = mtlb.start_matlab()


    def init_menu(self):
        '''
        Create UI elements for menu bar
        '''

        ### BOTTOM STATUS BAR ###
        self.statusBar()

        ### MENU ###
        menu_bar = self.menuBar()

        quit_act = QAction('&Quit', self)
        quit_act.setShortcut('Ctrl+Q')
        quit_act.setStatusTip('Exit application')
        quit_act.triggered.connect(self.close)

        open_act = QAction('&Open workspace', self)
        open_act.setShortcut('Ctrl+o')
        open_act.setStatusTip('Select a workspace to open')
        open_act.triggered.connect(self.open_file)

        self.save_act = QAction('&Save workspace', self)
        self.save_act.setShortcut('Ctrl+s')
        self.save_act.setStatusTip('Save current workspace')
        self.save_act.setEnabled(False)

        file_menu = menu_bar.addMenu('&File')
        file_menu.addAction(open_act)
        file_menu.addAction(self.save_act)
        file_menu.addAction(quit_act)

        set_out_folder_act = QAction('&Set output folder', self)
        set_out_folder_act.setShortcut('Ctrl+w')
        set_out_folder_act.triggered.connect(self.set_output_folder)

        utils_menu = menu_bar.addMenu('&Utilities')
        utils_menu.addAction(set_out_folder_act)

        ### WINDOW GEOMETRY ###
        self.setWindowState(Qt.WindowMaximized)
        self.setWindowTitle('Dense visualizer')
        self.show()


    def init_UI(self):
        '''
        Create UI elements for the main window
        Called after file opening (to prevent broken references)
        '''

        ### MAIN WINDOW ###

        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)

        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)

        self.save_act.setEnabled(True)
        self.save_act.triggered.connect(self.on_save_click)


        ### SLICE SELECTION ###

        self.slice_dropdown = QComboBox()        
        self.slice_dropdown.textActivated[str].connect(self.on_slice_change)
        main_layout.addWidget(self.slice_dropdown)


        ### IMAGES VIEW ###

        images_widget = QWidget()
        images_view = QVBoxLayout(images_widget)

        # Plots
        self.canvas = FigureCanvas(Figure(figsize=(5, 15)))
        self.axis = self.canvas.figure.subplots(1,4)
        images_view.addWidget(self.canvas)

        # Frame selection view
        frame_edit_widget = QWidget()
        frame_edit_view = QHBoxLayout(frame_edit_widget)
        images_view.addWidget(frame_edit_widget)
        # Frame selection slider
        self.frame_slider = QSlider(Qt.Horizontal)
        self.frame_slider.setMinimum(1)
        self.frame_slider.setTracking(True)
        self.frame_slider.valueChanged.connect(self.on_frame_slider_change)
        frame_edit_view.addWidget(self.frame_slider)
        # Frame selection input
        self.frame_input = QSpinBox()
        self.frame_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.frame_input.setMinimum(1)
        self.frame_input.editingFinished.connect(self.on_frame_input_change)
        frame_edit_view.addWidget(self.frame_input)
        # Maximum frames textbox
        self.frame_label = QLabel()
        frame_edit_view.addWidget(self.frame_label)


        ### ROI PANEL ###

        roi_widget = QWidget()
        roi_view = QVBoxLayout(roi_widget)
    
        # List of available ROIs
        self.roi_list = QListWidget()
        self.roi_list.itemPressed.connect(self.on_item_click)
        self.roi_list.itemDoubleClicked.connect(self.on_item_double_click)
        self.roi_list.setItemDelegate(HTMLDelegate())
        roi_view.addWidget(self.roi_list)

        # Apply button 
        apply_groupbox = QGroupBox('Update ROI info')
        apply_box_layout = QGridLayout()
        apply_groupbox.setLayout(apply_box_layout)
        roi_view.addWidget(apply_groupbox)

        self.apply_radio_group = QButtonGroup()
        radio_buttons = [QRadioButton(cat) for cat in ['base', 'mid', 'apex', '2ch', '3ch', '4ch']]
        for i, button in enumerate(radio_buttons):
            apply_box_layout.addWidget(button, i//3, i%3)
            self.apply_radio_group.addButton(button)
        
        apply_button = QPushButton('Apply', sizePolicy=QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum))
        apply_button.clicked.connect(self.on_apply_click)
        apply_box_layout.addWidget(apply_button, 2, 1, alignment=Qt.AlignCenter)
        # Button to undo apply for current item 
        delete_button = QPushButton('Delete', sizePolicy=QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum))
        delete_button.clicked.connect(self.on_delete_click)
        apply_box_layout.addWidget(delete_button, 3, 0, alignment=Qt.AlignCenter)
        # Button to undo apply for all items
        delete_all_button = QPushButton('Delete all', sizePolicy=QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum))
        delete_all_button.clicked.connect(self.on_delete_all_click)
        apply_box_layout.addWidget(delete_all_button, 3, 2, alignment=Qt.AlignCenter)

        # Other ROI buttons
        button_layout_widget = QWidget()
        button_layout = QGridLayout(button_layout_widget)
        roi_view.addWidget(button_layout_widget)
        # Button to clear ROI on images
        clear_button = QPushButton('Clear display', sizePolicy=QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum))
        clear_button.clicked.connect(self.on_clear_click)
        button_layout.addWidget(clear_button, 0, 0, 1, 2, alignment=Qt.AlignCenter)


        ### Horizontal flexible splitter between images and roi panel ###
        
        # Initial ratio 1:5 between roi panel and image window 
        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(roi_widget)
        h_splitter.addWidget(images_widget)
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 5) 
        main_layout.addWidget(h_splitter)


    def open_file(self):
        ''' 'Open workspace' menu action
        Load data from .dns workspace (must have been converted into .mat previously)
        Initialize UI
        '''

        # Dialog box for workspace file selection
        dialog = QFileDialog(self, "Open Workspace", str(self.input_folder), "Workspace file (*.dns);; Mat-file (*.mat)")
        dialog.setFileMode(QFileDialog.ExistingFile) # Mode: single file selection
        # If a file was already open, pre-select it in file selection dialog
        try:
            dialog.selectFile(self.filename)
        except AttributeError:
            pass
        # If selection succesfull, get filename, otherwise do nothing
        if dialog.exec_():
            self.filename = dialog.selectedFiles()[0]
        else:
            return

        self.input_folder = Path(self.filename).parent # Retain parent folder to save time when prompting file selection again
        # Default output folder set to parent of selected workspace file
        if not self.user_set_output:
            self.output_folder = self.input_folder
        
        # Initialize main UI
        self.init_UI()

        # Load data from DENSEanalysis workspace
        self.data = loadmat(self.filename, squeeze_me=True)
        self.metadata = self.data['seq']['ProtocolName']
        self.rois = self.data['roi']
        self.imgs = self.data['img']
        self.dns = self.data['dns']
    
        # If only 1 ROI entry in the data, need to force array structure
        # (Otherwise 0-d array loaded)
        if self.rois.size == 1:
            self.rois = self.rois.reshape(1,)
        # Same if only 1 slice entry:
        if self.dns.size == 1:
            self.dns = self.dns.reshape(1,)
        
        # Populate drop-down menu with slice names
        self.slice_dropdown.clear()
        for i in range(len(self.dns)):
            img_indices = [self.dns[i]['MagIndex'][0]] + self.dns[i]['PhaIndex'][~np.isnan(self.dns[i]['PhaIndex'])].tolist()
            img_indices = np.array(img_indices).astype(int).tolist()
            text = self.metadata[img_indices[0]-1] + ' -'
            for idx in img_indices:
                text += ' [{}]'.format(idx)
            self.slice_dropdown.addItem(text)

        # self.slice_dropdown.clear()
        # self.slice_dropdown.addItems([text + ' - [{}] [{}] [{}]'.format(3*i+1, 3*i+2, 3*i+3) for i, text in enumerate(self.metadata[::3])])

        # Move frame slider to beginning
        self.frame_slider.setValue(1)

        self.init_roi_list(new="CorrectedNames" not in self.rois.dtype.names)

        # Initialize images display
        self.on_slice_change(self.slice_dropdown.currentText())

    
    def init_roi_list(self, new):
        if new:
            roi_names = ['{}\t{}'.format(name, idx) for name, idx in zip(self.rois["Name"],self.rois["SeqIndex"])]
            self.new_assoc = [[] for _ in range(len(roi_names))]
            self.new_names = ['' for _ in range(len(roi_names))]
        else:
            self.new_assoc = [i.tolist() if len(i)>0 else [] for i in self.rois["CorrectedSeqIndex"]]
            self.new_names = [i if len(i)>0 else '' for i in self.rois["CorrectedNames"]]
            roi_names = ['{}\t{}'.format(name, idx) for name, idx in zip(self.rois["Name"],self.rois["SeqIndex"])]

        self.roi_list.clear()
        self.roi_list.addItems(roi_names)
        # Disable non-standard short or long axis ROIs
        for i in range(len(self.rois)):
            if not (self.rois[i]['Type'] in ["SA", "LA"]):
                self.roi_list.item(i).setFlags(Qt.NoItemFlags)
                self.roi_list.item(i).setForeground(Qt.gray)

        if not new:
            # Change text value
            for i, roi_item in enumerate(roi_names):

                roi_item = self.roi_list.item(i).text()
                roi_item_slice_removed = '\t'.join(roi_item.split('\t')[:2]) # Remove previous corrected slice indices if need be
                roi_item_with_slice = roi_item_slice_removed + '\t' + str(list(np.array(self.new_assoc[i])))
                roi_item_with_slice_cat = self.new_names[i] + ' - ' + roi_item_with_slice.split(' - ')[-1]
                self.roi_list.item(i).setText(roi_item_with_slice_cat)
        

    def update_images(self):
        '''
        Update images panel with given slice, frame and ROI (if selected)
        '''

        # Handle exception when displaying the data
        # (might happen when number of frames for ROI and slice differ)
        # (might happen when loading new workspace)
        try:
            # Update MRI images
            utils.clear_figures(self.axis)
            for i in range(4):
                try:
                    img = self.imgs[self.current_images_idx[i]][:,:,self.frame_slider.value()-1]
                    utils.imshow(self.axis[i], img)

                    if self.roi_list.selectedItems():
                        roi_data = self.rois[self.roi_list.currentRow()]
                        if i == 0:
                            contours = utils.anchor_to_contour(roi_data['Type'], *roi_data['Position'][self.frame_slider.value()-1])
                        try:
                            utils.roishow(self.axis[i], *contours, roi_data['Type'])
                        except UnboundLocalError: # Might happen if contours isn't created in time
                            pass
                # If z-axis img doesn't exists, display black img
                except IndexError:
                    img = np.zeros(img.shape)
                    utils.imshow(self.axis[i], img)

            self.canvas.draw()

        except (IndexError, AttributeError):
            pass


    def on_frame_slider_change(self):
        ''' Frame slider moved event
        Update image display with given frame
        '''
        # Update text box to corresponding frame
        self.frame_input.setValue(self.frame_slider.value())
        self.update_images()


    def on_frame_input_change(self):
        ''' Frame slection text box event
        Update image display with given frame
        '''
        # Update frame slider to corresponding frame
        self.frame_slider.setValue(self.frame_input.value())
        self.update_images()


    def on_slice_change(self,text):
        ''' Slice selection event
        Update image display with given slice (stay on same frame)
        '''
        # Update slice indices
        self.current_images_idx = ([int(i)-1 for i in re.findall("\[(.*?)\]", text)])
    
        # Update maximum number of frame as it can change from one slice to another
        nbr_frames = self.imgs[self.current_images_idx[0]].shape[2]
        self.frame_slider.setMaximum(nbr_frames)
        self.frame_label.setText('/ {}'.format(nbr_frames))
        
        self.update_images()


    def on_item_click(self, item):
        ''' ROI panel item selected event
        Update image display with given ROI
        '''
        self.update_images()


    def on_item_double_click(self, item):
        '''
        NOT USED
        Possibility to let the user change the ROI name by double-clicking on list item
        '''
        basename = item.text().split('\t')[0]
        text, ok = QInputDialog.getText(self, 'Edit', 'Edit ROI name:', QLineEdit.Normal, basename)
        if text and ok:
            updated_text = '\t'.join([text] + item.text().split('\t')[1:])
            item.setText(updated_text)

    
    def on_clear_click(self):
        ''' Clear button event
        Clear ROI selection and remove it from image display 
        '''
        self.roi_list.clearSelection()
        self.update_images()


    def on_apply_click(self):
        ''' Apply button event
        Associates current slice with current ROI, 
        by adding slice indices to list item text with a different color
        '''
        # Only take action if there is a selected ROI
        if self.roi_list.selectedItems():

            # Check if slice category is selected, otherwise display warning and do nothing
            try:
                slice_cat = self.apply_radio_group.checkedButton().text()
            except AttributeError:
                QMessageBox.warning(self, 'Warning', 'Cannot apply corrections. Please select a slice category and retry.')
                return
            
            # Change text value
            roi_item = self.roi_list.currentItem().text()
            roi_item_slice_removed = '\t'.join(roi_item.split('\t')[:2]) # Remove previous corrected slice indices if need be
            roi_item_with_slice = roi_item_slice_removed + '\t' + str(list(np.array(self.current_images_idx)+1))
            roi_item_with_slice_cat = slice_cat + ' - ' + roi_item_with_slice.split(' - ')[-1]
            self.roi_list.currentItem().setText(roi_item_with_slice_cat)

            # Update association list
            self.new_assoc[self.roi_list.currentRow()] = (np.array(self.current_images_idx)+1).tolist()

            # Update corrected ROI name list
            self.new_names[self.roi_list.currentRow()] = slice_cat

    
    def on_delete_click(self):
        ''' Delete button event
        Remove user-set association between current ROI and slice
        '''
        # Check if a ROI item is selected
        if self.roi_list.selectedItems():
            self.delete_user_association(self.roi_list.currentRow())
    

    def on_delete_all_click(self):
        ''' Delete all button event
        Remove user-set association for all ROIs
        '''
        for i in range(self.roi_list.count()):
            self.delete_user_association(i)


    def delete_user_association(self, index):
        '''
        Delete user-set assocation of a given list item
        by changing UI text and removing the entry in self.new_assoc
        :param index: index of corresponding item in self.roi_list
        '''
        roi_item = self.roi_list.item(index).text()
        roi_item_slice_removed = '\t'.join(roi_item.split('\t')[:2])
        roi_item_slice_removed = roi_item_slice_removed.split(' - ')[-1]
        self.roi_list.item(index).setText(roi_item_slice_removed)
        self.new_assoc[index] = []
        self.new_names[index] = ''


    def on_save_click(self):
        ''' Save button event
        Export data into similar format than input,
        adding an extra column to the 'roi' entry to save 
        user-set associations between ROIs and slices.
        '''
        if not self.user_set_output:
            self.user_set_output = True
            alert_msg = 'You did not specify any output folder. By default, the input file will be overwritten. \
If this is not the intended behaviour, please select the output folder in the Utilities menu. \
Do you wish to proceed with the saving? (This message will appear only once.)'
            alert_reply = QMessageBox.warning(self, 'Warning', alert_msg, QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No)

            if alert_reply == QMessageBox.StandardButton.No:
                return

        # Output path from given output folder and input filename
        output_file = os.path.join(self.output_folder, Path(self.filename).name)
        self.eng.update_workspace_corrected(self.new_names, self.new_assoc, self.filename, output_file, nargout=0)


    def center(self):
        ''' Function to center window on screen '''
        fg = self.frameGeometry()
        fg.moveCenter(self.screen().availableGeometry().center())
        self.move(fg.topLeft())


    def closeEvent(self, event):
        '''Function overwrite
        Alert window to ask for confirmation when quitting the app.
        '''
        # Alert window, default on YES
        reply = QMessageBox.question(self, 'Message',
                    "Are you sure you want to quit?", QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)

        # Accept or ignore quit event depending on alert confirmation
        if reply == QMessageBox.StandardButton.Yes:
            self.eng.quit()
            event.accept()
        else:
            event.ignore()


    def set_output_folder(self):
        
        temp = QFileDialog.getExistingDirectory(self, "Select output folder", "./")
        if temp != '':
            self.output_folder = temp
            self.user_set_output = True


def main():

    app = QApplication(sys.argv)
    ex = DenseVisualizer()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()