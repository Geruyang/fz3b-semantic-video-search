"""A read-only value with explicit minus/plus actions, in hundredths."""
import math
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QPushButton


class SimilarityStepper(QWidget):
    valueChanged=Signal(float)

    def __init__(self,parent=None):
        super().__init__(parent)
        self._units=17;self._minimum=-100;self._maximum=100;self._step=1
        self.setObjectName('similarityControl')
        layout=QHBoxLayout(self);layout.setContentsMargins(2,2,2,2);layout.setSpacing(2)
        self.minus_button=QPushButton('−');self.plus_button=QPushButton('+')
        self.display=QLabel('0.17');self.display.setAlignment(Qt.AlignCenter);self.display.setMinimumWidth(48)
        for button,name in ((self.minus_button,'降低相似度阈值'),(self.plus_button,'提高相似度阈值')):
            button.setFixedSize(32,32);button.setAccessibleName(name);button.setAutoRepeat(True)
        self.minus_button.clicked.connect(lambda:self.setValue(self.value()-self._step/100))
        self.plus_button.clicked.connect(lambda:self.setValue(self.value()+self._step/100))
        layout.addWidget(self.minus_button);layout.addWidget(self.display);layout.addWidget(self.plus_button)
        self.setAccessibleName('命中相似度阈值，使用减号或加号调整')
        self.setStyleSheet('QWidget#similarityControl {background:#1B283C;border:1px solid #41526A;border-radius:5px;} QPushButton {padding:0;font-size:18px;border:0;} QLabel {background:transparent;}')

    def value(self):return self._units/100

    def setValue(self,value):
        if not math.isfinite(value):raise ValueError('threshold must be finite')
        units=max(self._minimum,min(self._maximum,round(value*100)))
        changed=units!=self._units;self._units=units
        self.display.setText('%.2f'%self.value())
        self.minus_button.setEnabled(units>self._minimum);self.plus_button.setEnabled(units<self._maximum)
        if changed:self.valueChanged.emit(self.value())

    def setRange(self,minimum,maximum):
        if not math.isfinite(minimum) or not math.isfinite(maximum) or minimum>maximum:raise ValueError('invalid threshold range')
        self._minimum=round(minimum*100);self._maximum=round(maximum*100);self.setValue(self.value())

    def setSingleStep(self,step):
        if not math.isfinite(step) or step<.01:raise ValueError('threshold step must be at least .01')
        self._step=round(step*100)
