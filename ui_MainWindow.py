# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'MainWindow.ui'
#
# Created: Tue Jul 04 13:36:34 2017
#      by: pyside-uic 0.2.15 running on PySide 1.2.4
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(593, 491)
        self.centralwidget = QtGui.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout = QtGui.QHBoxLayout(self.centralwidget)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout_3 = QtGui.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.formLayout_2 = QtGui.QFormLayout()
        self.formLayout_2.setObjectName("formLayout_2")
        self.label_3 = QtGui.QLabel(self.centralwidget)
        self.label_3.setObjectName("label_3")
        self.formLayout_2.setWidget(0, QtGui.QFormLayout.LabelRole, self.label_3)
        self.horizontalLayout_4 = QtGui.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.nukeEdit = QtGui.QLineEdit(self.centralwidget)
        self.nukeEdit.setObjectName("nukeEdit")
        self.horizontalLayout_4.addWidget(self.nukeEdit)
        self.nukeButton = QtGui.QPushButton(self.centralwidget)
        self.nukeButton.setObjectName("nukeButton")
        self.horizontalLayout_4.addWidget(self.nukeButton)
        self.formLayout_2.setLayout(0, QtGui.QFormLayout.FieldRole, self.horizontalLayout_4)
        self.label = QtGui.QLabel(self.centralwidget)
        self.label.setObjectName("label")
        self.formLayout_2.setWidget(1, QtGui.QFormLayout.LabelRole, self.label)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.dirEdit = QtGui.QLineEdit(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.dirEdit.sizePolicy().hasHeightForWidth())
        self.dirEdit.setSizePolicy(sizePolicy)
        self.dirEdit.setObjectName("dirEdit")
        self.horizontalLayout_2.addWidget(self.dirEdit)
        self.dirButton = QtGui.QPushButton(self.centralwidget)
        self.dirButton.setObjectName("dirButton")
        self.horizontalLayout_2.addWidget(self.dirButton)
        self.formLayout_2.setLayout(1, QtGui.QFormLayout.FieldRole, self.horizontalLayout_2)
        self.verticalLayout_3.addLayout(self.formLayout_2)
        self.listWidget = QtGui.QListWidget(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(100)
        sizePolicy.setHeightForWidth(self.listWidget.sizePolicy().hasHeightForWidth())
        self.listWidget.setSizePolicy(sizePolicy)
        self.listWidget.setMinimumSize(QtCore.QSize(300, 0))
        self.listWidget.setObjectName("listWidget")
        self.verticalLayout_3.addWidget(self.listWidget)
        self.horizontalLayout.addLayout(self.verticalLayout_3)
        self.verticalLayout_2 = QtGui.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.versionLabel = QtGui.QLabel(self.centralwidget)
        self.versionLabel.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.versionLabel.setObjectName("versionLabel")
        self.verticalLayout_2.addWidget(self.versionLabel)
        spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout_2.addItem(spacerItem)
        self.gridLayout = QtGui.QGridLayout()
        self.gridLayout.setSizeConstraint(QtGui.QLayout.SetDefaultConstraint)
        self.gridLayout.setObjectName("gridLayout")
        self.proxyCheck = QtGui.QCheckBox(self.centralwidget)
        self.proxyCheck.setObjectName("proxyCheck")
        self.gridLayout.addWidget(self.proxyCheck, 0, 0, 1, 1)
        self.continueCheck = QtGui.QCheckBox(self.centralwidget)
        self.continueCheck.setObjectName("continueCheck")
        self.gridLayout.addWidget(self.continueCheck, 0, 1, 1, 1)
        self.priorityCheck = QtGui.QCheckBox(self.centralwidget)
        self.priorityCheck.setObjectName("priorityCheck")
        self.gridLayout.addWidget(self.priorityCheck, 1, 0, 1, 1)
        self.hiberCheck = QtGui.QCheckBox(self.centralwidget)
        self.hiberCheck.setObjectName("hiberCheck")
        self.gridLayout.addWidget(self.hiberCheck, 1, 1, 1, 1)
        self.verticalLayout_2.addLayout(self.gridLayout)
        self.renderButton = QtGui.QPushButton(self.centralwidget)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.renderButton.sizePolicy().hasHeightForWidth())
        self.renderButton.setSizePolicy(sizePolicy)
        self.renderButton.setMinimumSize(QtCore.QSize(200, 100))
        self.renderButton.setObjectName("renderButton")
        self.verticalLayout_2.addWidget(self.renderButton)
        self.stopButton = QtGui.QPushButton(self.centralwidget)
        self.stopButton.setEnabled(False)
        self.stopButton.setObjectName("stopButton")
        self.verticalLayout_2.addWidget(self.stopButton)
        self.horizontalLayout.addLayout(self.verticalLayout_2)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtGui.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 593, 23))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtGui.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.actionRender = QtGui.QAction(MainWindow)
        self.actionRender.setObjectName("actionRender")
        self.actionDir = QtGui.QAction(MainWindow)
        self.actionDir.setObjectName("actionDir")
        self.actionStop = QtGui.QAction(MainWindow)
        self.actionStop.setObjectName("actionStop")
        self.actionNuke = QtGui.QAction(MainWindow)
        self.actionNuke.setObjectName("actionNuke")

        self.retranslateUi(MainWindow)
        QtCore.QObject.connect(self.renderButton, QtCore.SIGNAL("clicked()"), self.actionRender.trigger)
        QtCore.QObject.connect(self.dirButton, QtCore.SIGNAL("clicked()"), self.actionDir.trigger)
        QtCore.QObject.connect(self.nukeButton, QtCore.SIGNAL("clicked()"), self.actionNuke.trigger)
        QtCore.QObject.connect(self.stopButton, QtCore.SIGNAL("clicked()"), self.actionStop.trigger)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QtGui.QApplication.translate("MainWindow", "Nuke批渲染", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("MainWindow", "Nuke", None, QtGui.QApplication.UnicodeUTF8))
        self.nukeButton.setText(QtGui.QApplication.translate("MainWindow", "浏览", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("MainWindow", "工作目录", None, QtGui.QApplication.UnicodeUTF8))
        self.dirButton.setText(QtGui.QApplication.translate("MainWindow", "浏览", None, QtGui.QApplication.UnicodeUTF8))
        self.versionLabel.setText(QtGui.QApplication.translate("MainWindow", "version", None, QtGui.QApplication.UnicodeUTF8))
        self.proxyCheck.setText(QtGui.QApplication.translate("MainWindow", "代理尺寸", None, QtGui.QApplication.UnicodeUTF8))
        self.continueCheck.setText(QtGui.QApplication.translate("MainWindow", "出错继续渲", None, QtGui.QApplication.UnicodeUTF8))
        self.priorityCheck.setText(QtGui.QApplication.translate("MainWindow", "低优先级", None, QtGui.QApplication.UnicodeUTF8))
        self.hiberCheck.setText(QtGui.QApplication.translate("MainWindow", "完成后休眠", None, QtGui.QApplication.UnicodeUTF8))
        self.renderButton.setText(QtGui.QApplication.translate("MainWindow", "渲染", None, QtGui.QApplication.UnicodeUTF8))
        self.stopButton.setText(QtGui.QApplication.translate("MainWindow", "停止渲染", None, QtGui.QApplication.UnicodeUTF8))
        self.actionRender.setText(QtGui.QApplication.translate("MainWindow", "render", None, QtGui.QApplication.UnicodeUTF8))
        self.actionDir.setText(QtGui.QApplication.translate("MainWindow", "dir", None, QtGui.QApplication.UnicodeUTF8))
        self.actionStop.setText(QtGui.QApplication.translate("MainWindow", "stop", None, QtGui.QApplication.UnicodeUTF8))
        self.actionNuke.setText(QtGui.QApplication.translate("MainWindow", "nuke", None, QtGui.QApplication.UnicodeUTF8))

