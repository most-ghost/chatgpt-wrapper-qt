import sys
import os
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtGui as qtg
from PyQt5 import QtCore as qtc
import resources.breeze_resources
import resources.syntax_pars as syntax_pars
import openai

default_system_role = ("You are intelligent, helpful, and an expert developer, who always " +
                        "gives the correct answer and does what's instructed. You always " +
                        "answer truthfully and don't make things up. (When responding to the " +
                        "user's prompt, make sure to properly style your response using Github " +
                        "Flavored Markdown. Use markdown syntax for elements like headings, lists, " +
                        "colored text, code blocks, highlights etc. Absolutely do not mention " +
                        "markdown or styling in your response.")
# I yoinked this role off a VS code extension. By the way, this is an important lesson- you can't stop
# the user from simply asking chatGPT to give up the system prompt, so don't assume anything you're writing
# is going to be 100% hidden from the user.


class cls_user_query_edit(qtw.QTextEdit):

    signal_send_prompt = qtc.pyqtSignal()

    def __init__(self):
        super().__init__()

    def insertFromMimeData(self, source):
        if source.hasText():
            # Removes formatting from pasted text.
            self.insertPlainText(source.text())

    def keyPressEvent(self, event):
        if event.key() in (qtc.Qt.Key_Enter, qtc.Qt.Key_Return) and event.modifiers() != qtc.Qt.ShiftModifier:
            self.signal_send_prompt.emit()
        else:
            super().keyPressEvent(event)


class cls_main_window(qtw.QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowIcon(qtg.QIcon(
            os.path.join(
            os.path.dirname(__file__), "resources/openai_logo.svg")))


        self.list_messages = [] # A list of messages to send with each prompt
        self.list_history = [(default_system_role, '','')] # An internal record of messages in tuple form, (role, prompt, reply). 
                             # There should always be one blank tuple at the end to represent the current (unwritten) message.
        self.message_counter = 1

        self.var_continue = True

        self.settings = qtc.QSettings('most_ghost', 'chatgpt-wrapper-qt') # Only used to store the API key.
        self.setWindowTitle('chatgpt-wrapper-qt')

        # WIDGETS - Top level

        struct_top = qtw.QWidget()
        lo_top = qtw.QVBoxLayout()
        struct_top.setLayout(lo_top)

        self.setCentralWidget(struct_top)

        struct_body = qtw.QWidget()
        lo_body = qtw.QHBoxLayout()
        struct_body.setLayout(lo_body)

        lo_top.addWidget(struct_body)
        struct_prompt = qtw.QFrame()
        struct_prompt.setLineWidth(10)
        struct_prompt_body = qtw.QWidget()
        lo_prompt = qtw.QVBoxLayout()
        lo_prompt_body = qtw.QHBoxLayout()
        struct_prompt_body.setLayout(lo_prompt_body)
        struct_prompt.setLayout(lo_prompt)
        lo_body.addWidget(struct_prompt)
        struct_prompt.setFrameShape(qtw.QFrame.Panel | qtw.QFrame.Sunken)

        self.wgt_api_key = qtw.QLineEdit()
        self.wgt_api_key.setEchoMode(qtw.QLineEdit.PasswordEchoOnEdit)
        self.wgt_api_key.setFocusPolicy(qtc.Qt.ClickFocus)
        lo_prompt.addWidget(self.wgt_api_key)
        self.wgt_api_key.setPlaceholderText('api key')
        self.wgt_api_key.textChanged.connect(lambda: self.wgt_api_key.setText(self.wgt_api_key.text().strip()))
        # This will get rid of any new lines or other assorted nasty if the user accidentally 
        # puts them in while copy + pasting

        lo_prompt.addWidget(struct_prompt_body)

        temp_api = self.settings.value('--ghostconfig/api')
        self.wgt_api_key.setText(temp_api)
        del temp_api
        self.wgt_api_key.textEdited.connect(lambda: 
                self.settings.setValue(f'--ghostconfig/api', f'{self.wgt_api_key.text()}')
        )

        # WIDGETS - Left Pane - Settings

        struct_roles = qtw.QWidget()
        lo_settings_pane = qtw.QVBoxLayout()
        struct_roles.setLayout(lo_settings_pane)
        lo_prompt_body.addWidget(struct_roles)
        
        wgt_label_system = qtw.QLabel("system role")

        self.wgt_edit_system = cls_user_query_edit()
        self.wgt_edit_system.setWordWrapMode(qtg.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.wgt_edit_system.setText(default_system_role)
        self.wgt_edit_system.setPlaceholderText("this pre-prompt gives chatGPT context on what you want from it.")


        struct_history = qtw.QGroupBox('history')
        lo_history = qtw.QVBoxLayout()
        struct_history.setLayout(lo_history)

        self.wgt_label_history = qtw.QLabel("messages: 0")

        struct_forget_buttons = qtw.QWidget()
        lo_forget_buttons = qtw.QHBoxLayout()
        struct_forget_buttons.setLayout(lo_forget_buttons)

        self.wgt_remove_oldest = qtw.QPushButton('forget oldest')
        self.wgt_remove_oldest.clicked.connect(self.slot_remove_oldest)
        self.wgt_remove_newest = qtw.QPushButton('forget newest')
        self.wgt_remove_newest.clicked.connect(self.slot_remove_newest)

        self.wgt_history_picker = qtw.QComboBox()
        self.wgt_history_picker.addItem('new')
        self.wgt_history_picker.activated.connect(self.slot_history_changed) 

        lo_history.addWidget(self.wgt_label_history)
        lo_forget_buttons.addWidget(self.wgt_remove_oldest)
        lo_forget_buttons.addWidget(self.wgt_remove_newest)
        lo_history.addWidget(struct_forget_buttons)
        lo_history.addWidget(self.wgt_history_picker)

        
        self.struct_spinbox_grid = qtw.QGroupBox('Parameters', checkable = True)
        lo_spinbox_grid = qtw.QGridLayout()
        self.struct_spinbox_grid.setLayout(lo_spinbox_grid)
        self.struct_spinbox_grid.clicked.connect(self.slot_reset_params)




        self.wgt_slider_freq = qtw.QSlider(orientation=qtc.Qt.Horizontal)
        self.wgt_slider_freq.setValue(0)
        self.wgt_slider_freq.setMinimum(-200)
        self.wgt_slider_freq.setMaximum(200)
        self.wgt_slider_freq.valueChanged.connect(self.slot_set_params_label)

        self.wgt_slider_pres = qtw.QSlider(orientation=qtc.Qt.Horizontal)
        self.wgt_slider_pres.setValue(0)
        self.wgt_slider_pres.setMinimum(-200)
        self.wgt_slider_pres.setMaximum(200)
        self.wgt_slider_pres.valueChanged.connect(self.slot_set_params_label)

        self.wgt_slider_temp = qtw.QSlider(orientation=qtc.Qt.Horizontal)
        self.wgt_slider_temp.setValue(70)
        self.wgt_slider_temp.setMaximum(200)
        self.wgt_slider_temp.valueChanged.connect(self.slot_set_params_label)
        self.wgt_label_params = qtw.QLabel("")
        self.slot_set_params_label()

        lo_spinbox_grid.addWidget(self.wgt_label_params, 0, 0, 1, 3)
        lo_spinbox_grid.addWidget(qtw.QLabel('temperature'), 1, 0)
        lo_spinbox_grid.addWidget(self.wgt_slider_temp, 1, 2)
        lo_spinbox_grid.addWidget(qtw.QLabel('freq. penalty'), 2, 0)
        lo_spinbox_grid.addWidget(self.wgt_slider_freq, 2, 2)
        lo_spinbox_grid.addWidget(qtw.QLabel('pres. penalty'), 3, 0)
        lo_spinbox_grid.addWidget(self.wgt_slider_pres, 3, 2)

        stylesheet_dangerzone = """
        QSlider::groove:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                        stop:0 #BF1200, stop:0.2 #DD8605, stop:0.3 #005105, stop:0.7 #005105, stop:0.8 #DD8605, stop:1 #BF1200);
        }

        QSlider::add-page:horizontal {
            background: transparent;
        }

        QSlider::sub-page:horizontal {
            background: transparent;
        }
        
        QSlider::handle:horizontal {
            border: 2px solid #2f88b7;
        }

        """


        stylesheet_dangerzone_temp = """
        QSlider::groove:horizontal {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                        stop:0 #005105, stop:0.45 #005105, stop:0.6 #DD8605, stop:1 #BF1200);
        }

        QSlider::add-page:horizontal {
            background: transparent;
        }

        QSlider::sub-page:horizontal {
            background: transparent;
        }

        QSlider::handle:horizontal {
            border: 2px solid #2f88b7;
        }

        """

        self.wgt_slider_freq.setStyleSheet(stylesheet_dangerzone)
        self.wgt_slider_pres.setStyleSheet(stylesheet_dangerzone)
        self.wgt_slider_temp.setStyleSheet(stylesheet_dangerzone_temp)


        lo_settings_pane.addWidget(wgt_label_system)
        lo_settings_pane.addWidget(self.wgt_edit_system)
        lo_settings_pane.addWidget(struct_history)
        lo_settings_pane.addWidget(self.struct_spinbox_grid)


        # WIDGETS - Middle Pane - Prompt


        self.wgt_prompt_label = qtw.QLabel('Prompt')
        self.wgt_user_prompt = cls_user_query_edit()
        self.wgt_user_prompt.setPlaceholderText('type in your prompt here \n \nshift+enter will insert a new line. enter alone will send.')
        self.wgt_user_prompt.signal_send_prompt.connect(self.slot_send_prompt)


        # WIDGETS - Right Pane - Response


        self.wgt_response_formatted = qtw.QTextEdit()
        self.wgt_response_formatted.setPlaceholderText('response will be displayed here')
        self.wgt_response_plain = qtw.QTextEdit()
        self.wgt_response_plain.setPlaceholderText('response will be displayed here')
        self.wgt_response_python = qtw.QTextEdit()
        self.wgt_response_python.setStyleSheet("""QTextEdit{ 
	                                            background-color: #2b2b2b;}""")
        self.wgt_response_python.setPlaceholderText('response will be displayed here')

        self.updating_document = qtg.QTextDocument()
        self.wgt_response_formatted.setDocument(self.updating_document)

        lo_prompt_body.addWidget(self.wgt_user_prompt)

        self.struct_response_tabs = qtw.QTabWidget()
        self.struct_response_tabs.addTab(self.wgt_response_formatted, 'formatted')
        self.struct_response_tabs.addTab(self.wgt_response_plain, 'plain text')
        self.struct_response_tabs.addTab(self.wgt_response_python, 'python')

        lo_body.addWidget(self.struct_response_tabs)

        wgt_prompt_button = qtw.QPushButton('send')
        wgt_prompt_button.clicked.connect(self.slot_send_prompt)

        wgt_prompt_stop = qtw.QPushButton('stop')
        wgt_prompt_stop.clicked.connect(self.slot_stop_prompt)
        wgt_prompt_stop.setStyleSheet("""
        QPushButton {
            background-color: #801515;
            border-color: #ff252b;
            } """)

        struct_send_strip = qtw.QWidget()
        lo_send_strip = qtw.QHBoxLayout()
        struct_send_strip.setLayout(lo_send_strip)

        lo_send_strip.addWidget(wgt_prompt_button, 3)
        lo_send_strip.addWidget(wgt_prompt_stop, 1)
        lo_prompt.addWidget(struct_send_strip)


        # FONTS

        font_typewriter = self.func_make_font("monofonto.otf", 16)

        self.func_recursive_font(self, font_typewriter)

        font_roboto = self.func_make_font("roboto.ttf", 16)
        font_roboto_small = self.func_make_font("roboto.ttf", 13)
        font_roboto_mono = self.func_make_font("robotomono.ttf", 13)
        self.wgt_response_formatted.setFont(font_roboto)
        self.wgt_response_plain.setFont(font_roboto_small)
        self.wgt_response_python.setFont(font_roboto_mono)


        self.show()


    def func_code_formatting(self, text):
        # Some simple code formatting. Or rather, non-code formatting, to get non-code text out of the way.)

        final_response = text[:].split('\n')
        code_flag = False
        code_response = []
        for line in final_response:
            if line[:9] == '```python`' or line[:3] == '```':
                code_flag = not code_flag # inverts code_flag
                continue
            elif line == "":
                code_response.append(line)
                continue
            elif code_flag == True:
                code_response.append(line)
            elif code_flag == False:
                code_response.append("# || " + line)
        return code_response
    

    def func_make_font(self, font_name, size):
        temp_font_id = qtg.QFontDatabase.addApplicationFont(
            os.path.join(
            os.path.dirname(__file__), f'resources/{font_name}'))
        temp_font_family = qtg.QFontDatabase.applicationFontFamilies(temp_font_id)[0]
        font = qtg.QFont(temp_font_family)
        font.setPointSize(size)
        return font


    def func_recursive_font(self, widget, font):
        widget.setFont(font)

        for child_widget in widget.findChildren(qtw.QWidget):
            self.func_recursive_font(child_widget, font)


    def slot_remove_oldest(self):
        if len(self.list_messages) == 0:
            pass
        else:
            self.list_messages.pop(0)
            self.list_messages.pop(0)
            self.wgt_label_history.setText(f'messages in memory: {int(len(self.list_messages) / 2)}')

        if len(self.list_history) > 1:
            self.list_history.pop(0)
            self.wgt_history_picker.removeItem(0)



    def slot_remove_newest(self):
        if len(self.list_messages) == 0:
            pass
        else:
            self.list_messages.pop(-1)
            self.list_messages.pop(-1)
            self.wgt_label_history.setText(f'messages in memory: {int(len(self.list_messages) / 2)}')

        if len(self.list_history) > 1:
            self.list_history.pop(-2) # Pop the one before the latest message
            self.wgt_history_picker.removeItem(len(self.wgt_history_picker) - 2)


    def slot_send_prompt(self):

        user_prompt = self.wgt_user_prompt.toPlainText().replace('\n', '')
        system_prompt = self.wgt_edit_system.toPlainText().replace('\n', '')
        message_prompt = [{"role" : "system", 
       "content": system_prompt}]
        full_response = []
        
        self.list_messages.append({"role": "user", 
               "content": f'{user_prompt}' })
        for i in self.list_messages:
            message_prompt.append(i)        

        try:


            dict_cursors = {}
            for i in range(self.struct_response_tabs.count()):
                dict_cursors[i] = qtg.QTextCursor(self.struct_response_tabs.widget(i).document())
                self.struct_response_tabs.widget(i).setTextCursor(dict_cursors[i])


            openai.api_key = self.wgt_api_key.text()
            model_engine = "gpt-3.5-turbo" 

            for chunk in openai.ChatCompletion.create(
            model = model_engine,
            temperature = round(self.wgt_slider_temp.value() / 100, 2),
            max_tokens = 2048,
            messages = message_prompt,
            frequency_penalty = round(self.wgt_slider_freq.value() / 100, 2),
            presence_penalty = round(self.wgt_slider_pres.value() / 100, 2),
            stream=True):
                content = chunk["choices"][0].get("delta", {}).get("content")
                if content is not None and self.var_continue == True:
                    full_response.append(content)
                    self.wgt_response_formatted.setMarkdown(''.join(full_response))
                    self.wgt_response_plain.setText(''.join(full_response))
                    intermediate_response = ''.join(full_response)

                    code_response = self.func_code_formatting(intermediate_response)
                    self.wgt_response_python.setText("\n".join(code_response))


                    for i in range(self.struct_response_tabs.count()):
                        dict_cursors[i].movePosition(qtg.QTextCursor.End)
                        self.struct_response_tabs.widget(i).setTextCursor(dict_cursors[i])
                        self.struct_response_tabs.widget(i).ensureCursorVisible()

                    qtw.QApplication.processEvents()
                
                elif self.var_continue == False:
                    break

        except Exception as e:
            for i in range(self.struct_response_tabs.count()):
                self.struct_response_tabs.widget(i).setPlaceholderText(f'There was an error: \n \n{e}')


        final_response = ''.join(full_response)
        self.list_messages.append({"role": "assistant", "content": final_response})
        self.wgt_label_history.setText(f'messages in memory: {int(len(self.list_messages) / 2)}')


        self.wgt_response_formatted.setMarkdown(final_response)
        self.wgt_response_plain.setText(final_response)
    
        code_response = self.func_code_formatting(final_response)
        self.wgt_response_python.setText("\n".join(code_response))



        for i in range(self.struct_response_tabs.count()):
            dict_cursors[i].movePosition(qtg.QTextCursor.End)
            self.struct_response_tabs.widget(i).setTextCursor(dict_cursors[i])
            self.struct_response_tabs.widget(i).ensureCursorVisible()


        self.list_history.insert(-1, (self.wgt_edit_system.toPlainText(), self.wgt_user_prompt.toPlainText(), final_response))
        self.wgt_history_picker.insertItem(len(self.wgt_history_picker) - 1, f'message {self.message_counter}')
        self.message_counter += 1

    def slot_stop_prompt(self):
        self.var_continue = False
        qtc.QTimer.singleShot(10, self.slot_reset_stop)

    def slot_reset_stop(self):
        self.var_continue = True

    def slot_reset_params(self):
        self.struct_spinbox_grid.setChecked(True)
        self.wgt_slider_temp.setValue(70)
        self.slot_set_params_label()
        self.wgt_slider_freq.setValue(0)
        self.wgt_slider_pres.setValue(0)
        # This is a bit jank but whatever, 
        # this is supposed to only be for me so I don't feel like doing this properly.

    def slot_set_params_label(self):
        temp = f'{self.wgt_slider_temp.value() / 100:.2f}'
        freq = f'{self.wgt_slider_freq.value() / 100:.2f}'
        pres = f'{self.wgt_slider_pres.value() / 100:.2f}'

        if freq[:1] != "-":
            freq = " " + freq

        if pres[:1] != "-":
            pres = " " + pres

        self.wgt_label_params.setText(
        f't: {temp} f:{freq} p:{pres}')

    
    def slot_history_changed(self, index):
        self.wgt_edit_system.setText(self.list_history[index][0])
        self.wgt_user_prompt.setText(self.list_history[index][1])
        self.wgt_response_formatted.setMarkdown(self.list_history[index][2])
        self.wgt_response_plain.setText(self.list_history[index][2])
        code_response = self.func_code_formatting(self.list_history[index][2])
        self.wgt_response_python.setText("\n".join(code_response))

if __name__ == '__main__': 
    app = qtw.QApplication(sys.argv)
    # app.setStyle("Fusion")
    style_file = qtc.QFile(":/dark/stylesheet.qss")
    style_file.open(qtc.QFile.ReadOnly | qtc.QFile.Text)
    stream = qtc.QTextStream(style_file)
    app.setStyleSheet(stream.readAll())
    window_main = cls_main_window()
    highlight = syntax_pars.PythonHighlighter(window_main.wgt_response_python.document())

    sys.exit(app.exec())
