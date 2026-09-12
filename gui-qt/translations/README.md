# Translations

Qt Linguist files for the control panel. Every user-visible string in
`qml/` goes through `qsTr()`, and the Python vocabulary in
`archerqt/catalog.py`, `tray.py` and `controller.py` through
`QCoreApplication.translate()`.

Update the catalogue after changing strings:

    /usr/lib/qt6/bin/lupdate -recursive ../qml ../archerqt -ts archer_es.ts

Compile for shipping (the app loads `archer_<locale>.qm` from this
directory at startup, falling back to English):

    /usr/lib/qt6/bin/lrelease archer_es.ts
