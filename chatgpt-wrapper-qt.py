import sys
import os
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtGui as qtg
from PyQt5 import QtCore as qtc
import breeze_resources
import openai

default_system_role = ("You are intelligent, helpful, and an expert developer, who always " +
                        "gives the correct answer and does what's instructed. You always " +
                        "answer truthfully and don't make things up. (When responding to the " +
                        "user's prompt, make sure to properly style your response using Github " +
                        "Flavored Markdown. Use markdown syntax for elements like headings, lists, " +
                        "colored text, code blocks, highlights etc. Absolutely do not mention " +
                        "markdown or styling in your response.")

class cls_plain_text_edit(qtw.QTextEdit):

    signal_shiftenter = qtc.pyqtSignal()

    def __init__(self):
        super().__init__()
     
    def insertFromMimeData(self, source):
        if source.hasText():
            # Removes formatting from pasted text.
            self.insertPlainText(source.text())

    def keyPressEvent(self, event):
        if event.key() in (qtc.Qt.Key_Enter, qtc.Qt.Key_Return) and event.modifiers() != qtc.Qt.ShiftModifier:
            self.signal_shiftenter.emit()
        else:
            super().keyPressEvent(event)


class cls_main_window(qtw.QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowIcon(qtg.QIcon(
            os.path.join(
            os.path.dirname(__file__), "openai_logo.svg")))


        self.list_messages = [] # A list of messages to send with each prompt
        self.list_history = [(default_system_role, '','')] # An internal record of messages in tuple form, (role, prompt, reply). 
                             # There should always be one blank tuple at the end to represent the current (unwritten) message.
        self.id_counter = 1

        self.settings = qtc.QSettings('most_ghost', 'chatgpt-wrapper-qt')
        self.setWindowTitle('chatgpt-wrapper-qt')

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

        lo_prompt.addWidget(struct_prompt_body)

        temp_api = self.settings.value('--ghostconfig/api')
        self.wgt_api_key.setText(temp_api)
        del temp_api

        self.wgt_api_key.textEdited.connect(lambda: 
                self.settings.setValue(f'--ghostconfig/api', f'{self.wgt_api_key.text()}')
        )


        struct_roles = qtw.QWidget()
        lo_roles = qtw.QVBoxLayout()
        struct_roles.setLayout(lo_roles)
        lo_prompt_body.addWidget(struct_roles)

        wgt_label_system = qtw.QLabel("system role")
        self.wgt_label_history = qtw.QLabel("message history: 0")
        self.wgt_edit_system = cls_plain_text_edit()
        self.wgt_edit_system.setWordWrapMode(qtg.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.wgt_edit_system.setText(default_system_role)
        self.wgt_edit_system.setPlaceholderText("this pre-prompt gives chatGPT context on what you want from it.")

        struct_forget_buttons = qtw.QWidget()
        lo_forget_buttons = qtw.QHBoxLayout()
        struct_forget_buttons.setLayout(lo_forget_buttons)

        self.wgt_remove_oldest = qtw.QPushButton('forget oldest')
        self.wgt_remove_oldest.clicked.connect(self.slot_remove_oldest)
        self.wgt_remove_newest = qtw.QPushButton('forget newest')
        self.wgt_remove_newest.clicked.connect(self.slot_remove_newest)
        self.wgt_label_temp = qtw.QLabel('temperature: 0.50')
        self.wgt_temp_slider = qtw.QSlider(orientation=qtc.Qt.Horizontal)
        self.wgt_temp_slider.setValue(50)
        self.wgt_temp_slider.valueChanged.connect(self.slot_temperature_changed)
        self.wgt_history_picker = qtw.QComboBox()
        self.wgt_history_picker.addItem('new')
        self.wgt_history_picker.activated.connect(self.slot_history_changed)        

        lo_roles.addWidget(wgt_label_system)
        lo_roles.addWidget(self.wgt_edit_system)
        lo_roles.addWidget(self.wgt_label_history)
        
        lo_forget_buttons.addWidget(self.wgt_remove_oldest)
        lo_forget_buttons.addWidget(self.wgt_remove_newest)
        lo_roles.addWidget(struct_forget_buttons)

        lo_roles.addWidget(self.wgt_history_picker)
        lo_roles.addWidget(self.wgt_label_temp)
        lo_roles.addWidget(self.wgt_temp_slider)



        self.wgt_label_prompt = qtw.QLabel('Prompt')
        self.wgt_edit_prompt = cls_plain_text_edit()
        self.wgt_edit_prompt.setPlaceholderText('enter your prompt here \n \nshift+enter will insert a new line. enter alone will send.')
        self.wgt_edit_prompt.signal_shiftenter.connect(self.slot_send_prompt)
        self.wgt_edit_response = qtw.QTextEdit()
        self.wgt_edit_response.setPlaceholderText('response will be displayed here')

        self.updating_document = qtg.QTextDocument()
        self.wgt_edit_response.setDocument(self.updating_document)

        lo_prompt_body.addWidget(self.wgt_edit_prompt)

        wgt_prompt_button = qtw.QPushButton('enter')
        lo_prompt.addWidget(wgt_prompt_button)
        wgt_prompt_button.clicked.connect(self.slot_send_prompt)

        self.var_temp = 0.50

        temp_font_id = qtg.QFontDatabase.addApplicationFont(
            os.path.join(
            os.path.dirname(__file__), "monofonto.otf"))
        temp_font_family = qtg.QFontDatabase.applicationFontFamilies(temp_font_id)[0]
        var_typewriter_font = qtg.QFont(temp_font_family)
        var_typewriter_font.setPointSize(16)

        self.func_recursive_font(self, var_typewriter_font)

        temp_font_id = qtg.QFontDatabase.addApplicationFont(
            os.path.join(
            os.path.dirname(__file__), "roboto.ttf"))
        temp_font_family = qtg.QFontDatabase.applicationFontFamilies(temp_font_id)[0]
        var_roboto_font = qtg.QFont(temp_font_family)
        var_roboto_font.setPointSize(16)

        lo_body.addWidget(self.wgt_edit_response)
        self.wgt_edit_response.setFont(var_roboto_font)

        print(self.wgt_label_prompt.x())

        self.show()


    def func_recursive_font(self, widget, font):
        widget.setFont(font)

        for child_widget in widget.findChildren(qtw.QWidget):
            self.func_recursive_font(child_widget, font)


    def slot_temperature_changed(self):
        self.var_temp = float(f"0.{self.wgt_temp_slider.value()}")
        self.wgt_label_temp.setText(f'temperature: {self.var_temp}')


    def slot_remove_oldest(self):
        if len(self.list_messages) == 0:
            pass
        else:
            self.list_messages.pop(0)
            self.list_messages.pop(0)
            self.wgt_label_history.setText(f'messages in memory: {int(len(self.list_messages) / 2)}')

        if len(self.list_history) > 1:
            print('Pop!')
            self.list_history.pop(0)
            print(self.list_history)
            self.wgt_history_picker.removeItem(0)



    def slot_remove_newest(self):
        if len(self.list_messages) == 0:
            pass
        else:
            self.list_messages.pop(-1)
            self.list_messages.pop(-1)
            self.wgt_label_history.setText(f'messages in memory: {int(len(self.list_messages) / 2)}')

        if len(self.list_history) > 1:
            print('Pop!')
            self.list_history.pop(-2) # Pop the one before the latest message
            print(self.list_history)
            self.wgt_history_picker.removeItem(len(self.wgt_history_picker) - 2)


    def slot_send_prompt(self):

        user_prompt = self.wgt_edit_prompt.toPlainText().replace('\n', '')
        system_prompt = self.wgt_edit_system.toPlainText().replace('\n', '')
        message_prompt = [{"role" : "system", 
       "content": system_prompt}]
        full_response = []
        
        self.list_messages.append({"role": "user", 
               "content": f'{user_prompt}' })
        for i in self.list_messages:
            message_prompt.append(i)        

        try:
            cursor = qtg.QTextCursor(self.wgt_edit_response.document())
            self.wgt_edit_response.setTextCursor(cursor)

            openai.api_key = self.wgt_api_key.text()
            model_engine = "gpt-3.5-turbo" 

            for chunk in openai.ChatCompletion.create(
            model = model_engine,
            temperature = self.var_temp,
            max_tokens = 2048,
            messages = message_prompt,
            stream=True):
                content = chunk["choices"][0].get("delta", {}).get("content")
                if content is not None:
                    full_response.append(content)
                    self.wgt_edit_response.setText(''.join(full_response))

                    cursor.movePosition(qtg.QTextCursor.End)
                    self.wgt_edit_response.setTextCursor(cursor)
                    
                    self.wgt_edit_response.ensureCursorVisible() 
                    qtw.QApplication.processEvents()
        except Exception as e:
            self.wgt_edit_response.setPlaceholderText(f'There was an error: \n \n{e}')

        final_response = ''.join(full_response)
        self.list_messages.append({"role": "assistant", "content": final_response})
        self.wgt_label_history.setText(f'messages in memory: {int(len(self.list_messages) / 2)}')
        self.wgt_edit_response.setMarkdown(final_response)

        cursor.movePosition(qtg.QTextCursor.End)
        self.wgt_edit_response.setTextCursor(cursor)        
        self.wgt_edit_response.ensureCursorVisible() 


        self.list_history.insert(-1, (self.wgt_edit_system.toPlainText(), self.wgt_edit_prompt.toPlainText(), final_response))
        print(self.list_history)
        self.wgt_history_picker.insertItem(len(self.wgt_history_picker) - 1, f'message {self.id_counter}')
        self.id_counter += 1

    def slot_history_changed(self, index):
        self.wgt_edit_system.setText(self.list_history[index][0])
        self.wgt_edit_prompt.setText(self.list_history[index][1])
        self.wgt_edit_response.setMarkdown(self.list_history[index][2])


if __name__ == '__main__': 
    app = qtw.QApplication(sys.argv)
    # app.setStyle("Fusion")
    style_file = qtc.QFile(":/dark/stylesheet.qss")
    style_file.open(qtc.QFile.ReadOnly | qtc.QFile.Text)
    stream = qtc.QTextStream(style_file)
    app.setStyleSheet(stream.readAll())
    window_main = cls_main_window()
    sys.exit(app.exec())
